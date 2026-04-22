import { useState, type ReactNode } from "react";
import { HelpModal } from "@/components/HelpModal";
import lisaPageVideo from "@/assets/lisa_page.mp4";

export type AppRoute = "home" | "wardrobe" | "style" | "buy" | "content";

const NAV: Array<{ key: AppRoute; label: string }> = [
  { key: "home", label: "Home" },
  { key: "wardrobe", label: "Wardrobe" },
  { key: "style", label: "Style" },
  { key: "buy", label: "Buy Analyzer" },
  { key: "content", label: "Simulation" },
];

const STREETWEAR_BRANDS = [
  { name: "Supreme", mark: "SP" },
  { name: "Stussy", mark: "ST" },
  { name: "Palace", mark: "PL" },
  { name: "A Bathing Ape", mark: "AB" },
  { name: "Off-White", mark: "OW" },
  { name: "Carhartt WIP", mark: "CW" },
  { name: "Noah", mark: "NH" },
  { name: "Kith", mark: "KT" },
  { name: "Awake NY", mark: "AY" },
  { name: "Stone Island", mark: "SI" },
  { name: "Nike ACG", mark: "AC" },
  { name: "Adidas", mark: "AD" },
  { name: "Jordan", mark: "JD" },
  { name: "The North Face", mark: "NF" },
  { name: "Comme des Garcons", mark: "CD" },
  { name: "Fear of God", mark: "FG" },
  { name: "Undefeated", mark: "UD" },
  { name: "Neighborhood", mark: "NB" },
  { name: "Human Made", mark: "HM" },
  { name: "Y-3", mark: "Y3" },
  { name: "Undercover", mark: "UC" },
];

function BrandTape({ suffix }: { suffix: string }) {
  return (
    <>
      {STREETWEAR_BRANDS.map((brand) => (
        <span key={`${brand.name}-${suffix}`} className="streetwear-chip">
          <span className="streetwear-mark" aria-hidden="true">
            {brand.mark}
          </span>
          <span>{brand.name}</span>
        </span>
      ))}
    </>
  );
}

const PARTICLES = [
  { top: "8%", left: "10%", size: 7, delay: "0s", duration: "7s" },
  { top: "18%", left: "28%", size: 5, delay: "1.5s", duration: "9s" },
  { top: "30%", left: "77%", size: 6, delay: "0.6s", duration: "8s" },
  { top: "42%", left: "58%", size: 8, delay: "2.2s", duration: "10s" },
  { top: "56%", left: "17%", size: 6, delay: "1.1s", duration: "8s" },
  { top: "66%", left: "86%", size: 5, delay: "2.6s", duration: "7s" },
  { top: "74%", left: "42%", size: 7, delay: "0.2s", duration: "9s" },
  { top: "84%", left: "69%", size: 6, delay: "1.8s", duration: "11s" },
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
    <div className="relative isolate min-h-full overflow-hidden bg-[#F5F3F0] text-black">
      <div aria-hidden="true" className="pointer-events-none absolute inset-0 overflow-hidden">
        {route === "home" ? (
          <video
            className="absolute inset-0 h-full w-full object-cover opacity-100"
            src={lisaPageVideo}
            autoPlay
            muted
            loop
            playsInline
          />
        ) : null}
        {route !== "home" ? (
          <>
            <div className="streetwear-noise" />
            <div className="streetwear-mesh" />
            <div className="streetwear-scanlines" />
            <div className="streetwear-aurora streetwear-aurora-a" />
            <div className="streetwear-aurora streetwear-aurora-b" />
            <div className="streetwear-aurora streetwear-aurora-c" />
            <div className="streetwear-prism streetwear-prism-a" />
            <div className="streetwear-prism streetwear-prism-b" />
            <div className="streetwear-prism streetwear-prism-c" />
            <div className="streetwear-orb streetwear-orb-a" />
            <div className="streetwear-orb streetwear-orb-b" />
            <div className="streetwear-orb streetwear-orb-c" />
            <div className="streetwear-beam streetwear-beam-a" />
            <div className="streetwear-beam streetwear-beam-b" />

            {PARTICLES.map((p, i) => (
              <span
                key={`particle-${i}`}
                className="streetwear-particle"
                style={{
                  top: p.top,
                  left: p.left,
                  width: `${p.size}px`,
                  height: `${p.size}px`,
                  animationDelay: p.delay,
                  animationDuration: p.duration,
                }}
              />
            ))}

            <div className="streetwear-grid">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={`streetwear-row-${i}`} className={`streetwear-row ${i % 2 ? "streetwear-row-reverse" : ""}`}>
                  <div className={`streetwear-track ${i === 2 ? "streetwear-track-slow" : ""}`}>
                    <BrandTape suffix={`d${i}-a`} />
                    <BrandTape suffix={`d${i}-b`} />
                  </div>
                </div>
              ))}
            </div>
          </>
        ) : null}
      </div>

      <header className="relative z-10 border-b border-line/40 bg-[#F5F3F0]/85 backdrop-blur">
        <div className="mx-auto flex w-full max-w-6xl items-center gap-4 px-4 py-3 md:px-6">
          <button
            type="button"
            onClick={() => onRoute("home")}
            className="shrink-0 text-left text-sm font-semibold uppercase tracking-[0.2em] text-[#B8933C]"
          >
            Apparel Intelligence
          </button>

          <nav className="flex min-w-0 flex-1 items-center gap-2 overflow-x-auto whitespace-nowrap pb-1 pt-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            {NAV.map((n) => {
              const active = n.key === route;
              return (
                <button
                  key={n.key}
                  type="button"
                  onClick={() => onRoute(n.key)}
                  className={[
                    "rounded-full px-3 py-1.5 text-xs font-semibold transition sm:px-4 sm:py-2 sm:text-sm",
                    active
                      ? "bg-[#C8A96A] text-black"
                      : "border border-line bg-[#E8E8E8] text-black/60 hover:border-accent/30 hover:text-black",
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
            className="shrink-0 rounded-full border border-line/60 bg-[#E8E8E8] px-4 py-2 text-sm font-semibold text-black/60 hover:border-accent/30 hover:text-black"
          >
            Help
          </button>
        </div>
      </header>

      <div className="relative z-10 mx-auto max-w-6xl px-5 pb-20 pt-8">
        {route === "home" ? (
          <section className="rounded-2xl bg-transparent p-6 md:p-8">
            <h1 className="text-3xl leading-tight tracking-tight text-white md:text-5xl">
              <span className="block font-bold">YOUR WARDROBE</span>
              <span className="block font-normal">UPGRADED</span>
            </h1>
          </section>
        ) : null}

        <main className={route === "home" ? "mt-8" : "mt-2"}>{children}</main>
      </div>

      <HelpModal open={helpOpen} onClose={() => setHelpOpen(false)}>
        <ol className="space-y-4 text-sm text-black/80">
          <li>
            <span className="font-semibold text-black">1) Wardrobe</span> — Upload 3–6 items (top, bottom, shoes, outerwear).
            Add optional hints like <span className="font-mono text-black/70">wool, winter, navy</span>.
          </li>
          <li>
            <span className="font-semibold text-black">What are “Hints”?</span> — They’re optional keywords that help the app label an
            item (material/season/color). If the system can’t “see” the details, hints keep the recommendation accurate.
          </li>
          <li>
            <span className="font-semibold text-black">2) Style</span> — Enter occasion / weather / vibe, then click{" "}
            <span className="font-semibold text-black">Recommend outfit</span>. You’ll get one clean outfit card with an explanation.
          </li>
          <li>
            <span className="font-semibold text-black">3) Buy Analyzer</span> — Describe a candidate item to get a Buy / Maybe / No Buy
            recommendation and a simple scorecard.
          </li>
          <li>
            <span className="font-semibold text-black">4) Simulation</span> — Generate a short script/caption and a Gemini reel preview (and a real MP4 when Veo is enabled).
          </li>
          <li>
            <span className="font-semibold text-black">Chat</span> — Use the bottom-right chat button anytime for quick tweaks or alternatives.
          </li>
        </ol>
        <div className="mt-6 rounded-2xl border border-line bg-[#E8E8E8]/30 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-black/50">Demo tip</p>
          <p className="mt-2 text-sm text-black/75">
            If you don’t add an API key, the app still works with deterministic fallbacks so the demo never blocks.
          </p>
        </div>
      </HelpModal>
    </div>
  );
}

