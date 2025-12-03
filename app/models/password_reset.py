import re
from pydantic import BaseModel, EmailStr, constr, validator
from fastapi import HTTPException, status


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetVerifyRequest(BaseModel):
    email: EmailStr
    otp_code: constr(min_length=4, max_length=4, pattern=r"^\d+$")


class PasswordResetUpdateRequest(BaseModel):
    email: EmailStr
    new_password: constr(min_length=8, max_length=128)

    @validator("new_password")
    def validate_new_password(cls, value: str) -> str:
        pattern = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\",.<>\/?\\|`~])"
        if len(value) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must be at least 8 characters long."
            )
        if not re.search(pattern, value):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Password must contain uppercase, lowercase, number, and special character."
            )
        return value

