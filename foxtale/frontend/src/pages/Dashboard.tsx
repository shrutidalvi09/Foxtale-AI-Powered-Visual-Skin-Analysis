import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight, Award, Bell, Calendar, Camera, ChevronRight, Cpu, Crown, Droplet, FileText, Flame, Grip, History, Lock,
  ScanFace, ShieldCheck, Sparkle, Sparkles, Trophy, Waves,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { useApp } from "../context/AppContext";
import { getInsights, listScans, productImageUrl, scanImageUrl } from "../services/api";
import type { CategoryResult, Insights, Scan } from "../types/analysis";
import { formatDate, greeting, scoreColor } from "../lib/format";
import WeatherCard from "../components/WeatherCard";
import { CountUp, Reveal, Skeleton } from "../lib/motion";

const MILESTONES = [1, 5, 10, 25, 50];

function journeyProgress(total: number): { current: number; target: number; maxed: boolean } {
  const target = MILESTONES.find((m) => total < m);
  if (!target) return { current: total, target: MILESTONES[MILESTONES.length - 1], maxed: true };
  return { current: total, target, maxed: false };
}

const FEATURES = [
  { icon: ScanFace, tone: "bg-tint text-fox-500", title: "Smart Face Scan", body: "Guided face positioning for accurate results.", to: "/scan" },
  { icon: Sparkles, tone: "bg-violet-50 text-violet-600 dark:bg-violet-500/15 dark:text-violet-300", title: "Skin Insights", body: "Understand visible skin characteristics.", to: "/about" },
  { icon: ShieldCheck, tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300", title: "Private by Design", body: "Your scans are processed on your own computer.", to: "/privacy" },
  { icon: History, tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/15 dark:text-blue-300", title: "Track Progress", body: "Compare and monitor your skin over time.", to: "/history" },
];

const OVERVIEW: { label: string; icon: LucideIcon; pick: (s: Scan) => CategoryResult; prefix?: string }[] = [
  { label: "Visible Spots", icon: ScanFace, pick: (s) => s.analysis.acne_like_spots },
  { label: "Redness", icon: Waves, pick: (s) => s.analysis.redness },
  { label: "Texture", icon: Grip, pick: (s) => s.analysis.texture },
  { label: "Hydration", icon: Droplet, pick: (s) => s.analysis.dryness_indicators, prefix: "Dryness" },
];

// Photography slots. Drop the files into public/images/; until then each slot falls back to artwork built from
// what the app already has (line-art face, Foxtale product photos from the backend catalogue).
const HERO_PHOTO = "/images/hero-model.jpg";
// the current hero photo (cropped from the reference mockup) already carries faint scan brackets; set false for a plain photo
const HERO_PHOTO_HAS_SCAN_MARKS = true;
const ROUTINE_PHOTO = "/images/routine-products.jpg";
// the catalogue shot whose warm amber tones suit the banner; cropped to the bottle and glowed into the brown
const BANNER_PRODUCT = "vitamin-c-serum.jpg";

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Minimal line-drawn head and shoulders, used wherever there is no photo yet. */
function FaceLineArt({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 200 240" className={className} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" aria-hidden>
      <path d="M100 28c-30 0-50 24-50 58 0 22 7 40 19 53 9 10 20 16 31 16s22-6 31-16c12-13 19-31 19-53 0-34-20-58-50-58Z" />
      <path d="M52 78c10-6 22-22 30-36 14 16 40 26 68 30" opacity=".6" />
      <path d="M80 96c4-3 10-3 14 0M106 96c4-3 10-3 14 0" />
      <path d="M100 104v18c0 3-3 5-6 5" opacity=".7" />
      <path d="M88 138c7 5 17 5 24 0" />
      <path d="M84 152v18M116 152v18" opacity=".7" />
      <path d="M84 170c-26 6-48 18-56 50M116 170c26 6 48 18 56 50" />
    </svg>
  );
}

/** Four scan-corner brackets filling their (relative) parent. */
function ScanCorners({ className = "border-white/70", size = "h-10 w-10", inset = "4" }: { className?: string; size?: string; inset?: "2" | "4" | "8" }) {
  const pos = { "2": ["left-2 top-2", "right-2 top-2", "bottom-2 left-2", "bottom-2 right-2"], "4": ["left-4 top-4", "right-4 top-4", "bottom-4 left-4", "bottom-4 right-4"], "8": ["left-8 top-8", "right-8 top-8", "bottom-8 left-8", "bottom-8 right-8"] }[inset];
  const edges = ["rounded-tl-xl border-l-[1.5px] border-t-[1.5px]", "rounded-tr-xl border-r-[1.5px] border-t-[1.5px]", "rounded-bl-xl border-b-[1.5px] border-l-[1.5px]", "rounded-br-xl border-b-[1.5px] border-r-[1.5px]"];
  return (
    <>
      {edges.map((e, i) => <span key={e} aria-hidden className={`pointer-events-none absolute ${size} ${pos[i]} ${e} ${className}`} />)}
    </>
  );
}

/** Soft blurred leaf for warmth in the corners of the hero and the routine banner. */
function Leaf({ className = "" }: { className?: string }) {
  return (
    <svg viewBox="0 0 120 160" className={`pointer-events-none ${className}`} aria-hidden>
      <path d="M60 155C58 110 40 70 8 40c38 4 66 30 72 70 6-36 2-72-14-104 30 22 48 58 44 100-4 22-20 40-50 49Z" fill="currentColor" />
    </svg>
  );
}

function HeroPhoto() {
  const [photo, setPhoto] = useState(true);
  return (
    <div className="relative h-64 overflow-hidden sm:h-80 lg:absolute lg:inset-y-0 lg:left-[40%] lg:right-0 lg:h-auto xl:right-[19%]">
      {photo ? (
        <img
          src={HERO_PHOTO} onError={() => setPhoto(false)}
          alt="Woman with glowing skin gently touching her cheek and looking at the camera"
          className="h-full w-full object-cover object-[50%_30%] lg:object-center"
        />
      ) : (
        <div className="flex h-full w-full items-center justify-center bg-[radial-gradient(circle_at_50%_45%,rgba(232,84,30,0.16),transparent_62%)]">
          <FaceLineArt className="h-[78%] w-auto text-fox-500/70" />
        </div>
      )}
      {/* fade the photo into the peach background: from below on phones, from the left (and right) on desktop */}
      {photo && (
        <>
          <div className="absolute inset-x-0 bottom-0 h-1/3 bg-gradient-to-t from-[color:var(--hero-from)] to-transparent lg:inset-y-0 lg:left-0 lg:right-auto lg:h-auto lg:w-2/5 lg:bg-gradient-to-r" aria-hidden />
          <div className="absolute inset-y-0 right-0 hidden w-28 bg-gradient-to-l from-[color:var(--hero-to)] to-transparent xl:block" aria-hidden />
        </>
      )}
      {/* AI scanning overlay: brackets around the face plus faint crosshair lines */}
      {!(photo && HERO_PHOTO_HAS_SCAN_MARKS) && <div className="pointer-events-none absolute left-1/2 top-1/2 h-[72%] w-[min(62%,280px)] -translate-x-1/2 -translate-y-1/2" aria-hidden>
        <ScanCorners className={photo ? "border-white/75" : "border-fox-500/60"} />
        <span className={`absolute inset-x-6 top-1/2 h-px ${photo ? "bg-white/30" : "bg-fox-500/25"}`} />
        <span className={`absolute inset-y-6 left-1/2 w-px ${photo ? "bg-white/25" : "bg-fox-500/20"}`} />
      </div>}
    </div>
  );
}

function Panel({ title, subtitle, action, children, className = "" }: { title: string; subtitle?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card p-6 ${className}`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-ink">{title}</h2>
          {subtitle && <p className="mt-1 text-sm text-muted">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </section>
  );
}

/** Bell in the header: shows the scan reminder (Settings > reminder days) when one is due. */
function Reminders({ overdue, days, lastScan, onScan }: { overdue: boolean; days: number | null; lastScan: string | null; onScan: () => void }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative">
      <button
        className="relative flex h-11 w-11 items-center justify-center rounded-full text-ink transition duration-200 hover:bg-card active:scale-90"
        onClick={() => setOpen((o) => !o)} aria-label={overdue ? "Reminders (1 new)" : "Reminders"} aria-expanded={open}
      >
        <Bell size={21} strokeWidth={1.5} />
        {overdue && <span className="absolute right-2.5 top-2.5 h-2.5 w-2.5 rounded-full border-2 border-app bg-fox-500" />}
      </button>
      {open && (
        <>
          <button className="fixed inset-0 z-40 cursor-default" aria-label="Close reminders" onClick={() => setOpen(false)} />
          <div className="toast-in absolute right-0 top-12 z-50 w-72 rounded-card border border-line bg-card p-5 shadow-card-hover">
            <p className="label-caps">Reminders</p>
            {overdue ? (
              <>
                <p className="mt-2 text-sm text-ink">It's been <b>{days} days</b> since your last scan. Time for a check-in?</p>
                <button className="btn-cta mt-3 w-full !py-2 text-sm" onClick={() => { setOpen(false); onScan(); }}>Scan now</button>
              </>
            ) : (
              <p className="mt-2 text-sm text-muted">{lastScan ? `You're all caught up. Last scan ${formatDate(lastScan, false)}.` : "No reminders yet. Your first scan sets the clock."}</p>
            )}
          </div>
        </>
      )}
    </div>
  );
}

const outlinePill = "inline-flex items-center gap-1.5 rounded-full border border-fox-600 px-4 py-2 text-xs font-semibold text-fox-text transition duration-200 hover:bg-fox-600 hover:text-white dark:border-fox-400 dark:text-fox-300 dark:hover:text-white";

export default function Dashboard() {
  const navigate = useNavigate();
  const { settings, dataVersion, profile, backendOnline } = useApp();
  const [data, setData] = useState<Insights | null>(null);
  const [scans, setScans] = useState<Scan[] | null>(null);
  const [routinePhoto, setRoutinePhoto] = useState(true);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 200);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    getInsights().then(setData).catch(() => setData(null));
    listScans()
      .then((s) => setScans([...s].sort((a, b) => b.timestamp.localeCompare(a.timestamp))))
      .catch(() => setScans([]));
  }, [dataVersion, backendOnline]);

  const startScan = () => navigate("/scan", { state: { autostart: true } });
  const total = data?.totalScans ?? 0;
  const { current, target, maxed } = journeyProgress(total);
  const latest = data?.latest ?? null;
  const overdue = data?.daysSinceLast != null && settings.reminder_days > 0 && data.daysSinceLast >= settings.reminder_days;
  const name = profile?.name?.trim() || "Fox";

  return (
    <div className="animate-fade-up space-y-6">
      {/* header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="font-display text-[26px] font-medium leading-tight text-ink sm:text-[32px]">{greeting()}, {name}! 👋</h1>
          <p className="mt-1.5 text-muted">Your skin tells a story. Let's explore it together.</p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <Reminders overdue={overdue} days={data?.daysSinceLast ?? null} lastScan={data?.lastScan ?? null} onScan={startScan} />
          <Link
            to="/settings" title="Your profile" aria-label="Your profile"
            className="flex h-11 w-11 items-center justify-center rounded-full bg-tint text-lg font-semibold text-fox-text transition duration-200 hover:ring-2 hover:ring-fox-300 dark:text-fox-300"
          >
            {name.charAt(0).toUpperCase()}
          </Link>
        </div>
      </div>

      {/* hero */}
      <section className="relative overflow-hidden rounded-hero border border-line bg-[linear-gradient(100deg,var(--hero-from)_42%,var(--hero-to))] lg:min-h-[360px]">
        <HeroPhoto />
        <div className="relative z-10 p-6 sm:p-8 lg:w-[45%] lg:py-9 lg:pl-10 lg:pr-0">
          <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-ink/75">AI Skin Analysis</p>
          <h2 className="mt-3 font-display text-[34px] font-medium leading-[1.1] text-ink sm:text-[40px] xl:text-[44px]">
            Understand Your Skin<br />With <span className="text-fox-500 dark:text-fox-400">AI Vision</span>
          </h2>
          <p className="mt-3 max-w-md text-[15px] leading-relaxed text-ink/80">Get visual insights from your facial scan. It's analysed on your computer and the report goes to your own WhatsApp.</p>
          <div className="mt-5 flex flex-wrap gap-x-8 gap-y-4">
            {[
              { icon: Lock, t: "Private", b: "Your data stays on your device" },
              { icon: Cpu, t: "AI Powered", b: "Advanced visual analysis" },
            ].map(({ icon: Icon, t, b }) => (
              <div key={t} className="flex items-center gap-3">
                <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-tint text-fox-500 ring-1 ring-fox-500/10"><Icon size={19} strokeWidth={1.5} /></span>
                <div><p className="text-sm font-semibold text-ink">{t}</p><p className="text-xs text-muted">{b}</p></div>
              </div>
            ))}
          </div>
          <button className="btn-cta mt-6 !px-7 !py-3 text-[15px]" onClick={startScan}>
            <Camera size={18} strokeWidth={1.75} /> Start AI Skin Scan <ArrowRight size={17} />
          </button>
          <p className="mt-3 text-xs text-muted">Takes about 30 seconds&nbsp;&nbsp;•&nbsp;&nbsp;Camera required</p>
        </div>
        <div className="absolute inset-y-0 right-0 z-10 hidden w-[19%] flex-col justify-between px-6 py-10 xl:flex">
          <p className="font-display text-[22px] italic leading-snug text-fox-text dark:text-fox-300">Clearer<br />Insights.<br />Healthier<br />Skin.</p>
          <img src="/logo_full.png" alt="Foxtale — You glow different" className="w-44 self-center object-contain" />
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="min-w-0 space-y-6">
          {/* skin overview */}
          <Panel
            title="Your Skin Overview" subtitle="Quick insights from your latest scan"
            action={
              <Link to="/history" className="flex shrink-0 items-center gap-1 text-xs text-muted transition hover:text-ink">
                Last scan • {data?.lastScan ? formatDate(data.lastScan, false) : "Not available"} <ChevronRight size={14} />
              </Link>
            }
          >
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {OVERVIEW.map(({ label, icon: Icon, pick, prefix }) => {
                const r = latest ? pick(latest) : null;
                return (
                  <Link
                    key={label} to={latest ? `/analysis/${latest.id}` : "/scan"}
                    className="group flex items-end justify-between gap-2 rounded-2xl border border-line bg-card p-4 transition duration-200 hover:-translate-y-0.5 hover:border-fox-300 hover:shadow-card-hover"
                  >
                    <div className="min-w-0">
                      <span className="flex h-11 w-11 items-center justify-center rounded-full bg-tint text-fox-500"><Icon size={20} strokeWidth={1.5} /></span>
                      <p className="mt-3 text-sm font-semibold text-ink">{label}</p>
                      <p className="mt-0.5 text-xs text-muted">{r ? `${prefix ? prefix + ": " : ""}${cap(r.level)}` : data === null ? "Loading…" : "Not available"}</p>
                    </div>
                    <ChevronRight size={17} strokeWidth={1.5} className="mb-0.5 shrink-0 text-muted transition-transform duration-200 group-hover:translate-x-0.5" />
                  </Link>
                );
              })}
            </div>
          </Panel>

          {/* explore features */}
          <Panel title="Explore Features" subtitle="Tools to help you understand and care for your skin better.">
            <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {FEATURES.map(({ icon: Icon, tone, title, body, to }) => (
                <Link key={title} to={to} className="group flex h-full flex-col rounded-2xl border border-line bg-card p-4 transition duration-200 hover:-translate-y-0.5 hover:border-fox-300 hover:shadow-card-hover">
                  <span className={`flex h-11 w-11 items-center justify-center rounded-full ${tone}`}><Icon size={20} strokeWidth={1.5} /></span>
                  <h3 className="mt-3 text-sm font-semibold text-ink">{title}</h3>
                  <p className="mt-1 flex-1 text-xs leading-relaxed text-muted">{body}</p>
                  <span className="mt-3 inline-flex items-center gap-1 text-xs font-semibold text-fox-text dark:text-fox-300">
                    Learn more <ArrowRight size={13} className="transition-transform duration-200 group-hover:translate-x-0.5" />
                  </span>
                </Link>
              ))}
            </div>
          </Panel>

          {/* routine banner */}
          <section className="relative overflow-hidden rounded-hero bg-gradient-to-r from-[#1c1915] via-[#2e2119] to-[#674831]">
            {routinePhoto ? (
              <div className="absolute inset-y-0 right-0 hidden w-[52%] sm:block [mask-image:linear-gradient(to_right,transparent,#000_38%)]">
                <img src={ROUTINE_PHOTO} onError={() => setRoutinePhoto(false)} alt="Foxtale serums and creams in amber, cream and terracotta tones beside green leaves" className="h-full w-full object-cover" />
              </div>
            ) : (
              <div className="absolute inset-y-0 right-[12%] hidden w-[200px] sm:block [mask-image:radial-gradient(ellipse_27%_60%_at_50%_50%,#000_35%,transparent_80%)]" aria-hidden>
                <img src={productImageUrl(`/product-images/${BANNER_PRODUCT}`) ?? ""} alt="" className="absolute left-[31px] top-[-26px] h-[230px] w-[230px] max-w-none" />
              </div>
            )}
            <Leaf className="absolute -bottom-8 right-6 h-36 w-28 text-[#6f8a4e] opacity-40 blur-[2px]" />
            <div className="relative p-7 sm:max-w-[55%] sm:px-9 sm:py-8">
              <h2 className="font-display text-2xl font-medium text-white sm:text-[28px]">Better Habits. Healthier Skin.</h2>
              <p className="mt-1.5 text-sm text-[#e8d9cc]">Daily care, real results.</p>
              <Link to="/routine" className="mt-5 inline-flex items-center gap-1.5 rounded-full border border-fox-400 px-5 py-2 text-sm font-semibold text-fox-300 transition duration-200 hover:bg-fox-600 hover:text-white">
                Explore Routine <ArrowRight size={14} />
              </Link>
            </div>
          </section>
        </div>

        {/* right column */}
        <div className="space-y-6">
          <Panel title="Recent Scan" subtitle="View your latest skin analysis">
            <div className="mt-6 flex items-center gap-5">
              <div className="relative h-32 w-28 shrink-0 overflow-hidden rounded-2xl bg-soft">
                {latest?.hasImage ? (
                  <img src={scanImageUrl(latest.id)} alt="Your latest scan" className="h-full w-full object-cover" />
                ) : (
                  <>
                    <div className="flex h-full w-full items-end justify-center pt-3 text-muted/70"><FaceLineArt className="h-[92%] w-auto" /></div>
                    <ScanCorners className="border-muted/50" size="h-5 w-5" inset="2" />
                  </>
                )}
              </div>
              <div className="min-w-0">
                {latest ? (
                  <>
                    {latest.analysis.overall_score != null ? (
                      <p className="text-[28px] font-bold leading-none" style={{ color: scoreColor(latest.analysis.overall_score) }}>
                        <CountUp value={latest.analysis.overall_score} duration={1100} /><span className="text-sm font-semibold text-muted"> / 100</span>
                      </p>
                    ) : <p className="text-sm font-semibold text-ink">Scan analysed</p>}
                    <p className="mt-2 text-xs text-muted">{formatDate(latest.timestamp)}</p>
                    <Link to={`/analysis/${latest.id}`} className={`mt-4 ${outlinePill}`}>View analysis <ArrowRight size={13} /></Link>
                  </>
                ) : data === null ? (
                  <div className="space-y-2"><Skeleton className="h-5 w-24" /><Skeleton className="h-10 w-36" /></div>
                ) : (
                  <>
                    <p className="text-sm font-bold text-ink">No scans yet</p>
                    <p className="mt-1 text-xs leading-relaxed text-muted">Start your first scan to get personalised insights.</p>
                    <button onClick={startScan} className={`mt-4 ${outlinePill}`}><Camera size={14} strokeWidth={1.75} /> Start Scan</button>
                  </>
                )}
              </div>
            </div>
          </Panel>

          <Panel
            title="Recent Activity"
            action={<Link to="/history" className="flex shrink-0 items-center gap-1 text-xs font-semibold text-fox-text transition hover:text-fox-700 dark:text-fox-300">View history <ArrowRight size={13} /></Link>}
          >
            {scans === null ? (
              <div className="mt-5 space-y-3"><Skeleton className="h-12" /><Skeleton className="h-12" /></div>
            ) : scans.length === 0 ? (
              <div className="py-8 text-center">
                <div className="relative mx-auto h-20 w-24">
                  <span className="absolute inset-x-2 inset-y-0 flex items-center justify-center rounded-full bg-soft text-muted"><FileText size={28} strokeWidth={1.25} /></span>
                  <Sparkle size={12} className="absolute left-0 top-2 text-muted/60" aria-hidden />
                  <Sparkle size={9} className="absolute bottom-3 left-1 text-muted/50" aria-hidden />
                  <Sparkle size={14} className="absolute right-0 top-0 text-fox-300" aria-hidden />
                  <Sparkle size={9} className="absolute bottom-1 right-2 text-muted/50" aria-hidden />
                </div>
                <p className="mt-5 text-sm font-bold text-ink">No activity yet</p>
                <p className="mx-auto mt-1.5 max-w-[240px] text-xs leading-relaxed text-muted">Your scans and reports will appear here after you complete your first analysis.</p>
              </div>
            ) : (
              <ul className="mt-3 divide-y divide-line">
                {scans.slice(0, 5).map((s) => (
                  <li key={s.id}>
                    <Link to={`/analysis/${s.id}`} className="group -mx-2 flex items-center gap-3 rounded-xl px-2 py-3 transition duration-200 hover:bg-soft">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-tint text-fox-500"><ScanFace size={17} strokeWidth={1.5} /></span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-semibold text-ink">{s.starred ? "★ " : ""}Skin scan{s.note ? ` · ${s.note}` : ""}</span>
                        <span className="block text-xs text-muted">{formatDate(s.timestamp)}</span>
                      </span>
                      {s.analysis.overall_score != null && (
                        <span className="text-sm font-bold" style={{ color: scoreColor(s.analysis.overall_score) }}>{s.analysis.overall_score}</span>
                      )}
                      <ChevronRight size={16} strokeWidth={1.5} className="text-muted transition-transform duration-200 group-hover:translate-x-0.5" />
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Panel>
        </div>
      </div>

      <Reveal><WeatherCard /></Reveal>

      {/* stats */}
      <div className="grid gap-6 sm:grid-cols-3">
        {[
          { icon: Calendar, label: "Scans analysed", value: <CountUp value={total} />, flame: false },
          { icon: Flame, label: "Current streak", value: data && data.streak > 1 ? <><CountUp value={data.streak} /> scans</> : "No streak yet", flame: !!data && data.streak > 1 },
          { icon: Trophy, label: "Last scan", value: data?.lastScan ? formatDate(data.lastScan, false) : "Never", flame: false },
        ].map(({ icon: Icon, label, value, flame }, i) => (
          <Reveal key={label} index={i}>
            <div className="card lift flex items-center gap-4 p-6">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-tint text-fox-500"><Icon size={20} strokeWidth={1.5} className={flame ? "flicker" : ""} /></span>
              <div><p className="text-xl font-bold text-ink">{value}</p><p className="text-sm text-muted">{label}</p></div>
            </div>
          </Reveal>
        ))}
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* journey */}
        <section className="card lift p-6 sm:p-7">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-bold text-ink">Your Skin Journey</h2>
            <span className="flex h-9 w-9 items-center justify-center rounded-full bg-tint text-fox-500"><Crown size={16} strokeWidth={1.5} /></span>
          </div>
          <div className="mt-6 flex items-center justify-between">
            {MILESTONES.map((m) => (
              <div key={m} className="flex flex-col items-center gap-1.5">
                <span className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-bold transition-all duration-500 ${total >= m ? "pop bg-fox-600 text-white shadow-glow" : "border border-line bg-soft text-muted"}`}>{m}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-label="Scans towards next milestone" aria-valuemin={0} aria-valuemax={target} aria-valuenow={current}>
            <div className="h-full rounded-full bg-gradient-to-r from-fox-400 to-fox-600 transition-all duration-1000 ease-out" style={{ width: mounted ? `${Math.min(100, (current / target) * 100)}%` : "0%" }} />
          </div>
          <p className="mt-3 text-center text-sm text-ink"><b className="text-fox-text dark:text-fox-300">{current} / {target}</b> scans completed</p>
          <p className="mt-1 text-center text-xs text-muted">{maxed ? "You've unlocked every milestone so far!" : "Keep scanning to track changes and unlock new insights."}</p>
        </section>

        {/* achievements */}
        <section className="card lift p-6 sm:p-7">
          <h2 className="text-lg font-bold text-ink">Achievements</h2>
          {data === null ? (
            <div className="mt-5 grid grid-cols-2 gap-2.5"><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /><Skeleton className="h-10" /></div>
          ) : data.badges.length === 0 ? (
            <p className="mt-4 text-sm text-muted">Badges appear here as you scan. Your first one unlocks after your first analysis.</p>
          ) : (
            <ul className="mt-5 grid grid-cols-2 gap-2.5">
              {data.badges.map((b, i) => (
                <li key={b.label} style={{ animationDelay: `${i * 60}ms` }} className={`flex items-center gap-2 rounded-2xl border p-3 text-xs font-semibold ${b.earned ? "pop border-fox-300 bg-tint text-fox-text dark:text-fox-300" : "border-line bg-soft text-muted"}`}>
                  {b.kind === "streak" ? <Flame size={15} strokeWidth={1.75} /> : <Award size={15} strokeWidth={1.75} />} {b.label}
                </li>
              ))}
            </ul>
          )}
          {data && data.badges.find((b) => !b.earned) && (
            <p className="mt-4 text-xs text-muted">Next up: <b className="text-ink">{data.badges.find((b) => !b.earned)?.label}</b></p>
          )}
        </section>
      </div>

      {data && data.trends.length > 0 && (
        <p className="card p-6 text-sm text-ink"><b>Trend:</b> {data.headline}</p>
      )}
    </div>
  );
}
