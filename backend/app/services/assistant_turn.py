from __future__ import annotations

import json
import re
from typing import Literal

from app.agents.definitions import concierge_agent
from app.agents.deps import ConciergeDeps
from app.agents.outputs import ConciergeOutput
from app.agents.orchestrator import (
    analyze_purchase_with_optional_agent,
    generate_reel_narration_with_optional_agent,
    generate_script_with_optional_agent,
    recommend_outfit_with_optional_agent,
)
from app.config import get_settings
from app.media.pipeline import build_anchor_scenes, build_media_prompts
from app.schemas.assistant import AssistantTurnResponse, ChatContext
from app.schemas.media import GenerateVideoRequest
from app.schemas.wardrobe import GarmentRecord
from app.services.store import get_store
from app.services.video_generation import run_generate_video


def _wardrobe_for_context(ctx: ChatContext) -> list[GarmentRecord]:
    store = get_store()
    all_g = store.all()
    if ctx.wardrobe_item_ids:
        wanted = set(ctx.wardrobe_item_ids)
        return [g for g in all_g if g.id in wanted]
    return all_g


def _detect_platform(msg: str) -> Literal["linkedin", "instagram", "tiktok"]:
    m = msg.lower()
    if "linkedin" in m:
        return "linkedin"
    if "tiktok" in m or "tik tok" in m:
        return "tiktok"
    if "instagram" in m or "insta" in m or "ig" in m:
        return "instagram"
    return "instagram"


async def _do_recommend(context: ChatContext, wardrobe: list[GarmentRecord], actions: list[str]) -> AssistantTurnResponse:
    rec = await recommend_outfit_with_optional_agent(
        occasion=context.occasion.strip() or "work_presentation",
        weather=context.weather.strip() or "mild_clear",
        vibe=context.vibe.strip() or "quiet_luxury",
        wardrobe=wardrobe,
        user_preference=context.preference.strip() or None,
    )
    actions.append("recommend_outfit")
    expl = rec.explanation[:420] + ("…" if len(rec.explanation) > 420 else "")
    return AssistantTurnResponse(
        reply=(
            f"I put together an outfit (confidence {rec.confidence:.2f}). {expl}\n"
            "You can open **Simulation** to turn this into scripts and a reel."
        ),
        actions=actions,
        recommendation=rec,
    )


async def _do_script(
    platform: Literal["linkedin", "instagram", "tiktok"],
    context: ChatContext,
    wardrobe: list[GarmentRecord],
    actions: list[str],
) -> AssistantTurnResponse:
    outfit_summary = context.outfit_summary
    if not outfit_summary:
        outfit_summary = ", ".join(f"{g.color} {g.category}" for g in wardrobe[:6]) or "neutral top, neutral bottom, neutral shoes"
    scr = await generate_script_with_optional_agent(
        platform=platform,
        outfit_summary=outfit_summary,
        user_voice=context.preference or None,
        tone=None,
        emotion=None,
        target_audience=None,
        scenario=None,
        vibe=context.vibe or None,
    )
    actions.append("generate_script")
    cap = f"\n\nCaption: {scr.caption}" if scr.caption else ""
    tags = ""
    if scr.hashtags:
        tags = "\n\n" + " ".join(scr.hashtags)
    return AssistantTurnResponse(
        reply=f"**{platform} script**\n\n{scr.script}{cap}{tags}",
        actions=actions,
        script=scr,
    )


async def _do_preview_reel(context: ChatContext, wardrobe: list[GarmentRecord], actions: list[str]) -> AssistantTurnResponse:
    outfit_summary = context.outfit_summary or "a clean minimalist outfit"
    scene = f"{outfit_summary}. Runway walk-through with natural light and slow pan."

    narr = await generate_reel_narration_with_optional_agent(
        outfit_summary=scene,
        face_anchor_present=bool(context.face_anchor_path),
        user_voice=None,
    )
    prompts = build_media_prompts(outfit=None, narrative=scene, duration_seconds=30)
    anchors = [g.image_path for g in wardrobe if str(g.image_path).startswith("uploads/")][:4]
    build_anchor_scenes(
        anchor_paths=anchors,
        scene_prompt=scene,
        narration=narr,
        face_anchor_path=context.face_anchor_path,
    )
    actions.append("preview_reel_copy")
    return AssistantTurnResponse(
        reply=(
            f"**Runway description:** {prompts.storyboard.logline}\n\n"
            f"**Narration:** {narr}\n\n"
            "_Open Simulation to edit per-scene lines and render video._"
        ),
        actions=actions,
    )


async def _do_render_video(context: ChatContext, wardrobe: list[GarmentRecord], actions: list[str]) -> AssistantTurnResponse:
    outfit_summary = context.outfit_summary or "neutral top, neutral bottom, neutral shoes"
    scene = f"{outfit_summary}. Runway walk-through with natural light and slow pan."
    anchors = [g.image_path for g in wardrobe if str(g.image_path).startswith("uploads/")]
    req = GenerateVideoRequest(
        scene_prompt=scene,
        anchor_image_paths=anchors,
        face_anchor_image_path=context.face_anchor_path,
        duration_seconds=30,
        narration_text=None,
    )
    vid = await run_generate_video(req)
    actions.append("generate_video")
    note = (
        "Video file is ready in the UI when `video_url` is set."
        if vid.video_url
        else "No MP4 returned: confirm `MEDIA_PROVIDER=gemini_video`, a valid `GEMINI_API_KEY`, and Veo access on your Google AI project."
    )
    return AssistantTurnResponse(
        reply=f"**Reel status:** {vid.status} ({vid.provider}). {vid.preview_message}\n{note}",
        actions=actions,
        video=vid,
    )


async def _do_analyze_purchase(
    garment_id: str,
    wardrobe: list[GarmentRecord],
    actions: list[str],
) -> AssistantTurnResponse:
    cand = next((g for g in wardrobe if g.id == garment_id), None)
    if not cand:
        return AssistantTurnResponse(
            reply=f"I couldn't find garment id `{garment_id}` in the active wardrobe list.",
            actions=actions,
        )
    pur = await analyze_purchase_with_optional_agent(cand, wardrobe)
    actions.append("analyze_purchase")
    return AssistantTurnResponse(
        reply=(
            f"Purchase read: **{pur.recommendation}**. {pur.explanation}\n"
            f"Compatibility: {pur.compatibility_score:.2f}; combo potential: {pur.outfit_combination_potential}."
        ),
        actions=actions,
    )


async def _dispatch_concierge(
    co: ConciergeOutput,
    message: str,
    context: ChatContext,
    wardrobe: list[GarmentRecord],
) -> AssistantTurnResponse:
    actions: list[str] = ["concierge_gemini"]
    if co.action == "chat_only":
        return AssistantTurnResponse(reply=co.reply, actions=actions)

    if co.action == "recommend_outfit":
        res = await _do_recommend(context, wardrobe, actions)
        return AssistantTurnResponse(
            reply=f"{co.reply}\n\n{res.reply}",
            actions=res.actions,
            recommendation=res.recommendation,
        )

    if co.action == "write_script":
        plat = co.script_platform or _detect_platform(message.lower())
        res = await _do_script(plat, context, wardrobe, actions)
        return AssistantTurnResponse(
            reply=f"{co.reply}\n\n{res.reply}",
            actions=res.actions,
            script=res.script,
        )

    if co.action == "preview_reel":
        res = await _do_preview_reel(context, wardrobe, actions)
        return AssistantTurnResponse(
            reply=f"{co.reply}\n\n{res.reply}",
            actions=res.actions,
        )

    if co.action == "render_video":
        res = await _do_render_video(context, wardrobe, actions)
        return AssistantTurnResponse(
            reply=f"{co.reply}\n\n{res.reply}",
            actions=res.actions,
            video=res.video,
        )

    if co.action == "analyze_purchase":
        gid = (co.purchase_garment_id or "").strip()
        if not gid:
            m = re.search(r"analyze\s+(?:purchase|buy)\s+(?:for\s+)?([a-z0-9\-]{4,})", message.lower())
            gid = m.group(1) if m else ""
        if not gid:
            return AssistantTurnResponse(
                reply=f"{co.reply}\n\nWhich wardrobe item should I analyze? Paste a garment id from Wardrobe.",
                actions=actions,
            )
        res = await _do_analyze_purchase(gid, wardrobe, actions)
        return AssistantTurnResponse(
            reply=f"{co.reply}\n\n{res.reply}",
            actions=res.actions,
        )

    return AssistantTurnResponse(reply=co.reply, actions=actions)


async def _gemini_concierge_turn(message: str, context: ChatContext, wardrobe: list[GarmentRecord]) -> AssistantTurnResponse | None:
    settings = get_settings()
    if not settings.has_live_llm:
        return None
    wardrobe_json = json.dumps([g.model_dump() for g in wardrobe], default=str)
    deps = ConciergeDeps(
        occasion=context.occasion,
        weather=context.weather,
        vibe=context.vibe,
        preference=context.preference,
        outfit_summary=context.outfit_summary,
        face_anchor_path=context.face_anchor_path,
        wardrobe_json=wardrobe_json,
    )
    agent = concierge_agent()
    prompt = (
        f"[CONTEXT]\noccasion={context.occasion!r}\nweather={context.weather!r}\nvibe={context.vibe!r}\n"
        f"preference={context.preference!r}\noutfit_summary={context.outfit_summary!r}\n"
        f"face_anchor_path={context.face_anchor_path!r}\n\n"
        f"[WARDROBE_JSON]\n{wardrobe_json}\n\n[USER_MESSAGE]\n{message}"
    )
    result = await agent.run(prompt, deps=deps)
    return await _dispatch_concierge(result.output, message, context, wardrobe)


async def _keyword_assistant_turn(message: str, context: ChatContext, wardrobe: list[GarmentRecord]) -> AssistantTurnResponse:
    msg = message.strip()
    low = msg.lower()
    actions: list[str] = []

    if any(
        k in low
        for k in (
            "recommend",
            "suggest an outfit",
            "suggest outfit",
            "what should i wear",
            "style me",
            "pick an outfit",
            "outfit idea",
        )
    ):
        return await _do_recommend(context, wardrobe, actions)

    m = re.search(r"analyze\s+(?:purchase|buy)\s+(?:for\s+)?([a-z0-9\-]{6,})", low)
    if m:
        return await _do_analyze_purchase(m.group(1), wardrobe, actions)

    if any(
        k in low
        for k in (
            "script",
            "caption",
            "hook",
            "linkedin",
            "instagram",
            "tiktok",
            "post copy",
            "write copy",
        )
    ):
        plat = _detect_platform(low)
        return await _do_script(plat, context, wardrobe, actions)

    if any(k in low for k in ("preview reel", "reel copy", "runway copy", "narration draft")):
        return await _do_preview_reel(context, wardrobe, actions)

    if any(
        k in low
        for k in (
            "render video",
            "generate video",
            "make the reel",
            "make a video",
            "veo",
            "runway video",
        )
    ):
        return await _do_render_video(context, wardrobe, actions)

    return AssistantTurnResponse(
        reply=(
            "Try asking:\n"
            "- “Recommend an outfit for work”\n"
            "- “Write an Instagram script for this outfit”\n"
            "- “Preview reel copy”\n"
            "- “Generate video”\n"
            "- “Analyze purchase for <garment-id>”"
        ),
        actions=actions,
    )


async def run_assistant_turn(message: str, context: ChatContext) -> AssistantTurnResponse:
    msg = message.strip()
    if not msg:
        return AssistantTurnResponse(
            reply="Ask me to recommend an outfit, write a script, preview reel copy, or render a video.",
            actions=[],
        )

    wardrobe = _wardrobe_for_context(context)
    settings = get_settings()

    if settings.has_live_llm:
        try:
            gem = await _gemini_concierge_turn(msg, context, wardrobe)
            if gem is not None:
                return gem
        except Exception:
            # Fall back to deterministic keyword router if Gemini errors (quota, network, etc.)
            pass

    return await _keyword_assistant_turn(msg, context, wardrobe)
