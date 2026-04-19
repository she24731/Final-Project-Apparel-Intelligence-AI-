import type {
  GarmentRecord,
  GenerateScriptResponse,
  GenerateVideoResponse,
  PurchaseAnalysisResponse,
  RecommendOutfitResponse,
} from "@/types";

export const mockWardrobe: GarmentRecord[] = [
  {
    id: "g-100",
    category: "outerwear",
    color: "charcoal",
    formality_score: 0.62,
    season: "winter",
    tags: ["wool", "minimal"],
    image_path: "uploads/charcoal_coat.png",
    embedding: [],
  },
  {
    id: "g-101",
    category: "top",
    color: "ivory",
    formality_score: 0.42,
    season: "all-season",
    tags: ["cotton", "oxford"],
    image_path: "uploads/ivory_shirt.png",
    embedding: [],
  },
  {
    id: "g-102",
    category: "bottom",
    color: "navy",
    formality_score: 0.48,
    season: "all-season",
    tags: ["tailored", "chino"],
    image_path: "uploads/navy_chinos.png",
    embedding: [],
  },
  {
    id: "g-103",
    category: "shoes",
    color: "brown",
    formality_score: 0.55,
    season: "all-season",
    tags: ["leather", "loafer"],
    image_path: "uploads/brown_loafer.png",
    embedding: [],
  },
];

export const mockRecommendation: RecommendOutfitResponse = {
  outfit_items: [
    { garment_id: "g-101", role: "top" },
    { garment_id: "g-102", role: "bottom" },
    { garment_id: "g-103", role: "footwear" },
    { garment_id: "g-100", role: "outerwear" },
  ],
  garments: mockWardrobe,
  explanation:
    "Quiet-luxury read: ivory oxford + navy chinos keeps contrast soft; charcoal coat elevates without theatrics. Brown loafers bridge day-to-night.",
  confidence: 0.84,
  retrieved_style_rule_ids: ["rule_formality_balance", "rule_color_harmony"],
  used_live_agent: false,
};

export const mockPurchase: PurchaseAnalysisResponse = {
  compatibility_score: 0.71,
  outfit_combination_potential: 5,
  recommendation: "BUY",
  explanation:
    "The candidate anchors multiple pairings with existing neutrals and does not duplicate silhouette roles already saturated in the wardrobe.",
  rationale_bullets: [
    "Top-3 cosine alignment vs wardrobe: 0.71",
    "Heuristic new outfit combinations: 5",
    "Formality band matches your stated work-social range.",
  ],
  used_live_agent: false,
};

export const mockScript: GenerateScriptResponse = {
  script:
    "If you only remember one thing about how I dress: I optimize for signal, not noise. Today’s look is calm tailoring—coat, oxford, chinos, loafers—because I want the conversation to lead, not the outfit.",
  caption: null,
  used_live_agent: false,
};

export const mockVideo: GenerateVideoResponse = {
  status: "mock",
  job_id: "mock-job-001",
  preview_message:
    "Mock runway reel: slow dolly-in, natural light, fabric drape emphasis. Hook Runway/Veo here for production.",
  video_url: null,
  provider: "mock",
};
