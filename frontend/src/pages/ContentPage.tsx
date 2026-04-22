import { NarrativeScriptPanel } from "@/components/NarrativeScriptPanel";
import { RunwayReelPreviewPanel } from "@/components/RunwayReelPreviewPanel";
import { apiPostJson } from "@/lib/api";
import type {
  GenerateScriptRequestBody,
  GenerateScriptResponse,
  GenerateVideoRequestBody,
  GenerateVideoResponse,
  PreviewReelCopyRequestBody,
  PreviewReelCopyResponse,
  RecommendOutfitResponse,
} from "@/types";

export function ContentPage({
  recommendation,
  script,
  video,
  scriptBusy,
  videoBusy,
  faceAnchorPath,
  onUploadFaceAnchor,
  onGenerateScript,
  onRenderVideo,
  stylePreference,
}: {
  recommendation: RecommendOutfitResponse | null;
  script: GenerateScriptResponse | null;
  video: GenerateVideoResponse | null;
  scriptBusy: boolean;
  videoBusy: boolean;
  faceAnchorPath: string | null;
  onUploadFaceAnchor: (file: File) => Promise<void>;
  onGenerateScript: (body: GenerateScriptRequestBody) => Promise<void>;
  onRenderVideo: (body: GenerateVideoRequestBody) => Promise<void>;
  stylePreference: string;
}) {
  const hasOutfit = !!recommendation && recommendation.garments.length > 0;

  const generateScenes = async (body: PreviewReelCopyRequestBody) => apiPostJson<PreviewReelCopyResponse>("/generate-scenes", body);

  const generateSceneAssets = async (body: PreviewReelCopyRequestBody & { scene: PreviewReelCopyResponse["scenes"][number] }) =>
    apiPostJson<PreviewReelCopyResponse["scenes"][number]>("/generate-scene-assets", body);

  return (
    <div className="space-y-10">
      <section>
        <h2 className="flex items-center gap-2 text-2xl font-semibold tracking-tight text-black md:text-3xl">
          <span aria-hidden="true">🎬</span>
          <span>Simulation</span>
        </h2>
        <p className="mt-2 text-sm text-black/70">Turn an outfit into a script and a generated reel preview.</p>
      </section>

      {!hasOutfit ? (
        <div className="rounded-3xl border border-dashed border-line/80 bg-[#E8E8E8]/40 p-10 text-center">
          <p className="text-sm text-black/70">No outfit selected yet.</p>
          <p className="mt-2 text-xs text-black/45">Pick an outfit from Style or Buy Analyzer, then come back here.</p>
        </div>
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <NarrativeScriptPanel
          recommendation={recommendation}
          script={script}
          busy={scriptBusy}
          stylePreference={stylePreference}
          onGenerate={onGenerateScript}
        />
        <RunwayReelPreviewPanel
          recommendation={recommendation}
          video={video}
          busy={videoBusy}
          faceAnchorPath={faceAnchorPath}
          onUploadFaceAnchor={onUploadFaceAnchor}
          onGenerateScenes={generateScenes}
          onGenerateSceneAssets={generateSceneAssets}
          onRenderVideo={onRenderVideo}
        />
      </div>
    </div>
  );
}
