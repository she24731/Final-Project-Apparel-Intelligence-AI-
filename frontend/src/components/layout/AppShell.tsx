import { useState, type ReactNode } from "react";
import { HelpModal } from "@/components/HelpModal";

export type AppRoute = "home" | "wardrobe" | "style" | "buy" | "content";

const NAV: Array<{ key: AppRoute; label: string }> = [
  { key: "home", label: "Home" },
  { key: "wardrobe", label: "Wardrobe" },
  { key: "style", label: "Style" },
  { key: "buy", label: "Buy Analyzer" },
  { key: "content", label: "Simulation" },
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
  const [helpOpen, setHelpOpen] = useState(false);
  return (
    <div className="min-h-full bg-gradient-to-b from-ink-950 via-ink-950 to-ink-900">
      <div className="mx-auto max-w-6xl px-5 pb-20 pt-10">
        <header className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Apparel Intelligence</p>
            <button
              type="button"
              onClick={() => onRoute("home")}
              className="mt-3 text-left text-3xl font-semibold tracking-tight text-mist md:text-4xl"
            >
              Your wardrobe, upgraded
            </button>
            <p className="mt-3 max-w-2xl text-sm leading-relaxed text-mist/70">
              A guided flow for outfit decisions, purchase ROI, and runway-ready content—built for reliable class demos.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
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
            <button
              type="button"
              onClick={() => setHelpOpen(true)}
              className="rounded-full border border-line bg-ink-950 px-4 py-2 text-sm font-semibold text-mist/80 hover:border-accent/40 hover:text-mist"
            >
              Help
            </button>
          </div>
        </header>

        <main className="mt-12">{children}</main>
      </div>

      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)}>
        <ol className="space-y-4 text-sm text-mist/80">
          <li>
            <span className="font-semibold text-mist">1) Wardrobe</span> — Upload 3–6 items (top, bottom, shoes, outerwear).
            Add optional hints like <span className="font-mono text-mist/70">wool, winter, navy</span>.
          </li>
          <li>
            <span className="font-semibold text-mist">What are “Hints”?</span> — They’re optional keywords that help the app label an
            item (material/season/color). If the system can’t “see” the details, hints keep the recommendation accurate.
          </li>
          <li>
            <span className="font-semibold text-mist">2) Style</span> — Enter occasion / weather / vibe, then click{" "}
            <span className="font-semibold text-mist">Recommend outfit</span>. You’ll get one clean outfit card with an explanation.
          </li>
          <li>
            <span className="font-semibold text-mist">3) Buy Analyzer</span> — Describe a candidate item to get a Buy / Maybe / No Buy
            recommendation and a simple scorecard.
          </li>
          <li>
            <span className="font-semibold text-mist">4) Simulation</span> — Generate a short script/caption and a Gemini reel preview (and a real MP4 when Veo is enabled).
          </li>
          <li>
            <span className="font-semibold text-mist">Chat</span> — Use the bottom-right chat button anytime for quick tweaks or alternatives.
          </li>
        </ol>
        <div className="mt-6 rounded-2xl border border-line bg-ink-950/40 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-mist/50">Demo tip</p>
          <p className="mt-2 text-sm text-mist/75">
            If you don’t add an API key, the app still works with deterministic fallbacks so the demo never blocks.
          </p>
        </div>
      </HelpModal>
    </div>
  );
}

