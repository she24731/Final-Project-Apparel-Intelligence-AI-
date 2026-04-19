from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import health, media, purchase, recommend, wardrobe

app = FastAPI(title="Apparel Intelligence API", version="0.1.0")

_settings = get_settings()
_settings.data_dir.mkdir(parents=True, exist_ok=True)
_settings.uploads_dir.mkdir(parents=True, exist_ok=True)
_settings.generated_media_dir.mkdir(parents=True, exist_ok=True)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(wardrobe.router)
app.include_router(recommend.router)
app.include_router(purchase.router)
app.include_router(media.router)

# Serve uploaded images for UI thumbnails.
app.mount("/uploads", StaticFiles(directory=str(_settings.uploads_dir)), name="uploads")
# Serve generated media (mp4) for the Content page.
app.mount("/generated_media", StaticFiles(directory=str(_settings.generated_media_dir)), name="generated_media")


@app.on_event("startup")
async def startup() -> None:
    _settings.data_dir.mkdir(parents=True, exist_ok=True)
    _settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    # Initialize retrieval KB (wardrobe ingests on demand)
    from app.retrieval.service import get_retrieval_service

    _ = get_retrieval_service()
