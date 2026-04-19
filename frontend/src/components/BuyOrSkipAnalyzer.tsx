import { useState } from "react";
import { Card } from "@/components/ui/Card";
import type { GarmentRecord, PurchaseAnalysisResponse } from "@/types";

export function BuyOrSkipAnalyzer({
  wardrobe,
  busy,
  error,
  result,
  onAnalyze,
}: {
  wardrobe: GarmentRecord[];
  busy: boolean;
  error: string | null;
  result: PurchaseAnalysisResponse | null;
  onAnalyze: (candidate: GarmentRecord) => Promise<void>;
}) {
  const [category, setCategory] = useState("shoes");
  const [color, setColor] = useState("cognac");
  const [formality, setFormality] = useState(0.55);

  return (
    <Card title="Buy / Skip analyzer" subtitle="Compatibility + versatility heuristics with optional LLM overlay.">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="space-y-2 text-xs font-medium text-mist/70">
          Category
          <select
            value={category}
            onChange={(e) => setCategory(e.target.value)}
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
            onChange={(e) => setColor(e.target.value)}
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
            onChange={(e) => setFormality(Number(e.target.value))}
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none focus:ring-2 focus:ring-accent/30"
          />
        </label>
      </div>

      <div className="mt-4 flex items-center justify-between gap-3">
        <p className="text-xs text-mist/50">Wardrobe size: {wardrobe.length}</p>
        <button
          type="button"
          disabled={busy || wardrobe.length === 0}
          onClick={() =>
            void onAnalyze({
              id: `candidate-${Date.now()}`,
              category,
              color,
              formality_score: formality,
              season: "all-season",
              tags: ["candidate"],
              image_path: "uploads/candidate_stub.png",
              embedding: [],
            })
          }
          className="rounded-xl border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist hover:border-accent/50 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Scoring…" : "Analyze purchase"}
        </button>
      </div>

      {error ? <p className="mt-3 text-xs text-red-300">{error}</p> : null}

      {!result ? (
        <div className="mt-5 rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-6 text-center text-sm text-mist/55">
          Run an analysis to see recommendation, scores, and rationale.
        </div>
      ) : (
        <div className="mt-5 grid gap-4 md:grid-cols-3">
          <ScoreTile label="Compatibility" value={result.compatibility_score} />
          <ScoreTile label="Outfit potential" value={result.outfit_combination_potential} isInt />
          <div className="rounded-xl border border-line bg-ink-950/40 p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Verdict</p>
            <p className="mt-2 text-2xl font-semibold text-mist">{result.recommendation}</p>
            <p className="mt-2 text-xs text-mist/55">{result.used_live_agent ? "LLM overlay on" : "Deterministic"}</p>
          </div>
          <div className="md:col-span-3">
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
