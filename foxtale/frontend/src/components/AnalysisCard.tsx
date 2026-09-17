import type { LucideIcon } from "lucide-react";
import type { SeverityLevel } from "../types/analysis";

const LEVEL_STYLES: Record<SeverityLevel, string> = {
  minimal: "bg-emerald-50 text-emerald-700 border-emerald-200",
  mild: "bg-amber-50 text-amber-700 border-amber-200",
  moderate: "bg-orange-50 text-orange-700 border-orange-200",
  noticeable: "bg-rose-50 text-rose-700 border-rose-200",
};

const LEVEL_LABEL: Record<SeverityLevel, string> = {
  minimal: "Minimal",
  mild: "Mild",
  moderate: "Moderate",
  noticeable: "Noticeable",
};

interface AnalysisCardProps {
  icon: LucideIcon;
  title: string;
  level: SeverityLevel;
  detail: string;
  confidence: number;
}

export default function AnalysisCard({ icon: Icon, title, level, detail, confidence }: AnalysisCardProps) {
  return (
    <div className="card flex flex-col gap-4 p-5">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2 text-navy-700">
          <Icon size={18} />
          <h3 className="text-sm font-semibold">{title}</h3>
        </div>
        <span className="text-xs text-navy-400">{Math.round(confidence * 100)}% confidence</span>
      </div>

      <div
        className={`inline-flex w-fit items-center rounded-full border px-3 py-1 text-sm font-bold ${LEVEL_STYLES[level]}`}
      >
        {LEVEL_LABEL[level]}
      </div>

      <p className="text-sm text-navy-600">{detail}</p>
    </div>
  );
}
