import { useEffect, useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import { useImageLightbox } from "@/components/ui/ImageLightbox";
import type { GarmentRecord } from "@/types";

export function WardrobeUploadPanel({
  items,
  busy,
  error,
  onIngest,
  onDelete,
}: {
  items: GarmentRecord[];
  busy: boolean;
  error: string | null;
  onIngest: (file: File, hints: string | undefined) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
}) {
  const { open } = useImageLightbox();
  const [hints, setHints] = useState("");
  const [selectedName, setSelectedName] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);
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
    setToast(`Uploading ${arr.length} image${arr.length === 1 ? "" : "s"}…`);
    for (const f of arr) {
      setSelectedName(f.name);
      // Upload sequentially for stability (avoids flooding API + keeps UI predictable).
      // eslint-disable-next-line no-await-in-loop
      await onIngest(f, batchHints);
    }
    setSelectedName(null);
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
      right={<span className="text-xs text-mist/50">{summary}</span>}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-mist/70">Image</label>

          <div
            className={[
              "rounded-3xl border border-dashed p-5 transition",
              isDragging ? "border-accent/70 bg-ink-950/50" : "border-line/80 bg-ink-950/20",
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
                <p className="text-sm font-semibold text-mist">Drop images here</p>
                <p className="mt-1 text-xs text-mist/55">
                  Or choose multiple files. We’ll add them all to your wardrobe.
                </p>
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

          <div className="flex items-center gap-3">
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
            <button
              type="button"
              disabled={busy}
              onClick={() => inputRef.current?.click()}
              className="rounded-xl border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist hover:border-accent/40 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Choose photos
            </button>
            <span className="text-sm text-mist/60">{selectedName ?? "No file selected"}</span>
          </div>
          {toast ? (
            <div className="rounded-2xl border border-accent/25 bg-ink-950/40 px-4 py-3 text-sm text-mist/80">
              {toast}
            </div>
          ) : null}
          <p className="text-xs text-mist/45">Accepted: JPG, PNG, WebP, HEIC/HEIF, AVIF, GIF (max 10MB).</p>
          <label className="block text-xs font-medium text-mist/70">Hints (optional)</label>
          <p className="text-xs text-mist/45">
            A short description to help labeling (e.g., <span className="font-mono">wool, winter, navy</span>). This improves
            recommendations when image analysis is limited.
          </p>
          <input
            value={hints}
            onChange={(e) => setHints(e.target.value)}
            placeholder="wool, winter, navy…"
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/30 placeholder:text-mist/35 focus:ring-2"
          />
          {busy ? <p className="text-xs text-mist/60">Uploading{selectedName ? `: ${selectedName}` : ""}…</p> : null}
          {error ? <p className="text-xs text-red-300">{error}</p> : null}
        </div>

        <div className="rounded-xl border border-line bg-ink-950/40 p-4">
          <div className="mb-3 flex items-center justify-between">
            <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Your wardrobe</p>
            <p className="text-xs text-mist/45">Used in Style + Buy Analyzer</p>
          </div>
          {empty ? (
            <div className="flex h-full min-h-[140px] flex-col items-center justify-center text-center">
              <p className="text-sm text-mist/70">No garments yet</p>
              <p className="mt-2 max-w-xs text-xs text-mist/45">Upload a piece to populate your digital wardrobe.</p>
            </div>
          ) : (
            <ul className="max-h-56 space-y-3 overflow-auto pr-1 text-sm">
              {items.map((g) => (
                <li key={g.id} className="flex items-start justify-between gap-3 border-b border-line/60 pb-3 last:border-0 last:pb-0">
                  <div className="flex items-start gap-3">
                    <div className="h-12 w-12 overflow-hidden rounded-xl border border-line bg-ink-950/40">
                      <img
                        src={`/api/${g.image_path}`}
                        alt={`${g.category} ${g.color}`}
                        className="h-full w-full object-cover"
                        loading="lazy"
                        onClick={() => open(`/api/${g.image_path}`, `${g.category} · ${g.color}`)}
                        style={{ cursor: "zoom-in" }}
                        onError={(e) => {
                          // Hide broken thumbnails quietly.
                          (e.currentTarget as HTMLImageElement).style.display = "none";
                        }}
                      />
                    </div>
                    <div>
                      <p className="font-medium text-mist">
                        {g.category} · <span className="text-mist/70">{g.color}</span>
                      </p>
                      <p className="mt-1 text-xs text-mist/50">{g.tags.slice(0, 4).join(" · ")}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="rounded-full border border-line bg-ink-950/50 px-3 py-1 text-[11px] text-mist/60">
                      In wardrobe
                    </span>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => void onDelete(g.id)}
                      className="rounded-full border border-line bg-ink-950/50 px-3 py-1 text-[11px] font-semibold text-mist/70 hover:border-red-400/40 hover:text-mist disabled:opacity-40"
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
