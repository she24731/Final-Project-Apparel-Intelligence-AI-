import type { RecommendOutfitResponse } from "@/types";

export function OutfitCard({ data }: { data: RecommendOutfitResponse }) {
  const items = data.outfit_items.map((i) => {
    const g = data.garments.find((x) => x.id === i.garment_id);
    return {
      role: i.role,
      label: g ? `${g.color} ${g.category}` : i.garment_id,
      tags: g?.tags ?? [],
    };
  });

  return (
    <div className="rounded-3xl border border-line bg-ink-900/60 p-8 shadow-[0_0_0_1px_rgba(255,255,255,0.02)] backdrop-blur">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Recommended outfit</p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-mist">A clean, confident set</h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mist/70">{data.explanation}</p>
        </div>
        <div className="rounded-2xl border border-line bg-ink-950/50 px-4 py-3 text-right">
          <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-mist/45">Confidence</p>
          <p className="mt-1 text-2xl font-semibold text-mist">{data.confidence.toFixed(2)}</p>
        </div>
      </div>

      <div className="mt-8 grid gap-3 md:grid-cols-2">
        {items.map((it) => (
          <div key={`${it.role}-${it.label}`} className="rounded-2xl border border-line bg-ink-950/40 p-5">
            <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">{it.role}</p>
            <p className="mt-2 text-lg font-semibold text-mist">{it.label}</p>
            {it.tags.length ? <p className="mt-2 text-xs text-mist/50">{it.tags.slice(0, 4).join(" · ")}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

