import { useState } from "react";
import { Card } from "@/components/ui/Card";
import { apiPostJson } from "@/lib/api";
import type {
  GenerateScriptRequestBody,
  GenerateScriptResponse,
  RecommendOutfitResponse,
  SocialPostPrepareResponse,
} from "@/types";

export function NarrativeScriptPanel({
  recommendation,
  script,
  busy,
  stylePreference,
  onGenerate,
}: {
  recommendation: RecommendOutfitResponse | null;
  script: GenerateScriptResponse | null;
  busy: boolean;
  stylePreference: string;
  onGenerate: (body: GenerateScriptRequestBody) => Promise<void>;
}) {
  const [platform, setPlatform] = useState<"linkedin" | "instagram" | "tiktok">("linkedin");
  const [tone, setTone] = useState("authentic");
  const [emotion, setEmotion] = useState("calm confidence");
  const [targetAudience, setTargetAudience] = useState("your ideal viewer");
  const [scenario, setScenario] = useState("a normal day");
  const [vibe, setVibe] = useState("quiet quality");
  const [showCreative, setShowCreative] = useState(true);
  const [shareBusy, setShareBusy] = useState<string | null>(null);

  const summary =
    recommendation?.garments.map((g) => `${g.color} ${g.category}`).join(", ") ??
    "Ivory shirt · navy chinos · charcoal coat · brown loafers";

  const outfit_summary =
    recommendation?.garments.map((g) => `${g.color} ${g.category}`).join(", ") ??
    "ivory shirt, navy chinos, charcoal coat, brown loafers";

  const copyText = async (label: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setShareBusy(`Copied (${label})`);
      setTimeout(() => setShareBusy(null), 1600);
    } catch {
      setShareBusy("Copy blocked by browser");
      setTimeout(() => setShareBusy(null), 2000);
    }
  };

  const preparePost = async (target: "linkedin" | "instagram" | "tiktok") => {
    if (!script) {
      setShareBusy("Generate a script first");
      setTimeout(() => setShareBusy(null), 1600);
      return;
    }
    setShareBusy(target);
    try {
      const res = await apiPostJson<SocialPostPrepareResponse>("/social/prepare-post", {
        platform: target,
        script: script.script,
        caption: script.caption,
        hashtags: script.hashtags ?? undefined,
        link_url: typeof window !== "undefined" ? window.location.origin : undefined,
      });
      await copyText("clipboard", res.clipboard_text);
      if (target === "linkedin" && res.linkedin_share_url) {
        window.open(res.linkedin_share_url, "_blank", "noopener,noreferrer");
      }
      if (target === "instagram") {
        window.open(res.instagram_web_url, "_blank", "noopener,noreferrer");
      }
      if (target === "tiktok") {
        window.open(res.tiktok_upload_url, "_blank", "noopener,noreferrer");
      }
      if (navigator.share) {
        try {
          await navigator.share({ text: res.clipboard_text, title: "Apparel Intelligence draft" });
        } catch {
          /* user cancelled */
        }
      }
    } finally {
      setShareBusy(null);
    }
  };

  return (
    <Card title="Script & caption" subtitle="Platform-native copy with creative controls—each click varies the offline template.">
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
          onClick={() =>
            void onGenerate({
              platform,
              outfit_summary,
              user_voice: stylePreference.trim() || null,
              tone: tone.trim() || null,
              emotion: emotion.trim() || null,
              target_audience: targetAudience.trim() || null,
              scenario: scenario.trim() || null,
              vibe: vibe.trim() || null,
              variation_salt: typeof crypto !== "undefined" ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`,
            })
          }
          className="rounded-xl bg-ink-950 px-4 py-2 text-sm font-semibold text-mist ring-1 ring-line hover:ring-accent/40 disabled:opacity-40"
        >
          {busy ? "Writing…" : "Generate script"}
        </button>
        <button
          type="button"
          onClick={() => setShowCreative((v) => !v)}
          className="rounded-xl border border-line bg-ink-950 px-3 py-2 text-xs font-semibold text-mist/80 hover:border-accent/40"
        >
          {showCreative ? "Hide creative fields" : "Creative fields"}
        </button>
      </div>

      {showCreative ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2">
          {(
            [
              ["Tone", tone, setTone],
              ["Emotion", emotion, setEmotion],
              ["Audience", targetAudience, setTargetAudience],
              ["Scenario", scenario, setScenario],
              ["Vibe", vibe, setVibe],
            ] as const
          ).map(([label, val, set]) => (
            <label key={label} className="block text-xs text-mist/55">
              {label}
              <input
                value={val}
                onChange={(e) => set(e.target.value)}
                className="mt-1 w-full rounded-xl border border-line bg-ink-950 px-3 py-2 text-sm text-mist outline-none ring-accent/15 focus:ring-2"
              />
            </label>
          ))}
        </div>
      ) : null}

      {!script ? (
        <p className="mt-4 text-xs text-mist/45">No script yet. Outfit summary: {summary}</p>
      ) : (
        <div className="mt-4 space-y-3">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-mist/85">{script.script}</p>
          {script.caption ? <p className="text-xs text-mist/60">Caption: {script.caption}</p> : null}
          {script.hashtags?.length ? (
            <p className="text-xs text-mist/50">{script.hashtags.join(" ")}</p>
          ) : null}

          <div className="flex flex-wrap gap-2 pt-2">
            <button
              type="button"
              disabled={!!shareBusy}
              onClick={() => void preparePost("linkedin")}
              className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/45 disabled:opacity-40"
            >
              LinkedIn (copy + share link)
            </button>
            <button
              type="button"
              disabled={!!shareBusy}
              onClick={() => void preparePost("instagram")}
              className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/45 disabled:opacity-40"
            >
              Instagram (copy + create)
            </button>
            <button
              type="button"
              disabled={!!shareBusy}
              onClick={() => void preparePost("tiktok")}
              className="rounded-lg border border-line bg-ink-950 px-3 py-1.5 text-xs font-semibold text-mist hover:border-accent/45 disabled:opacity-40"
            >
              TikTok (copy + upload)
            </button>
          </div>
          <p className="text-[11px] text-mist/40">
            {shareBusy ? `${shareBusy}…` : "Posting APIs need OAuth apps per network—this flow copies text and opens the best-effort web destination."}
          </p>
        </div>
      )}
    </Card>
  );
}
