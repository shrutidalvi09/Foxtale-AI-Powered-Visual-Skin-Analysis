export type SeverityLevel = "minimal" | "mild" | "moderate" | "noticeable";

export interface CategoryResult {
  level: SeverityLevel;
  confidence: number;
  count?: number | null;
}

export interface SkinAnalysis {
  acne_like_spots: CategoryResult;
  redness: CategoryResult;
  texture: CategoryResult;
  dryness_indicators: CategoryResult;
  // added by the v2 engine; absent on scans saved by older versions
  oiliness?: CategoryResult;
  tone_evenness?: CategoryResult;
  overall_score?: number | null;
  region_scores?: Record<string, Record<string, number>>;
  metrics?: Record<string, number>;
  skin_tone?: { label: string; ita: number; undertone: string; hue: number; swatch: string } | null;
  engine_version?: number;
}

export interface RegionObservation {
  region: string;
  category: string;
  observation: string;
  confidence: number;
  x: number;
  y: number;
}

export interface Quality {
  position_score: number;
  lighting_score: number;
  distance_score: number;
  sharpness_score: number;
  angle_score: number;
  overall: number;
  tips?: string[];
}

export interface Journal {
  routine: string[];
  environment: string[];
}

export interface Scan {
  id: string;
  timestamp: string;
  analysis: SkinAnalysis;
  regions: RegionObservation[];
  quality: Quality | null;
  hasImage: boolean;
  note: string;
  starred: boolean;
  journal: Journal;
  deletedAt: string | null;
  persisted: boolean;
  daysLeft?: number;
}

export type AnalysisErrorCode =
  | "no_face"
  | "multiple_faces"
  | "too_close"
  | "too_far"
  | "not_enough_skin";

export interface AnalyzeResponse {
  faceDetected: boolean;
  scan?: Scan;
  disclaimer: string;
  error?: AnalysisErrorCode;
  message?: string;
}

export interface CategoryRow {
  key: string;
  label: string;
  level: SeverityLevel;
  confidence: number;
  measurement: string;
  meaning: string;
}

export interface Suggestion {
  id: string;
  name: string;
  step: "cleanse" | "treat" | "eye" | "moisturize" | "protect";
  stepLabel: string;
  when: string;
  ingredients: string[];
  reason: string;
  howItWorks: string;
  howToUse: string;
  caution: string;
  url: string;
  size: string;
  price: number | null;
  priceSource: "foxtale" | "retailer_mrp";
  shape: "tube" | "dropper" | "jar";
  variantId: string | null;
  owned: boolean;
  image: string | null;
}

export interface SkinProfile {
  skinType: string;
  skinTypeReason: string;
  tone: { label: string; undertone: string; swatch: string; note: string | null } | null;
  spots: { total: number; pimples: number; marks: number; level: SeverityLevel };
  texture: { level: SeverityLevel };
  toneEvenness: { level: SeverityLevel | null };
}

export interface Finding {
  key: string;
  icon: string;
  category: string;
  headline: string;
  level: SeverityLevel | null;
  note: string;
  where: string;
  measured: boolean;
}

export interface Report {
  findings: Finding[];
  profile: SkinProfile;
  overallScore: number | null;
  scoreLabel: string | null;
  summary: string;
  categories: CategoryRow[];
  regionScores: { name: string; score: number; concern: string }[];
  changes: string[];
  recommendations: string[];
  methodology: {
    steps: { title: string; body: string }[];
    scoreExplanation: string;
    limitations: string;
  };
  areas: Record<string, string>;
  skincare: {
    skinType: string;
    tone?: string | null;
    concerns: { key: string; label: string }[];
    suggestions: Suggestion[];
    notes: string[];
    conflicts: { severity: "avoid" | "caution" | "info"; title: string; detail: string; fix: string; products: string[] }[];
    cost: { total: number; unpriced: number };
    priceNote: string;
    catalogDate: string;
  };
}

export interface Settings {
  save_history: boolean;
  save_images: boolean;
  theme: "light" | "dark";
  reminder_days: number;
  min_confidence: number;
  owned_products: string[];
  onboarding_complete: boolean;
  whatsapp_auto?: boolean;
  whatsapp_registered?: boolean;
  wishlist?: string[];
}

export interface Insights {
  totalScans: number;
  streak: number;
  badges: { label: string; kind: string; earned: boolean }[];
  firstScan: string | null;
  lastScan: string | null;
  daysSinceLast: number | null;
  trends: { label: string; direction: "improved" | "worsened" | "stable"; earlyLevel: string; recentLevel: string }[];
  scoreSeries: { timestamp: string; score: number | null }[];
  featureSeries: {
    timestamp: string;
    overall: number | null;
    acne: number | null;
    darkSpots: number | null;
    uniformity: number | null;
    poresScore: number | null;
    redness: number;
  }[];
  mostFrequentRegion: string | null;
  mostFrequentCategory: string | null;
  headline: string;
  baseline: Record<string, string>;
  latest: Scan | null;
}

export interface PrivacyStats {
  scanCount: number;
  trashCount: number;
  imageCount: number;
  diskBytes: number;
  dataDir: string;
}
