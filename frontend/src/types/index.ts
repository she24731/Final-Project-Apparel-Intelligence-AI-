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
  used_live_agent: boolean;
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

export interface ChatTurn {
  id: string;
  role: "user" | "assistant";
  content: string;
  ts: string;
}
