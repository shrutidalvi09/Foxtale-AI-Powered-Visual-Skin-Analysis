import { useEffect } from "react";
import type { ReactNode } from "react";
import { ShieldAlert, X } from "lucide-react";
import type { SeverityLevel } from "../types/analysis";
import { scoreColor } from "../lib/format";
import { useCountUp, useInView } from "../lib/motion";

export function LevelPill({ level, className = "" }: { level: SeverityLevel; className?: string }) {
  return <span className={`pill lvl-${level} ${className}`}>{level.charAt(0).toUpperCase() + level.slice(1)}</span>;
}

export function IconBadge({ children, tone = "fox" }: { children: ReactNode; tone?: "fox" | "green" | "blue" | "violet" }) {
  const tones = {
    fox: "bg-fox-50 text-fox-500 dark:bg-fox-500/15",
    green: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15",
    blue: "bg-blue-50 text-blue-600 dark:bg-blue-500/15",
    violet: "bg-violet-50 text-violet-600 dark:bg-violet-500/15",
  };
  return (
    <span className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full ${tones[tone]}`}>{children}</span>
  );
}

export function SectionTitle({ title, subtitle, icon }: { title: string; subtitle?: string; icon?: ReactNode }) {
  return (
    <div className="flex items-start gap-3">
      {icon && <IconBadge>{icon}</IconBadge>}
      <div>
        <h2 className="text-[15px] font-extrabold text-ink">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-muted">{subtitle}</p>}
      </div>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-extrabold uppercase tracking-wide text-ink sm:text-[28px]">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Disclaimer({ compact = false }: { compact?: boolean }) {
  return (
    <div className={`flex items-start gap-3 rounded-2xl border border-fox-500/20 bg-fox-50 dark:bg-fox-500/10 ${compact ? "p-3" : "p-4"}`}>
      <ShieldAlert className="mt-0.5 shrink-0 text-fox-500" size={compact ? 18 : 20} />
      <p className={`leading-relaxed text-ink ${compact ? "text-xs" : "text-sm"}`}>
        <span className="font-bold">AI Disclaimer:</span> This analysis is based only on visible features in the captured
        image and is not a medical diagnosis. For persistent, painful, spreading, or concerning skin changes, consult a
        qualified dermatologist.
      </p>
    </div>
  );
}

export function ScoreRing({ score, size = 132 }: { score: number | null | undefined; size?: number }) {
  const stroke = 11;
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const value = score ?? 0;
  const [ref, seen] = useInView<HTMLDivElement>(0.3);
  const shown = useCountUp(value, 1100, seen);
  return (
    <div ref={ref} className="relative shrink-0" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--line)" strokeWidth={stroke} />
        {score != null && (
          <circle
            cx={size / 2} cy={size / 2} r={r} fill="none" stroke={scoreColor(value)} strokeWidth={stroke}
            strokeLinecap="round" strokeDasharray={c} strokeDashoffset={seen ? c * (1 - value / 100) : c}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.22, 1, 0.36, 1) .15s" }}
          />
        )}
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span className="text-[34px] font-extrabold leading-none text-ink">{score == null ? "--" : shown}</span>
        {score != null && <span className="mt-1 text-[11px] text-muted">out of 100</span>}
      </div>
    </div>
  );
}

export function ScoreBar({ score }: { score: number }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.2);
  return (
    <div ref={ref} className="h-2.5 w-full overflow-hidden rounded-full bg-line">
      <div
        className="h-full rounded-full"
        style={{
          width: seen ? `${Math.max(4, score)}%` : "0%", background: scoreColor(score),
          transition: "width .9s cubic-bezier(0.22, 1, 0.36, 1) .1s",
        }}
      />
    </div>
  );
}

export function Modal({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="page-enter fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-[2px]" onClick={onClose} role="presentation">
      <div
        role="dialog" aria-modal="true" aria-label={title}
        className="card pop w-full max-w-md p-6" onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-3 flex items-start justify-between gap-4">
          <h3 className="text-lg font-extrabold text-ink">{title}</h3>
          <button onClick={onClose} aria-label="Close" className="rounded-full p-1 text-muted hover:bg-soft"><X size={18} /></button>
        </div>
        {children}
      </div>
    </div>
  );
}

export function EmptyState({ icon, title, body, action }: { icon: ReactNode; title: string; body: string; action?: ReactNode }) {
  return (
    <div className="card page-enter mx-auto flex max-w-lg flex-col items-center px-8 py-14 text-center">
      <span className="pop float mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15">{icon}</span>
      <h2 className="text-xl font-extrabold text-ink">{title}</h2>
      <p className="mt-2 text-sm text-muted">{body}</p>
      {action && <div className="mt-6">{action}</div>}
    </div>
  );
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-3 py-16 text-muted" role="status">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-line border-t-fox-500" />
      <span className="text-sm">{label}...</span>
    </div>
  );
}
