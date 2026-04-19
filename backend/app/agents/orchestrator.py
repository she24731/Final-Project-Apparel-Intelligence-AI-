from __future__ import annotations

import json
import re
from typing import Any

from app.agents.definitions import narrative_agent, purchase_roi_agent, styling_agent, wardrobe_ingestion_agent
from app.agents.deps import NarrativeDeps, PurchaseDeps, StylingDeps, WardrobeDeps
from app.agents.outputs import (
    NarrativeAgentOutput,
    PurchaseROIAdvisorOutput,
    StylingAgentOutput,
    WardrobeIngestionOutput,
)
from app.config import get_settings
from app.schemas.media import GenerateScriptResponse
from app.schemas.purchase import PurchaseAnalysisResponse
from app.schemas.recommend import OutfitItemRef, RecommendOutfitResponse
from app.schemas.wardrobe import GarmentRecord, IngestGarmentResponse
from app.services.embeddings import deterministic_embedding
from app.services.image_category import infer_category_from_image
from app.services.outfit_heuristic import new_garment_id, recommend_outfit_deterministic
from app.services.purchase_logic import analyze_purchase_deterministic
from app.services.style_rules import retrieve_style_rules


def color_from_filename(filename: str) -> str:
    name = filename.lower()
    tokens = re.split(r"[^a-z]+", name)
    palette = ("black", "navy", "white", "gray", "grey", "brown", "beige", "olive", "burgundy", "cream")
    for t in tokens:
        if t in palette:
            return t
    return "neutral"


def _category_from_filename(filename: str) -> str:
    n = filename.lower()
    if any(k in n for k in ("jacket", "coat", "parka", "blazer")):
        return "outerwear"
    if any(k in n for k in ("shoe", "sneaker", "boot", "loafer")):
        return "shoes"
    if any(k in n for k in ("pant", "jean", "trouser", "chino", "skirt")):
        return "bottom"
    if any(k in n for k in ("tie", "belt", "bag", "watch", "scarf")):
        return "accessory"
    return "top"


def ingest_garment_offline(filename: str, image_path: str, hints: str | None) -> IngestGarmentResponse:
    gid = new_garment_id()
    # Visual category guess (helps for random filenames like *.jpg.webp)
    img_guess = infer_category_from_image(f"data/{image_path}", filename_hint=filename)
    category = img_guess.category or _category_from_filename(filename)
    color = color_from_filename(filename)
    formality = 0.55 if category in {"outerwear", "accessory"} else 0.45
    season = "winter" if "wool" in (hints or "").lower() or "coat" in filename.lower() else "all-season"
    hint_tags = [h.strip().lower() for h in hints.split(",") if h.strip()] if hints else []
    tags = sorted({category, color, *hint_tags})[:8]
    emb = deterministic_embedding((gid, category, color, filename))
    garment = GarmentRecord(
        id=gid,
        category=category,
        color=color,
        formality_score=formality,
        season=season,
        tags=tags or [category],
        image_path=image_path,
        embedding=emb,
    )
    return IngestGarmentResponse(
        garment=garment,
        ingestion_notes=f"Offline ingestion (visual guess: {img_guess.notes}).",
        used_live_agent=False,
    )


async def ingest_garment_with_optional_agent(filename: str, image_path: str, hints: str | None) -> IngestGarmentResponse:
    settings = get_settings()
    if not settings.has_live_llm:
        return ingest_garment_offline(filename, image_path, hints)
    try:
        agent = wardrobe_ingestion_agent()
        img_guess = infer_category_from_image(f"data/{image_path}", filename_hint=filename)
        user = (
            f"Filename: {filename}\nHints: {hints or 'none'}\n"
            f"Heuristic color guess: {color_from_filename(filename)}\n"
            f"Heuristic category guess: {_category_from_filename(filename)}\n"
            f"Visual category guess: {img_guess.category} ({img_guess.notes})"
        )
        result = await agent.run(user, deps=WardrobeDeps(filename=filename, hints=hints))
        meta: WardrobeIngestionOutput = result.output
        gid = new_garment_id()
        # Safety override: if visual heuristic is confident and agent disagrees, trust the visual guess.
        category = meta.category
        if img_guess.confidence >= 0.6 and meta.category != img_guess.category:
            category = img_guess.category
        emb = deterministic_embedding((gid, meta.category, meta.color, filename))
        garment = GarmentRecord(
            id=gid,
            category=category,
            color=meta.color,
            formality_score=meta.formality_score,
            season=meta.season,
            tags=meta.tags,
            image_path=image_path,
            embedding=emb,
        )
        return IngestGarmentResponse(
            garment=garment,
            ingestion_notes="Structured output from WardrobeIngestionAgent.",
            used_live_agent=True,
        )
    except Exception as exc:  # noqa: BLE001 - demo resilience
        base = ingest_garment_offline(filename, image_path, hints)
        base.ingestion_notes = f"Agent failed ({exc!s}); used offline fallback."
        return base


async def recommend_outfit_with_optional_agent(
    occasion: str,
    weather: str,
    vibe: str,
    wardrobe: list[GarmentRecord],
    user_preference: str | None,
) -> RecommendOutfitResponse:
    settings = get_settings()
    base = recommend_outfit_deterministic(occasion, weather, vibe, wardrobe, user_preference)
    if not settings.has_live_llm:
        return base
    try:
        rules = retrieve_style_rules((occasion, weather, vibe), top_n=3)
        rules_text = "\n".join(f"- [{r.id}] {r.text}" for r in rules)
        wardrobe_json = json.dumps([g.model_dump() for g in wardrobe], default=str)
        agent = styling_agent()
        prompt = (
            f"occasion={occasion}; weather={weather}; vibe={vibe}; user_preference={user_preference!s}\n"
            f"STYLE_RULES:\n{rules_text}\nWARDROBE_JSON:\n{wardrobe_json}"
        )
        deps = StylingDeps(
            occasion=occasion,
            weather=weather,
            vibe=vibe,
            wardrobe=wardrobe,
            user_preference=user_preference,
            retrieved_rules=rules_text,
        )
        out: StylingAgentOutput = (await agent.run(prompt, deps=deps)).output
        ids = out.garment_ids_in_order
        roles = out.roles_in_order
        if len(roles) < len(ids):
            roles = roles + ["piece"] * (len(ids) - len(roles))
        by_id: dict[str, GarmentRecord] = {g.id: g for g in wardrobe}
        outfit_items = [
            OutfitItemRef(garment_id=gid, role=roles[i] if i < len(roles) else "piece")
            for i, gid in enumerate(ids)
            if gid in by_id
        ]
        garments = [by_id[i.garment_id] for i in outfit_items]
        if not outfit_items:
            return base
        return RecommendOutfitResponse(
            outfit_items=outfit_items,
            garments=garments,
            explanation=out.explanation or base.explanation,
            confidence=float(out.confidence),
            retrieved_style_rule_ids=[r.id for r in rules],
            used_live_agent=True,
        )
    except Exception:
        return base


async def analyze_purchase_with_optional_agent(
    candidate: GarmentRecord,
    wardrobe: list[GarmentRecord],
) -> PurchaseAnalysisResponse:
    if not candidate.embedding:
        tags = ",".join(candidate.tags or [])
        candidate = candidate.model_copy(
            update={
                "embedding": deterministic_embedding(
                    (
                        candidate.id,
                        candidate.category,
                        candidate.color,
                        f"{float(candidate.formality_score):.2f}",
                        candidate.season,
                        tags,
                        "purchase_candidate",
                    ),
                ),
            },
        )
    det = analyze_purchase_deterministic(candidate, wardrobe)
    settings = get_settings()
    if not settings.has_live_llm:
        return det
    try:
        agent = purchase_roi_agent()
        deps = PurchaseDeps(
            candidate=candidate,
            wardrobe=wardrobe,
            compatibility_score=det.compatibility_score,
            outfit_combination_potential=det.outfit_combination_potential,
        )
        prompt = (
            f"compatibility_score={det.compatibility_score}; "
            f"outfit_combination_potential={det.outfit_combination_potential}\n"
            f"CANDIDATE_JSON:\n{candidate.model_dump_json()}\n"
            f"WARDROBE_JSON:\n{json.dumps([g.model_dump() for g in wardrobe])}"
        )
        adv: PurchaseROIAdvisorOutput = (await agent.run(prompt, deps=deps)).output
        return PurchaseAnalysisResponse(
            compatibility_score=det.compatibility_score,
            outfit_combination_potential=det.outfit_combination_potential,
            recommendation=adv.recommendation,
            explanation=adv.explanation,
            rationale_bullets=adv.rationale_bullets or det.rationale_bullets,
            used_live_agent=True,
        )
    except Exception:
        return det


def _narrative_offline(platform: str, outfit_summary: str, user_voice: str | None) -> GenerateScriptResponse:
    voice = user_voice or "confident and concise"
    if platform == "linkedin":
        script = (
            f"Hi — I am dialing up my presence for client-facing days. "
            f"Today's look is intentional: {outfit_summary}. "
            f"It reads polished without feeling stiff, which matches how I want collaborators to feel working with me."
        )
        cap = None
    elif platform == "dating":
        script = (
            f"If we meet, you'll probably notice this first: {outfit_summary}. "
            f"I like when style feels honest—{voice}—and comfortable enough to wander a city after dinner."
        )
        cap = "Low-key confident energy. Good food > loud clubs."
    else:
        script = (
            f"Outfit check: {outfit_summary}. "
            f"Three beats: clean silhouette, one texture pop, shoes that can keep up. {voice}."
        )
        cap = "Fit recap — steal the formula, not the flex."
    return GenerateScriptResponse(script=script, caption=cap, used_live_agent=False)


async def generate_script_with_optional_agent(
    platform: str,
    outfit_summary: str,
    user_voice: str | None,
) -> GenerateScriptResponse:
    settings = get_settings()
    if not settings.has_live_llm:
        return _narrative_offline(platform, outfit_summary, user_voice)
    try:
        agent = narrative_agent()
        deps = NarrativeDeps(platform=platform, outfit_summary=outfit_summary, user_voice=user_voice)
        prompt = f"platform={platform}\noutfit_summary={outfit_summary}\nuser_voice={user_voice!s}"
        out: NarrativeAgentOutput = (await agent.run(prompt, deps=deps)).output
        cap = None if platform == "linkedin" else out.caption
        return GenerateScriptResponse(script=out.script, caption=cap, used_live_agent=True)
    except Exception:
        return _narrative_offline(platform, outfit_summary, user_voice)


async def generate_reel_narration_with_optional_agent(
    *,
    outfit_summary: str,
    face_anchor_present: bool,
    user_voice: str | None,
) -> str:
    """
    Generate a short narration for a 30s reel.
    We keep it deterministic when Gemini isn't configured.
    """
    voice = user_voice or "confident, warm, and concise"
    if not get_settings().has_live_llm:
        face = "with your face anchor" if face_anchor_present else "without a face anchor"
        return (
            f"Runway reel narration ({face}): Clean silhouette, calm palette, and a confident walk. "
            f"Outfit: {outfit_summary}. Keep it {voice}."
        )
    try:
        agent = narrative_agent()
        prompt = (
            "Write a 25–40 second voiceover for an Instagram-style fashion reel.\n"
            f"Outfit summary: {outfit_summary}\n"
            f"Face anchor present: {face_anchor_present}\n"
            f"Voice: {voice}\n"
            "Constraints: 3 short beats (hook, details, close). No brand names."
        )
        deps = NarrativeDeps(platform="tiktok", outfit_summary=outfit_summary, user_voice=voice)
        out: NarrativeAgentOutput = (await agent.run(prompt, deps=deps)).output
        return out.script
    except Exception:
        face = "with your face anchor" if face_anchor_present else "without a face anchor"
        return (
            f"Runway reel narration ({face}): Clean silhouette, calm palette, and a confident walk. "
            f"Outfit: {outfit_summary}. Keep it {voice}."
        )


def orchestration_diagram() -> dict[str, Any]:
    """Documentation helper for API consumers / course report."""
    return {
        "ingest": ["WardrobeIngestionAgent (optional)", "deterministic_embedding", "InMemoryWardrobeStore"],
        "recommend": ["retrieve_style_rules (vector mock)", "StylingAgent (optional)", "heuristic fallback"],
        "purchase": ["deterministic scores", "PurchaseROIAdvisor (optional narrative overlay)"],
        "script": ["NarrativeAgent (optional)", "offline templates"],
        "video": ["GenerateVideoResponse mock / Runway hook"],
    }
