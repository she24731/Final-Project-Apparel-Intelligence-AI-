import { OutfitCard } from "@/components/OutfitCard";
import { StyleContextBar, type StyleContext } from "@/components/StyleContextBar";
import type { RecommendOutfitResponse } from "@/types";

export function StylePage({
  context,
  onChange,
  onRecommend,
  onUseOutfit,
  busy,
  error,
  recommendation,
}: {
  context: StyleContext;
  onChange: (v: StyleContext) => void;
  onRecommend: () => Promise<void>;
  onUseOutfit: (outfit: RecommendOutfitResponse) => void;
  busy: boolean;
  error: string | null;
  recommendation: RecommendOutfitResponse | null;
}) {
  const isMissing = context.occasion.trim().length === 0 || context.weather.trim().length === 0 || context.vibe.trim().length === 0;
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Style</h2>
        <p className="mt-2 text-sm text-mist/65">Enter the context. We’ll recommend one outfit you can trust.</p>
      </section>

      <StyleContextBar value={context} onChange={onChange} />

      <div className="flex flex-col items-center gap-4 py-2">
        <button
          type="button"
          disabled={busy}
          onClick={() => void onRecommend()}
          className="w-full max-w-sm rounded-2xl bg-accent px-6 py-4 text-base font-semibold text-ink-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {busy ? "Recommending…" : "Recommend outfit"}
        </button>
        {isMissing ? <p className="text-xs text-mist/45">Tip: fill Occasion, Weather, and Vibe for a more tailored result.</p> : null}
        {error ? <p className="text-sm text-red-300">{error}</p> : null}
      </div>

      {!recommendation ? (
        <div className="rounded-3xl border border-dashed border-line/80 bg-ink-950/20 p-10 text-center">
          <p className="text-sm text-mist/70">No recommendation yet.</p>
          <p className="mt-2 text-xs text-mist/45">Upload wardrobe items first, then run “Recommend outfit.”</p>
        </div>
      ) : (
        <div className="space-y-4">
          <OutfitCard data={recommendation} />
          <div className="flex justify-end">
            <button
              type="button"
              onClick={() => onUseOutfit(recommendation)}
              className="rounded-2xl bg-accent px-5 py-3 text-sm font-semibold text-ink-950 transition hover:opacity-95"
            >
              Use this outfit in Content
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

