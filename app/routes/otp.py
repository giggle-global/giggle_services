import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.otp import SendOTPRequest, VerifyOTPRequest
from app.schemas.response import APIResponse, ok
from app.services.otp import OTPService
from app.services.user import UserService
from app.core.keycloak import get_current_user
from app.models.otp import OTPPurpose

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/otp", tags=["OTP"])


def get_otp_service() -> OTPService:
    return OTPService()


def get_user_service() -> UserService:
    return UserService()


@router.post("/send", response_model=APIResponse[dict])
def send_otp(payload: SendOTPRequest, svc: OTPService = Depends(get_otp_service)):
    logger.debug("OTP send requested for email=%s purpose=%s", payload.email, payload.purpose)
    try:
        svc.send_otp(email=payload.email, purpose=payload.purpose)
        logger.info("OTP sent to email=%s purpose=%s", payload.email, payload.purpose)
        return ok(message="OTP sent successfully", data={"email": payload.email})
    except ValueError as exc:
        logger.error("Email configuration error: %s", str(exc))
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to send OTP to email=%s", payload.email)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send OTP. Please check server configuration.")


@router.post("/verify", response_model=APIResponse[dict])
def verify_otp(payload: VerifyOTPRequest, svc: OTPService = Depends(get_otp_service)):
    logger.debug("OTP verify requested for email=%s purpose=%s", payload.email, payload.purpose)
    svc.verify_otp(email=payload.email, otp_code=payload.otp_code, purpose=payload.purpose)
    logger.info("OTP verified for email=%s purpose=%s", payload.email, payload.purpose)
    return ok(message="OTP verified", data={"email": payload.email, "verified": True})


@router.post("/verify/phone", response_model=APIResponse[dict])
def verify_phone(
    payload: VerifyOTPRequest,
    svc: OTPService = Depends(get_otp_service),
    user_svc: UserService = Depends(get_user_service),
    current_user: dict = Depends(get_current_user),
):
    """
    Verify phone number using OTP (delivered via email) and mark phone_verified on the user.
    """
    logger.debug("Phone verification OTP verify requested for email=%s", payload.email)
    if payload.purpose != OTPPurpose.PHONE_VERIFY:
        payload.purpose = OTPPurpose.PHONE_VERIFY
    svc.verify_otp(email=payload.email, otp_code=payload.otp_code, purpose=payload.purpose)

    # Update user record
    user_svc.user_repo.update_user(
        user_id=current_user.get("user_id"),
        update_payload={
            "phone_verified": True,
        },
    )
    logger.info("Phone verified for user_id=%s email=%s", current_user.get("user_id"), payload.email)
    return ok(message="Phone verified", data={"verified": True})

