import { useCallback, useEffect, useMemo, useState } from "react";
import { AgentChatPanel } from "@/components/AgentChatPanel";
import { BuyOrSkipAnalyzer } from "@/components/BuyOrSkipAnalyzer";
import { Dashboard } from "@/components/Dashboard";
import { NarrativeScriptPanel } from "@/components/NarrativeScriptPanel";
import { OccasionContextForm, type OccasionContext } from "@/components/OccasionContextForm";
import { OutfitRecommendationDisplay } from "@/components/OutfitRecommendationDisplay";
import { RunwayReelPreviewPanel } from "@/components/RunwayReelPreviewPanel";
import { WardrobeUploadPanel } from "@/components/WardrobeUploadPanel";
import { ApiError, apiGet, apiPostJson, apiPostMultipart } from "@/lib/api";
import { mockPurchase, mockRecommendation, mockScript, mockVideo, mockWardrobe } from "@/mocks/sampleData";
import type {
  GarmentRecord,
  GenerateScriptResponse,
  GenerateVideoResponse,
  PurchaseAnalysisResponse,
  RecommendOutfitResponse,
} from "@/types";

export default function App() {
  const [useLiveApi, setUseLiveApi] = useState(false);
  const [healthLabel, setHealthLabel] = useState("unknown");

  const [wardrobe, setWardrobe] = useState<GarmentRecord[]>(mockWardrobe);
  const [context, setContext] = useState<OccasionContext>({
    occasion: "work_presentation",
    weather: "mild_clear",
    vibe: "quiet_luxury",
    preference: "no loud logos",
  });

  const [recommendation, setRecommendation] = useState<RecommendOutfitResponse | null>(mockRecommendation);
  const [purchase, setPurchase] = useState<PurchaseAnalysisResponse | null>(mockPurchase);
  const [script, setScript] = useState<GenerateScriptResponse | null>(mockScript);
  const [video, setVideo] = useState<GenerateVideoResponse | null>(mockVideo);

  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});

  const setBusyKey = (k: string, v: boolean) => setBusy((p) => ({ ...p, [k]: v }));
  const setErr = (k: string, v: string | null) => setErrors((p) => ({ ...p, [k]: v }));

  const refreshHealth = useCallback(async () => {
    if (!useLiveApi) {
      setHealthLabel("mock mode");
      return;
    }
    try {
      const h = await apiGet<{ status: string }>("/health");
      setHealthLabel(h.status === "ok" ? "connected" : h.status);
    } catch {
      setHealthLabel("unreachable");
    }
  }, [useLiveApi]);

  useEffect(() => {
    void refreshHealth();
  }, [refreshHealth]);

  useEffect(() => {
    if (useLiveApi) {
      setWardrobe([]);
      setRecommendation(null);
      setPurchase(null);
      setScript(null);
      setVideo(null);
    } else {
      setWardrobe(mockWardrobe);
      setRecommendation(mockRecommendation);
      setPurchase(mockPurchase);
      setScript(mockScript);
      setVideo(mockVideo);
    }
  }, [useLiveApi]);

  const wardrobeIds = useMemo(() => wardrobe.map((g) => g.id), [wardrobe]);

  const ingest = async (file: File, hints: string | undefined) => {
    setBusyKey("ingest", true);
    setErr("ingest", null);
    try {
      if (!useLiveApi) {
        const next: GarmentRecord = {
          id: `local-${crypto.randomUUID()}`,
          category: "top",
          color: "uploaded",
          formality_score: 0.45,
          season: "all-season",
          tags: hints ? hints.split(",").map((s) => s.trim()) : ["upload"],
          image_path: `uploads/${file.name}`,
          embedding: [],
        };
        setWardrobe((w) => [...w, next]);
        return;
      }
      const fd = new FormData();
      fd.append("file", file);
      if (hints) fd.append("hints", hints);
      const res = await apiPostMultipart<{ garment: GarmentRecord }>("/ingest-garment", fd);
      setWardrobe((w) => [...w, res.garment]);
    } catch (e) {
      setErr("ingest", e instanceof ApiError ? `${e.status}: ${e.body}` : "upload failed");
    } finally {
      setBusyKey("ingest", false);
    }
  };

  const recommend = async () => {
    setBusyKey("rec", true);
    setErr("rec", null);
    try {
      if (!useLiveApi) {
        setRecommendation(mockRecommendation);
        return;
      }
      const res = await apiPostJson<RecommendOutfitResponse>("/recommend-outfit", {
        occasion: context.occasion,
        weather: context.weather,
        vibe: context.vibe,
        wardrobe_item_ids: wardrobeIds,
        user_preference: context.preference || null,
      });
      setRecommendation(res);
    } catch (e) {
      setErr("rec", e instanceof ApiError ? `${e.status}: ${e.body}` : "recommend failed");
      setRecommendation(mockRecommendation);
    } finally {
      setBusyKey("rec", false);
    }
  };

  const analyze = async (candidate: GarmentRecord) => {
    setBusyKey("pur", true);
    setErr("pur", null);
    try {
      if (!useLiveApi) {
        setPurchase(mockPurchase);
        return;
      }
      const res = await apiPostJson<PurchaseAnalysisResponse>("/analyze-purchase", {
        candidate,
        wardrobe_item_ids: wardrobeIds,
      });
      setPurchase(res);
    } catch (e) {
      setErr("pur", e instanceof ApiError ? `${e.status}: ${e.body}` : "analyze failed");
      setPurchase(mockPurchase);
    } finally {
      setBusyKey("pur", false);
    }
  };

  const genScript = async (platform: "linkedin" | "dating" | "tiktok") => {
    setBusyKey("scr", true);
    setErr("scr", null);
    const outfit_summary =
      recommendation?.garments.map((g) => `${g.color} ${g.category}`).join(", ") ??
      "ivory shirt, navy chinos, charcoal coat, brown loafers";
    try {
      if (!useLiveApi) {
        setScript(mockScript);
        return;
      }
      const res = await apiPostJson<GenerateScriptResponse>("/generate-script", {
        platform,
        outfit_summary,
        user_voice: context.preference || null,
      });
      setScript(res);
    } catch (e) {
      setErr("scr", e instanceof ApiError ? `${e.status}: ${e.body}` : "script failed");
      setScript(mockScript);
    } finally {
      setBusyKey("scr", false);
    }
  };

  const genVideo = async () => {
    setBusyKey("vid", true);
    setErr("vid", null);
    try {
      if (!useLiveApi) {
        setVideo(mockVideo);
        return;
      }
      const res = await apiPostJson<GenerateVideoResponse>("/generate-video", {
        scene_prompt: "Runway walk-through with natural light and slow pan.",
        anchor_image_paths: [],
        duration_seconds: 5,
      });
      setVideo(res);
    } catch (e) {
      setErr("vid", e instanceof ApiError ? `${e.status}: ${e.body}` : "video failed");
      setVideo(mockVideo);
    } finally {
      setBusyKey("vid", false);
    }
  };

  return (
    <Dashboard healthLabel={healthLabel} useLiveApi={useLiveApi} onToggleLive={setUseLiveApi}>
      <div className="space-y-6 lg:col-span-7">
        <WardrobeUploadPanel items={wardrobe} busy={!!busy.ingest} error={errors.ingest} onIngest={ingest} />
        <OccasionContextForm value={context} onChange={setContext} onSubmit={recommend} busy={!!busy.rec} />
        <OutfitRecommendationDisplay data={recommendation} busy={!!busy.rec} />
        <BuyOrSkipAnalyzer wardrobe={wardrobe} busy={!!busy.pur} error={errors.pur} result={purchase} onAnalyze={analyze} />
      </div>
      <div className="space-y-6 lg:col-span-5">
        <AgentChatPanel recommendation={recommendation} />
        <NarrativeScriptPanel recommendation={recommendation} script={script} busy={!!busy.scr} onGenerate={genScript} />
        <RunwayReelPreviewPanel video={video} busy={!!busy.vid} onGenerate={genVideo} />
      </div>
    </Dashboard>
  );
}
