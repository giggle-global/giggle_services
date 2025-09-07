# app/services/token.py
from datetime import datetime, timezone
from typing import Optional
from fastapi import HTTPException
from app.repositories.token import TokenRepository
from app.models.token import SignupTokenCreate, SignupTokenOut
from app.models.user import RoleEnum  # reuse your RoleEnum

MAX_TOKENS_DEFAULT = 5

class TokenService:
    def __init__(self, repo: TokenRepository = None):
        self.repo = repo or TokenRepository()

    def generate_token(self, requested_by_user: dict, ttl_seconds: int = 24*3600) -> SignupTokenOut:
        """
        requested_by_user: dict includes 'user_id' and 'role' fields
        SA role bypasses limit (unlimited)
        normal users limited to MAX_TOKENS_DEFAULT active tokens
        """
        user_id = requested_by_user["user_id"]
        role = requested_by_user.get("role")

        if role != RoleEnum.SUPER_ADMIN.value:
            active_count = self.repo.count_active_tokens_by_user(user_id)
            if active_count >= MAX_TOKENS_DEFAULT:
                raise HTTPException(400, f"Token generation limit exceeded ({MAX_TOKENS_DEFAULT}).")

        payload = SignupTokenCreate(generated_by=user_id, ttl_seconds=ttl_seconds)
        return self.repo.create_token(payload)
    
    def _now_for_query(self):
    # If DB stores tz-aware datetimes, return aware; else return naive UTC.
    # If you don't know, store tz-aware and use aware everywhere.
        return datetime.now(timezone.utc)
    
    def _to_aware_utc(self, dt: Optional[datetime]) -> Optional[datetime]:
        """
        Convert a datetime to timezone-aware UTC.
        - If dt is None -> returns None
        - If dt.tzinfo is None -> assume it's UTC and set tzinfo=timezone.utc
        - Otherwise convert to UTC
        """
        if dt is None:
            return None
        if dt.tzinfo is None:
            # PyMongo commonly returns naive UTC datetimes, treat them as UTC
            return dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)

    def validate_token_for_signup(self, token: str) -> dict:
        if not token:
            raise HTTPException(400, "Token required")
        record = self.repo.get_by_token(token)
        if not record:
            raise HTTPException(400, "Invalid token")
        now = datetime.now(timezone.utc)
        if record.get("used"):
            raise HTTPException(400, "Token already used")
        expires_at = self._to_aware_utc(record.get("expires_at"))
        if not expires_at:
            # defensive: invalid token record
            raise HTTPException(400, "Token record invalid: missing expires_at")
        if expires_at <= now:
            raise HTTPException(400, "Token expired")
        if record.get("target_role") != "FL":
            raise HTTPException(400, "Token not valid for freelancer signup")
        return record

    def consume_token(self, token: str, new_user_id: str) -> dict:
        """
        Atomically mark token used and return updated record.
        If mark fails, raises HTTPException.
        """
        return self.repo.mark_used(token, new_user_id)

    def list_tokens(self, user_id: str) -> list:
        return self.repo.list_tokens_for_user(user_id)

    def revoke_token(self, token: str) -> dict:
        return self.repo.revoke_token(token)
