from __future__ import annotations

import re
from typing import Literal

from app.agents.orchestrator import (
    analyze_purchase_with_optional_agent,
    generate_reel_narration_with_optional_agent,
    generate_script_with_optional_agent,
    recommend_outfit_with_optional_agent,
)
from app.media.pipeline import build_anchor_scenes, build_media_prompts
from app.schemas.assistant import AssistantTurnResponse, ChatContext
from app.schemas.media import GenerateVideoRequest
from app.services.store import get_store
from app.services.video_generation import run_generate_video


def _wardrobe_for_context(ctx: ChatContext):
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


async def run_assistant_turn(message: str, context: ChatContext) -> AssistantTurnResponse:
    msg = message.strip()
    low = msg.lower()
    actions: list[str] = []

    if not msg:
        return AssistantTurnResponse(
            reply="Ask me to recommend an outfit, write a script, preview reel copy, or render a video.",
            actions=actions,
        )

    wardrobe = _wardrobe_for_context(context)

    # Outfit recommendation
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
                f"You can open **Simulation** to turn this into scripts and a reel."
            ),
            actions=actions,
            recommendation=rec,
        )

    # Purchase analysis (needs explicit candidate id in message: "analyze purchase for <id>")
    m = re.search(r"analyze\s+(?:purchase|buy)\s+(?:for\s+)?([a-z0-9\-]{6,})", low)
    if m:
        gid = m.group(1)
        cand = next((g for g in wardrobe if g.id == gid), None)
        if not cand:
            return AssistantTurnResponse(
                reply=f"I couldn't find garment id `{gid}` in the active wardrobe list.",
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

    # Script / caption
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
        outfit_summary = context.outfit_summary
        if not outfit_summary:
            outfit_summary = ", ".join(f"{g.color} {g.category}" for g in wardrobe[:6]) or "neutral top, neutral bottom, neutral shoes"
        scr = await generate_script_with_optional_agent(
            platform=plat,
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
            reply=f"**{plat} script**\n\n{scr.script}{cap}{tags}",
            actions=actions,
            script=scr,
        )

    # Preview reel copy (no provider)
    if any(k in low for k in ("preview reel", "reel copy", "runway copy", "narration draft")):
        outfit_summary = context.outfit_summary or "a clean minimalist outfit"
        scene = f"{outfit_summary}. Runway walk-through with natural light and slow pan."

        narr = await generate_reel_narration_with_optional_agent(
            outfit_summary=scene,
            face_anchor_present=bool(context.face_anchor_path),
            user_voice=None,
        )
        prompts = build_media_prompts(outfit=None, narrative=scene, duration_seconds=30)
        anchors = [g.image_path for g in wardrobe if str(g.image_path).startswith("uploads/")][:4]
        scenes = build_anchor_scenes(
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
                f"_Open Simulation to edit per-scene lines and render video._"
            ),
            actions=actions,
        )

    # Video render
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
            "Video file is ready above."
            if vid.video_url
            else "No MP4 yet: backend is in `MEDIA_PROVIDER=mock` unless you configure Gemini video. "
            "Set `MEDIA_PROVIDER=gemini_video` and `GEMINI_API_KEY` in `backend/.env` for real renders."
        )
        return AssistantTurnResponse(
            reply=f"**Reel status:** {vid.status} ({vid.provider}). {vid.preview_message}\n{note}",
            actions=actions,
            video=vid,
        )

    return AssistantTurnResponse(
        reply=(
            "Try asking:\n"
            "- “Recommend an outfit for work”\n"
            "- “Write an Instagram script for this outfit”\n"
            "- “Preview reel copy”\n"
            "- “Generate video” (needs provider config for MP4)\n"
            "- “Analyze purchase for <garment-id>”"
        ),
        actions=actions,
    )
