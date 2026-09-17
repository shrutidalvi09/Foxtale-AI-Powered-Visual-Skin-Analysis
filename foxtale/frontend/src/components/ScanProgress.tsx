import { useEffect, useState } from "react";
import { BadgeCheck } from "lucide-react";

const STEPS = [
  "Detecting face...",
  "Analyzing skin regions...",
  "Checking visible texture...",
  "Checking visible redness...",
  "Generating report...",
];

interface ScanProgressProps {
  /** True once the backend has actually responded; lets the animation finish gracefully. */
  done: boolean;
}

export default function ScanProgress({ done }: ScanProgressProps) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (done) return;
    const interval = setInterval(() => {
      setStepIndex((i) => Math.min(i + 1, STEPS.length - 1));
    }, 750);
    return () => clearInterval(interval);
  }, [done]);

  const progress = done ? 100 : Math.round(((stepIndex + 1) / STEPS.length) * 90);
  const label = done ? "Analysis complete" : STEPS[stepIndex];

  return (
    <div className="mx-auto w-full max-w-md">
      <div className="mb-3 flex items-center justify-center gap-2 text-sm font-semibold text-navy-800">
        {done ? (
          <BadgeCheck className="text-emerald-500" size={18} />
        ) : (
          <span className="h-2 w-2 animate-pulse-slow rounded-full bg-accent-500" />
        )}
        {label}
      </div>
      <div className="h-2.5 w-full overflow-hidden rounded-full bg-navy-900/10">
        <div
          className="h-full rounded-full bg-gradient-to-r from-accent-500 to-fox-500 transition-all duration-500 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      <p className="mt-2 text-center text-xs text-navy-600">{progress}%</p>
    </div>
  );
}
