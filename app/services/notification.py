"""
Notification Service - Handles creating and sending notifications
Uses RabbitMQ for async message processing
"""
import logging
from typing import Dict, Any, Optional
from app.repositories.notification import NotificationRepository
from app.repositories.user import UserRepository
from app.models.notification import NotificationType, NotificationCreate, NotificationOut
from app.core.rabbitmq import RabbitMQConnection
from app.core.email_service import EmailService
from pymongo.errors import PyMongoError

logger = logging.getLogger(__name__)

class NotificationService:
    def __init__(self):
        self.repo = NotificationRepository()
        self.user_repo = UserRepository()
        self.email_service = EmailService()

    def create_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        link: Optional[str] = None,
        send_email: bool = False
    ) -> Dict[str, Any]:
        """
        Create a notification and optionally send via RabbitMQ and email
        """
        try:
            # Create notification in database
            notification_data = {
                "user_id": user_id,
                "type": notification_type.value,
                "title": title,
                "message": message,
                "data": data or {},
                "link": link
            }
            
            notification = self.repo.create(notification_data)
            
            # Publish to RabbitMQ for async processing
            try:
                # Map notification types to routing keys
                routing_key_map = {
                    NotificationType.REQUEST_RECEIVED: "request",
                    NotificationType.REQUEST_ACCEPTED: "request",
                    NotificationType.REQUEST_REJECTED: "request",
                    NotificationType.MILESTONE_REMINDER: "milestone",
                    NotificationType.MILESTONE_COMPLETED: "milestone",
                    NotificationType.MILESTONE_APPROVED: "milestone",
                }
                routing_key = routing_key_map.get(notification_type, "general")
                
                RabbitMQConnection.publish_message(
                    exchange='notifications',
                    routing_key=routing_key,
                    message={
                        "notification_id": notification.get("notification_id"),
                        "user_id": user_id,
                        "type": notification_type.value,
                        "title": title,
                        "message": message,
                        "data": data,
                        "link": link,
                        "send_email": send_email
                    }
                )
            except Exception as e:
                logger.warning("Failed to publish to RabbitMQ (notification still created): %s", e)
                # Continue even if RabbitMQ fails - notification is already in DB

            # Send email if requested and user has email notifications enabled
            if send_email:
                try:
                    user = self.user_repo.get_user_by_id(user_id)
                    if user and user.get("notification_service", {}).get("email", False):
                        self.email_service.send_notification_email(
                            to_email=user.get("email"),
                            subject=title,
                            message=message,
                            notification_data=data
                        )
                except Exception as e:
                    logger.warning("Failed to send notification email: %s", e)
                    # Don't fail the whole operation if email fails

            return notification
        except PyMongoError as e:
            logger.exception("Mongo error creating notification: %s", e)
            raise

    def notify_request_received(
        self,
        freelancer_id: str,
        client_name: str,
        project_title: str,
        request_id: str,
        project_id: str
    ):
        """Notify freelancer when they receive a request"""
        return self.create_notification(
            user_id=freelancer_id,
            notification_type=NotificationType.REQUEST_RECEIVED,
            title="New Project Request",
            message=f"{client_name} has sent you a request for the project: {project_title}",
            data={
                "request_id": request_id,
                "project_id": project_id,
                "client_name": client_name
            },
            link=f"/freelancer/gig?request_id={request_id}",
            send_email=True
        )

    def notify_milestone_reminder(
        self,
        user_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        due_date: int
    ):
        """Notify user 24 hours before milestone due date"""
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.MILESTONE_REMINDER,
            title="Milestone Reminder",
            message=f"Milestone '{milestone_title}' is due in 24 hours",
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "due_date": due_date,
                "milestone_title": milestone_title
            },
            link=f"/milestone?agreement_id={agreement_id}",
            send_email=True
        )

    def get_user_notifications(
        self,
        user_id: str,
        limit: int = 50,
        skip: int = 0,
        unread_only: bool = False
    ) -> list:
        """Get notifications for a user"""
        try:
            return self.repo.get_user_notifications(user_id, limit, skip, unread_only)
        except PyMongoError as e:
            logger.exception("Mongo error fetching notifications: %s", e)
            raise

    def get_unread_count(self, user_id: str) -> int:
        """Get count of unread notifications"""
        try:
            return self.repo.get_unread_count(user_id)
        except PyMongoError as e:
            logger.exception("Mongo error counting unread: %s", e)
            raise

    def mark_as_read(self, notification_id: str, user_id: str) -> bool:
        """Mark a notification as read"""
        try:
            return self.repo.mark_as_read(notification_id, user_id)
        except PyMongoError as e:
            logger.exception("Mongo error marking as read: %s", e)
            raise

    def mark_all_as_read(self, user_id: str) -> int:
        """Mark all notifications as read for a user"""
        try:
            return self.repo.mark_all_as_read(user_id)
        except PyMongoError as e:
            logger.exception("Mongo error marking all as read: %s", e)
            raise

