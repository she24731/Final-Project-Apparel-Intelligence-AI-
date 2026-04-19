import { useState } from "react";
import { Card } from "@/components/ui/Card";
import type { GenerateScriptResponse, RecommendOutfitResponse } from "@/types";

export function NarrativeScriptPanel({
  recommendation,
  script,
  busy,
  onGenerate,
}: {
  recommendation: RecommendOutfitResponse | null;
  script: GenerateScriptResponse | null;
  busy: boolean;
  onGenerate: (platform: "linkedin" | "instagram" | "tiktok") => Promise<void>;
}) {
  const [platform, setPlatform] = useState<"linkedin" | "instagram" | "tiktok">("linkedin");

  const summary =
    recommendation?.garments.map((g) => `${g.color} ${g.category}`).join(", ") ??
    "Ivory shirt · navy chinos · charcoal coat · brown loafers";

  return (
    <Card title="Script & caption" subtitle="Generate a short script you can actually say out loud.">
      <div className="flex flex-wrap items-center gap-3">
        <label className="text-xs text-mist/60">
          Platform
          <select
            value={platform}
            onChange={(e) => setPlatform(e.target.value as typeof platform)}
            className="ml-2 rounded-lg border border-line bg-ink-950 px-2 py-1 text-sm text-mist"
          >
            <option value="linkedin">LinkedIn</option>
            <option value="instagram">Instagram</option>
            <option value="tiktok">TikTok</option>
          </select>
        </label>
        <button
          type="button"
          disabled={busy}
          onClick={() => void onGenerate(platform)}
          className="rounded-xl bg-ink-950 px-4 py-2 text-sm font-semibold text-mist ring-1 ring-line hover:ring-accent/40 disabled:opacity-40"
        >
          {busy ? "Writing…" : "Generate script"}
        </button>
      </div>

      {!script ? (
        <p className="mt-4 text-xs text-mist/45">No script yet. Uses outfit summary: {summary}</p>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="text-sm leading-relaxed text-mist/85">{script.script}</p>
          {script.caption ? <p className="text-xs text-mist/60">Caption: {script.caption}</p> : null}
        </div>
      )}
    </Card>
  );
}
