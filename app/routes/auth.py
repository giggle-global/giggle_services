# app/routers/auth.py  (your optimized router)
from fastapi import APIRouter, Depends
from starlette import status
from app.models.user import (
    UserCreate, UserUpdate, UserOut,
    TokenResponse, LoginRequest, RefreshRequest
)
from app.services.user import UserService
from app.schemas.response import APIResponse, ok
from app.core.exceptions import Forbidden

router = APIRouter(prefix="/auth", tags=["AUTHENTICATION"])

# --- Prefer DI for testability (easy to mock in tests) ---
def get_user_service() -> UserService:
    return UserService()

@router.post("/signup",
             response_model=APIResponse[UserOut],
             status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, svc: UserService = Depends(get_user_service)):
    if getattr(user, "role", None) == "SA":
        # This will be caught by the global HTTPException handler and wrapped
        raise Forbidden("Cannot create super admin users.")
    created: UserOut = svc.create_user(user)
    return ok(data=created, message="User created", status_code=status.HTTP_201_CREATED)

@router.post("/login",
             response_model=APIResponse[TokenResponse],
             status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, svc: UserService = Depends(get_user_service)):
    tokens_dict = svc.user_login(payload)        # returns dict or model
    tokens = TokenResponse(**tokens_dict)        # normalize
    return ok(data=tokens, message="Login successful")

@router.post("/refresh",
             response_model=APIResponse[TokenResponse],
             status_code=status.HTTP_200_OK)
def refresh_token(payload: RefreshRequest, svc: UserService = Depends(get_user_service)):
    tokens_dict = svc.user_refresh(payload)
    tokens = TokenResponse(**tokens_dict)
    return ok(data=tokens, message="Token refreshed")

# Example (optional) update profile route to show uniform response
@router.put("/me",
            response_model=APIResponse[UserOut],
            status_code=status.HTTP_200_OK)
def update_me(update: UserUpdate, svc: UserService = Depends(get_user_service)):
    updated: UserOut = svc.update_current_user(update)
    return ok(data=updated, message="Profile updated")
