from typing import Optional
from pydantic import BaseModel, Field, EmailStr
from enum import Enum

# 1. Define the Role Enum
class RoleEnum(str, Enum):
    SUPER_ADMIN = "SA"
    CLIENT = "CL"
    FREELANCER = "FL"
    # Add more roles as needed


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
    photo_id: Optional[str] = None
    email: Optional[EmailStr] = None
    phone_number: Optional[str] = None
    role: Optional[RoleEnum] = None

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