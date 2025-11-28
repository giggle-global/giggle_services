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
        CL (Client) role limited to 1 active token (only one invite code)
        FL (Freelancer) and other roles limited to MAX_TOKENS_DEFAULT active tokens
        """
        user_id = requested_by_user["user_id"]
        role = requested_by_user.get("role")

        if role != RoleEnum.SUPER_ADMIN.value:
            if role == RoleEnum.CLIENT.value:
                # Clients can only generate ONE invite code
                active_count = self.repo.count_active_tokens_by_user(user_id)
                if active_count >= 1:
                    raise HTTPException(400, "You can only generate one invite code. You already have an active invite code.")
            else:
                # Freelancers and other roles have the default limit
                active_count = self.repo.count_active_tokens_by_user(user_id)
                if active_count >= MAX_TOKENS_DEFAULT:
                    raise HTTPException(400, f"Token generation limit exceeded ({MAX_TOKENS_DEFAULT}).")

        # Determine target_role based on who is generating the token
        from app.models.token import TokenTargetRole
        if role == RoleEnum.CLIENT.value:
            target_role = TokenTargetRole.CLIENT
        else:
            target_role = TokenTargetRole.FREELANCER

        payload = SignupTokenCreate(generated_by=user_id, target_role=target_role, ttl_seconds=ttl_seconds)
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

    def validate_token_for_signup(self, token: str, target_user_role: str = None) -> dict:
        """
        Validate token for signup. 
        target_user_role: The role of the user trying to sign up (FL or CL)
        """
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
        
        token_target_role = record.get("target_role")
        # Validate that token matches the signup role
        if token_target_role == "FL" and target_user_role != "FL":
            raise HTTPException(400, "This invite code is only valid for freelancer signup")
        if token_target_role == "CL" and target_user_role != "CL":
            raise HTTPException(400, "This invite code is only valid for client signup")
        
        return record

    def consume_token(self, token: str, new_user_id: str) -> dict:
        """
        Atomically mark token used and return updated record.
        If mark fails, raises HTTPException.
        """
        return self.repo.mark_used(token, new_user_id)

    def list_tokens(self, user_id: str) -> list:
        return self.repo.list_tokens_for_user(user_id)
    
    def get_active_token(self, user_id: str) -> Optional[dict]:
        """Get the active token for a user (useful for clients who can only have one)"""
        return self.repo.get_active_token_for_user(user_id)

    def revoke_token(self, token: str) -> dict:
        return self.repo.revoke_token(token)
