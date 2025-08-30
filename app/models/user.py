from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

# 1. Define the Role Enum
class RoleEnum(str, Enum):
    SUPER_ADMIN = "SA"
    CLIENT = "CL"
    FREELANCER = "FL"


class NotificationService(BaseModel):
    email: bool = Field(False, example=True)
    sms: bool = Field(False, example=False)
    in_app: bool = Field(False, example=True)

    class Config:
        schema_extra = {
            "example": {
                "email": True,
                "sms": False,
                "in_app": True
            }
        }


class PaymentInformation(BaseModel):
    account_holder_name: Optional[str] = Field(None, example="John Doe")
    account_number: Optional[str] = Field(None, example="1234567890")
    ifsc_code: Optional[str] = Field(None, example="HDFC0001234")
    bank_name: Optional[str] = Field(None, example="HDFC Bank")
    upi_id: Optional[str] = Field(None, example="john@upi")
    gst: Optional[str] = Field(None, example="29ABCDE1234F2Z5")
    account_type: Optional[str] = Field(None, example="Savings")

    class Config:
        schema_extra = {
            "example": {
                "account_holder_name": "John Doe",
                "account_number": "1234567890",
                "ifsc_code": "HDFC0001234",
                "bank_name": "HDFC Bank",
                "upi_id": "john@upi",
                "gst": "29ABCDE1234F2Z5",
                "account_type": "Savings"
            }
        }


class UserBase(BaseModel):
    username: str = Field(..., example="johndoe")
    email: EmailStr = Field(..., example="johndoe@example.com")
    phone_number: str = Field(..., example="+919876543210")
    role: RoleEnum = Field(..., example=RoleEnum.CLIENT.value)
    first_name: Optional[str] = Field(None, example="John")
    last_name: Optional[str] = Field(None, example="Doe")
    status: Optional[str] = Field("ACTIVE", example="ACTIVE")
    keycloak_id: Optional[str] = Field(None, example="c12d3f45-6789-4abc-def1-23456789abcd")
    user_id: Optional[str] = Field(None, example="user-001")


class UserCreate(UserBase):
    passcode: str = Field(..., example="StrongPass@123")

    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe",
                "email": "johndoe@example.com",
                "phone_number": "+919876543210",
                "role": "CL",
                "first_name": "John",
                "last_name": "Doe",
                "status": "ACTIVE",
                "passcode": "StrongPass@123"
            }
        }


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, example="Johnny")
    last_name: Optional[str] = Field(None, example="Doe")
    username: Optional[str] = Field(None, example="johnnydoe")
    email: Optional[EmailStr] = Field(None, example="johnny@example.com")
    phone_number: Optional[str] = Field(None, example="+919812345678")
    bio: Optional[str] = Field(None, example="Freelance web developer")
    profile_pic: Optional[bytes] = None  # Could be UploadFile in routes
    notification_service: Optional[NotificationService] = None
    language_preference: Optional[str] = Field(None, example="en")
    payment_information: Optional[PaymentInformation] = None
    skill_set: Optional[List[str]] = Field(None, example=["Python", "FastAPI", "MongoDB"])

    class Config:
        schema_extra = {
            "example": {
                "first_name": "Johnny",
                "last_name": "Doe",
                "username": "johnnydoe",
                "email": "johnny@example.com",
                "phone_number": "+919812345678",
                "bio": "Freelance web developer",
                "notification_service": {
                    "email": True,
                    "sms": False,
                    "in_app": True
                },
                "language_preference": "en",
                "payment_information": {
                    "account_holder_name": "John Doe",
                    "account_number": "1234567890",
                    "ifsc_code": "HDFC0001234",
                    "bank_name": "HDFC Bank",
                    "upi_id": "john@upi",
                    "gst": "29ABCDE1234F2Z5",
                    "account_type": "Savings"
                },
                "skill_set": ["Python", "FastAPI", "MongoDB"]
            }
        }


class UserOut(BaseModel):
    user_id: str
    username: str
    email: EmailStr
    phone_number: str
    role: RoleEnum
    first_name: Optional[str]
    last_name: Optional[str]
    status: Optional[str] = "ACTIVE"
    keycloak_id: Optional[str] = None

    class Config:
        orm_mode = True
        schema_extra = {
            "example": {
                "user_id": "user-001",
                "username": "johndoe",
                "email": "johndoe@example.com",
                "phone_number": "+919876543210",
                "role": "CL",
                "first_name": "John",
                "last_name": "Doe",
                "status": "ACTIVE",
                "keycloak_id": "c12d3f45-6789-4abc-def1-23456789abcd"
            }
        }


class LoginRequest(BaseModel):
    username: str = Field(..., example="johndoe@example.com")
    password: str = Field(..., example="StrongPass@123")

    class Config:
        schema_extra = {
            "example": {
                "username": "johndoe@example.com",
                "password": "StrongPass@123"
            }
        }


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOi...logout_token")

    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOi...logout_token"
            }
        }


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOi...refresh_token")

    class Config:
        schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOi...refresh_token"
            }
        }


class TokenResponse(BaseModel):
    access_token: str = Field(..., example="eyJhbGciOi...access_token")
    refresh_token: str = Field(..., example="eyJhbGciOi...refresh_token")
    expires_in: int = Field(..., example=3600)
    refresh_expires_in: int = Field(..., example=86400)
    token_type: str = Field(..., example="bearer")

    class Config:
        schema_extra = {
            "example": {
                "access_token": "eyJhbGciOi...access_token",
                "refresh_token": "eyJhbGciOi...refresh_token",
                "expires_in": 3600,
                "refresh_expires_in": 86400,
                "token_type": "bearer"
            }
        }


class LoginResponse(BaseModel):
    tokens: TokenResponse
    user: UserOut

    class Config:
        schema_extra = {
            "example": {
                "tokens": {
                    "access_token": "eyJhbGciOi...access_token",
                    "refresh_token": "eyJhbGciOi...refresh_token",
                    "expires_in": 3600,
                    "refresh_expires_in": 86400,
                    "token_type": "bearer"
                },
                "user": {
                    "user_id": "user-001",
                    "username": "johndoe",
                    "email": "johndoe@example.com",
                    "phone_number": "+919876543210",
                    "role": "CL",
                    "first_name": "John",
                    "last_name": "Doe",
                    "status": "ACTIVE",
                    "keycloak_id": "c12d3f45-6789-4abc-def1-23456789abcd"
                }
            }
        }
