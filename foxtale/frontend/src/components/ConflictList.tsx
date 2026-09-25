import { AlertOctagon, AlertTriangle, CheckCircle2, Info } from "lucide-react";

export interface Issue {
  severity: "avoid" | "caution" | "info";
  title: string;
  detail: string;
  fix: string;
  products: string[];
}

const STYLE = {
  avoid: { icon: AlertOctagon, box: "border-rose-300 bg-rose-50 dark:border-rose-500/40 dark:bg-rose-500/10", tone: "text-rose-600", label: "Avoid" },
  caution: { icon: AlertTriangle, box: "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10", tone: "text-amber-600", label: "Be careful" },
  info: { icon: Info, box: "border-line bg-soft", tone: "text-blue-500", label: "Good to know" },
} as const;

/** Routine check results. With no issues it shows a short all-clear. */
export default function ConflictList({ issues, emptyText = "No clashes found in this routine." }: { issues: Issue[]; emptyText?: string }) {
  if (issues.length === 0) {
    return (
      <p className="flex items-center gap-2 rounded-2xl border border-emerald-300 bg-emerald-50 p-3.5 text-sm font-semibold text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-200">
        <CheckCircle2 size={17} /> {emptyText}
      </p>
    );
  }
  return (
    <ul className="space-y-3">
      {issues.map((i) => {
        const st = STYLE[i.severity];
        const Icon = st.icon;
        return (
          <li key={i.title + i.products.join()} className={`page-enter rounded-2xl border p-4 ${st.box}`}>
            <p className="flex items-start gap-2.5 text-sm font-extrabold text-ink"><Icon size={18} className={`mt-0.5 shrink-0 ${st.tone}`} /> <span><span className={`mr-2 text-[10.5px] uppercase tracking-widest ${st.tone}`}>{st.label}</span>{i.title}</span></p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{i.detail}</p>
            <p className="mt-1.5 text-[13px] leading-relaxed text-ink"><b>What to do:</b> {i.fix}</p>
            {i.products.length > 0 && <p className="mt-1.5 text-[11.5px] text-muted">{i.products.join(" · ")}</p>}
          </li>
        );
      })}
    </ul>
  );
}
