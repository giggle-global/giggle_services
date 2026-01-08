# app/services/user.py
from datetime import timedelta, datetime, timezone
# IST is UTC+5:30
IST = timezone(timedelta(hours=5, minutes=30))
import random
import uuid
import logging
from typing import Dict, Any, Optional, List

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.user import UserRepository
from app.models.user import UserCreate, UserUpdate, LoginRequest, RefreshRequest
from app.services.token import TokenService
from app.core.keycloak import (
    create_user_in_keycloak,
    authenticate_with_keycloak,
    refresh_access_token,
    delete_user_in_keycloak,  # <-- implement this in your keycloak module
    get_client_access_token,
    set_user_password,
    update_user_in_keycloak,
)
from app.core.config import config

from app.services.skill import SkillService
from app.models.skill import UserSkillEntry
from app.core.general import generate_random_name

from app.core.db import database

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()
        self.token_service = TokenService()
        self.skill_service = SkillService()

    # ---------- Helpers ----------
    def _ensure_unique_email(self, email: str) -> None:
        """Raise 409 if email already exists."""
        try:
            existing = self.user_repo.get_user_by_email(email)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                existing = None
            else:
                raise
        except AttributeError:
            existing = self.user_repo.collection.find_one({"email": email})
        if existing:
            logger.warning("Email already exists: %s", email)
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")
        
    def create_user(self, user: UserCreate) -> Dict[str, Any]:
        # Basic validation
        if not user.email or not user.passcode:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email and password are required")
        if user.role == "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot create super admin users")

        # Ensure email unique in our DB first
        self._ensure_unique_email(user.email)

        # Track referral information
        referral_info = None
        referring_client_id = None

        # If freelancer signup, require and validate token
        if user.role == "FL":
            signup_token = getattr(user, "signup_token", None)
            if not signup_token:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "Missing signup token for freelancer signup")

            logger.debug("Validating signup token: %s", signup_token)
            # call instance method correctly (positional arg)
            try:
                token_record = self.token_service.validate_token_for_signup(token=signup_token, target_user_role="FL")
                referring_freelancer_id = token_record.get("generated_by")
                referral_info = {
                    "referred_by": referring_freelancer_id,
                    "referred_at": datetime.now(timezone.utc),
                    "invite_code": signup_token
                }
                logger.info("Freelancer signup with referral: new_freelancer=%s referred_by=%s", user.email, referring_freelancer_id)
            except HTTPException as exc:
                logger.warning("Signup token validation failed: %s", exc.detail)
                raise
        
        # If client signup, validate token if provided (optional for clients)
        elif user.role == "CL":
            signup_token = getattr(user, "signup_token", None)
            if signup_token:
                logger.debug("Validating client signup token: %s", signup_token)
                try:
                    token_record = self.token_service.validate_token_for_signup(token=signup_token, target_user_role="CL")
                    referring_client_id = token_record.get("generated_by")
                    referral_info = {
                        "referred_by": referring_client_id,
                        "referred_at": datetime.now(timezone.utc),
                        "invite_code": signup_token
                    }
                    logger.info("Client signup with referral: new_client=%s referred_by=%s", user.email, referring_client_id)
                except HTTPException as exc:
                    logger.warning("Client signup token validation failed: %s", exc.detail)
                    raise

        # create user ids etc
        user.user_id = user.user_id or str(uuid.uuid4())

        keycloak_payload = {
            "username": user.user_id,
            "email": user.email,
            "firstName": getattr(user, "first_name", user.first_name or ""),
            "lastName": getattr(user, "last_name", None),
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": user.passcode, "temporary": False}],
            "attributes": {"role": user.role},
        }

        # Create in Keycloak: acquire admin token then call creation function
        keycloak_id = None
        try:
            logger.debug("Acquiring Keycloak admin token to create user")
            # kc_token = get_client_access_token()  # returns a token string
            logger.debug("Creating user in Keycloak: %s", {"username": user.user_id, "email": user.email})
            # Note: create_user_in_keycloak(token, payload) expected signature
            keycloak_id = create_user_in_keycloak(keycloak_payload)
            user.username = generate_random_name()
            user.keycloak_id = keycloak_id
            user.kyc = False  # default KYC to False on creation
            user.first_intro_done = False
            user.update_cool_down_period = 5
            try:
                token = get_client_access_token()
                set_user_password(token, keycloak_id, user.passcode, temporary=False)
            except Exception:
                logger.exception("Failed to ensure Keycloak password for email=%s", user.email)

        except HTTPException:
            logger.exception("Keycloak creation failed for email=%s", user.email)
            raise
        except Exception as e:
            logger.exception("Keycloak creation failed (unexpected) for email=%s: %s", user.email, e)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Identity provider error: {e}")

        # Persist to Mongo; if DB fails, rollback Keycloak
        created = None
        try:
            logger.debug("Persisting user to Mongo: user_id=%s email=%s", user.user_id, user.email)
            print("User data to be created:", user.model_dump())
            created = self.user_repo.create_user(user)
            logger.info("User created in DB: user_id=%s email=%s", user.user_id, user.email)
        except PyMongoError as e:
            logger.exception("Mongo error on user create; attempting Keycloak rollback. user_id=%s", user.user_id)
            try:
                if keycloak_id:
                    delete_user_in_keycloak(keycloak_id)
                    logger.info("Rolled back Keycloak user: keycloak_id=%s", keycloak_id)
            except Exception:
                logger.exception("Failed to roll back Keycloak user keycloak_id=%s", keycloak_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to save user")

        # Store referral info in user's record immediately after creation (for both clients and freelancers)
        if referral_info and created:
            try:
                # Convert datetime to ISO string for storage
                referral_info_to_store = {
                    "referred_by": referral_info["referred_by"],
                    "referred_at": referral_info["referred_at"].isoformat() if isinstance(referral_info["referred_at"], datetime) else str(referral_info["referred_at"]),
                    "invite_code": referral_info["invite_code"]
                }
                logger.info("Storing referral info for new user %s: %s", created["user_id"], referral_info_to_store)
                self.user_repo.update_user(
                    user_id=created["user_id"],
                    update_payload={"referral_info": referral_info_to_store}
                )
                logger.info("Successfully stored referral info for new user %s", created["user_id"])
            except Exception as e:
                logger.exception("Failed to store referral info for new user %s: %s", created["user_id"], e)
                # Don't fail the signup, just log the error

        # If client signup with referral, consume token and grant benefit to referring client
        if user.role == "CL" and referral_info:
            try:
                signup_token = referral_info["invite_code"]
                logger.debug("Consuming client signup token '%s' for new client %s", signup_token, created["user_id"])
                consumed = self.token_service.consume_token(signup_token, created["user_id"])
                logger.info("Client signup token consumed: %s -> used_by=%s", signup_token, created["user_id"])
                
                # Update referring client: grant free gig fee benefit
                try:
                    referring_client = self.user_repo.get_user_by_id(referring_client_id)
                    if referring_client:
                        # Initialize referral tracking if not exists
                        referral_tracking = referring_client.get("referral_tracking", {})
                        referrals_made = referral_tracking.get("referrals_made", [])
                        
                        # Convert datetime to ISO string for storage
                        referred_at_str = referral_info["referred_at"]
                        if isinstance(referred_at_str, datetime):
                            referred_at_str = referred_at_str.isoformat()
                        elif not isinstance(referred_at_str, str):
                            referred_at_str = str(referred_at_str)
                        
                        referrals_made.append({
                            "referred_user_id": created["user_id"],
                            "referred_at": referred_at_str,
                            "invite_code": signup_token
                        })
                        
                        # Grant free gig fee benefit (next gig fee will be free)
                        referral_tracking["has_free_gig_fee"] = True
                        referral_tracking["referrals_made"] = referrals_made
                        referral_tracking["last_referral_at"] = referred_at_str
                        
                        # Update referring client with referral tracking
                        self.user_repo.update_user(
                            user_id=referring_client_id,
                            update_payload={"referral_tracking": referral_tracking}
                        )
                        logger.info("Granted free gig fee benefit to referring client: %s", referring_client_id)
                except Exception as e:
                    logger.exception("Failed to grant referral benefit to client %s: %s", referring_client_id, e)
                    # Don't fail the signup if benefit granting fails, just log it
                
                # Store referral info in new client's record
                try:
                    # Convert datetime to ISO string for storage
                    referral_info_to_store = {
                        "referred_by": referral_info["referred_by"],
                        "referred_at": referral_info["referred_at"].isoformat() if isinstance(referral_info["referred_at"], datetime) else str(referral_info["referred_at"]),
                        "invite_code": referral_info["invite_code"]
                    }
                    self.user_repo.update_user(
                        user_id=created["user_id"],
                        update_payload={"referral_info": referral_info_to_store}
                    )
                except Exception as e:
                    logger.exception("Failed to store referral info for new client %s: %s", created["user_id"], e)
                    
            except HTTPException as exc:
                # Token consumption failed - rollback
                logger.exception("Failed to consume client signup token after DB create; performing rollback. token=%s", signup_token)
                try:
                    self.user_repo.delete_user(created["user_id"])
                    logger.info("Rolled back DB user: user_id=%s", created["user_id"])
                except Exception:
                    logger.exception("Failed to roll back DB user: user_id=%s", created["user_id"])
                try:
                    if keycloak_id:
                        delete_user_in_keycloak(keycloak_id)
                        logger.info("Rolled back Keycloak user after token consume failure: keycloak_id=%s", keycloak_id)
                except Exception:
                    logger.exception("Failed to roll back Keycloak user after token consume failure: keycloak_id=%s", keycloak_id)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invite code invalid or already used: {exc.detail}")

        # If freelancer signup with referral, consume token and grant benefit to referring freelancer
        elif user.role == "FL" and referral_info:
            try:
                signup_token = referral_info["invite_code"]
                logger.debug("Consuming freelancer signup token '%s' for new freelancer %s", signup_token, created["user_id"])
                consumed = self.token_service.consume_token(signup_token, created["user_id"])
                logger.info("Freelancer signup token consumed: %s -> used_by=%s", signup_token, created["user_id"])
                
                # Update referring freelancer: grant referral tracking
                try:
                    referring_freelancer = self.user_repo.get_user_by_id(referring_freelancer_id)
                    if referring_freelancer:
                        # Initialize referral tracking if not exists
                        referral_tracking = referring_freelancer.get("referral_tracking", {})
                        referrals_made = referral_tracking.get("referrals_made", [])
                        
                        # Convert datetime to ISO string for storage
                        referred_at_str = referral_info["referred_at"]
                        if isinstance(referred_at_str, datetime):
                            referred_at_str = referred_at_str.isoformat()
                        elif not isinstance(referred_at_str, str):
                            referred_at_str = str(referred_at_str)
                        
                        referrals_made.append({
                            "referred_user_id": created["user_id"],
                            "referred_at": referred_at_str,
                            "invite_code": signup_token
                        })
                        
                        # Update referral tracking
                        referral_tracking["referrals_made"] = referrals_made
                        referral_tracking["last_referral_at"] = referred_at_str
                        
                        # Update referring freelancer with referral tracking
                        self.user_repo.update_user(
                            user_id=referring_freelancer_id,
                            update_payload={"referral_tracking": referral_tracking}
                        )
                        logger.info("Added referral tracking to referring freelancer: %s", referring_freelancer_id)
                except Exception as e:
                    logger.exception("Failed to add referral tracking to freelancer %s: %s", referring_freelancer_id, e)
                    # Don't fail the signup if tracking fails, just log it
                    
            except HTTPException as exc:
                # Token consumption failed - rollback
                logger.exception("Failed to consume freelancer signup token after DB create; performing rollback. token=%s", signup_token)
                try:
                    self.user_repo.delete_user(created["user_id"])
                    logger.info("Rolled back DB user: user_id=%s", created["user_id"])
                except Exception:
                    logger.exception("Failed to roll back DB user: user_id=%s", created["user_id"])
                try:
                    if keycloak_id:
                        delete_user_in_keycloak(keycloak_id)
                        logger.info("Rolled back Keycloak user after token consume failure: keycloak_id=%s", keycloak_id)
                except Exception:
                    logger.exception("Failed to roll back Keycloak user after token consume failure: keycloak_id=%s", keycloak_id)
                raise HTTPException(status.HTTP_400_BAD_REQUEST, f"Invite code invalid or already used: {exc.detail}")

        # Remove sensitive data before returning (like passcode)
        if created and "passcode" in created:
            created.pop("passcode", None)

        return created

    def reset_password(self, email: str, new_password: str) -> None:
        if not email or not new_password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email and new password are required")

        try:
            user = self.user_repo.get_user_by_email(email)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_404_NOT_FOUND:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            raise

        keycloak_id = user.get("keycloak_id")
        if not keycloak_id:
            logger.error("Unable to reset password, keycloak_id missing for email=%s", email)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "User identity is not configured correctly")

        try:
            token = get_client_access_token()
            set_user_password(token, keycloak_id, new_password, temporary=False)
            logger.info("Password reset successful for email=%s", email)
        except HTTPException:
            raise
        except Exception as exc:
            logger.exception("Password reset failed for email=%s", email)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"Failed to reset password: {exc}")

    def get_user(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            return user
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error fetching user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch user")

    def get_user_profile_admin(self, user_id: str) -> Dict[str, Any]:
        """Admin method to get user profile including deleted users"""
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id_admin(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            return user
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Error fetching user profile for admin user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch user profile")

    def list_freelancer(self) -> Any:
        try:
            return self.user_repo.get_freelancers()
        except Exception as e:
            logger.exception("Error listing freelancers: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch freelancers")
        
    def list_all_users(self) -> Any:
        try:
            users = self.user_repo.get_all_users()
            # Add project count for each user
            from app.core.db import database
            project_collection = database["projects"]
            request_collection = database["chat_requests"]
            
            for user in users:
                user_id = user.get("user_id")
                role = user.get("role")
                project_count = 0
                
                if role == "CL":
                    # For clients: count unique projects from created projects and agreements
                    agreement_collection = database["agreements"]
                    
                    # Get distinct project_ids from projects where client created them
                    created_projects = set(project_collection.distinct("id", {
                        "client_id": user_id
                    }))
                    
                    # Get distinct project_ids from agreements where client is involved
                    agreement_projects = set(agreement_collection.distinct("project_id", {
                        "client.user_id": user_id
                    }))
                    
                    # Combine both sets to get unique project count
                    all_projects = created_projects.union(agreement_projects)
                    project_count = len(all_projects)
                elif role == "FL":
                    # For freelancers: count unique projects from requests and agreements
                    agreement_collection = database["agreements"]
                    
                    # Get distinct project_ids from requests where freelancer is involved (only accepted, not pending)
                    request_projects = set(request_collection.distinct("project_id", {
                        "freelancer_id": user_id,
                        "status": "accepted"
                    }))
                    
                    # Get distinct project_ids from agreements where freelancer is involved
                    agreement_projects = set(agreement_collection.distinct("project_id", {
                        "freelancer.user_id": user_id
                    }))
                    
                    # Combine both sets to get unique project count
                    all_projects = request_projects.union(agreement_projects)
                    project_count = len(all_projects)
                
                user["project_count"] = project_count
            
            return users
        except Exception as e:
            logger.exception("Error listing freelancers: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch freelancers")
        
    def update_user(self, user_id: str, user_data: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        if not user_data:
            raise HTTPException(status_code=400, detail="No data to update")

        # Role-based enforcement: if the user is NOT a 'client', drop company/contact info
        role = current_user.get("role")
        print("user_data before role check:", user_data)
        if role != "CL":
            user_data.pop("contact_info", None)
            user_data.pop("company_info", None)

        # Optional: whitelist allowed fields to avoid accidental writes
        allowed_fields = {
            "first_name", "last_name", "email", "phone_number", "bio",
            "designation", "experience_years", "experience_months", "profile_pic",
            "language_preference", "skill_set", "contact_info", "company_info", "payment_information", "notification_service", "kyc", "first_intro_done",
            "user_settings", "location_info", "interested_industries", "ongoing_gigs_count", "availability", "is_affiliate"
        }
        update_payload = {k: v for k, v in user_data.items() if k in allowed_fields}

        protected = ["first_name", "last_name", "username", "email", "phone_number"]

        # update_payload is a dict
        if any(k in update_payload for k in protected): 
            user_details = self.user_repo.get_user_by_id(user_id)
            if user_details:
                days_to_wait = user_details.get("update_cool_down_period", 5)
                last_edit_date = user_details.get("first_edit_date")  # Using first_edit_date to track last edit
                
                # If last_edit_date exists, check cooldown from last edit
                if last_edit_date:
                    # Convert to timezone-aware IST datetime
                    # Handle string, datetime, or MongoDB datetime
                    if isinstance(last_edit_date, str):
                        # Handle both 'Z' and '+00:00' ISO 8601 formats
                        iso_string = last_edit_date.replace('Z', '+00:00') if last_edit_date.endswith('Z') else last_edit_date
                        last_edit_date = datetime.fromisoformat(iso_string)
                    
                    # Convert to IST (handle both UTC and IST stored values)
                    if last_edit_date.tzinfo is None:
                        # Assume UTC if naive, then convert to IST
                        last_edit_date = last_edit_date.replace(tzinfo=timezone.utc).astimezone(IST)
                    elif last_edit_date.tzinfo == timezone.utc:
                        # Convert from UTC to IST
                        last_edit_date = last_edit_date.astimezone(IST)
                    # If already in IST, use as is
                    
                    next_allowed_update = last_edit_date + timedelta(days=days_to_wait)
                    now = datetime.now(timezone.utc).astimezone(IST)  # Current time in IST
                    
                    if now < next_allowed_update:
                        days_remaining = (next_allowed_update - now).days + 1
                        raise HTTPException(status_code=403, detail=f"User details can be updated only after {days_to_wait} days from the last edit. Please wait {days_remaining} more day(s).")
                
                # Set/update first_edit_date in the update payload after successful cooldown check
                # This will be the new "last edit date" after this update completes
                # Store in IST (UTC+5:30) - convert from UTC
                utc_now = datetime.now(timezone.utc)
                ist_now = utc_now.astimezone(IST)
                update_payload["first_edit_date"] = ist_now

        try:
            updated = self.user_repo.update_user(user_id=user_id, update_payload=update_payload)
            if not updated:
                raise HTTPException(status_code=404, detail="User not found")
            logger.info("User updated: user_id=%s", user_id)
            return updated
        except PyMongoError:
            logger.exception("Mongo error updating user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Failed to update user")
        except HTTPException:
            raise
        except Exception:
            logger.exception("Unexpected error updating user_id=%s", user_id)
            raise HTTPException(status_code=500, detail="Failed to update user")
        
    def update_user_skills(self, user_id: str, entries: List[UserSkillEntry], current_user: dict):
        """
        current_user used to authorize (user can update own skills or admin can update others)
        """
        # authorization: allow user to update their own skills or SA
        if current_user["user_id"] != user_id and current_user.get("role") != "SA":
            raise HTTPException(403, "Not authorized to update skills for this user")

        validated = self.skill_service.validate_user_skill_entries(entries)
        # store validated list in user's 'skill_set' field
        updated = self.user_repo.update_user_skills(user_id, validated)
        return updated

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            deleted = self.user_repo.delete_user(user_id)
            # if not deleted:
            #     print("User not found")
            #     raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            # logger.info("User deleted: user_id=%s", user_id)
            return {"detail": "User deleted"}
        except HTTPException:
            raise
        except PyMongoError:
            logger.exception("Mongo error deleting user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to delete user")
        except Exception:
            logger.exception("Unexpected error deleting user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to delete user")

    # ---------- Auth ----------
    def user_login(self, data: LoginRequest) -> Dict[str, Any]:
        if not data.email or not data.password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "username and password are required")
        try:
            logger.debug("Keycloak auth attempt for username=%s", data.email)
            tokens = authenticate_with_keycloak(username=data.email, passcode=data.password)
            logger.info("Login success for username=%s", data.email)
            print("Tokens obtained:", tokens)
            return tokens
        except HTTPException:
            # your keycloak client can raise 401/403; bubble up
            logger.warning("Login failed for username=%s", data.email)
            raise
        except Exception as e:
            logger.exception("Keycloak auth error for username=%s", data.email)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Identity provider error: {e}")

    def user_refresh(self, data: RefreshRequest) -> Dict[str, Any]:
        if not data.refresh_token:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "refresh_token is required")
        try:
            logger.debug("Refreshing token")
            tokens = refresh_access_token(refresh_token=data.refresh_token)
            logger.info("Token refreshed")
            return tokens
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Keycloak refresh error")
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Identity provider error: {e}")

    # ---------- Admin ----------
    def ban_user(self, user_id: str, reason: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
            if user.get("status") == "BANNED":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "User already banned.")
            result = self.user_repo.ban_user(user_id, reason)
            logger.info("User banned: user_id=%s", user_id)
            return result
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error banning user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to ban user")

    def unban_user(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
            if user.get("status") != "BANNED":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "User is not banned.")
            result = self.user_repo.unban_user(user_id)
            logger.info("User unbanned: user_id=%s", user_id)
            return result
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error unbanning user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to unban user")

    def affiliate(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
            result = self.user_repo.affiliate(user_id)
            logger.info("Affiliate status toggled: user_id=%s, is_affiliate=%s", user_id, result.get("is_affiliate"))
            return result
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error toggling affiliate status for user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to toggle affiliate status")

    def create_root_user(self) -> Dict[str, Any]:
        """Idempotent super admin bootstrap. Also updates email and password if user exists."""
        root_email = config.user_name
        root_pass = config.passcode
        root_role = "SA"
        root_name = "Super Admin"

        try:
            # check by email OR role to avoid duplicates
            existing = self.user_repo.collection.find_one({"$or": [{"email": root_email}, {"role": root_role}]})
            if existing:
                existing_email = existing.get("email")
                keycloak_id = existing.get("keycloak_id")
                user_id = existing.get("user_id")
                
                logger.info("Root user already exists: existing_email=%s, new_email=%s", existing_email, root_email)
                
                if keycloak_id:
                    try:
                        token = get_client_access_token()
                        
                        # Update email in Keycloak if it changed
                        if existing_email != root_email:
                            logger.info("Root user email changed from %s to %s, updating in Keycloak", existing_email, root_email)
                            update_data = {
                                "email": root_email,
                                "emailVerified": True
                            }
                            update_user_in_keycloak(token, keycloak_id, update_data)
                            
                            # Update email in MongoDB
                            if user_id:
                                self.user_repo.collection.update_one(
                                    {"user_id": user_id},
                                    {"$set": {"email": root_email}}
                                )
                                logger.info("Root user email updated in MongoDB: user_id=%s", user_id)
                        
                        # Always update password in Keycloak (sync with .env)
                        set_user_password(token, keycloak_id, root_pass, temporary=False)
                        logger.info("Root user password updated in Keycloak: email=%s", root_email)
                    except Exception as e:
                        logger.error("Failed to update root user in Keycloak: %s", str(e), exc_info=True)
                        # Don't fail the startup if update fails, but log the error
                else:
                    logger.warning("Root user exists but has no keycloak_id, cannot update credentials")
                
                return {"detail": "Root user already exists."}

            user_id = str(uuid.uuid4())
            keycloak_payload = {
                "username": user_id,
                "email": root_email,
                "firstName": root_name,
                "lastName": root_name,
                "enabled": True,
                "emailVerified": True,
                "credentials": [{"type": "password", "value": root_pass, "temporary": False}],
                "attributes": {"role": root_role},
            }

            logger.debug("Creating root user in Keycloak: email=%s", root_email)
            keycloak_id = create_user_in_keycloak(keycloak_payload)

            user = UserCreate(
                user_id=user_id,
                first_name=root_name,
                last_name=root_name,
                username=user_id,
                name=root_name,
                email=root_email,
                phone_number="9999999999",
                status="ACTIVE",
                passcode=root_pass,
                role=root_role,
                keycloak_id=keycloak_id,
                registration_type="admin",
            )

            created = self.user_repo.create_user(user)
            logger.info("Root user created/ensured: email=%s user_id=%s", root_email, user_id)
            return created

        except PyMongoError as e:
            logger.exception("Mongo error creating root user")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create root user")
        except HTTPException:
            raise
        except Exception as e:
            logger.exception("Unexpected error creating root user")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create root user")

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get admin dashboard statistics"""
        try:
            user_collection = database["user"]
            agreement_collection = database["agreements"]
            ticket_collection = database["tickets"]
            
            # KPI Cards
            total_users = user_collection.count_documents({})
            banned_accounts = user_collection.count_documents({"status": "BANNED"})
            active_projects = agreement_collection.count_documents({"status": "Active"})
            resolved_disputes = ticket_collection.count_documents({"status": {"$in": ["resolved", "closed"]}})
            
            # Dispute Resolution Chart
            ongoing_disputes = ticket_collection.count_documents({"status": {"$in": ["open", "in_progress", "reopened"]}})
            total_disputes = resolved_disputes + ongoing_disputes
            dispute_resolution_data = {
                "ongoing": ongoing_disputes,
                "resolved": resolved_disputes,
                "total_users": total_disputes
            }
            
            # Project Activity Chart (All 12 months of current year, with data only for months that have occurred)
            now = datetime.utcnow()
            current_year = now.year
            project_activity_data = {"freelancer": [], "clients": []}
            months = []
            
            # Get all 12 months of the current year
            for month_num in range(1, 13):
                month_start = datetime(current_year, month_num, 1)
                
                # Calculate month end (start of next month)
                if month_num == 12:
                    month_end = datetime(current_year + 1, 1, 1)
                else:
                    month_end = datetime(current_year, month_num + 1, 1)
                
                month_name = month_start.strftime("%b").upper()
                months.append(month_name)
                
                # Only query data for months that have occurred (up to current month)
                if month_num <= now.month:
                    # Count agreements created in this month
                    # Both client and freelancer activity represent agreements created in that month
                    # Client activity: Agreements created (clients initiate agreements)
                    # Freelancer activity: Agreements involving freelancers (all agreements have freelancers)
                    total_agreements = agreement_collection.count_documents({
                        "created_at": {"$gte": month_start, "$lt": month_end}
                    })
                    
                    # For now, both show the same count (total agreements created)
                    # This represents project activity from both perspectives:
                    # - Clients: How many agreements they created
                    # - Freelancers: How many agreements they're involved in
                    client_count = total_agreements
                    freelancer_count = total_agreements
                else:
                    # Future months get 0
                    client_count = 0
                    freelancer_count = 0
                
                project_activity_data["freelancer"].append(freelancer_count)
                project_activity_data["clients"].append(client_count)
            
            # Dispute Frequency Chart
            dispute_frequency_weekly = []
            dispute_frequency_monthly = []
            dispute_frequency_yearly = []
            
            # Weekly (last 7 days) - use timeline first entry timestamp
            for i in range(6, -1, -1):
                target_date = now - timedelta(days=i)
                day_start = datetime(target_date.year, target_date.month, target_date.day, 0, 0, 0)
                day_end = datetime(target_date.year, target_date.month, target_date.day, 23, 59, 59)
                # Tickets use timeline[0].timestamp for creation date
                count = ticket_collection.count_documents({
                    "timeline.0.timestamp": {"$gte": day_start, "$lte": day_end}
                })
                dispute_frequency_weekly.append(count)
            
            # Monthly (last 4 weeks)
            for i in range(3, -1, -1):
                week_start_date = now - timedelta(days=(i * 7))
                week_start = datetime(week_start_date.year, week_start_date.month, week_start_date.day, 0, 0, 0)
                week_end_date = week_start_date + timedelta(days=7)
                week_end = datetime(week_end_date.year, week_end_date.month, week_end_date.day, 23, 59, 59)
                count = ticket_collection.count_documents({
                    "timeline.0.timestamp": {"$gte": week_start, "$lte": week_end}
                })
                dispute_frequency_monthly.append(count)
            
            # Yearly (all 12 months of current year, with data only for months that have occurred)
            current_year = now.year
            for month_num in range(1, 13):
                month_start = datetime(current_year, month_num, 1)
                
                # Calculate month end (start of next month)
                if month_num == 12:
                    month_end = datetime(current_year + 1, 1, 1)
                else:
                    month_end = datetime(current_year, month_num + 1, 1)
                
                # Only query data for months that have occurred (up to current month)
                if month_num <= now.month:
                    count = ticket_collection.count_documents({
                        "timeline.0.timestamp": {"$gte": month_start, "$lt": month_end}
                    })
                else:
                    # Future months get 0
                    count = 0
                
                dispute_frequency_yearly.append(count)
            
            return {
                "kpis": {
                    "total_users": total_users,
                    "active_projects": active_projects,
                    "resolved_disputes": resolved_disputes,
                    "banned_accounts": banned_accounts
                },
                "project_activity": {
                    "months": months,
                    "freelancer": project_activity_data["freelancer"],
                    "clients": project_activity_data["clients"]
                },
                "dispute_resolution": dispute_resolution_data,
                "dispute_frequency": {
                    "weekly": dispute_frequency_weekly,
                    "monthly": dispute_frequency_monthly,
                    "yearly": dispute_frequency_yearly
                }
            }
        except Exception as e:
            logger.exception("Error fetching dashboard stats")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch dashboard statistics")

    def get_freelancer_dashboard_stats(self, freelancer_id: str, metric_type: Optional[str] = None, quarter: Optional[str] = None) -> Dict[str, Any]:
        """Get freelancer dashboard statistics"""
        try:
            agreement_collection = database["agreements"]
            request_collection = database["chat_requests"]
            now = datetime.utcnow()
            
            # Current month range
            current_month_start = datetime(now.year, now.month, 1)
            if now.month == 12:
                current_month_end = datetime(now.year + 1, 1, 1)
            else:
                current_month_end = datetime(now.year, now.month + 1, 1)
            
            # Previous month range
            if now.month == 1:
                previous_month_start = datetime(now.year - 1, 12, 1)
                previous_month_end = datetime(now.year, 1, 1)
            else:
                previous_month_start = datetime(now.year, now.month - 1, 1)
                previous_month_end = datetime(now.year, now.month, 1)
            
            # Active Projects - agreements where freelancer is involved and status is Active
            active_projects = agreement_collection.count_documents({
                "freelancer.user_id": freelancer_id,
                "status": "Active"
            })
            
            # Completed Projects - agreements where freelancer is involved and status is Completed
            completed_projects = agreement_collection.count_documents({
                "freelancer.user_id": freelancer_id,
                "status": "Completed"
            })
            
            # Project Requests - requests where freelancer is the recipient
            project_requests = request_collection.count_documents({
                "freelancer_id": freelancer_id,
                "status": {"$in": ["pending", "accepted"]}
            })
            
            # Calculate trends (current month vs previous month)
            # Active Projects trend
            active_current_month = agreement_collection.count_documents({
                "freelancer.user_id": freelancer_id,
                "status": "Active",
                "created_at": {"$gte": current_month_start, "$lt": current_month_end}
            })
            active_previous_month = agreement_collection.count_documents({
                "freelancer.user_id": freelancer_id,
                "status": "Active",
                "created_at": {"$gte": previous_month_start, "$lt": previous_month_end}
            })
            active_trend = self._calculate_percentage_change(active_previous_month, active_current_month)
            
            # Project Requests trend
            requests_current_month = request_collection.count_documents({
                "freelancer_id": freelancer_id,
                "created_at": {"$gte": int(current_month_start.timestamp()), "$lt": int(current_month_end.timestamp())}
            })
            requests_previous_month = request_collection.count_documents({
                "freelancer_id": freelancer_id,
                "created_at": {"$gte": int(previous_month_start.timestamp()), "$lt": int(previous_month_end.timestamp())}
            })
            requests_trend = self._calculate_percentage_change(requests_previous_month, requests_current_month)
            
            # Earning - set to 0 for now (logic will be updated later)
            total_earning = 0
            earning_trend = None
            
            result = {
                "active_projects": {
                    "count": active_projects,
                    "trend": active_trend
                },
                "completed_projects": {
                    "count": completed_projects,
                    "trend": None  # No trend for completed projects
                },
                "project_requests": {
                    "count": project_requests,
                    "trend": requests_trend
                },
                "earning": {
                    "amount": total_earning,
                    "trend": earning_trend
                }
            }
            
            # Add chart data if metric_type and quarter are provided
            if metric_type and quarter:
                chart_data = self._get_chart_data(freelancer_id, metric_type, quarter, agreement_collection, request_collection)
                result["chart_data"] = chart_data
            
            return result
        except Exception as e:
            logger.exception("Error fetching freelancer dashboard stats")
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch freelancer dashboard statistics")
    
    def _get_chart_data(self, freelancer_id: str, metric_type: str, quarter: str, agreement_collection, request_collection) -> Dict[str, Any]:
        """Get chart data for a specific metric and quarter"""
        try:
            # Determine year (use current year)
            now = datetime.utcnow()
            year = now.year
            
            # Map quarter to months
            quarter_months = {
                "Q1": [(year, 1), (year, 2), (year, 3)],  # Jan-Mar
                "Q2": [(year, 4), (year, 5), (year, 6)],  # Apr-Jun
                "Q3": [(year, 7), (year, 8), (year, 9)],  # Jul-Sep
                "Q4": [(year, 10), (year, 11), (year, 12)]  # Oct-Dec
            }
            
            # Map quarter to previous quarter's last month
            previous_quarter_last_month = {
                "Q1": (year - 1, 12),  # Dec of previous year
                "Q2": (year, 3),      # Mar
                "Q3": (year, 6),      # Jun
                "Q4": (year, 9)       # Sep
            }
            
            if quarter not in quarter_months:
                return {"months": [], "values": []}
            
            # All 12 months for x-axis
            month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
            
            # Initialize values array with zeros for all 12 months
            values = [0] * 12
            
            # Get previous quarter's last month data point
            prev_year, prev_month = previous_quarter_last_month[quarter]
            prev_month_start = datetime(prev_year, prev_month, 1)
            if prev_month == 12:
                prev_month_end = datetime(prev_year + 1, 1, 1)
            else:
                prev_month_end = datetime(prev_year, prev_month + 1, 1)
            
            # Calculate value for previous quarter's last month
            prev_month_value = 0
            if metric_type == "active-projects":
                prev_month_value = agreement_collection.count_documents({
                    "freelancer.user_id": freelancer_id,
                    "status": "Active",
                    "created_at": {"$gte": prev_month_start, "$lt": prev_month_end}
                })
            elif metric_type == "completed-projects":
                prev_month_value = agreement_collection.count_documents({
                    "freelancer.user_id": freelancer_id,
                    "status": "Completed",
                    "created_at": {"$gte": prev_month_start, "$lt": prev_month_end}
                })
            elif metric_type == "project-requests":
                prev_month_value = request_collection.count_documents({
                    "freelancer_id": freelancer_id,
                    "created_at": {"$gte": int(prev_month_start.timestamp()), "$lt": int(prev_month_end.timestamp())}
                })
            elif metric_type == "earnings":
                # Set to 0 for now (logic will be updated later)
                prev_month_value = 0
            
            # Get selected quarter months
            months = quarter_months[quarter]
            
            # Populate values for selected quarter months
            for year_num, month_num in months:
                month_start = datetime(year_num, month_num, 1)
                if month_num == 12:
                    month_end = datetime(year_num + 1, 1, 1)
                else:
                    month_end = datetime(year_num, month_num + 1, 1)
                
                month_index = month_num - 1  # 0-based index for array
                
                if metric_type == "active-projects":
                    count = agreement_collection.count_documents({
                        "freelancer.user_id": freelancer_id,
                        "status": "Active",
                        "created_at": {"$gte": month_start, "$lt": month_end}
                    })
                    values[month_index] = count
                elif metric_type == "completed-projects":
                    count = agreement_collection.count_documents({
                        "freelancer.user_id": freelancer_id,
                        "status": "Completed",
                        "created_at": {"$gte": month_start, "$lt": month_end}
                    })
                    values[month_index] = count
                elif metric_type == "project-requests":
                    count = request_collection.count_documents({
                        "freelancer_id": freelancer_id,
                        "created_at": {"$gte": int(month_start.timestamp()), "$lt": int(month_end.timestamp())}
                    })
                    values[month_index] = count
                elif metric_type == "earnings":
                    # Set to 0 for now (logic will be updated later)
                    values[month_index] = 0
            
            # Insert previous month value at the correct position
            prev_month_index = prev_month - 1  # 0-based index
            values[prev_month_index] = prev_month_value
            
            return {
                "months": month_names,
                "values": values,
                "previous_month_index": prev_month_index,
                "quarter_start_index": months[0][1] - 1  # First month of quarter (0-based)
            }
        except Exception as e:
            logger.exception("Error fetching chart data")
            return {"months": [], "values": []}
    
    def _calculate_percentage_change(self, previous: float, current: float) -> Optional[float]:
        """Calculate percentage change between previous and current values"""
        if previous == 0:
            return 100.0 if current > 0 else 0.0
        return round(((current - previous) / previous) * 100, 1)