# Giggle User-Matching Algorithm

## Overview

The Giggle matching algorithm efficiently matches freelancers to gig postings based on 5 key criteria, providing a total score of 0-100 points. This ensures clients find the most suitable creators for their projects.

## Scoring Criteria

### 1. Industry Match (20 points)
- Matches the project's industry/category with freelancer's skill set
- **Full Match (20 pts)**: Freelancer skills directly match project industry
- **Partial Match (10-15 pts)**: Some keywords match
- **No Match (0 pts)**: No relevant skills

### 2. Timeline Availability (10 points)
- Based on freelancer's current workload (ongoing gigs count)
- **Fully Available (10 pts)**: 0 ongoing gigs
- **Partially Available (5 pts)**: 1 ongoing gig
- **Busy (2 pts)**: 2+ ongoing gigs

### 3. Background Industry (20 points)
- Matches freelancer's portfolio/experience with client's industry background
- **Proven Experience (20 pts)**: Portfolio shows work in the industry
- **Interested (10 pts)**: Listed in interested industries (for newcomers)
- **No Match (0 pts)**: No relevant background

### 4. User Rating (20 points)
Based on average review ratings (1-5 stars):

| Rating Range | Score | Notes |
|--------------|-------|-------|
| 4.5 - 5.0 | 20/20 | Excellent |
| 4.0 - 4.4 | 15/20 | Good |
| 3.0 - 3.9 | 10/20 | Average |
| 0.0 - 2.9 | 0/20 | Poor |
| No reviews | 15/20 | Default for new users (3.75 stars equivalent) |

### 5. Geographic Location (30 points)

Location scoring matrix based on client's preference:

| Client Requirement | Freelancer Location | | | |
|-------------------|---------------------|-----|-----|-----|
| | **Same City** | **Same Region** | **Same Country** | **Anywhere** |
| **Same City** | 30 | 30 | 30 | 30 |
| **Same Region** | 20 | 30 | 30 | 30 |
| **Same Country** | 10 | 20 | 30 | 30 |
| **Anywhere** | 30 | 30 | 30 | 30 |

**Note**: If preference is "Rest of World" (different country), score is 0 unless preference is "Anywhere".

## Example Use Case

### Scenario
**Client (X)**: Restaurant owner in Mumbai needs a website in 4 weeks, budget 100,000 Gs, requires creator from same city.

**Freelancer A**:
- Experience: F&B Website Development
- Location: Mumbai
- Ongoing gigs: 0
- Rating: 4.8 stars

**Freelancer B**:
- Experience: None (interested in F&B)
- Location: Bangalore
- Ongoing gigs: 1
- Rating: New user (default 3.75)

### Score Calculation

| Criteria | Freelancer A | Freelancer B |
|----------|-------------|-------------|
| Industry Match | 20/20 | 20/20 |
| Timeline | 10/10 | 5/10 |
| Background | 20/20 | 10/20 |
| Rating | 20/20 | 15/20 |
| Geography | 30/30 | 10/30 |
| **Total** | **100/100** | **60/100** |

**Result**: Freelancer A's profile appears first in the matching list.

## API Endpoints

### 1. Match Freelancers to Project
```http
GET /matching/projects/{project_id}/freelancers?limit=50&min_score=60
```

**Response**:
```json
{
  "status_code": 200,
  "message": "Found 25 matching freelancers",
  "data": [
    {
      "freelancer_id": "user-123",
      "username": "johndoe",
      "first_name": "John",
      "last_name": "Doe",
      "score": 95,
      "score_breakdown": {
        "industry": 20,
        "timeline": 10,
        "background": 20,
        "rating": 20,
        "geography": 25,
        "total": 95
      },
      "bio": "Experienced web developer",
      "designation": "Full Stack Developer"
    }
  ]
}
```

### 2. Get Freelancer Match Score for Specific Project
```http
GET /matching/freelancers/{freelancer_id}/projects/{project_id}/score
```

**Response**:
```json
{
  "status_code": 200,
  "message": "Match score calculated successfully",
  "data": {
    "project_id": "proj-456",
    "project_title": "Restaurant Website",
    "freelancer_id": "user-123",
    "freelancer_name": "John Doe",
    "score": 95,
    "score_breakdown": {
      "industry": 20,
      "timeline": 10,
      "background": 20,
      "rating": 20,
      "geography": 25,
      "total": 95
    },
    "rating": 4.8
  }
}
```

### 3. Get Top Matching Freelancers
```http
GET /matching/projects/{project_id}/top-matches?top_n=10
```

**Response**: Simplified list of top N freelancers with highest scores.

### 4. Get Freelancer Average Rating
```http
GET /matching/freelancers/{freelancer_id}/rating
```

**Response**:
```json
{
  "status_code": 200,
  "message": "Rating retrieved successfully",
  "data": {
    "freelancer_id": "user-123",
    "average_rating": 4.75,
    "score": 20,
    "rating_bracket": "4.5 - 5.0"
  }
}
```

## Data Model Updates

### User Model Updates
Added fields for matching algorithm:

```python
class UserUpdate(BaseModel):
    # ... existing fields ...
    
    # Location fields
    location_info: Optional[LocationInfo] = None  # {city, region, country}
    
    # Freelancer-specific matching fields
    interested_industries: Optional[List[str]] = None  # e.g., ["F&B", "Healthcare"]
    ongoing_gigs_count: Optional[int] = 0
```

### Project Model Updates
Added fields for matching requirements:

```python
class ProjectBase(BaseModel):
    # ... existing fields ...
    
    # Matching algorithm fields
    industry: Optional[str] = None  # e.g., "Website Development"
    background_industry: Optional[str] = None  # e.g., "F&B"
    timeline_weeks: Optional[int] = None  # e.g., 4
    required_location: Optional[Dict[str, str]] = None  # {city, region, country}
    location_preference: Optional[LocationRequirement] = None  # same_city/region/country/anywhere
```

## Implementation Files

### Core Files Created/Modified

1. **`app/services/matching.py`** - Main matching algorithm service
   - `match_freelancers_to_project()` - Match and rank freelancers
   - `_calculate_match_score()` - Calculate total score with breakdown
   - Individual scoring methods for each criterion
   - `get_freelancer_average_rating()` - Rating calculation

2. **`app/routes/matching.py`** - API endpoints
   - `/matching/projects/{project_id}/freelancers` - Match freelancers
   - `/matching/freelancers/{freelancer_id}/projects/{project_id}/score` - Get score
   - `/matching/projects/{project_id}/top-matches` - Top matches
   - `/matching/freelancers/{freelancer_id}/rating` - Get rating

3. **`app/models/user.py`** - Updated with location and industry fields

4. **`app/models/project.py`** - Updated with matching requirements

5. **Repository Updates**:
   - `app/repositories/user.py` - Added `find_by_role()`, `find_by_user_id()`
   - `app/repositories/review.py` - Added `find_by_freelancer_id()`
   - `app/repositories/portfolio.py` - Added `find_by_user_id()`

## Usage Examples

### Client: Finding Matching Freelancers

```python
# After creating a project with matching requirements
import requests

project_data = {
    "title": "Restaurant Website",
    "industry": "Website Development",
    "background_industry": "F&B",
    "timeline_weeks": 4,
    "required_location": {
        "city": "Mumbai",
        "region": "Maharashtra",
        "country": "India"
    },
    "location_preference": "same_city",
    "budget": 100000
}

# Create project
response = requests.post("/projects/", json=project_data, headers=auth_headers)
project_id = response.json()["data"]["id"]

# Get matched freelancers
matches = requests.get(
    f"/matching/projects/{project_id}/freelancers?min_score=70",
    headers=auth_headers
)

print(f"Found {len(matches.json()['data'])} freelancers with score >= 70")
```

### Freelancer: Checking Match Score

```python
# Freelancer wants to see how well they match a gig
freelancer_id = "user-123"
project_id = "proj-456"

score = requests.get(
    f"/matching/freelancers/{freelancer_id}/projects/{project_id}/score",
    headers=auth_headers
)

print(f"Your match score: {score.json()['data']['score']}/100")
print(f"Breakdown: {score.json()['data']['score_breakdown']}")
```

## Benefits

1. **Fair to Newcomers**: Default rating of 15/20 (3.75 stars) ensures new users aren't penalized
2. **Objective Matching**: Transparent scoring based on concrete criteria
3. **Flexible Location**: Supports both strict and flexible location requirements
4. **Experience Recognition**: Values proven experience while allowing newcomers to match on interest
5. **Availability Aware**: Considers freelancer workload for realistic matching

## Future Enhancements

Potential improvements to the algorithm:

1. **Skills Weighting**: Give different weights to different skills based on project requirements
2. **Budget Matching**: Consider freelancer's typical rates vs project budget
3. **Historical Performance**: Factor in past project completion rates
4. **Response Time**: Consider freelancer's average response time to opportunities
5. **Certification Badges**: Bonus points for verified skills/certifications
6. **Machine Learning**: Use ML to refine weights based on successful matches

## Testing the Algorithm

### Test Scenario Setup

1. Create test users (freelancers) with varying profiles:
   - Different locations
   - Different skill sets
   - Different experience levels
   - Different ratings

2. Create test project with specific requirements

3. Call matching endpoint and verify scoring

4. Adjust data and verify scores change appropriately

### Sample Test Data

```python
# Test Freelancer 1: Perfect match
freelancer_1 = {
    "role": "FL",
    "skill_set": ["React", "Node.js", "MongoDB"],
    "location_info": {"city": "Mumbai", "region": "Maharashtra", "country": "India"},
    "interested_industries": ["F&B", "E-commerce"],
    "ongoing_gigs_count": 0
}

# Test Project
project = {
    "industry": "Website Development",
    "background_industry": "F&B",
    "timeline_weeks": 4,
    "required_location": {"city": "Mumbai", "region": "Maharashtra", "country": "India"},
    "location_preference": "same_city"
}

# Expected: High score (90-100)
```

## Support

For questions or issues with the matching algorithm:
- Check the API documentation at `/docs` (FastAPI auto-generated)
- Review the scoring breakdown in API responses
- Adjust project requirements for broader/narrower matching

---

**Version**: 1.0  
**Last Updated**: November 2025  
**Status**: Production Ready ✅

