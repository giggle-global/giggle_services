# app/services/matching.py
"""
User-Matching Algorithm Service
Implements the Giggle matching algorithm with 5 scoring criteria:
- Industry Match (20 pts)
- Timeline Availability (10 pts)
- Background Industry (20 pts)
- User Rating (20 pts)
- Geographic Location (30 pts)
Total: 100 pts
"""

from typing import List, Dict, Optional
from app.repositories.user import UserRepository
from app.repositories.project import ProjectRepository
from app.repositories.portfolio import PortfolioRepository
from app.repositories.review import ReviewRepository
from app.models.project import LocationRequirement
import logging

logger = logging.getLogger(__name__)


class MatchingService:
    def __init__(self):
        self.user_repo = UserRepository()
        self.project_repo = ProjectRepository()
        self.portfolio_repo = PortfolioRepository()
        self.review_repo = ReviewRepository()

    def match_freelancers_to_project(self, project_id: str, limit: int = 50) -> List[Dict]:
        """
        Match and rank freelancers for a given project
        Returns list of freelancers with their match scores (0-100)
        """
        # Get project details
        project = self.project_repo.find_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")

        # Get all freelancers
        freelancers = self.user_repo.find_by_role("FL")
        
        # Calculate scores for each freelancer
        matches = []
        for freelancer in freelancers:
            if freelancer.get("status") != "ACTIVE":
                continue
                
            score_breakdown = self._calculate_match_score(project, freelancer)
            total_score = score_breakdown["total"]
            
            matches.append({
                "freelancer_id": freelancer.get("user_id"),
                "username": freelancer.get("username"),
                "first_name": freelancer.get("first_name"),
                "last_name": freelancer.get("last_name"),
                "email": freelancer.get("email"),
                "score": total_score,
                "score_breakdown": score_breakdown,
                "profile_pic": freelancer.get("profile_pic"),
                "bio": freelancer.get("bio"),
                "designation": freelancer.get("designation"),
            })
        
        # Sort by score (highest first)
        matches.sort(key=lambda x: x["score"], reverse=True)
        
        return matches[:limit]

    def _calculate_match_score(self, project: Dict, freelancer: Dict) -> Dict:
        """
        Calculate match score breakdown for a freelancer against a project
        Returns dict with individual scores and total
        """
        industry_score = self._calculate_industry_score(project, freelancer)
        timeline_score = self._calculate_timeline_score(project, freelancer)
        background_score = self._calculate_background_score(project, freelancer)
        rating_score = self._calculate_rating_score(freelancer)
        geography_score = self._calculate_geography_score(project, freelancer)
        
        total = industry_score + timeline_score + background_score + rating_score + geography_score
        
        return {
            "industry": industry_score,
            "timeline": timeline_score,
            "background": background_score,
            "rating": rating_score,
            "geography": geography_score,
            "total": total,
        }

    def _calculate_industry_score(self, project: Dict, freelancer: Dict) -> int:
        """
        Industry Match Score: 0-20 points
        Check if freelancer's skills match the project industry
        """
        project_industry = project.get("industry", "").lower()
        if not project_industry:
            return 20  # No specific industry required
        
        # Check freelancer skills
        freelancer_skills = freelancer.get("skill_set", [])
        if not freelancer_skills:
            return 0
        
        # Simple keyword matching (can be enhanced)
        freelancer_skills_str = " ".join([s.lower() for s in freelancer_skills])
        
        # Check if project industry keywords are in freelancer skills
        if project_industry in freelancer_skills_str:
            return 20
        
        # Partial match based on common keywords
        industry_keywords = project_industry.split()
        matches = sum(1 for keyword in industry_keywords if keyword in freelancer_skills_str)
        
        if matches > 0:
            return min(20, matches * 10)  # Partial credit
        
        return 0

    def _calculate_timeline_score(self, project: Dict, freelancer: Dict) -> int:
        """
        Timeline Availability Score: 0-10 points
        Based on freelancer's current workload
        """
        timeline_weeks = project.get("timeline_weeks", 0)
        ongoing_gigs = freelancer.get("ongoing_gigs_count", 0)
        
        # If no timeline specified, give full score
        if not timeline_weeks:
            return 10
        
        # Score based on ongoing gigs count
        if ongoing_gigs == 0:
            return 10  # Fully available
        elif ongoing_gigs == 1:
            return 5   # Partially available
        else:
            return 2   # Busy with multiple gigs

    def _calculate_background_score(self, project: Dict, freelancer: Dict) -> int:
        """
        Background Industry Score: 0-20 points
        Check if freelancer has experience in the client's industry background
        """
        background_industry = project.get("background_industry", "").lower()
        if not background_industry:
            return 20  # No specific background required
        
        # Check portfolio for matching industry experience
        portfolios = self.portfolio_repo.find_by_user_id(freelancer.get("user_id"))
        
        for portfolio in portfolios:
            # Check if portfolio has tags or description matching the background
            portfolio_str = (
                portfolio.get("title", "") + " " + 
                portfolio.get("description", "")
            ).lower()
            
            if background_industry in portfolio_str:
                return 20  # Has proven experience
        
        # Check interested industries (for newcomers)
        interested = freelancer.get("interested_industries", [])
        if interested and background_industry in " ".join(interested).lower():
            return 10  # Interested but no proven experience
        
        return 0  # No match

    def _calculate_rating_score(self, freelancer: Dict) -> int:
        """
        User Rating Score: 0-20 points
        Based on average rating from reviews
        Rating Range -> Score:
        - 4.5 - 5.0  -> 20/20
        - 4.0 - 4.4  -> 15/20
        - 3.0 - 3.9  -> 10/20
        - 0.0 - 2.9  -> 0/20
        - No ratings -> 15/20 (default for new users)
        """
        freelancer_id = freelancer.get("user_id")
        
        # Get all reviews for this freelancer
        reviews = self.review_repo.find_by_freelancer_id(freelancer_id)
        
        if not reviews or len(reviews) == 0:
            return 15  # Default score for new users (equivalent to 3.75 stars)
        
        # Calculate average rating
        total_stars = sum(review.get("stars", 0) for review in reviews)
        avg_rating = total_stars / len(reviews)
        
        # Map rating to score
        if avg_rating >= 4.5:
            return 20
        elif avg_rating >= 4.0:
            return 15
        elif avg_rating >= 3.0:
            return 10
        else:
            return 0

    def _calculate_geography_score(self, project: Dict, freelancer: Dict) -> int:
        """
        Geographic Location Score: 0-30 points
        Based on proximity matrix:
        
        User Requirement | Freelancer Location
                        | Same City | Same Region | Same Country | Anywhere
        Same City       |   30      |    30       |     30       |   30
        Same Region     |   20      |    30       |     30       |   30
        Same Country    |   10      |    20       |     30       |   30
        Rest of World   |    0      |     0       |      0       |   30
        """
        location_preference = project.get("location_preference", LocationRequirement.ANYWHERE.value)
        
        # If anywhere is acceptable, everyone gets full score
        if location_preference == LocationRequirement.ANYWHERE.value:
            return 30
        
        # Get location details
        required_loc = project.get("required_location", {})
        freelancer_loc = freelancer.get("location_info", {})
        
        if not required_loc or not freelancer_loc:
            # If location data is missing, give partial score
            return 15
        
        req_city = required_loc.get("city", "").lower()
        req_region = required_loc.get("region", "").lower()
        req_country = required_loc.get("country", "").lower()
        
        fr_city = freelancer_loc.get("city", "").lower()
        fr_region = freelancer_loc.get("region", "").lower()
        fr_country = freelancer_loc.get("country", "").lower()
        
        # Check city match
        same_city = req_city and fr_city and req_city == fr_city
        same_region = req_region and fr_region and req_region == fr_region
        same_country = req_country and fr_country and req_country == fr_country
        
        # Apply scoring matrix
        if location_preference == LocationRequirement.SAME_CITY.value:
            if same_city or same_region or same_country:
                return 30
            else:
                return 0  # Rest of world
        
        elif location_preference == LocationRequirement.SAME_REGION.value:
            if same_city:
                return 20
            elif same_region or same_country:
                return 30
            else:
                return 0
        
        elif location_preference == LocationRequirement.SAME_COUNTRY.value:
            if same_city:
                return 10
            elif same_region:
                return 20
            elif same_country:
                return 30
            else:
                return 0
        
        return 0

    def get_freelancer_average_rating(self, freelancer_id: str) -> float:
        """
        Calculate and return the average rating for a freelancer
        Returns 3.75 (default) if no reviews exist
        """
        reviews = self.review_repo.find_by_freelancer_id(freelancer_id)
        
        if not reviews or len(reviews) == 0:
            return 3.75  # Default rating (15/20 * 5 = 3.75)
        
        total_stars = sum(review.get("stars", 0) for review in reviews)
        return total_stars / len(reviews)

    def get_match_score_for_freelancer(self, project_id: str, freelancer_id: str) -> Dict:
        """
        Get the match score for a specific freelancer against a project
        Useful for freelancers to see how well they match a gig
        """
        project = self.project_repo.find_by_id(project_id)
        if not project:
            raise ValueError(f"Project {project_id} not found")
        
        freelancer = self.user_repo.find_by_user_id(freelancer_id)
        if not freelancer:
            raise ValueError(f"Freelancer {freelancer_id} not found")
        
        score_breakdown = self._calculate_match_score(project, freelancer)
        
        return {
            "project_id": project_id,
            "project_title": project.get("title"),
            "freelancer_id": freelancer_id,
            "freelancer_name": f"{freelancer.get('first_name', '')} {freelancer.get('last_name', '')}",
            "score": score_breakdown["total"],
            "score_breakdown": score_breakdown,
            "rating": self.get_freelancer_average_rating(freelancer_id)
        }

