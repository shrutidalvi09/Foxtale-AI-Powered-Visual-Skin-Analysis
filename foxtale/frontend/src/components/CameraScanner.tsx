import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { AlertTriangle, Camera, ImagePlus, RotateCcw, ScanSearch, Sparkles, Video, VideoOff } from "lucide-react";
import { liveScan } from "../services/api";
import type { LiveResult } from "../services/api";

const WARMUP_MIN_FRAMES = 8;
const WARMUP_MIN_LEVEL = 12;
const WARMUP_TIMEOUT_MS = 4000;
const BURST_FRAMES = 5;
const BURST_GAP_MS = 90;

export interface CameraScannerHandle {
  start: () => void;
  stop: () => void;
}

interface Props {
  capturedImage: string | null;
  onCapture: (dataUrl: string) => void;
  onRetake: () => void;
  countdown: boolean;
  disabled?: boolean;
}

function drawSquare(video: HTMLVideoElement, size: number): HTMLCanvasElement {
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const side = Math.min(video.videoWidth, video.videoHeight);
  canvas
    .getContext("2d", { willReadFrequently: true })
    ?.drawImage(video, (video.videoWidth - side) / 2, (video.videoHeight - side) / 2, side, side, 0, 0, size, size);
  return canvas;
}

/** Mean brightness and a sharpness proxy (variance of horizontal gradients) of a canvas. */
function measure(canvas: HTMLCanvasElement): { level: number; sharp: number } {
  const w = 96;
  const small = document.createElement("canvas");
  small.width = w;
  small.height = w;
  const ctx = small.getContext("2d", { willReadFrequently: true });
  if (!ctx) return { level: 255, sharp: 0 };
  ctx.drawImage(canvas, 0, 0, w, w);
  const { data } = ctx.getImageData(0, 0, w, w);
  let sum = 0;
  const grays = new Float32Array(w * w);
  for (let i = 0; i < w * w; i++) {
    const g = 0.299 * data[i * 4] + 0.587 * data[i * 4 + 1] + 0.114 * data[i * 4 + 2];
    grays[i] = g;
    sum += g;
  }
  let gsum = 0;
  let gsq = 0;
  let n = 0;
  for (let y = 0; y < w; y++) {
    for (let x = 1; x < w; x++) {
      const d = grays[y * w + x] - grays[y * w + x - 1];
      gsum += d;
      gsq += d * d;
      n++;
    }
  }
  const mean = gsum / n;
  return { level: sum / (w * w), sharp: gsq / n - mean * mean };
}

const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Camera preview + capture. The camera is OFF until the user asks for it, is
 * released on stop/unmount, waits for the sensor to settle before allowing a
 * capture (no black first frames), and picks the sharpest of a short burst.
 */
const CameraScanner = forwardRef<CameraScannerHandle, Props>(function CameraScanner(
  { capturedImage, onCapture, onRetake, countdown, disabled },
  ref
) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const [state, setState] = useState<"idle" | "starting" | "live">("idle");
  const [ready, setReady] = useState(false);
  const [count, setCount] = useState<number | null>(null);
  const [capturing, setCapturing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [flash, setFlash] = useState(0);
  const [live, setLive] = useState<LiveResult | null>(null);
  const capturingRef = useRef(false);
  const okStreak = useRef(0);
  const takeRef = useRef<(() => void) | null>(null);
  const [auto, setAuto] = useState<boolean>(() => {
    try {
      return localStorage.getItem("foxtale_autocapture") === "on";
    } catch {
      return false;
    }
  });
  const autoRef = useRef(auto);
  useEffect(() => {
    autoRef.current = auto;
    try {
      localStorage.setItem("foxtale_autocapture", auto ? "on" : "off");
    } catch {
      // ignore
    }
  }, [auto]);

  const stop = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setState("idle");
    setReady(false);
    setCount(null);
  }, []);

  const start = useCallback(async () => {
    setError(null);
    setReady(false);
    setState("starting");
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 1280 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      const video = videoRef.current;
      if (!video) return;
      video.srcObject = stream;
      await video.play();
      setState("live");

      // warm-up: wait for the auto-exposure to settle so the first frames are not black
      const began = performance.now();
      let frames = 0;
      let last = 0;
      let stable = 0;
      while (streamRef.current === stream && performance.now() - began < WARMUP_TIMEOUT_MS) {
        await sleep(90);
        if (video.videoWidth === 0) continue;
        const { level } = measure(drawSquare(video, 96));
        frames++;
        stable = Math.abs(level - last) < 3 ? stable + 1 : 0;
        last = level;
        if (frames >= WARMUP_MIN_FRAMES && level > WARMUP_MIN_LEVEL && stable >= 3) break;
      }
      if (streamRef.current === stream) setReady(true);
    } catch {
      stop();
      setError("Camera permission is required for face scanning. Please allow camera access in your browser settings, or upload a photo instead.");
    }
  }, [stop]);

  useImperativeHandle(ref, () => ({ start, stop }), [start, stop]);

  useEffect(() => () => stop(), [stop]);

  // Live spot check: every ~0.7 s a small copy of the frame goes to the local server, which answers with the
  // face box and any spots it can see. One request at a time; if the server is unreachable the preview just stays plain.
  useEffect(() => {
    capturingRef.current = capturing;
  }, [capturing]);

  useEffect(() => {
    if (state !== "live" || !ready) {
      setLive(null);
      return;
    }
    let stopped = false;
    let inFlight = false;
    const ctrl = new AbortController();
    const tick = async () => {
      const video = videoRef.current;
      if (stopped || inFlight || capturingRef.current || !video || video.videoWidth === 0) return;
      inFlight = true;
      try {
        const blob = await new Promise<Blob | null>((r) => drawSquare(video, 384).toBlob(r, "image/jpeg", 0.7));
        if (blob) {
          const res = await liveScan(blob, ctrl.signal);
          if (!stopped) {
            setLive(res);
            const c = res.checks;
            const allOk = !!res.face && !!c && c.lighting === "ok" && c.distance === "ok" && c.centered === "ok" && c.sharpness === "ok";
            okStreak.current = allOk ? okStreak.current + 1 : 0;
            if (autoRef.current && okStreak.current >= 3 && !capturingRef.current) {
              okStreak.current = 0;
              takeRef.current?.();
            }
          }
        }
      } catch {
        // preview only: ignore errors
      } finally {
        inFlight = false;
      }
    };
    tick();
    const id = setInterval(tick, 700);
    return () => {
      stopped = true;
      ctrl.abort();
      clearInterval(id);
    };
  }, [state, ready]);

  const takePhoto = useCallback(async () => {
    const video = videoRef.current;
    if (!video || capturing) return;
    setCapturing(true);
    if (countdown) {
      for (let n = 3; n >= 1; n--) {
        setCount(n);
        await sleep(800);
      }
      setCount(null);
    }
    const size = Math.min(video.videoWidth, video.videoHeight, 900);
    const frames: { canvas: HTMLCanvasElement; level: number; sharp: number }[] = [];
    for (let i = 0; i < BURST_FRAMES; i++) {
      const canvas = drawSquare(video, size);
      frames.push({ canvas, ...measure(canvas) });
      await sleep(BURST_GAP_MS);
    }
    const maxLevel = Math.max(...frames.map((f) => f.level));
    const usable = frames.filter((f) => f.level >= maxLevel * 0.85);
    const best = usable.reduce((a, b) => (b.sharp > a.sharp ? b : a));
    setFlash((f) => f + 1);
    onCapture(best.canvas.toDataURL("image/jpeg", 0.92));
    stop();
    setCapturing(false);
  }, [capturing, countdown, onCapture, stop]);

  takeRef.current = () => {
    void takePhoto();
  };

  const onFile = (file: File | undefined) => {
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      stop();
      onCapture(String(reader.result));
    };
    reader.readAsDataURL(file);
  };

  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative aspect-square w-full max-w-[520px] overflow-hidden rounded-[28px] bg-[#0b1224] shadow-card">
        {capturedImage ? (
          <img src={capturedImage} alt="Captured face" className="pop h-full w-full object-cover" />
        ) : (
          <video ref={videoRef} className={`h-full w-full -scale-x-100 object-cover ${state === "live" ? "" : "opacity-0"}`} muted playsInline />
        )}

        {flash > 0 && <div key={flash} className="flash pointer-events-none absolute inset-0 bg-white" aria-hidden />}

        {!capturedImage && state !== "live" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-8 text-center">
            {error ? (
              <>
                <AlertTriangle className="text-fox-400" size={34} />
                <p className="text-sm text-white/85">{error}</p>
              </>
            ) : (
              <>
                <span className={`flex h-20 w-20 items-center justify-center rounded-full border border-white/25 bg-white/10 ${state === "starting" ? "animate-pulse" : "float"}`}>
                  <Video className="text-fox-300" size={30} />
                </span>
                <p className="text-base font-bold text-white">{state === "starting" ? "Starting camera..." : "Camera is off"}</p>
                <p className="text-sm text-white/60">Start the camera when you are ready. Nothing is recorded until you press Capture.</p>
              </>
            )}
          </div>
        )}

        {!capturedImage && state === "live" && (
          <>
            <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
              <div className="relative h-[72%] w-[58%]">
                {["top-0 left-0 border-l-4 border-t-4 rounded-tl-2xl", "top-0 right-0 border-r-4 border-t-4 rounded-tr-2xl",
                  "bottom-0 left-0 border-l-4 border-b-4 rounded-bl-2xl", "bottom-0 right-0 border-r-4 border-b-4 rounded-br-2xl"].map((c) => (
                  <span key={c} className={`absolute h-9 w-9 border-fox-400 ${c} ${ready ? "drop-shadow-[0_0_6px_rgba(255,159,90,0.9)]" : "opacity-60"}`} />
                ))}
                {ready && (
                  <div className="absolute inset-x-1 top-0 h-full overflow-hidden rounded-lg">
                    <div className="h-1/3 w-full animate-scan-line bg-gradient-to-b from-transparent via-fox-400/50 to-transparent" />
                  </div>
                )}
              </div>
            </div>
            {ready && live?.face && (
              <div
                className="pointer-events-none absolute rounded-2xl border-2 border-emerald-400/90 shadow-[0_0_18px_rgba(52,211,153,0.45)] transition-all duration-300"
                style={{ left: `${(1 - live.face.x - live.face.w) * 100}%`, top: `${live.face.y * 100}%`, width: `${live.face.w * 100}%`, height: `${live.face.h * 100}%` }}
                aria-hidden
              />
            )}
            {ready && live?.spots.map((sp, i) => (
              <span
                key={`${i}-${Math.round(sp.x * 100)}-${Math.round(sp.y * 100)}`} aria-hidden
                className={`pop pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 ${sp.kind === "pimple" ? "border-rose-400 bg-rose-400/25" : "border-amber-300 bg-amber-300/20"}`}
                style={{ left: `${(1 - sp.x) * 100}%`, top: `${sp.y * 100}%`, width: `${Math.max(sp.r * 200, 3.5)}%`, aspectRatio: "1", transition: "left .35s ease, top .35s ease" }}
              />
            ))}
            {ready && (
              <div className="pointer-events-none absolute left-3 top-3 flex items-center gap-2 rounded-full bg-black/60 px-3 py-1.5 text-[11px] font-bold text-white backdrop-blur">
                <ScanSearch size={13} className="text-fox-300" />
                {live?.face
                  ? live.spots.length === 0 ? "Face found · no spots spotted"
                    : `${live.spots.filter((s) => s.kind === "pimple").length} pimple-like · ${live.spots.filter((s) => s.kind === "mark").length} marks spotted`
                  : "Looking for your face..."}
              </div>
            )}
            <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-black/60 px-4 py-1.5 text-xs font-semibold text-white backdrop-blur">
              <Sparkles size={14} className="text-fox-300" />
              {!ready ? "Getting the camera ready..." : live?.message ?? "Live preview · the full analysis runs when you capture"}
            </div>
            {count !== null && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <span key={count} className="count-pop text-8xl font-extrabold text-white drop-shadow-lg">{count}</span>
              </div>
            )}
          </>
        )}
      </div>

      {state === "live" && ready && (
        <div className="flex w-full max-w-[520px] flex-wrap justify-center gap-2" aria-live="polite">
          {([
            ["Lighting", live?.checks?.lighting, { too_dark: "Add more light", too_bright: "Too bright, reduce light" }],
            ["Distance", live?.checks?.distance, { too_far: "Move closer", too_close: "Move back" }],
            ["Position", live?.checks?.centered, { left: "Move left", right: "Move right", up: "Move down", down: "Move up" }],
            ["Sharpness", live?.checks?.sharpness, { blurry: "Hold still" }],
          ] as [string, string | undefined, Record<string, string>][]).map(([label, value, hints]) => {
            const known = live?.face && value;
            const ok = known && value === "ok";
            return (
              <span key={label} className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-bold transition-colors ${
                !known ? "border-line text-muted" : ok ? "border-emerald-400 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300" : "border-amber-400 bg-amber-50 text-amber-800 dark:bg-amber-500/10 dark:text-amber-200"
              }`}>
                {known ? (ok ? "✓" : "!") : "·"} {known && !ok ? hints[value as string] ?? label : label}
              </span>
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center justify-center gap-3">
        {capturedImage ? (
          <button
            className="btn-soft"
            disabled={disabled}
            onClick={() => {
              onRetake();
              start();
            }}
          >
            <RotateCcw size={16} /> Retake
          </button>
        ) : state === "live" ? (
          <>
            <button className="btn-cta" onClick={takePhoto} disabled={!ready || capturing}>
              <Camera size={18} /> {capturing ? "Capturing..." : "Capture"}
            </button>
            <button className="btn-soft" onClick={stop} disabled={capturing}>
              <VideoOff size={16} /> Stop Camera
            </button>
            <label className="flex cursor-pointer items-center gap-2 text-sm text-muted">
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} className="h-4 w-4 accent-fox-500" />
              Auto-capture when ready
            </label>
          </>
        ) : (
          <>
            <button className="btn-cta" onClick={start} disabled={state === "starting" || disabled}>
              <Video size={18} /> {state === "starting" ? "Starting..." : "Start Camera"}
            </button>
            <button className="btn-soft" onClick={() => fileRef.current?.click()} disabled={disabled}>
              <ImagePlus size={16} /> Upload Photo
            </button>
          </>
        )}
        <input ref={fileRef} type="file" accept="image/jpeg,image/png,image/webp" className="hidden" onChange={(e) => { onFile(e.target.files?.[0]); e.target.value = ""; }} />
      </div>
    </div>
  );
});

export default CameraScanner;
