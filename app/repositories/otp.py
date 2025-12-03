from datetime import datetime, timedelta, timezone
from typing import Optional

from pymongo.collection import Collection

from app.core.db import database
from app.models.otp import OTPPurpose


class OTPRepository:
    """
    Repository for persisting OTP verification attempts.
    Each (email, purpose) combination stores the latest OTP entry.
    """

    def __init__(self):
        self.collection: Collection = database["email_otp_verifications"]
        try:
            self.collection.create_index([("email", 1), ("purpose", 1)], unique=True)
            self.collection.create_index("expires_at", expireAfterSeconds=0)
        except Exception:
            # Index creation failures shouldn't block application startup.
            pass

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def upsert_otp(
        self,
        *,
        email: str,
        otp_code: str,
        purpose: OTPPurpose,
        ttl_seconds: int,
        max_attempts: int,
    ) -> dict:
        """
        Store or update the OTP for an email/purpose combination.
        """
        now = self._now()
        expires_at = now + timedelta(seconds=ttl_seconds)
        doc = {
            "email": email,
            "otp_code": otp_code,
            "purpose": purpose.value,
            "created_at": now,
            "expires_at": expires_at,
            "verified": False,
            "attempts": 0,
            "max_attempts": max_attempts,
            "last_sent_at": now,
        }
        self.collection.update_one(
            {"email": email, "purpose": purpose.value},
            {"$set": doc},
            upsert=True,
        )
        return doc

    def get_active_otp(self, email: str, purpose: OTPPurpose) -> Optional[dict]:
        return self.collection.find_one(
            {
                "email": email,
                "purpose": purpose.value,
                "expires_at": {"$gt": self._now()},
            },
            {"_id": 0},
        )

    def increment_attempts(self, email: str, purpose: OTPPurpose) -> Optional[dict]:
        return self.collection.find_one_and_update(
            {"email": email, "purpose": purpose.value},
            {"$inc": {"attempts": 1}},
            projection={"_id": 0},
            return_document=True,
        )

    def mark_verified(self, email: str, purpose: OTPPurpose) -> Optional[dict]:
        return self.collection.find_one_and_update(
            {"email": email, "purpose": purpose.value},
            {"$set": {"verified": True, "verified_at": self._now()}},
            projection={"_id": 0},
            return_document=True,
        )

    def delete_entry(self, email: str, purpose: OTPPurpose) -> None:
        self.collection.delete_one({"email": email, "purpose": purpose.value})

