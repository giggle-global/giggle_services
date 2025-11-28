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

        if not all([smtp_server, smtp_port, smtp_username, smtp_password, sender]):
            raise ValueError("SMTP configuration is incomplete. Please check environment variables.")

        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = sender
        message["To"] = ", ".join(to_addresses)

        if body_text:
            message.attach(MIMEText(body_text, "plain"))
        message.attach(MIMEText(body_html, "html"))

        try:
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.sendmail(sender, list(to_addresses), message.as_string())
                logger.info("SMTP email sent to %s", to_addresses)
        except Exception as exc:
            logger.exception("Failed to send email via SMTP")
            raise RuntimeError("Failed to send email via SMTP") from exc

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
            raise ValueError("SES sender email is not configured.")

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
            logger.exception("Failed to send email via SES")
            raise RuntimeError("Failed to send email via SES") from exc

