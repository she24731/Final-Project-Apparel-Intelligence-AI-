import { Card } from "@/components/ui/Card";
import type { GenerateVideoResponse } from "@/types";

export function RunwayReelPreviewPanel({
  video,
  busy,
  onGenerate,
}: {
  video: GenerateVideoResponse | null;
  busy: boolean;
  onGenerate: () => Promise<void>;
}) {
  return (
    <Card
      title="Runway preview"
      subtitle="A short runway-style concept preview for this outfit."
      right={
        <button
          type="button"
          disabled={busy}
          onClick={() => void onGenerate()}
          className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/50 disabled:opacity-40"
        >
          {busy ? "Staging…" : "Generate preview"}
        </button>
      }
    >
      {!video ? (
        <div className="rounded-xl border border-dashed border-line/80 bg-ink-950/30 p-8 text-center text-sm text-mist/55">
          Generate a preview to see the runway concept.
        </div>
      ) : (
        <div className="space-y-3">
          <div className="aspect-video w-full rounded-2xl border border-line bg-gradient-to-br from-ink-950 via-ink-900 to-ink-950">
            <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
              <p className="text-xs font-semibold uppercase tracking-[0.2em] text-accent">Runway</p>
              <p className="max-w-md text-sm text-mist/75">{video.preview_message}</p>
            </div>
          </div>
          {video.video_url ? (
            <video className="w-full rounded-2xl border border-line" controls src={video.video_url} />
          ) : null}
        </div>
      )}
    </Card>
  );
}
