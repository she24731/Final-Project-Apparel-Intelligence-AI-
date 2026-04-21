from __future__ import annotations

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from app.agents.orchestrator import ingest_garment_with_optional_agent
from app.schemas.wardrobe import IngestGarmentResponse
from app.schemas.wardrobe import GarmentRecord
from app.retrieval.service import get_retrieval_service
from app.services.store import get_store
from app.utils.image_upload import looks_like_image_upload

router = APIRouter(tags=["wardrobe"])


@router.get("/garments", response_model=list[GarmentRecord])
async def list_garments() -> list[GarmentRecord]:
    """Return the current server-side wardrobe items."""
    return get_store().all()


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
    # Demo-friendly: accept common images including iPhone HEIC/HEIF.
    # Reject only clearly non-image uploads.
    if not looks_like_image_upload(filename=file.filename, content_type=file.content_type):
        raise HTTPException(
            status_code=415,
            detail="Unsupported file type. Please upload an image file (JPG, PNG, WebP, HEIC, etc.).",
        )
    max_mb = 10
    if len(content) > max_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Max size is {max_mb}MB.")
    dest.write_bytes(content)
    rel_path = f"uploads/{safe_name}"

    resp = await ingest_garment_with_optional_agent(filename=file.filename, image_path=rel_path, hints=hints)
    get_store().upsert(resp.garment)
    # Keep retrieval index warm for demo responsiveness
    get_retrieval_service().ingest_wardrobe(get_store().all())
    return resp


@router.delete("/garments/{garment_id}")
async def delete_garment(garment_id: str) -> dict[str, str]:
    from app.config import get_settings

    settings = get_settings()
    store = get_store()
    deleted = store.delete(garment_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Garment not found")

    # Best-effort delete file on disk (if it lives under uploads/)
    try:
        if deleted.image_path.startswith("uploads/"):
            fname = deleted.image_path.split("/", 1)[1]
            p = settings.uploads_dir / fname
            if p.exists():
                p.unlink()
    except Exception:
        pass

    get_retrieval_service().ingest_wardrobe(store.all())
    return {"status": "deleted", "id": garment_id}


@router.delete("/garments")
async def delete_all_garments() -> dict[str, int]:
    """
    Delete all garments in the server wardrobe.
    Intended for demo UX when users upload hundreds of photos.
    """
    from app.config import get_settings

    settings = get_settings()
    store = get_store()
    deleted = store.clear()
    removed_files = 0

    # Best-effort delete each uploaded file referenced by garments.
    for g in deleted:
        try:
            if g.image_path.startswith("uploads/"):
                fname = g.image_path.split("/", 1)[1]
                p = settings.uploads_dir / fname
                if p.exists():
                    p.unlink()
                    removed_files += 1
        except Exception:
            pass

    get_retrieval_service().ingest_wardrobe(store.all())
    return {"deleted_count": len(deleted), "removed_files": removed_files}
