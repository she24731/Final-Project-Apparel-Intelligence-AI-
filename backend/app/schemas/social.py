from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class SocialPostPrepareRequest(BaseModel):
    """Prepare copy + safe web intents for manual posting (no OAuth secrets in MVP)."""

    platform: Literal["linkedin", "instagram", "tiktok"]
    script: str
    caption: str | None = None
    hashtags: list[str] | None = None
    link_url: str | None = Field(
        default=None,
        description="Optional public URL to attach (portfolio, lookbook, storefront).",
    )


class SocialPostPrepareResponse(BaseModel):
    platform: str
    clipboard_text: str
    linkedin_share_url: str | None = None
    instagram_web_url: str = "https://www.instagram.com/create/select/"
    tiktok_upload_url: str = "https://www.tiktok.com/upload"
    notes: str = (
        "Official auto-posting requires each platform’s OAuth app. "
        "This endpoint returns copy you can paste and the best-effort web destinations."
    )
