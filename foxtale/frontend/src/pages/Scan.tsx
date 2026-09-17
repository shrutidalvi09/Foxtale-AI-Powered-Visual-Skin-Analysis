import { useCallback, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ScanFace, AlertCircle, RefreshCw } from "lucide-react";
import CameraScanner from "../components/CameraScanner";
import ScanProgress from "../components/ScanProgress";
import Disclaimer from "../components/Disclaimer";
import { analyzeImage, dataUrlToFile, ApiError } from "../services/api";
import { useScan } from "../context/ScanContext";
import type { AnalysisErrorCode } from "../types/analysis";

const ERROR_COPY: Record<AnalysisErrorCode, { title: string; body: string }> = {
  no_face: {
    title: "No face detected",
    body: "Please position your face inside the scanning area.",
  },
  multiple_faces: {
    title: "Multiple faces detected",
    body: "Please make sure only one person is visible.",
  },
  poor_lighting: {
    title: "Lighting is insufficient",
    body: "Move to a well-lit area and try again.",
  },
  too_close: {
    title: "Face too close",
    body: "Move slightly farther away.",
  },
  too_far: {
    title: "Face too far",
    body: "Move closer to the camera.",
  },
};

type Phase = "camera" | "scanning";

export default function Scan() {
  const navigate = useNavigate();
  const { capturedImage, setCapturedImage, setLatestResult, clearScan } = useScan();
  const [phase, setPhase] = useState<Phase>("camera");
  const [scanDone, setScanDone] = useState(false);
  const [errorInfo, setErrorInfo] = useState<{ title: string; body: string } | null>(null);

  const runAnalysis = useCallback(
    async (dataUrl: string) => {
      setPhase("scanning");
      setScanDone(false);
      setErrorInfo(null);
      try {
        const file = await dataUrlToFile(dataUrl);
        const result = await analyzeImage(file);
        setScanDone(true);

        if (!result.faceDetected) {
          const known = result.error && ERROR_COPY[result.error];
          setErrorInfo(
            known ?? {
              title: "Could not analyze image",
              body: result.message ?? "Please try again.",
            }
          );
          setPhase("camera");
          return;
        }

        if (result.analysis) {
          setLatestResult(result.analysis, result.regions);
          navigate("/results");
        }
      } catch (err) {
        setScanDone(true);
        const message = err instanceof ApiError ? err.message : "Something went wrong.";
        setErrorInfo({ title: "Analysis failed", body: message });
        setPhase("camera");
      }
    },
    [navigate, setLatestResult]
  );

  const handleCapture = useCallback((dataUrl: string) => {
    setCapturedImage(dataUrl);
  }, [setCapturedImage]);

  const handleRetake = useCallback(() => {
    clearScan();
    setErrorInfo(null);
  }, [clearScan]);

  const handleTryAgain = useCallback(() => {
    setErrorInfo(null);
    clearScan();
  }, [clearScan]);

  return (
    <div className="mx-auto max-w-2xl px-6 py-14">
      <div className="mb-8 text-center">
        <div className="mb-3 flex items-center justify-center gap-2 text-accent-600">
          <ScanFace size={22} />
          <span className="text-sm font-semibold uppercase tracking-wide">Face Scanner</span>
        </div>
        <h1 className="text-3xl font-extrabold text-navy-900">Scan your face</h1>
        <p className="mt-2 text-navy-600">Position your face here for a visual skin analysis.</p>
      </div>

      {errorInfo && (
        <div className="mb-6 flex items-start gap-3 rounded-2xl border border-rose-200 bg-rose-50 p-4">
          <AlertCircle className="mt-0.5 shrink-0 text-rose-500" size={20} />
          <div className="flex-1">
            <p className="text-sm font-semibold text-rose-700">{errorInfo.title}</p>
            <p className="text-sm text-rose-600">{errorInfo.body}</p>
          </div>
          <button onClick={handleTryAgain} className="shrink-0 text-rose-600" aria-label="Try again">
            <RefreshCw size={18} />
          </button>
        </div>
      )}

      {phase === "camera" && (
        <div className="flex flex-col items-center gap-6">
          <CameraScanner
            capturedImage={capturedImage}
            onCapture={handleCapture}
            onRetake={handleRetake}
          />

          {capturedImage && (
            <button onClick={() => runAnalysis(capturedImage)} className="btn-primary">
              <ScanFace size={18} />
              Start Scan
            </button>
          )}
        </div>
      )}

      {phase === "scanning" && (
        <div className="flex flex-col items-center gap-8 py-8">
          {capturedImage && (
            <div className="h-40 w-40 overflow-hidden rounded-2xl opacity-90 shadow-glass">
              <img src={capturedImage} alt="Captured face" className="h-full w-full object-cover" />
            </div>
          )}
          <ScanProgress done={scanDone} />
        </div>
      )}

      <div className="mt-10">
        <Disclaimer compact />
      </div>
    </div>
  );
}
