import { useMemo, useState } from "react";
import { Card } from "@/components/ui/Card";
import type { GarmentRecord } from "@/types";

export function WardrobeUploadPanel({
  items,
  busy,
  error,
  onIngest,
}: {
  items: GarmentRecord[];
  busy: boolean;
  error: string | null;
  onIngest: (file: File, hints: string | undefined) => Promise<void>;
}) {
  const [hints, setHints] = useState("");
  const empty = items.length === 0;

  const summary = useMemo(() => `${items.length} item${items.length === 1 ? "" : "s"} indexed`, [items.length]);

  return (
    <Card
      title="Upload items"
      subtitle="Add a few pieces. We’ll keep the details organized for styling and purchase decisions."
      right={<span className="text-xs text-mist/50">{summary}</span>}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="space-y-3">
          <label className="block text-xs font-medium text-mist/70">Image</label>
          <input
            type="file"
            accept="image/*"
            disabled={busy}
            onChange={async (e) => {
              const f = e.target.files?.[0];
              if (!f) return;
              await onIngest(f, hints.trim() || undefined);
              e.target.value = "";
            }}
            className="block w-full cursor-pointer text-sm text-mist/80 file:mr-4 file:rounded-lg file:border-0 file:bg-ink-800 file:px-4 file:py-2 file:text-xs file:font-semibold file:text-mist hover:file:bg-ink-800/80"
          />
          <label className="block text-xs font-medium text-mist/70">Hints (optional)</label>
          <input
            value={hints}
            onChange={(e) => setHints(e.target.value)}
            placeholder="wool, winter, navy…"
            className="w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/30 placeholder:text-mist/35 focus:ring-2"
          />
          {busy ? <p className="text-xs text-mist/60">Adding…</p> : null}
          {error ? <p className="text-xs text-red-300">{error}</p> : null}
        </div>

        <div className="rounded-xl border border-line bg-ink-950/40 p-4">
          {empty ? (
            <div className="flex h-full min-h-[140px] flex-col items-center justify-center text-center">
              <p className="text-sm text-mist/70">No garments yet</p>
              <p className="mt-2 max-w-xs text-xs text-mist/45">Upload a piece to populate your digital wardrobe.</p>
            </div>
          ) : (
            <ul className="max-h-56 space-y-3 overflow-auto pr-1 text-sm">
              {items.map((g) => (
                <li key={g.id} className="flex items-start justify-between gap-3 border-b border-line/60 pb-3 last:border-0 last:pb-0">
                  <div>
                    <p className="font-medium text-mist">
                      {g.category} · <span className="text-mist/70">{g.color}</span>
                    </p>
                    <p className="mt-1 text-xs text-mist/50">{g.tags.slice(0, 4).join(" · ")}</p>
                  </div>
                  <span className="rounded-full border border-line bg-ink-950/50 px-3 py-1 text-[11px] text-mist/60">
                    Saved
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </Card>
  );
}
