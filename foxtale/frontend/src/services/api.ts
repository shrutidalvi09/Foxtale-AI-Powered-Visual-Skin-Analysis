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
