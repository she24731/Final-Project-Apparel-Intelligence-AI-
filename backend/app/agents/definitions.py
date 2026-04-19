from __future__ import annotations

import os

from pydantic_ai import Agent

from app.agents.deps import NarrativeDeps, PurchaseDeps, StylingDeps, WardrobeDeps
from app.agents.outputs import (
    NarrativeAgentOutput,
    PurchaseROIAdvisorOutput,
    StylingAgentOutput,
    WardrobeIngestionOutput,
)
from app.config import Settings, get_settings

WARDROBE_SYSTEM = """You are WardrobeIngestionAgent for Apparel Intelligence.
Infer category, color, formality (0 casual .. 1 formal), season, and short tags.
Categories must be one of: top, bottom, outerwear, shoes, accessory.
Season: one of all-season, summer, winter.
Keep tags <= 8 items, lowercase, no hashtags."""

STYLING_SYSTEM = """You are StylingAgent. Given wardrobe JSON and context, pick garment_ids_in_order
and parallel roles_in_order (top, bottom, footwear, outerwear, accessory).
Explain briefly (2-4 sentences). confidence in [0,1].
Only use ids that exist in the wardrobe list."""

PURCHASE_SYSTEM = """You are PurchaseROIAdvisor. Use compatibility_score and outfit_combination_potential
from the user message as facts; do not invent new numbers.
Return BUY / NO_BUY / MAYBE with concise explanation and 3-5 rationale_bullets."""

NARRATIVE_SYSTEM = """You are NarrativeAgent for Apparel Intelligence.
Write a human, platform-native spoken script (12–22 seconds aloud) using the outfit summary and creative controls.
Rules:
- linkedin: credible, specific, no hashtag spam; caption may be null or a one-line hook.
- instagram: warm, visual, 1–2 line breaks in caption; add 3–6 tasteful hashtags in `hashtags`.
- tiktok: punchy hooks, pattern interrupts ok; short lines; add 4–8 hashtags in `hashtags`.
Never invent brand names. Keep it filmable on a phone."""


def _ensure_gemini_env(settings: Settings) -> None:
    if settings.gemini_api_key:
        os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key.strip())


def build_wardrobe_ingestion_agent(settings: Settings) -> Agent[WardrobeDeps, WardrobeIngestionOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=WardrobeDeps,
        output_type=WardrobeIngestionOutput,
        system_prompt=WARDROBE_SYSTEM,
        retries=2,
    )


def build_styling_agent(settings: Settings) -> Agent[StylingDeps, StylingAgentOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=StylingDeps,
        output_type=StylingAgentOutput,
        system_prompt=STYLING_SYSTEM,
        retries=2,
    )


def build_purchase_roi_agent(settings: Settings) -> Agent[PurchaseDeps, PurchaseROIAdvisorOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=PurchaseDeps,
        output_type=PurchaseROIAdvisorOutput,
        system_prompt=PURCHASE_SYSTEM,
        retries=2,
    )


def build_narrative_agent(settings: Settings) -> Agent[NarrativeDeps, NarrativeAgentOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=NarrativeDeps,
        output_type=NarrativeAgentOutput,
        system_prompt=NARRATIVE_SYSTEM,
        retries=2,
    )


_agents: dict[str, object] = {}


def wardrobe_ingestion_agent() -> Agent[WardrobeDeps, WardrobeIngestionOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "wardrobe"
    if key not in _agents:
        _agents[key] = build_wardrobe_ingestion_agent(s)
    return _agents[key]  # type: ignore[return-value]


def styling_agent() -> Agent[StylingDeps, StylingAgentOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "styling"
    if key not in _agents:
        _agents[key] = build_styling_agent(s)
    return _agents[key]  # type: ignore[return-value]


def purchase_roi_agent() -> Agent[PurchaseDeps, PurchaseROIAdvisorOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "purchase"
    if key not in _agents:
        _agents[key] = build_purchase_roi_agent(s)
    return _agents[key]  # type: ignore[return-value]


def narrative_agent() -> Agent[NarrativeDeps, NarrativeAgentOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "narrative"
    if key not in _agents:
        _agents[key] = build_narrative_agent(s)
    return _agents[key]  # type: ignore[return-value]
