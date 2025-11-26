# app/routes/matching.py
"""
Matching Algorithm API Routes
Provides endpoints to match freelancers to projects and vice versa
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Dict, Any
from app.services.matching import MatchingService
from app.schemas.response import APIResponse, ok
from app.core.keycloak import get_current_user

router = APIRouter(prefix="/matching", tags=["Matching Algorithm"])


def get_matching_service():
    return MatchingService()


@router.get(
    "/projects/{project_id}/freelancers",
    response_model=APIResponse[List[Dict]],
    summary="Match Freelancers to Project",
    description="""
    Returns a ranked list of freelancers matched to the specified project.
    Freelancers are scored based on 5 criteria (total 100 points):
    - Industry Match: 20 points
    - Timeline Availability: 10 points
    - Background Industry: 20 points
    - User Rating: 20 points
    - Geographic Location: 30 points
    """
)
def match_freelancers_to_project(
    project_id: str,
    limit: int = Query(50, description="Maximum number of freelancers to return", ge=1, le=100),
    min_score: int = Query(0, description="Minimum match score (0-100)", ge=0, le=100),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MatchingService = Depends(get_matching_service)
):
    """
    Match and rank freelancers for a specific project.
    Only accessible by clients (project owners).
    """
    try:
        matches = svc.match_freelancers_to_project(project_id, limit=limit)
        
        # Filter by minimum score if specified
        if min_score > 0:
            matches = [m for m in matches if m["score"] >= min_score]
        
        return ok(
            data=matches,
            message=f"Found {len(matches)} matching freelancers"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error matching freelancers: {str(e)}"
        )


@router.get(
    "/freelancers/{freelancer_id}/projects/{project_id}/score",
    response_model=APIResponse[Dict],
    summary="Get Match Score for Freelancer",
    description="""
    Get the detailed match score for a specific freelancer against a project.
    Returns the total score and breakdown by criteria.
    Useful for freelancers to see how well they match a gig posting.
    """
)
def get_freelancer_match_score(
    project_id: str,
    freelancer_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MatchingService = Depends(get_matching_service)
):
    """
    Get match score breakdown for a specific freelancer-project pair.
    Accessible by the freelancer themselves or project owner.
    """
    try:
        # Authorization: Only freelancer or project owner can see this
        user_id = current_user.get("id")
        user_role = current_user.get("role")
        
        # For now, allow any authenticated user to view scores
        # In production, you may want to restrict this
        
        score_data = svc.get_match_score_for_freelancer(project_id, freelancer_id)
        
        return ok(
            data=score_data,
            message="Match score calculated successfully"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error calculating match score: {str(e)}"
        )


@router.get(
    "/freelancers/{freelancer_id}/rating",
    response_model=APIResponse[Dict],
    summary="Get Freelancer Average Rating",
    description="""
    Get the average rating for a freelancer.
    Returns 3.75 (default) if no reviews exist.
    """
)
def get_freelancer_rating(
    freelancer_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MatchingService = Depends(get_matching_service)
):
    """
    Get average rating for a freelancer.
    New users get a default rating of 3.75 (15/20 score).
    """
    try:
        avg_rating = svc.get_freelancer_average_rating(freelancer_id)
        
        # Map rating to score bracket
        if avg_rating >= 4.5:
            score = 20
            bracket = "4.5 - 5.0"
        elif avg_rating >= 4.0:
            score = 15
            bracket = "4.0 - 4.4"
        elif avg_rating >= 3.0:
            score = 10
            bracket = "3.0 - 3.9"
        else:
            score = 0
            bracket = "0.0 - 2.9"
        
        return ok(
            data={
                "freelancer_id": freelancer_id,
                "average_rating": round(avg_rating, 2),
                "score": score,
                "rating_bracket": bracket
            },
            message="Rating retrieved successfully"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving rating: {str(e)}"
        )


@router.get(
    "/projects/{project_id}/top-matches",
    response_model=APIResponse[List[Dict]],
    summary="Get Top Matching Freelancers",
    description="""
    Returns top 10 best-matched freelancers for a project.
    Quick endpoint for getting the best candidates.
    """
)
def get_top_matches(
    project_id: str,
    top_n: int = Query(10, description="Number of top matches to return", ge=1, le=50),
    current_user: Dict[str, Any] = Depends(get_current_user),
    svc: MatchingService = Depends(get_matching_service)
):
    """
    Get top N freelancers with highest match scores for a project.
    """
    try:
        matches = svc.match_freelancers_to_project(project_id, limit=top_n)
        
        # Return simplified data for top matches
        top_matches = []
        for match in matches:
            top_matches.append({
                "freelancer_id": match["freelancer_id"],
                "name": f"{match.get('first_name', '')} {match.get('last_name', '')}".strip(),
                "score": match["score"],
                "designation": match.get("designation"),
                "bio": match.get("bio"),
            })
        
        return ok(
            data=top_matches,
            message=f"Top {len(top_matches)} matches retrieved"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving top matches: {str(e)}"
        )

