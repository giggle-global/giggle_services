# app/services/user.py
import uuid
import logging
from typing import Dict, Any, Optional

from fastapi import HTTPException, status
from pymongo.errors import PyMongoError

from app.repositories.user import UserRepository
from app.models.user import UserCreate, UserUpdate, LoginRequest, RefreshRequest
from app.core.keycloak import (
    create_user_in_keycloak,
    authenticate_with_keycloak,
    refresh_access_token,
    delete_user_in_keycloak,  # <-- implement this in your keycloak module
)
from app.core.config import config

logger = logging.getLogger(__name__)


class UserService:
    def __init__(self, user_repo: Optional[UserRepository] = None):
        self.user_repo = user_repo or UserRepository()

    # ---------- Helpers ----------
    def _ensure_unique_email(self, email: str) -> None:
        """Raise 409 if email already exists."""
        try:
            existing = self.user_repo.get_user_by_email(email)  # implement in repo
        except AttributeError:
            # Fallback if repo doesn’t have it yet
            existing = self.user_repo.collection.find_one({"email": email})
        if existing:
            logger.warning("Email already exists: %s", email)
            raise HTTPException(status.HTTP_409_CONFLICT, "Email already in use")

    # ---------- CRUD ----------
    def create_user(self, user: UserCreate) -> Dict[str, Any]:
        if not user.email or not user.passcode:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email and password are required")
        if user.role == "SA":
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Cannot create super admin users")

        # Ensure email unique in our DB first
        self._ensure_unique_email(user.email)

        user.user_id = user.user_id or str(uuid.uuid4())
        keycloak_payload = {
            "username": user.user_id,
            "email": user.email,
            "firstName": user.first_name,
            "lastName": user.last_name,
            "enabled": True,
            "emailVerified": True,
            "credentials": [{"type": "password", "value": user.passcode, "temporary": False}],
            "attributes": {"role": user.role},
        }

        keycloak_id = None
        try:
            logger.debug("Creating user in Keycloak: %s", {"username": user.user_id, "email": user.email})
            keycloak_id = create_user_in_keycloak(keycloak_payload)
            user.keycloak_id = keycloak_id
        except HTTPException:
            # If your keycloak client already raises HTTPException, just bubble it.
            logger.exception("Keycloak creation failed for email=%s", user.email)
            raise
        except Exception as e:
            logger.exception("Keycloak creation failed (unexpected) for email=%s", user.email)
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Identity provider error: {e}")

        # Save to Mongo; roll back Keycloak if DB fails
        try:
            logger.debug("Persisting user to Mongo: user_id=%s email=%s", user.user_id, user.email)
            created = self.user_repo.create_user(user)
            logger.info("User created: user_id=%s email=%s", user.user_id, user.email)
            return created
        except PyMongoError as e:
            logger.exception("Mongo error on user create; attempting Keycloak rollback. user_id=%s", user.user_id)
            # Best effort rollback in Keycloak
            try:
                if keycloak_id:
                    delete_user_in_keycloak(keycloak_id)
                    logger.info("Rolled back Keycloak user: keycloak_id=%s", keycloak_id)
            except Exception:
                logger.error("Failed to roll back Keycloak user keycloak_id=%s", keycloak_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to save user")
        except Exception as e:
            logger.exception("Unexpected error on user create: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to create user")

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

    def list_freelancer(self) -> Any:
        try:
            return self.user_repo.get_freelancers()
        except Exception as e:
            logger.exception("Error listing freelancers: %s", e)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch freelancers")

    def update_user(self, user_id: str, user: UserUpdate) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            updated = self.user_repo.update_user(user_id, user)
            if not updated:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            logger.info("User updated: user_id=%s", user_id)
            return updated
        except HTTPException:
            raise
        except PyMongoError:
            logger.exception("Mongo error updating user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update user")
        except Exception:
            logger.exception("Unexpected error updating user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to update user")

    def delete_user(self, user_id: str) -> Dict[str, Any]:
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            deleted = self.user_repo.delete_user(user_id)
            if not deleted:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
            logger.info("User deleted: user_id=%s", user_id)
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
        if not data.username or not data.password:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "username and password are required")
        try:
            logger.debug("Keycloak auth attempt for username=%s", data.username)
            tokens = authenticate_with_keycloak(username=data.username, passcode=data.password)
            logger.info("Login success for username=%s", data.username)
            return tokens
        except HTTPException:
            # your keycloak client can raise 401/403; bubble up
            logger.warning("Login failed for username=%s", data.username)
            raise
        except Exception as e:
            logger.exception("Keycloak auth error for username=%s", data.username)
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
    def ban_user(self, user_id: str):
        if not user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "user_id is required")
        try:
            user = self.user_repo.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found.")
            if user.get("status") == "BANNED":
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "User already banned.")
            result = self.user_repo.ban_user(user_id)
            logger.info("User banned: user_id=%s", user_id)
            return result
        except HTTPException:
            raise
        except Exception:
            logger.exception("Error banning user_id=%s", user_id)
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to ban user")

    def create_root_user(self) -> Dict[str, Any]:
        """Idempotent super admin bootstrap."""
        root_email = config.user_name
        root_pass = config.passcode
        root_role = "SA"
        root_name = "Super Admin"

        try:
            # check by email OR role to avoid duplicates
            existing = self.user_repo.collection.find_one({"$or": [{"email": root_email}, {"role": root_role}]})
            if existing:
                logger.info("Root user already exists: email=%s", root_email)
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
