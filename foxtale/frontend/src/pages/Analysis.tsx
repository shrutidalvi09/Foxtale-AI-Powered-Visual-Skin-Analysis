import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  ArrowRight, BarChart3, Bot, Camera, CheckCircle2, ChevronLeft, ChevronRight, CircleDashed, CircleDot, ClipboardCheck,
  Contrast, Download, Droplet, Droplets, Eye, Flame, Grid3x3, HeartPulse, Info, Lightbulb, Lock, NotebookPen, Plus, ScanFace,
  ScanSearch, Scissors, Shield, ShieldAlert, ShoppingBag, Smile, Sparkles, Star, Sun, SunDim, Trash2, Volume2, Waves, Zap, Heart,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useApp } from "../context/AppContext";
import { useVoice } from "../context/VoiceContext";
import {
  cartUrl, deleteScan, downloadPdf, getOptions, getReport, listScans, patchScan, productImageUrl, scanImageUrl,
} from "../services/api";
import type { Finding, RegionObservation, Report, Scan, SeverityLevel, Suggestion } from "../types/analysis";
import { CATEGORY_COLORS, LEVEL_DOT, rupees, scoreColor } from "../lib/format";
import { EmptyState, LevelPill, Modal, ScoreRing } from "../components/ui";
import { Reveal, Skeleton, usePulseKey, useInView } from "../lib/motion";
import { PHOTO_GROUPS, RegionDonut } from "../components/PhotoPanel";
import { DeliveryStatus } from "../components/WhatsApp";
import AiInsights from "../components/AiInsights";
import ConflictList from "../components/ConflictList";

// ------------------------------------------------------------------ helpers

const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);

/** Finding key -> photo filter group (cards with a group open the photo filtered to it). */
const FINDING_GROUP: Record<string, string> = {
  acne: "acne", dark_spots: "dark", under_eye: "eye", fine_lines: "lines", sun_spots: "dark", scars: "dark",
  redness: "redness", texture: "texture", dryness: "dryness", oiliness: "oiliness", uniformity: "tone",
};

/** Line icon + accent colour for each finding, in place of the emoji the API sends. */
const FINDING_ICON: Record<string, { icon: LucideIcon; color: string }> = {
  acne: { icon: CircleDot, color: "#f43f5e" },
  dark_spots: { icon: Contrast, color: "#b45309" },
  uniformity: { icon: SunDim, color: "#f59e0b" },
  texture: { icon: Grid3x3, color: "#8b5cf6" },
  under_eye: { icon: Eye, color: "#7c3aed" },
  redness: { icon: Flame, color: "#f97316" },
  pores: { icon: CircleDashed, color: "#3b82f6" },
  dryness: { icon: Droplet, color: "#0ea5e9" },
  oiliness: { icon: Droplets, color: "#12a06a" },
  scars: { icon: Scissors, color: "#be123c" },
  fine_lines: { icon: Waves, color: "#0d9488" },
  sun_spots: { icon: Sun, color: "#eab308" },
  facial_hair: { icon: Smile, color: "#64748b" },
  symmetry: { icon: ScanFace, color: "#12a06a" },
};

const qualityLabel = (s: number) => (s >= 85 ? "Excellent" : s >= 70 ? "Good" : s >= 55 ? "Fair" : "Needs care");

function Bar({ value, color }: { value: number; color: string }) {
  const [ref, seen] = useInView<HTMLDivElement>(0.2);
  return (
    <div ref={ref} className="h-1.5 w-full overflow-hidden rounded-full bg-line">
      <div className="h-full rounded-full" style={{ width: seen ? `${Math.max(3, Math.min(100, value))}%` : "0%", background: color, transition: "width .9s cubic-bezier(0.22, 1, 0.36, 1) .1s" }} />
    </div>
  );
}

function IconDot({ icon: Icon, color, size = 40 }: { icon: LucideIcon; color: string; size?: number }) {
  return (
    <span className="flex shrink-0 items-center justify-center rounded-full" style={{ width: size, height: size, background: `${color}1a`, color }}>
      <Icon size={size * 0.48} strokeWidth={1.75} />
    </span>
  );
}

function CardTitle({ icon: Icon, title, right }: { icon: LucideIcon; title: string; right?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-3">
      <h2 className="flex items-center gap-2.5 text-[16px] font-bold text-ink"><Icon size={18} className="text-fox-500" /> {title}</h2>
      {right}
    </div>
  );
}

// ------------------------------------------------------------------ sections

type NavTarget = { key: string; label: string; icon: LucideIcon; ref: React.MutableRefObject<HTMLElement | null> };

/** Sticky jump bar; the chip for the section you are reading is filled orange. */
function SectionNav({ targets }: { targets: NavTarget[] }) {
  const [active, setActive] = useState(targets[0]?.key);
  useEffect(() => {
    const onScroll = () => {
      let current = targets[0]?.key;
      for (const t of targets) {
        const el = t.ref.current;
        if (el && el.getBoundingClientRect().top < window.innerHeight * 0.35) current = t.key;
      }
      setActive(current);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [targets]);

  return (
    <div className="no-scrollbar sticky top-0 z-30 -mx-1 mb-4 overflow-x-auto bg-app/90 px-1 py-2 backdrop-blur">
      <div className="flex min-w-max gap-1">
        {targets.map(({ key, label, icon: Icon, ref }) => (
          <button
            key={key} aria-current={active === key}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold transition-all duration-300 ${
              active === key ? "bg-fox-600 text-white shadow-glow" : "text-ink/75 hover:bg-card hover:text-ink"
            }`}
            onClick={() => ref.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
          >
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function SlimDisclaimer() {
  return (
    <p className="flex items-start gap-2.5 rounded-xl border border-fox-500/20 bg-fox-50 px-4 py-3 text-[12.5px] leading-relaxed text-ink dark:bg-fox-500/10">
      <ShieldAlert size={16} className="mt-0.5 shrink-0 text-fox-500" />
      <span><b>AI Disclaimer:</b> This analysis is based only on visible features in the captured image and is not a medical
        diagnosis. For persistent, painful, spreading, or concerning skin changes, consult a qualified dermatologist.</span>
    </p>
  );
}

type Metric = { key: string; title: string; icon: LucideIcon; color: string; score: number; level: SeverityLevel; text: string; link: string; group: string };

function MetricCard({ m, index, onOpen }: { m: Metric; index: number; onOpen: (group: string) => void }) {
  return (
    <Reveal index={index} className="h-full">
      <div className="card lift flex h-full flex-col p-5">
        <div className="flex items-start gap-3">
          <IconDot icon={m.icon} color={m.color} size={42} />
          <div className="min-w-0">
            <p className="text-[11.5px] font-bold uppercase tracking-[0.08em] text-ink">{m.title}</p>
            <div className="mt-1.5 flex flex-wrap items-baseline gap-x-2 gap-y-1">
              <span className="text-[30px] font-bold leading-none" style={{ color: LEVEL_DOT[m.level] }}>{m.score}</span>
              <span className="text-[12px] text-muted">/100</span>
              <LevelPill level={m.level} className="!py-0.5" />
            </div>
          </div>
        </div>
        <p className="mt-3 flex-1 text-[12.5px] leading-relaxed text-muted">{m.text}</p>
        <button className="mt-3 self-start text-[12.5px] font-bold text-accent-600 hover:underline dark:text-accent-400" onClick={() => onOpen(m.group)}>{m.link}</button>
      </div>
    </Reveal>
  );
}

function QualityCard({ items, index, onOpen }: { items: [string, number][]; index: number; onOpen: () => void }) {
  const score = Math.round(items.reduce((s, [, v]) => s + v, 0) / Math.max(1, items.length));
  return (
    <Reveal index={index} className="h-full">
      <div className="card lift flex h-full flex-col p-5">
        <div className="flex items-start gap-3">
          <IconDot icon={Sparkles} color="#12a06a" size={42} />
          <div>
            <p className="text-[11.5px] font-bold uppercase tracking-[0.08em] text-ink">Skin quality</p>
            <div className="mt-1.5 flex items-baseline gap-2">
              <span className="text-[30px] font-bold leading-none" style={{ color: scoreColor(score) }}>{score}</span>
              <span className="text-[12px] text-muted">/100</span>
              <span className="pill lvl-minimal !py-0.5">{qualityLabel(score)}</span>
            </div>
          </div>
        </div>
        <dl className="mt-3 flex-1 space-y-0.5 text-[12px]">
          {items.map(([k, v]) => (
            <div key={k} className="flex justify-between"><dt className="text-muted">{k}</dt><dd className="font-bold" style={{ color: scoreColor(v) }}>{v}%</dd></div>
          ))}
        </dl>
        <button className="mt-2 self-start text-[12.5px] font-bold text-accent-600 hover:underline dark:text-accent-400" onClick={onOpen}>About your skin quality</button>
      </div>
    </Reveal>
  );
}

function ProfileStrip({ report, findings }: { report: Report; findings: Finding[] }) {
  const p = report.profile;
  const red = report.categories.find((c) => c.key === "Redness");
  const oil = report.categories.find((c) => c.key === "Oiliness");
  const pores = findings.find((f) => f.key === "pores");
  const sensitivity = { minimal: "Low", mild: "Mild", moderate: "Moderate", noticeable: "High" } as const;
  const sebum = { minimal: "Low", mild: "Normal", moderate: "Oily", noticeable: "Very oily" } as const;
  const items: { icon: LucideIcon; color: string; label: string; value: string; note: string; swatch?: string }[] = [
    { icon: Droplet, color: "#64748b", label: "Skin type", value: cap(p.skinType), note: "Estimated from shine and dryness" },
    { icon: Zap, color: "#3b82f6", label: "Sensitivity", value: red ? sensitivity[red.level] : "—", note: "Based on visible redness" },
    { icon: CircleDashed, color: "#8b5cf6", label: "Visible pores", value: pores?.level ? (pores.where ? cap(pores.where.replace(/^(on|around) the /, "")) : cap(pores.level)) : "—", note: pores?.headline.replace(/^Pore visibility: /, "Visibility: ") ?? "Not measured" },
    { icon: Sun, color: "#f59e0b", label: "Skin tone", value: p.tone?.label ?? "—", note: p.tone ? `${cap(p.tone.undertone)} undertone` : "Not measured", swatch: p.tone?.swatch },
    { icon: Droplets, color: "#3b82f6", label: "Sebum level", value: oil ? sebum[oil.level] : "—", note: report.areas["Oiliness"] && !report.areas["Oiliness"].startsWith("Not") ? `Most shine: ${report.areas["Oiliness"]}` : "No strong shine spotted" },
  ];
  return (
    <Reveal className="card mt-4 grid gap-5 p-5 lg:grid-cols-[minmax(0,1.25fr)_repeat(5,minmax(0,1fr))] lg:items-center">
      <div className="lg:border-r lg:border-line lg:pr-4">
        <p className="label-caps">Skin profile</p>
        <p className="mt-1 text-[20px] font-bold text-ink">{cap(p.skinType)}</p>
        <p className="mt-1 text-[12px] leading-relaxed text-muted">{p.skinTypeReason}</p>
      </div>
      {items.map(({ icon, color, label, value, note, swatch }) => (
        <div key={label} className="flex items-start gap-3">
          {swatch ? <span className="h-9 w-9 shrink-0 rounded-full border-2 border-card shadow-card ring-1 ring-line" style={{ background: swatch }} aria-label={`Measured skin colour ${swatch}`} /> : <IconDot icon={icon} color={color} size={36} />}
          <div className="min-w-0">
            <p className="label-caps">{label}</p>
            <p className="mt-0.5 text-[13.5px] font-bold text-ink">{value}</p>
            <p className="text-[11.5px] leading-snug text-muted">{note}</p>
          </div>
        </div>
      ))}
    </Reveal>
  );
}

function FindingTile({ f, index, onOpen }: { f: Finding; index: number; onOpen: (key: string) => void }) {
  const clickable = !!FINDING_GROUP[f.key] && f.measured;
  const meta = FINDING_ICON[f.key] ?? { icon: Info, color: "#64748b" };
  const pct = f.key === "uniformity" || f.key === "symmetry" ? Number(f.headline.match(/(\d+)%/)?.[1] ?? NaN) : NaN;
  const hasPct = !Number.isNaN(pct);
  const score = f.score ?? null;
  const barColor = hasPct ? scoreColor(pct) : f.level ? LEVEL_DOT[f.level] : "var(--muted)";
  return (
    <Reveal index={index} className="h-full">
      <button
        type="button" disabled={!clickable} onClick={() => onOpen(f.key)}
        className={`lift flex h-full w-full flex-col rounded-2xl border border-line bg-card p-3.5 text-left ${clickable ? "cursor-pointer hover:border-fox-300" : "cursor-default"} ${f.measured ? "" : "opacity-60"}`}
        aria-label={clickable ? `${f.headline}. Show on photo` : f.headline}
      >
        <span className="flex w-full items-start gap-3">
          <IconDot icon={meta.icon} color={meta.color} size={34} />
          <span className="min-w-0 flex-1">
            <span className="block text-[13px] font-bold leading-snug text-ink">{f.headline}</span>
            <span className="mt-1 line-clamp-3 text-[11.5px] leading-relaxed text-muted">{f.note}</span>
          </span>
        </span>
        {(hasPct || score != null || f.level) && (
          <span className="mt-auto flex w-full items-center gap-2.5 pt-3">
            {f.level && <LevelPill level={f.level} className="!px-2 !py-0.5 text-[10px]" />}
            {(hasPct || score != null) && <>
              <Bar value={hasPct ? pct : score ?? 0} color={barColor} />
              <span className="shrink-0 text-[12px] font-bold text-ink">{hasPct ? `${pct}%` : <>{score}<span className="font-normal text-muted"> /100</span></>}</span>
            </>}
          </span>
        )}
      </button>
    </Reveal>
  );
}

const STEP_TABS: { key: string; label: string; steps: Suggestion["step"][] }[] = [
  { key: "all", label: "For your skin type", steps: [] },
  { key: "cleanse", label: "Cleanser", steps: ["cleanse"] },
  { key: "treat", label: "Serum & treatment", steps: ["treat"] },
  { key: "eye", label: "Eye care", steps: ["eye"] },
  { key: "moisturize", label: "Moisturiser", steps: ["moisturize"] },
  { key: "protect", label: "Sunscreen", steps: ["protect"] },
];
const STEP_BG: Record<string, string> = {
  cleanse: "linear-gradient(160deg,#e9f4ff,#d6eafd)", treat: "linear-gradient(160deg,#fff0e6,#ffdcc8)",
  eye: "linear-gradient(160deg,#f3ecff,#e2d6fc)", moisturize: "linear-gradient(160deg,#e7f8f1,#cfeee2)",
  protect: "linear-gradient(160deg,#fff8e1,#ffecb5)",
};

function MiniProduct({ s, wished, onOwned, onWish }: { s: Suggestion; wished: boolean; onOwned: (id: string, owned: boolean) => void; onWish: (id: string) => void }) {
  const src = productImageUrl(s.image);
  return (
    <article className="lift flex w-[200px] shrink-0 flex-col overflow-hidden rounded-2xl border border-line bg-card sm:w-auto">
      <div className="zoom-img relative flex h-[132px] items-center justify-center overflow-hidden" style={{ background: STEP_BG[s.step] }}>
        {src ? <img src={src} alt={s.name} loading="lazy" className="h-full w-full object-cover mix-blend-multiply" /> : <ShoppingBag size={34} className="text-ink/30" />}
        <span className="absolute left-2 top-2 rounded-full bg-white/85 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide text-ink">{s.stepLabel}</span>
      </div>
      <div className="flex flex-1 flex-col p-3">
        <a href={s.url} target="_blank" rel="noreferrer" className="line-clamp-2 min-h-[2.4rem] text-[12.5px] font-bold leading-snug text-ink hover:text-fox-text">{s.name}</a>
        <p className="mt-1 text-[14px] font-bold text-ink">{s.price ? rupees(s.price) : <span className="text-[11px] font-normal text-muted">Price on foxtale.in</span>}</p>
        <p className="mt-1 line-clamp-2 flex-1 text-[11px] leading-relaxed text-muted">{s.reason || s.ingredients.slice(0, 3).join(" · ")}</p>
        <div className="mt-3 flex items-center gap-1.5">
          <button
            onClick={() => onOwned(s.id, !s.owned)} aria-pressed={s.owned}
            className={`flex-1 rounded-full border px-2 py-1.5 text-[11.5px] font-bold transition ${s.owned ? "border-emerald-500 bg-emerald-50 text-emerald-700 dark:bg-emerald-500/15 dark:text-emerald-300" : "border-fox-500 text-fox-text hover:bg-fox-50 dark:text-fox-300 dark:hover:bg-fox-500/10"}`}
          >
            {s.owned ? "✓ In routine" : "Add to Routine"}
          </button>
          <button onClick={() => onWish(s.id)} aria-pressed={wished} aria-label={wished ? `Remove ${s.name} from wishlist` : `Add ${s.name} to wishlist`} className="rounded-full p-1.5 transition hover:bg-fox-50 active:scale-90 dark:hover:bg-fox-500/10">
            <Heart key={String(wished)} size={15} className={wished ? "star-burst fill-rose-500 text-rose-500" : "text-fox-500"} />
          </button>
        </div>
      </div>
    </article>
  );
}

function SkincareRow({ skincare, wishlist, onOwned, onWish }: { skincare: Report["skincare"]; wishlist: string[]; onOwned: (id: string, owned: boolean) => void; onWish: (id: string) => void }) {
  const [tab, setTab] = useState("all");
  const tabs = STEP_TABS.filter((t) => t.key === "all" || skincare.suggestions.some((s) => t.steps.includes(s.step)));
  const current = STEP_TABS.find((t) => t.key === tab) ?? STEP_TABS[0];
  const shown = skincare.suggestions.filter((s) => tab === "all" || current.steps.includes(s.step));
  const buyable = skincare.suggestions.filter((x) => !x.owned && x.variantId);
  return (
    <div>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="no-scrollbar flex gap-1.5 overflow-x-auto" role="tablist" aria-label="Product step">
          {tabs.map((t) => (
            <button key={t.key} role="tab" aria-selected={tab === t.key} onClick={() => setTab(t.key)}
              className={`shrink-0 rounded-lg border px-3 py-1.5 text-[12px] font-semibold transition ${tab === t.key ? "border-fox-500 bg-fox-50 text-fox-text dark:bg-fox-500/15 dark:text-fox-300" : "border-line text-ink/80 hover:border-fox-300"}`}>
              {t.label}
            </button>
          ))}
        </div>
        <p className="text-[12px] text-muted">Products for you ({skincare.suggestions.length}) · <Link to="/shop" className="font-bold text-fox-text hover:underline dark:text-fox-300">View all</Link></p>
      </div>

      {skincare.conflicts.length > 0 && <div className="mt-3"><ConflictList issues={skincare.conflicts} /></div>}

      <div key={tab} className="no-scrollbar -mx-1 mt-4 flex gap-3 overflow-x-auto px-1 pb-1 sm:grid sm:grid-cols-2 sm:overflow-visible xl:grid-cols-4">
        {shown.map((s) => <MiniProduct key={s.id} s={s} wished={wishlist.includes(s.id)} onOwned={onOwned} onWish={onWish} />)}
      </div>
      {shown.length === 0 && <p className="mt-4 text-sm text-muted">No products for this step.</p>}

      {buyable.length > 0 && (
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3 rounded-xl bg-soft px-4 py-3">
          <p className="text-[12.5px] text-ink"><b>{buyable.length} product{buyable.length === 1 ? "" : "s"}</b> to buy · opens foxtale.in with these in your cart</p>
          <a href={cartUrl(buyable.map((x) => x.variantId as string))} target="_blank" rel="noreferrer" className="btn-cta !px-4 !py-2 text-[13px]"><ShoppingBag size={15} /> Buy the routine</a>
        </div>
      )}
      <p className="mt-3 text-[10.5px] leading-relaxed text-muted">Cosmetic suggestions based on what is visible in your photo, not medical advice. Patch-test new products. Details from foxtale.in as of {skincare.catalogDate}.</p>
    </div>
  );
}

/** Four short focus cards picked from what the scan measured, topped up with everyday basics. */
const INSIGHTS: Record<string, { title: string; icon: LucideIcon; color: string; body: string }> = {
  dryness_indicators: { title: "Hydration", icon: Droplet, color: "#12a06a", body: "Improve hydration with hyaluronic acid based products." },
  acne_like_spots: { title: "Acne Control", icon: CircleDot, color: "#e8541e", body: "Use salicylic acid and niacinamide to reduce breakouts." },
  redness: { title: "Calm Redness", icon: Flame, color: "#f97316", body: "Soothing ingredients like centella and niacinamide calm visible redness." },
  oiliness: { title: "Oil Balance", icon: Droplets, color: "#0ea5e9", body: "Lightweight, non-comedogenic gels keep shine in check." },
  texture: { title: "Smoother Texture", icon: Grid3x3, color: "#8b5cf6", body: "Gentle exfoliation with AHA/BHA helps refine uneven texture." },
  tone_evenness: { title: "Even Tone", icon: SunDim, color: "#f59e0b", body: "Vitamin C and daily SPF help brighten and even out tone." },
  dark_spots: { title: "Fade Dark Spots", icon: Contrast, color: "#b45309", body: "Vitamin C, alpha arbutin and SPF help fade marks over time." },
  pores: { title: "Refine Pores", icon: CircleDashed, color: "#3b82f6", body: "Niacinamide and BHA keep pores clear and less visible." },
  sun: { title: "Sun Protection", icon: Sun, color: "#7c3aed", body: "Daily SPF is essential to prevent tanning and pigmentation." },
  barrier: { title: "Barrier Support", icon: Shield, color: "#2563eb", body: "Strengthen your skin barrier with ceramides and peptides." },
};

function KeyInsights({ concerns }: { concerns: { key: string }[] }) {
  const keys = [...concerns.map((c) => c.key).filter((k) => INSIGHTS[k]), "sun", "barrier", "dryness_indicators"];
  const picked = [...new Set(keys)].slice(0, 4);
  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {picked.map((k, i) => {
        const c = INSIGHTS[k];
        return (
          <Reveal key={k} index={i} className="h-full">
            <div className="lift flex h-full flex-col rounded-2xl border border-line p-4" style={{ background: `linear-gradient(170deg, ${c.color}12, transparent 70%)` }}>
              <p className="flex items-center gap-2 text-[13px] font-bold text-ink"><IconDot icon={c.icon} color={c.color} size={28} /> {c.title}</p>
              <p className="mt-2.5 flex-1 text-[12px] leading-relaxed text-muted">{c.body}</p>
              <Link to="/ingredients" className="mt-3 inline-flex items-center gap-1 text-[12px] font-bold text-fox-text hover:underline dark:text-fox-300">Learn more <ArrowRight size={13} /></Link>
            </div>
          </Reveal>
        );
      })}
    </div>
  );
}

function FacialAnalysis({ image, regions, report, selected, onSelect, group, onGroupChange }: {
  image: string | null; regions: RegionObservation[]; report: Report | null; selected: RegionObservation | null;
  onSelect: (r: RegionObservation) => void; group: string; onGroupChange: (g: string) => void;
}) {
  const [heatmap, setHeatmap] = useState(false);
  const [showRegions, setShowRegions] = useState(false);
  const visible = useMemo(() => (group === "all" ? regions : regions.filter((r) => PHOTO_GROUPS[group]?.categories.includes(r.category))), [regions, group]);
  const legend = Object.keys(CATEGORY_COLORS).filter((c) => regions.some((r) => r.category === c));
  const observations = useMemo(() => {
    const seen = new Map<string, RegionObservation>();
    for (const r of visible) {
      const k = `${r.observation}|${r.region}`;
      if (!seen.has(k)) seen.set(k, r);
    }
    return [...seen.values()].sort((a, b) => b.confidence - a.confidence).slice(0, 6);
  }, [visible]);
  const avgConf = regions.length ? Math.round((100 * regions.reduce((s, r) => s + r.confidence, 0)) / regions.length) : null;

  return (
    <div className="grid gap-5 md:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
      <div>
        <div className="mb-3 flex flex-wrap items-center gap-2">
          <select className="input !w-auto !rounded-full !py-1.5 text-[12.5px]" value={group} onChange={(e) => onGroupChange(e.target.value)} aria-label="Concern filter">
            <option value="all">All concerns</option>
            {Object.entries(PHOTO_GROUPS).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}
          </select>
          <button className={`chip !px-3 !py-1.5 text-[12.5px] ${heatmap ? "chip-on" : ""}`} onClick={() => setHeatmap((h) => !h)} aria-pressed={heatmap}><Flame size={14} className="text-fox-500" /> Heatmap</button>
        </div>
        <div className="flex gap-3">
          {image && legend.length > 0 && (
            <ul className="hidden w-[104px] shrink-0 space-y-1.5 pt-2 text-[11.5px] text-ink sm:block">
              {legend.map((c) => <li key={c} className="flex items-center gap-2"><span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: CATEGORY_COLORS[c] }} /> {c.replace(" indicators", "").replace("-like spots", "")}</li>)}
            </ul>
          )}
          <div className="flex min-h-[280px] flex-1 items-center justify-center overflow-hidden rounded-2xl bg-soft">
            {image ? (
              <div className="relative inline-block max-w-full">
                <img src={image} alt="Your scan with markers" className="block max-h-[420px] max-w-full rounded-xl" />
                {visible.map((r, i) => heatmap ? (
                  <span key={`h${i}`} aria-hidden className="pop pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
                    style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: "22%", aspectRatio: "1", animationDelay: `${i * 40}ms`, background: `radial-gradient(circle, ${CATEGORY_COLORS[r.category] ?? "#3b8dff"}99 0%, transparent 70%)` }} />
                ) : (
                  <button key={i} onClick={() => onSelect(r)} aria-label={`${r.category} in ${r.region}`}
                    className={`pop absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white transition-all duration-200 hover:scale-125 ${selected === r ? "h-5 w-5 ring-4 ring-white/60" : "h-3.5 w-3.5"}`}
                    style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, background: CATEGORY_COLORS[r.category] ?? "#3b8dff", animationDelay: `${300 + i * 50}ms` }} />
                ))}
              </div>
            ) : (
              <div className="flex max-w-xs flex-col items-center gap-2 px-6 py-10 text-center">
                <Camera size={26} className="text-muted" />
                <p className="text-sm font-bold text-ink">No photo for this scan</p>
                <p className="text-xs text-muted">Photos are kept only when "Save scan photos" is on in Privacy.</p>
              </div>
            )}
          </div>
        </div>
        {avgConf != null && <p className="mt-2 text-[11.5px] font-bold text-fox-text dark:text-fox-300">Average marker confidence: {avgConf}%</p>}
        {selected && <p className="mt-1 text-[12px] text-ink"><b>{cap(selected.region.toLowerCase())}</b> · {selected.observation} ({Math.round(selected.confidence * 100)}% confidence)</p>}
      </div>

      <div className="space-y-5">
        <div>
          <p className="mb-3 text-[13px] font-bold text-ink">Region breakdown</p>
          <RegionDonut regions={visible} />
          {report && report.regionScores.length > 0 && (
            <>
              <button className="mt-3 rounded-lg border border-fox-500 px-3 py-1.5 text-[12px] font-bold text-fox-text hover:bg-fox-50 dark:text-fox-300 dark:hover:bg-fox-500/10" onClick={() => setShowRegions((s) => !s)} aria-expanded={showRegions}>
                {showRegions ? "Hide region details" : "View region details"}
              </button>
              <div className={`drawer ${showRegions ? "open" : ""}`}>
                <div>
                  <ul className="mt-3 space-y-2">
                    {report.regionScores.map((r) => (
                      <li key={r.name}>
                        <div className="flex justify-between text-[12px]"><span className="font-bold text-ink">{r.name} <span className="font-normal text-muted">{r.concern}</span></span><span className="font-bold">{r.score}</span></div>
                        <Bar value={r.score} color={scoreColor(r.score)} />
                      </li>
                    ))}
                  </ul>
                </div>
              </div>
            </>
          )}
        </div>
        <div>
          <p className="mb-2 text-[13px] font-bold text-ink">Visible observations</p>
          {observations.length === 0 ? <p className="text-[12px] text-muted">Nothing flagged for this filter.</p> : (
            <ul className="space-y-1.5">
              {observations.map((r) => (
                <li key={`${r.observation}|${r.region}`}>
                  <button onClick={() => onSelect(r)} className={`flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-[12px] transition hover:border-fox-300 ${selected === r ? "border-fox-500 bg-fox-50 dark:bg-fox-500/10" : "border-line"}`}>
                    <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: CATEGORY_COLORS[r.category] ?? "#3b8dff" }} />
                    <span className="text-ink">{r.observation} <span className="text-muted">· {cap(r.region.toLowerCase())}</span></span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading your analysis">
      <Skeleton className="h-10 w-72" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">{[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-40" />)}</div>
      <Skeleton className="h-24" />
      <div className="grid gap-4 lg:grid-cols-2"><Skeleton className="h-96" /><Skeleton className="h-96" /></div>
    </div>
  );
}

// ------------------------------------------------------------------ page

export default function Analysis() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { current, setCurrent, settings, updateSettings, toast, bumpData, dataVersion } = useApp();

  const [scan, setScan] = useState<Scan | null>(null);
  const [saved, setSaved] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<Report | null>(null);
  const [selected, setSelected] = useState<RegionObservation | null>(null);
  const [photoGroup, setPhotoGroup] = useState<string>("all");
  const [note, setNote] = useState("");
  const [options, setOptions] = useState<{ routine: string[]; environment: string[] }>({ routine: [], environment: [] });
  const [pdfBusy, setPdfBusy] = useState(false);
  const [methodOpen, setMethodOpen] = useState(false);
  const starKey = usePulseKey(scan?.starred);

  const findingsRef = useRef<HTMLElement | null>(null);
  const reportRef = useRef<HTMLElement | null>(null);
  const skincareRef = useRef<HTMLElement | null>(null);
  const photoRef = useRef<HTMLElement | null>(null);
  const notesRef = useRef<HTMLElement | null>(null);
  const tipsRef = useRef<HTMLElement | null>(null);
  const aiRef = useRef<HTMLElement | null>(null);
  const voice = useVoice();

  const readAloud = useCallback(() => {
    if (!report) return;
    const score = report.overallScore != null ? `Your visible-skin score is ${report.overallScore} out of a hundred, ${report.scoreLabel ?? ""}. ` : "";
    void voice.speakDirect(`${score}${report.summary}`);
  }, [report, voice]);

  // which scan is on screen: /analysis/:id, else the one just analysed, else the newest saved one
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    listScans()
      .then((all) => {
        if (cancelled) return;
        setSaved(all);
        const fromRoute = id ? all.find((s) => s.id === id) : undefined;
        const chosen = fromRoute ?? (!id ? (current?.scan ?? all[0]) : undefined) ?? null;
        setScan(chosen ?? null);
        setNote(chosen?.note ?? "");
        setSelected(null);
      })
      .catch(() => {
        if (!cancelled) {
          setScan(current?.scan ?? null);
          setNote(current?.scan.note ?? "");
        }
      })
      .finally(() => !cancelled && setLoading(false));
    getOptions().then(setOptions).catch(() => undefined);
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id, dataVersion]);

  const index = scan ? saved.findIndex((s) => s.id === scan.id) : -1;
  const previous: Scan | null = useMemo(() => {
    if (!scan) return null;
    if (index >= 0) return saved[index + 1] ?? null;
    return saved[0] ?? null;
  }, [scan, saved, index]);

  const owned = settings.owned_products;
  useEffect(() => {
    if (!scan) {
      setReport(null);
      return;
    }
    let cancelled = false;
    getReport({ analysis: scan.analysis, regions: scan.regions, previousAnalysis: previous?.analysis ?? null, owned })
      .then((r) => !cancelled && setReport(r))
      .catch(() => !cancelled && setReport(null));
    return () => {
      cancelled = true;
    };
  }, [scan, previous, owned]);

  const image =
    scan && current && current.scan.id === scan.id && current.imageDataUrl
      ? current.imageDataUrl
      : scan?.hasImage
      ? scanImageUrl(scan.id)
      : null;

  const setOwned = useCallback(
    (productId: string, isOwned: boolean) => {
      const next = owned.filter((p) => p !== productId);
      if (isOwned) next.push(productId);
      updateSettings({ owned_products: next });
      toast(isOwned ? "Added to your routine" : "Removed from your routine");
    },
    [owned, updateSettings, toast]
  );

  const toggleWish = useCallback((productId: string) => {
    const list = settings.wishlist ?? [];
    updateSettings({ wishlist: list.includes(productId) ? list.filter((p) => p !== productId) : [...list, productId] });
    toast(list.includes(productId) ? "Removed from wishlist" : "Saved to your wishlist");
  }, [settings.wishlist, updateSettings, toast]);

  const update = async (patch: Parameters<typeof patchScan>[1]) => {
    if (!scan || !scan.persisted) return;
    try {
      const next = await patchScan(scan.id, patch);
      setScan(next);
      setSaved((all) => all.map((s) => (s.id === next.id ? next : s)));
      if (current?.scan.id === next.id) setCurrent({ ...current, scan: next });
      bumpData();
    } catch {
      toast("Could not save that change");
    }
  };

  const toggleJournal = (kind: "routine" | "environment", item: string) => {
    if (!scan) return;
    const list = scan.journal[kind];
    const nextList = list.includes(item) ? list.filter((i) => i !== item) : [...list, item];
    update({ journal: { ...scan.journal, [kind]: nextList } });
  };

  const exportPdf = async () => {
    if (!scan) return;
    setPdfBusy(true);
    try {
      const blob = await downloadPdf(scan, previous?.analysis ?? null, image && image.startsWith("data:") ? image : null);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `foxtale-report-${scan.timestamp.slice(0, 10)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
      toast("PDF report downloaded");
    } catch {
      toast("Could not build the PDF report");
    } finally {
      setPdfBusy(false);
    }
  };

  const remove = async () => {
    if (!scan) return;
    if (!scan.persisted) {
      setCurrent(null);
      setScan(null);
      return;
    }
    try {
      await deleteScan(scan.id);
      if (current?.scan.id === scan.id) setCurrent(null);
      bumpData();
      toast("Moved to Recently Deleted");
      navigate("/history");
    } catch {
      toast("Could not delete this scan");
    }
  };

  const openPhoto = (group: string) => {
    setPhotoGroup(group);
    setSelected(null);
    setTimeout(() => photoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
  };

  if (loading && !scan) return <AnalysisSkeleton />;
  if (!scan) {
    return (
      <EmptyState
        icon={<BarChart3 size={28} />} title="No analysis yet"
        body="Run a face scan to see your skin analysis, score and a matching skincare routine here."
        action={<Link to="/scan" state={{ autostart: true }} className="btn-cta"><Camera size={18} /> Start New Scan</Link>}
      />
    );
  }

  const navTargets: NavTarget[] = [
    { key: "findings", label: "Findings", icon: ScanSearch, ref: findingsRef },
    { key: "report", label: "Report", icon: ClipboardCheck, ref: reportRef },
    { key: "skincare", label: "Skincare", icon: HeartPulse, ref: skincareRef },
    { key: "photo", label: "Photo & Regions", icon: Camera, ref: photoRef },
    { key: "notes", label: "Notes & Journal", icon: NotebookPen, ref: notesRef },
    { key: "tips", label: "Tips", icon: Lightbulb, ref: tipsRef },
    { key: "ai", label: "AI Insights", icon: Bot, ref: aiRef },
  ];

  const a = scan.analysis;
  const cat = (key: string) => report?.categories.find((c) => c.key === key);
  const catScore = (key: string) => cat(key)?.score ?? 0;
  const regionsOf = (category: string) => report?.areas[category] && !report.areas[category].startsWith("Not") ? report.areas[category].toLowerCase() : "";
  const levelText: Record<SeverityLevel, string> = { minimal: "Barely visible", mild: "Mild", moderate: "Moderate", noticeable: "Clearly visible" };

  const metrics: Metric[] = report ? [
    { key: "acne", title: "Acne-like spots", icon: CircleDot, color: "#f43f5e", score: catScore("Acne-like spots"), level: cat("Acne-like spots")?.level ?? "minimal",
      text: `${report.profile.spots.pimples} pimple-like, ${report.profile.spots.marks} flat mark${report.profile.spots.marks === 1 ? "" : "s"}${regionsOf("Acne-like spots") ? ` · ${regionsOf("Acne-like spots")}` : ""}`, link: "About your acne", group: "acne" },
    { key: "redness", title: "Redness", icon: Flame, color: "#f97316", score: catScore("Redness"), level: cat("Redness")?.level ?? "minimal",
      text: `${levelText[cat("Redness")?.level ?? "minimal"]} redness${regionsOf("Redness") ? ` around ${regionsOf("Redness")}` : ""}`, link: "About your redness", group: "redness" },
    { key: "texture", title: "Texture", icon: Grid3x3, color: "#8b5cf6", score: catScore("Texture"), level: cat("Texture")?.level ?? "minimal",
      text: cat("Texture")?.measurement ?? "", link: "About your texture", group: "texture" },
    { key: "dryness", title: "Dryness indicators", icon: Droplet, color: "#0ea5e9", score: catScore("Dryness indicators"), level: cat("Dryness indicators")?.level ?? "minimal",
      text: `${levelText[cat("Dryness indicators")?.level ?? "minimal"]} dryness${regionsOf("Dryness indicators") ? ` in ${regionsOf("Dryness indicators")}` : ""}`, link: "About your dryness", group: "dryness" },
  ] : [];
  const uniformity = Number(report?.findings.find((f) => f.key === "uniformity")?.headline.match(/(\d+)%/)?.[1] ?? NaN);
  const qualityItems: [string, number][] = report ? [
    ["Clarity", 100 - catScore("Acne-like spots")],
    ["Smoothness", 100 - catScore("Texture")],
    ["Even tone", Number.isNaN(uniformity) ? 100 - catScore("Tone evenness") : uniformity],
    ["Radiance", 100 - catScore("Dryness indicators")],
    ...(report.overallScore != null ? [["Overall health", report.overallScore] as [string, number]] : []),
  ] : [];
  const breakdown: [string, number, string][] = report ? [
    ...(report.overallScore != null ? [["Overall skin health", report.overallScore, scoreColor(report.overallScore)] as [string, number, string]] : []),
    ...report.categories.map((c) => [c.label.replace("Indicators", "").replace(" / Shine", "").trim(), c.score ?? 0, LEVEL_DOT[c.level]] as [string, number, string]),
  ] : [];
  const journalScans = (index >= 0 ? saved.slice(Math.max(0, index - 2), Math.max(0, index - 2) + 5) : saved.slice(0, 5));
  const startOfList = index >= 0 && index + 1 >= saved.length;
  const endOfList = index <= 0;
  const when = new Date(scan.timestamp);
  const stamp = `${when.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}, ${when.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;

  return (
    <div className="animate-fade-up">
      {/* header */}
      <div className="mb-4 flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-[26px] font-bold leading-tight text-ink sm:text-[30px]">Your Skin Analysis</h1>
          <p className="mt-1 text-[13.5px] text-muted">AI-powered visual skin assessment · {stamp}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <button className="btn-soft !rounded-xl !px-4" disabled={index < 0 || startOfList} onClick={() => navigate(`/analysis/${saved[index + 1].id}`)}><ChevronLeft size={16} /> Previous</button>
          <button className="btn-soft !rounded-xl !px-4" disabled={index < 0 || endOfList} onClick={() => navigate(`/analysis/${saved[index - 1].id}`)}>Next <ChevronRight size={16} /></button>
          <button className="btn-soft !rounded-xl !px-4" disabled={!scan.persisted} onClick={() => update({ starred: !scan.starred })} aria-pressed={scan.starred} title={scan.persisted ? "" : "Turn on Save scan history to star scans"}>
            <Star key={starKey} size={16} className={`${starKey ? "star-burst" : ""} ${scan.starred ? "fill-amber-400 text-amber-400" : ""}`} /> {scan.starred ? "Starred" : "Star"}
          </button>
          {voice.status?.enabled && <button className="btn-soft !rounded-xl !px-4" onClick={readAloud} disabled={!report}><Volume2 size={16} /> Read aloud</button>}
          <button className="btn-cta !rounded-xl !px-5 !py-2.5 text-sm" onClick={exportPdf} disabled={pdfBusy}><Download size={16} /> {pdfBusy ? "Building..." : "Download PDF"}</button>
        </div>
      </div>

      <DeliveryStatus key={scan.id} scanId={scan.id} />
      <SectionNav targets={navTargets} />
      <SlimDisclaimer />

      {!scan.persisted && (
        <p className="mt-3 flex items-start gap-2 rounded-xl bg-soft p-3 text-[12.5px] text-muted">
          <Info size={15} className="mt-0.5 shrink-0" /> This scan is not saved. Turn on "Save scan history" in Privacy to keep scans, add notes and compare over time.
        </p>
      )}

      {/* metric cards */}
      <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {report ? (
          <>
            {metrics.map((m, i) => <MetricCard key={m.key} m={m} index={i} onOpen={openPhoto} />)}
            <QualityCard items={qualityItems} index={4} onOpen={() => reportRef.current?.scrollIntoView({ behavior: "smooth", block: "start" })} />
          </>
        ) : [0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-44" />)}
      </div>

      {report && <ProfileStrip report={report} findings={report.findings} />}

      {/* findings | health report */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Reveal as="section" innerRef={findingsRef} className="card scroll-mt-16 p-5">
          <CardTitle icon={ScanSearch} title="Detailed Findings" right={
            <button className="flex items-center gap-1 text-[12.5px] font-bold text-fox-text hover:underline dark:text-fox-300" onClick={() => setMethodOpen(true)}>How we analyze <Info size={14} /></button>
          } />
          {report ? (
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {report.findings.map((f, i) => <FindingTile key={f.key} f={f} index={i} onOpen={(k) => openPhoto(FINDING_GROUP[k] ?? "all")} />)}
            </div>
          ) : <div className="grid gap-3 sm:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-28" />)}</div>}
          <p className="mt-3 text-[10.5px] leading-relaxed text-muted">Estimates from one photo using computer vision, not a clinical assessment. Tap a card to see it on your photo.</p>
        </Reveal>

        <Reveal as="section" innerRef={reportRef} className="card scroll-mt-16 p-5">
          <CardTitle icon={ClipboardCheck} title="Skin Health Report" />
          {report ? (
            <>
              <div className="flex flex-wrap items-center gap-6">
                <div className="flex flex-col items-center">
                  <ScoreRing score={report.overallScore} size={140} />
                  {report.scoreLabel && <p className="mt-2 text-[15px] font-bold" style={{ color: scoreColor(report.overallScore ?? 0) }}>{report.scoreLabel}</p>}
                </div>
                <div className="min-w-[220px] flex-1">
                  <p className="label-caps mb-2">Score breakdown</p>
                  <ul className="space-y-2">
                    {breakdown.map(([label, v, color], i) => (
                      <li key={label} className="grid grid-cols-[minmax(0,1.1fr)_minmax(0,1.3fr)_28px] items-center gap-3 text-[12px]">
                        <span className={`truncate text-ink ${i === 0 ? "font-bold" : "font-semibold"}`}>{label}</span>
                        <Bar value={v} color={color} />
                        <span className="text-right font-bold text-ink">{v}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-2 text-[10.5px] text-muted">Overall: higher is better. Concerns: higher means more visible.</p>
                </div>
              </div>
              <div className="mt-5 rounded-xl border-l-4 border-emerald-500 bg-emerald-50/70 px-4 py-3 text-[12.5px] leading-relaxed text-ink dark:bg-emerald-500/10">
                {report.summary}
                {report.changes.slice(0, 2).map((c) => <span key={c} className="mt-1 block text-[11.5px] text-muted">{c}</span>)}
              </div>
              {scan.quality && (
                <p className="mt-3 text-[11.5px] text-muted">
                  Scan quality <b style={{ color: scoreColor(scan.quality.overall) }}>{scan.quality.overall}/100</b> · lighting {scan.quality.lighting_score} · sharpness {scan.quality.sharpness_score} · angle {scan.quality.angle_score}
                </p>
              )}
            </>
          ) : <Skeleton className="h-72" />}
        </Reveal>
      </div>

      {/* skincare | insights */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Reveal as="section" innerRef={skincareRef} className="card scroll-mt-16 p-5">
          <CardTitle icon={Sparkles} title="Personalized Skincare Recommendations" />
          {report ? <SkincareRow skincare={report.skincare} wishlist={settings.wishlist ?? []} onOwned={setOwned} onWish={toggleWish} /> : <Skeleton className="h-64" />}
        </Reveal>
        <Reveal as="section" className="card p-5">
          <CardTitle icon={Sparkles} title="Key Insights" />
          {report ? <KeyInsights concerns={report.skincare.concerns} /> : <Skeleton className="h-48" />}
        </Reveal>
      </div>

      {/* facial analysis | notes + tips */}
      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <Reveal as="section" innerRef={photoRef} className="card scroll-mt-16 p-5">
          <CardTitle icon={ScanFace} title="Facial Analysis" />
          <FacialAnalysis image={image} regions={scan.regions} report={report} selected={selected} onSelect={setSelected} group={photoGroup} onGroupChange={setPhotoGroup} />
        </Reveal>

        <div className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-2">
          <Reveal as="section" innerRef={notesRef} className="card scroll-mt-16 p-5">
            <CardTitle icon={NotebookPen} title="Notes & Skin Journal" />
            <p className="label-caps mb-1.5">Add a note</p>
            <textarea
              className="input min-h-[78px] resize-none !rounded-xl text-[12.5px]" value={note} disabled={!scan.persisted} maxLength={2000}
              placeholder="Add notes about your skin, products or anything..." onChange={(e) => setNote(e.target.value)}
            />
            <button className="mt-2 rounded-lg border border-fox-500 px-3 py-1.5 text-[12px] font-bold text-fox-text transition hover:bg-fox-50 disabled:opacity-40 dark:text-fox-300 dark:hover:bg-fox-500/10" disabled={!scan.persisted || note === scan.note} onClick={() => update({ note })}>Save Note</button>
            {!scan.persisted && <p className="mt-1.5 text-[11px] text-muted">Notes and the journal are available for saved scans.</p>}

            {journalScans.length > 0 && (
              <>
                <p className="label-caps mb-2 mt-5">Scan journal</p>
                <div className="no-scrollbar flex gap-1.5 overflow-x-auto">
                  {journalScans.map((s) => {
                    const d = new Date(s.timestamp);
                    const on = s.id === scan.id;
                    return (
                      <button key={s.id} onClick={() => navigate(`/analysis/${s.id}`)} aria-current={on}
                        className={`flex w-[54px] shrink-0 flex-col items-center rounded-lg border py-1.5 transition ${on ? "border-fox-500 bg-fox-50 dark:bg-fox-500/15" : "border-line hover:border-fox-300"}`}>
                        <span className={`text-[9.5px] font-bold uppercase ${on ? "text-fox-text dark:text-fox-300" : "text-muted"}`}>{d.toLocaleDateString(undefined, { month: "short" })}</span>
                        <span className="text-[17px] font-bold leading-tight text-ink">{d.getDate()}</span>
                        <span className="text-[9px] text-muted">{d.getFullYear()}</span>
                        <span className="mt-0.5 text-[9.5px] font-bold" style={{ color: s.analysis.overall_score != null ? scoreColor(s.analysis.overall_score) : undefined }}>{s.analysis.overall_score ?? "--"}</span>
                      </button>
                    );
                  })}
                </div>
              </>
            )}

            <p className="label-caps mb-2 mt-5">Quick tags</p>
            <div className="flex flex-wrap gap-1.5">
              {[...options.routine.map((o) => ["routine", o] as const), ...options.environment.map((o) => ["environment", o] as const)].map(([kind, o]) => {
                const on = scan.journal[kind].includes(o);
                return (
                  <button key={`${kind}-${o}`} disabled={!scan.persisted} aria-pressed={on} onClick={() => toggleJournal(kind, o)}
                    className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-[11.5px] font-semibold transition disabled:opacity-50 ${on ? "border-fox-500 bg-fox-50 text-fox-text dark:bg-fox-500/15 dark:text-fox-300" : "border-line text-ink hover:border-fox-300"}`}>
                    {on ? "✓" : <Plus size={11} />} {o}
                  </button>
                );
              })}
            </div>
          </Reveal>

          <Reveal as="section" innerRef={tipsRef} className="card scroll-mt-16 p-5">
            <CardTitle icon={Lightbulb} title="Recommendations & Tips" />
            <ul className="space-y-3">
              {(report?.recommendations ?? []).slice(0, 6).map((t) => (
                <li key={t} className="flex gap-2.5 text-[12.5px] leading-relaxed text-ink"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-500" />{t}</li>
              ))}
            </ul>
            {report && (
              <button className="mt-4 inline-flex items-center gap-1 text-[12.5px] font-bold text-fox-text hover:underline dark:text-fox-300" onClick={() => setMethodOpen(true)}>How this was measured <ArrowRight size={13} /></button>
            )}
          </Reveal>
        </div>
      </div>

      <Reveal as="section" innerRef={aiRef} className="scroll-mt-16"><AiInsights scanId={scan.id} persisted={scan.persisted} hasImage={scan.hasImage} /></Reveal>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-muted"><Lock size={14} /> Your face image is processed only for this analysis.</p>
        <div className="flex gap-2">
          <button className="btn-danger" onClick={remove}><Trash2 size={16} /> Delete Scan</button>
          <Link to="/scan" state={{ autostart: true }} className="btn-cta !py-2.5 text-sm"><Camera size={16} /> New Scan</Link>
        </div>
      </div>

      <Modal open={methodOpen} onClose={() => setMethodOpen(false)} title="How this was measured">
        {report && (
          <div className="max-h-[60vh] space-y-2.5 overflow-y-auto text-[12.5px] leading-relaxed text-muted">
            {report.methodology.steps.map((s) => <p key={s.title}><b className="text-ink">{s.title}:</b> {s.body}</p>)}
            <p>{report.methodology.scoreExplanation}</p>
            <p>{report.methodology.limitations}</p>
            {a.engine_version == null && <p>This scan was made by an earlier engine version, so some scores are estimated from levels.</p>}
          </div>
        )}
      </Modal>
    </div>
  );
}
