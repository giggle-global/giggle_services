# app/routes/review.py
from fastapi import APIRouter, Depends, Query
from typing import List
from app.models.review import ReviewCreate, ReviewOut, ReviewUpdate
from app.services.review import ReviewService
from app.core.keycloak import get_current_user  # your JWT dependency

router = APIRouter(prefix="/reviews", tags=["reviews"])
service = ReviewService()

@router.post("/", response_model=ReviewOut)
def create_review(payload: ReviewCreate, current_user: dict = Depends(get_current_user)):
    return service.create_review(payload, current_user)

# @router.put("/{review_id}", response_model=ReviewOut)
# def update_review(review_id: str, payload: ReviewUpdate, current_user: dict = Depends(get_current_user)):
#     return service.update_review(review_id, payload, current_user)

# @router.delete("/{review_id}")
# def delete_review(review_id: str, current_user: dict = Depends(get_current_user)):
#     service.delete_review(review_id, current_user)
#     return {"detail": "Review deleted"}

@router.get("/freelancer/{freelancer_id}", response_model=List[ReviewOut])
def list_for_freelancer(freelancer_id: str, limit: int = Query(50, ge=1, le=200), skip: int = 0, current_user: dict = Depends(get_current_user)):
    return service.list_reviews_for_freelancer(freelancer_id, current_user, limit, skip)

@router.get("/client/{client_id}", response_model=List[ReviewOut])
def list_by_client(client_id: str, limit: int = Query(50, ge=1, le=200), skip: int = 0, current_user: dict = Depends(get_current_user)):
    return service.list_reviews_by_client(client_id, current_user, limit, skip)

# @router.get("/{review_id}", response_model=ReviewOut)
# def get_review(review_id: str, current_user: dict = Depends(get_current_user)):
#     return service.get_review(review_id, current_user)

@router.get("/freelancer/{freelancer_id}/average")
def avg_rating(freelancer_id: str, current_user: dict = Depends(get_current_user)):
    avg = service.average_rating(freelancer_id, current_user)
    return {"freelancer_id": freelancer_id, "average": avg}
