from __future__ import annotations

import os

from pydantic_ai import Agent

from app.agents.deps import ConciergeDeps, NarrativeDeps, PurchaseDeps, ReelSceneCopyDeps, StylingDeps, WardrobeDeps
from app.agents.outputs import (
    ConciergeOutput,
    NarrativeAgentOutput,
    PurchaseROIAdvisorOutput,
    ReelSceneCopyOutput,
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

REEL_SCENE_COPY_SYSTEM = """You write a SINGLE scene beat for a multi-shot runway / fashion reel.
The user will concatenate your scenes into ~30s total.
Output:
- shot_description: concrete visual direction (camera, light, motion, styling) for a generative video model.
Do not name luxury brands. Keep it filmable on phone or studio."""

CONCIERGE_SYSTEM = """You are the Apparel Intelligence concierge. You help with wardrobe, outfits, social scripts, and runway reels.
You MUST choose exactly one `action` field for every turn:

- chat_only: styling advice, Q&A, clarifications, small talk—no backend tool call.
- recommend_outfit: user wants an outfit suggestion for occasion/weather (use CONTEXT fields; wardrobe JSON lists real ids).
- write_script: user wants spoken script/caption/hooks for LinkedIn, Instagram, or TikTok (set script_platform).
- preview_reel: user wants runway description / shot plan (no video file).
- render_video: user explicitly wants to generate a video file / reel render (may take time; uses Veo when configured).
- analyze_purchase: user asks whether to buy an item; set purchase_garment_id to a real id from wardrobe JSON.

Rules:
- Prefer chat_only if the user is vague or only greeting.
- Never invent garment ids; purchase_garment_id must match wardrobe JSON if used.
- Keep `reply` concise (<= 120 words) unless the user asks for detail.
- If recommending an action that needs missing info, use chat_only and ask one clarifying question."""


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


def build_reel_scene_copy_agent(settings: Settings) -> Agent[ReelSceneCopyDeps, ReelSceneCopyOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=ReelSceneCopyDeps,
        output_type=ReelSceneCopyOutput,
        system_prompt=REEL_SCENE_COPY_SYSTEM,
        retries=2,
    )


def build_concierge_agent(settings: Settings) -> Agent[ConciergeDeps, ConciergeOutput]:
    _ensure_gemini_env(settings)
    return Agent(
        settings.pydantic_ai_model,
        deps_type=ConciergeDeps,
        output_type=ConciergeOutput,
        system_prompt=CONCIERGE_SYSTEM,
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


def reel_scene_copy_agent() -> Agent[ReelSceneCopyDeps, ReelSceneCopyOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "reel_scene_copy"
    if key not in _agents:
        _agents[key] = build_reel_scene_copy_agent(s)
    return _agents[key]  # type: ignore[return-value]


def concierge_agent() -> Agent[ConciergeDeps, ConciergeOutput]:
    s = get_settings()
    if not s.has_live_llm:
        raise RuntimeError("Live LLM disabled")
    key = "concierge"
    if key not in _agents:
        _agents[key] = build_concierge_agent(s)
    return _agents[key]  # type: ignore[return-value]
