import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import { useImageLightbox } from "@/components/ui/ImageLightbox";
import { ApiError, apiPostMultipart, mediaUrl } from "@/lib/api";
import type {
  GenerateVideoRequestBody,
  GenerateVideoResponse,
  PreviewReelCopyRequestBody,
  PreviewReelCopyResponse,
  RecommendOutfitResponse,
  ReelSceneDraft,
  ReelVideoScenePayload,
} from "@/types";

export function RunwayReelPreviewPanel({
  recommendation,
  video,
  busy,
  faceAnchorPath,
  onUploadFaceAnchor,
  onGenerateScenes,
  onGenerateSceneAssets,
  onRenderVideo,
}: {
  recommendation: RecommendOutfitResponse | null;
  video: GenerateVideoResponse | null;
  busy: boolean;
  faceAnchorPath: string | null;
  onUploadFaceAnchor: (file: File) => Promise<void>;
  onGenerateScenes: (body: PreviewReelCopyRequestBody) => Promise<PreviewReelCopyResponse>;
  onGenerateSceneAssets: (body: PreviewReelCopyRequestBody & { scene: ReelSceneDraft }) => Promise<ReelSceneDraft>;
  onRenderVideo: (body: GenerateVideoRequestBody) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const musicInputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [musicUploading, setMusicUploading] = useState<string | null>(null);
  const [musicErr, setMusicErr] = useState<string | null>(null);
  const [musicPath, setMusicPath] = useState<string | null>(null);
  const [copyErr, setCopyErr] = useState<string | null>(null);
  const [copyBusy, setCopyBusy] = useState(false);
  const [sceneAssetBusy, setSceneAssetBusy] = useState<number | null>(null);
  const [sceneAssetErr, setSceneAssetErr] = useState<Record<number, string | null>>({});
  const { open: openLightbox } = useImageLightbox();
  const [scenePrompt, setScenePrompt] = useState("");
  const [logline, setLogline] = useState("");
  const [scenes, setScenes] = useState<ReelSceneDraft[]>([]);
  const autoPreviewTimerRef = useRef<number | null>(null);

  // Persist panel-local Simulation state across route/tab toggles (component remounts).
  const persistKey = useMemo(() => {
    const outfitKey = recommendation?.garments?.map((g) => g.image_path).join("|") ?? "";
    return `apparel_sim_panel_v1:${faceAnchorPath ?? "noface"}:${outfitKey}`;
  }, [faceAnchorPath, recommendation]);

  const persistWrite = useCallback(
    (next: Partial<{ scenePrompt: string; logline: string; scenes: ReelSceneDraft[]; musicPath: string | null }>) => {
      try {
        const raw = sessionStorage.getItem(persistKey);
        const base = raw ? (JSON.parse(raw) as Record<string, unknown>) : {};
        sessionStorage.setItem(persistKey, JSON.stringify({ ...base, ...next }));
      } catch {
        // ignore
      }
    },
    [persistKey],
  );

  useEffect(() => {
    try {
      const raw = sessionStorage.getItem(persistKey);
      if (!raw) return;
      const parsed = JSON.parse(raw) as {
        scenePrompt?: string;
        logline?: string;
        scenes?: ReelSceneDraft[];
        musicPath?: string | null;
      };
      if (typeof parsed.scenePrompt === "string") setScenePrompt(parsed.scenePrompt);
      if (typeof parsed.logline === "string") setLogline(parsed.logline);
      if (Array.isArray(parsed.scenes)) setScenes(parsed.scenes);
      if (typeof parsed.musicPath !== "undefined") setMusicPath(parsed.musicPath ?? null);
    } catch {
      // ignore
    }
  }, [persistKey]);

  const outfitSummary = useMemo(() => {
    if (!recommendation?.garments.length) return "";
    return recommendation.garments.map((g) => `${g.color} ${g.category}`).join(", ");
  }, [recommendation]);

  const wardrobeAnchors = useMemo(() => {
    if (!recommendation?.garments.length) return [];
    return recommendation.garments.map((g) => g.image_path).filter((p) => typeof p === "string" && p.startsWith("uploads/"));
  }, [recommendation]);

  // Intentionally do not auto-fill the movie idea.
  // The user should supply a real "movie idea" (concept + vibe) rather than a generic template.

  const previewSrc = useMemo(() => {
    if (!faceAnchorPath) return null;
    return mediaUrl(faceAnchorPath);
  }, [faceAnchorPath]);

  const runGenerateScenes = useCallback(async () => {
    if (!scenePrompt.trim()) {
      setCopyErr('Please enter a “Movie idea” first (one sentence: concept + vibe).');
      return;
    }
    if (!recommendation?.garments.length) {
      setCopyErr("No wardrobe anchors found yet. Pick an outfit first (so we have garment images to turn into scenes).");
      return;
    }
    if (autoPreviewTimerRef.current !== null) {
      window.clearTimeout(autoPreviewTimerRef.current);
      autoPreviewTimerRef.current = null;
    }
    setCopyBusy(true);
    setCopyErr(null);
    try {
      const res = await onGenerateScenes({
        scene_prompt: scenePrompt.trim(),
        anchor_image_paths: wardrobeAnchors,
        face_anchor_path: faceAnchorPath,
        duration_seconds: 30,
        face_anchor_present: !!faceAnchorPath,
      });
      setLogline(res.description);
      setScenes(res.scenes);
      persistWrite({
        scenePrompt: scenePrompt.trim(),
        logline: res.description,
        scenes: res.scenes,
        musicPath,
      });
    } catch (e) {
      setCopyErr(e instanceof ApiError ? e.body : "Couldn’t generate scene assets.");
    } finally {
      setCopyBusy(false);
    }
  }, [scenePrompt, recommendation?.garments.length, onGenerateScenes, wardrobeAnchors, faceAnchorPath, persistWrite, musicPath]);

  const pickFile = async (f: File | null) => {
    if (!f) return;
    setUploading(f.name);
    setUploadErr(null);
    try {
      await onUploadFaceAnchor(f);
    } catch (e) {
      if (e instanceof ApiError) {
        setUploadErr(`Upload failed (${e.status}). ${e.body}`);
      } else {
        setUploadErr("Upload failed. Please try a different image (JPG/PNG/WebP/HEIC).");
      }
    } finally {
      setUploading(null);
    }
  };

  const runRender = async () => {
    if (!scenePrompt.trim()) {
      setCopyErr('Please enter a “Movie idea” first (one sentence: concept + vibe).');
      return;
    }
    if (!faceAnchorPath) {
      setCopyErr("Please upload a face anchor selfie first (required for FMV).");
      return;
    }
    if (!wardrobeAnchors.length) {
      setCopyErr("Pick an outfit first (Style → Recommend outfit), so we have garment anchors.");
      return;
    }
    const scenePayload: ReelVideoScenePayload[] | undefined =
      scenes.length > 0
        ? scenes.map((s) => ({
            anchor_image_path: s.anchor_image_path,
            render_image_path: s.generated_image_path ?? null,
            anchor_type: s.anchor_type ?? "wardrobe",
            description: s.description,
            duration_seconds: s.duration_seconds ?? 8,
          }))
        : undefined;
    await onRenderVideo({
      scene_prompt: scenePrompt.trim(),
      anchor_image_paths: wardrobeAnchors,
      face_anchor_image_path: faceAnchorPath,
      duration_seconds: 30,
      background_music_path: musicPath,
      require_fmv: true,
      scenes: scenePayload,
    });
  };

  const providerHint =
    "Each anchor (selfie + garment shots) gets its own AI shot description. Video render stitches one clip per scene when MEDIA_PROVIDER=gemini_video and GEMINI_API_KEY are set (billable).";

  return (
    <Card
      title="Gemini Reel Lab"
      subtitle="Multi-scene ~30s reel: one shot per anchor image, then stitched into a single MP4."
      right={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            disabled={busy || copyBusy}
            onClick={() => void runGenerateScenes()}
            className="rounded-lg border border-line bg-[#E8E8E8] px-3 py-1.5 text-xs font-semibold text-black hover:border-accent/50 disabled:opacity-40"
          >
            {copyBusy ? "Working…" : "Generate scenes"}
          </button>
          <button
            type="button"
            disabled={busy}
            onClick={() => void runRender()}
            className="rounded-lg border border-accent/40 bg-[#C8A96A]/10 px-3 py-1.5 text-xs font-semibold text-black hover:bg-[#C8A96A]/20 disabled:opacity-40"
          >
            {busy ? "Rendering…" : "Generate video"}
          </button>
        </div>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-black/50">{providerHint}</p>
        {copyBusy ? <p className="text-xs text-[#C8A96A]">Generating shot descriptions for each scene…</p> : null}
        {copyErr ? <p className="text-xs text-red-300/85">{copyErr}</p> : null}

        <div
          className={[
            "rounded-2xl border border-line bg-[#E8E8E8]/30 p-4 transition",
            dragOver ? "border-accent/60 ring-2 ring-accent/20" : "",
          ].join(" ")}
          onDragEnter={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(true);
          }}
          onDragOver={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(true);
          }}
          onDragLeave={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(false);
          }}
          onDrop={(e) => {
            e.preventDefault();
            e.stopPropagation();
            setDragOver(false);
            const f = e.dataTransfer.files?.[0] ?? null;
            void pickFile(f);
          }}
        >
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/55">Face anchor (optional)</p>
              <p className="mt-1 text-xs text-black/45">
                Upload a selfie to unlock a dedicated opening scene. Wardrobe images each get their own scene.
              </p>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={inputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  e.currentTarget.value = "";
                  void pickFile(f);
                }}
              />
              <button
                type="button"
                disabled={busy || !!uploading}
                onClick={() => inputRef.current?.click()}
                className="rounded-xl border border-line bg-[#E8E8E8] px-4 py-2 text-xs font-semibold text-black hover:border-accent/50 disabled:opacity-40"
              >
                {uploading ? `Uploading ${uploading}…` : faceAnchorPath ? "Replace selfie" : "Choose selfie"}
              </button>
            </div>
          </div>

          {previewSrc ? (
            <div className="mt-3 flex items-center gap-3">
              <div className="h-14 w-14 overflow-hidden rounded-xl border border-line bg-[#F5F5F5]">
                <img src={previewSrc} alt="Face anchor" className="h-full w-full object-cover" loading="lazy" />
              </div>
              <p className="text-xs text-black/55">{faceAnchorPath}</p>
            </div>
          ) : null}
          {uploadErr ? <p className="mt-3 text-xs text-red-300/80">{uploadErr}</p> : null}
        </div>

        <div className="rounded-2xl border border-line bg-[#E8E8E8]/25 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/55">Movie idea</p>
          <p className="mt-1 text-xs text-black/45">
            One sentence that combines concept + vibe (what happens + how it should feel/look/sound).
          </p>
          <textarea
            value={scenePrompt}
            onChange={(e) => {
              setScenePrompt(e.target.value);
              persistWrite({ scenePrompt: e.target.value });
            }}
            rows={3}
            placeholder='e.g. "Late-afternoon Paris café: Lisa slips in for coffee, calm confidence, warm film grain." Or "Mission Impossible-style runway sprint: stealthy, kinetic, high-contrast lights."'
            className="mt-2 w-full rounded-xl border border-line bg-[#F5F5F5] px-3 py-2 text-sm text-black outline-none ring-accent/15 focus:ring-2"
          />
        </div>

        <div className="rounded-2xl border border-line bg-[#E8E8E8]/25 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/55">Background music (optional)</p>
              <p className="mt-1 text-xs text-black/45">Upload an audio file (mp3/m4a/wav/ogg) to mux into the final MP4.</p>
            </div>
            <div className="flex items-center gap-2">
              <input
                ref={musicInputRef}
                type="file"
                accept="audio/*,.mp3,.m4a,.wav,.ogg,.aac"
                className="hidden"
                onChange={(e) => {
                  const f = e.target.files?.[0] ?? null;
                  e.currentTarget.value = "";
                  if (!f) return;
                  void (async () => {
                    setMusicUploading(f.name);
                    setMusicErr(null);
                    try {
                      const fd = new FormData();
                      fd.append("file", f);
                      const res = await apiPostMultipart<{ path: string }>("/upload-music", fd);
                      setMusicPath(res.path);
                      persistWrite({ musicPath: res.path });
                    } catch (e) {
                      setMusicErr(e instanceof ApiError ? e.body : "Music upload failed.");
                    } finally {
                      setMusicUploading(null);
                    }
                  })();
                }}
              />
              <button
                type="button"
                disabled={busy || !!musicUploading}
                onClick={() => musicInputRef.current?.click()}
                className="rounded-xl border border-line bg-[#E8E8E8] px-4 py-2 text-xs font-semibold text-black hover:border-accent/50 disabled:opacity-40"
              >
                {musicUploading ? `Uploading ${musicUploading}…` : musicPath ? "Replace music" : "Choose music"}
              </button>
            </div>
          </div>
          {musicPath ? <p className="mt-2 text-[11px] text-black/50">Using: {musicPath}</p> : null}
          {musicErr ? <p className="mt-2 text-xs text-red-300/80">{musicErr}</p> : null}
        </div>

        {scenes.length > 0 ? (
          <div className="space-y-3">
            <div className="flex items-baseline justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-accent/90">Scenes for ~30s reel</p>
              <p className="text-[11px] text-black/45">{scenes.length} shot{scenes.length === 1 ? "" : "s"} · edit each beat, then render</p>
            </div>
            {scenes.slice(0, 5).map((s, idx) => (
              <div
                key={`${s.anchor_image_path ?? "x"}-${idx}`}
                className="rounded-2xl border border-accent/20 bg-[#E8E8E8]/30 p-4"
              >
                <div className="flex flex-wrap items-start gap-3">
                  {s.generated_video_path || s.generated_image_path || s.anchor_image_path ? (
                    <button
                      type="button"
                      className="h-20 w-20 shrink-0 overflow-hidden rounded-xl border border-line bg-[#F5F5F5] text-left ring-0 transition hover:ring-2 hover:ring-accent/35"
                      onClick={() =>
                        openLightbox(
                          mediaUrl(s.generated_video_path || s.generated_image_path || s.anchor_image_path || ""),
                          s.label || `Scene ${idx + 1}`,
                        )
                      }
                      title="Click to enlarge"
                    >
                      {s.generated_video_path ? (
                        <video
                          src={mediaUrl(s.generated_video_path)}
                          className="h-full w-full object-cover"
                          muted
                          playsInline
                          autoPlay
                          loop
                          preload="metadata"
                        />
                      ) : (
                        <img
                          src={mediaUrl(s.generated_image_path || s.anchor_image_path || "")}
                          alt=""
                          className="h-full w-full object-cover"
                          loading="lazy"
                        />
                      )}
                    </button>
                  ) : (
                    <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-xl border border-dashed border-line text-[10px] text-black/40">
                      No still
                    </div>
                  )}
                  <div className="min-w-0 flex-1 space-y-2">
                    <p className="text-xs font-semibold text-black">
                      {s.label || `Scene ${idx + 1}`}{" "}
                      <span className="text-black/45">
                        ({s.anchor_type === "face" ? "face" : s.anchor_type === "wardrobe" ? "garment" : "beat"}) · ~{s.duration_seconds ?? 8}s
                      </span>
                    </p>
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        disabled={busy || copyBusy || sceneAssetBusy === idx}
                        onClick={() =>
                          void (async () => {
                            setSceneAssetErr((e) => ({ ...e, [idx]: null }));
                            setSceneAssetBusy(idx);
                            try {
                              const updated = await onGenerateSceneAssets({
                                scene_prompt: scenePrompt.trim(),
                                anchor_image_paths: wardrobeAnchors,
                                face_anchor_path: faceAnchorPath,
                                duration_seconds: 30,
                                face_anchor_present: !!faceAnchorPath,
                                scene: s,
                              });
                              const next = [...scenes];
                              next[idx] = updated;
                              setScenes(next);
                            } catch (e) {
                              setSceneAssetErr((prev) => ({
                                ...prev,
                                [idx]: e instanceof ApiError ? e.body : "Couldn’t generate scene image.",
                              }));
                            } finally {
                              setSceneAssetBusy(null);
                            }
                          })()
                        }
                        className="rounded-lg border border-line bg-[#E8E8E8] px-3 py-1.5 text-[11px] font-semibold text-black/80 hover:border-accent/45 disabled:opacity-40"
                      >
                        {sceneAssetBusy === idx
                          ? "Working…"
                          : s.generated_image_path
                            ? "Regenerate image"
                            : "Generate image"}
                      </button>
                    </div>
                    {sceneAssetErr[idx] ? (
                      <p className="text-[11px] text-red-300/90">{sceneAssetErr[idx]}</p>
                    ) : null}
                    <label className="block text-[11px] text-black/50">
                      Description
                      <textarea
                        value={s.description}
                        onChange={(e) => {
                          const next = [...scenes];
                          next[idx] = { ...s, description: e.target.value };
                          setScenes(next);
                          persistWrite({ scenes: next });
                        }}
                        rows={3}
                        className="mt-1 w-full rounded-xl border border-line bg-[#F5F5F5] px-3 py-2 text-xs text-black/90 outline-none ring-accent/15 focus:ring-2"
                      />
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-line/80 bg-[#E8E8E8]/30 p-6 text-center text-sm text-black/55">
            {recommendation ? "Scenes appear here after AI drafts load (or tap Regenerate scenes)." : "Select an outfit on Style first."}
          </div>
        )}

        {logline ? (
          <div className="rounded-2xl border border-line bg-[#E8E8E8]/30 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-black/55">Storyboard logline</p>
            <textarea
              value={logline}
              onChange={(e) => setLogline(e.target.value)}
              rows={2}
              className="mt-2 w-full rounded-xl border border-line bg-[#F5F5F5] px-3 py-2 text-xs text-black/75 outline-none ring-accent/15 focus:ring-2"
            />
          </div>
        ) : null}

        {video ? (
          <div className="space-y-3">
            <div className="aspect-video w-full rounded-2xl border border-line bg-gradient-to-br from-[#E8E8E8] via-[#F5F5F5] to-[#E8E8E8]">
              <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">
                  {video.provider === "gemini_video"
                    ? "Gemini Veo"
                    : video.provider === "gemini_stub"
                      ? "Gemini (demo)"
                      : video.provider === "placeholder"
                        ? "Local (placeholder)"
                        : video.provider}
                </p>
                <p className="max-w-md text-sm text-black/75">{video.preview_message}</p>
              </div>
            </div>
            {video.video_url ? (
              <div className="space-y-2">
                <video className="w-full rounded-2xl border border-line" controls src={mediaUrl(video.video_url)} />
                <a
                  href={mediaUrl(video.video_url)}
                  download
                  className="inline-flex rounded-xl border border-line bg-[#E8E8E8] px-4 py-2 text-xs font-semibold text-black hover:border-accent/45"
                >
                  Download MP4
                </a>
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    </Card>
  );
}
