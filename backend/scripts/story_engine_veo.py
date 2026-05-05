from __future__ import annotations

import argparse
import base64
import json
import os
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import ffmpeg  # type: ignore
from google import genai  # type: ignore
from google.genai import types  # type: ignore


STYLE_MODIFIER = (
    "Hollywood blockbuster montage style, 24 fps, cinematic lighting, dynamic tracking shot, "
    "sharp focus, 35mm lens, high-action energy with quick cuts."
)


@dataclass(frozen=True)
class Anchors:
    face_path: Path
    garment_paths: list[Path]


@dataclass(frozen=True)
class SceneMemory:
    """State that persists across the autonomous loop."""

    previous_scene_description: str | None = None
    previous_final_frame_path: Path | None = None
    garment_a_path: Path | None = None
    garment_b_path: Path | None = None


@dataclass(frozen=True)
class VeoPayload:
    """
    Canonical payload for this story engine.

    Matches the requested structure:
    - start_frame_b64: null for scene 1; base64(last frame) for scene 2+
    - reference_images_b64: [Face, Garment_A, (Garment_B or start_frame)] for scene 1, and
      [Face, Garment_A] for scene 2+ (while start_frame carries continuity).
    """

    scene_index: int
    start_frame_path: Path | None
    reference_image_paths: list[Path]
    start_frame_b64: str | None
    reference_images_b64: list[str]


def _read_bytes(p: Path) -> bytes:
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(str(p))
    return p.read_bytes()


def _load_dotenv_if_present(*, env_path: Path) -> None:
    """
    Minimal .env loader (no external dependency).

    This script primarily uses environment variables, but in this repo the backend key is commonly
    stored in `backend/.env`. If GEMINI_API_KEY isn't set, we read it from that file.
    """
    if os.getenv("GEMINI_API_KEY", "").strip():
        return
    try:
        if not env_path.exists() or not env_path.is_file():
            return
        for line in env_path.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if not s or s.startswith("#") or "=" not in s:
                continue
            k, v = s.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k == "GEMINI_API_KEY" and v:
                os.environ["GEMINI_API_KEY"] = v
                return
    except Exception:
        return


def _mime_for_path(p: Path) -> str:
    ext = p.suffix.lower()
    if ext in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if ext == ".webp":
        return "image/webp"
    return "image/png"


def _image_from_path(p: Path) -> types.Image:
    """
    Construct a google-genai Image with an explicit mime_type for SDK compatibility.
    """
    return types.Image.from_file(location=str(p), mime_type=_mime_for_path(p))


def load_anchors(*, face_anchor: Path, garments_dir: Path) -> Anchors:
    """
    Load 1 face anchor image + a folder of garment anchors.

    The user provides:
    - face_anchor: path to a single image
    - garments_dir: directory containing multiple garment/outfit images
    """
    face_anchor = face_anchor.expanduser().resolve()
    garments_dir = garments_dir.expanduser().resolve()

    if not face_anchor.exists():
        raise FileNotFoundError(f"Face anchor not found: {face_anchor}")
    if not garments_dir.exists() or not garments_dir.is_dir():
        raise FileNotFoundError(f"Garments directory not found: {garments_dir}")

    garment_paths = sorted(
        [p for p in garments_dir.iterdir() if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}]
    )
    if len(garment_paths) < 2:
        raise ValueError("Need at least 2 garment anchor images in the garments folder.")

    return Anchors(face_path=face_anchor, garment_paths=garment_paths)


def _parse_json_object(text: str) -> dict[str, Any]:
    m = re.search(r"\{[\s\S]*\}", text or "")
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _is_transient_api_error(exc: Exception) -> bool:
    """
    Best-effort classification of transient API errors (rate limit / temporary overload).
    google-genai raises typed exceptions, but we avoid importing internals and just inspect messages.
    """
    msg = str(exc).lower()
    return any(k in msg for k in ("503", "unavailable", "429", "resource_exhausted", "too many requests", "rate"))


def _with_retries(fn, *, what: str, max_attempts: int = 5, base_sleep_s: float = 1.2):
    last: Exception | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except Exception as e:
            last = e
            if attempt >= max_attempts or not _is_transient_api_error(e):
                raise
            # Exponential backoff + small jitter.
            sleep_s = base_sleep_s * (2 ** (attempt - 1)) + (0.15 * attempt)
            time.sleep(min(12.0, sleep_s))
    if last is not None:
        raise last
    raise RuntimeError(f"Unknown failure in {what}")


def call_writer_llm(
    *,
    client: genai.Client,
    model: str,
    core_premise: str,
    previous_scene_description: str | None,
) -> str:
    """
    Step A (The Writer):
    Ask a text LLM for the next logical plot beat in exactly ONE short sentence.
    Must return strict JSON: {"plot": "..."}.
    """
    prev = (previous_scene_description or "").strip()
    prompt = (
        "Based on the premise and what just happened, write the next logical scene action in exactly one short sentence.\n"
        "Return ONLY valid JSON: {\"plot\": \"your sentence\"}.\n\n"
        f"CORE_PREMISE:\n{core_premise.strip()}\n\n"
        f"PREVIOUS_SCENE_DESCRIPTION:\n{prev if prev else '(none)'}\n"
    )
    resp = _with_retries(
        lambda: client.models.generate_content(model=model, contents=prompt),
        what="writer_llm.generate_content",
    )
    payload = _parse_json_object(getattr(resp, "text", "") or "")
    plot = str(payload.get("plot", "") or "").strip()
    plot = re.sub(r"\s+", " ", plot)
    if len(plot) < 6:
        raise ValueError(f"Writer LLM returned invalid plot JSON. Raw response: {getattr(resp, 'text', '')!r}")
    return plot


def _b64_image(p: Path) -> str:
    """
    Base64 helper for debugging / logging.
    The Veo SDK call below uses types.Image.from_bytes, but we still keep this for visibility
    because your spec explicitly says 'Images (Max 3, Base64)'.
    """
    return base64.b64encode(_read_bytes(p)).decode("utf-8")


def build_veo_inputs(
    *,
    anchors: Anchors,
    rng: random.Random,
    scene_index: int,
    memory: SceneMemory,
) -> VeoPayload:
    """
    Step B (The Payload: FIXED LOGIC)

    Scene 1:
      - start_frame: null
      - referenceImages: [Face_Anchor, Garment_A, Garment_B]

    Scene 2+:
      - start_frame: base64(final frame of previous scene)
      - referenceImages: [Face_Anchor, Garment_A]
    """
    face = anchors.face_path

    def _pick_other_garment(exclude: Path) -> Path:
        choices = [p for p in anchors.garment_paths if p != exclude]
        return rng.choice(choices) if choices else exclude

    # Pick (or reuse) the "Garment_A" anchor for continuity.
    garment_a = memory.garment_a_path or rng.choice(anchors.garment_paths)

    if scene_index == 0:
        garment_b = memory.garment_b_path or _pick_other_garment(garment_a)
        ref_paths = [face, garment_a, garment_b]
        return VeoPayload(
            scene_index=scene_index,
            start_frame_path=None,
            reference_image_paths=ref_paths,
            start_frame_b64=None,
            reference_images_b64=[_b64_image(p) for p in ref_paths],
        )

    # Scene 2+: start_frame is previous final frame (required for chaining).
    if memory.previous_final_frame_path is None:
        # Degrade gracefully: if missing, treat as scene 1 style (no start_frame).
        garment_b = memory.garment_b_path or _pick_other_garment(garment_a)
        ref_paths = [face, garment_a, garment_b]
        return VeoPayload(
            scene_index=scene_index,
            start_frame_path=None,
            reference_image_paths=ref_paths,
            start_frame_b64=None,
            reference_images_b64=[_b64_image(p) for p in ref_paths],
        )

    start_frame = memory.previous_final_frame_path
    ref_paths = [face, garment_a]
    return VeoPayload(
        scene_index=scene_index,
        start_frame_path=start_frame,
        reference_image_paths=ref_paths,
        start_frame_b64=_b64_image(start_frame),
        reference_images_b64=[_b64_image(p) for p in ref_paths],
    )


def build_veo_prompt(
    *,
    plot: str,
    has_image3: bool,
) -> str:
    """
    Text Prompt Construction (v4):
    prompt = [STYLE_MODIFIER] + [Scene Plot] + strict anchor + camera motion instruction.
    """
    plot_s = re.sub(r"\s+", " ", (plot or "").strip())
    garments = "Image 2 (and Image 3 if applicable)" if has_image3 else "Image 2"
    return (
        f"{STYLE_MODIFIER} {plot_s}\n"
        "Ensure the protagonist has the exact facial features of Image 1 and wears the garments from "
        f"{garments}. "
        "The camera must maintain a dynamic tracking motion following the subject."
    ).strip()


def call_veo(
    *,
    client: genai.Client,
    model: str,
    prompt: str,
    payload: VeoPayload,
    out_mp4: Path,
    duration_seconds: int = 8,
) -> None:
    """
    Send payload to Veo, await MP4, and save it to out_mp4.

    Error handling:
    - Surfaces API errors with messages
    - Verifies the MP4 exists + is non-empty
    """
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    cfg = types.GenerateVideosConfig(number_of_videos=1, duration_seconds=int(duration_seconds), aspect_ratio="9:16")

    def _start_op():
        """
        Start the Veo operation.

        IMPORTANT:
        We always construct the canonical payload (start_frame + referenceImages) as requested,
        but the current google-genai SDK only supports a single `image=` input for generate_videos().

        Mapping (best-effort):
        - Scene 1 (start_frame=null): send no image; prompt-only generation (allowed by API).
        - Scene 2+ (start_frame=previous frame): send `image=start_frame` to seed continuity.

        Reference images are still part of the canonical payload (and are base64-encoded in-memory),
        but cannot all be passed through this SDK call today. This keeps the code forward-compatible:
        when the SDK/API supports multiple reference images, this function is the only place you update.
        """
        if payload.start_frame_path is None:
            return client.models.generate_videos(model=model, prompt=prompt, image=None, config=cfg)
        return client.models.generate_videos(model=model, prompt=prompt, image=_image_from_path(payload.start_frame_path), config=cfg)

    try:
        op = _with_retries(_start_op, what="veo.generate_videos")
    except Exception as e:
        raise RuntimeError(f"Veo request failed: {e!s}") from e

    while not op.done:
        time.sleep(3)
        op = client.operations.get(op)

    if getattr(op, "error", None):
        err_obj = getattr(op, "error", None)
        msg = None
        try:
            msg = getattr(err_obj, "message", None) or str(err_obj)
        except Exception:
            msg = "unknown error"
        raise RuntimeError(f"Veo operation error: {msg}")

    video = op.response.generated_videos[0].video
    wrote = False
    try:
        if hasattr(video, "download"):
            video.download(str(out_mp4))
            wrote = True
        elif hasattr(video, "video_bytes") and getattr(video, "video_bytes", None):
            out_mp4.write_bytes(getattr(video, "video_bytes"))
            wrote = True
        elif hasattr(video, "data") and getattr(video, "data", None):
            out_mp4.write_bytes(getattr(video, "data"))
            wrote = True
        elif getattr(video, "uri", None):
            # Preferred: use authenticated file download through the SDK.
            try:
                data = client.files.download(file=video)
                if data:
                    out_mp4.write_bytes(data)
                    wrote = True
            except Exception:
                wrote = False
    except Exception as e:
        raise RuntimeError(f"Failed to write Veo MP4: {e!s}") from e

    if not wrote or not out_mp4.exists() or out_mp4.stat().st_size == 0:
        # Persist minimal debug context to help diagnose SDK response shapes.
        try:
            dbg = {
                "video_has_download": bool(hasattr(video, "download")),
                "video_uri": getattr(video, "uri", None),
                "video_mime_type": getattr(video, "mime_type", None),
                "video_has_video_bytes": bool(getattr(video, "video_bytes", None)),
                "video_has_data": bool(getattr(video, "data", None)),
                "op_response_repr": repr(getattr(op, "response", None)),
            }
            out_mp4.with_suffix(".debug.json").write_text(json.dumps(dbg, indent=2), encoding="utf-8")
        except Exception:
            pass
        raise RuntimeError("Veo returned empty MP4 bytes (see .debug.json next to output).")


def extract_final_frame(*, mp4_path: Path, out_png: Path) -> Path:
    """
    Extract the final frame of the MP4 (used as Image 3 from Scene 2 onwards).
    Implementation: probe duration, then seek to duration-0.06s and grab 1 frame.
    """
    out_png.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = ffmpeg.probe(str(mp4_path))
        dur_s = float(info.get("format", {}).get("duration", "0") or 0.0)
    except Exception:
        dur_s = 0.0

    # Fallback timestamp if probe fails
    ts = max(0.0, (dur_s - 0.06) if dur_s > 0.2 else 0.0)

    try:
        (
            ffmpeg.input(str(mp4_path), ss=ts)
            .output(str(out_png), vframes=1, format="image2", vcodec="png")
            .overwrite_output()
            .run(quiet=True)
        )
    except Exception as e:
        raise RuntimeError(f"Failed to extract final frame: {e!s}") from e

    if not out_png.exists() or out_png.stat().st_size == 0:
        raise RuntimeError("Final frame extraction produced empty PNG.")
    return out_png


def call_vision_language_description(
    *,
    client: genai.Client,
    model: str,
    core_premise: str,
    frame_path: Path,
) -> str:
    """
    Analyze & Remember:
    Describe the visual scene from the extracted final frame.
    This becomes 'Previous Scene Description' for the next loop.
    """
    # Use an explicit Part with inline bytes; this avoids SDK variants that require a file URI.
    img_part = types.Part.from_bytes(data=_read_bytes(frame_path), mime_type=_mime_for_path(frame_path))
    prompt = (
        "You are summarizing a video frame for story continuity.\n"
        "Write one concise sentence describing what we SEE: subject, outfit, setting, lighting, action.\n"
        "Tie it to the CORE PREMISE vibe. No brands, no character names.\n"
        "Return STRICT JSON: {\"description\": \"...\"}.\n\n"
        f"CORE PREMISE:\n{core_premise.strip()}\n"
    )
    resp = _with_retries(
        lambda: client.models.generate_content(model=model, contents=[prompt, img_part]),
        what="vision.generate_content",
    )
    payload = _parse_json_object(getattr(resp, "text", "") or "")
    desc = str(payload.get("description", "") or "").strip()
    desc = re.sub(r"\s+", " ", desc)
    if len(desc) < 10:
        raise ValueError(f"Vision-language returned invalid JSON description. Raw: {getattr(resp, 'text', '')!r}")
    return desc


def concat_mp4s(*, mp4_paths: list[Path], out_mp4: Path, transition: str = "hard_cut", dissolve_s: float = 0.25) -> None:
    """
    Post-processing: concatenate all MP4s into a single movie.

    - transition="hard_cut": simple concat (montage cut)
    - transition="dissolve": xfade dissolve between clips (montage dissolve)
    """
    if not mp4_paths:
        raise ValueError("No MP4s to concatenate.")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    if transition == "dissolve" and len(mp4_paths) >= 2:
        # Build an xfade chain. We re-encode for filter_complex.
        streams = [ffmpeg.input(str(p)) for p in mp4_paths]
        # Compute offsets using probe durations.
        durs: list[float] = []
        for p in mp4_paths:
            try:
                info = ffmpeg.probe(str(p))
                d = float(info.get("format", {}).get("duration", "0") or 0.0)
            except Exception:
                d = 0.0
            durs.append(max(0.0, d))

        # xfade offset is cumulative_duration - dissolve_s
        v = streams[0].video
        acc = durs[0]
        for i in range(1, len(streams)):
            off = max(0.0, acc - float(dissolve_s))
            v = ffmpeg.filter([v, streams[i].video], "xfade", transition="fade", duration=float(dissolve_s), offset=off)
            acc += durs[i]

        try:
            (
                ffmpeg.output(v, str(out_mp4), vcodec="libx264", pix_fmt="yuv420p", r=24, movflags="+faststart")
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to concatenate MP4s with dissolve: {e!s}") from e
        if not out_mp4.exists() or out_mp4.stat().st_size == 0:
            raise RuntimeError("Concatenation produced empty MP4.")
        return

    # Create a concat list file.
    list_file = out_mp4.with_suffix(".concat.txt")
    lines = []
    for p in mp4_paths:
        if not p.exists():
            raise FileNotFoundError(str(p))
        # ffmpeg concat demuxer expects: file '/path'
        lines.append(f"file '{p.as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

    try:
        (
            ffmpeg.input(str(list_file), format="concat", safe=0)
            .output(str(out_mp4), c="copy", movflags="+faststart")
            .overwrite_output()
            .run(quiet=True)
        )
    except Exception as e:
        raise RuntimeError(f"Failed to concatenate MP4s: {e!s}") from e

    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise RuntimeError("Concatenation produced empty MP4.")


def _trim_mid_slice(*, clip_path: Path, out_path: Path, slice_s: float, fps: int = 24) -> Path:
    """
    Take a short slice from the middle of a clip to create a fast-paced montage cut.
    We re-encode to ensure consistent timebase/fps for concat/xfade.
    """
    out_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        info = ffmpeg.probe(str(clip_path))
        dur_s = float(info.get("format", {}).get("duration", "0") or 0.0)
    except Exception:
        dur_s = 0.0

    # Choose a slice centered around the middle. Clamp to valid range.
    slice_s = float(max(0.5, min(6.0, slice_s)))
    if dur_s <= 0.01:
        start = 0.0
    else:
        mid = dur_s * 0.5
        start = max(0.0, mid - (slice_s * 0.5))
        # ensure we don't run past end
        start = max(0.0, min(start, max(0.0, dur_s - slice_s - 0.02)))

    try:
        (
            ffmpeg.input(str(clip_path), ss=start)
            .output(
                str(out_path),
                t=slice_s,
                vcodec="libx264",
                pix_fmt="yuv420p",
                r=fps,
                preset="veryfast",
                crf=20,
                movflags="+faststart",
                an=None,
            )
            .overwrite_output()
            .run(quiet=True)
        )
    except Exception as e:
        raise RuntimeError(f"Failed to trim montage slice: {e!s}") from e

    if not out_path.exists() or out_path.stat().st_size == 0:
        raise RuntimeError("Trim produced empty MP4.")
    return out_path


def montage_concat_mp4s(
    *,
    mp4_paths: list[Path],
    out_mp4: Path,
    slice_s: float = 2.0,
    transition: str = "hard_cut",
    xfade_s: float = 0.2,
    fps: int = 24,
) -> None:
    """
    Fast-paced blockbuster montage:
    - Trim each clip to a short mid-action slice (2–3s recommended)
    - Concatenate with hard cuts or a very fast crossfade (0.2s)
    """
    if not mp4_paths:
        raise ValueError("No MP4s to montage.")
    out_mp4.parent.mkdir(parents=True, exist_ok=True)

    tmp_dir = out_mp4.parent / "_montage_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    trimmed: list[Path] = []
    for i, p in enumerate(mp4_paths):
        trimmed_path = tmp_dir / f"slice_{i+1:02d}.mp4"
        trimmed.append(_trim_mid_slice(clip_path=p, out_path=trimmed_path, slice_s=slice_s, fps=fps))

    if transition == "dissolve" and len(trimmed) >= 2:
        # xfade chain (fast 0.2s) for trailer pacing
        streams = [ffmpeg.input(str(p)) for p in trimmed]
        durs = [float(max(0.0, slice_s)) for _ in trimmed]

        v = streams[0].video
        acc = durs[0]
        for i in range(1, len(streams)):
            off = max(0.0, acc - float(xfade_s))
            v = ffmpeg.filter([v, streams[i].video], "xfade", transition="fade", duration=float(xfade_s), offset=off)
            acc += durs[i]

        try:
            (
                ffmpeg.output(v, str(out_mp4), vcodec="libx264", pix_fmt="yuv420p", r=fps, movflags="+faststart")
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to montage-concat with dissolve: {e!s}") from e
    else:
        # Hard cut montage via concat demuxer
        list_file = out_mp4.with_suffix(".montage.concat.txt")
        list_file.write_text("\n".join([f"file '{p.as_posix()}'" for p in trimmed]) + "\n", encoding="utf-8")
        try:
            (
                ffmpeg.input(str(list_file), format="concat", safe=0)
                .output(str(out_mp4), c="copy", movflags="+faststart")
                .overwrite_output()
                .run(quiet=True)
            )
        except Exception:
            # If stream copy fails (codec/timebase mismatch), re-encode as fallback.
            try:
                (
                    ffmpeg.input(str(list_file), format="concat", safe=0)
                    .output(str(out_mp4), vcodec="libx264", pix_fmt="yuv420p", r=fps, preset="veryfast", crf=20, movflags="+faststart")
                    .overwrite_output()
                    .run(quiet=True)
                )
            except Exception as e:
                raise RuntimeError(f"Failed to montage-concat with hard cuts: {e!s}") from e

    if not out_mp4.exists() or out_mp4.stat().st_size == 0:
        raise RuntimeError("Montage concatenation produced empty MP4.")


def main() -> int:
    ap = argparse.ArgumentParser(description="Autonomous Veo Story Engine (face+garments+memory loop).")
    ap.add_argument("--face", required=True, help="Path to face anchor image")
    ap.add_argument("--garments", required=True, help="Directory containing garment anchor images")
    ap.add_argument("--premise", required=True, help="Core premise text, e.g., 'A cyberpunk detective hunts a hacker'")
    ap.add_argument("--loops", type=int, default=4, help="Number of autonomous scenes/clips to generate")
    ap.add_argument("--out", default="story_engine_out", help="Output directory")
    ap.add_argument("--seed", default="42", help="RNG seed for garment sampling (string)")
    ap.add_argument("--writer-model", default="gemini-2.5-flash", help="Text model for the Writer step")
    ap.add_argument("--vision-model", default="gemini-2.5-flash", help="Vision-language model for frame description")
    ap.add_argument("--veo-model", default="veo-2.0-generate-001", help="Veo video model name")
    ap.add_argument("--clip-seconds", type=int, default=8, help="Per-clip duration (Veo often enforces 4–8s)")
    ap.add_argument("--transition", default="hard_cut", choices=["hard_cut", "dissolve"], help="Clip transition style")
    ap.add_argument("--montage-slice-seconds", type=float, default=2.0, help="Trim each clip to this slice length (mid-clip)")
    args = ap.parse_args()

    # If the user didn't export GEMINI_API_KEY, load it from backend/.env in this repo.
    # This keeps the script runnable in the same environment as the FastAPI backend.
    _load_dotenv_if_present(env_path=Path(__file__).resolve().parents[1] / ".env")

    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("Missing GEMINI_API_KEY in environment.")

    anchors = load_anchors(face_anchor=Path(args.face), garments_dir=Path(args.garments))
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = random.Random(int.from_bytes(args.seed.encode("utf-8"), "little") % (2**32))
    client = genai.Client(api_key=api_key)

    memory = SceneMemory(previous_scene_description=None, previous_final_frame_path=None, garment_a_path=None, garment_b_path=None)
    clips: list[Path] = []

    core_premise = str(args.premise).strip()
    loops = max(1, int(args.loops))

    for i in range(loops):
        plot = call_writer_llm(
            client=client,
            model=str(args.writer_model),
            core_premise=core_premise,
            previous_scene_description=memory.previous_scene_description,
        )

        payload = build_veo_inputs(anchors=anchors, rng=rng, scene_index=i, memory=memory)
        prompt = build_veo_prompt(plot=plot, has_image3=(len(payload.reference_image_paths) >= 3))

        clip_path = out_dir / f"scene_{i + 1:02d}.mp4"
        call_veo(
            client=client,
            model=str(args.veo_model),
            prompt=prompt,
            payload=payload,
            out_mp4=clip_path,
            duration_seconds=int(args.clip_seconds),
        )
        clips.append(clip_path)

        frame_path = out_dir / f"scene_{i + 1:02d}_final.png"
        extract_final_frame(mp4_path=clip_path, out_png=frame_path)

        desc = call_vision_language_description(
            client=client,
            model=str(args.vision_model),
            core_premise=core_premise,
            frame_path=frame_path,
        )

        # Remember: previous final frame drives start_frame for the next scene.
        # Also lock garment A/B after scene 1 for continuity.
        memory = SceneMemory(
            previous_scene_description=desc,
            previous_final_frame_path=frame_path,
            garment_a_path=payload.reference_image_paths[1] if len(payload.reference_image_paths) >= 2 else memory.garment_a_path,
            garment_b_path=payload.reference_image_paths[2] if len(payload.reference_image_paths) >= 3 else memory.garment_b_path,
        )

    final_mp4 = out_dir / "movie.mp4"
    # Fast-paced montage output: trim each clip to a short mid-action slice, then quick-cut / fast-dissolve.
    montage_concat_mp4s(
        mp4_paths=clips,
        out_mp4=final_mp4,
        slice_s=float(args.montage_slice_seconds),
        transition="dissolve" if str(args.transition) == "dissolve" else "hard_cut",
        xfade_s=0.2,
        fps=24,
    )
    print(str(final_mp4))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

