import { NarrativeScriptPanel } from "@/components/NarrativeScriptPanel";
import { RunwayReelPreviewPanel } from "@/components/RunwayReelPreviewPanel";
import type { GenerateScriptResponse, GenerateVideoResponse, RecommendOutfitResponse } from "@/types";

export function ContentPage({
  recommendation,
  script,
  video,
  scriptBusy,
  videoBusy,
  faceAnchorPath,
  onUploadFaceAnchor,
  onGenerateScript,
  onGenerateVideo,
}: {
  recommendation: RecommendOutfitResponse | null;
  script: GenerateScriptResponse | null;
  video: GenerateVideoResponse | null;
  scriptBusy: boolean;
  videoBusy: boolean;
  faceAnchorPath: string | null;
  onUploadFaceAnchor: (file: File) => Promise<void>;
  onGenerateScript: (platform: "linkedin" | "instagram" | "tiktok") => Promise<void>;
  onGenerateVideo: () => Promise<void>;
}) {
  const hasOutfit = !!recommendation && recommendation.garments.length > 0;
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Simulation</h2>
        <p className="mt-2 text-sm text-mist/65">Turn an outfit into a script, narration, and a generated reel preview.</p>
      </section>

      {!hasOutfit ? (
        <div className="rounded-3xl border border-dashed border-line/80 bg-ink-950/20 p-10 text-center">
          <p className="text-sm text-mist/70">No outfit selected yet.</p>
          <p className="mt-2 text-xs text-mist/45">Pick an outfit from Style or Buy Analyzer, then come back here.</p>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <NarrativeScriptPanel
          recommendation={recommendation}
          script={script}
          busy={scriptBusy}
          onGenerate={onGenerateScript}
        />
        <RunwayReelPreviewPanel
          video={video}
          busy={videoBusy}
          faceAnchorPath={faceAnchorPath}
          onUploadFaceAnchor={onUploadFaceAnchor}
          onGenerate={onGenerateVideo}
        />
      </div>
    </div>
  );
}

