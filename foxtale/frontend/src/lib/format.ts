import type { SeverityLevel } from "../types/analysis";

export const LEVEL_SCORE: Record<SeverityLevel, number> = { minimal: 0, mild: 1, moderate: 2, noticeable: 3 };

export const LEVEL_DOT: Record<SeverityLevel, string> = {
  minimal: "#10b981",
  mild: "#f59e0b",
  moderate: "#f97316",
  noticeable: "#f43f5e",
};

export const CATEGORY_COLORS: Record<string, string> = {
  "Acne-like spots": "#f43f5e",
  Redness: "#f97316",
  Texture: "#f59e0b",
  "Dryness indicators": "#3b82f6",
  Oiliness: "#a3a316",
  "Tone evenness": "#a855f7",
};

export function formatDate(iso: string, withTime = true): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
  return withTime
    ? `${date}  ·  ${d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`
    : date;
}

export function scoreColor(score: number): string {
  if (score >= 85) return "#10b981";
  if (score >= 70) return "#84cc16";
  if (score >= 55) return "#f59e0b";
  return "#f43f5e";
}

export function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 18 ? "Good afternoon" : "Good evening";
}
