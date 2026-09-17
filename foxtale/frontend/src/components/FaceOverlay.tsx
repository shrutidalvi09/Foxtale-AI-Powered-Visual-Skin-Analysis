import { Sparkles } from "lucide-react";

interface FaceOverlayProps {
  active: boolean;
  label?: string;
}

/** Futuristic corner-bracket scanning frame overlaid on the live camera preview. */
export default function FaceOverlay({ active, label }: FaceOverlayProps) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
      <div className="relative h-[70%] w-[58%] max-w-xs">
        {/* corner brackets */}
        {(["top-0 left-0", "top-0 right-0", "bottom-0 left-0", "bottom-0 right-0"] as const).map(
          (pos, i) => (
            <span
              key={pos}
              className={`absolute ${pos} h-8 w-8 border-accent-400 ${
                i === 0
                  ? "border-l-4 border-t-4 rounded-tl-xl"
                  : i === 1
                  ? "border-r-4 border-t-4 rounded-tr-xl"
                  : i === 2
                  ? "border-l-4 border-b-4 rounded-bl-xl"
                  : "border-r-4 border-b-4 rounded-br-xl"
              } ${active ? "drop-shadow-[0_0_6px_rgba(94,168,255,0.8)]" : "opacity-60"}`}
            />
          )
        )}

        {/* scanning sweep line */}
        {active && (
          <div className="absolute inset-x-1 top-0 h-full overflow-hidden rounded-lg">
            <div className="h-1/3 w-full animate-scan-line bg-gradient-to-b from-transparent via-accent-400/70 to-transparent" />
          </div>
        )}
      </div>

      {label && (
        <div className="absolute bottom-4 left-1/2 flex -translate-x-1/2 items-center gap-2 rounded-full bg-navy-900/80 px-4 py-1.5 text-xs font-medium text-white backdrop-blur">
          <Sparkles size={14} className={active ? "animate-pulse-slow text-accent-400" : "text-white/60"} />
          {label}
        </div>
      )}
    </div>
  );
}
