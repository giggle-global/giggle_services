# app/routes/token.py
from fastapi import APIRouter, Depends, HTTPException
from typing import List
from app.services.token import TokenService
from app.models.token import SignupTokenOut
from app.core.keycloak import get_current_user  # your dependency that returns user dict
from app.schemas.response import APIResponse
from starlette import status

router = APIRouter(prefix="/tokens", tags=["TOKENS"])
token_service = TokenService()

@router.post("/generate", response_model=APIResponse)
def generate_token(
    ttl_seconds: int = 24*3600, 
    current_user: dict = Depends(get_current_user)
):
    token: SignupTokenOut = token_service.generate_token(current_user, ttl_seconds=ttl_seconds)
    token_dict = token.model_dump()      # convert Pydantic object -> dict
    return APIResponse(data=token_dict, message="Token generated successfully", status_code=status.HTTP_201_CREATED)

@router.get("/client/invite-code", response_model=APIResponse)
def get_client_invite_code(
    current_user: dict = Depends(get_current_user)
):
    """
    Get or generate invite code for clients.
    Clients can only have one active invite code.
    If they already have one, return it. Otherwise, generate a new one.
    """
    user_role = current_user.get("role")
    if user_role != "CL":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This endpoint is only available for clients")
    
    user_id = current_user["user_id"]
    
    # Check if client already has an active invite code
    active_token = token_service.get_active_token(user_id)
    
    if active_token:
        # Return existing active token
        return APIResponse(
            data=active_token,
            message="Invite code retrieved successfully",
            status_code=status.HTTP_200_OK
        )
    else:
        # Check if client has any tokens (even if expired/used) to prevent duplicate generation
        # If they have tokens but none are active, we'll still generate a new one
        # But first, try to generate - if it fails with "already have" error, 
        # try to get the most recent token from the list
        try:
            # Generate new token (will enforce one-code limit in generate_token)
            token: SignupTokenOut = token_service.generate_token(current_user, ttl_seconds=365*24*3600)  # 1 year expiry for client codes
            token_dict = token.model_dump()
            return APIResponse(
                data=token_dict,
                message="Invite code generated successfully",
                status_code=status.HTTP_201_CREATED
            )
        except HTTPException as e:
            # If error is about already having a code, try to get it from the list
            if "already have" in str(e.detail).lower() or "one invite code" in str(e.detail).lower():
                # Get all tokens and find the most recent active one
                all_tokens = token_service.list_tokens(user_id)
                if all_tokens:
                    # Find the most recent non-expired, non-used token
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    for token_item in all_tokens:
                        expires_at = token_item.get("expires_at")
                        used = token_item.get("used", False)
                        
                        if not used and expires_at:
                            # Handle datetime conversion
                            if isinstance(expires_at, datetime):
                                if expires_at.tzinfo is None:
                                    expires_at = expires_at.replace(tzinfo=timezone.utc)
                                if expires_at > now:
                                    return APIResponse(
                                        data=token_item,
                                        message="Invite code retrieved successfully",
                                        status_code=status.HTTP_200_OK
                                    )
                    # If no active token found but tokens exist, return the most recent one anyway
                    # (user might have an expired code, but we'll show it)
                    return APIResponse(
                        data=all_tokens[0],
                        message="Invite code retrieved successfully",
                        status_code=status.HTTP_200_OK
                    )
            # Re-raise the original exception if we can't handle it
            raise

@router.get("/", response_model=List[SignupTokenOut])
def list_tokens(current_user: dict = Depends(get_current_user)):
    # return token_service.list_tokens(current_user["user_id"])
    return APIResponse(
        data=token_service.list_tokens(current_user["user_id"]),
        message="Tokens retrieved successfully",
        code=status.HTTP_200_OK
    )

# @router.post("/validate")
# def validate_token(payload: dict, current_user: dict = Depends(get_current_user)):
#     """
#     Validate token. Payload: {"token": "<token-string>"}
#     (This endpoint can be public if you want validation during signup without auth;
#     but your signup flow has no auth, so better expose a public /tokens/validate endpoint.)
#     """
#     token = payload.get("token")
#     return token_service.validate_token_for_signup(token)

# @router.post("/revoke")
# def revoke_token(payload: dict, current_user: dict = Depends(get_current_user)):
#     token = payload.get("token")
#     return token_service.revoke_token(token)
