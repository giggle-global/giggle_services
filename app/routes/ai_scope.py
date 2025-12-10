"""AI scope assistant endpoints."""

from typing import Any, Dict

from fastapi import APIRouter, Depends, status

from app.core.keycloak import get_current_user
from app.models.ai_scope import (
    ScopeConfirmRequest,
    ScopeConfirmResponse,
    ScopeQuestionRequest,
    ScopeQuestionResponse,
    ScopeSuggestionUpdate,
    ScopeSuggestionRequest,
    ScopeSuggestionResponse,
)
from app.schemas.response import APIResponse, ok
from app.services.ai_scope import AIScopeService

router = APIRouter(prefix="/ai/scope", tags=["AI Scope Assistant"])


def get_ai_scope_service() -> AIScopeService:
    return AIScopeService()


@router.post(
    "/question",
    response_model=APIResponse[ScopeQuestionResponse],
    status_code=status.HTTP_200_OK,
)
def next_question(
    payload: ScopeQuestionRequest,
    svc: AIScopeService = Depends(get_ai_scope_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Return the next clarifying question for the AI scope wizard."""
    response = svc.next_question(payload)
    return ok(data=response, message="Next question generated")


@router.post(
    "/suggestion",
    response_model=APIResponse[ScopeSuggestionResponse],
    status_code=status.HTTP_200_OK,
)
def scope_suggestion(
    payload: ScopeSuggestionRequest,
    svc: AIScopeService = Depends(get_ai_scope_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Generate scope summary, content plan, and budget recommendation."""
    response = svc.generate_suggestion(payload)
    return ok(data=response, message="Scope recommendation generated")


@router.post(
    "/suggestion/update",
    response_model=APIResponse[ScopeSuggestionResponse],
    status_code=status.HTTP_200_OK,
)
def scope_suggestion_update(
    payload: ScopeSuggestionUpdate,
    svc: AIScopeService = Depends(get_ai_scope_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Apply inline edits to an existing suggestion (no AI regeneration)."""
    response = svc.update_suggestion(payload)
    return ok(data=response, message="Scope suggestion updated")


@router.post(
    "/confirm",
    response_model=APIResponse[ScopeConfirmResponse],
    status_code=status.HTTP_201_CREATED,
)
def confirm_scope(
    payload: ScopeConfirmRequest,
    svc: AIScopeService = Depends(get_ai_scope_service),
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    """Confirm scope, create project, and return top matched freelancers."""
    response = svc.confirm_scope(payload, current_user=current_user)
    return ok(
        data=response,
        message="Scope confirmed, project created, and matches prepared",
        status_code=status.HTTP_201_CREATED,
    )
