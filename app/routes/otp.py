import logging

from fastapi import APIRouter, Depends, status

from app.models.otp import SendOTPRequest, VerifyOTPRequest
from app.schemas.response import APIResponse, ok
from app.services.otp import OTPService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/otp", tags=["OTP"])


def get_otp_service() -> OTPService:
    return OTPService()


@router.post("/send", response_model=APIResponse[dict])
def send_otp(payload: SendOTPRequest, svc: OTPService = Depends(get_otp_service)):
    logger.debug("OTP send requested for email=%s purpose=%s", payload.email, payload.purpose)
    svc.send_otp(email=payload.email, purpose=payload.purpose)
    logger.info("OTP sent to email=%s purpose=%s", payload.email, payload.purpose)
    return ok(message="OTP sent successfully", data={"email": payload.email})


@router.post("/verify", response_model=APIResponse[dict])
def verify_otp(payload: VerifyOTPRequest, svc: OTPService = Depends(get_otp_service)):
    logger.debug("OTP verify requested for email=%s purpose=%s", payload.email, payload.purpose)
    svc.verify_otp(email=payload.email, otp_code=payload.otp_code, purpose=payload.purpose)
    logger.info("OTP verified for email=%s purpose=%s", payload.email, payload.purpose)
    return ok(message="OTP verified", data={"email": payload.email, "verified": True})

