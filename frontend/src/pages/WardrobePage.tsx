import { WardrobeUploadPanel } from "@/components/WardrobeUploadPanel";
import type { GarmentRecord } from "@/types";

export function WardrobePage({
  wardrobe,
  busy,
  error,
  onIngest,
}: {
  wardrobe: GarmentRecord[];
  busy: boolean;
  error: string | null;
  onIngest: (file: File, hints: string | undefined) => Promise<void>;
}) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Wardrobe</h2>
        <p className="mt-2 text-sm text-mist/65">Upload a few key pieces to seed your digital closet.</p>
      </section>
      <WardrobeUploadPanel items={wardrobe} busy={busy} error={error} onIngest={onIngest} />
    </div>
  );
}

