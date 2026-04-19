import { useEffect, useMemo, useState } from "react";
import { AppShell, type AppRoute } from "@/components/layout/AppShell";
import { ChatWidget } from "@/components/ChatWidget";
import { ImageLightboxProvider } from "@/components/ui/ImageLightbox";
import { ApiError, apiDelete, apiGet, apiPostJson, apiPostMultipart } from "@/lib/api";
import { mockPurchase, mockRecommendation, mockScript, mockVideo } from "@/mocks/sampleData";
import { BuyAnalyzerPage } from "@/pages/BuyAnalyzerPage";
import { ContentPage } from "@/pages/ContentPage";
import { HomePage } from "@/pages/HomePage";
import { StylePage } from "@/pages/StylePage";
import { WardrobePage } from "@/pages/WardrobePage";
import type {
  AssistantTurnResponse,
  GarmentRecord,
  GenerateScriptRequestBody,
  GenerateScriptResponse,
  GenerateVideoRequestBody,
  GenerateVideoResponse,
  PurchaseAnalysisResponse,
  RecommendOutfitResponse,
} from "@/types";

export default function App() {
  const [route, setRoute] = useState<AppRoute>("wardrobe");

  const [serverWardrobe, setServerWardrobe] = useState<GarmentRecord[]>([]);
  const [localWardrobe, setLocalWardrobe] = useState<GarmentRecord[]>([]);
  const [context, setContext] = useState({
    occasion: "",
    weather: "",
    vibe: "",
    preference: "",
  });

  const [recommendation, setRecommendation] = useState<RecommendOutfitResponse | null>(null);
  const [purchase, setPurchase] = useState<PurchaseAnalysisResponse | null>(null);
  const [script, setScript] = useState<GenerateScriptResponse | null>(null);
  const [video, setVideo] = useState<GenerateVideoResponse | null>(null);
  const [faceAnchorPath, setFaceAnchorPath] = useState<string | null>(null);

  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<Record<string, string | null>>({});

  const setBusyKey = (k: string, v: boolean) => setBusy((p) => ({ ...p, [k]: v }));
  const setErr = (k: string, v: string | null) => setErrors((p) => ({ ...p, [k]: v }));

  const wardrobe = useMemo(() => [...serverWardrobe, ...localWardrobe], [serverWardrobe, localWardrobe]);
  const serverWardrobeIds = useMemo(() => serverWardrobe.map((g) => g.id), [serverWardrobe]);

  const refreshServerWardrobe = async () => {
    try {
      const items = await apiGet<GarmentRecord[]>("/garments");
      setServerWardrobe(items);
    } catch {
      // If server isn't reachable, keep whatever we have.
    }
  };

  useEffect(() => {
    void refreshServerWardrobe();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const ingest = async (file: File, hints: string | undefined) => {
    setBusyKey("ingest", true);
    setErr("ingest", null);
    try {
      const fd = new FormData();
      fd.append("file", file);
      if (hints) fd.append("hints", hints);
      const res = await apiPostMultipart<{ garment: GarmentRecord }>("/ingest-garment", fd);
      setServerWardrobe((w) => [...w, res.garment]);
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
      setLocalWardrobe((w) => [...w, next]);
      setErr("ingest", e instanceof ApiError ? "Couldn’t reach the server. Saved locally for the demo." : "Saved locally for the demo.");
    } finally {
      setBusyKey("ingest", false);
    }
  };

  const removeGarment = async (id: string) => {
    setBusyKey("delete", true);
    setErr("ingest", null);
    try {
      if (!id.startsWith("local-")) {
        await apiDelete(`/garments/${id}`);
      }
    } catch {
      // If backend isn't reachable, still remove locally for demo control.
    } finally {
      if (id.startsWith("local-")) {
        setLocalWardrobe((w) => w.filter((g) => g.id !== id));
      } else {
        setServerWardrobe((w) => w.filter((g) => g.id !== id));
      }
      setBusyKey("delete", false);
    }
  };

  const recommend = async () => {
    setBusyKey("rec", true);
    setErr("rec", null);
    try {
      const occasion = context.occasion.trim() || "work_presentation";
      const weather = context.weather.trim() || "mild_clear";
      const vibe = context.vibe.trim() || "quiet_luxury";
      const preference = context.preference.trim();
      const res = await apiPostJson<RecommendOutfitResponse>("/recommend-outfit", {
        occasion,
        weather,
        vibe,
        wardrobe_item_ids: serverWardrobeIds,
        user_preference: preference.length ? preference : null,
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
        wardrobe_item_ids: serverWardrobeIds,
      });
      setPurchase(res);
    } catch (e) {
      setErr("pur", "Couldn’t run a live analysis. Showing a demo result.");
      setPurchase(mockPurchase);
    } finally {
      setBusyKey("pur", false);
    }
  };

  const ingestCandidate = async (file: File, hints: string | undefined) => {
    const fd = new FormData();
    fd.append("file", file);
    if (hints) fd.append("hints", hints);
    const res = await apiPostMultipart<{ garment: GarmentRecord }>("/ingest-garment", fd);
    return res.garment;
  };

  const cleanupCandidate = async (id: string) => {
    try {
      await apiDelete(`/garments/${id}`);
    } catch {
      // ignore
    }
  };

  const genScript = async (body: GenerateScriptRequestBody) => {
    setBusyKey("scr", true);
    setErr("scr", null);
    try {
      const res = await apiPostJson<GenerateScriptResponse>("/generate-script", body);
      setScript(res);
    } catch (e) {
      setErr("scr", "Couldn’t generate live copy. Showing a demo script.");
      setScript(mockScript);
    } finally {
      setBusyKey("scr", false);
    }
  };

  const renderVideo = async (body: GenerateVideoRequestBody) => {
    setBusyKey("vid", true);
    setErr("vid", null);
    try {
      if (!recommendation || recommendation.garments.length === 0) {
        setErr("vid", "Pick an outfit first (from Style or Buy Analyzer), then generate a preview.");
        return;
      }
      const res = await apiPostJson<GenerateVideoResponse>("/generate-video", body);
      setVideo(res);
    } catch (e) {
      setErr("vid", "Couldn’t generate a live preview. Showing a demo preview.");
      setVideo(mockVideo);
    } finally {
      setBusyKey("vid", false);
    }
  };

  const uploadFaceAnchor = async (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", "face");
    const res = await apiPostMultipart<{ path: string }>("/upload-anchor", fd);
    setFaceAnchorPath(res.path);
  };

  return (
    <ImageLightboxProvider>
      <AppShell route={route} onRoute={setRoute}>
        {route === "home" ? <HomePage onGoWardrobe={() => setRoute("wardrobe")} /> : null}
        {route === "wardrobe" ? (
          <WardrobePage
            wardrobe={wardrobe}
            busy={!!busy.ingest || !!busy.delete}
            error={errors.ingest}
            onIngest={ingest}
            onDelete={removeGarment}
            onNext={() => setRoute("style")}
          />
        ) : null}
        {route === "style" ? (
          <StylePage
            context={context}
            onChange={setContext}
            onRecommend={recommend}
            onUseOutfit={(outfit) => {
              setRecommendation(outfit);
              setRoute("content");
            }}
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
            onUseCombo={({ title, garmentIds, occasion, description }) => {
              const garments = garmentIds
                .map((id) => wardrobe.find((g) => g.id === id))
                .filter(Boolean) as GarmentRecord[];
              const rec = {
                outfit_items: garmentIds.map((id) => ({ garment_id: id, role: "piece" })),
                garments,
                explanation: description ? `${title}. ${description}` : title,
                confidence: 0.62,
                retrieved_style_rule_ids: [],
                used_live_agent: false,
              };
              setRecommendation(rec);
              setRoute("content");
            }}
            onIngestCandidate={ingestCandidate}
            onCleanupCandidate={cleanupCandidate}
          />
        ) : null}
        {route === "content" ? (
          <ContentPage
            recommendation={recommendation}
            script={script}
            video={video}
            scriptBusy={!!busy.scr}
            videoBusy={!!busy.vid}
            faceAnchorPath={faceAnchorPath}
            onUploadFaceAnchor={uploadFaceAnchor}
            onGenerateScript={genScript}
            onRenderVideo={renderVideo}
            stylePreference={context.preference}
          />
        ) : null}
      </AppShell>
      <ChatWidget
        context={{
          occasion: context.occasion,
          weather: context.weather,
          vibe: context.vibe,
          preference: context.preference,
          wardrobe_item_ids: serverWardrobeIds,
          outfit_summary: recommendation?.garments.map((g) => `${g.color} ${g.category}`).join(", ") ?? null,
          face_anchor_path: faceAnchorPath,
        }}
        onApplyResult={(res: AssistantTurnResponse) => {
          if (res.recommendation) setRecommendation(res.recommendation);
          if (res.script) setScript(res.script);
          if (res.video) setVideo(res.video);
        }}
      />
    </ImageLightboxProvider>
  );
}
