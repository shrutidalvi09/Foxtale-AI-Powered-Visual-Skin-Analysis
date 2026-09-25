import type {
  AnalyzeResponse,
  Insights,
  PrivacyStats,
  RegionObservation,
  Report,
  Scan,
  Settings,
  SkinAnalysis,
  Quality,
} from "../types/analysis";

export const API_BASE_URL: string = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, init);
  } catch {
    throw new ApiError("Could not reach the Foxtale server. Make sure the backend is running.", 0);
  }
  if (!res.ok) {
    let detail = "Something went wrong.";
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : detail;
    } catch {
      // keep the generic message
    }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

const json = (method: string, body: unknown): RequestInit => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

/** Convert a captured data URL (from <canvas>.toDataURL) into a File for upload. */
export async function dataUrlToFile(dataUrl: string, filename = "scan.jpg"): Promise<File> {
  const res = await fetch(dataUrl);
  const blob = await res.blob();
  return new File([blob], filename, { type: blob.type || "image/jpeg" });
}

export function analyzeImage(imageFile: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("image", imageFile);
  return request<AnalyzeResponse>("/api/analyze", { method: "POST", body: form });
}

export const health = () => request<{ status: string }>("/api/health");

// scans
export const listScans = () => request<Scan[]>("/api/scans");
export const getScan = (id: string) => request<Scan>(`/api/scans/${id}`);
export const scanImageUrl = (id: string) => `${API_BASE_URL}/api/scans/${id}/image`;
export const patchScan = (
  id: string,
  patch: { note?: string; starred?: boolean; journal?: { routine: string[]; environment: string[] } }
) => request<Scan>(`/api/scans/${id}`, json("PATCH", patch));
export const deleteScan = (id: string) => request<{ ok: boolean }>(`/api/scans/${id}`, { method: "DELETE" });

// trash
export const listTrash = () => request<Scan[]>("/api/trash");
export const restoreScan = (id: string) => request<{ ok: boolean }>(`/api/trash/${id}/restore`, { method: "POST" });
export const deleteForever = (id: string) => request<{ ok: boolean }>(`/api/trash/${id}`, { method: "DELETE" });
export const emptyTrash = () => request<{ deleted: number }>("/api/trash", { method: "DELETE" });

// report
export interface ReportInput {
  analysis: SkinAnalysis;
  regions: RegionObservation[];
  previousAnalysis?: SkinAnalysis | null;
  owned?: string[];
}
export const getReport = (body: ReportInput) => request<Report>("/api/report", json("POST", body));

export async function downloadPdf(
  scan: Scan,
  previous: SkinAnalysis | null,
  imageDataUrl: string | null
): Promise<Blob> {
  const body = {
    analysis: scan.analysis,
    regions: scan.regions,
    quality: scan.quality as Quality | null,
    timestamp: scan.timestamp,
    note: scan.note,
    previousAnalysis: previous,
    imageDataUrl: scan.hasImage ? null : imageDataUrl,
  };
  const query = scan.hasImage ? `?scanId=${encodeURIComponent(scan.id)}` : "";
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/report/pdf${query}`, json("POST", body));
  } catch {
    throw new ApiError("Could not reach the Foxtale server. Make sure the backend is running.", 0);
  }
  if (!res.ok) throw new ApiError("Could not build the PDF report.", res.status);
  return res.blob();
}

// dashboard + settings
export const getInsights = () => request<Insights>("/api/insights");
export const getSettings = () => request<Settings>("/api/settings");
export const putSettings = (patch: Partial<Settings>) => request<Settings>("/api/settings", json("PUT", patch));
export const getOptions = () => request<{ routine: string[]; environment: string[] }>("/api/options");

// privacy
export const getPrivacy = () => request<PrivacyStats>("/api/privacy");
export const exportUrl = () => `${API_BASE_URL}/api/export`;
export const wipeData = () => request<{ ok: boolean }>("/api/data", { method: "DELETE" });
export async function importData(file: File): Promise<{ imported: number }> {
  const form = new FormData();
  form.append("file", file);
  return request<{ imported: number }>("/api/import", { method: "POST", body: form });
}

export const productImageUrl = (path: string | null) => (path ? `${API_BASE_URL}${path}` : null);

// whatsapp
export interface WhatsAppStatus {
  configured: boolean;
  dryRun: boolean;
  registered: boolean;
  masked: string;
  auto: boolean;
  skipped: boolean;
}
export interface WhatsAppDelivery {
  status: "none" | "pending" | "sending" | "sent" | "failed";
  error: string | null;
  updatedAt: string | null;
}
export const getWhatsApp = () => request<WhatsAppStatus>("/api/whatsapp/status");
export const registerWhatsApp = (phone: string) =>
  request<{ sent: boolean; masked: string; dryRun: boolean }>("/api/whatsapp/register", json("POST", { phone }));
export const verifyWhatsApp = (code: string) => request<WhatsAppStatus>("/api/whatsapp/verify", json("POST", { code }));
export const skipWhatsApp = () => request<WhatsAppStatus>("/api/whatsapp/skip", { method: "POST" });
export const removeWhatsApp = () => request<WhatsAppStatus>("/api/whatsapp", { method: "DELETE" });
export const setWhatsAppAuto = (enabled: boolean) => request<WhatsAppStatus>("/api/whatsapp/auto", json("PUT", { enabled }));
export const getDelivery = (scanId: string) => request<WhatsAppDelivery>(`/api/whatsapp/delivery/${scanId}`);
export const resendWhatsApp = (scanId: string) => request<{ ok: boolean }>(`/api/whatsapp/resend/${scanId}`, { method: "POST" });

// live camera preview
export interface LiveSpot {
  x: number;
  y: number;
  r: number;
  kind: "pimple" | "mark";
  contrast: number;
}
export interface LiveResult {
  face: { x: number; y: number; w: number; h: number } | null;
  spots: LiveSpot[];
  message: string | null;
  error: string | null;
  checks?: { lighting: string; distance: string; centered: string; sharpness: string };
}
export async function liveScan(frame: Blob, signal?: AbortSignal): Promise<LiveResult> {
  const form = new FormData();
  form.append("image", frame, "frame.jpg");
  return request<LiveResult>("/api/live", { method: "POST", body: form, signal });
}

// profile (onboarding questionnaire)
export interface Profile {
  name: string;
  age_range: string;
  gender: string;
  goals: string[];
  sensitive_skin: boolean;
  pregnant: boolean;
  allergies: string;
  budget: "any" | "low" | "mid";
  onboarded: boolean;
}
export const getProfile = () => request<Partial<Profile>>("/api/profile");
export const putProfile = (p: Profile) => request<Profile>("/api/profile", json("PUT", p));

// routine tracker
export interface RoutineState {
  today: { AM: string[]; PM: string[] };
  history: { day: string; am: number; pm: number }[];
  streak: number;
  todayDate: string;
}
export const getRoutine = (days = 21) => request<RoutineState>(`/api/routine?days=${days}`);
export const toggleRoutine = (day: string, slot: "AM" | "PM", productId: string, done: boolean) =>
  request<{ ok: boolean }>("/api/routine", json("POST", { day, slot, productId, done }));

/** Foxtale's Shopify cart link: opens foxtale.in with these variants already in the cart. */
export const cartUrl = (variantIds: string[]) =>
  `https://foxtale.in/cart/${variantIds.map((v) => `${v}:1`).join(",")}`;

// ingredient checker, product results, weekly check-in
export interface IngredientFinding {
  severity: "avoid" | "caution" | "info";
  ingredient: string;
  label: string;
  why: string;
}
export interface IngredientResult {
  ok: boolean;
  message?: string;
  verdict?: "good" | "caution" | "avoid";
  summary?: string;
  findings?: IngredientFinding[];
  positives?: string[];
  conflicts?: { with: string; detail: string }[];
  counts?: { ingredients: number; recognised: number; unrecognised: number };
  note?: string;
  usedProfile?: boolean;
}
export const checkIngredients = (text: string) => request<IngredientResult>("/api/ingredients/check", json("POST", { text }));

export interface ProductEffect {
  productId: string;
  name: string;
  image: string;
  startedAt: string;
  days: number;
  status: "collecting" | "improving" | "steady" | "mixed" | "worse";
  message: string;
  startedWith: string[];
  before: number;
  after: number;
  metrics: { target: string; label: string; unit: string; before: number; after: number; delta: number; verdict: "improved" | "steady" | "worse" }[];
}
export const getEffects = () => request<ProductEffect[]>("/api/effects");
export const setProductStart = (productId: string, startedAt: string) =>
  request<{ ok: boolean }>("/api/effects/start", json("PUT", { productId, startedAt }));

export interface DigestState {
  enabled: boolean;
  day: number;
  hour: number;
  lastSent: string | null;
  registered: boolean;
  preview: { name: string; skin: string; routine: string; tip: string };
}
export const getDigest = () => request<DigestState>("/api/digest");
export const putDigest = (enabled: boolean, day: number, hour: number) => request<DigestState>("/api/digest", json("PUT", { enabled, day, hour }));
export const sendDigestNow = () => request<{ ok: boolean }>("/api/digest/send", { method: "POST" });

export interface RoutineCheck {
  products: string[];
  issues: { severity: "avoid" | "caution" | "info"; title: string; detail: string; fix: string; products: string[] }[];
}
export const getRoutineCheck = () => request<RoutineCheck>("/api/routine/check");

// shop catalog, skin weather, skin diary
export interface CatalogProduct {
  id: string;
  name: string;
  step: "cleanse" | "treat" | "eye" | "moisturize" | "protect";
  stepLabel: string;
  when: string;
  ingredients: string[];
  targets: string[];
  targetLabels: string[];
  skinTypes: string[];
  active: boolean;
  howItWorks: string;
  howToUse: string;
  caution: string;
  url: string;
  size: string;
  price: number | null;
  priceSource: "foxtale" | "retailer_mrp";
  variantId: string | null;
  shape: "tube" | "dropper" | "jar";
  reason: string;
  image: string | null;
  owned: boolean;
}
export interface Combo {
  id: string;
  name: string;
  price_inr: number;
  variant_id: string;
  url: string;
  concerns: string[];
  highlights: string[];
  has_retinol: boolean;
  has_acids: boolean;
  image: string;
}
export interface Catalog {
  products: CatalogProduct[];
  combos: Combo[];
  comboNote: string;
  catalogDate: string;
  priceNote: string;
}
export const getCatalog = () => request<Catalog>("/api/catalog");
export const comboImageUrl = (path: string) => `${API_BASE_URL}${path}`;

export interface WeatherTip {
  icon: string;
  tone: "good" | "ok" | "warn";
  title: string;
  text: string;
  products: string[];
  productNames: string[];
}
export interface SkinWeather {
  configured: boolean;
  error?: string;
  city?: string;
  skinType?: string;
  temp?: number | null;
  humidity?: number | null;
  uv?: number | null;
  uvLabel?: string | null;
  aqi?: number | null;
  aqiLabel?: string | null;
  tips?: WeatherTip[];
}
export const getWeather = () => request<SkinWeather>("/api/weather");
export const setLocation = (city: string) => request<{ name: string; lat: number; lon: number }>("/api/location", json("PUT", { city }));
export const clearLocation = () => request<{ ok: boolean }>("/api/location", { method: "DELETE" });

export interface DiaryEntry {
  day: string;
  sleep_hours?: number;
  water_glasses?: number;
  stress?: number;
  skin_feel?: number;
  flags: string[];
  note: string;
}
export interface DiaryPatterns {
  daysLogged: number;
  daysWithFeel: number;
  streak: number;
  ready: boolean;
  insights: { factor: string; title: string; text: string; direction: "better" | "worse"; confidence: "low" | "medium"; n: number }[];
  scanInsights: { factor: string; title: string; text: string; direction: "better" | "worse"; confidence: "low" | "medium"; n: number }[];
  message: string;
  caveat: string;
}
export const getDiary = (days = 60) => request<{ entries: DiaryEntry[]; flags: Record<string, string> }>(`/api/diary?days=${days}`);
export const saveDiary = (day: string, e: Omit<DiaryEntry, "day">) => request<DiaryEntry>(`/api/diary/${day}`, json("PUT", e));
export const getDiaryPatterns = () => request<DiaryPatterns>("/api/diary/patterns");
