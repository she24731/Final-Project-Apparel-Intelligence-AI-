export function HomePage({ onGoWardrobe }: { onGoWardrobe: () => void }) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Welcome</h2>
        <p className="mt-2 text-sm text-mist/65">
          Apparel Intelligence helps you build a digital wardrobe, generate one clean outfit recommendation, and decide whether a new
          item is worth buying.
        </p>
      </section>

      <div className="rounded-3xl border border-line bg-ink-900/50 p-8 backdrop-blur">
        <h3 className="text-lg font-semibold text-mist">Recommended flow</h3>
        <ol className="mt-4 space-y-3 text-sm text-mist/75">
          <li>
            <span className="font-semibold text-mist">1) Wardrobe</span> — Upload a few items (top, bottom, shoes, outerwear).
          </li>
          <li>
            <span className="font-semibold text-mist">2) Style</span> — Enter occasion/weather/vibe and click{" "}
            <span className="font-semibold text-mist">Recommend outfit</span>.
          </li>
          <li>
            <span className="font-semibold text-mist">3) Buy Analyzer</span> — Check BUY / MAYBE / NO BUY for a candidate item.
          </li>
          <li>
            <span className="font-semibold text-mist">4) Content</span> — Generate a script/caption and a runway preview.
          </li>
          <li>
            <span className="font-semibold text-mist">Chat</span> — Use the bottom-right chat button anytime for quick tweaks.
          </li>
        </ol>

        <div className="mt-6 flex flex-col gap-3 sm:flex-row">
          <button
            type="button"
            onClick={onGoWardrobe}
            className="rounded-2xl bg-accent px-6 py-4 text-base font-semibold text-ink-950 transition hover:opacity-95"
          >
            Start by uploading wardrobe items
          </button>
          <div className="rounded-2xl border border-line bg-ink-950/40 px-5 py-4 text-sm text-mist/70">
            Tip: “Hints (optional)” is just a short description like <span className="font-mono">wool, winter, navy</span> to help the
            system label your item.
          </div>
        </div>
      </div>
    </div>
  );
}

