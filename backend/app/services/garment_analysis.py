from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]

import numpy as np

from app.services.image_category import infer_category_from_image


@dataclass(frozen=True)
class GarmentAnalysis:
    """
    Lightweight structured data for anchor images.

    This is intentionally heuristic/cheap (no heavy CV), but stable + useful as conditioning context.
    """

    path: str
    filename: str
    category: str
    category_confidence: float
    dominant_rgb: tuple[int, int, int] | None
    dominant_color_name: str | None
    aspect_ratio: float | None
    notes: str

    def to_dict(self) -> dict:
        return {
            "path": self.path,
            "filename": self.filename,
            "category": self.category,
            "category_confidence": float(self.category_confidence),
            "dominant_rgb": list(self.dominant_rgb) if self.dominant_rgb else None,
            "dominant_color_name": self.dominant_color_name,
            "aspect_ratio": float(self.aspect_ratio) if self.aspect_ratio is not None else None,
            "notes": self.notes,
        }


def _color_name(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    # Very small palette: good enough for prompts.
    if max(r, g, b) < 60:
        return "black"
    if min(r, g, b) > 195:
        return "white"
    if abs(r - g) < 18 and abs(g - b) < 18:
        return "gray"
    if r > g + 35 and r > b + 35:
        return "red"
    if g > r + 35 and g > b + 35:
        return "green"
    if b > r + 35 and b > g + 35:
        return "blue"
    if r > 150 and g > 120 and b < 110:
        return "beige"
    if r > 120 and g > 90 and b < 80:
        return "brown"
    return "neutral"


def _dominant_rgb(p: Path) -> tuple[int, int, int] | None:
    if Image is None:
        return None
    try:
        with Image.open(p) as im:
            im = im.convert("RGB")
            # Downsample for speed.
            im = im.resize((96, 96))
            arr = np.asarray(im, dtype=np.float32).reshape(-1, 3)
            if arr.size == 0:
                return None
            # Robust “dominant”: median of pixels.
            med = np.median(arr, axis=0)
            rgb = (int(med[0]), int(med[1]), int(med[2]))
            return rgb
    except Exception:
        return None


def analyze_anchor_image(*, local_path: Path, rel_path: str, filename_hint: str | None = None) -> GarmentAnalysis:
    fn = filename_hint or local_path.name
    guess = infer_category_from_image(local_path, filename_hint=fn)
    rgb = _dominant_rgb(local_path)
    aspect = None
    if Image is not None:
        try:
            with Image.open(local_path) as im:
                w, h = im.size
                if w and h:
                    aspect = float(h) / float(w)
        except Exception:
            aspect = None
    return GarmentAnalysis(
        path=rel_path,
        filename=fn,
        category=guess.category,
        category_confidence=float(guess.confidence),
        dominant_rgb=rgb,
        dominant_color_name=_color_name(rgb) if rgb else None,
        aspect_ratio=aspect,
        notes=guess.notes,
    )

