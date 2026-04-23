from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.routers import assistant, health, media, purchase, recommend, social, wardrobe

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
app.include_router(social.router)
app.include_router(assistant.router)

# Some clients run behind a frontend dev proxy that prefixes paths with `/api`.
# To avoid brittle env/proxy mismatches, we support both the bare routes and `/api/*`.
app.include_router(health.router, prefix="/api")
app.include_router(wardrobe.router, prefix="/api")
app.include_router(recommend.router, prefix="/api")
app.include_router(purchase.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(social.router, prefix="/api")
app.include_router(assistant.router, prefix="/api")

# Serve uploaded images for UI thumbnails.
app.mount("/uploads", StaticFiles(directory=str(_settings.uploads_dir)), name="uploads")
# Also serve them under `/api/uploads` for callers whose base includes `/api`.
app.mount("/api/uploads", StaticFiles(directory=str(_settings.uploads_dir)), name="api_uploads")
# Serve generated media (mp4) for the Content page.
app.mount("/generated_media", StaticFiles(directory=str(_settings.generated_media_dir)), name="generated_media")
# And under `/api/generated_media` for symmetry with `/api` bases.
app.mount(
    "/api/generated_media",
    StaticFiles(directory=str(_settings.generated_media_dir)),
    name="api_generated_media",
)

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.on_event("startup")
async def startup() -> None:
    _settings.data_dir.mkdir(parents=True, exist_ok=True)
    _settings.uploads_dir.mkdir(parents=True, exist_ok=True)
    # Initialize retrieval KB (wardrobe ingests on demand)
    from app.retrieval.service import get_retrieval_service

    _ = get_retrieval_service()
