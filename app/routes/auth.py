from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.user import UserCreate, UserUpdate, UserOut, TokenResponse, LoginRequest, RefreshRequest
from app.services.user import UserService
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/auth", tags=["users"])

user_service = UserService()

@router.post("/signup")
def create_user(user: UserCreate):
    data = user_service.create_user(user)
    data = TokenResponse(**data)
    return data

@router.post("/login", response_model=TokenResponse)
def login(data: LoginRequest):
    data = user_service.user_login(data)
    data = TokenResponse(**data)
    return data

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(data: RefreshRequest):
    data = user_service.user_refresh(data)
    data = TokenResponse(**data)
    return data

# @router.post("/logout")
# def logout(data: RefreshRequest):
#     url = f"{config.keyclock_url}/realms/{config.realme_name}/protocol/openid-connect/logout"
#     payload = {
#         "client_id": config.client_id,
#         "client_secret": config.client_secret,
#         "refresh_token": data.refresh_token,
#     }
#     response = requests.post(url, data=payload)
#     if response.status_code == 204:
#         return {"detail": "Logged out successfully"}
#     raise HTTPException(status_code=401, detail="Logout failed")

    
