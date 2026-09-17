import type { AnalyzeResponse } from "../types/analysis";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

/** Convert a captured data URL (from <canvas>.toDataURL) into a File for upload. */
export async function dataUrlToFile(dataUrl: string, filename = "scan.jpg"): Promise<File> {
  const res = await fetch(dataUrl);
  const blob = await res.blob();
  return new File([blob], filename, { type: blob.type || "image/jpeg" });
}

export async function analyzeImage(imageFile: File): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("image", imageFile);

  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}/api/analyze`, {
      method: "POST",
      body: form,
    });
  } catch {
    throw new ApiError(
      "Could not reach the Foxtale server. Make sure the backend is running.",
      0
    );
  }

  if (!res.ok) {
    let detail = "Something went wrong while analyzing the image.";
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse failure
    }
    throw new ApiError(detail, res.status);
  }

  return (await res.json()) as AnalyzeResponse;
}
