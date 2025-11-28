# app/routers/auth.py
import logging
from fastapi import APIRouter, Depends, HTTPException
from starlette import status
from app.models.user import UserCreate, UserUpdate, UserOut, TokenResponse, LoginRequest, RefreshRequest, LoginResponse
from app.models.password_reset import (
    PasswordResetRequest,
    PasswordResetVerifyRequest,
    PasswordResetUpdateRequest,
)
from app.services.user import UserService
from app.services.otp import OTPService
from app.models.otp import OTPPurpose
from app.schemas.response import APIResponse, ok
from app.core.exceptions import Forbidden
from app.repositories.user import UserRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["AUTHENTICATION"])

def get_user_service() -> UserService:
    return UserService()

def get_otp_service() -> OTPService:
    return OTPService()

def get_user_repo() -> UserRepository:
    return UserRepository()

@router.post("/signup", response_model=APIResponse[UserOut], status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    svc: UserService = Depends(get_user_service),
    otp_svc: OTPService = Depends(get_otp_service),
):
    logger.debug(f"Signup request received: {user.model_dump()}")
    if getattr(user, "role", None) == "SA":
        logger.warning("Attempt to create Super Admin user blocked.")
        raise Forbidden("Cannot create super admin users.")

    # Ensure email verified before creating account
    otp_svc.ensure_verified(email=user.email)
    user.email_verified = True

    created_raw = svc.create_user(user)

    # Normalize to UserOut (works whether repo returned dict or model)
    created = created_raw if isinstance(created_raw, UserOut) else UserOut(**created_raw)

    # Safe user_id extraction for logging
    user_id = getattr(created, "user_id", None)
    logger.info(f"User created successfully: {user_id}")

    # Clear OTP entry to prevent reuse
    otp_svc.clear_otp(email=user.email)

    return ok(data=created, message="User created", status_code=status.HTTP_201_CREATED)


@router.post("/login", response_model=APIResponse[LoginResponse], status_code=status.HTTP_200_OK)
def login(payload: LoginRequest, svc: UserService = Depends(get_user_service)):
    logger.debug(f"Login attempt for email: {payload.email}")

    tokens_dict = svc.user_login(payload)
    tokens = TokenResponse(**tokens_dict)

    logger.info(f"Login successful for email: {payload.email}")

    # Get user details from database using email instead of decoding token
    # This avoids token validation issues and is more reliable
    user_repo = UserRepository()
    user_details: dict = user_repo.get_user_by_email(payload.email)
    # logger.debug(f"User details fetched: {user_details}")

    login_data = LoginResponse(tokens=tokens, user=UserOut(**user_details))
    return ok(data=login_data, message="Login successful")

@router.post("/refresh", response_model=APIResponse[TokenResponse], status_code=status.HTTP_200_OK)
def refresh_token(payload: RefreshRequest, svc: UserService = Depends(get_user_service)):
    logger.debug("Token refresh requested")
    tokens_dict = svc.user_refresh(payload)
    tokens = TokenResponse(**tokens_dict)
    logger.info("Token refreshed successfully")
    return ok(data=tokens, message="Token refreshed")


@router.post("/password/forgot", response_model=APIResponse[dict])
def forgot_password(
    payload: PasswordResetRequest,
    otp_svc: OTPService = Depends(get_otp_service),
    user_repo: UserRepository = Depends(get_user_repo),
):
    try:
        user_repo.get_user_by_email(payload.email)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_404_NOT_FOUND:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Invalid email address")
        raise

    otp_svc.send_otp(email=payload.email, purpose=OTPPurpose.PASSWORD_RESET)
    return ok(message="OTP sent to email.", data={"email": payload.email})


@router.post("/password/verify", response_model=APIResponse[dict])
def verify_password_reset(
    payload: PasswordResetVerifyRequest,
    otp_svc: OTPService = Depends(get_otp_service),
):
    otp_svc.verify_otp(email=payload.email, otp_code=payload.otp_code, purpose=OTPPurpose.PASSWORD_RESET)
    return ok(message="OTP verified. You can now reset your password.", data={"verified": True})


@router.post("/password/reset", response_model=APIResponse[dict])
def reset_password(
    payload: PasswordResetUpdateRequest,
    svc: UserService = Depends(get_user_service),
    otp_svc: OTPService = Depends(get_otp_service),
):
    otp_svc.ensure_verified(email=payload.email, purpose=OTPPurpose.PASSWORD_RESET)
    svc.reset_password(email=payload.email, new_password=payload.new_password)
    otp_svc.clear_otp(email=payload.email, purpose=OTPPurpose.PASSWORD_RESET)
    return ok(message="Password updated successfully", data={"email": payload.email})

# @router.put("/me", response_model=APIResponse[UserOut], status_code=status.HTTP_200_OK)
# def update_me(update: UserUpdate, svc: UserService = Depends(get_user_service)):
#     logger.debug(f"Update profile request: {update.model_dump(exclude_unset=True)}")
#     updated: UserOut = svc.update_current_user(update)
#     logger.info(f"Profile updated for user: {updated.id}")
#     return ok(data=updated, message="Profile updated")
