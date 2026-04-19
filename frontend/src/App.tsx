import { useMemo, useState } from "react";
import { AppShell, type AppRoute } from "@/components/layout/AppShell";
import { ApiError, apiPostJson, apiPostMultipart } from "@/lib/api";
import { mockPurchase, mockRecommendation, mockScript, mockVideo, mockWardrobe } from "@/mocks/sampleData";
import { BuyAnalyzerPage } from "@/pages/BuyAnalyzerPage";
import { ChatPage } from "@/pages/ChatPage";
import { ContentPage } from "@/pages/ContentPage";
import { StylePage } from "@/pages/StylePage";
import { WardrobePage } from "@/pages/WardrobePage";
import type {
  GarmentRecord,
  GenerateScriptResponse,
  GenerateVideoResponse,
  PurchaseAnalysisResponse,
  RecommendOutfitResponse,
} from "@/types";

export default function App() {
  const [route, setRoute] = useState<AppRoute>("style");

  const [wardrobe, setWardrobe] = useState<GarmentRecord[]>(mockWardrobe);
  const [context, setContext] = useState({
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

  const wardrobeIds = useMemo(() => wardrobe.map((g) => g.id), [wardrobe]);

  const ingest = async (file: File, hints: string | undefined) => {
    setBusyKey("ingest", true);
    setErr("ingest", null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (hints) fd.append("hints", hints);
      const res = await apiPostMultipart<{ garment: GarmentRecord }>("/ingest-garment", fd);
      setWardrobe((w) => [...w, res.garment]);
    } catch (e) {
      // Quiet fallback: still add a local placeholder so the flow continues.
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
      setErr("ingest", e instanceof ApiError ? "Couldn’t reach the server. Saved locally for the demo." : "Saved locally for the demo.");
    } finally {
      setBusyKey("ingest", false);
    }
  };

  const recommend = async () => {
    setBusyKey("rec", true);
    setErr("rec", null);
    try {
      const res = await apiPostJson<RecommendOutfitResponse>("/recommend-outfit", {
        occasion: context.occasion,
        weather: context.weather,
        vibe: context.vibe,
        wardrobe_item_ids: wardrobeIds,
        user_preference: context.preference || null,
      });
      setRecommendation(res);
    } catch (e) {
      setErr("rec", "Couldn’t generate a live recommendation. Showing a demo result.");
      setRecommendation(mockRecommendation);
    } finally {
      setBusyKey("rec", false);
    }
  };

  const analyze = async (candidate: GarmentRecord) => {
    setBusyKey("pur", true);
    setErr("pur", null);
    try {
      const res = await apiPostJson<PurchaseAnalysisResponse>("/analyze-purchase", {
        candidate,
        wardrobe_item_ids: wardrobeIds,
      });
      setPurchase(res);
    } catch (e) {
      setErr("pur", "Couldn’t run a live analysis. Showing a demo result.");
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
      const res = await apiPostJson<GenerateScriptResponse>("/generate-script", {
        platform,
        outfit_summary,
        user_voice: context.preference || null,
      });
      setScript(res);
    } catch (e) {
      setErr("scr", "Couldn’t generate live copy. Showing a demo script.");
      setScript(mockScript);
    } finally {
      setBusyKey("scr", false);
    }
  };

  const genVideo = async () => {
    setBusyKey("vid", true);
    setErr("vid", null);
    try {
      const res = await apiPostJson<GenerateVideoResponse>("/generate-video", {
        scene_prompt: "Runway walk-through with natural light and slow pan.",
        anchor_image_paths: [],
        duration_seconds: 5,
      });
      setVideo(res);
    } catch (e) {
      setErr("vid", "Couldn’t generate a live preview. Showing a demo preview.");
      setVideo(mockVideo);
    } finally {
      setBusyKey("vid", false);
    }
  };

  return (
    <AppShell route={route} onRoute={setRoute}>
      {route === "wardrobe" ? (
        <WardrobePage wardrobe={wardrobe} busy={!!busy.ingest} error={errors.ingest} onIngest={ingest} />
      ) : null}
      {route === "style" ? (
        <StylePage
          context={context}
          onChange={setContext}
          onRecommend={recommend}
          busy={!!busy.rec}
          error={errors.rec}
          recommendation={recommendation}
        />
      ) : null}
      {route === "buy" ? (
        <BuyAnalyzerPage
          wardrobe={wardrobe}
          busy={!!busy.pur}
          error={errors.pur}
          result={purchase}
          onAnalyze={analyze}
        />
      ) : null}
      {route === "content" ? (
        <ContentPage
          recommendation={recommendation}
          script={script}
          video={video}
          scriptBusy={!!busy.scr}
          videoBusy={!!busy.vid}
          onGenerateScript={genScript}
          onGenerateVideo={genVideo}
        />
      ) : null}
      {route === "chat" ? <ChatPage recommendation={recommendation} /> : null}
    </AppShell>
  );
}
