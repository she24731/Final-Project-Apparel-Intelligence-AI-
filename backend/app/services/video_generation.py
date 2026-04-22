from __future__ import annotations

import os
import subprocess
from pathlib import Path
import re
import hashlib

from app.config import get_settings
from app.media.pipeline import build_media_prompts, pick_provider
from app.schemas.media import GenerateVideoRequest, GenerateVideoResponse


def _resolve_local_image(settings, p: str) -> Path | None:
    if not p:
        return None
    try:
        # Stored paths are typically like "uploads/x.jpg" or "generated_media/x.mp4".
        local = (settings.data_dir / p).resolve()
        if local.exists():
            return local
    except Exception:
        return None
    return None


def _motionify_scene_prompt(*, base: str, idx: int, total: int) -> str:
    """
    Convert a mostly-visual scene beat into a motion-first prompt for real video generation.
    """
    b = (base or "").strip() or "High-intensity action trailer beat."
    return (
        "FULL MOTION VIDEO (FMV). Every pixel changes over time. No still frames, no slideshow, no ken-burns zoom/pan.\n"
        "Cinematography: aggressive dolly-in/push-in, fast tracking shots, parallax, rack focus, "
        "fluid character movement, realistic motion blur.\n"
        "Physics: hair + fabric move with wind; cloth drape responds to body motion; objects interact with inertia; "
        "shadows/reflections update continuously.\n"
        f"Beat {idx+1}/{total}: {b}\n"
        "Constraints: keep the same face-anchor identity and keep the outfit consistent across time.\n"
    )


def _slideshow_fallback_mp4(*, req: GenerateVideoRequest, job_id: str) -> str | None:
    """
    Build a lightweight slideshow MP4 from anchor stills.

    This makes the app feel "seamless" even when paid video providers aren't available
    (e.g., Veo access/billing). Requires moviepy (already in requirements.txt).
    """
    settings = get_settings()
    try:
        from moviepy import AudioFileClip, ColorClip, ImageClip, VideoFileClip, concatenate_videoclips  # type: ignore
    except Exception:
        return None

    out_dir = settings.generated_media_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{job_id}_slideshow.mp4"

    target_w, target_h = 1080, 1920
    clips = []
    if req.scenes:
        for seg in req.scenes:
            dur = int(seg.duration_seconds or 6)
            # Prefer AI-generated render still if present.
            lp = _resolve_local_image(settings, seg.render_image_path or "") or _resolve_local_image(
                settings, seg.anchor_image_path or ""
            )
            if lp:
                c = ImageClip(str(lp)).with_duration(max(2, min(16, dur)))
            else:
                c = ColorClip(size=(target_w, target_h), color=(10, 10, 12)).with_duration(max(2, min(16, dur)))
            # Force 9:16 output by center-cropping after scaling to cover.
            try:
                c = c.resized(height=target_h)
                if c.w < target_w:
                    c = c.resized(width=target_w)
                c = c.cropped(x_center=c.w / 2, y_center=c.h / 2, width=target_w, height=target_h)
                # Subtle “Ken Burns” zoom so the reel feels alive (still → motion).
                d = float(c.duration)
                c = c.resized(lambda t: 1.0 + 0.05 * min(1.0, float(t) / max(d, 0.01)))
            except Exception:
                pass
            clips.append(c)
    else:
        # Legacy: use the first available anchor, repeat to fill duration_seconds.
        anchors = []
        if req.face_anchor_image_path:
            anchors.append(req.face_anchor_image_path)
        anchors.extend(req.anchor_image_paths or [])
        lp = _resolve_local_image(settings, anchors[0]) if anchors else None
        dur = int(req.duration_seconds or 8)
        if lp:
            c = ImageClip(str(lp)).with_duration(max(2, min(60, dur)))
        else:
            c = ColorClip(size=(target_w, target_h), color=(10, 10, 12)).with_duration(max(2, min(60, dur)))
        try:
            c = c.resized(height=target_h)
            if c.w < target_w:
                c = c.resized(width=target_w)
            c = c.cropped(x_center=c.w / 2, y_center=c.h / 2, width=target_w, height=target_h)
            d = float(c.duration)
            c = c.resized(lambda t: 1.0 + 0.05 * min(1.0, float(t) / max(d, 0.01)))
        except Exception:
            pass
        clips.append(c)

    if not clips:
        return None

    try:
        final = concatenate_videoclips(clips, method="compose")
        final.write_videofile(
            str(out_file),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            preset="veryfast",
            threads=2,
            logger=None,
        )
    except Exception:
        try:
            if out_file.exists():
                out_file.unlink()
        except Exception:
            pass
        return None
    finally:
        for c in clips:
            try:
                c.close()
            except Exception:
                pass

    return f"generated_media/{out_file.name}"


def _mux_background_music(*, video_path: Path, music_path: Path, out_path: Path) -> bool:
    """
    Mux background music into MP4 (loops/trim to video length).
    """
    try:
        if not video_path.exists() or not music_path.exists():
            return False
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(video_path),
            "-stream_loop",
            "-1",
            "-i",
            str(music_path),
            "-shortest",
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, timeout=120)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _pick_music_preset(movie_idea: str) -> str:
    t = (movie_idea or "").lower()
    # Action / spy / chase
    if any(k in t for k in ("mission impossible", "spy", "chase", "heist", "escape", "run", "gun", "fight", "stunt", "explosion")):
        return "action"
    # Suspense / thriller
    if any(k in t for k in ("suspense", "thriller", "tension", "stealth", "infiltrate", "noir", "mystery")):
        return "suspense"
    # Romance / dreamy
    if any(k in t for k in ("romance", "love", "date", "sunset", "cafe", "paris", "dreamy", "warm")):
        return "romance"
    # Tech / cyber
    if any(k in t for k in ("cyber", "neon", "hacker", "futur", "sci-fi", "robot", "matrix")):
        return "cyber"
    # Stable fallback based on hash, to avoid always identical “default”.
    h = int(hashlib.sha256(t.encode("utf-8")).hexdigest(), 16) if t else 0
    return ("action", "suspense", "romance", "cyber")[h % 4]


def _lyria_prompt(*, movie_idea: str, preset: str) -> str:
    """
    Lyria prompting prefers concrete musical direction (genre/mood/instruments/tempo).
    We keep this instrumental so it works reliably as a background bed.
    """
    idea = (movie_idea or "").strip()
    if preset == "action":
        return (
            "Create a 30-second high-energy cinematic action trailer music clip. "
            "Driving percussion, pulsing bass, sharp string ostinatos, brass stabs, "
            "riser impacts, clean transitions. Instrumental only (no vocals). "
            f"Context: {idea}"
        )
    if preset == "suspense":
        return (
            "Create a 30-second suspense / spy-thriller underscore. "
            "Tight rhythmic pulses, muted low strings, subtle impacts, rising tension, "
            "clean modern sound design. Instrumental only (no vocals). "
            f"Context: {idea}"
        )
    if preset == "romance":
        return (
            "Create a 30-second romantic cinematic underscore. "
            "Warm strings, gentle piano, soft swells, hopeful cadence. "
            "Instrumental only (no vocals). "
            f"Context: {idea}"
        )
    if preset == "cyber":
        return (
            "Create a 30-second cyberpunk action underscore. "
            "Glitchy synth bass, arpeggiators, tight drums, futuristic textures. "
            "Instrumental only (no vocals). "
            f"Context: {idea}"
        )
    return f"Create a 30-second cinematic instrumental music bed (no vocals). Context: {idea}"


def _generate_lyria_music_mp3(*, out_path: Path, movie_idea: str) -> tuple[bool, str | None]:
    """
    Generate a 30s MP3 bed with Gemini Lyria 3 Clip.
    Returns False if the SDK/model/quota isn't available, so callers can fall back.
    """
    settings = get_settings()
    if not settings.gemini_api_key or not settings.gemini_api_key.strip():
        return False, "missing GEMINI_API_KEY"
    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except Exception:
        return False, "google-genai SDK missing"

    preset = _pick_music_preset(movie_idea)
    prompt = _lyria_prompt(movie_idea=movie_idea, preset=preset)

    try:
        client = genai.Client(api_key=settings.gemini_api_key)
        resp = client.models.generate_content(
            model="lyria-3-clip-preview",
            contents=prompt,
            config=types.GenerateContentConfig(
                # Lyria 3 Clip returns MP3 by default; specifying response_mime_type
                # can be rejected for this model.
                response_modalities=["AUDIO", "TEXT"],
            ),
        )
        audio_data = None
        for part in (getattr(resp, "parts", None) or []):
            inline = getattr(part, "inline_data", None)
            if inline is not None and getattr(inline, "data", None):
                audio_data = inline.data
                break
        if not audio_data:
            return False, "no audio bytes returned"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(audio_data)
        ok = out_path.exists() and out_path.stat().st_size > 4096
        return (ok, None) if ok else (False, "audio file too small")
    except Exception as e:
        return False, str(e)


def _generate_default_music(*, out_path: Path, duration_s: int, movie_idea: str) -> bool:
    """
    Generate a lightweight instrumental bed (no external deps).
    This is not "great music", but it ensures demos always have a soundtrack.
    """
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        dur = max(6, min(300, int(duration_s or 30)))
        preset = _pick_music_preset(movie_idea)
        # Output AAC in an M4A container for easy muxing.
        # Different presets = different “energy” without external assets.
        if preset == "action":
            # Punchier bass + higher pulse
            fc = (
                f"[0:a]volume=0.22,highpass=f=40[a0];"
                f"[1:a]volume=0.16[a1];"
                f"[2:a]lowpass=f=1800,volume=0.06[a2];"
                f"[a0][a1][a2]amix=inputs=3:normalize=0,volume=0.95[aout]"
            )
            src0 = f"sine=frequency=98:duration={dur}:sample_rate=44100"
            src1 = f"sine=frequency=196:duration={dur}:sample_rate=44100"
        elif preset == "suspense":
            # Lower, darker bed
            fc = (
                f"[0:a]volume=0.20,lowpass=f=800[a0];"
                f"[1:a]volume=0.12,lowpass=f=1200[a1];"
                f"[2:a]lowpass=f=900,volume=0.08[a2];"
                f"[a0][a1][a2]amix=inputs=3:normalize=0,volume=0.85[aout]"
            )
            src0 = f"sine=frequency=73:duration={dur}:sample_rate=44100"
            src1 = f"sine=frequency=110:duration={dur}:sample_rate=44100"
        elif preset == "romance":
            # Brighter, softer
            fc = (
                f"[0:a]volume=0.16[a0];"
                f"[1:a]volume=0.12[a1];"
                f"[2:a]lowpass=f=2200,volume=0.05[a2];"
                f"[a0][a1][a2]amix=inputs=3:normalize=0,volume=0.78[aout]"
            )
            src0 = f"sine=frequency=220:duration={dur}:sample_rate=44100"
            src1 = f"sine=frequency=330:duration={dur}:sample_rate=44100"
        else:  # cyber
            fc = (
                f"[0:a]volume=0.18[a0];"
                f"[1:a]volume=0.14[a1];"
                f"[2:a]lowpass=f=2500,volume=0.06[a2];"
                f"[a0][a1][a2]amix=inputs=3:normalize=0,volume=0.90[aout]"
            )
            src0 = f"sine=frequency=155:duration={dur}:sample_rate=44100"
            src1 = f"sine=frequency=233:duration={dur}:sample_rate=44100"

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            src0,
            "-f",
            "lavfi",
            "-i",
            src1,
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=white:amplitude=0.02:duration={dur}:sample_rate=44100",
            "-filter_complex",
            fc,
            "-map",
            "[aout]",
            "-c:a",
            "aac",
            "-b:a",
            "160k",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, timeout=120)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _kenburns_clip_mp4(*, still_path: Path, out_path: Path, duration_s: int, movie_idea: str) -> bool:
    """
    Create a short silent MP4 from a still using ffmpeg zoompan.
    """
    try:
        if not still_path.exists():
            return False
        w, h = 1080, 1920
        fps = 18
        dur = max(2, min(16, int(duration_s or 6)))
        frames = max(1, int(dur * fps))
        preset = _pick_music_preset(movie_idea)
        # Faster motion for action; gentler for romance.
        z_inc = "0.0012"
        z_max = "1.06"
        if preset == "action":
            z_inc, z_max = "0.0024", "1.12"
        elif preset == "suspense":
            z_inc, z_max = "0.0018", "1.09"
        elif preset == "romance":
            z_inc, z_max = "0.0010", "1.05"
        # Add slight “handheld” drift via x/y sin terms (subtle).
        vf = (
            f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},"
            f"zoompan=z='min(zoom+{z_inc},{z_max})':"
            f"x='iw/2-(iw/zoom/2)+sin(on/9)*12':y='ih/2-(ih/zoom/2)+cos(on/11)*10':"
            f"d={frames}:s={w}x{h}:fps={fps},"
            f"eq=contrast=1.08:saturation=1.10"
        )
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-loop",
            "1",
            "-i",
            str(still_path),
            "-t",
            f"{float(dur):.3f}",
            "-vf",
            vf,
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-an",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, timeout=120)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _concat_mp4s(*, clip_paths: list[Path], out_path: Path) -> bool:
    """
    Concatenate mp4 clips (same codec/settings) using ffmpeg concat demuxer.
    """
    try:
        if not clip_paths:
            return False
        for p in clip_paths:
            if not p.exists() or p.stat().st_size == 0:
                return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        lst = out_path.parent / f"{out_path.stem}_concat.txt"
        def _ffmpeg_concat_quote(path: Path) -> str:
            # ffmpeg concat file expects: file '<path>'
            # Escape single quotes inside paths.
            s = str(path)
            s = s.replace("'", "'\\''")
            return f"file '{s}'"

        # concat demuxer requires a file list.
        lines = [_ffmpeg_concat_quote(p) for p in clip_paths]
        lst.write_text("\n".join(lines) + "\n", encoding="utf-8")
        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(lst),
            "-c",
            "copy",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, timeout=180)
        try:
            lst.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _stitch_with_crossfades(*, clip_paths: list[Path], out_path: Path, xfade_s: float = 0.4) -> bool:
    """
    Create one continuous MP4 with subtle crossfades between clips.
    Re-encodes (needed for xfade).
    """
    try:
        if len(clip_paths) == 0:
            return False
        if len(clip_paths) == 1:
            out_path.write_bytes(clip_paths[0].read_bytes())
            return out_path.exists() and out_path.stat().st_size > 0
        for p in clip_paths:
            if not p.exists() or p.stat().st_size == 0:
                return False

        def _probe_duration_s(p: Path) -> float | None:
            try:
                r = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=nokey=1:noprint_wrappers=1",
                        str(p),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                return float((r.stdout or "").strip())
            except Exception:
                return None

        durs = [(_probe_duration_s(p) or 0.0) for p in clip_paths]
        if any(d <= 0.05 for d in durs):
            return False

        # Build filter graph: v0 xfade v1 -> v01 xfade v2 -> ...
        inputs = []
        for p in clip_paths:
            inputs += ["-i", str(p)]

        # Assume each clip is ~dur; we fade near the end of each clip.
        # We don't know exact durations without ffprobe; approximate by using a fixed offset
        # and letting ffmpeg handle the overlap via shortest.
        # To improve continuity, we keep xfade small (0.4s).
        filter_parts = []
        # Normalize scale/aspect just in case.
        for i in range(len(clip_paths)):
            filter_parts.append(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1[v{i}]")
        cur = "v0"
        # Cumulative offsets so final duration ~ sum(durs) - xfade*(n-1)
        cum = durs[0]
        for i in range(1, len(clip_paths)):
            nxt = f"v{i}"
            out = f"vx{i}"
            offset = max(0.0, cum - float(xfade_s))
            filter_parts.append(
                f"[{cur}][{nxt}]xfade=transition=fade:duration={xfade_s}:offset={offset:.3f}[{out}]"
            )
            cur = out
            cum = cum + durs[i] - float(xfade_s)
        filter_complex = ";".join(filter_parts)

        cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            f"[{cur}]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-preset",
            "veryfast",
            "-crf",
            "20",
            "-an",
            "-movflags",
            "+faststart",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, timeout=240)
        return out_path.exists() and out_path.stat().st_size > 0
    except Exception:
        return False


def _local_animated_reel_mp4(*, req: GenerateVideoRequest, job_id: str) -> str | None:
    """
    Build an animated (Ken Burns) reel by generating per-scene clips from scene stills,
    then concatenating into one MP4.
    """
    settings = get_settings()
    out_dir = settings.generated_media_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    final_mp4 = out_dir / f"{job_id}_reel.mp4"

    clip_paths: list[Path] = []
    for i, seg in enumerate(req.scenes or []):
        still_local = _resolve_local_image(settings, seg.render_image_path or "") or _resolve_local_image(
            settings, seg.anchor_image_path or ""
        )
        if still_local is None:
            continue
        clip = out_dir / f"{job_id}_s{i+1:02d}.mp4"
        if not _kenburns_clip_mp4(
            still_path=still_local,
            out_path=clip,
            duration_s=int(seg.duration_seconds or 6),
            movie_idea=req.scene_prompt or "",
        ):
            continue
        clip_paths.append(clip)

    if not clip_paths:
        return None

    # Prefer continuous crossfades for a "real" reel feel.
    if not _stitch_with_crossfades(clip_paths=clip_paths, out_path=final_mp4, xfade_s=0.4):
        # Fall back to straight concat if xfade fails.
        if not _concat_mp4s(clip_paths=clip_paths, out_path=final_mp4):
            return None

    # Cleanup per-scene clips to save disk.
    for p in clip_paths:
        try:
            p.unlink(missing_ok=True)  # type: ignore[arg-type]
        except Exception:
            pass
    return f"generated_media/{final_mp4.name}"


async def run_generate_video(body: GenerateVideoRequest) -> GenerateVideoResponse:
    settings = get_settings()
    provider = pick_provider(provider_name=settings.media_provider, has_runway_key=bool(settings.runway_api_key))
    if body.scenes and len(body.scenes) > 0:
        stitched = " | ".join(s.description for s in body.scenes)
        prompts = build_media_prompts(outfit=None, narrative=stitched, duration_seconds=body.duration_seconds)
        if body.require_fmv:
            total = len(body.scenes)
            req = body.model_copy(
                update={
                    "scenes": [
                        s.model_copy(update={"description": _motionify_scene_prompt(base=s.description, idx=i, total=total)})
                        for i, s in enumerate(body.scenes)
                    ]
                }
            )
        else:
            req = body
    else:
        prompts = build_media_prompts(outfit=None, narrative=body.scene_prompt, duration_seconds=body.duration_seconds)
        req = body

    # Prefer real dynamic video providers when available; otherwise generate a local animated reel.
    try:
        res = await provider.generate(req=req, prompts=prompts)
    except Exception as e:
        res = GenerateVideoResponse(
            status="failed",
            job_id="",
            preview_message=f"Video provider failed: {e!s}. Falling back to local animation.",
            video_url=None,
            provider=provider.name,
            description=prompts.storyboard.logline,
            video_prompt=prompts.video_prompt,
        )

    def _looks_like_quota_error(s: str) -> bool:
        t = (s or "").lower()
        return ("resource_exhausted" in t) or ("exceeded your current quota" in t) or ("rate limit" in t) or ("code': 429" in t) or ("code\": 429" in t)

    # If user requires FMV, we normally fail closed; however, when the provider is quota-limited (429),
    # automatically downgrade to local fallback (clearly labeled) so the demo flow isn't blocked.
    allow_fallback = body.require_fmv and _looks_like_quota_error(res.preview_message or "")

    if body.require_fmv and (res.video_url is None or res.provider != "gemini_video") and (not allow_fallback):
        detail = (res.preview_message or "").strip()
        extra = f" Provider detail: {detail}" if detail else ""
        return GenerateVideoResponse(
            status="failed",
            job_id=res.job_id or "",
            preview_message=(
                "Full-motion video (FMV) was required, but the video provider did not return a real motion clip. "
                "Enable a real video provider (e.g. `MEDIA_PROVIDER=gemini_video` with Veo access) and try again."
                + extra
            ),
            video_url=None,
            provider=res.provider or provider.name,
            description=prompts.storyboard.logline,
            video_prompt=prompts.video_prompt,
        )

    # If provider didn't give us a real MP4, or if we have explicit scenes, ensure we return a dynamic reel.
    if (req.scenes and len(req.scenes) > 0) and (res.video_url is None or res.provider != "gemini_video"):
        job_id = os.urandom(8).hex()
        animated_url = _local_animated_reel_mp4(req=req, job_id=job_id)
        if animated_url:
            msg = "Generated a continuous animated multi-scene reel (motion + crossfades)."
            if allow_fallback:
                msg = (
                    "FMV provider quota-limited (429). Fell back to local animated reel (NOT full-motion model video)."
                )
            res = GenerateVideoResponse(
                status="completed",
                job_id=job_id,
                preview_message=msg,
                video_url=animated_url,
                provider="local_animated",
                description=prompts.storyboard.logline,
                video_prompt=prompts.video_prompt,
            )

    # Background music: if user didn't upload any, generate a default bed and mux it in.
    try:
        bg_rel = body.background_music_path
        if (not bg_rel) and res.video_url:
            # Create default music (per run).
            rel_video = res.video_url.lstrip("/")
            local_video = (settings.data_dir / rel_video).resolve()
            out_dir = settings.generated_media_dir
            out_dir.mkdir(parents=True, exist_ok=True)
            # Prefer Gemini Lyria (real music) when available.
            lyria_music = out_dir / f"{Path(local_video).stem}_lyria.mp3"
            ok, lyria_err = _generate_lyria_music_mp3(out_path=lyria_music, movie_idea=body.scene_prompt or "")
            if ok:
                bg_rel = f"generated_media/{lyria_music.name}"
            else:
                default_music = out_dir / f"{Path(local_video).stem}_bgm.m4a"
                if _generate_default_music(
                    out_path=default_music,
                    duration_s=int(body.duration_seconds or 30),
                    movie_idea=body.scene_prompt or "",
                ):
                    bg_rel = f"generated_media/{default_music.name}"
                    # Helpful signal in UI logs/debugging (kept short).
                    if lyria_err and (res.preview_message or ""):
                        res.preview_message = (res.preview_message[:460] + "…") if len(res.preview_message) > 480 else res.preview_message
                        res.preview_message = f"{res.preview_message}\n(Lyria music unavailable: {lyria_err})"

        if bg_rel and res.video_url:
            rel_video = res.video_url.lstrip("/")
            local_video = (settings.data_dir / rel_video).resolve()
            local_music = (settings.data_dir / bg_rel).resolve()
            if local_video.exists() and local_video.suffix.lower() == ".mp4" and local_music.exists():
                out_dir = settings.generated_media_dir
                out_dir.mkdir(parents=True, exist_ok=True)
                out_mp4 = out_dir / f"{local_video.stem}_music.mp4"
                if _mux_background_music(video_path=local_video, music_path=local_music, out_path=out_mp4):
                    res.video_url = f"generated_media/{out_mp4.name}"
    except Exception:
        pass

    # Seamless UX fallback: if the selected provider doesn't return an MP4, generate a slideshow MP4
    # from the anchor stills so the UI has something to play/download.
    if (not body.require_fmv) and res.video_url is None and (req.scenes or req.anchor_image_paths or req.face_anchor_image_path):
        job = res.job_id or "slideshow"
        fallback_url = _slideshow_fallback_mp4(req=req, job_id=job)
        if fallback_url:
            res.video_url = fallback_url
            # Seamless UX: don't surface provider failure if fallback succeeded.
            res.preview_message = "Generated a local vertical animated MP4 from your scene stills."
            # Treat as completed so the UI doesn't look like a failure.
            if res.status in ("failed", "queued", "mock"):
                res.status = "completed"
    if res.description is None:
        res.description = prompts.storyboard.logline
    if res.video_prompt is None:
        res.video_prompt = prompts.video_prompt
    return res
