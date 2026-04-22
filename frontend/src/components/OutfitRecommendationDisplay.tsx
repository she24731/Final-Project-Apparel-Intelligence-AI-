import { Card } from "@/components/ui/Card";
import type { RecommendOutfitResponse } from "@/types";

export function OutfitRecommendationDisplay({ data, busy }: { data: RecommendOutfitResponse | null; busy: boolean }) {
  return (
    <Card
      title="Outfit recommendation"
      subtitle="A single clean recommendation with a short explanation."
      right={busy ? <span className="text-xs text-black/50">Updating…</span> : null}
    >
      {!data ? (
        <div className="rounded-xl border border-dashed border-line/80 bg-[#E8E8E8]/30 p-8 text-center text-sm text-black/55">
          Submit context to generate a recommendation.
        </div>
      ) : (
        <div className="space-y-5">
          <div className="flex flex-wrap items-end justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-wide text-black/50">Confidence</p>
              <p className="mt-1 text-3xl font-semibold text-black">{data.confidence.toFixed(2)}</p>
            </div>
          </div>

          <p className="text-sm leading-relaxed text-black/80">{data.explanation}</p>

          <div className="grid gap-3 md:grid-cols-2">
            {data.outfit_items.map((item) => {
              const g = data.garments.find((x) => x.id === item.garment_id);
              return (
                <div key={`${item.garment_id}-${item.role}`} className="rounded-2xl border border-line bg-[#E8E8E8] p-4">
                  <p className="text-xs font-semibold uppercase tracking-wide text-accent">{item.role}</p>
                  <p className="mt-2 text-lg font-semibold text-black">{g ? `${g.category} · ${g.color}` : item.garment_id}</p>
                  <p className="mt-2 text-xs text-black/55">{g?.tags.join(" · ") ?? "—"}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}
    </Card>
  );
}
