from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.schemas.assistant import AssistantTurnRequest, AssistantTurnResponse
from app.schemas.reel_preview import PreviewReelCopyRequest
from app.services.store import get_store
from app.services.assistant_turn import run_assistant_turn
from app.utils.image_upload import looks_like_image_upload

router = APIRouter(tags=["assistant"])


@router.post("/assistant/turn", response_model=AssistantTurnResponse)
async def assistant_turn(body: AssistantTurnRequest) -> AssistantTurnResponse:
    return await run_assistant_turn(body.message, body.context)


@router.post("/assistant/turn-multipart", response_model=AssistantTurnResponse)
async def assistant_turn_multipart(
    message: str = Form(...),
    context_json: str = Form(default="{}"),
    files: list[UploadFile] = File(default_factory=list),
) -> AssistantTurnResponse:
    """
    Chat entrypoint that supports attachments:
    - first image becomes face anchor (if context.face_anchor_path missing)
    - remaining images are ingested as wardrobe items
    """
    from app.config import get_settings
    from app.schemas.assistant import ChatContext
    from app.agents.orchestrator import ingest_garment_with_optional_agent
    from app.routers.media import upload_anchor  # reuse logic

    try:
        ctx_obj = json.loads(context_json or "{}")
    except Exception:
        ctx_obj = {}
    ctx = ChatContext(**(ctx_obj or {}))

    settings = get_settings()
    store = get_store()

    # Handle attachments.
    if files:
        # Filter to images only.
        img_files = [
            f
            for f in files
            if looks_like_image_upload(filename=f.filename, content_type=f.content_type)
        ]
        # Face anchor: first image if missing.
        if not ctx.face_anchor_path and img_files:
            try:
                # Call existing anchor uploader with kind=face
                res = await upload_anchor(file=img_files[0], kind="face")  # type: ignore[arg-type]
                ctx.face_anchor_path = res.get("path")
            except Exception as exc:
                raise HTTPException(status_code=400, detail=f"Failed to upload face anchor: {exc!s}")

            img_files = img_files[1:]

        # Ingest remaining as wardrobe candidates.
        for f in img_files[:8]:
            try:
                if not f.filename:
                    continue
                settings.data_dir.mkdir(parents=True, exist_ok=True)
                settings.uploads_dir.mkdir(parents=True, exist_ok=True)
                safe_name = f.filename.replace("/", "_").replace("\\", "_")
                dest = settings.uploads_dir / safe_name
                content = await f.read()
                if not content:
                    continue
                dest.write_bytes(content)
                rel_path = f"uploads/{safe_name}"
                ing = await ingest_garment_with_optional_agent(filename=f.filename, image_path=rel_path, hints=None)
                store.upsert(ing.garment)
                if ing.garment and ing.garment.id:
                    ctx.wardrobe_item_ids = list({*ctx.wardrobe_item_ids, ing.garment.id})
            except Exception:
                continue

    res = await run_assistant_turn(message, ctx)
    # Always return updated context so the frontend stays synced.
    res.updated_context = ctx
    return res
