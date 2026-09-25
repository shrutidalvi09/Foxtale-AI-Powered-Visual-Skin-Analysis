import { forwardRef, useCallback, useEffect, useImperativeHandle, useRef, useState } from "react";
import { AlertTriangle, Camera, ImagePlus, RotateCcw, Sparkles, Video, VideoOff } from "lucide-react";

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
            <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 whitespace-nowrap rounded-full bg-black/60 px-4 py-1.5 text-xs font-semibold text-white backdrop-blur">
              <Sparkles size={14} className="text-fox-300" />
              {ready ? "Position your face inside the frame" : "Getting the camera ready..."}
            </div>
            {count !== null && (
              <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                <span key={count} className="count-pop text-8xl font-extrabold text-white drop-shadow-lg">{count}</span>
              </div>
            )}
          </>
        )}
      </div>

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
