#!/usr/bin/env python3
"""
End-to-end check for POST /generate-scenes (same flow as UI: face + wardrobe anchors).

Requires GEMINI_API_KEY (e.g. in backend/.env). Uses DATA_DIR under this backend folder.

Usage (from repo):
  cd apparel-intelligence/backend && .venv/bin/python scripts/e2e_generate_scenes.py
"""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def _load_dotenv(env_path: Path) -> None:
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if k and k not in os.environ:
            os.environ[k] = v


def main() -> int:
    backend_dir = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(backend_dir))
    os.environ.setdefault("DATA_DIR", str(backend_dir / "data"))
    _load_dotenv(backend_dir / ".env")

    if not (os.getenv("GEMINI_API_KEY") or "").strip():
        print("SKIP: GEMINI_API_KEY not set (add to backend/.env).", file=sys.stderr)
        return 2

    data_dir = Path(os.environ["DATA_DIR"]).resolve()
    uploads = data_dir / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)

    # Prefer real JPEGs from the course Images folder (if present).
    final_project = backend_dir.parent.parent
    images_dir = final_project / "Images"
    face_dest = uploads / "e2e_face.jpg"
    garm_dest = uploads / "e2e_garment.jpg"
    face_src = images_dir / "IMG_7545.JPG"
    garm_src = images_dir / "IMG_8077.JPG"
    wardrobe_dir = images_dir / "Wardrobe"
    if face_src.is_file():
        shutil.copyfile(face_src, face_dest)
    if garm_src.is_file():
        shutil.copyfile(garm_src, garm_dest)
    elif wardrobe_dir.is_dir():
        cand = next(
            (p for p in sorted(wardrobe_dir.iterdir()) if p.is_file() and p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}),
            None,
        )
        if cand is not None:
            shutil.copyfile(cand, garm_dest)
    elif face_src.is_file():
        shutil.copyfile(face_src, garm_dest)
    if not face_dest.is_file():
        # Minimal valid PNG (1x1) so the test still exercises paths if Images/ missing.
        png = (
            b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
            b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00\x05"
            b"\x18\xd8N\x12\x00\x00\x00\x00IEND\xaeB`\x82"
        )
        face_dest.write_bytes(png)
        garm_dest.write_bytes(png)
    if not garm_dest.is_file() or garm_dest.stat().st_size < 100:
        shutil.copyfile(face_dest, garm_dest)

    face_rel = f"uploads/{face_dest.name}"
    garm_rel = f"uploads/{garm_dest.name}"

    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    r = client.post(
        "/generate-scenes",
        json={
            "scene_prompt": (
                "Soft evening light in the city; one person in casual streetwear, calm cinematic framing, no violence."
            ),
            "anchor_image_paths": [garm_rel],
            "face_anchor_path": face_rel,
            "duration_seconds": 30,
            "face_anchor_present": True,
        },
    )
    if r.status_code != 200:
        print(r.status_code, r.text, file=sys.stderr)
        return 1
    body = r.json()
    scenes = body.get("scenes") or []
    if len(scenes) < 1:
        print("No scenes in response", file=sys.stderr)
        return 1
    missing = [i for i, s in enumerate(scenes) if not (s.get("generated_image_path") or "").strip()]
    if missing:
        print("Missing generated_image_path for scenes:", missing, file=sys.stderr)
        return 1
    print("OK:", len(scenes), "scenes with stills; first:", scenes[0].get("generated_image_path"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
