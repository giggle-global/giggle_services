import json
import logging
import math
from statistics import mean
from typing import Any, Dict, List, Optional

from fastapi import HTTPException, status
from openai import OpenAI

from app.core.config import config

logger = logging.getLogger(__name__)
from app.models.ai_scope import (
    MatchedFreelancer,
    ScopeConfirmRequest,
    ScopeConfirmResponse,
    ScopeQA,
    ScopeQuestionRequest,
    ScopeQuestionResponse,
    ScopeSuggestionUpdate,
    ScopeSuggestion,
    ScopeSuggestionRequest,
    ScopeSuggestionResponse,
    SimilarProject,
)
from app.models.project import ProjectCreate
from app.repositories.project import ProjectRepository
from app.services.matching import MatchingService
from app.services.project import ProjectService

MAX_QUESTIONS = 3
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
            "Ask exactly 3 questions in this strict order based on the current 'sequence':\n"
            "1. (Sequence 1): What specific deliverables/outcomes they want\n"
            "2. (Sequence 2): Timeline and deadline preferences\n"
            "3. (Sequence 3): Budget expectations (ask for range or preference: 'tight budget', 'moderate', 'premium' - NOT exact amounts)\n\n"
            # "- Target audience or purpose\n"
            # "- Style, tone, or quality expectations\n"
            # "- Any specific requirements or constraints\n\n"
            "Do NOT ask about target audience, style, or other constraints for now.\n\n"
            "Adapt your questions to the project type mentioned. For example:\n"
            "- Software/Web: features, platform, technical needs\n"
            "- Design: style, dimensions, format, revisions\n"
            "- Writing: word count, tone, SEO, research depth\n"
            "- Marketing: channels, goals, audience demographics\n"
            "- Video: length, style, editing level, deliverable format\n\n"
            "Keep questions short, precise, and avoid yes/no questions.\n"
            "When it makes sense, propose 3-6 SHORT answer options that a user could click on (buttons, chips, etc.). "
            "Options should be concise phrases, not sentences.\n\n"
            "Respond strictly with JSON using this schema:\n"
            '{"question": "...", "options": ["..."], "is_final": false}.\n'
            "If you think free-text is better, you MUST still return an empty list for 'options' (e.g. \"options\": [])."
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
            raw_response = self._invoke_chat(messages)
            logger.info(f"[AI] Raw OpenAI response: {raw_response[:500]}...")  # Log first 500 chars
            response_json = self._safe_json(raw_response)
            logger.info(f"[AI] Parsed JSON: {response_json}")
            question_text = response_json.get("question")
            options = response_json.get("options") or []
            if not isinstance(options, list):
                logger.warning("[AI] 'options' field was not a list; defaulting to empty list")
                options = []
        except json.JSONDecodeError as exc:
            logger.error(f"[AI] JSON decode error: {exc}. Raw response: {raw_response if 'raw_response' in locals() else 'N/A'}")
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"Failed to parse AI response as JSON: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[AI] Unexpected error generating question: {exc}")
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"Failed to generate question: {exc}"
            ) from exc

        is_final = sequence >= MAX_QUESTIONS or not question_text
        return ScopeQuestionResponse(
            question=question_text,
            options=options,
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
            "7. Typical ranges vary by type (reflective of current Indian freelance market):\n"
            "   - Software/Web: Simple (₹15k-₹50k), Moderate (₹50k-₹150k), Complex (₹150k-₹300k)\n"
            "   - Design/Creative: Simple (₹5k-₹25k), Moderate (₹25k-₹75k), Complex (₹75k-₹200k)\n"
            "   - Writing/Content: Simple (₹3k-₹15k), Moderate (₹15k-₹50k), Complex (₹50k-₹100k)\n"
            "   - Marketing: Simple (₹10k-₹30k), Moderate (₹30k-₹100k), Complex (₹100k-₹250k)\n\n"
            "Always provide data-driven budget recommendations with justification relevant to the project type."
        )
        messages = [
            {"role": "system", "content": "You are a concise project strategist for all types of freelance work who responds with JSON only."},
            {"role": "user", "content": instructions + "\nContext:\n" + json.dumps(message, ensure_ascii=False)},
        ]

        try:
            raw_response = self._invoke_chat(messages)
            logger.info(f"[AI] Raw OpenAI suggestion response: {raw_response[:500]}...")
            payload_json = self._safe_json(raw_response)
            logger.info(f"[AI] Parsed suggestion JSON keys: {list(payload_json.keys())}")
        except json.JSONDecodeError as exc:
            logger.error(f"[AI] JSON decode error in suggestion: {exc}. Raw response: {raw_response if 'raw_response' in locals() else 'N/A'}")
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, detail=f"Failed to parse AI suggestion as JSON: {exc}"
            ) from exc
        except Exception as exc:  # noqa: BLE001
            logger.exception(f"[AI] Unexpected error generating suggestion: {exc}")
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
    # Suggestion Update (inline edits)
    # ------------------------------------------------------------------ #
    def update_suggestion(self, payload: ScopeSuggestionUpdate) -> ScopeSuggestionResponse:
        """
        Apply client-side edits to an existing suggestion object without regenerating from AI.
        """
        suggestion = payload.suggestion

        # Apply partial updates
        if payload.scope_summary is not None:
            suggestion.scope_summary = payload.scope_summary
        if payload.content_sections is not None:
            suggestion.content_sections = payload.content_sections
        if payload.key_features is not None:
            suggestion.key_features = payload.key_features
        if payload.tone is not None:
            suggestion.tone = payload.tone
        if payload.recommended_budget is not None:
            suggestion.recommended_budget = payload.recommended_budget
        if payload.suggested_timeline_weeks is not None:
            suggestion.suggested_timeline_weeks = payload.suggested_timeline_weeks

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

        # Extract budget min/max from suggestion to preserve original AI-generated range
        budget_min = budget_object.get("min")
        budget_max = budget_object.get("max")
        
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
            scope_summary=suggestion.scope_summary,
            content_sections=suggestion.content_sections,
            key_features=suggestion.key_features,
            tone=suggestion.tone,
            budget_min=float(budget_min) if budget_min is not None else None,
            budget_max=float(budget_max) if budget_max is not None else None,
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
            # Remove markdown code fences
            cleaned = cleaned.strip("`")
            # Remove language identifier (e.g., "json")
            if "\n" in cleaned:
                cleaned = cleaned.split("\n", 1)[-1]
        return json.loads(cleaned)  # FIXED: This was inside the if block!

    @staticmethod
    def _format_history(answers: List[ScopeQA]) -> str:
        if not answers:
            return ""
        return "\n".join(
            [f"Q{i+1}: {qa.question}\nA{i+1}: {qa.answer}" for i, qa in enumerate(answers)]
        )

