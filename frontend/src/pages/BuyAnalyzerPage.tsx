import { BuyOrSkipAnalyzer } from "@/components/BuyOrSkipAnalyzer";
import type { GarmentRecord, PurchaseAnalysisResponse } from "@/types";

export function BuyAnalyzerPage({
  wardrobe,
  busy,
  error,
  result,
  onAnalyze,
  onUseCombo,
  onIngestCandidate,
  onCleanupCandidate,
}: {
  wardrobe: GarmentRecord[];
  busy: boolean;
  error: string | null;
  result: PurchaseAnalysisResponse | null;
  onAnalyze: (candidate: GarmentRecord) => Promise<void>;
  onUseCombo: (opts: { title: string; garmentIds: string[]; occasion?: string | null; description?: string | null }) => void;
  onIngestCandidate: (file: File, hints: string | undefined) => Promise<GarmentRecord>;
  onCleanupCandidate: (id: string) => Promise<void>;
}) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Buy Analyzer</h2>
        <p className="mt-2 text-sm text-mist/65">A fast ROI read: compatibility, versatility, and redundancy.</p>
      </section>
      <BuyOrSkipAnalyzer
        wardrobe={wardrobe}
        busy={busy}
        error={error}
        result={result}
        onAnalyze={onAnalyze}
        onUseCombo={onUseCombo}
        onIngestCandidate={onIngestCandidate}
        onCleanupCandidate={onCleanupCandidate}
      />
    </div>
  );
}

