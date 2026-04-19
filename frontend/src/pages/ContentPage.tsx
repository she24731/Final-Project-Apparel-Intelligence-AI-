import { NarrativeScriptPanel } from "@/components/NarrativeScriptPanel";
import { RunwayReelPreviewPanel } from "@/components/RunwayReelPreviewPanel";
import type { GenerateScriptResponse, GenerateVideoResponse, RecommendOutfitResponse } from "@/types";

export function ContentPage({
  recommendation,
  script,
  video,
  scriptBusy,
  videoBusy,
  onGenerateScript,
  onGenerateVideo,
}: {
  recommendation: RecommendOutfitResponse | null;
  script: GenerateScriptResponse | null;
  video: GenerateVideoResponse | null;
  scriptBusy: boolean;
  videoBusy: boolean;
  onGenerateScript: (platform: "linkedin" | "dating" | "tiktok") => Promise<void>;
  onGenerateVideo: () => Promise<void>;
}) {
  return (
    <div className="space-y-10">
      <section>
        <h2 className="text-2xl font-semibold tracking-tight text-mist md:text-3xl">Content</h2>
        <p className="mt-2 text-sm text-mist/65">Turn an outfit into a caption, a script, and a runway-style preview.</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <NarrativeScriptPanel
          recommendation={recommendation}
          script={script}
          busy={scriptBusy}
          onGenerate={onGenerateScript}
        />
        <RunwayReelPreviewPanel video={video} busy={videoBusy} onGenerate={onGenerateVideo} />
      </div>
    </div>
  );
}

