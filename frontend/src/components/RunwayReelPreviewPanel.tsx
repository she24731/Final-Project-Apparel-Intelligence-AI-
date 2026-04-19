import { useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import type { GenerateVideoResponse } from "@/types";
import { ApiError } from "@/lib/api";

export function RunwayReelPreviewPanel({
  video,
  busy,
  faceAnchorPath,
  onUploadFaceAnchor,
  onGenerate,
}: {
  video: GenerateVideoResponse | null;
  busy: boolean;
  faceAnchorPath: string | null;
  onUploadFaceAnchor: (file: File) => Promise<void>;
  onGenerate: () => Promise<void>;
}) {
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState<string | null>(null);
  const [uploadErr, setUploadErr] = useState<string | null>(null);

  const previewSrc = useMemo(() => {
    if (!faceAnchorPath) return null;
    // Backend serves /uploads/* under /api/uploads/*
    return `/api/${faceAnchorPath}`;
  }, [faceAnchorPath]);

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

  return (
    <Card
      title="Gemini Reel Lab"
      subtitle="Add a selfie anchor (optional). We’ll auto-write description + narration, then stage a 30s reel."
      right={
        <button
          type="button"
          disabled={busy}
          onClick={() => void onGenerate()}
          className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/50 disabled:opacity-40"
        >
          {busy ? "Staging…" : "Generate preview"}
        </button>
      }
    >
      <div className="space-y-3">
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
                Drop a selfie here (JPG/PNG/WebP/HEIC). We’ll use it as an anchor image for the reel.
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

      {!video ? (
        <div className="rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-8 text-center text-sm text-mist/55">
          Generate a preview to see the runway concept.
        </div>
      ) : (
        <div className="space-y-3">
          {(video.description || video.narration_text) ? (
            <div className="rounded-2xl border border-line bg-ink-950/30 p-4">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Generated</p>
              {video.description ? <p className="mt-2 text-xs text-mist/65">{video.description}</p> : null}
              {video.narration_text ? (
                <div className="mt-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-mist/55">Narration</p>
                  <p className="mt-1 text-sm leading-relaxed text-mist/80">{video.narration_text}</p>
                </div>
              ) : null}
            </div>
          ) : null}
          <div className="aspect-video w-full rounded-2xl border border-line bg-gradient-to-br from-ink-950 via-ink-900 to-ink-950">
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Runway</p>
              <p className="max-w-md text-sm text-mist/75">{video.preview_message}</p>
            </div>
          </div>
          {video.video_url ? (
            <video className="w-full rounded-2xl border border-line" controls src={video.video_url} />
          ) : null}
        </div>
      )}
      </div>
    </Card>
  );
}
