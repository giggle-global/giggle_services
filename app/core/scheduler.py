"""
Background scheduler for milestone reminders and other scheduled tasks
Uses APScheduler for cron-like scheduling
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, timedelta
from app.repositories.milestones import MilestoneRepository
from app.repositories.agreements import AgreementRepository
from app.services.notification import NotificationService
from app.models.milestones import MilestoneStatus

logger = logging.getLogger(__name__)

class MilestoneScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.milestone_repo = MilestoneRepository()
        self.agreement_repo = AgreementRepository()
        self.notification_service = NotificationService()
        self._setup_jobs()

    def _setup_jobs(self):
        """Setup scheduled jobs"""
        # Run at the start of each hour (00:00, 01:00, 02:00, etc.) to check for milestones due in 24 hours
        self.scheduler.add_job(
            func=self._check_milestone_reminders,
            trigger=CronTrigger(minute=0),  # Run at minute 0 of every hour
            id='milestone_reminder_check',
            name='Check milestones due in 24 hours',
            replace_existing=True
        )
        logger.info("Milestone scheduler jobs configured - will run at the start of each hour")

    def _check_milestone_reminders(self):
        """Check for milestones due in 24 hours and send notifications"""
        try:
            logger.info("Running milestone reminder check...")
            now = datetime.utcnow()
            # 24 hours from now
            target_time = now + timedelta(hours=24)
            
            # Get all active milestones (Pending or InProgress)
            from app.core.db import database
            milestones_collection = database["milestones"]
            all_milestones = list(milestones_collection.find({
                "status": {"$in": [MilestoneStatus.PENDING.value, MilestoneStatus.IN_PROGRESS.value]},
                "due_date": {"$exists": True, "$ne": None}
            }, {"_id": 0}))

            from app.repositories.notification import NotificationRepository
            notification_repo = NotificationRepository()
            
            for milestone in all_milestones:
                due_date_epoch = milestone.get("due_date")
                if not due_date_epoch:
                    continue
                
                due_date = datetime.fromtimestamp(due_date_epoch)
                
                # Check if milestone is due in approximately 24 hours (±1 hour window)
                time_diff = (due_date - now).total_seconds()
                hours_until_due = time_diff / 3600
                
                # If between 23-25 hours, send reminder
                if 23 <= hours_until_due <= 25:
                    milestone_id = milestone.get("milestone_id")
                    agreement_id = milestone.get("agreement_id")
                    
                    # Check if we've already sent a reminder for this milestone today
                    # Look for existing notifications with this milestone_id and type
                    from app.core.db import database
                    notifications_collection = database["notifications"]
                    existing_notifications = list(notifications_collection.find({
                        "type": "milestone_reminder",
                        "data.milestone_id": milestone_id,
                        "created_at": {
                            "$gte": int((now - timedelta(hours=2)).timestamp())  # Within last 2 hours
                        }
                    }).limit(1))
                    
                    if existing_notifications:
                        logger.debug("Reminder already sent for milestone: %s", milestone_id)
                        continue
                    
                    # Get agreement to find client and freelancer
                    agreement = self.agreement_repo.get_by_id(agreement_id)
                    if not agreement:
                        logger.warning("Agreement not found for milestone: %s", milestone_id)
                        continue
                    
                    client_id = agreement.get("client", {}).get("user_id")
                    freelancer_id = agreement.get("freelancer", {}).get("user_id")
                    milestone_title = milestone.get("title", "Milestone")
                    
                    # Send notification to both client and freelancer
                    try:
                        if freelancer_id:
                            self.notification_service.notify_milestone_reminder(
                                user_id=freelancer_id,
                                milestone_title=milestone_title,
                                milestone_id=milestone_id,
                                agreement_id=agreement_id,
                                due_date=due_date_epoch
                            )
                            logger.info("Milestone reminder sent to freelancer: %s milestone: %s", freelancer_id, milestone_id)
                        
                        if client_id:
                            self.notification_service.notify_milestone_reminder(
                                user_id=client_id,
                                milestone_title=milestone_title,
                                milestone_id=milestone_id,
                                agreement_id=agreement_id,
                                due_date=due_date_epoch
                            )
                            logger.info("Milestone reminder sent to client: %s milestone: %s", client_id, milestone_id)
                    except Exception as e:
                        logger.error("Error sending milestone reminder: %s", e)
                        continue
            
            logger.info("Milestone reminder check completed")
        except Exception as e:
            logger.exception("Error in milestone reminder check: %s", e)

    def start(self):
        """Start the scheduler"""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("Milestone scheduler started")
        else:
            logger.warning("Scheduler is already running")

    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("Milestone scheduler stopped")

# Global scheduler instance
milestone_scheduler = MilestoneScheduler()

