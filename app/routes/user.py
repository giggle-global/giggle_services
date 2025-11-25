# app/routes/user.py
import logging
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from app.models.user import UserUpdate, UserOut, KycUpdate
from app.services.user import UserService
from app.services.skill import SkillService
from app.core.keycloak import get_current_user
from app.schemas.response import APIResponse, ok
from app.models.skill import UserSkillEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/users", tags=["USERS"])

def get_user_service() -> UserService:
    return UserService()

def get_skill_service() -> SkillService:
    return SkillService()

@router.get("/", response_model=APIResponse[Dict [str, Any]])
def get_user(current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    user_id = current_user.get("user_id")
    logger.debug(f"Fetching current user: user_id={user_id}")
    user = svc.get_user(user_id=user_id)
    logger.info(f"Fetched current user: user_id={user_id}")
    return ok(data=user, message="Fetched current user")

@router.get("/freelancer", response_model=APIResponse[List[Dict [str, Any]]])
def get_freelancer(current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Freelancer list requested by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user["role"] == "FL":
        logger.warning("Freelancer attempted to fetch freelancer list (forbidden).")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only clients can get the freelancers list")
    freelancers = svc.list_freelancer()
    logger.info(f"Freelancer list fetched: count={len(freelancers) if freelancers else 0}")
    return ok(data=freelancers, message="Freelancers fetched")



@router.get("/all", response_model=APIResponse[List[Dict [str, Any]]])
def list_all_users(current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"All users list requested by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user["role"] != "SA":
        logger.warning("Non-SA attempted to fetch all users list (forbidden).")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can get the users list")
    users = svc.list_all_users()
    logger.info(f"All users list fetched: count={len(users) if users else 0}")
    return ok(data=users, message="All users fetched")  

@router.get("/profile/{user_id}", response_model=APIResponse[Dict[str, Any]])
def get_profile(
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: UserService = Depends(get_user_service)
):
    logger.debug(
        "Profile fetch requested by user_id=%s (role=%s) for target=%s",
        current_user.get("user_id"),
        current_user.get("role"),
        user_id
    )

    requester_role = current_user.get("role")

    # Only allow SA, clients, and freelancers to fetch profiles
    if requester_role not in ("SA", "CL", "FL"):
        logger.warning(
            "Unauthorized role attempted to view profile. role=%s requester=%s",
            requester_role,
            current_user.get("user_id")
        )
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized to view profiles")

    user = svc.get_user(user_id=user_id)

    if requester_role == "CL":
        # Clients can only view active freelancers
        if user.get("role") != "FL" or user.get("status") != "ACTIVE":
            logger.warning(
                "Client attempted to view unauthorized profile. requester=%s target_role=%s target_status=%s",
                current_user.get("user_id"),
                user.get("role"),
                user.get("status")
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Clients can only view active freelancer profiles")

    elif requester_role == "FL":
        # Freelancers can only view client profiles
        if user.get("role") != "CL":
            logger.warning(
                "Freelancer attempted to view unauthorized profile. requester=%s target_role=%s",
                current_user.get("user_id"),
                user.get("role")
            )
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Freelancers can only view client profiles")

    logger.info("Profile fetched for user_id=%s by requester=%s", user_id, current_user.get("user_id"))
    return ok(data=user, message="User profile fetched")

@router.put("/", response_model=APIResponse[Dict [str, Any]])
def update_user(update: UserUpdate, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    user_id = current_user.get("user_id")
    logger.debug(f"Update requested for user_id={user_id} payload={update.model_dump(exclude_unset=True)}")
    updated = svc.update_user(user_id=user_id, user_data=update.model_dump(exclude_unset=True), current_user=current_user)
    logger.info(f"User updated: user_id={user_id}")
    return ok(data=updated, message="User updated")


@router.put("/kyc", response_model=APIResponse[Dict [str, Any]])
def update_user_kyc(update: KycUpdate, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    user_id = current_user.get("user_id")
    logger.debug(f"Update requested for user_id={user_id} payload={update.model_dump(exclude_unset=True)}")
    updated = svc.update_user(user_id=user_id, user_data=update.model_dump(exclude_unset=True), current_user=current_user)
    logger.info(f"User updated: user_id={user_id}")
    return ok(data=updated, message="User updated")


@router.patch("/{user_id}/skills")
def update_user_skills(
    user_id: str,
    entries: List[UserSkillEntry],
    current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)
):
    """
    Update user's skills. Body: [{"skill_id": "...", "level": "basic"}, ...]
    """
    updated = svc.update_user_skills(user_id, entries, current_user)
    return {"data": updated, "message": "Skills updated", "code": 200}

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

@router.patch("/ban/{user_id}/{reason}", response_model=APIResponse[None])
def ban_user(user_id: str, reason: str, current_user: Dict[str, Any] = Depends(get_current_user), svc: UserService = Depends(get_user_service)):
    logger.debug(f"Ban requested by user_id={current_user.get('user_id')} target={user_id}")
    if current_user["role"] != "SA":
        logger.warning("Non-SA attempted to ban user.")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can ban users")
    if not user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID is required to ban a user")
    if reason == "" or reason is None or reason.strip() == ""  or reason.lower() == "null" :
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reason is required to ban a user")
    if len(reason) > 50:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reason length should be less than 50 characters")
    svc.ban_user(user_id, reason)
    logger.info(f"User banned: user_id={user_id}")
    return ok(message="User has been banned", data=None, status_code=status.HTTP_200_OK)


@router.get("/skills")
def get_skills(
    current_user: Dict[str, Any] = Depends(get_current_user), ssc: SkillService = Depends(get_skill_service)
):
    """
    Update user's skills. Body: [{"skill_id": "...", "level": "basic"}, ...]
    """
    updated = ssc.list_skills(category=None)
    return {"data": updated, "message": "Skills fetched", "code": 200}

@router.get("/admin/dashboard", response_model=APIResponse[Dict[str, Any]])
def get_admin_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user), 
    svc: UserService = Depends(get_user_service)
):
    """
    Get admin dashboard statistics including KPIs, charts data
    Only super admin can access this endpoint
    """
    logger.debug(f"Dashboard stats requested by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user.get("role") != "SA":
        logger.warning("Non-SA attempted to fetch dashboard stats (forbidden).")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only super admin can access dashboard statistics")
    
    try:
        stats = svc.get_dashboard_stats()
        logger.info(f"Dashboard stats fetched successfully")
        return ok(data=stats, message="Dashboard statistics fetched")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching dashboard stats")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch dashboard statistics")

@router.get("/freelancer/dashboard", response_model=APIResponse[Dict[str, Any]])
def get_freelancer_dashboard(
    current_user: Dict[str, Any] = Depends(get_current_user), 
    svc: UserService = Depends(get_user_service)
):
    """
    Get freelancer dashboard statistics including KPIs
    Only freelancers can access this endpoint
    """
    logger.debug(f"Freelancer dashboard stats requested by user_id={current_user.get('user_id')} role={current_user.get('role')}")
    if current_user.get("role") != "FL":
        logger.warning("Non-freelancer attempted to fetch freelancer dashboard stats (forbidden).")
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Only freelancers can access freelancer dashboard statistics")
    
    try:
        freelancer_id = current_user.get("user_id")
        if not freelancer_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "User ID not found")
        stats = svc.get_freelancer_dashboard_stats(freelancer_id)
        logger.info(f"Freelancer dashboard stats fetched successfully for user_id={freelancer_id}")
        return ok(data=stats, message="Freelancer dashboard statistics fetched")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error fetching freelancer dashboard stats")
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch freelancer dashboard statistics")