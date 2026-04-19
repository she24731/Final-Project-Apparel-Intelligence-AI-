from __future__ import annotations

import json
import sys
from typing import Any


def main() -> int:
    # This script is intentionally tiny and deterministic.
    # It validates that the backend core modules import and the main endpoints can be called in-process.
    import os
    import pathlib
    import sys

    # Ensure `import app.*` works when run from repo root in CI.
    backend_dir = pathlib.Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("PYTHONPATH", str(backend_dir))

    from app.main import app
    from fastapi.testclient import TestClient

    client = TestClient(app)

    r = client.get("/health")
    assert r.status_code == 200, r.text

    # recommend-outfit (should always return a structured response, even with empty wardrobe)
    r = client.post(
        "/recommend-outfit",
        json={
            "occasion": "work_presentation",
            "weather": "mild_clear",
            "vibe": "quiet_luxury",
            "wardrobe_item_ids": [],
            "user_preference": "no loud logos",
        },
    )
    assert r.status_code == 200, r.text
    data: dict[str, Any] = r.json()
    assert "confidence" in data
    assert "outfit_items" in data

    # analyze-purchase should work without embeddings (backend will compute deterministic embedding)
    r = client.post(
        "/analyze-purchase",
        json={
            "candidate": {
                "id": "candidate-ci",
                "category": "shoes",
                "color": "brown",
                "formality_score": 0.65,
                "season": "all-season",
                "tags": ["leather"],
                "image_path": "uploads/candidate_stub.png",
                "embedding": [],
            },
            "wardrobe_item_ids": [],
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "recommendation" in data

    # Ensure response is JSON-serializable (no numpy scalars, etc.)
    json.dumps(data)

    r = client.post(
        "/generate-script",
        json={
            "platform": "tiktok",
            "outfit_summary": "navy top, charcoal trousers, white sneakers",
            "tone": "warm",
            "emotion": "playful",
            "target_audience": "creatives",
            "scenario": "commute",
            "vibe": "quiet luxury",
        },
    )
    assert r.status_code == 200, r.text
    assert "script" in r.json()

    r = client.post(
        "/preview-reel-copy",
        json={
            "scene_prompt": "neutral top, neutral bottom. runway walk.",
            "anchor_image_paths": [],
            "face_anchor_path": None,
            "duration_seconds": 12,
            "face_anchor_present": False,
        },
    )
    assert r.status_code == 200, r.text
    assert "scenes" in r.json()

    r = client.post(
        "/social/prepare-post",
        json={
            "platform": "linkedin",
            "script": "Hello world",
            "caption": "Test",
            "hashtags": ["style"],
            "link_url": "http://127.0.0.1:5173",
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("clipboard_text")

    r = client.post(
        "/assistant/turn",
        json={
            "message": "Write an Instagram script for this outfit",
            "context": {
                "outfit_summary": "ivory shirt, navy chinos",
                "wardrobe_item_ids": [],
            },
        },
    )
    assert r.status_code == 200, r.text
    assert r.json().get("reply")

    print("ci_smoke_ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
