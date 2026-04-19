import type { RecommendOutfitResponse } from "@/types";
import { useImageLightbox } from "@/components/ui/ImageLightbox";

export function OutfitCard({ data }: { data: RecommendOutfitResponse }) {
  const { open } = useImageLightbox();
  const items = data.outfit_items.map((i) => {
    const g = data.garments.find((x) => x.id === i.garment_id);
    return {
      role: i.role,
      label: g ? `${g.color} ${g.category}` : i.garment_id,
      tags: g?.tags ?? [],
      imagePath: g?.image_path ?? null,
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
            <div className="mt-3 flex items-center gap-3">
              <div className="h-12 w-12 overflow-hidden rounded-xl border border-line bg-ink-950/40">
                {it.imagePath ? (
                  <img
                    src={`/api/${it.imagePath}`}
                    alt={it.label}
                    className="h-full w-full object-cover"
                    loading="lazy"
                    onClick={() => open(`/api/${it.imagePath}`, it.label)}
                    style={{ cursor: "zoom-in" }}
                    onError={(e) => {
                      (e.currentTarget as HTMLImageElement).style.display = "none";
                    }}
                  />
                ) : null}
              </div>
              <p className="text-lg font-semibold text-mist">{it.label}</p>
            </div>
            {it.tags.length ? <p className="mt-2 text-xs text-mist/50">{it.tags.slice(0, 4).join(" · ")}</p> : null}
          </div>
        ))}
      </div>
    </div>
  );
}

