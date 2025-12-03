import json
import math
from statistics import mean
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from openai import OpenAI

from app.core.config import config
from app.models.ai_scope import (
    MatchedFreelancer,
    ScopeConfirmRequest,
    ScopeConfirmResponse,
    ScopeQA,
    ScopeQuestionRequest,
    ScopeQuestionResponse,
    ScopeSuggestion,
    ScopeSuggestionRequest,
    ScopeSuggestionResponse,
    SimilarProject,
)
from app.models.project import ProjectCreate
from app.repositories.project import ProjectRepository
from app.services.matching import MatchingService
from app.services.project import ProjectService

MAX_QUESTIONS = 5
OPENAI_MODEL = "gpt-4o-mini"


class AIScopeService:
    """AI assistant that guides clients through scoping and matching flow."""

    def __init__(self) -> None:
        api_key = config.get("openai_api_key")
        if not api_key:
            raise HTTPException(
                status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OPENAI_API_KEY is not configured in the environment",
            )
        self.client = OpenAI(api_key=api_key)
        self.project_repo = ProjectRepository()
        self.project_service = ProjectService()

    # ------------------------------------------------------------------ #
    # Question Flow
    # ------------------------------------------------------------------ #
    def next_question(self, payload: ScopeQuestionRequest) -> ScopeQuestionResponse:
        answers = payload.answers or []
        sequence = len(answers) + 1

        if sequence > MAX_QUESTIONS:
            return ScopeQuestionResponse(
                question=None,
                sequence=sequence,
                max_questions=MAX_QUESTIONS,
                is_final=True,
            )

        prompt = (
            "You are an AI discovery assistant helping clients define their project requirements for ANY type of freelance work "
            "(software, design, writing, marketing, video, consulting, etc.).\n\n"
            "Ask the next clarifying question based on the project type. Focus on:\n"
            "- What specific deliverables/outcomes they want\n"
            "- Timeline and deadline preferences\n"
            "- Target audience or purpose\n"
            "- Style, tone, or quality expectations\n"
            "- Budget expectations (ask for range or preference: 'tight budget', 'moderate', 'premium' - NOT exact amounts)\n"
            "- Any specific requirements or constraints\n\n"
            "Adapt your questions to the project type mentioned. For example:\n"
            "- Software/Web: features, platform, technical needs\n"
            "- Design: style, dimensions, format, revisions\n"
            "- Writing: word count, tone, SEO, research depth\n"
            "- Marketing: channels, goals, audience demographics\n"
            "- Video: length, style, editing level, deliverable format\n\n"
            "Keep questions short, precise, and avoid yes/no questions. Respond strictly with JSON: "
            '{"question": "...", "is_final": false}.'
        )
        context = {
            "sequence": sequence,
            "max_questions": MAX_QUESTIONS,
            "project_hint": payload.project_hint,
            "target_industry": payload.industry,
            "client_background": payload.background_industry,
            "history": self._format_history(answers),
        }
        messages = [
            {"role": "system", "content": "You are a helpful project scope assistant for any type of freelance work across all industries."},
            {"role": "user", "content": prompt + "\nContext:\n" + json.dumps(context, ensure_ascii=False)},
        ]

        try:
            response_json = self._safe_json(self._invoke_chat(messages))
            question_text = response_json.get("question")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"Failed to generate question: {exc}"
            ) from exc

        is_final = sequence >= MAX_QUESTIONS or not question_text
        return ScopeQuestionResponse(
            question=question_text,
            sequence=sequence,
            max_questions=MAX_QUESTIONS,
            is_final=is_final,
        )

    # ------------------------------------------------------------------ #
    # Suggestion Generation
    # ------------------------------------------------------------------ #
    def generate_suggestion(self, payload: ScopeSuggestionRequest) -> ScopeSuggestionResponse:
        if not payload.answers:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Answers are required.")

        similar_projects = self.project_repo.find_similar(
            industry=payload.industry,
            background=payload.background_industry,
            limit=8,
        )
        budget_values = [
            float(project.get("budget"))
            for project in similar_projects
            if isinstance(project.get("budget"), (int, float))
        ]
        average_budget = round(mean(budget_values), 2) if budget_values else None

        message = {
            "project_hint": payload.project_hint,
            "industry": payload.industry,
            "client_background": payload.background_industry,
            "answers": self._format_history(payload.answers),
            "similar_projects": [
                {
                    "title": project.get("title"),
                    "industry": project.get("industry"),
                    "background_industry": project.get("background_industry"),
                    "budget": project.get("budget"),
                    "duration": project.get("duration"),
                }
                for project in similar_projects[:5]
            ],
            "average_budget": average_budget,
        }
        instructions = (
            "You are an AI project strategist for ANY type of freelance work (software, design, writing, marketing, video, consulting, etc.). "
            "Based on the information, craft JSON with keys:\n"
            "scope_summary (string - comprehensive summary of the project), "
            "content_sections (array of strings describing deliverables/components), "
            "key_features (array of strings - main requirements, outcomes, or specifications), "
            "tone (string - project style/approach), "
            "recommended_budget (object with currency='INR', min, max, estimate - all as integers in rupees), "
            "suggested_timeline_weeks (integer).\n\n"
            "ADAPT TO PROJECT TYPE:\n"
            "- Software/Web: features → technical features, integrations\n"
            "- Design: features → design elements, deliverables, revisions\n"
            "- Writing: features → content pieces, word count, topics\n"
            "- Marketing: features → campaigns, channels, strategies\n"
            "- Video: features → video segments, editing techniques, final outputs\n"
            "- Consulting: features → deliverables, sessions, reports\n\n"
            "CRITICAL BUDGET ANALYSIS:\n"
            "1. If user mentioned budget preference (tight/moderate/premium/specific range), acknowledge it\n"
            "2. Analyze similar_projects average_budget and project complexity\n"
            "3. Calculate realistic budget based on: scope, deliverables, timeline, and market rates for the project type\n"
            "4. If user's expectation is too low, adjust upward and explain why in scope_summary\n"
            "5. If user's expectation is too high, suggest optimal budget and explain savings\n"
            "6. If average_budget from similar projects exists, use it as primary reference\n"
            "7. Typical ranges vary by type:\n"
            "   - Software/Web: Simple (₹50k-₹150k), Moderate (₹150k-₹350k), Complex (₹350k-₹800k)\n"
            "   - Design/Creative: Simple (₹20k-₹80k), Moderate (₹80k-₹200k), Complex (₹200k-₹500k)\n"
            "   - Writing/Content: Simple (₹10k-₹50k), Moderate (₹50k-₹150k), Complex (₹150k-₹400k)\n"
            "   - Marketing: Simple (₹30k-₹100k), Moderate (₹100k-₹300k), Complex (₹300k-₹800k)\n\n"
            "Always provide data-driven budget recommendations with justification relevant to the project type."
        )
        messages = [
            {"role": "system", "content": "You are a concise project strategist for all types of freelance work who responds with JSON only."},
            {"role": "user", "content": instructions + "\nContext:\n" + json.dumps(message, ensure_ascii=False)},
        ]

        try:
            payload_json = self._safe_json(self._invoke_chat(messages))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"Failed to generate scope suggestion: {exc}"
            ) from exc

        recommended_budget = payload_json.get("recommended_budget") or {
            "currency": "INR",
            "min": average_budget or 0,
            "max": average_budget or 0,
            "estimate": average_budget or 0,
        }

        suggestion = ScopeSuggestion(
            scope_summary=payload_json.get("scope_summary", "No summary generated."),
            content_sections=payload_json.get("content_sections", []),
            key_features=payload_json.get("key_features", []),
            tone=payload_json.get("tone"),
            recommended_budget=recommended_budget,
            average_budget=average_budget,
            suggested_timeline_weeks=payload_json.get("suggested_timeline_weeks"),
            similar_projects=[
                SimilarProject(
                    project_id=project.get("id"),
                    title=project.get("title"),
                    industry=project.get("industry"),
                    background_industry=project.get("background_industry"),
                    budget=project.get("budget"),
                    duration=project.get("duration"),
                )
                for project in similar_projects[:5]
            ],
        )

        return ScopeSuggestionResponse(suggestion=suggestion)

    # ------------------------------------------------------------------ #
    # Confirmation & Matching
    # ------------------------------------------------------------------ #
    def confirm_scope(
        self,
        payload: ScopeConfirmRequest,
        current_user: Dict[str, Any],
    ) -> ScopeConfirmResponse:
        suggestion = payload.suggestion

        # Determine numeric budget
        budget_object = suggestion.recommended_budget or {}
        budget_estimate = (
            budget_object.get("estimate")
            or budget_object.get("avg")
            or suggestion.average_budget
            or 0
        )

        timeline_weeks = suggestion.suggested_timeline_weeks or 12
        duration_months = max(1, math.ceil(timeline_weeks / 4))

        # Build required_location dict only with non-None values
        location_dict = {}
        if payload.location_city:
            location_dict["city"] = payload.location_city
        if payload.location_region:
            location_dict["region"] = payload.location_region
        if payload.location_country:
            location_dict["country"] = payload.location_country

        # Map frontend location preference to LocationRequirement enum
        location_pref_map = {
            "anywhere": "anywhere",
            "country": "same_country",
            "state": "same_region",
            "specific": "same_city",
        }
        location_preference = location_pref_map.get(payload.location_preference, "anywhere")

        project_payload = ProjectCreate(
            title=payload.project_title or suggestion.scope_summary[:60],
            platform="Web/Mobile",
            duration=duration_months,
            design_status="In Progress",
            budget=float(budget_estimate),
            industry=payload.industry,
            background_industry=payload.background_industry,
            timeline_weeks=timeline_weeks,
            required_location=location_dict if location_dict else None,
            location_preference=location_preference,
        )

        created_project = self.project_service.create(project_payload, current_user=current_user)
        project_id = getattr(created_project, "id", None) or created_project.get("id")

        # Run matching algorithm for newly created project
        # Use min_score=40 to filter out poorly matched freelancers
        # Score breakdown: Industry(20) + Timeline(10) + Background(20) + Rating(20) + Geography(30) = 100
        matching_service = MatchingService()
        matches = matching_service.match_freelancers_to_project(project_id, limit=10, min_score=40)
        matched_freelancers = [
            MatchedFreelancer(
                freelancer_id=item.get("freelancer_id"),
                name=" ".join(filter(None, [item.get("first_name"), item.get("last_name")])).strip() or None,
                score=item.get("score"),
                designation=item.get("designation"),
                bio=item.get("bio"),
                skill_set=item.get("skill_set"),
                score_breakdown=item.get("score_breakdown"),
            )
            for item in matches
        ]

        return ScopeConfirmResponse(
            project_id=project_id,
            message="Scope confirmed, project created, and matches prepared.",
            matched_freelancers=matched_freelancers,
        )

    # ------------------------------------------------------------------ #
    # OpenAI helpers
    # ------------------------------------------------------------------ #
    def _invoke_chat(self, messages: List[Dict[str, str]]) -> str:
        completion = self.client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.4,
            messages=messages,
        )
        return completion.choices[0].message.content.strip()

    @staticmethod
    def _safe_json(payload: str) -> Dict[str, Any]:
        cleaned = payload.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.strip("`")
            cleaned = cleaned.split("\n", 1)[-1]
        return json.loads(cleaned)

    @staticmethod
    def _format_history(answers: List[ScopeQA]) -> str:
        if not answers:
            return ""
        return "\n".join(
            [f"Q{i+1}: {qa.question}\nA{i+1}: {qa.answer}" for i, qa in enumerate(answers)]
        )

