from __future__ import annotations

import hashlib
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


def _narrative_offline(
    platform: str,
    outfit_summary: str,
    user_voice: str | None,
    *,
    tone: str | None = None,
    emotion: str | None = None,
    target_audience: str | None = None,
    scenario: str | None = None,
    vibe: str | None = None,
) -> GenerateScriptResponse:
    voice = user_voice or "sound like a real person, not a press release"
    t = tone or "authentic"
    em = emotion or "calm confidence"
    aud = target_audience or "people who care about craft and fit"
    scen = scenario or "a normal day when you still want to feel put-together"
    vb = vibe or "quiet quality"
    h = int(hashlib.sha256(f"{platform}:{outfit_summary}:{voice}:{t}".encode()).hexdigest(), 16)
    variant = h % 3

    if platform == "linkedin":
        hooks = (
            (
                f"If we meet on Zoom or in a room, I want the first signal to be judgment and taste—not noise. "
                f"Today I’m wearing {outfit_summary}. It’s {t}, aimed at {aud}, in a {vb} register."
            ),
            (
                f"Quick leadership frame: I’m not dressing for performance art; I’m dressing for decisions. "
                f"This combo—{outfit_summary}—keeps me {em} while staying appropriate for {scen}."
            ),
            (
                f"I’ve been thinking about presence as a form of respect. "
                f"This outfit ({outfit_summary}) is my version of showing up: {t}, {em}, built for {aud}."
            ),
        )
        script = hooks[variant]
        cap = f"Fit note — {vb}: intention over flex."
        return GenerateScriptResponse(script=script, caption=cap, hashtags=None, used_live_agent=False)

    if platform == "instagram":
        hooks = (
            (
                f"Okay—fit check, but make it human.\n"
                f"The pieces: {outfit_summary}.\n"
                f"The vibe: {vb}. The feeling I want: {em}.\n"
                f"Scenario: {scen}. Talking to: {aud}.\n"
                f"Three seconds: silhouette. Six seconds: texture. Finish on the shoes—promise."
            ),
            (
                f"Camera roll energy, not a catalog.\n"
                f"{outfit_summary} — styled for {scen}, with a {t} tone.\n"
                f"I’m going for {em} because that’s what I want people to feel when they scroll past."
            ),
            (
                f"This is the ‘I actually got dressed’ version of me.\n"
                f"{outfit_summary}. {vb} palette, {t} delivery.\n"
                f"If you’re {aud}, tell me what you’d tweak—lace swap? layer? I’m listening."
            ),
        )
        script = hooks[variant]
        cap = f"{vb} / {t} — saved you the Pinterest board."
        tags = ["#ootd", "#quietluxury", "#fitcheck", "#menswear", "#styletips", "#wardrobe"]
        return GenerateScriptResponse(script=script, caption=cap, hashtags=tags, used_live_agent=False)

    # tiktok
    hooks = (
        (
            f"POV: you’re not trying to go viral—you’re trying to look like you mean it.\n"
            f"Fit: {outfit_summary}.\n"
            f"Set the tone: {t}. Emotion: {em}. Audience: {aud}.\n"
            f"Scenario: {scen}. Keep it tight—hook, prove it, out."
        ),
        (
            f"Stop scrolling—three beats.\n"
            f"One: {outfit_summary}.\n"
            f"Two: the vibe is {vb}.\n"
            f"Three: I’m speaking to {aud} with {t} energy—{em}.\n"
            f"That’s the whole thesis."
        ),
        (
            f"Real talk: clothes are a shortcut to credibility.\n"
            f"Today: {outfit_summary}.\n"
            f"I’m in {scen}, aiming at {aud}, channeling {em}.\n"
            f"If it feels relatable, duet me with your swap."
        ),
    )
    script = hooks[variant]
    cap = "Fit thesis in 20s — steal the structure."
    tags = ["#fitok", "#fitcheck", "#styletips", "#outfitideas", "#OOTD", "#fashiontiktok", "#wardrobe"]
    return GenerateScriptResponse(script=script, caption=cap, hashtags=tags, used_live_agent=False)


async def generate_script_with_optional_agent(
    platform: str,
    outfit_summary: str,
    user_voice: str | None,
    *,
    tone: str | None = None,
    emotion: str | None = None,
    target_audience: str | None = None,
    scenario: str | None = None,
    vibe: str | None = None,
) -> GenerateScriptResponse:
    settings = get_settings()
    if not settings.has_live_llm:
        return _narrative_offline(
            platform,
            outfit_summary,
            user_voice,
            tone=tone,
            emotion=emotion,
            target_audience=target_audience,
            scenario=scenario,
            vibe=vibe,
        )
    try:
        agent = narrative_agent()
        deps = NarrativeDeps(
            platform=platform,
            outfit_summary=outfit_summary,
            user_voice=user_voice,
            tone=tone,
            emotion=emotion,
            target_audience=target_audience,
            scenario=scenario,
            vibe=vibe,
        )
        prompt = (
            f"platform={platform}\noutfit_summary={outfit_summary}\nuser_voice={user_voice!s}\n"
            f"tone={tone!s}\nemotion={emotion!s}\ntarget_audience={target_audience!s}\n"
            f"scenario={scenario!s}\nvibe={vibe!s}"
        )
        out: NarrativeAgentOutput = (await agent.run(prompt, deps=deps)).output
        cap = None if platform == "linkedin" else out.caption
        return GenerateScriptResponse(
            script=out.script,
            caption=cap,
            hashtags=out.hashtags,
            used_live_agent=True,
        )
    except Exception:
        return _narrative_offline(
            platform,
            outfit_summary,
            user_voice,
            tone=tone,
            emotion=emotion,
            target_audience=target_audience,
            scenario=scenario,
            vibe=vibe,
        )


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
        summary = outfit_summary.strip()
        if summary.lower().startswith("outfit:"):
            summary = summary[7:].strip()
        return (
            f"Runway reel narration ({face}): clean silhouette, calm palette, confident walk. "
            f"{summary}. Keep it {voice}."
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
        summary = outfit_summary.strip()
        if summary.lower().startswith("outfit:"):
            summary = summary[7:].strip()
        return (
            f"Runway reel narration ({face}): clean silhouette, calm palette, confident walk. "
            f"{summary}. Keep it {voice}."
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
