import { useEffect, useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import { useImageLightbox } from "@/components/ui/ImageLightbox";
import { mediaUrl } from "@/lib/api";
import type { GarmentRecord } from "@/types";

export function WardrobeUploadPanel({
  items,
  busy,
  error,
  onIngest,
  onDelete,
  onRemoveAll,
}: {
  items: GarmentRecord[];
  busy: boolean;
  error: string | null;
  onIngest: (file: File, hints: string | undefined) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onRemoveAll: () => Promise<void>;
}) {
  const { open } = useImageLightbox();
  const [hints, setHints] = useState("");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const [uploadTotal, setUploadTotal] = useState(0);
  const [uploadDone, setUploadDone] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const empty = items.length === 0;
  const [prevCount, setPrevCount] = useState(items.length);

  const summary = useMemo(() => `${items.length} item${items.length === 1 ? "" : "s"} indexed`, [items.length]);

  const uploadMany = async (files: FileList | File[]) => {
    const arr = Array.from(files);
    if (arr.length === 0) return;
    const tooBig = arr.find((f) => f.size > 10 * 1024 * 1024);
    if (tooBig) {
      alert(`“${tooBig.name}” is over 10MB. Please choose smaller images.`);
      return;
    }
    // Apply the current hints to the whole batch (optional).
    const batchHints = hints.trim() || undefined;
    setHints("");
    setUploadTotal(arr.length);
    setUploadDone(0);
    setToast(`Uploading 0/${arr.length}… (${arr.length} left)`);
    for (const f of arr) {
      setSelectedName(f.name);
      // Upload sequentially for stability (avoids flooding API + keeps UI predictable).
      // eslint-disable-next-line no-await-in-loop
      await onIngest(f, batchHints);
      setUploadDone((d) => {
        const next = Math.min(arr.length, d + 1);
        const left = Math.max(0, arr.length - next);
        setToast(`Uploading ${next}/${arr.length}… (${left} left)`);
        return next;
      });
    }
    setSelectedName(null);
    setUploadTotal(0);
    setUploadDone(0);
    setToast(`Added ${arr.length} item${arr.length === 1 ? "" : "s"} to your wardrobe.`);
  };

  useEffect(() => {
    // Detect successful add (count increased after an upload attempt).
    if (!busy && selectedName && items.length > prevCount) {
      setToast(`Added “${selectedName}” to your wardrobe.`);
      setSelectedName(null);
    }
    setPrevCount(items.length);
  }, [busy, items.length, prevCount, selectedName]);

  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast(null), 2800);
    return () => window.clearTimeout(t);
  }, [toast]);

  return (
    <Card
      title="Upload items"
      subtitle="Add a few pieces. We’ll keep the details organized for styling and purchase decisions."
      right={<span className="text-xs text-black/50">{summary}</span>}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-black/70">Image</label>

          <div
            className={[
              "rounded-3xl border border-dashed p-5 transition",
              isDragging ? "border-accent/70 bg-[#E8E8E8]" : "border-line/80 bg-[#F5F5F5]",
            ].join(" ")}
            onDragEnter={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(true);
            }}
            onDragOver={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(true);
            }}
            onDragLeave={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(false);
            }}
            onDrop={(e) => {
              e.preventDefault();
              e.stopPropagation();
              setIsDragging(false);
              const files = e.dataTransfer.files;
              void uploadMany(files);
            }}
          >
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <p className="text-sm font-semibold text-black">Drop images here</p>
                <p className="mt-1 text-xs text-black/55">Or choose multiple files. We'll add them all to your wardrobe.</p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => inputRef.current?.click()}
                className="rounded-2xl bg-mist px-5 py-3 text-sm font-semibold text-ink-950 disabled:opacity-40"
              >
                Choose photos
              </button>
            </div>
          </div>

          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            multiple
            className="hidden"
            onChange={(e) => {
              const files = e.target.files;
              // Clear immediately so selecting the same file again works.
              e.target.value = "";
              if (!files || files.length === 0) return;
              void uploadMany(files);
            }}
          />
          {toast ? (
            <div className="rounded-2xl border border-accent/25 bg-[#E8E8E8] px-4 py-3 text-sm text-black">
              {toast}
            </div>
          ) : null}
          <p className="text-xs text-black/45">Accepted: JPG, PNG, WebP, HEIC/HEIF, AVIF, GIF (max 10MB).</p>
          <label className="block text-xs font-medium text-black/70">Hints (optional)</label>
          <p className="text-xs text-black/45">
            A short description to help labeling (e.g., <span className="font-mono">wool, winter, navy</span>). This improves
            recommendations when image analysis is limited.
          </p>
          <input
            value={hints}
            onChange={(e) => setHints(e.target.value)}
            placeholder="wool, winter, navy…"
            className="w-full rounded-xl border border-line bg-[#F5F5F5] px-3 py-2 text-sm text-black outline-none ring-accent/30 placeholder:text-black/35 focus:ring-2"
          />
          {busy ? (
            <p className="text-xs text-black/60">
              Uploading{selectedName ? `: ${selectedName}` : ""}…
              {uploadTotal > 0 ? (
                <span className="ml-2 text-black/45">
                  ({uploadDone}/{uploadTotal} · {Math.max(0, uploadTotal - uploadDone)} left)
                </span>
              ) : null}
            </p>
          ) : null}
          {error ? <p className="text-xs text-red-300">{error}</p> : null}
        </div>

        <div className="rounded-xl border border-line bg-[#E8E8E8] p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-black/50">Your wardrobe</p>
            <div className="flex items-center">
              {!empty ? (
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => void onRemoveAll()}
                  className="rounded-full border border-line bg-[#E8E8E8] px-3 py-1 text-[11px] font-semibold text-black/70 hover:border-red-400/40 hover:text-black disabled:opacity-40"
                >
                  Remove all
                </button>
              ) : null}
            </div>
          </div>
          {empty ? (
            <div className="flex h-full min-h-[140px] flex-col items-center justify-center text-center">
              <p className="text-sm text-black/70">No garments yet</p>
              <p className="mt-2 max-w-xs text-xs text-black/45">Upload a piece to populate your digital wardrobe.</p>
            </div>
          ) : (
            <ul className="max-h-56 space-y-3 overflow-auto pr-1 text-sm">
              {items.map((g) => (
                <li key={g.id} className="flex items-start justify-between gap-3 border-b border-line/60 pb-3 last:border-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    <div className="h-12 w-12 overflow-hidden rounded-xl border border-line bg-[#F5F5F5]">
                      <img
                        src={mediaUrl(g.image_path)}
                        alt={`${g.category} ${g.color}`}
                        className="h-full w-full object-cover"
                        loading="lazy"
                        onClick={() => open(mediaUrl(g.image_path), `${g.category} · ${g.color}`)}
                        style={{ cursor: "zoom-in" }}
                        onError={(e) => {
                          // Hide broken thumbnails quietly.
                          (e.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </div>
                    <div>
                      <p className="font-medium text-black">
                        {g.category} · <span className="text-black/70">{g.color}</span>
                      </p>
                      <p className="mt-1 text-xs text-black/50">{g.tags.slice(0, 4).join(" · ")}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-line bg-[#E8E8E8] px-3 py-1 text-[11px] text-black/60">
                      In wardrobe
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onDelete(g.id)}
                      className="rounded-full border border-line bg-[#E8E8E8] px-3 py-1 text-[11px] font-semibold text-black/70 hover:border-red-400/40 hover:text-black disabled:opacity-40"
                    >
                      Remove
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}
