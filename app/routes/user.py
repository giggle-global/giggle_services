# app/routes/user.py
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserCreate, UserUpdate, UserOut, TokenResponse, LoginRequest, RefreshRequest
from app.services.user import UserService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["USERS"])

def get_user_service() -> UserService:
    return UserService()

@router.get("/", response_model=APIResponse[UserOut])
def get_user(current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    user_id = current_user.get("user_id")
    logger.debug(f"Fetching current user: user_id={user_id}")
    user = svc.get_user(user_id=user_id)
    logger.info(f"Fetched current user: user_id={user_id}")
    return ok(data=user, message="Fetched current user")

@router.get("/freelancer", response_model=APIResponse[List[UserOut]])
def get_freelancer(current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Freelancer list requested by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user["role"] == "FL":
        logger.warning("Freelancer attempted to fetch freelancer list (forbidden).")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can get the freelancers list")
    freelancers = svc.list_freelancer()
    logger.info(f"Freelancer list fetched: count={len(freelancers) if freelancers else 0}")
    return ok(data=freelancers, message="Freelancers fetched")

@router.get("/profile/{user_id}", response_model=APIResponse[UserOut])
def get_profile(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Profile fetch requested by user_id={current_user.get('user_id')} for target={user_id}")
    if current_user["role"] != "SA":
        logger.warning("Non-SA attempted to view other user's profile.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can view other users")
    user = svc.get_user(user_id=user_id)
    logger.info(f"Profile fetched for user_id={user_id}")
    return ok(data=user, message="User profile fetched")

@router.put("/", response_model=APIResponse[UserOut])
def update_user(update: UserUpdate, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    user_id = current_user.get("user_id")
    logger.debug(f"Update requested for user_id={user_id} payload={update.model_dump(exclude_unset=True)}")
    updated = svc.update_user(user_id=user_id, user=update.model_dump(exclude_unset=True))
    logger.info(f"User updated: user_id={user_id}")
    return ok(data=updated, message="User updated")

@router.delete("/delete/{user_id}", response_model=APIResponse[None])
def delete_user(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Delete requested by user_id={current_user.get('user_id')} target={user_id}")
    if current_user["role"] != "SA":
        logger.warning("Non-SA attempted to delete user.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can delete users")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID is required to delete a user")
    svc.delete_user(user_id)
    logger.info(f"User deleted: user_id={user_id}")
    return ok(message="User deleted", data=None, status_code=status.HTTP_200_OK)

@router.patch("/ban/{user_id}", response_model=APIResponse[None])
def ban_user(user_id: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Ban requested by user_id={current_user.get('user_id')} target={user_id}")
    if current_user["role"] != "SA":
        logger.warning("Non-SA attempted to ban user.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can ban users")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID is required to ban a user")
    svc.ban_user(user_id)
    logger.info(f"User banned: user_id={user_id}")
    return ok(message="User has been banned", data=None, status_code=status.HTTP_200_OK)
