# app/routers/auth.py
import logging
from fastapi import APIRouter, Depends
from starlette import status
from app.models.user import UserCreate, UserUpdate, UserOut, TokenResponse, LoginRequest, RefreshRequest
from app.services.user import UserService
from app.schemas.response import APIResponse, ok
from app.core.exceptions import Forbidden

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["AUTHENTICATION"])

def get_user_service() -> UserService:
    return UserService()

@router.post("/signup", response_model=APIResponse[UserOut], status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, svc: UserService = Depends(get_user_service)):
    logger.debug(f"Signup request received: {user.model_dump()}")
    if getattr(user, "role", None) == "SA":
        logger.warning("Attempt to create Super Admin user blocked.")
        raise Forbidden("Cannot create super admin users.")

    created_raw = svc.create_user(user)

    # Normalize to UserOut (works whether repo returned dict or model)
    created = created_raw if isinstance(created_raw, UserOut) else UserOut(**created_raw)

    # Safe user_id extraction for logging
    user_id = getattr(created, "user_id", None)
    logger.info(f"User created successfully: {user_id}")

    return ok(data=created, message="User created", status_code=status.HTTP_201_CREATED)


@router.post("/login", response_model=APIResponse[TokenResponse], status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, svc: UserService = Depends(get_user_service)):
    logger.debug(f"Login attempt for email: {payload.username}")
    tokens_dict = svc.user_login(payload)
    tokens = TokenResponse(**tokens_dict)
    logger.info(f"Login successful for email: {payload.username}")
    return ok(data=tokens, message="Login successful")

@router.post("/refresh", response_model=APIResponse[TokenResponse], status_code=status.HTTP_200_OK)
def refresh_token(payload: RefreshRequest, svc: UserService = Depends(get_user_service)):
    logger.debug("Token refresh requested")
    tokens_dict = svc.user_refresh(payload)
    tokens = TokenResponse(**tokens_dict)
    logger.info("Token refreshed successfully")
    return ok(data=tokens, message="Token refreshed")

@router.put("/me", response_model=APIResponse[UserOut], status_code=status.HTTP_200_OK)
def update_me(update: UserUpdate, svc: UserService = Depends(get_user_service)):
    logger.debug(f"Update profile request: {update.model_dump(exclude_unset=True)}")
    updated: UserOut = svc.update_current_user(update)
    logger.info(f"Profile updated for user: {updated.id}")
    return ok(data=updated, message="Profile updated")
