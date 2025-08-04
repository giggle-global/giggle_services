from app.repositories.user import UserRepository
from app.models.user import UserCreate, UserUpdate, LoginRequest, RefreshRequest
from app.core.keycloak import create_user_in_keycloak, authenticate_with_keycloak, refresh_access_token
from app.core.config import config
import uuid
from fastapi import HTTPException

class UserService:
    def __init__(self, user_repo: UserRepository = None):
        self.user_repo = user_repo or UserRepository()

    def create_user(self, user: UserCreate) -> dict:
        user.user_id = str(uuid.uuid4())
        # 1. Prepare Keycloak payload
        keycloak_payload = {
            "username": user.user_id,
            "email": user.email,
            "firstName": user.name,
            "lastName": user.name,
            "enabled": True,
            "emailVerified": True, 
            "credentials": [
                {"type": "password", "value": user.passcode, "temporary": False}
            ],
            "attributes": {
                "role": user.role,
            }
        }
        # 2. Create in Keycloak
        keycloak_id = create_user_in_keycloak(keycloak_payload)

        # 3. Attach keycloak_id to user for Mongo
        user.keycloak_id = keycloak_id

        # 4. Save user to Mongo
        return self.user_repo.create_user(user)

    def get_user(self, user_id: str) -> dict:
        return self.user_repo.get_user_by_id(user_id)

    def update_user(self, user_id: str, user: UserUpdate) -> dict:
        return self.user_repo.update_user(user_id, user)

    def delete_user(self, user_id: str):
        return self.user_repo.delete_user(user_id)
    
    def user_login(self, data: LoginRequest) -> dict:
        data = authenticate_with_keycloak(username=data.username, passcode=data.password)
        return data
    
    def user_refresh(self, data: RefreshRequest) -> dict:
        data = refresh_access_token(refresh_token=data.refresh_token)
        return data
    
    def ban_user(self, user_id: str):
        user = self.user_repo.get_user_by_id(user_id)
        if not user:
            raise HTTPException(404, "User not found.")
        if user.get("status") == "BANNED":
            raise HTTPException(400, "User already banned.")
        return self.user_repo.ban_user(user_id)
    
    def create_root_user(self) -> dict:
        # Use values from config, not os.environ!
        root_email = config.user_name  # This is your superadmin email
        root_pass = config.passcode
        root_role = "SA"
        root_name = "Super Admin"

        # Check if root user exists (by email or role)
        existing = self.user_repo.collection.find_one({
            "$or": [{"email": root_email}, {"role": root_role}]
        })
        if existing:
            return {"detail": "Root user already exists."}
        
        user_id = str(uuid.uuid4())

        # Build Keycloak payload
        keycloak_payload = {
            "username": user_id,
            "email": root_email,
            "firstName": root_name,
            "lastName": root_name,
            "enabled": True,
            "emailVerified": True, 
            "credentials": [
                {"type": "password", "value": root_pass, "temporary": False}
            ],
            "attributes": {
                "role": root_role,
            }
        }
        # Create in Keycloak
        keycloak_id = create_user_in_keycloak(keycloak_payload)

        # Build Mongo user object
        user = UserCreate(
            user_id=user_id,
            name=root_name,
            email=root_email,
            phone_number="9999999999",
            status="ACTIVE",
            passcode=root_pass,
            role=root_role,
            keycloak_id=keycloak_id,
            registration_type="admin"
        )

        created = self.user_repo.create_user(user)
        return created
