export type SeverityLevel = "minimal" | "mild" | "moderate" | "noticeable";

export interface CategoryResult {
  level: SeverityLevel;
  confidence: number;
  count?: number;
}

export interface SkinAnalysis {
  acne_like_spots: CategoryResult;
  redness: CategoryResult;
  texture: CategoryResult;
  dryness_indicators: CategoryResult;
}

export interface RegionObservation {
  region: string;
  category: string;
  observation: string;
  confidence: number;
  x: number;
  y: number;
}

export type AnalysisErrorCode =
  | "no_face"
  | "multiple_faces"
  | "poor_lighting"
  | "too_close"
  | "too_far";

export interface AnalyzeResponse {
  faceDetected: boolean;
  analysis?: SkinAnalysis;
  regions: RegionObservation[];
  disclaimer: string;
  error?: AnalysisErrorCode;
  message?: string;
}

export interface ScanRecord {
  id: string;
  timestamp: string;
  analysis: SkinAnalysis;
  regions: RegionObservation[];
}
