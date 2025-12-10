from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ScopeQA(BaseModel):
    """Single question/answer pair captured during discovery."""

    question: str = Field(..., description="Question that was asked")
    answer: str = Field(..., description="User's reply to the question")


class ScopeQuestionRequest(BaseModel):
    """Payload used to request the next AI-generated clarifying question."""

    answers: List[ScopeQA] = Field(default_factory=list, description="Previously answered questions")
    project_hint: Optional[str] = Field(
        default=None,
        description="Initial prompt or short description provided by the user",
    )
    industry: Optional[str] = Field(default=None, description="Target industry / vertical")
    background_industry: Optional[str] = Field(
        default=None,
        description="Client's own industry (used to search similar scopes)",
    )


class ScopeQuestionResponse(BaseModel):
    """Represents the next question in the flow."""

    question: Optional[str] = Field(
        default=None,
        description="AI generated question. None when questionnaire is complete.",
    )
    options: List[str] = Field(
        default_factory=list,
        description="Optional list of AI-generated answer options for UI (buttons, chips, etc.). "
        "Can be empty when a free-text answer is more appropriate.",
    )
    sequence: int = Field(..., description="1-based index of this question")
    max_questions: int = Field(..., description="Maximum number of questions allowed")
    is_final: bool = Field(..., description="True when the questionnaire is finished")


class SimilarProject(BaseModel):
    """Compact representation of historical projects used for benchmarking."""

    project_id: Optional[str] = None
    title: Optional[str] = None
    industry: Optional[str] = None
    background_industry: Optional[str] = None
    budget: Optional[float] = None
    duration: Optional[int] = Field(None, description="Duration in months")


class ScopeSuggestionRequest(BaseModel):
    """Payload to generate scope suggestion + pricing."""

    answers: List[ScopeQA] = Field(..., description="All collected Q/A pairs")
    project_hint: Optional[str] = Field(default=None, description="Original idea / prompt")
    industry: Optional[str] = Field(default=None, description="Target industry for the scope")
    background_industry: Optional[str] = Field(
        default=None,
        description="Client's background industry (helps fetch similar scopes)",
    )


class ScopeSuggestion(BaseModel):
    """AI generated scope summary and commercial suggestion."""

    scope_summary: str
    content_sections: List[str] = Field(default_factory=list, description="Recommended content / deliverables")
    key_features: List[str] = Field(default_factory=list)
    tone: Optional[str] = Field(default=None, description="Suggested writing tone for the proposal")
    recommended_budget: Dict[str, Any] = Field(
        ...,
        description="Budget object with currency/min/max/estimate fields",
    )
    average_budget: Optional[float] = Field(
        default=None,
        description="Average budget calculated from similar scopes",
    )
    suggested_timeline_weeks: Optional[int] = Field(
        default=None,
        description="Estimated delivery timeline in weeks",
    )
    similar_projects: List[SimilarProject] = Field(default_factory=list)


class ScopeSuggestionResponse(BaseModel):
    suggestion: ScopeSuggestion


class ScopeSuggestionUpdate(BaseModel):
    """Partial update payload for an existing suggestion."""

    suggestion: ScopeSuggestion
    scope_summary: Optional[str] = None
    content_sections: Optional[List[str]] = None
    key_features: Optional[List[str]] = None
    tone: Optional[str] = None
    recommended_budget: Optional[Dict[str, Any]] = None
    suggested_timeline_weeks: Optional[int] = None
class ScopeConfirmRequest(BaseModel):
    """Payload to confirm the suggestion and spin up a project."""

    suggestion: ScopeSuggestion
    project_title: Optional[str] = None
    industry: Optional[str] = None
    background_industry: Optional[str] = None
    location_city: Optional[str] = None
    location_region: Optional[str] = None
    location_country: Optional[str] = None
    location_preference: Optional[str] = None  # "anywhere", "country", "state", "specific"


class MatchedFreelancer(BaseModel):
    freelancer_id: str
    name: Optional[str] = None
    score: Optional[float] = None
    designation: Optional[str] = None
    bio: Optional[str] = None
    skill_set: Optional[List] = None
    score_breakdown: Optional[Dict[str, int]] = None


class ScopeConfirmResponse(BaseModel):
    project_id: str
    message: Optional[str] = None
    matched_freelancers: List[MatchedFreelancer] = Field(default_factory=list)

