"""
Notification Service - Handles creating and sending notifications
Uses RabbitMQ for async message processing
"""
import logging
import json
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

            # region agent log: debug notification creation (hypothesis H1 - stale/incorrect links)
            try:
                debug_payload = {
                    "sessionId": "debug-session",
                    "runId": "pre-fix",
                    "hypothesisId": "H1",
                    "location": "notification.py:create_notification",
                    "message": "Notification created",
                    "data": {
                        "notification_id": notification.get("notification_id"),
                        "user_id": user_id,
                        "type": notification_type.value,
                        "link": link,
                    },
                    "timestamp": __import__("time").time(),
                }
                with open(
                    r"c:\Users\Admin\OneDrive\Desktop\Giggle__ - Copy\.cursor\debug.log",
                    "a",
                    encoding="utf-8",
                ) as f:
                    f.write(json.dumps(debug_payload) + "\n")
            except Exception:
                # Never break main flow for logging
                pass
            # endregion agent log
            
            # Publish to RabbitMQ for async processing
            try:
                # Map notification types to routing keys
                routing_key_map = {
                    NotificationType.REQUEST_RECEIVED: "request",
                    NotificationType.REQUEST_ACCEPTED: "request",
                    NotificationType.REQUEST_REJECTED: "request",
                    NotificationType.CLIENT_REQUEST_LIMIT_REACHED: "request",
                    NotificationType.MILESTONE_REMINDER: "milestone",
                    NotificationType.MILESTONE_COMPLETED: "milestone",
                    NotificationType.MILESTONE_APPROVED: "milestone",
                    NotificationType.MILESTONE_PAYMENT_REMINDER: "milestone",
                    NotificationType.MILESTONE_PAYMENT_CONFIRMED: "milestone",
                    NotificationType.AGREEMENT_CREATED: "general",
                    NotificationType.AGREEMENT_UPDATED: "general",
                    NotificationType.AGREEMENT_COMPLETED: "general",
                    NotificationType.AGREEMENT_SIGN_REMINDER: "general",
                    NotificationType.DISPUTE_RAISED: "dispute",
                    NotificationType.DISPUTE_RESOLVED: "dispute",
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

            # Send email if requested
            if send_email:
                try:
                    user = self.user_repo.get_user_by_id(user_id)
                    if not user:
                        logger.warning("Cannot send notification email: User %s not found", user_id)
                        return notification
                    
                    user_email = user.get("email")
                    if not user_email:
                        logger.warning("Cannot send notification email: User %s has no email address", user_id)
                        return notification
                    
                    # Check if user has email notifications enabled (default to True if not set)
                    notification_prefs = user.get("notification_service", {})
                    email_enabled = notification_prefs.get("email", True)  # Default to True if not set
                    
                    if email_enabled:
                        logger.info("Sending notification email to %s for notification %s", user_email, notification.get("notification_id"))
                        try:
                            # Prepare notification data with link included
                            email_notification_data = (data or {}).copy()
                            if link:
                                email_notification_data["link"] = link
                            
                            logger.debug("Email notification data: %s", email_notification_data)
                            self.email_service.send_notification_email(
                                to_email=user_email,
                                subject=title,
                                message=message,
                                notification_data=email_notification_data
                            )
                            logger.info("[OK] Notification email sent successfully to %s", user_email)
                        except ValueError as e:
                            # Configuration errors - log as error with details
                            logger.error("[ERROR] Email configuration error for user %s: %s", user_id, str(e))
                            logger.error("   Check SMTP/SES environment variables: SMTP_SERVER, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM_EMAIL")
                        except Exception as email_error:
                            # Other email errors - log with full traceback
                            logger.exception("[ERROR] Failed to send notification email to %s: %s", user_email, str(email_error))
                            logger.error("   Email service provider: %s", self.email_service.provider)
                    else:
                        logger.debug("Email notifications disabled for user %s, skipping email send", user_id)
                except Exception as e:
                    logger.exception("Failed to process notification email for user %s: %s", user_id, str(e))
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
        """Notify freelancer when they receive a request.

        Frontend: Requests are handled inside the unified messages page for both
        client and freelancer. The freelancer messages route is
        /creator/messages, and the component can use request_id to focus the
        correct thread/section. The tab=received parameter ensures it opens
        the "Received Request" tab instead of the DM tab.
        """
        return self.create_notification(
            user_id=freelancer_id,
            notification_type=NotificationType.REQUEST_RECEIVED,
            title="New Project Request",
            message=f"You have received a new request for the project: {project_title}",
            data={
                "request_id": request_id,
                "project_id": project_id,
                "client_name": client_name,
            },
            # Navigate to freelancer messages page, with request context and tab parameter
            # tab=received opens the "Received Request" tab (tab 1) instead of DM tab (tab 0)
            link=f"/creator/messages?request_id={request_id}&tab=received",
            send_email=True,
        )

    def notify_milestone_reminder(
        self,
        user_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        due_date: int
    ):
        """Notify user 24 hours before milestone due date.

        Frontend: Milestones are shown via the shared MilestoneComponent mounted
        at /owner/milestone or /creator/milestone. We do not encode role in
        the link here; the messages UI or caller's role will determine which
        route to use. For now, default to the generic milestone page, which is
        available under both owner and creator namespaces.
        """
        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.MILESTONE_REMINDER,
            title="Milestone Reminder",
            message=f"Milestone '{milestone_title}' is due in 24 hours",
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "due_date": due_date,
                "milestone_title": milestone_title,
            },
            # Generic milestone page; role-specific layout wraps this component
            link=f"/milestone?agreement_id={agreement_id}",
            send_email=True,
        )

    def notify_milestone_payment_reminder(
        self,
        client_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        project_title: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
    ):
        """Notify client to send payment after verifying a milestone."""
        amount_text = ""
        if amount is not None:
            # Format amount to 2 decimal places
            formatted_amount = f"{amount:.2f}"
            amount_text = f" {currency or ''}{formatted_amount}"
        project_text = f" in project '{project_title}'" if project_title else ""
        message = f"Please send payment for milestone '{milestone_title}'{project_text}{amount_text}".strip()

        return self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.MILESTONE_PAYMENT_REMINDER,
            title="Payment Needed for Milestone",
            message=message,
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "milestone_title": milestone_title,
                "project_title": project_title,
                "amount": amount,
                "currency": currency,
            },
            # Route client to gig page for this agreement
            link=f"/owner/gig?agreement_id={agreement_id}",
            send_email=True,
        )

    def notify_milestone_payment_confirmed(
        self,
        freelancer_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        project_title: str | None = None,
        amount: float | None = None,
        currency: str | None = None,
    ):
        """Notify freelancer that client marked payment as sent (question prompt)."""
        amount_text = ""
        if amount is not None:
            # Format amount to 2 decimal places
            formatted_amount = f"{amount:.2f}"
            amount_text = f" {currency or ''}{formatted_amount}"
        project_text = f" in project '{project_title}'" if project_title else ""
        message = f"Payment has been sent for milestone '{milestone_title}'{project_text}{amount_text}. Have you received it?".strip()

        return self.create_notification(
            user_id=freelancer_id,
            notification_type=NotificationType.MILESTONE_PAYMENT_CONFIRMED,
            title="Payment Sent for Milestone",
            message=message,
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "milestone_title": milestone_title,
                "project_title": project_title,
                "amount": amount,
                "currency": currency,
            },
            # Route freelancer to gig page for this agreement
            link=f"/creator/gig?agreement_id={agreement_id}",
            send_email=True,
        )

    def notify_milestone_completed(
        self,
        user_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        project_title: str | None = None,
        recipient_role: Optional[str] = None,
    ):
        """Notify both client and freelancer that milestone has been completed (after payment received)."""
        project_text = f" in project '{project_title}'" if project_title else ""
        message = f"Milestone '{milestone_title}'{project_text} has been completed successfully."
        
        # Determine URL based on recipient role
        if recipient_role == "CL":
            link = f"/owner/gig?agreement_id={agreement_id}"
        elif recipient_role == "FL":
            link = f"/creator/gig?agreement_id={agreement_id}"
        else:
            # Fallback to generic gig if role not provided
            link = f"/gig?agreement_id={agreement_id}"

        return self.create_notification(
            user_id=user_id,
            notification_type=NotificationType.MILESTONE_COMPLETED,
            title="Milestone Completed",
            message=message,
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "milestone_title": milestone_title,
                "project_title": project_title,
            },
            link=link,
            send_email=True,
        )

    def notify_milestone_work_completed(
        self,
        client_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        project_title: str | None = None,
    ):
        """Notify client that freelancer has completed the milestone work (waiting for verification)."""
        project_text = f" in project '{project_title}'" if project_title else ""
        message = f"Freelancer has completed milestone '{milestone_title}'{project_text}. Please verify the work."

        return self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.MILESTONE_COMPLETED,
            title="Milestone Work Completed",
            message=message,
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "milestone_title": milestone_title,
                "project_title": project_title,
            },
            link=f"/owner/gig?agreement_id={agreement_id}",
            send_email=True,
        )

    def notify_milestone_verified(
        self,
        freelancer_id: str,
        milestone_title: str,
        milestone_id: str,
        agreement_id: str,
        project_title: str | None = None,
    ):
        """Notify freelancer that client has verified the milestone (ready for payment)."""
        project_text = f" in project '{project_title}'" if project_title else ""
        message = f"Client has verified milestone '{milestone_title}'{project_text}. Payment will be sent soon."

        return self.create_notification(
            user_id=freelancer_id,
            notification_type=NotificationType.MILESTONE_APPROVED,
            title="Milestone Verified",
            message=message,
            data={
                "milestone_id": milestone_id,
                "agreement_id": agreement_id,
                "milestone_title": milestone_title,
                "project_title": project_title,
            },
            link=f"/creator/gig?agreement_id={agreement_id}",
            send_email=True,
        )

    def notify_request_accepted(
        self,
        client_id: str,
        freelancer_name: str,
        project_title: str,
        request_id: str,
        project_id: str
    ):
        """Notify client when freelancer accepts their request.
        
        Frontend: Routes to the client messages page on the DM tab (tab 0) where
        accepted requests are shown. The request_id parameter ensures the correct
        request is selected.
        """
        return self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.REQUEST_ACCEPTED,
            title="Request Accepted",
            message=f"Your request has been accepted for the project: {project_title}",
            data={
                "request_id": request_id,
                "project_id": project_id,
                "freelancer_name": freelancer_name,
                "project_title": project_title
            },
            # Navigate to client messages page, DM tab (tab 0, default)
            # No tab parameter needed since DM tab is the default
            link=f"/owner/messages?request_id={request_id}",
            send_email=True
        )

    def notify_request_rejected(
        self,
        client_id: str,
        freelancer_name: str,
        project_title: str,
        request_id: str,
        project_id: str
    ):
        """Notify client when freelancer rejects their request"""
        return self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.REQUEST_REJECTED,
            title="Request Response",
            message=f"There has been a respone to your request: {project_title}",
            data={
                "request_id": request_id,
                "project_id": project_id,
                "freelancer_name": freelancer_name,
                "project_title": project_title
            },
            link=f"/owner/messages?request_id={request_id}&tab=1",
            send_email=True
        )

    def notify_client_request_limit_reached(
        self,
        client_id: str,
        max_requests: int
    ):
        """Notify client when they reach their request limit"""
        return self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.CLIENT_REQUEST_LIMIT_REACHED,
            title="Request Limit Reached",
            message=f"You have reached your request limit of {max_requests} requests. You cannot send more requests until some are completed or cancelled.",
            data={
                "max_requests": max_requests,
                "current_count": max_requests
            },
            link="/owner/projects",
            send_email=True
        )

    def notify_agreement_sign_reminder(
        self,
        recipient_id: str,
        agreement_title: str,
        agreement_id: str,
        project_id: str,
        other_party_name: str,
        recipient_role: Optional[str] = None
    ):
        """Notify recipient to sign the agreement after the other party has signed"""
        # Determine recipient role if not provided
        if not recipient_role:
            try:
                from app.repositories.agreements import AgreementRepository
                agreement_repo = AgreementRepository()
                agreement = agreement_repo.get_by_id(agreement_id)
                if agreement:
                    client_id = agreement.get("client", {}).get("user_id")
                    freelancer_id = agreement.get("freelancer", {}).get("user_id")
                    if recipient_id == client_id:
                        recipient_role = "CL"
                    elif recipient_id == freelancer_id:
                        recipient_role = "FL"
            except Exception as e:
                logger.warning(f"Failed to determine recipient role from agreement {agreement_id}: {e}")
        
        # Determine URL based on recipient role
        if recipient_role == "CL":
            link = f"/owner/gig-agreement?agreement_id={agreement_id}"
        elif recipient_role == "FL":
            link = f"/creator/gig-agreement?agreement_id={agreement_id}"
        else:
            # Fallback to generic gig-agreement if role not provided
            link = f"/gig-agreement?agreement_id={agreement_id}"
        
        return self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.AGREEMENT_SIGN_REMINDER,
            title="Reminder to Sign Agreement",
            message=f"The other party has signed the agreement '{agreement_title}'. Please sign the agreement to proceed.",
            data={
                "agreement_id": agreement_id,
                "project_id": project_id,
                "agreement_title": agreement_title,
                "other_party_name": other_party_name
            },
            link=link,
            send_email=True
        )

    def notify_agreement_created(
        self,
        recipient_id: str,
        creator_name: str,
        agreement_title: str,
        agreement_id: str,
        project_id: str,
        recipient_role: Optional[str] = None
    ):
        """Notify recipient when an agreement is created"""
        # Determine recipient role if not provided
        if not recipient_role:
            try:
                from app.repositories.agreements import AgreementRepository
                agreement_repo = AgreementRepository()
                agreement = agreement_repo.get_by_id(agreement_id)
                if agreement:
                    client_id = agreement.get("client", {}).get("user_id")
                    freelancer_id = agreement.get("freelancer", {}).get("user_id")
                    if recipient_id == client_id:
                        recipient_role = "CL"
                    elif recipient_id == freelancer_id:
                        recipient_role = "FL"
            except Exception as e:
                logger.warning(f"Failed to determine recipient role from agreement {agreement_id}: {e}")
        
        # Determine URL based on recipient role
        if recipient_role == "CL":
            link = f"/owner/gig-agreement?agreement_id={agreement_id}"
        elif recipient_role == "FL":
            link = f"/creator/gig-agreement?agreement_id={agreement_id}"
        else:
            # Fallback to generic gig-agreement if role not provided
            link = f"/gig-agreement?agreement_id={agreement_id}"
        
        return self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.AGREEMENT_CREATED,
            title="New Agreement Created",
            message=f"A new agreement has been created: {agreement_title}",
            data={
                "agreement_id": agreement_id,
                "project_id": project_id,
                "creator_name": creator_name,
                "agreement_title": agreement_title
            },
            link=link,
            send_email=True
        )

    def notify_agreement_updated(
        self,
        recipient_id: str,
        agreement_title: str,
        agreement_id: str,
        project_id: str,
        recipient_role: Optional[str] = None
    ):
        """Notify recipient when an agreement is updated (without names)"""
        # Determine recipient role if not provided
        if not recipient_role:
            try:
                from app.repositories.agreements import AgreementRepository
                agreement_repo = AgreementRepository()
                agreement = agreement_repo.get_by_id(agreement_id)
                if agreement:
                    client_id = agreement.get("client", {}).get("user_id")
                    freelancer_id = agreement.get("freelancer", {}).get("user_id")
                    if recipient_id == client_id:
                        recipient_role = "CL"
                    elif recipient_id == freelancer_id:
                        recipient_role = "FL"
            except Exception as e:
                logger.warning(f"Failed to determine recipient role from agreement {agreement_id}: {e}")
        
        # Determine URL based on recipient role
        if recipient_role == "CL":
            link = f"/owner/gig-agreement?agreement_id={agreement_id}"
        elif recipient_role == "FL":
            link = f"/creator/gig-agreement?agreement_id={agreement_id}"
        else:
            # Fallback to generic gig-agreement if role not provided
            link = f"/gig-agreement?agreement_id={agreement_id}"
        
        return self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.AGREEMENT_UPDATED,
            title="Agreement Updated",
            message=f"The agreement has been updated: {agreement_title}",
            data={
                "agreement_id": agreement_id,
                "project_id": project_id,
                "agreement_title": agreement_title
            },
            link=link,
            send_email=True
        )

    def notify_agreement_version_accepted(
        self,
        recipient_id: str,
        accepting_party_name: str,
        agreement_title: str,
        agreement_id: str,
        project_id: str,
        recipient_role: Optional[str] = None
    ):
        """Notify recipient when the other party has accepted their version of the agreement"""
        # Determine recipient role if not provided
        if not recipient_role:
            try:
                from app.repositories.agreements import AgreementRepository
                agreement_repo = AgreementRepository()
                agreement = agreement_repo.get_by_id(agreement_id)
                if agreement:
                    client_id = agreement.get("client", {}).get("user_id")
                    freelancer_id = agreement.get("freelancer", {}).get("user_id")
                    if recipient_id == client_id:
                        recipient_role = "CL"
                    elif recipient_id == freelancer_id:
                        recipient_role = "FL"
            except Exception as e:
                logger.warning(f"Failed to determine recipient role from agreement {agreement_id}: {e}")
        
        # Determine URL based on recipient role
        if recipient_role == "CL":
            link = f"/owner/gig-agreement?agreement_id={agreement_id}"
        elif recipient_role == "FL":
            link = f"/creator/gig-agreement?agreement_id={agreement_id}"
        else:
            # Fallback to generic gig-agreement if role not provided
            link = f"/gig-agreement?agreement_id={agreement_id}"
        
        return self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.AGREEMENT_UPDATED,
            title="Agreement Version Accepted",
            message=f"The other party has accepted your version of the agreement '{agreement_title}'. You can now proceed to sign the agreement.",
            data={
                "agreement_id": agreement_id,
                "project_id": project_id,
                "agreement_title": agreement_title,
                "accepting_party_name": accepting_party_name,
                "type": "version_accepted"
            },
            link=link,
            send_email=True
        )

    def notify_dispute_raised(
        self,
        recipient_id: str,
        raised_by_role: str,
        subject: str,
        project_name: str | None,
        agreement_id: str | None,
        ticket_id: str,
        project_id: str | None = None,
        client_id: str | None = None,
        freelancer_id: str | None = None,
    ):
        """
        Notify the opposite party when a dispute is raised.
        `recipient_id` is the user who should receive the notification
        (opposite of the user who raised the ticket).

        Context uses project name (if provided) instead of project id.
        Roles are expressed as 'owner' (client) and 'creator' (freelancer).
        
        Routing logic:
        - If agreement_id exists (from gig page): route to /owner/gig or /creator/gig with agreement_id
        - Else if project_id exists (from message page): route to /owner/messages or /creator/messages with project_id
        - Else: fallback to /owner/messages or /creator/messages with ticket_id
        """
        # Map internal roles to friendly labels
        role_map = {
            "CL": "owner",
            "FL": "creator",
        }
        friendly_role = role_map.get(raised_by_role, "user")

        context_parts = []
        if project_name:
            context_parts.append(f"project \"{project_name}\"")
        # We deliberately do NOT show agreement_id in the user-facing text
        # If we want to indicate there is an agreement, use a generic label only
        if agreement_id:
            context_parts.append("agreement")
        context = " for " + ", ".join(context_parts) if context_parts else ""

        title = "Dispute raised"
        message = f"A dispute has been raised by the {friendly_role} about \"{subject}\"{context}."

        # Determine recipient's role (client or freelancer)
        recipient_role = None
        if client_id and recipient_id == client_id:
            recipient_role = "client"
        elif freelancer_id and recipient_id == freelancer_id:
            recipient_role = "freelancer"
        else:
            # Fallback: try to get role from user repository
            try:
                user = self.user_repo.get_user(user_id=recipient_id)
                if user:
                    role_code = user.get("role", "")
                    if role_code == "CL":
                        recipient_role = "client"
                    elif role_code == "FL":
                        recipient_role = "freelancer"
            except Exception:
                logger.warning(f"Could not determine recipient role for user_id={recipient_id}, defaulting to client")
                recipient_role = "client"  # Default fallback

        # Determine routing based on source and recipient role:
        # - If created from gig page (has agreement_id): route to gig page with agreement_id
        # - If created from message page (has project_id, no agreement_id): route to messages page with project_id
        # - Otherwise: fallback to messages page with ticket_id
        if agreement_id:
            # From gig page - route to gig page
            if recipient_role == "client":
                link = f"/owner/gig?agreement_id={agreement_id}"
            else:
                link = f"/creator/gig?agreement_id={agreement_id}"
        elif project_id:
            # From message page - route to messages page
            if recipient_role == "client":
                link = f"/owner/messages?project_id={project_id}"
            else:
                link = f"/creator/messages?project_id={project_id}"
        else:
            # Fallback - route to messages page with ticket_id
            if recipient_role == "client":
                link = f"/owner/messages?ticket_id={ticket_id}"
            else:
                link = f"/creator/messages?ticket_id={ticket_id}"

        return self.create_notification(
            user_id=recipient_id,
            notification_type=NotificationType.DISPUTE_RAISED,
            title=title,
            message=message,
            data={
                "ticket_id": ticket_id,
                "project_name": project_name,
                "agreement_id": agreement_id,
                "project_id": project_id,
                "raised_by_role": raised_by_role,
                "raised_by_role_label": friendly_role,
            },
            link=link,
            send_email=True,
        )

    def notify_dispute_resolved(
        self,
        client_id: str,
        freelancer_id: str,
        subject: str,
        project_name: str | None,
        agreement_id: str | None,
        ticket_id: str,
    ):
        """
        Notify both parties when a dispute is resolved.
        Context uses project name (if provided) instead of project id.
        """
        context_parts = []
        if project_name:
            context_parts.append(f"project \"{project_name}\"")
        # Again, do not expose agreement_id in text; just mention agreement generically
        if agreement_id:
            context_parts.append("agreement")
        context = " for " + ", ".join(context_parts) if context_parts else ""

        title = "Dispute resolved"
        message = f"The dispute \"{subject}\"{context} has been resolved."

        # notify client
        self.create_notification(
            user_id=client_id,
            notification_type=NotificationType.DISPUTE_RESOLVED,
            title=title,
            message=message,
            data={
                "ticket_id": ticket_id,
                "project_name": project_name,
                "agreement_id": agreement_id,
                "role": "CL",
            },
            link=f"/owner/projects?ticket_id={ticket_id}",
            send_email=True,
        )

        # notify freelancer
        self.create_notification(
            user_id=freelancer_id,
            notification_type=NotificationType.DISPUTE_RESOLVED,
            title=title,
            message=message,
            data={
                "ticket_id": ticket_id,
                "project_name": project_name,
                "agreement_id": agreement_id,
                "role": "FL",
            },
            link=f"/creator/gig?ticket_id={ticket_id}",
            send_email=True,
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

