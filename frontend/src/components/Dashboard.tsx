import type { ReactNode } from "react";

export function Dashboard({
  healthLabel,
  useLiveApi,
  onToggleLive,
  children,
}: {
  healthLabel: string;
  useLiveApi: boolean;
  onToggleLive: (v: boolean) => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-full bg-gradient-to-b from-ink-950 via-ink-950 to-ink-900">
      <div className="mx-auto max-w-6xl px-5 pb-16 pt-10">
        <div className="flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Apparel Intelligence</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-mist md:text-4xl">
              Agentic wardrobe intelligence
            </h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mist/70">
              Ingest garments, reason over context, score purchase ROI, and stage runway-ready media—built for course demos
              with deterministic fallbacks when APIs sleep.
            </p>
          </div>
          <div className="flex flex-col items-start gap-3 md:items-end">
            <div className="rounded-full border border-line bg-ink-900 px-4 py-2 text-xs text-mist/80">
              API: <span className="font-mono text-mist">{healthLabel}</span>
            </div>
            <label className="flex cursor-pointer items-center gap-2 text-xs text-mist/70">
              <input
                type="checkbox"
                className="h-4 w-4 rounded border-line bg-ink-900 accent-accent"
                checked={useLiveApi}
                onChange={(e) => onToggleLive(e.target.checked)}
              />
              Use live backend when available
            </label>
          </div>
        </div>

        <div className="mt-10 grid grid-cols-1 gap-6 lg:grid-cols-12">{children}</div>
      </div>
    </div>
  );
}
