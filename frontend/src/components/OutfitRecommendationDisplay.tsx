import { Card } from "@/components/ui/Card";
import type { RecommendOutfitResponse } from "@/types";

export function OutfitRecommendationDisplay({ data, busy }: { data: RecommendOutfitResponse | null; busy: boolean }) {
  return (
    <Card
      title="Outfit recommendation"
      subtitle="A single clean recommendation with a short explanation."
      right={busy ? <span className="text-xs text-mist/50">Updating…</span> : null}
    >
      {!data ? (
        <div className="rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-8 text-center text-sm text-mist/55">
          Submit context to generate a recommendation.
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Confidence</p>
              <p className="mt-1 text-3xl font-semibold text-mist">{data.confidence.toFixed(2)}</p>
            </div>
          </div>

          <p className="text-sm leading-relaxed text-mist/80">{data.explanation}</p>

          <div className="grid gap-3 md:grid-cols-2">
            {data.outfit_items.map((item) => {
              const g = data.garments.find((x) => x.id === item.garment_id);
              return (
                <div key={`${item.garment_id}-${item.role}`} className="rounded-2xl border border-line bg-ink-950/50 p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-accent">{item.role}</p>
                  <p className="mt-2 text-lg font-semibold text-mist">{g ? `${g.category} · ${g.color}` : item.garment_id}</p>
                  <p className="mt-2 text-xs text-mist/55">{g?.tags.join(" · ") ?? "—"}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}
