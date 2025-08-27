from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.models.user import UserCreate, UserUpdate, UserOut, TokenResponse, LoginRequest, RefreshRequest
from app.services.user import UserService
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/users", tags=["auth"])

user_service = UserService()

@router.get("/", response_model=UserOut)
def get_user(current_user: dict = Depends(get_current_user)):
    user_id=current_user.get("user_id")
    print("collected user id", user_id)
    return user_service.get_user(user_id=user_id)

@router.get("/profile/{user_id}", response_model=UserOut)
def get_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(403, "Only super admin can view other users")
    return user_service.get_user(user_id=user_id)

@router.put("/", response_model=UserOut)
def update_user(update: UserUpdate, current_user: dict = Depends(get_current_user)):
    user_id=current_user.get("user_id")
    print("collected user id", user_id)
    update_data = update.model_dump(exclude_unset=True)
    return user_service.update_user(user_id=user_id, user=update_data)

@router.delete("/delete/{user_id}")
def delete_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(403, "Only super admin can delete users")
    print("current user role", current_user["role"])
    if not user_id:
        raise HTTPException(400, "User ID is required to ban a user")
    user_service.delete_user(user_id)
    return {"detail": "User deleted"}

@router.patch("/ban/{user_id}")
def ban_user(user_id: str, current_user: dict = Depends(get_current_user)):
    if current_user["role"] != "SA":
        raise HTTPException(403, "Only super admin can ban users")
    print("current user role", current_user["role"])
    if not user_id:
        raise HTTPException(400, "User ID is required to ban a user")
    user_service.ban_user(user_id)
    return {"detail": "User has been banned."}
    
