import { useEffect, useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import { ApiError, apiPostJson, mediaUrl } from "@/lib/api";
import type {
  GenerateVideoRequestBody,
  GenerateVideoResponse,
  PreviewReelCopyResponse,
  RecommendOutfitResponse,
  ReelSceneDraft,
} from "@/types";

export function RunwayReelPreviewPanel({
  recommendation,
  video,
  busy,
  faceAnchorPath,
  onUploadFaceAnchor,
  onPreviewReelCopy,
  onRenderVideo,
}: {
  recommendation: RecommendOutfitResponse | null;
  video: GenerateVideoResponse | null;
  busy: boolean;
  faceAnchorPath: string | null;
  onUploadFaceAnchor: (file: File) => Promise<void>;
  onPreviewReelCopy: (body: {
    scene_prompt: string;
    anchor_image_paths: string[];
    face_anchor_path: string | null;
    duration_seconds: number;
    face_anchor_present: boolean;
  }) => Promise<PreviewReelCopyResponse>;
  onRenderVideo: (body: GenerateVideoRequestBody) => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);
  const [copyBusy, setCopyBusy] = useState(false);
  const [scenePrompt, setScenePrompt] = useState("");
  const [narration, setNarration] = useState("");
  const [logline, setLogline] = useState("");
  const [scenes, setScenes] = useState<ReelSceneDraft[]>([]);

  const outfitSummary = useMemo(() => {
    if (!recommendation?.garments.length) return "";
    return recommendation.garments.map((g) => `${g.color} ${g.category}`).join(", ");
  }, [recommendation]);

  const wardrobeAnchors = useMemo(() => {
    if (!recommendation?.garments.length) return [];
    return recommendation.garments.map((g) => g.image_path).filter((p) => typeof p === "string" && p.startsWith("uploads/"));
  }, [recommendation]);

  useEffect(() => {
    if (!outfitSummary) return;
    setScenePrompt((prev) =>
      prev.trim().length ? prev : `${outfitSummary}. Runway walk-through with natural light and slow pan.`,
    );
  }, [outfitSummary]);

  const previewSrc = useMemo(() => {
    if (!faceAnchorPath) return null;
    return mediaUrl(faceAnchorPath);
  }, [faceAnchorPath]);

  const mergedNarration = useMemo(() => {
    if (scenes.length) {
      return scenes.map((s) => s.narration.trim()).filter(Boolean).join("\n\n");
    }
    return narration;
  }, [scenes, narration]);

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

  const runPreviewCopy = async () => {
    if (!scenePrompt.trim()) return;
    setCopyBusy(true);
    setUploadErr(null);
    try {
      const res = await onPreviewReelCopy({
        scene_prompt: scenePrompt.trim(),
        anchor_image_paths: wardrobeAnchors,
        face_anchor_path: faceAnchorPath,
        duration_seconds: 30,
        face_anchor_present: !!faceAnchorPath,
      });
      setLogline(res.description);
      setNarration(res.narration_text);
      setScenes(res.scenes);
    } catch (e) {
      setUploadErr(e instanceof ApiError ? e.body : "Couldn’t generate reel copy.");
    } finally {
      setCopyBusy(false);
    }
  };

  const runRender = async () => {
    if (!scenePrompt.trim()) return;
    await onRenderVideo({
      scene_prompt: scenePrompt.trim(),
      anchor_image_paths: wardrobeAnchors,
      face_anchor_image_path: faceAnchorPath,
      duration_seconds: 30,
      narration_text: mergedNarration.trim().length ? mergedNarration.trim() : null,
    });
  };

  const providerHint =
    "No MP4 is returned while MEDIA_PROVIDER is `mock`. Set `MEDIA_PROVIDER=gemini_video` and a valid `GEMINI_API_KEY` in backend/.env to render real video via Gemini Veo (billable).";

  return (
    <Card
      title="Gemini Reel Lab"
      subtitle="Generate editable runway copy per anchor, then render video when you are ready."
      right={
        <div className="flex flex-wrap justify-end gap-2">
          <button
            type="button"
            disabled={busy || copyBusy || !recommendation}
            onClick={() => void runPreviewCopy()}
            className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/50 disabled:opacity-40"
          >
            {copyBusy ? "Drafting…" : "Generate copy"}
          </button>
          <button
            type="button"
            disabled={busy || !recommendation}
            onClick={() => void runRender()}
            className="rounded-lg border border-accent/40 bg-accent/10 px-3 py-1.5 text-xs font-semibold text-mist hover:bg-accent/20 disabled:opacity-40"
          >
            {busy ? "Rendering…" : "Generate video"}
          </button>
        </div>
      }
    >
      <div className="space-y-3">
        <p className="text-xs text-mist/50">{providerHint}</p>

        <div
          className={[
            "rounded-2xl border border-line bg-ink-950/30 p-4 transition",
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
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Face anchor (optional)</p>
              <p className="mt-1 text-xs text-mist/45">
                Drop a selfie (JPG/PNG/WebP/HEIC). Used as continuity for image-to-video providers.
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
                className="rounded-xl border border-line bg-ink-950 px-4 py-2 text-xs font-semibold text-mist hover:border-accent/50 disabled:opacity-40"
              >
                {uploading ? `Uploading ${uploading}…` : faceAnchorPath ? "Replace selfie" : "Choose selfie"}
              </button>
            </div>
          </div>

          {previewSrc ? (
            <div className="mt-3 flex items-center gap-3">
              <div className="h-14 w-14 overflow-hidden rounded-xl border border-line bg-ink-950/40">
                <img src={previewSrc} alt="Face anchor" className="h-full w-full object-cover" loading="lazy" />
              </div>
              <p className="text-xs text-mist/55">{faceAnchorPath}</p>
            </div>
          ) : null}
          {uploadErr ? <p className="mt-3 text-xs text-red-300/80">{uploadErr}</p> : null}
        </div>

        <div className="rounded-2xl border border-line bg-ink-950/25 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Runway brief (editable)</p>
          <textarea
            value={scenePrompt}
            onChange={(e) => setScenePrompt(e.target.value)}
            rows={3}
            className="mt-2 w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/15 focus:ring-2"
          />
        </div>

        <div className="rounded-2xl border border-line bg-ink-950/25 p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Voiceover (editable)</p>
          <textarea
            value={narration}
            onChange={(e) => setNarration(e.target.value)}
            rows={4}
            className="mt-2 w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/15 focus:ring-2"
          />
          <p className="mt-2 text-[11px] text-mist/40">
            If you edit per-scene narration below, those lines replace this block when rendering.
          </p>
        </div>

        {logline ? (
          <div className="rounded-2xl border border-line bg-ink-950/30 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Storyboard logline</p>
            <textarea
              value={logline}
              onChange={(e) => setLogline(e.target.value)}
              rows={2}
              className="mt-2 w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-xs text-mist/75 outline-none ring-accent/15 focus:ring-2"
            />
          </div>
        ) : null}

        {scenes.length ? (
          <div className="space-y-3">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Per anchor / scene</p>
            {scenes.map((s, idx) => (
              <div key={`${s.anchor_image_path ?? "none"}-${idx}`} className="rounded-2xl border border-line bg-ink-950/30 p-4">
                <div className="flex flex-wrap items-start gap-3">
                  {s.anchor_image_path ? (
                    <div className="h-16 w-16 shrink-0 overflow-hidden rounded-xl border border-line bg-ink-950/40">
                      <img
                        src={mediaUrl(s.anchor_image_path)}
                        alt=""
                        className="h-full w-full object-cover"
                        loading="lazy"
                      />
                    </div>
                  ) : null}
                  <div className="min-w-0 flex-1 space-y-2">
                    <p className="text-[11px] text-mist/45">{s.anchor_image_path ?? "No image (single scene)"}</p>
                    <textarea
                      value={s.description}
                      onChange={(e) => {
                        const next = [...scenes];
                        next[idx] = { ...s, description: e.target.value };
                        setScenes(next);
                      }}
                      rows={2}
                      className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-xs text-mist/80 outline-none ring-accent/15 focus:ring-2"
                    />
                    <textarea
                      value={s.narration}
                      onChange={(e) => {
                        const next = [...scenes];
                        next[idx] = { ...s, narration: e.target.value };
                        setScenes(next);
                      }}
                      rows={2}
                      className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-xs text-mist/80 outline-none ring-accent/15 focus:ring-2"
                    />
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {!video && !logline && recommendation ? (
          <div className="rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-8 text-center text-sm text-mist/55">
            Click <span className="text-mist/80">Generate copy</span> to draft narration and per-anchor beats.
          </div>
        ) : null}

        {video ? (
          <div className="space-y-3">
            <div className="aspect-video w-full rounded-2xl border border-line bg-gradient-to-br from-ink-950 via-ink-900 to-ink-950">
              <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
                <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Runway</p>
                <p className="max-w-md text-sm text-mist/75">{video.preview_message}</p>
              </div>
            </div>
            {video.video_url ? (
              <div className="space-y-2">
                <video className="w-full rounded-2xl border border-line" controls src={mediaUrl(video.video_url)} />
                <a
                  href={mediaUrl(video.video_url)}
                  download
                  className="inline-flex rounded-xl border border-line bg-ink-950 px-4 py-2 text-xs font-semibold text-mist hover:border-accent/45"
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
