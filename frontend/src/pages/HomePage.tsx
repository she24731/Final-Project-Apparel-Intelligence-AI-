export function HomePage({ onGoWardrobe }: { onGoWardrobe: () => void }) {
  return (
    <div className="space-y-10">
      <div className="fixed bottom-6 left-1/2 z-30 w-[min(92vw,56rem)] -translate-x-1/2 rounded-3xl bg-transparent p-8">
        <p className="text-sm font-medium text-white/80">
          Upload your wardrobe, get outfit recommendations, check whether new items are worth buying, and turn looks into content.
        </p>
        <h3 className="mt-2 text-lg font-semibold text-white">Recommended flow</h3>
        <ol className="mt-4 space-y-3 text-sm text-white/75">
          <li>
            <span className="font-semibold text-white">1) Wardrobe</span> — Upload a few items (top, bottom, shoes, outerwear).
          </li>
          <li>
            <span className="font-semibold text-white">2) Style</span> — Enter occasion/weather/vibe and click{" "}
            <span className="font-semibold text-white">Recommend outfit</span>.
          </li>
          <li>
            <span className="font-semibold text-white">3) Buy Analyzer</span> — Check BUY / MAYBE / NO BUY for a candidate item.
          </li>
          <li>
            <span className="font-semibold text-white">4) Content</span> — Generate a script/caption and a runway preview.
          </li>
          <li>
            <span className="font-semibold text-white">Chat</span> — Use the bottom-right chat button anytime for quick tweaks.
          </li>
        </ol>

        <div className="mt-6 flex justify-center">
          <button
            type="button"
            onClick={onGoWardrobe}
            className="rounded-2xl bg-accent px-6 py-4 text-base font-semibold text-ink-950 transition hover:opacity-95"
          >
            Start by uploading wardrobe items
          </button>
        </div>
      </div>
    </div>
  );
}

