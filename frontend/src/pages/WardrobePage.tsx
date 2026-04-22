import { WardrobeUploadPanel } from "@/components/WardrobeUploadPanel";
import type { GarmentRecord } from "@/types";

export function WardrobePage({
  wardrobe,
  busy,
  error,
  onIngest,
  onDelete,
  onRemoveAll,
  onNext,
  onGoBuyAnalyzer,
}: {
  wardrobe: GarmentRecord[];
  busy: boolean;
  error: string | null;
  onIngest: (file: File, hints: string | undefined) => Promise<void>;
  onDelete: (id: string) => Promise<void>;
  onRemoveAll: () => Promise<void>;
  onNext: () => void;
  onGoBuyAnalyzer: () => void;
}) {
  const hasEnough = wardrobe.length >= 3;
  return (
    <div className="space-y-10">
      <section>
        <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">
          <span aria-hidden="true">👕</span>
          <span>Wardrobe</span>
        </h2>
        <p className="mt-2 text-sm text-black/70">Upload a few key pieces to seed your digital closet.</p>
      </section>

      <WardrobeUploadPanel
        items={wardrobe}
        busy={busy}
        error={error}
        onIngest={onIngest}
        onDelete={onDelete}
        onRemoveAll={onRemoveAll}
      />

      <div className="rounded-3xl border border-line bg-[#E8E8E8] p-6 backdrop-blur">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-accent">Next step</p>
            <p className="mt-2 text-sm text-black/75">
              After you've uploaded a few items, go to <span className="font-semibold text-black">Style</span> to generate an outfit.
            </p>
            <ul className="mt-3 space-y-1 text-xs text-black/55">
              <li>Recommended minimum: 1 top + 1 bottom + 1 shoes (outerwear optional)</li>
              <li>Current wardrobe size: {wardrobe.length}</li>
            </ul>
          </div>
          <div className="flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={onNext}
              disabled={!hasEnough}
              className="rounded-2xl bg-accent px-6 py-4 text-base font-semibold text-ink-950 transition hover:opacity-95 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Go to Style
            </button>
            <button
              type="button"
              onClick={onGoBuyAnalyzer}
              disabled={!hasEnough}
              className="rounded-2xl border border-line bg-[#E8E8E8] px-6 py-4 text-base font-semibold text-black transition hover:border-accent/40 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Go to Buy Analyzer
            </button>
          </div>
        </div>
        {!hasEnough ? (
          <p className="mt-4 text-xs text-black/45">Upload at least 3 items to unlock a good recommendation.</p>
        ) : null}
      </div>
    </div>
  );
}

