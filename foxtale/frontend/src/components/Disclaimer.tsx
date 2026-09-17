import { ShieldAlert } from "lucide-react";

export default function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <div
      className={`flex items-start gap-3 rounded-2xl border border-fox-500/20 bg-fox-500/5 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <ShieldAlert className="mt-0.5 shrink-0 text-fox-600" size={compact ? 18 : 20} />
      <p className={`text-navy-800 ${compact ? "text-xs" : "text-sm"} leading-relaxed`}>
        <span className="font-semibold">AI Disclaimer:</span> This analysis is based only on
        visible features in the captured image and is not a medical diagnosis. For persistent,
        painful, spreading, or concerning skin changes, consult a qualified dermatologist.
      </p>
    </div>
  );
}
