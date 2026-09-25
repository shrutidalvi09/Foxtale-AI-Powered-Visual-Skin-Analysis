import { useMemo, useState } from "react";
import { Check, ChevronDown, ExternalLink, ListChecks, Moon, Sun } from "lucide-react";
import type { Report, Suggestion } from "../types/analysis";
import { productImageUrl } from "../services/api";
import { rupees } from "../lib/format";
import { Reveal } from "../lib/motion";

const STEP_STYLE: Record<string, { from: string; to: string; body: string }> = {
  cleanse: { from: "#e4f1ff", to: "#cfe4fb", body: "#3b8dff" },
  treat: { from: "#ffece0", to: "#ffd9c2", body: "#e54a00" },
  moisturize: { from: "#e0f6ef", to: "#c8ecdf", body: "#12a06a" },
  protect: { from: "#fff5d9", to: "#ffe9ae", body: "#e0a100" },
};

/** Packaging illustration used until a product has a photo. */
function Placeholder({ s }: { s: Suggestion }) {
  const st = STEP_STYLE[s.step];
  const lead = (s.ingredients[0] ?? "").replace(/^Sodium /i, "").toUpperCase();
  return (
    <svg viewBox="0 0 240 240" className="h-full w-full" role="img" aria-label={`${s.name} packaging illustration`}>
      <defs>
        <linearGradient id={`g-${s.id}`} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor={st.from} />
          <stop offset="1" stopColor={st.to} />
        </linearGradient>
      </defs>
      <rect width="240" height="240" fill={`url(#g-${s.id})`} />
      <ellipse cx="120" cy="212" rx="44" ry="6" fill="rgba(0,0,0,.12)" />
      {s.shape === "jar" && (
        <>
          <rect x="68" y="130" width="104" height="80" rx="12" fill="#fff" />
          <rect x="64" y="108" width="112" height="26" rx="8" fill={st.body} />
        </>
      )}
      {s.shape === "dropper" && (
        <>
          <rect x="88" y="104" width="64" height="106" rx="12" fill="#fff" />
          <rect x="108" y="88" width="24" height="18" fill={st.body} />
          <rect x="111" y="52" width="18" height="40" rx="9" fill={st.body} opacity=".85" />
        </>
      )}
      {s.shape === "tube" && (
        <>
          <path d="M88 84 H152 L146 210 H94 Z" fill="#fff" />
          <rect x="88" y="78" width="64" height="10" fill={st.body} />
        </>
      )}
      <rect x="98" y={s.shape === "jar" ? 148 : 130} width="44" height="3" rx="1.5" fill={st.body} />
      <text x="120" y={s.shape === "jar" ? 168 : 150} textAnchor="middle" fontSize="8" fontWeight="800" fill="#1b2233">
        {lead.slice(0, 16)}
      </text>
    </svg>
  );
}

function ProductCard({ s, index, onOwned }: { s: Suggestion; index: number; onOwned: (id: string, owned: boolean) => void }) {
  const [open, setOpen] = useState(false);
  const src = productImageUrl(s.image);
  return (
    <article className="lift flex h-full flex-col rounded-2xl border border-line bg-card p-3 shadow-card hover:border-fox-300">
      <div className="zoom-img aspect-square overflow-hidden rounded-xl">
        {src ? <img src={src} alt={s.name} loading="lazy" className="h-full w-full object-cover" /> : <Placeholder s={s} />}
      </div>

      <div className="mt-3 flex items-center justify-between">
        <span className="text-[11px] font-extrabold uppercase tracking-widest text-fox-500">{index} · {s.stepLabel}</span>
        <span className="pill bg-soft text-muted">{s.when}</span>
      </div>
      <h3 className="mt-1.5 min-h-[2.6rem] text-[13.5px] font-extrabold leading-snug text-ink">{s.name}</h3>

      <div className="mt-1 flex items-baseline gap-2">
        {s.price ? (
          <>
            <span className="text-lg font-extrabold text-ink">{rupees(s.price)}</span>
            <span className="text-[11px] text-muted">{s.priceSource === "retailer_mrp" ? "MRP" : "on foxtale.in"} · {s.size}</span>
          </>
        ) : (
          <span className="text-[11px] text-muted">{s.size} · check price on foxtale.in</span>
        )}
      </div>
      <p className="mt-1 text-[11px] text-muted">{s.ingredients.slice(0, 3).join("  ·  ")}</p>

      <p className="label-caps mt-3">{s.owned ? "Keep using" : "Why this for you"}</p>
      <p className="mt-1 text-[12.5px] leading-relaxed text-ink">{s.reason}</p>

      <button className="chip mt-3 w-full justify-center !py-1.5 text-[12.5px]" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <ChevronDown size={14} className={`transition-transform duration-300 ${open ? "rotate-180" : ""}`} /> {open ? "Hide details" : "How it works"}
      </button>
      <div className={`drawer ${open ? "open" : ""}`} aria-hidden={!open}>
        <div>
          <div className="mt-3 space-y-2.5 text-[12.5px] leading-relaxed">
            <div><p className="label-caps">How it works</p><p className="text-ink">{s.howItWorks}</p></div>
            <div><p className="label-caps">How to use</p><p className="text-ink">{s.howToUse}</p></div>
            {s.caution && <div><p className="label-caps">Good to know</p><p className="text-ink">{s.caution}</p></div>}
          </div>
        </div>
      </div>

      <div className="mt-auto flex items-center justify-between pt-3">
        <button
          className={`chip !px-3 !py-1.5 text-[12.5px] ${s.owned ? "chip-on" : ""}`}
          onClick={() => onOwned(s.id, !s.owned)} aria-pressed={s.owned}
        >
          <span key={String(s.owned)} className={s.owned ? "pop flex" : "flex"}><Check size={13} /></span> {s.owned ? "In my routine" : "I use this"}
        </button>
        <a
          href={s.url} target="_blank" rel="noreferrer" title="View on foxtale.in"
          className="rounded-full p-2 text-fox-500 hover:bg-fox-50 dark:hover:bg-fox-500/10" aria-label={`View ${s.name} on foxtale.in`}
        >
          <ExternalLink size={16} />
        </a>
      </div>
    </article>
  );
}

export default function Skincare({ skincare, onOwned }: { skincare: Report["skincare"]; onOwned: (id: string, owned: boolean) => void }) {
  const [when, setWhen] = useState<"all" | "AM" | "PM">("all");
  const shown = useMemo(() => skincare.suggestions.filter((s) => when === "all" || s.when.includes(when)), [skincare, when]);
  const { cost } = skincare;
  const tabs = [
    { key: "all", label: "Full routine", icon: ListChecks },
    { key: "AM", label: "Morning", icon: Sun },
    { key: "PM", label: "Evening", icon: Moon },
  ] as const;

  return (
    <div>
      <div className="flex flex-wrap items-center gap-2 text-sm">
        <span className="font-bold text-ink">Your skin looks</span>
        <span className="pill bg-fox-50 text-fox-text dark:bg-fox-500/15 dark:text-fox-300">{skincare.skinType.charAt(0).toUpperCase() + skincare.skinType.slice(1)}</span>
        {skincare.concerns.length > 0 && <span className="ml-2 font-bold text-ink">Focus on</span>}
        {skincare.concerns.slice(0, 3).map((c) => (
          <span key={c.key} className="pill bg-soft text-ink">{c.label.charAt(0).toUpperCase() + c.label.slice(1)}</span>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap gap-2" role="tablist" aria-label="Routine time">
          {tabs.map(({ key, label, icon: Icon }) => (
            <button key={key} role="tab" aria-selected={when === key} className={`chip !py-1.5 text-[13px] ${when === key ? "chip-on" : ""}`} onClick={() => setWhen(key)}>
              <Icon size={14} /> {label}
            </button>
          ))}
        </div>
        {cost.total > 0 ? (
          <p className="text-sm font-bold text-ink">
            Products to buy: about {rupees(cost.total)}{cost.unpriced ? `  +  ${cost.unpriced} not priced` : ""}
          </p>
        ) : shown.length > 0 ? (
          <p className="text-sm font-bold text-muted">Check prices on foxtale.in</p>
        ) : null}
      </div>

      <div key={when} className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {shown.map((s, i) => <Reveal key={s.id} index={i} className="h-full"><ProductCard s={s} index={i + 1} onOwned={onOwned} /></Reveal>)}
      </div>
      {shown.length === 0 && <p className="mt-4 text-sm text-muted">No products for this part of the day.</p>}

      <p className="mt-5 whitespace-pre-line text-[11px] leading-relaxed text-muted">
        {skincare.priceNote}
        {"\n"}Cosmetic suggestions based on what is visible in your photo, not medical advice. Patch-test new products and
        check the label. Product details are from foxtale.in as of {skincare.catalogDate} and can change. If your skin is
        painful, spreading or not improving, see a dermatologist.
      </p>
    </div>
  );
}
