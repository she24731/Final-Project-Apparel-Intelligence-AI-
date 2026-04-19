export type GarmentCategory = "top" | "bottom" | "outerwear" | "shoes" | "accessory";

export interface GarmentRecord {
  id: string;
  category: GarmentCategory | string;
  color: string;
  formality_score: number;
  season: string;
  tags: string[];
  image_path: string;
  embedding: number[];
}

export interface OutfitItemRef {
  garment_id: string;
  role: string;
}

export interface RecommendOutfitResponse {
  outfit_items: OutfitItemRef[];
  garments: GarmentRecord[];
  explanation: string;
  confidence: number;
  retrieved_style_rule_ids: string[];
  used_live_agent: boolean;
}

export type PurchaseRecommendation = "BUY" | "NO_BUY" | "MAYBE";

export interface PurchaseAnalysisResponse {
  compatibility_score: number;
  outfit_combination_potential: number;
  compatibility_score_0_100?: number | null;
  versatility_score_0_100?: number | null;
  redundancy_score_0_100?: number | null;
  estimated_new_combinations?: number | null;
  top_matching_existing_items?: string[];
  outfit_suggestions?: { title: string; occasion?: string | null; description?: string | null; garment_ids: string[]; reason?: string | null }[];
  decision_criteria?: string[];
  recommendation: PurchaseRecommendation;
  explanation: string;
  rationale_bullets: string[];
  used_live_agent: boolean;
}

export interface GenerateScriptResponse {
  script: string;
  caption: string | null;
  hashtags?: string[] | null;
  used_live_agent: boolean;
}

export interface GenerateScriptRequestBody {
  platform: "linkedin" | "instagram" | "tiktok";
  outfit_summary: string;
  user_voice?: string | null;
  tone?: string | null;
  emotion?: string | null;
  target_audience?: string | null;
  scenario?: string | null;
  vibe?: string | null;
}

export interface ReelSceneDraft {
  anchor_image_path: string | null;
  description: string;
  narration: string;
}

export interface PreviewReelCopyResponse {
  description: string;
  narration_text: string;
  video_prompt: string;
  scenes: ReelSceneDraft[];
}

export interface GenerateVideoRequestBody {
  scene_prompt: string;
  anchor_image_paths: string[];
  duration_seconds: number;
  face_anchor_image_path: string | null;
  narration_text: string | null;
}

export interface SocialPostPrepareResponse {
  platform: string;
  clipboard_text: string;
  linkedin_share_url: string | null;
  instagram_web_url: string;
  tiktok_upload_url: string;
  notes: string;
}

export interface GenerateVideoResponse {
  status: "queued" | "completed" | "failed" | "mock";
  job_id: string;
  preview_message: string;
  video_url: string | null;
  provider: string;
  description?: string | null;
  narration_text?: string | null;
  video_prompt?: string | null;
}

export interface AssistantTurnResponse {
  reply: string;
  actions: string[];
  recommendation?: RecommendOutfitResponse | null;
  script?: GenerateScriptResponse | null;
  video?: GenerateVideoResponse | null;
}

export interface ChatContextPayload {
  occasion: string;
  weather: string;
  vibe: string;
  preference: string;
  wardrobe_item_ids: string[];
  outfit_summary: string | null;
  face_anchor_path: string | null;
}

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: string;
}
