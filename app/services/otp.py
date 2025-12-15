import random
import string
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status

from app.core.email_service import EmailService
from app.models.otp import OTPPurpose
from app.repositories.otp import OTPRepository


class OTPService:
    """
    Handles OTP generation, rate-limiting, storage, and verification.
    """

    OTP_CODE_LENGTH = 4
    DEFAULT_TTL_SECONDS = 3 * 60  # 3 minutes
    DEFAULT_MAX_ATTEMPTS = 3
    RESEND_COOLDOWN_SECONDS = 60

    def __init__(
        self,
        repository: Optional[OTPRepository] = None,
        email_service: Optional[EmailService] = None,
    ):
        self.repo = repository or OTPRepository()
        self.email_service = email_service or EmailService()

    def _now(self):
        return datetime.now(timezone.utc)

    def _generate_code(self) -> str:
        alphabet = string.digits
        secure_random = random.SystemRandom()
        return "".join(secure_random.choice(alphabet) for _ in range(self.OTP_CODE_LENGTH))

    def _normalize_datetime(self, value) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, str):
            try:
                # Handle Mongo ISO strings that end with 'Z'
                iso_value = value.replace("Z", "+00:00") if value.endswith("Z") else value
                value = datetime.fromisoformat(iso_value)
            except ValueError:
                return None
        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc)
        return None

    def send_otp(self, email: str, purpose: OTPPurpose = OTPPurpose.SIGNUP) -> None:
        existing = self.repo.get_active_otp(email, purpose)
        if existing:
            last_sent_at = existing.get("last_sent_at")
            last_sent_at_dt = self._normalize_datetime(last_sent_at)
            if last_sent_at_dt and (self._now() - last_sent_at_dt).total_seconds() < self.RESEND_COOLDOWN_SECONDS:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"OTP already sent. Please wait {self.RESEND_COOLDOWN_SECONDS} seconds before requesting another.",
                )

        otp_code = self._generate_code()
        ttl_seconds = self.DEFAULT_TTL_SECONDS
        max_attempts = self.DEFAULT_MAX_ATTEMPTS

        self.repo.upsert_otp(
            email=email,
            otp_code=otp_code,
            purpose=purpose,
            ttl_seconds=ttl_seconds,
            max_attempts=max_attempts,
        )

        self._send_email(email=email, otp_code=otp_code, purpose=purpose, ttl_seconds=ttl_seconds)

    def _send_email(self, email: str, otp_code: str, purpose: OTPPurpose, ttl_seconds: int) -> None:
        ttl_minutes = ttl_seconds // 60

        if purpose == OTPPurpose.PASSWORD_RESET:
            subject = "Giggle – Reset Your Password"
            body_text = (
                f"We received a request to reset the password for {email}.\n\n"
                f"Your verification code is {otp_code}. It expires in {ttl_minutes} minutes.\n"
                "If you didn’t request this, you can safely ignore this email."
            )
            body_html = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; color: #0f172a;">
                    <h2 style="color:#2563eb;">Reset your password</h2>
                    <p>Hi there,</p>
                    <p>We received a request to reset the password for <strong>{email}</strong>.</p>
                    <p style="font-size: 18px; letter-spacing: 6px; font-weight: bold; color: #111827;">
                      {otp_code}
                    </p>
                    <p>This code expires in <strong>{ttl_minutes} minutes</strong>. If you didn’t request a reset, you can ignore this email.</p>
                    <p style="margin-top:24px;">Thanks,<br/>Giggle Support</p>
                  </body>
                </html>
            """
        elif purpose == OTPPurpose.PHONE_VERIFY:
            subject = "Giggle – Verify Your Phone"
            body_text = (
                f"We received a request to verify the phone number associated with {email}.\n\n"
                f"Your verification code is {otp_code}. It expires in {ttl_minutes} minutes.\n"
                "If you didn’t request this, you can safely ignore this email."
            )
            body_html = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; color: #0f172a;">
                    <h2 style="color:#2563eb;">Verify your phone</h2>
                    <p>Hi there,</p>
                    <p>Use the code below to verify your phone number for <strong>{email}</strong>.</p>
                    <p style="font-size: 18px; letter-spacing: 6px; font-weight: bold; color: #111827;">
                      {otp_code}
                    </p>
                    <p>This code expires in <strong>{ttl_minutes} minutes</strong>. If you didn’t request this, you can ignore this email.</p>
                    <p style="margin-top:24px;">Thanks,<br/>Giggle Support</p>
                  </body>
                </html>
            """
        else:
            subject = "Giggle – Verify Your Email"
            body_text = (
                f"Welcome to Giggle!\n\nYour verification code is {otp_code}. "
                f"It expires in {ttl_minutes} minutes. "
                "If you didn’t request this, please ignore the email."
            )
            body_html = f"""
                <html>
                  <body style="font-family: Arial, sans-serif; color: #0f172a;">
                    <h2 style="color:#2563eb;">Verify your email</h2>
                    <p>Hello,</p>
                    <p>Thanks for signing up. Use the code below to verify your email address.</p>
                    <p style="font-size: 18px; letter-spacing: 6px; font-weight: bold; color: #111827;">
                      {otp_code}
                    </p>
                    <p>This code expires in <strong>{ttl_minutes} minutes</strong>. If you didn’t create this account, you can ignore this email.</p>
                    <p style="margin-top:24px;">Thanks,<br/>Giggle Team</p>
                  </body>
                </html>
            """
        self.email_service.send_email(
            to_addresses=[email],
            subject=subject,
            body_html=body_html,
            body_text=body_text,
        )

    def verify_otp(self, email: str, otp_code: str, purpose: OTPPurpose = OTPPurpose.SIGNUP) -> None:
        record = self.repo.get_active_otp(email, purpose)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP not found or expired. Please request a new code.",
            )

        if record.get("verified"):
            return

        if record.get("attempts", 0) >= record.get("max_attempts", self.DEFAULT_MAX_ATTEMPTS):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Maximum OTP attempts exceeded. Please request a new code.",
            )

        if record.get("otp_code") != otp_code:
            updated = self.repo.increment_attempts(email, purpose)
            remaining = max(
                0,
                record.get("max_attempts", self.DEFAULT_MAX_ATTEMPTS) - (updated.get("attempts", 0)),
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {remaining} attempts remaining.",
            )

        self.repo.mark_verified(email, purpose)

    def clear_otp(self, email: str, purpose: OTPPurpose = OTPPurpose.SIGNUP) -> None:
        self.repo.delete_entry(email, purpose)

    def ensure_verified(self, email: str, purpose: OTPPurpose = OTPPurpose.SIGNUP) -> None:
        """
        Ensure that an email has a verified OTP before proceeding (e.g., signup).
        """
        record = self.repo.get_active_otp(email, purpose)
        if not record or not record.get("verified"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email verification required before continuing.",
            )

