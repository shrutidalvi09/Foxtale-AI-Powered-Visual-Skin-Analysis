import { useCallback, useEffect, useRef, useState } from "react";
import { Camera, RotateCcw, Video, VideoOff, AlertTriangle } from "lucide-react";
import FaceOverlay from "./FaceOverlay";

interface CameraScannerProps {
  capturedImage: string | null;
  onCapture: (dataUrl: string) => void;
  onRetake: () => void;
}

export default function CameraScanner({ capturedImage, onCapture, onRetake }: CameraScannerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [isStreaming, setIsStreaming] = useState(false);
  const [permissionError, setPermissionError] = useState<string | null>(null);
  const [starting, setStarting] = useState(false);

  const stopCamera = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    setIsStreaming(false);
  }, []);

  const startCamera = useCallback(async () => {
    setPermissionError(null);
    setStarting(true);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: "user", width: { ideal: 720 }, height: { ideal: 720 } },
        audio: false,
      });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play();
      }
      setIsStreaming(true);
    } catch (err) {
      setIsStreaming(false);
      setPermissionError(
        "Camera permission is required for face scanning. Please enable camera access in your browser settings."
      );
    } finally {
      setStarting(false);
    }
  }, []);

  useEffect(() => {
    return () => stopCamera();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleCapture = useCallback(() => {
    const video = videoRef.current;
    if (!video) return;
    const size = Math.min(video.videoWidth, video.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const sx = (video.videoWidth - size) / 2;
    const sy = (video.videoHeight - size) / 2;
    ctx.drawImage(video, sx, sy, size, size, 0, 0, size, size);
    const dataUrl = canvas.toDataURL("image/jpeg", 0.92);
    onCapture(dataUrl);
    stopCamera();
  }, [onCapture, stopCamera]);

  const handleRetake = useCallback(() => {
    onRetake();
    startCamera();
  }, [onRetake, startCamera]);

  return (
    <div className="flex flex-col items-center gap-5">
      <div className="relative aspect-square w-full max-w-md overflow-hidden rounded-3xl bg-navy-900 shadow-glass">
        {capturedImage ? (
          <img src={capturedImage} alt="Captured face" className="h-full w-full object-cover" />
        ) : (
          <video
            ref={videoRef}
            className={`h-full w-full object-cover ${isStreaming ? "" : "opacity-0"}`}
            muted
            playsInline
          />
        )}

        {!capturedImage && !isStreaming && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-3 px-6 text-center">
            {permissionError ? (
              <>
                <AlertTriangle className="text-fox-400" size={32} />
                <p className="text-sm text-white/80">{permissionError}</p>
              </>
            ) : (
              <>
                <Video className="text-white/50" size={32} />
                <p className="text-sm text-white/60">Camera is off</p>
              </>
            )}
          </div>
        )}

        {!capturedImage && isStreaming && (
          <FaceOverlay active label="Position your face inside the frame" />
        )}
      </div>

      <div className="flex flex-wrap items-center justify-center gap-3">
        {capturedImage ? (
          <button onClick={handleRetake} className="btn-secondary">
            <RotateCcw size={18} />
            Retake
          </button>
        ) : isStreaming ? (
          <>
            <button onClick={handleCapture} className="btn-primary">
              <Camera size={18} />
              Capture
            </button>
            <button onClick={stopCamera} className="btn-secondary">
              <VideoOff size={18} />
              Stop Camera
            </button>
          </>
        ) : (
          <button onClick={startCamera} disabled={starting} className="btn-primary">
            <Video size={18} />
            {starting ? "Starting..." : "Start Camera"}
          </button>
        )}
      </div>
    </div>
  );
}
