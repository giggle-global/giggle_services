import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional, Sequence

from app.core.config import config
from app.core.aws_utils import send_email_via_ses


logger = logging.getLogger(__name__)


class EmailService:
    """
    Simple email utility that can send messages via SMTP (default) or AWS SES.
    The provider is selected via the EMAIL_PROVIDER environment variable.
    """

    def __init__(self, provider: Optional[str] = None):
        self.provider = (provider or config.get("email_provider") or "smtp").lower()
        # Log email provider configuration on initialization for debugging
        logger.info("EmailService initialized with provider: %s", self.provider)
        
        # Validate configuration on initialization
        if self.provider == "smtp":
            smtp_server = config.get("smtp_server")
            smtp_port = config.get("smtp_port", 587)
            smtp_username = config.get("smtp_username")
            smtp_password = config.get("smtp_password")
            smtp_from = config.get("smtp_from_email")
            
            missing_config = []
            if not smtp_server:
                missing_config.append("SMTP_SERVER")
            if not smtp_username:
                missing_config.append("SMTP_USERNAME")
            if not smtp_password:
                missing_config.append("SMTP_PASSWORD")
            if not smtp_from:
                missing_config.append("SMTP_FROM_EMAIL")
            
            if missing_config:
                logger.warning("[WARNING] SMTP configuration incomplete. Missing: %s", ", ".join(missing_config))
                logger.warning("   Emails will fail to send until these are configured.")
            else:
                logger.info("[OK] SMTP configuration validated - Server: %s:%s, From: %s", 
                          smtp_server, smtp_port, smtp_from)
        elif self.provider == "ses":
            aws_key = config.get("aws_access_key")
            aws_secret = config.get("aws_secret_key")
            ses_from = config.get("ses_from_email")
            
            missing_config = []
            if not aws_key:
                missing_config.append("AWS_ACCESS_KEY")
            if not aws_secret:
                missing_config.append("AWS_SECRET_KEY")
            if not ses_from:
                missing_config.append("SES_FROM_EMAIL")
            
            if missing_config:
                logger.warning("[WARNING] AWS SES configuration incomplete. Missing: %s", ", ".join(missing_config))
                logger.warning("   Emails will fail to send until these are configured.")
            else:
                logger.info("[OK] AWS SES configuration validated - From: %s", ses_from)

    def send_email(
        self,
        to_addresses: Sequence[str],
        subject: str,
        body_html: str,
        body_text: Optional[str] = None,
        from_email: Optional[str] = None,
    ) -> None:
        if not to_addresses:
            raise ValueError("to_addresses must contain at least one email")

        if self.provider == "ses":
            self._send_via_ses(
                to_addresses=to_addresses,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_email=from_email,
            )
        else:
            # Default to SMTP to preserve current behaviour until SES is adopted.
            self._send_via_smtp(
                to_addresses=to_addresses,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_email=from_email,
            )

    def _send_via_smtp(
        self,
        to_addresses: Sequence[str],
        subject: str,
        body_html: str,
        body_text: Optional[str],
        from_email: Optional[str],
    ) -> None:
        smtp_server = config.get("smtp_server")
        smtp_port = config.get("smtp_port")
        smtp_username = config.get("smtp_username")
        smtp_password = config.get("smtp_password")
        sender = from_email or config.get("smtp_from_email") or smtp_username
        
        # Debug logging (without sensitive data)
        logger.debug("SMTP config - server: %s, port: %s, username: %s, sender: %s", 
                    smtp_server, smtp_port, smtp_username, sender)

        # Check which configuration values are missing
        missing_config = []
        if not smtp_server:
            missing_config.append("SMTP_SERVER")
        if not smtp_port:
            missing_config.append("SMTP_PORT")
        if not smtp_username:
            missing_config.append("SMTP_USERNAME")
        if not smtp_password:
            missing_config.append("SMTP_PASSWORD")
        if not sender:
            missing_config.append("SMTP_FROM_EMAIL or sender email")
        
        if missing_config:
            error_msg = f"SMTP configuration is incomplete. Missing environment variables: {', '.join(missing_config)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(to_addresses)

        if body_text:
            message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))

        try:
            logger.debug("Connecting to SMTP server %s:%s", smtp_server, smtp_port)
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                logger.debug("Starting TLS...")
                server.starttls()
                logger.debug("Logging in with username: %s", smtp_username)
                server.login(smtp_username, smtp_password)
                logger.debug("Sending email from %s to %s", sender, to_addresses)
                server.sendmail(sender, list(to_addresses), message.as_string())
                logger.info("[OK] SMTP email sent successfully to %s", to_addresses)
        except smtplib.SMTPAuthenticationError as exc:
            logger.error("[ERROR] SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD")
            logger.error("   Server: %s, Port: %s, Username: %s", smtp_server, smtp_port, smtp_username)
            logger.exception("Full authentication error:")
            raise RuntimeError("Failed to send email via SMTP: Authentication failed") from exc
        except smtplib.SMTPConnectError as exc:
            logger.error("[ERROR] SMTP connection failed. Check SMTP_SERVER and SMTP_PORT")
            logger.error("   Server: %s, Port: %s", smtp_server, smtp_port)
            logger.exception("Full connection error:")
            raise RuntimeError(f"Failed to send email via SMTP: Cannot connect to {smtp_server}:{smtp_port}") from exc
        except Exception as exc:
            logger.error("[ERROR] Failed to send email via SMTP: %s", str(exc))
            logger.error("   Server: %s, Port: %s, From: %s, To: %s", smtp_server, smtp_port, sender, to_addresses)
            logger.exception("Full SMTP error:")
            raise RuntimeError(f"Failed to send email via SMTP: {str(exc)}") from exc

    def _send_via_ses(
        self,
        to_addresses: Sequence[str],
        subject: str,
        body_html: str,
        body_text: Optional[str],
        from_email: Optional[str],
    ) -> None:
        sender = from_email or config.get("ses_from_email")
        if not sender:
            error_msg = "SES sender email is not configured. Please set SES_FROM_EMAIL or SMTP_FROM_EMAIL environment variable."
            logger.error(error_msg)
            raise ValueError(error_msg)
        
        # Check AWS credentials
        aws_access_key = config.get("aws_access_key")
        aws_secret_key = config.get("aws_secret_key")
        aws_region = config.get("aws_region")
        
        missing_aws = []
        if not aws_access_key:
            missing_aws.append("AWS_ACCESS_KEY")
        if not aws_secret_key:
            missing_aws.append("AWS_SECRET_KEY")
        if not aws_region:
            missing_aws.append("AWS_REGION")
        
        if missing_aws:
            error_msg = f"AWS SES configuration is incomplete. Missing environment variables: {', '.join(missing_aws)}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        try:
            send_email_via_ses(
                source=sender,
                to_addresses=list(to_addresses),
                subject=subject,
                body_text=body_text,
                body_html=body_html,
            )
            logger.info("SES email sent to %s", to_addresses)
        except Exception as exc:
            logger.exception("Failed to send email via SES: %s", str(exc))
            raise RuntimeError(f"Failed to send email via SES: {str(exc)}") from exc

    def send_notification_email(
        self,
        to_email: str,
        subject: str,
        message: str,
        notification_data: Optional[dict] = None
    ) -> None:
        """Send a notification email with HTML template"""
        logger.info("Preparing notification email to %s with subject: %s", to_email, subject)
        
        # Build link URL if provided
        link_url = "#"
        if notification_data and notification_data.get("link"):
            link_url = notification_data.get("link")
            logger.debug("Notification email includes link: %s", link_url)
        
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px 8px 0 0; }}
                .content {{ background: #f9f9f9; padding: 20px; border-radius: 0 0 8px 8px; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin-top: 20px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h2>Giggle Notification</h2>
                </div>
                <div class="content">
                    <p>{message}</p>
                    {f'<a href="{link_url}" class="button">View Details</a>' if link_url != "#" else ""}
                </div>
            </div>
        </body>
        </html>
        """
        
        text_body = message
        
        logger.debug("Calling send_email with provider: %s", self.provider)
        try:
            self.send_email(
                to_addresses=[to_email],
                subject=subject,
                body_html=html_body,
                body_text=text_body
            )
            logger.info("Notification email sent successfully via %s to %s", self.provider, to_email)
        except Exception as e:
            logger.error("Failed to send notification email to %s via %s: %s", to_email, self.provider, str(e))
            raise

