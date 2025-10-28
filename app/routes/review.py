# app/routes/review.py
from fastapi import APIRouter, Depends, Query, status
from typing import Dict, Any, Optional
from app.models.review import ReviewCreate, ReviewUpdate
from app.services.review import ReviewService
from app.core.keycloak import get_current_user
from app.schemas.response import ok, APIResponse

router = APIRouter(prefix="/reviews", tags=["reviews"])
service = ReviewService()


# ➤ Create Review
@router.post("/", response_model=APIResponse, status_code=201)
def create_review(
    payload: ReviewCreate,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    created = service.create_review(payload, current_user)
    return ok(created, "Review created", status.HTTP_201_CREATED)


# # ➤ Update Review (future use)
# @router.put("/{review_id}", response_model=APIResponse)
# def update_review(
#     review_id: str,
#     payload: ReviewUpdate,
#     current_user: Dict[str, Any] = Depends(get_current_user),
# ):
#     updated = service.update_review(review_id, payload, current_user)
#     return ok(updated, "Review updated", status.HTTP_200_OK)


# # ➤ Delete Review (future use)
# @router.delete("/{review_id}", response_model=APIResponse)
# def delete_review(
#     review_id: str,
#     current_user: Dict[str, Any] = Depends(get_current_user),
# ):
#     service.delete_review(review_id, current_user)
#     return ok(None, "Review deleted", status.HTTP_200_OK)


# ➤ List Reviews for Freelancer
@router.get("/freelancer/{freelancer_id}", response_model=APIResponse)
def list_for_freelancer(
    freelancer_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    reviews = service.list_reviews_for_freelancer(freelancer_id, current_user, limit, skip)
    return ok(reviews, "Freelancer reviews fetched", status.HTTP_200_OK)


# ➤ List Reviews by Client
@router.get("/client/{client_id}", response_model=APIResponse)
def list_by_client(
    client_id: str,
    limit: int = Query(50, ge=1, le=200),
    skip: int = 0,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    reviews = service.list_reviews_by_client(client_id, current_user, limit, skip)
    return ok(reviews, "Client reviews fetched", status.HTTP_200_OK)


# # ➤ Get Review by ID (future use)
# @router.get("/{review_id}", response_model=APIResponse)
# def get_review(
#     review_id: str,
#     current_user: Dict[str, Any] = Depends(get_current_user),
# ):
#     review = service.get_review(review_id, current_user)
#     return ok(review, "Review fetched", status.HTTP_200_OK)


# ➤ Average Rating for Freelancer
@router.get("/average/review/{type}/{user_id}", response_model=APIResponse)
def avg_rating(
    type: str,
    user_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
):
    avg = service.average_rating(type, user_id, current_user)
    return ok({"user_id": user_id, "average": avg}, "Average rating fetched", status.HTTP_200_OK)
