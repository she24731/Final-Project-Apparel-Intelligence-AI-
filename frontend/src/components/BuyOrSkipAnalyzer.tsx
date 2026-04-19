import { useMemo, useRef, useState } from "react";
import { Card } from "@/components/ui/Card";
import { useImageLightbox } from "@/components/ui/ImageLightbox";
import type { GarmentRecord, PurchaseAnalysisResponse } from "@/types";

export function BuyOrSkipAnalyzer({
  wardrobe,
  busy,
  error,
  result,
  onAnalyze,
  onUseCombo,
  onIngestCandidate,
  onCleanupCandidate,
}: {
  wardrobe: GarmentRecord[];
  busy: boolean;
  error: string | null;
  result: PurchaseAnalysisResponse | null;
  onAnalyze: (candidate: GarmentRecord) => Promise<void>;
  onUseCombo: (opts: { title: string; garmentIds: string[]; occasion?: string | null; description?: string | null }) => void;
  onIngestCandidate: (file: File, hints: string | undefined) => Promise<GarmentRecord>;
  onCleanupCandidate: (id: string) => Promise<void>;
}) {
  const { open } = useImageLightbox();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const [category, setCategory] = useState("shoes");
  const [color, setColor] = useState("cognac");
  const [formality, setFormality] = useState(0.55);
  const [notes, setNotes] = useState("");
  const [candidate, setCandidate] = useState<GarmentRecord | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const [isDragging, setIsDragging] = useState(false);

  const wardrobeSize = wardrobe.length;
  const canAnalyze = !busy;

  const candidatePreview = useMemo(() => {
    if (!candidate?.image_path) return null;
    return `/api/${candidate.image_path}`;
  }, [candidate?.image_path]);

  const removeCandidatePhoto = async () => {
    setLocalError(null);
    if (candidate?.id && !candidate.id.startsWith("candidate-")) {
      try {
        await onCleanupCandidate(candidate.id);
      } catch {
        // ignore
      }
    }
    setCandidate(null);
  };

  const ingestCandidateFile = async (file: File) => {
    setLocalError(null);
    if (file.size > 10 * 1024 * 1024) {
      setLocalError(`“${file.name}” is over 10MB. Please choose a smaller image.`);
      return;
    }
    try {
      const ingested = await onIngestCandidate(file, notes.trim() || undefined);
      setCandidate(ingested);
      setCategory(ingested.category);
      setColor(ingested.color);
      setFormality(ingested.formality_score);
    } catch {
      setLocalError("Couldn’t upload the candidate photo. You can still describe it below.");
    }
  };

  const analyze = async () => {
    setLocalError(null);
    const base: GarmentRecord =
      candidate ??
      ({
        id: `candidate-${Date.now()}`,
        category,
        color,
        formality_score: formality,
        season: "all-season",
        tags: ["candidate"],
        image_path: "uploads/candidate_stub.png",
        embedding: [],
      } satisfies GarmentRecord);

    const withNotes: GarmentRecord = {
      ...base,
      category,
      color,
      formality_score: formality,
      tags: [
        ...(base.tags ?? []),
        ...(notes.trim()
          ? notes
              .split(",")
              .map((s) => s.trim())
              .filter(Boolean)
          : []),
      ],
    };
    // If the user edited parameters after uploading a photo, clear embedding so backend recomputes
    // a deterministic embedding from the edited metadata (so scores change).
    if (candidate) withNotes.embedding = [];

    try {
      await onAnalyze(withNotes);
    } finally {
      // Best-effort cleanup if we temporarily ingested a candidate image on the backend.
      if (candidate?.id && candidate.id && !candidate.id.startsWith("candidate-")) {
        try {
          await onCleanupCandidate(candidate.id);
        } catch {
          // ignore
        }
      }
    }
  };

  return (
    <Card title="Analyze a purchase" subtitle="Upload the item you’re considering, or describe it. We’ll score fit vs your wardrobe.">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Candidate item (optional photo)</p>
          <div
            className={[
              "rounded-3xl border border-dashed p-4 transition",
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
              const f = e.dataTransfer.files?.[0] ?? null;
              if (!f) return;
              void ingestCandidateFile(f);
            }}
          >
            <div className="flex items-center gap-3">
              <div className="h-14 w-14 overflow-hidden rounded-2xl border border-line bg-ink-950/40">
                {candidatePreview ? (
                  <img
                    src={candidatePreview}
                    alt="Candidate preview"
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onClick={() => open(candidatePreview, "Candidate photo")}
                    style={{ cursor: "zoom-in" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : null}
              </div>
              <div className="flex flex-1 items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-mist">{candidate ? "Photo added" : "Drop an image here"}</p>
                  <p className="mt-1 text-xs text-mist/55">Or click to choose. JPG/PNG/WebP/HEIC. Max 10MB.</p>
                </div>
                <button
                  type="button"
                  disabled={busy}
                  onClick={() => inputRef.current?.click()}
                  className="rounded-2xl border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Choose photo
                </button>
                {candidate ? (
                  <button
                    type="button"
                    disabled={busy}
                    onClick={() => void removeCandidatePhoto()}
                    className="rounded-2xl border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist/70 hover:border-red-400/40 hover:text-mist disabled:cursor-not-allowed disabled:opacity-40"
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </div>
          </div>
          <input
            ref={inputRef}
            type="file"
            accept="image/*"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0] ?? null;
              e.target.value = "";
              if (!f) return;
              void ingestCandidateFile(f);
            }}
          />

          <label className="space-y-2 text-xs font-medium text-mist/70">
            Description / notes (comma-separated)
            <input
              value={notes}
              onChange={(e) => {
                setNotes(e.target.value);
                if (candidate) setCandidate({ ...candidate, embedding: [] });
              }}
              placeholder="e.g. slim fit, black, leather, no logos"
              className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none focus:ring-2 focus:ring-accent/30"
            />
          </label>
        </div>

        <div className="space-y-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Candidate details</p>
        <label className="space-y-2 text-xs font-medium text-mist/70">
          Category
          <select
            value={category}
            onChange={(e) => {
              setCategory(e.target.value);
              if (candidate) setCandidate({ ...candidate, embedding: [] });
            }}
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none focus:ring-2 focus:ring-accent/30"
          >
            <option value="top">top</option>
            <option value="bottom">bottom</option>
            <option value="outerwear">outerwear</option>
            <option value="shoes">shoes</option>
            <option value="accessory">accessory</option>
          </select>
        </label>
        <label className="space-y-2 text-xs font-medium text-mist/70">
          Color
          <input
            value={color}
            onChange={(e) => {
              setColor(e.target.value);
              if (candidate) setCandidate({ ...candidate, embedding: [] });
            }}
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none focus:ring-2 focus:ring-accent/30"
          />
        </label>
        <label className="space-y-2 text-xs font-medium text-mist/70">
          Formality (0–1)
          <input
            type="number"
            step="0.01"
            min={0}
            max={1}
            value={formality}
            onChange={(e) => {
              setFormality(Number(e.target.value));
              if (candidate) setCandidate({ ...candidate, embedding: [] });
            }}
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none focus:ring-2 focus:ring-accent/30"
          />
        </label>
        </div>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <div>
          <p className="text-xs text-mist/50">Wardrobe size: {wardrobeSize}</p>
          {wardrobeSize === 0 ? (
            <p className="mt-1 text-[11px] text-mist/45">
              Tip: upload a few wardrobe items first for a real “buy / no-buy” read. You can still run a demo analysis now.
            </p>
          ) : null}
        </div>
        <button
          type="button"
          disabled={!canAnalyze}
          onClick={() => void analyze()}
          className="rounded-xl border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Scoring…" : "Analyze purchase"}
        </button>
      </div>

      {localError ? <p className="mt-3 text-xs text-red-300">{localError}</p> : null}
      {error ? <p className="mt-2 text-xs text-red-300">{error}</p> : null}

      {!result ? (
        <div className="mt-5 rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-6 text-center text-sm text-mist/55">
          Run an analysis to see recommendation, scores, and rationale.
        </div>
      ) : (
        <div className="mt-5 space-y-4">
          <div className="grid gap-4 md:grid-cols-3">
            <ScoreTile label="Compatibility" value={result.compatibility_score} />
            <ScoreTile label="Outfit potential" value={result.outfit_combination_potential} isInt />
            <div className="rounded-xl border border-line bg-ink-950/40 p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Verdict</p>
              <p className="mt-2 text-2xl font-semibold text-mist">{result.recommendation}</p>
            </div>
          </div>

          {result.decision_criteria?.length ? (
            <div className="rounded-2xl border border-line bg-ink-950/30 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Verdict criteria</p>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-mist/60">
                {result.decision_criteria.map((c) => (
                  <li key={c}>{c}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {result.outfit_suggestions?.length ? (
            <div className="rounded-2xl border border-line bg-ink-950/30 p-5">
              <p className="text-xs font-semibold uppercase tracking-[0.18em] text-mist/55">Fits with these outfits</p>
              <p className="mt-1 text-xs text-mist/45">
                Outfit potential counts <span className="font-semibold">estimated combinations</span>. Below are the combinations we generated for this analysis.
              </p>
              <div className="mt-3 grid gap-3 md:grid-cols-3">
                {result.outfit_suggestions.map((sug, idx) => (
                  <div key={sug.title} className="rounded-2xl border border-line bg-ink-950/40 p-4">
                    <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-mist/55">
                      Combo {idx + 1}{sug.occasion ? ` · ${sug.occasion}` : ""}
                    </p>
                    <p className="mt-2 text-sm font-semibold text-mist">{sug.title}</p>
                    {sug.description ? <p className="mt-1 text-xs text-mist/55">{sug.description}</p> : null}
                    <div className="mt-3 flex flex-wrap gap-2">
                      {sug.garment_ids.map((gid) => {
                        const g = wardrobe.find((w) => w.id === gid);
                        if (!g) return null;
                        const src = `/api/${g.image_path}`;
                        return (
                          <div key={gid} className="flex items-center gap-2 rounded-xl border border-line bg-ink-950/40 px-2 py-2">
                            <div className="h-9 w-9 overflow-hidden rounded-lg border border-line bg-ink-950/40">
                              <img
                                src={src}
                                alt={`${g.color} ${g.category}`}
                                className="h-full w-full object-cover"
                                loading="lazy"
                                onClick={() => open(src, `${g.category} · ${g.color}`)}
                                style={{ cursor: "zoom-in" }}
                                onError={(e) => {
                                  (e.currentTarget as HTMLImageElement).style.display = "none";
                                }}
                              />
                            </div>
                            <div>
                              <p className="text-xs font-semibold text-mist">{g.category}</p>
                              <p className="text-[11px] text-mist/55">{g.color}</p>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                    <div className="mt-4 flex justify-end">
                      <button
                        type="button"
                        onClick={() =>
                          onUseCombo({
                            title: sug.title,
                            garmentIds: sug.garment_ids,
                            occasion: sug.occasion,
                            description: sug.description,
                          })
                        }
                        className="rounded-xl bg-accent px-4 py-2 text-xs font-semibold text-ink-950 hover:opacity-95"
                      >
                        Use this combo in Content
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div>
            <p className="text-sm text-mist/80">{result.explanation}</p>
            <ul className="mt-3 list-disc space-y-1 pl-5 text-xs text-mist/60">
              {result.rationale_bullets.map((b) => (
                <li key={b}>{b}</li>
              ))}
            </ul>
          </div>
        </div>
      )}
    </Card>
  );
}

function ScoreTile({ label, value, isInt }: { label: string; value: number; isInt?: boolean }) {
  return (
    <div className="rounded-xl border border-line bg-ink-950/40 p-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">{label}</p>
      <p className="mt-2 text-3xl font-semibold text-mist">{isInt ? value : value.toFixed(2)}</p>
    </div>
  );
}
