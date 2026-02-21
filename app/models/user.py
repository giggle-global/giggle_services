from typing import Optional, List
from pydantic import BaseModel, Field, EmailStr, validator
from enum import Enum
import re
from fastapi import HTTPException, status

# 1. Define the Role Enum
class RoleEnum(str, Enum):
    SUPER_ADMIN = "SA"
    CLIENT = "CL"
    FREELANCER = "FL"

class ThemeEnum(str, Enum):
    LIGHT = "LIGHT"
    DARK = "DARK"


class AvailabilityEnum(str, Enum):
    """Freelancer availability based on hours per week"""
    LOW = "low"  # max 10hr/wk
    MEDIUM = "medium"  # 10-30hr/wk
    IMMEDIATE = "immediate"  # 30+hr/wk


class PaymentTypeEnum(str, Enum):
    HOURLY = "Hourly"
    BUDGET = "Budget"


class NotificationService(BaseModel):
    email: bool = Field(False, example=True)
    # sms: bool = Field(False, example=False)
    in_app: bool = Field(False, example=True)

    class Config:
       json_schema_extra= {
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
       json_schema_extra= {
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
    username: Optional[str] = Field(None, example="johndoe")
    email: EmailStr = Field(..., example="johndoe@example.com")
    phone_number: Optional[str] = Field(None, example="+919876543210")
    role: RoleEnum = Field(..., example=RoleEnum.CLIENT.value)
    first_name: Optional[str] = Field(None, example="John")
    last_name: Optional[str] = Field(None, example="Doe")
    status: Optional[str] = Field("ACTIVE", example="ACTIVE")
    keycloak_id: Optional[str] = Field(None, example="c12d3f45-6789-4abc-def1-23456789abcd")
    user_id: Optional[str] = Field(None, example="user-001")
    kyc: Optional[bool] = Field(False, example=True)
    first_intro_done: Optional[bool] = Field(False, example=True)
    email_verified: bool = Field(False, example=True)
    phone_verified: bool = Field(False, example=True)
    is_affiliate: Optional[bool] = Field(False, example=False)
    preferred_payment_type: Optional[PaymentTypeEnum] = Field(None, example=PaymentTypeEnum.HOURLY.value)
    hourly_rate: Optional[float] = Field(None, example=25.0)


class UserCreate(UserBase):
    passcode: str = Field(..., example="StrongPass@123")
    signup_token: Optional[str] = Field(None, example="eyJhbGciOi...signup_token")  # For FL role
    update_cool_down_period: Optional[int] = Field(5, example=0)  # in days


    @validator("passcode")
    def validate_passcode_strength(cls, v: str) -> str:
        pattern = r"(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*()_+\-=\[\]{};':\",.<>\/?\\|`~])"
        if len(v) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passcode must be at least 8 characters long."
            )
        if not re.search(pattern, v):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Passcode must contain at least one uppercase letter, one lowercase letter, one number, and one special character."
            )
        return v

    class Config:
       json_schema_extra= {
            "example": {
                "email": "johndoe@example.com",
                "phone_number": "+919876543210",
                "role": "CL",
                "first_name": "John",
                "last_name": "Doe",
                "status": "ACTIVE",
                "passcode": "StrongPass@123",
                "signup_token": "eyJhbGciOi...signup_token"
            }
        }


class LocationInfo(BaseModel):
    """Geographic location information for matching algorithm"""
    city: Optional[str] = Field(None, example="Mumbai")
    region: Optional[str] = Field(None, example="Maharashtra")
    country: Optional[str] = Field(None, example="India")
    
    class Config:
        json_schema_extra = {
            "example": {
                "city": "Mumbai",
                "region": "Maharashtra",
                "country": "India"
            }
        }

class ContactInfo(BaseModel):
    linkedin: Optional[str] = Field(None, example="https://linkedin.com/in/johndoe")
    website: Optional[str] = Field(None, example="https://example.com")
    timezone: Optional[str] = Field(None, example="UTC+05:30")
    secondary_phone: Optional[str] = Field(None, example="+919812345678")
    secondary_email: Optional[EmailStr] = Field(None, example="alt@example.com")
    linkedin_verified: bool = Field(False, example=True)
    linkedin_profile_id: Optional[str] = Field(None, example="abcd1234")
    linkedin_vanity: Optional[str] = Field(None, example="johndoe")
    linkedin_verified_at: Optional[int] = Field(None, example=1700000000)

class CompanyContactInfo(BaseModel):
    contact_person: Optional[str] = Field(None, example="Jane Doe")
    contact_email: Optional[EmailStr] = Field(None, example="jane@example")
    contact_phone: Optional[str] = Field(None, example="+919876543211")
    contact_address: Optional[str] = Field(None, example="123, Business St, City, Country")
    contact_designation: Optional[str] = Field(None, example="HR Manager")
    contact_timezone: Optional[str] = Field(None, example="UTC+05:30 chennai")
    
class CompanyInfo(BaseModel):
    company_name: Optional[str] = Field(None, example="KPS Pvt. Limited")
    website: Optional[str] = Field(None, example="https://kpspvt.com")
    industry: Optional[str] = Field(None, example="Tech & IT")
    company_size: Optional[str] = Field(None, example="11-50 employees")
    company_contacts: Optional[CompanyContactInfo] = None
    company_description: Optional[str] = Field(None, example="We build web products")



class UserSettingInfo(BaseModel):
    theme: Optional[ThemeEnum] = Field("LIGHT", example="LIGHT")
    timezone: Optional[str] = Field(None, example="UTC+05:30")
    currency: Optional[str] = Field(None, example="INR")


class UserUpdate(BaseModel):
    first_name: Optional[str] = Field(None, example="Johnny")
    last_name: Optional[str] = Field(None, example="Doe")
    # username: Optional[str] = Field(None, example="johnnydoe")
    email: Optional[EmailStr] = Field(None, example="johnny@example.com")
    phone_number: Optional[str] = Field(None, example="+919812345678")
    bio: Optional[str] = Field(None, example="Freelance web developer", max_length=210)
    designation: Optional[str] = Field(None, example="Web Developer")
    experience_years: Optional[int] = Field(None, example=2)
    experience_months: Optional[int] = Field(None, example=6)
    profile_pic: Optional[bytes] = None  # Could be UploadFile in routes
    notification_service: Optional[NotificationService] = None
    language_preference: Optional[str] = Field(None, example="en")
    payment_information: Optional[PaymentInformation] = None
    skill_set: Optional[List[str]] = Field(None, example=["Python", "FastAPI", "MongoDB"])

    # Location and matching fields (available for both client and freelancer)
    location_info: Optional[LocationInfo] = None
    # Freelancer-specific fields for matching algorithm
    interested_industries: Optional[List[str]] = Field(None, example=["F&B", "Healthcare", "E-commerce"])
    ongoing_gigs_count: Optional[int] = Field(0, example=2, description="Number of active gigs")
    availability: Optional[AvailabilityEnum] = Field(None, example=AvailabilityEnum.MEDIUM.value, description="Freelancer availability: low (max 10hr/wk), medium (10-30hr/wk), immediate (30+hr/wk)")
    preferred_payment_type: Optional[PaymentTypeEnum] = Field(None, example=PaymentTypeEnum.HOURLY.value)
    hourly_rate: Optional[float] = Field(None, example=25.0)
    
    #client-specific fields
    contact_info: Optional[ContactInfo] = None
    company_info: Optional[CompanyInfo] = None

    user_settings: Optional[UserSettingInfo] = None

    class Config:
       json_schema_extra= {
            "example": {
                "first_name": "Johnny",
                "last_name": "Doe",
                "username": "johnnydoe",
                "email": "johnny@example.com",
                "phone_number": "+919812345678",
                "bio": "Freelance web developer",
                "notification_service": {
                    "email": True,
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
                "user_settings": {
                    "theme": "LIGHT",
                    "timezone": "UTC+05:30",
                    "currency": "INR"
                },
                "availability": "medium",
                "preferred_payment_type": "Hourly"
            }
        }

class KycUpdate(BaseModel):
    kyc: Optional[bool] = Field(False, example=True)
    first_intro_done: Optional[bool] = Field(False, example=True)

    class Config:
       json_schema_extra= {
            "example": {
                "kyc": True,
                "first_intro_done": True
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
    kyc: Optional[bool] = Field(False, example=True)
    first_intro_done: Optional[bool] = Field(False, example=True)
    user_settings: Optional[UserSettingInfo] = None
    preferred_payment_type: Optional[PaymentTypeEnum] = None
    hourly_rate: Optional[float] = None

    class Config:
        from_attributes = True
        json_schema_extra= {
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
    email: str = Field(..., example="johndoe@example.com")
    password: str = Field(..., example="StrongPass@123")

    class Config:
       json_schema_extra= {
            "example": {
                "email": "johndoe@example.com",
                "password": "StrongPass@123"
            }
        }


class LogoutRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOi...logout_token")

    class Config:
       json_schema_extra= {
            "example": {
                "refresh_token": "eyJhbGciOi...logout_token"
            }
        }


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., example="eyJhbGciOi...refresh_token")

    class Config:
       json_schema_extra= {
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
       json_schema_extra= {
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
       json_schema_extra= {
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


class BanUserRequest(BaseModel):
    reason: str = Field(..., min_length=1, max_length=50, example="Violation of terms of service")

    class Config:
       json_schema_extra= {
            "example": {
                "reason": "Violation of terms of service"
            }
        }