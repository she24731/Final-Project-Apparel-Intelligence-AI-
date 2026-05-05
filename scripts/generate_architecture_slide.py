from __future__ import annotations

import math
from pathlib import Path


def _rounded_rect(draw, xy, r, fill, outline, width=2):
    # Pillow rounded_rectangle exists, but keep compatibility with older builds.
    try:
        draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)
        return
    except Exception:
        pass

    (x0, y0, x1, y1) = xy
    draw.rectangle([x0 + r, y0, x1 - r, y1], fill=fill, outline=None)
    draw.rectangle([x0, y0 + r, x1, y1 - r], fill=fill, outline=None)
    draw.pieslice([x0, y0, x0 + 2 * r, y0 + 2 * r], 180, 270, fill=fill)
    draw.pieslice([x1 - 2 * r, y0, x1, y0 + 2 * r], 270, 360, fill=fill)
    draw.pieslice([x0, y1 - 2 * r, x0 + 2 * r, y1], 90, 180, fill=fill)
    draw.pieslice([x1 - 2 * r, y1 - 2 * r, x1, y1], 0, 90, fill=fill)
    draw.rounded_rectangle(xy, radius=r, fill=None, outline=outline, width=width)


def _shadow(draw, xy, r, shadow_color, offset=(0, 8)):
    x0, y0, x1, y1 = xy
    ox, oy = offset
    _rounded_rect(draw, (x0 + ox, y0 + oy, x1 + ox, y1 + oy), r=r, fill=shadow_color, outline=None, width=0)


def _arrow(draw, a, b, color, width=4, head=14):
    ax, ay = a
    bx, by = b
    draw.line([ax, ay, bx, by], fill=color, width=width)
    ang = math.atan2(by - ay, bx - ax)
    hx = bx - head * math.cos(ang)
    hy = by - head * math.sin(ang)
    left = (hx + head * 0.55 * math.cos(ang + math.pi / 2), hy + head * 0.55 * math.sin(ang + math.pi / 2))
    right = (hx + head * 0.55 * math.cos(ang - math.pi / 2), hy + head * 0.55 * math.sin(ang - math.pi / 2))
    draw.polygon([(bx, by), left, right], fill=color)


def _center_text(draw, box, text, font, color):
    x0, y0, x1, y1 = box
    w = x1 - x0
    h = y1 - y0
    tw, th = draw.textbbox((0, 0), text, font=font)[2:]
    draw.text((x0 + (w - tw) / 2, y0 + (h - th) / 2), text, font=font, fill=color)


def _badge(draw, xy, text, font, fill, outline, text_color):
    x0, y0, x1, y1 = xy
    r = (y1 - y0) // 2
    _rounded_rect(draw, xy, r=r, fill=fill, outline=outline, width=2)
    _center_text(draw, xy, text, font, text_color)


def generate_png(out_png: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    W, H = 1920, 1080
    img = Image.new("RGB", (W, H), "#F6F3EE")
    draw = ImageDraw.Draw(img)

    def font(size: int, bold: bool = False):
        # Best-effort: use system fonts if present; fall back to default.
        candidates = []
        if bold:
            candidates += [
                "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
                "/System/Library/Fonts/HelveticaNeue.ttc",
            ]
        else:
            candidates += [
                "/System/Library/Fonts/Supplemental/Arial.ttf",
                "/System/Library/Fonts/HelveticaNeue.ttc",
            ]
        for p in candidates:
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    title_f = font(44, bold=True)
    h_f = font(26, bold=True)
    body_f = font(22, bold=False)
    badge_f = font(18, bold=True)
    small_f = font(18, bold=False)

    # Palette
    ink = "#141414"
    muted = "#5A5A5A"
    line = "#E4DDD2"
    shadow = "#00000022"

    front_fill = "#EAF2FF"
    front_line = "#5B8CFF"
    back_fill = "#FFF1DA"
    back_line = "#C89B3C"
    opt_fill = "#F1F1F1"
    opt_line = "#8A8A8A"

    # Header
    draw.text((60, 42), "Apparel Intelligence (AI) — Tool Architecture", font=title_f, fill=ink)
    draw.text((60, 96), "Frontend vs Backend + optional AI + local retrieval + storage", font=body_f, fill=muted)

    # Columns geometry
    top = 160
    gap_x = 44
    col_w = (W - 2 * 60 - 2 * gap_x) // 3
    x1 = 60
    x2 = x1 + col_w + gap_x
    x3 = x2 + col_w + gap_x

    # Left: user/browser
    user_box = (x1, top + 110, x1 + col_w, top + 310)
    _shadow(draw, user_box, r=24, shadow_color=shadow)
    _rounded_rect(draw, user_box, r=24, fill="#FFFFFF", outline=line, width=2)
    draw.text((user_box[0] + 26, user_box[1] + 24), "User / Browser", font=h_f, fill=ink)
    draw.text((user_box[0] + 26, user_box[1] + 70), "Chrome / Safari\nDrag & drop images\nChat + navigation", font=body_f, fill=muted)

    # Middle: frontend + backend (stacked)
    fe_box = (x2, top, x2 + col_w, top + 360)
    be_box = (x2, top + 410, x2 + col_w, top + 860)
    for box, fill, outline, title in [
        (fe_box, front_fill, front_line, "Frontend (React + Vite)"),
        (be_box, back_fill, back_line, "Backend (FastAPI)"),
    ]:
        _shadow(draw, box, r=28, shadow_color=shadow)
        _rounded_rect(draw, box, r=28, fill=fill, outline=outline, width=3)
        draw.text((box[0] + 26, box[1] + 22), title, font=h_f, fill=ink)

    # Frontend badges
    fe_badges = ["React", "TypeScript", "Vite", "Tailwind CSS", "PostCSS", "Autoprefixer"]
    bx, by = fe_box[0] + 24, fe_box[1] + 78
    for i, t in enumerate(fe_badges):
        w = 160 if len(t) <= 10 else 190
        _badge(draw, (bx, by, bx + w, by + 40), t, badge_f, fill="#FFFFFF", outline="#B9D0FF", text_color=ink)
        bx += w + 12
        if bx > fe_box[2] - 220:
            bx = fe_box[0] + 24
            by += 52

    draw.text((fe_box[0] + 26, fe_box[1] + 230), "Feature: Chat Widget + drag/drop\nSends JSON + multipart to backend", font=body_f, fill=muted)

    # Backend badges
    be_badges = ["FastAPI", "Uvicorn", "Pydantic", "pydantic-settings", "python-multipart", "httpx"]
    bx, by = be_box[0] + 24, be_box[1] + 78
    for i, t in enumerate(be_badges):
        w = 190 if len(t) > 10 else 150
        _badge(draw, (bx, by, bx + w, by + 40), t, badge_f, fill="#FFFFFF", outline="#F0C87A", text_color=ink)
        bx += w + 12
        if bx > be_box[2] - 240:
            bx = be_box[0] + 24
            by += 52

    draw.text(
        (be_box[0] + 26, be_box[1] + 260),
        "Endpoints: /assistant/turn (JSON)\n/assistant/turn-multipart (uploads)\n/garments, /recommend-outfit, /generate-video",
        font=body_f,
        fill=muted,
    )

    # Right: optional components stacked
    llm_box = (x3, top, x3 + col_w, top + 240)
    rag_box = (x3, top + 290, x3 + col_w, top + 540)
    store_box = (x3, top + 590, x3 + col_w, top + 860)
    for box, title, badges in [
        (llm_box, "LLM / Agents (optional)", ["pydantic-ai", "google-genai (Gemini)", "Deterministic fallback"]),
        (rag_box, "Local Retrieval (RAG-lite)", ["Deterministic embeddings", "Local vector store", "NumPy cosine similarity"]),
        (store_box, "Local Storage", ["uploads/ (images)", "data/ (wardrobe store)", "generated_media/ (video)"]),
    ]:
        _shadow(draw, box, r=24, shadow_color=shadow)
        _rounded_rect(draw, box, r=24, fill=opt_fill, outline=opt_line, width=2)
        draw.text((box[0] + 22, box[1] + 20), title, font=h_f, fill=ink)
        y = box[1] + 70
        for b in badges:
            draw.text((box[0] + 22, y), f"• {b}", font=body_f, fill=muted)
            y += 38

    # Arrows
    _arrow(draw, (user_box[2], (user_box[1] + user_box[3]) // 2), (fe_box[0], fe_box[1] + 120), color="#3B82F6", width=5)
    draw.text((x1 + col_w + 14, top + 240), "HTTP", font=small_f, fill=muted)

    _arrow(draw, (fe_box[2], fe_box[1] + 170), (be_box[0], be_box[1] + 170), color="#C89B3C", width=5)
    draw.text((x2 + col_w + 14, top + 310), "REST API / JSON + multipart", font=small_f, fill=muted)

    # backend -> optional
    _arrow(draw, (be_box[2], be_box[1] + 140), (llm_box[0], llm_box[1] + 120), color="#8A8A8A", width=4)
    draw.text((x3 - 240, top + 530), "when enabled", font=small_f, fill=muted)

    _arrow(draw, (be_box[2], be_box[1] + 250), (rag_box[0], rag_box[1] + 120), color="#8A8A8A", width=4)
    _arrow(draw, (rag_box[0], rag_box[1] + 180), (be_box[2], be_box[1] + 330), color="#8A8A8A", width=3)
    draw.text((x3 - 260, top + 650), "context + style KB", font=small_f, fill=muted)

    _arrow(draw, (be_box[2], be_box[1] + 400), (store_box[0], store_box[1] + 140), color="#8A8A8A", width=4)
    draw.text((x3 - 210, top + 820), "save uploads + media", font=small_f, fill=muted)

    # Legend footer
    footer_y = H - 96
    _badge(draw, (60, footer_y, 220, footer_y + 44), "Frontend tools", badge_f, fill=front_fill, outline=front_line, text_color=ink)
    _badge(draw, (240, footer_y, 400, footer_y + 44), "Backend tools", badge_f, fill=back_fill, outline=back_line, text_color=ink)
    _badge(draw, (420, footer_y, 600, footer_y + 44), "Optional components", badge_f, fill=opt_fill, outline=opt_line, text_color=ink)
    draw.text((640, footer_y + 10), "Single-machine demo: local storage + deterministic fallbacks", font=small_f, fill=muted)

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png, format="PNG", optimize=True)


def generate_pptx(diagram_png: Path, out_pptx: Path) -> None:
    from pptx import Presentation
    from pptx.util import Inches

    prs = Presentation()
    # Set 16:9
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)

    slide = prs.slides.add_slide(prs.slide_layouts[6])  # blank
    # Add image full-bleed with small margins
    margin = Inches(0.25)
    slide.shapes.add_picture(
        str(diagram_png),
        margin,
        margin,
        width=prs.slide_width - 2 * margin,
        height=prs.slide_height - 2 * margin,
    )

    out_pptx.parent.mkdir(parents=True, exist_ok=True)
    prs.save(str(out_pptx))


def main() -> None:
    repo = Path(__file__).resolve().parents[1]
    out_dir = repo / "artifacts"
    png = out_dir / "apparel-intelligence-architecture-tools.png"
    pptx = out_dir / "apparel-intelligence-architecture-tools.pptx"
    generate_png(png)
    generate_pptx(png, pptx)
    print(f"Wrote: {png}")
    print(f"Wrote: {pptx}")


if __name__ == "__main__":
    main()

