from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore[assignment]
import numpy as np


@dataclass(frozen=True)
class ImageCategoryGuess:
    category: str
    confidence: float
    notes: str


def _clamp01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def _foreground_mask(img: Image.Image) -> np.ndarray:
    """
    Create a boolean foreground mask with a lightweight background estimation.

    Works best for common product shots with a mostly-uniform background.
    """
    im = img.convert("RGBA")
    arr = np.asarray(im, dtype=np.uint8)  # (H,W,4)
    rgb = arr[:, :, :3].astype(np.int16)
    alpha = arr[:, :, 3].astype(np.int16)

    h, w = rgb.shape[:2]
    # Sample corners to estimate background color (median is robust).
    sample = np.concatenate(
        [
            rgb[0: max(1, h // 20), 0: max(1, w // 20)].reshape(-1, 3),
            rgb[0: max(1, h // 20), -max(1, w // 20) :].reshape(-1, 3),
            rgb[-max(1, h // 20) :, 0: max(1, w // 20)].reshape(-1, 3),
            rgb[-max(1, h // 20) :, -max(1, w // 20) :].reshape(-1, 3),
        ],
        axis=0,
    )
    bg = np.median(sample, axis=0)  # (3,)

    # Distance from background in RGB space.
    diff = np.sqrt(np.sum((rgb - bg) ** 2, axis=2))  # (H,W)
    # Alpha helps for transparent PNG/WebP.
    mask = (diff >= 18.0) & (alpha >= 16)

    # Light cleanup: remove sparse noise by requiring local density.
    # Compute a coarse downsampled density map.
    block = 8
    hh = (h // block) * block
    ww = (w // block) * block
    if hh >= block and ww >= block:
        m = mask[:hh, :ww].reshape(hh // block, block, ww // block, block).mean(axis=(1, 3))
        keep_blocks = m >= 0.06
        mask2 = np.zeros_like(mask)
        mask2[:hh, :ww] = np.kron(keep_blocks, np.ones((block, block), dtype=bool))
        mask = mask & mask2
    return mask


def _bbox(mask: np.ndarray) -> tuple[int, int, int, int] | None:
    ys, xs = np.where(mask)
    if ys.size == 0 or xs.size == 0:
        return None
    y0, y1 = int(ys.min()), int(ys.max())
    x0, x1 = int(xs.min()), int(xs.max())
    return y0, x0, y1, x1


def _two_leg_score(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> float:
    """
    Pants often show a clear split into two vertical legs in the lower half.
    Returns 0..1 score for that pattern.
    """
    y0, x0, y1, x1 = bbox
    h = y1 - y0 + 1
    w = x1 - x0 + 1
    if h < 40 or w < 40:
        return 0.0
    # Focus on lower 60% where legs separate.
    y_start = y0 + int(h * 0.35)
    roi = mask[y_start : y1 + 1, x0 : x1 + 1]
    col = roi.mean(axis=0)  # 0..1
    if col.max() <= 0.02:
        return 0.0
    col = col / (col.max() + 1e-6)

    mid = w // 2
    left_max = float(col[:mid].max()) if mid > 3 else 0.0
    right_max = float(col[mid:].max()) if w - mid > 3 else 0.0
    center_min = float(col[max(0, mid - w // 12) : min(w, mid + w // 12)].min())

    # Two strong sides and a valley in the middle.
    peak_strength = min(left_max, right_max)
    valley = 1.0 - center_min
    score = peak_strength * valley
    return _clamp01(score)


def _vertical_mass_bottomness(mask: np.ndarray, bbox: tuple[int, int, int, int]) -> float:
    """Shoes are typically concentrated near the bottom of the bbox."""
    y0, x0, y1, x1 = bbox
    roi = mask[y0 : y1 + 1, x0 : x1 + 1]
    h = roi.shape[0]
    if h <= 5:
        return 0.0
    weights = np.arange(h, dtype=np.float64) / max(1.0, (h - 1))
    mass = roi.mean(axis=1)
    if mass.sum() <= 1e-6:
        return 0.0
    centroid = float((mass * weights).sum() / (mass.sum() + 1e-9))  # 0 top .. 1 bottom
    return _clamp01(centroid)


def infer_category_from_image(path: str | Path, filename_hint: str | None = None) -> ImageCategoryGuess:
    """
    Lightweight visual classifier (no heavy CV).

    Goal: avoid obvious mislabels (e.g., pants categorized as top).
    Uses foreground extraction + shape signals + filename hint.
    """
    if Image is None:
        # Pillow isn't available; fall back to filename + safe defaults instead of crashing the API.
        name = (filename_hint or "").lower()
        if any(t in name for t in ("pant", "pants", "jean", "trouser", "chino", "skirt")):
            return ImageCategoryGuess(category="bottom", confidence=0.7, notes="no_pillow_filename_token")
        if any(t in name for t in ("shoe", "sneaker", "boot", "loafer", "heel")):
            return ImageCategoryGuess(category="shoes", confidence=0.7, notes="no_pillow_filename_token")
        if any(t in name for t in ("coat", "jacket", "blazer", "parka")):
            return ImageCategoryGuess(category="outerwear", confidence=0.65, notes="no_pillow_filename_token")
        return ImageCategoryGuess(category="top", confidence=0.35, notes="no_pillow_default")

    try:
        p = Path(path)
        with Image.open(p) as img:
            w, h = img.size
            mask = _foreground_mask(img)
    except Exception:
        return ImageCategoryGuess(category="top", confidence=0.1, notes="image_open_failed")

    if w <= 0 or h <= 0:
        return ImageCategoryGuess(category="top", confidence=0.1, notes="bad_dimensions")

    ratio = h / w
    name = (filename_hint or "").lower()

    # Explicit filename tokens win (when present).
    if any(t in name for t in ("pant", "pants", "jean", "trouser", "chino", "skirt")):
        return ImageCategoryGuess(category="bottom", confidence=0.85, notes="filename_token")
    if any(t in name for t in ("shoe", "sneaker", "boot", "loafer", "heel")):
        return ImageCategoryGuess(category="shoes", confidence=0.85, notes="filename_token")
    if any(t in name for t in ("coat", "jacket", "blazer", "parka")):
        return ImageCategoryGuess(category="outerwear", confidence=0.8, notes="filename_token")

    bb = _bbox(mask)
    if bb is None:
        # If segmentation fails, fall back to global ratio.
        if ratio >= 1.35:
            return ImageCategoryGuess(category="bottom", confidence=0.45, notes=f"no_fg_ratio={ratio:.2f}")
        if ratio <= 0.85:
            return ImageCategoryGuess(category="shoes", confidence=0.45, notes=f"no_fg_ratio={ratio:.2f}")
        return ImageCategoryGuess(category="top", confidence=0.4, notes=f"no_fg_ratio={ratio:.2f}")

    y0, x0, y1, x1 = bb
    bb_h = y1 - y0 + 1
    bb_w = x1 - x0 + 1
    bb_ratio = bb_h / max(1, bb_w)

    fg_area = float(mask[y0 : y1 + 1, x0 : x1 + 1].mean())
    leg_score = _two_leg_score(mask, bb)
    bottomness = _vertical_mass_bottomness(mask, bb)

    # Classification rules
    # Pants/bottoms: taller bbox, moderate fg coverage, often two-leg pattern.
    # Pants can appear "wide" (two legs side-by-side) so bbox_ratio isn't always tall.
    # The two-leg pattern is the strongest signal.
    if leg_score >= 0.22 and bb_ratio >= 0.45:
        conf = _clamp01(0.55 + 0.45 * leg_score)
        return ImageCategoryGuess(category="bottom", confidence=conf, notes=f"two_leg={leg_score:.2f},bb_ratio={bb_ratio:.2f}")
    if bb_ratio >= 1.45 and fg_area >= 0.05:
        conf = _clamp01(0.55 + 0.15 * min(1.0, (bb_ratio - 1.45)))
        return ImageCategoryGuess(category="bottom", confidence=conf, notes=f"tall_bb_ratio={bb_ratio:.2f}")

    # Shoes: wide bbox and foreground mass near bottom.
    if bb_ratio <= 0.95 and bottomness >= 0.62:
        conf = _clamp01(0.5 + 0.4 * (bottomness - 0.62))
        return ImageCategoryGuess(category="shoes", confidence=conf, notes=f"bottomness={bottomness:.2f},bb_ratio={bb_ratio:.2f}")

    # Outerwear can also be tall but typically not two-leg; if tallish but broad, lean outerwear.
    if bb_ratio >= 1.25 and leg_score < 0.12 and fg_area >= 0.07:
        return ImageCategoryGuess(category="outerwear", confidence=0.55, notes=f"outerwear_shape bb_ratio={bb_ratio:.2f}")

    # Default: top.
    return ImageCategoryGuess(category="top", confidence=0.52, notes=f"default bb_ratio={bb_ratio:.2f},leg={leg_score:.2f}")

