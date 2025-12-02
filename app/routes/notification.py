from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any
from app.services.notification import NotificationService
from app.models.notification import NotificationOut
from app.schemas.response import APIResponse, ok
from app.core.keycloak import get_current_user
from app.core.scheduler import milestone_scheduler
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications"])

def get_notification_service() -> NotificationService:
    return NotificationService()

@router.get("/", response_model=APIResponse[List[NotificationOut]])
def get_notifications(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
    unread_only: bool = Query(False),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service)
):
    """Get notifications for the current user"""
    try:
        notifications = svc.get_user_notifications(
            user_id=current_user["user_id"],
            limit=limit,
            skip=skip,
            unread_only=unread_only
        )
        return ok(data=notifications, message=f"Found {len(notifications)} notifications")
    except Exception as e:
        logger.exception("Error fetching notifications: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch notifications")

@router.get("/unread-count", response_model=APIResponse[int])
def get_unread_count(
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service)
):
    """Get count of unread notifications"""
    try:
        count = svc.get_unread_count(current_user["user_id"])
        return ok(data=count, message=f"You have {count} unread notifications")
    except Exception as e:
        logger.exception("Error fetching unread count: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to fetch unread count")

@router.put("/{notification_id}/read", response_model=APIResponse[Dict[str, Any]])
def mark_as_read(
    notification_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service)
):
    """Mark a notification as read"""
    try:
        success = svc.mark_as_read(notification_id, current_user["user_id"])
        if not success:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Notification not found")
        return ok(data={"notification_id": notification_id, "status": "read"}, message="Notification marked as read")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error marking notification as read: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to mark notification as read")

@router.put("/read-all", response_model=APIResponse[Dict[str, Any]])
def mark_all_as_read(
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: NotificationService = Depends(get_notification_service)
):
    """Mark all notifications as read for the current user"""
    try:
        count = svc.mark_all_as_read(current_user["user_id"])
        return ok(data={"count": count}, message=f"Marked {count} notifications as read")
    except Exception as e:
        logger.exception("Error marking all notifications as read: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to mark all notifications as read")

@router.get("/scheduler/status", response_model=APIResponse[Dict[str, Any]])
def get_scheduler_status(
    current_user: Dict[str, Any] = Depends(get_current_user)
):
    """Check if milestone scheduler is running"""
    try:
        is_running = milestone_scheduler.scheduler.running
        jobs = milestone_scheduler.scheduler.get_jobs()
        
        status_info = {
            "running": is_running,
            "jobs_count": len(jobs),
            "next_run_time": str(jobs[0].next_run_time) if jobs and jobs[0].next_run_time else None
        }
        
        return ok(data=status_info, message="Scheduler status retrieved")
    except Exception as e:
        logger.exception("Error getting scheduler status: %s", e)
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, "Failed to get scheduler status")

