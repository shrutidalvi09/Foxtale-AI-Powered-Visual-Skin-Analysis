import { useCallback, useEffect, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { BadgeCheck, BarChart3, Eye, Glasses, Maximize, Smile, Sun, TimerReset, AlertTriangle } from "lucide-react";
import CameraScanner from "../components/CameraScanner";
import type { CameraScannerHandle } from "../components/CameraScanner";
import { Disclaimer, PageHeader, Spinner } from "../components/ui";
import { WhatsAppGate } from "../components/WhatsApp";
import { useApp } from "../context/AppContext";
import { analyzeImage, ApiError, dataUrlToFile } from "../services/api";

const ERROR_COPY: Record<string, [string, string]> = {
  no_face: ["No face detected", "Please position your face inside the scanning area."],
  multiple_faces: ["Multiple faces detected", "Please make sure only one person is visible."],
  too_close: ["Face too close", "Move slightly farther away."],
  too_far: ["Face too far", "Move closer to the camera."],
  not_enough_skin: ["Not enough visible skin", "Face the camera and keep hair or hands off your face, then try again."],
};

const TIPS = [
  { icon: Eye, text: "Look straight at the camera" },
  { icon: Maximize, text: "Keep your face centered" },
  { icon: Sun, text: "Good natural lighting works best" },
  { icon: Glasses, text: "Remove glasses, hat, and heavy makeup" },
  { icon: Smile, text: "Relax and keep a neutral expression" },
];

const STEPS = ["Detecting face...", "Isolating skin...", "Measuring spots and redness...", "Checking texture and tone...", "Building your report..."];

function Progress({ done }: { done: boolean }) {
  const [i, setI] = useState(0);
  useEffect(() => {
    if (done) return;
    const t = setInterval(() => setI((n) => Math.min(n + 1, STEPS.length - 1)), 800);
    return () => clearInterval(t);
  }, [done]);
  const pct = done ? 100 : Math.round(((i + 1) / STEPS.length) * 90);
  return (
    <div className="mx-auto w-full max-w-md" role="status">
      <div className="mb-3 flex items-center justify-center gap-2 text-sm font-bold text-ink">
        {done ? <BadgeCheck className="pop text-emerald-500" size={18} /> : <span className="h-2 w-2 animate-pulse rounded-full bg-fox-500" />}
        {done ? "Analysis complete" : STEPS[i]}
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-line">
        <div className="relative h-full overflow-hidden rounded-full bg-gradient-to-r from-fox-400 to-fox-600 transition-all duration-500" style={{ width: `${pct}%` }}>
          {!done && <span className="skeleton !bg-transparent absolute inset-0" aria-hidden />}
        </div>
      </div>
      <ul className="mt-4 space-y-1.5 text-left text-[13px]">
        {STEPS.map((step, n) => {
          const complete = done || n < i;
          return (
            <li key={step} className={`flex items-center gap-2 transition-colors duration-300 ${complete ? "text-ink" : n === i ? "text-fox-text dark:text-fox-300" : "text-muted"}`}>
              <span className={`flex h-4 w-4 items-center justify-center rounded-full border text-[9px] ${complete ? "pop border-emerald-500 bg-emerald-500 text-white" : n === i ? "border-fox-500" : "border-line"}`}>{complete ? "✓" : ""}</span>
              {step.replace("...", "")}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

export default function Scan() {
  const navigate = useNavigate();
  const location = useLocation();
  const { setCurrent, bumpData, toast, whatsapp, backendOnline } = useApp();
  // Reports go to WhatsApp, so a verified number is needed before the first scan (unless the server has no WhatsApp set up).
  const needsGate = !!whatsapp && !whatsapp.registered && !whatsapp.skipped;
  const pendingStart = useRef(false);
  const camera = useRef<CameraScannerHandle>(null);
  const [captured, setCaptured] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<{ title: string; body: string } | null>(null);
  const [countdown, setCountdown] = useState<boolean>(() => {
    try {
      return localStorage.getItem("foxtale_countdown") !== "off";
    } catch {
      return true;
    }
  });

  // "Start New Scan" buttons elsewhere ask for the camera to open straight away (after registration, if needed).
  useEffect(() => {
    if ((location.state as { autostart?: boolean } | null)?.autostart) {
      pendingStart.current = true;
      navigate(location.pathname, { replace: true, state: null });
    }
  }, [location, navigate]);

  useEffect(() => {
    if (pendingStart.current && !needsGate && whatsapp) {
      pendingStart.current = false;
      // wait a tick so the camera component has mounted
      setTimeout(() => camera.current?.start(), 50);
    }
  }, [needsGate, whatsapp]);

  const toggleCountdown = () => {
    setCountdown((c) => {
      try {
        localStorage.setItem("foxtale_countdown", c ? "off" : "on");
      } catch {
        // ignore
      }
      return !c;
    });
  };

  const analyze = useCallback(async () => {
    if (!captured) return;
    setError(null);
    setAnalyzing(true);
    setDone(false);
    try {
      const result = await analyzeImage(await dataUrlToFile(captured));
      if (!result.faceDetected || !result.scan) {
        const [title, body] = ERROR_COPY[result.error ?? ""] ?? ["Could not analyze image", result.message ?? "Please try again."];
        setError({ title, body });
        setAnalyzing(false);
        return;
      }
      setDone(true);
      setCurrent({ scan: result.scan, imageDataUrl: captured });
      bumpData();
      setTimeout(() => navigate("/analysis"), 500);
    } catch (err) {
      setError({
        title: "Analysis failed",
        body: err instanceof ApiError ? err.message : "Something went wrong while analyzing this photo.",
      });
      toast("Analysis failed");
      setAnalyzing(false);
    }
  }, [captured, setCurrent, bumpData, navigate, toast]);

  return (
    <div className="animate-fade-up">
      <PageHeader title="Skin Scan" subtitle="Capture a clear photo of your face for a visible-skin analysis." />

      {whatsapp === null && backendOnline !== false ? (
        <Spinner label="Checking your WhatsApp setup" />
      ) : needsGate ? (
        <WhatsAppGate />
      ) : (
      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_340px]">
        <div className="card p-5 sm:p-7">
          {error && (
            <div key={error.title + error.body} className="shake mb-5 flex items-start gap-3 rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-800 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-200" role="alert">
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
              <p><span className="font-bold">{error.title}.</span> {error.body}</p>
            </div>
          )}

          <CameraScanner
            ref={camera}
            capturedImage={captured}
            onCapture={(d) => { setCaptured(d); setError(null); }}
            onRetake={() => { setCaptured(null); setError(null); }}
            countdown={countdown}
            disabled={analyzing}
          />

          {captured && (
            <div className="mt-6 flex flex-col items-center gap-4">
              {analyzing ? (
                <Progress done={done} />
              ) : (
                <button className="btn-cta" onClick={analyze}>
                  <BarChart3 size={18} /> Analyze
                </button>
              )}
            </div>
          )}
          {!captured && (
            <label className="mx-auto mt-5 flex w-fit cursor-pointer items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={countdown} onChange={toggleCountdown} className="h-4 w-4 accent-fox-500" />
              <TimerReset size={15} /> 3-second countdown before capture
            </label>
          )}
        </div>

        <aside className="space-y-5">
          <div className="card p-5">
            <h2 className="text-[15px] font-extrabold text-ink">Best scan tips</h2>
            <ul className="mt-3 space-y-3">
              {TIPS.map(({ icon: Icon, text }) => (
                <li key={text} className="flex items-center gap-3 text-sm text-ink">
                  <span className="flex h-8 w-8 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15"><Icon size={15} /></span>
                  {text}
                </li>
              ))}
            </ul>
          </div>
          <div className="card p-5">
            <h2 className="text-[15px] font-extrabold text-ink">What happens next</h2>
            <ol className="mt-3 space-y-2 text-sm text-muted">
              <li><b className="text-ink">1.</b> Press Analyze after capturing.</li>
              <li><b className="text-ink">2.</b> Your photo is measured on this computer.</li>
              <li><b className="text-ink">3.</b> Your report opens on the Analysis page, with a skincare routine matched to it.</li>
              {whatsapp?.registered && whatsapp.auto && <li><b className="text-ink">4.</b> The PDF report is sent to your WhatsApp ({whatsapp.masked}) automatically.</li>}
            </ol>
          </div>
          <Disclaimer compact />
        </aside>
      </div>
      )}
    </div>
  );
}
