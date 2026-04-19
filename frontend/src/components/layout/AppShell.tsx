import type { ReactNode } from "react";

export type AppRoute = "wardrobe" | "style" | "buy" | "content" | "chat";

const NAV: Array<{ key: AppRoute; label: string }> = [
  { key: "wardrobe", label: "Wardrobe" },
  { key: "style", label: "Style" },
  { key: "buy", label: "Buy Analyzer" },
  { key: "content", label: "Content" },
  { key: "chat", label: "Chat" },
];

export function AppShell({
  route,
  onRoute,
  children,
}: {
  route: AppRoute;
  onRoute: (r: AppRoute) => void;
  children: ReactNode;
}) {
  return (
    <div className="min-h-full bg-gradient-to-b from-ink-950 via-ink-950 to-ink-900">
      <div className="mx-auto max-w-6xl px-5 pb-20 pt-10">
        <header className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Apparel Intelligence</p>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-mist md:text-4xl">Your wardrobe, upgraded</h1>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mist/70">
              A guided flow for outfit decisions, purchase ROI, and runway-ready content—built for reliable class demos.
            </p>
          </div>
          <nav className="flex flex-wrap gap-2">
            {NAV.map((n) => {
              const active = n.key === route;
              return (
                <button
                  key={n.key}
                  type="button"
                  onClick={() => onRoute(n.key)}
                  className={[
                    "rounded-full px-4 py-2 text-sm font-semibold transition",
                    active
                      ? "bg-mist text-ink-950"
                      : "border border-line bg-ink-950 text-mist/80 hover:border-accent/40 hover:text-mist",
                  ].join(" ")}
                >
                  {n.label}
                </button>
              );
            })}
          </nav>
        </header>

        <main className="mt-12">{children}</main>
      </div>
    </div>
  );
}

