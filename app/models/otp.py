from datetime import datetime, timedelta
from enum import Enum
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, constr, validator


OTP_CODE_LENGTH = 4


class OTPPurpose(str, Enum):
    SIGNUP = "signup"
    PASSWORD_RESET = "password_reset"


class OTPVerificationBase(BaseModel):
    email: EmailStr
    otp_code: constr(min_length=OTP_CODE_LENGTH, max_length=OTP_CODE_LENGTH) = Field(
        ..., pattern=r"^\d+$", description="Numeric OTP code"
    )
    purpose: OTPPurpose = OTPPurpose.SIGNUP
    expires_at: datetime
    created_at: datetime
    verified: bool = False
    attempts: int = 0


class OTPVerificationCreate(BaseModel):
    email: EmailStr
    purpose: OTPPurpose = OTPPurpose.SIGNUP
    ttl_seconds: int = Field(600, ge=60, le=3600)

    @validator("ttl_seconds")
    def ensure_reasonable_ttl(cls, value: int) -> int:
        # Provide a sensible fallback if someone misconfigures the value.
        if value < 60:
            return 60
        if value > 3600:
            return 3600
        return value


class OTPVerificationOut(OTPVerificationBase):
    pass


class SendOTPRequest(BaseModel):
    email: EmailStr
    purpose: OTPPurpose = OTPPurpose.SIGNUP


class VerifyOTPRequest(BaseModel):
    email: EmailStr
    otp_code: constr(min_length=OTP_CODE_LENGTH, max_length=OTP_CODE_LENGTH) = Field(
        ..., pattern=r"^\d+$"
    )
    purpose: OTPPurpose = OTPPurpose.SIGNUP

