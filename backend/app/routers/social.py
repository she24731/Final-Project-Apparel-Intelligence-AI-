from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter

from app.schemas.social import SocialPostPrepareRequest, SocialPostPrepareResponse

router = APIRouter(tags=["social"])


@router.post("/social/prepare-post", response_model=SocialPostPrepareResponse)
def prepare_post(body: SocialPostPrepareRequest) -> SocialPostPrepareResponse:
    """
    Returns clipboard-ready text plus best-effort web URLs.

    Fully automated posting requires each network's OAuth developer app; this MVP focuses on copy + destinations.
    """
    link = (body.link_url or "").strip() or "http://127.0.0.1:5173"
    script = body.script.strip()
    cap = (body.caption or "").strip()
    tag_line = " ".join(f"#{t.lstrip('#')}" for t in (body.hashtags or []) if t.strip())

    parts: list[str] = []
    if script:
        parts.append(script)
    if cap:
        parts.append(cap)
    if tag_line:
        parts.append(tag_line)
    if link and body.platform != "linkedin":
        parts.append(link)
    clipboard = "\n\n".join(p for p in parts if p)

    linkedin_share = f"https://www.linkedin.com/sharing/share-offsite/?url={quote(link, safe='')}"

    return SocialPostPrepareResponse(
        platform=body.platform,
        clipboard_text=clipboard,
        linkedin_share_url=linkedin_share,
    )
