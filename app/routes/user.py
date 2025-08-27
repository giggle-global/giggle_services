# app/routes/user.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List

from app.models.user import (
    UserCreate, UserUpdate, UserOut,
    TokenResponse, LoginRequest, RefreshRequest
)
from app.services.user import UserService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok  # import response wrapper

router = APIRouter(prefix="/users", tags=["USERS"])

user_service = UserService()

# --- Routes ---

@router.get("/", response_model=APIResponse[UserOut])
def get_user(current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id")
    user = user_service.get_user(user_id=user_id)
    return ok(data=user, message="Fetched current user")


@router.get("/freelancer", response_model=APIResponse[List[UserOut]])
def get_freelancer(current_user: dict = Depends(get_current_user)):
    if current_user["role"] == "FL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can get the freelancers list")
    freelancers = user_service.list_freelancer()
    return ok(data=freelancers, message="Freelancers fetched")


@router.get("/profile/{user_id}", response_model=APIResponse[UserOut])
def get_profile(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can view other users")
    user = user_service.get_user(user_id=user_id)
    return ok(data=user, message="User profile fetched")


@router.put("/", response_model=APIResponse[UserOut])
def update_user(update: UserUpdate, current_user: dict = Depends(get_current_user)):
    user_id = current_user.get("user_id")
    update_data = update.model_dump(exclude_unset=True)
    updated = user_service.update_user(user_id=user_id, user=update_data)
    return ok(data=updated, message="User updated")


@router.delete("/delete/{user_id}", response_model=APIResponse[None])
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can delete users")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID is required to delete a user")
    user_service.delete_user(user_id)
    return ok(message="User deleted", data=None, status_code=status.HTTP_200_OK)


@router.patch("/ban/{user_id}", response_model=APIResponse[None])
def ban_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can ban users")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID is required to ban a user")
    user_service.ban_user(user_id)
    return ok(message="User has been banned", data=None, status_code=status.HTTP_200_OK)
