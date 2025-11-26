# Matching Algorithm Quick Reference

## Quick Start

### 1. Set Up Project with Matching Requirements

```json
POST /projects/
{
  "title": "Restaurant Website",
  "platform": "Web",
  "duration": 1,
  "budget": 100000,
  "industry": "Website Development",
  "background_industry": "F&B",
  "timeline_weeks": 4,
  "required_location": {
    "city": "Mumbai",
    "region": "Maharashtra",
    "country": "India"
  },
  "location_preference": "same_city"
}
```

### 2. Get Matched Freelancers

```http
GET /matching/projects/{project_id}/freelancers?limit=50&min_score=60
```

### 3. View Match Score (Freelancer View)

```http
GET /matching/freelancers/{freelancer_id}/projects/{project_id}/score
```

## Scoring Cheat Sheet

| Criteria | Max Points | Key Factors |
|----------|------------|-------------|
| Industry | 20 | Skills match project type |
| Timeline | 10 | Current workload (0-2+ gigs) |
| Background | 20 | Portfolio in client's industry |
| Rating | 20 | Average review stars (default: 15) |
| Geography | 30 | Location proximity |
| **TOTAL** | **100** | |

## Rating to Score Conversion

| Stars | Score |
|-------|-------|
| 4.5-5.0 | 20 |
| 4.0-4.4 | 15 |
| 3.0-3.9 | 10 |
| 0.0-2.9 | 0 |
| No reviews | 15 (default) |

## Location Scoring Matrix

**Client wants Same City**:
- Freelancer same city/region/country → 30 pts
- Freelancer elsewhere → 0 pts

**Client wants Same Region**:
- Freelancer same city → 20 pts
- Freelancer same region/country → 30 pts
- Freelancer elsewhere → 0 pts

**Client wants Same Country**:
- Freelancer same city → 10 pts
- Freelancer same region → 20 pts
- Freelancer same country → 30 pts
- Freelancer elsewhere → 0 pts

**Client wants Anywhere**:
- All freelancers → 30 pts

## Update User Profile for Better Matching

### Freelancers
```json
PATCH /users/{user_id}
{
  "location_info": {
    "city": "Mumbai",
    "region": "Maharashtra",
    "country": "India"
  },
  "interested_industries": ["F&B", "Healthcare", "E-commerce"],
  "ongoing_gigs_count": 1,
  "skill_set": ["React", "Node.js", "MongoDB"]
}
```

### Clients
```json
# Set location when creating project
{
  "required_location": {
    "city": "Mumbai",
    "region": "Maharashtra",
    "country": "India"
  },
  "location_preference": "same_city"  // or same_region, same_country, anywhere
}
```

## Common API Responses

### Successful Match
```json
{
  "status_code": 200,
  "message": "Found 25 matching freelancers",
  "data": [
    {
      "freelancer_id": "user-123",
      "score": 95,
      "score_breakdown": {
        "industry": 20,
        "timeline": 10,
        "background": 20,
        "rating": 20,
        "geography": 25,
        "total": 95
      },
      "first_name": "John",
      "last_name": "Doe",
      "designation": "Full Stack Developer"
    }
  ]
}
```

### Score Breakdown
```json
{
  "status_code": 200,
  "data": {
    "score": 85,
    "score_breakdown": {
      "industry": 20,    // Skills match
      "timeline": 5,     // Has 1 ongoing gig
      "background": 10,  // Interested but no portfolio
      "rating": 20,      // Excellent rating (4.6 stars)
      "geography": 30,   // Same city
      "total": 85
    }
  }
}
```

## Tips for Better Matches

### For Clients
1. ✅ Specify industry and background clearly
2. ✅ Set realistic timeline
3. ✅ Be flexible with location preference if possible
4. ✅ Use `min_score` parameter to filter results

### For Freelancers
1. ✅ Keep profile updated with current location
2. ✅ List all relevant skills
3. ✅ Build portfolio with diverse projects
4. ✅ Add interested industries even without experience
5. ✅ Update `ongoing_gigs_count` regularly
6. ✅ Maintain good ratings through quality work

## Example Scenarios

### High Score (90+)
- Perfect skill match
- Available (0 ongoing gigs)
- Proven experience in background
- Excellent rating (4.5+)
- Same city

### Medium Score (60-80)
- Some skills match
- Partially available (1 gig)
- Interested in background
- Good rating (4.0+)
- Same region/country

### Low Score (<60)
- No skill match OR
- Different country (when same city required) OR
- Poor rating (<3.0)

## API Endpoints Summary

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/matching/projects/{id}/freelancers` | GET | Get all matches |
| `/matching/projects/{id}/top-matches` | GET | Get top N matches |
| `/matching/freelancers/{fid}/projects/{pid}/score` | GET | Get specific score |
| `/matching/freelancers/{id}/rating` | GET | Get average rating |

## Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `limit` | 50 | Max results (1-100) |
| `min_score` | 0 | Minimum score filter (0-100) |
| `top_n` | 10 | Number of top matches (1-50) |

---

**Quick Access**: For full documentation, see `MATCHING_ALGORITHM.md`

