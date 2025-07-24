from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

# 1. Define the Role Enum
class RoleEnum(str, Enum):
    SUPER_ADMIN = "SA"
    CLIENT = "CL"
    FREELANCER = "FL"

class NotificationService(BaseModel):
    email: bool = False
    sms: bool = False
    in_app: bool = False

class PaymentInformation(BaseModel):
    account_holder_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None
    upi_id: Optional[str] = None
    gst: Optional[str] = None
    account_type: Optional[str] = None  # e.g., "Savings", "Current"


class UserBase(BaseModel):
    name: Optional[str]
    photo_id: Optional[str] = None
    email: Optional[EmailStr]
    phone_number: str
    status: Optional[str] = "ACTIVE"
    passcode: Optional[str] = None
    role: Optional[RoleEnum]
    keycloak_id: Optional[str] = None
    user_id: Optional[str] = None

class UserCreate(UserBase):
    passcode: str  # Required for creation
    

class UserUpdate(BaseModel):
    name: Optional[str] = None
    last_name: Optional[str] = None
    photo_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    role: Optional[RoleEnum] = None
    bio: Optional[str] = None
    profile_pic: Optional[bytes] = None  # Or handle as UploadFile in your route
    notification_service: Optional[NotificationService] = None
    language_preference: Optional[str] = None  # "en", "hi", etc.
    payment_information: Optional[PaymentInformation] = None
    username: Optional[str] = None
    skill_set: Optional[List[str]] = None


class UserOut(UserBase):
    user_id: str

    class Config:
        orm_mode = True






class LoginRequest(BaseModel):
    username: str  # email or username, as per Keycloak config
    password: str

class LogoutRequest(BaseModel):
    refresh_token: str

class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    refresh_expires_in: int
    token_type: str