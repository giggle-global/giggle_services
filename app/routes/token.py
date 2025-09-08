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
