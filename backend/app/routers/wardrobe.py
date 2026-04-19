from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.orchestrator import ingest_garment_with_optional_agent
from app.schemas.wardrobe import IngestGarmentResponse
from app.retrieval.service import get_retrieval_service
from app.services.store import get_store

router = APIRouter(tags=["wardrobe"])


@router.post("/ingest-garment", response_model=IngestGarmentResponse)
async def ingest_garment(
    file: UploadFile = File(...),
    hints: str | None = Form(default=None),
) -> IngestGarmentResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Missing filename on upload")
    from app.config import get_settings

    settings = get_settings()
    settings.data_dir.mkdir(parents=True, exist_ok=True)
    settings.uploads_dir.mkdir(parents=True, exist_ok=True)

    safe_name = file.filename.replace("/", "_").replace("\\", "_")
    dest = settings.uploads_dir / safe_name
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")
    dest.write_bytes(content)
    rel_path = f"uploads/{safe_name}"

    resp = await ingest_garment_with_optional_agent(filename=file.filename, image_path=rel_path, hints=hints)
    get_store().upsert(resp.garment)
    # Keep retrieval index warm for demo responsiveness
    get_retrieval_service().ingest_wardrobe(get_store().all())
    return resp
