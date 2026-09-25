import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  Award, BarChart3, Bell, Calendar, Camera, Crown, Flame, History, Lock, ScanFace, ScanLine, ShieldCheck, Sparkles, Trophy,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import { getInsights } from "../services/api";
import type { Insights } from "../types/analysis";
import { LEVEL_DOT, formatDate, greeting, scoreColor } from "../lib/format";
import { LevelPill } from "../components/ui";
import WeatherCard from "../components/WeatherCard";
import { CountUp, Reveal, Skeleton } from "../lib/motion";

const MILESTONES = [1, 5, 10, 25, 50];

function journeyProgress(total: number): { current: number; target: number; maxed: boolean } {
  const target = MILESTONES.find((m) => total < m);
  if (!target) return { current: total, target: MILESTONES[MILESTONES.length - 1], maxed: true };
  return { current: total, target, maxed: false };
}

const FEATURES = [
  { icon: ScanFace, tone: "bg-orange-50 text-fox-500 dark:bg-fox-500/15", title: "Smart Face Scan", body: "Guided face positioning for accurate results.", to: "/scan" },
  { icon: Sparkles, tone: "bg-violet-50 text-violet-600 dark:bg-violet-500/15", title: "Skin Insights", body: "Understand visible skin characteristics.", to: "/about" },
  { icon: ShieldCheck, tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15", title: "Private by Design", body: "Your scans are processed on your own computer.", to: "/privacy" },
  { icon: History, tone: "bg-blue-50 text-blue-600 dark:bg-blue-500/15", title: "Track Progress", body: "Compare and monitor your skin over time.", to: "/history" },
];

export default function Dashboard() {
  const navigate = useNavigate();
  const { settings, dataVersion, profile } = useApp();
  const [data, setData] = useState<Insights | null>(null);
  const [mounted, setMounted] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setMounted(true), 200);
    return () => clearTimeout(t);
  }, []);

  useEffect(() => {
    getInsights().then(setData).catch(() => setData(null));
  }, [dataVersion]);

  const startScan = () => navigate("/scan", { state: { autostart: true } });
  const total = data?.totalScans ?? 0;
  const { current, target, maxed } = journeyProgress(total);
  const latest = data?.latest ?? null;
  const overdue = data?.daysSinceLast != null && settings.reminder_days > 0 && data.daysSinceLast >= settings.reminder_days;

  return (
    <div className="animate-fade-up space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-ink sm:text-[30px]">{greeting()}, {profile?.name?.trim() || "Fox"}! 👋</h1>
          <p className="mt-1 text-muted">Let's understand your skin today.</p>
        </div>
        <button className="btn-cta text-base" onClick={startScan}><ScanFace size={18} /> Start New Scan</button>
      </div>

      {overdue && (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-fox-500/25 bg-fox-50 p-4 dark:bg-fox-500/10">
          <p className="flex items-center gap-2.5 text-sm font-semibold text-ink"><Bell size={18} className="text-fox-500" /> It's been {data?.daysSinceLast} days since your last scan. Time for a check-in?</p>
          <button className="btn-cta !px-5 !py-2 text-sm" onClick={startScan}>Scan Now</button>
        </div>
      )}

      {/* hero */}
      <section className="card overflow-hidden">
        <div className="grid items-center gap-6 bg-gradient-to-br from-fox-50 via-card to-card p-7 dark:from-fox-500/10 md:grid-cols-[1.2fr_1fr] md:p-10">
          <div>
            <h2 className="text-3xl font-extrabold leading-tight text-ink sm:text-4xl">
              Understand Your Skin<br />With AI <span className="text-fox-500">Vision</span>
            </h2>
            <p className="mt-3 max-w-md text-muted">Get visual insights from your facial scan. It is analysed on your computer and the report goes to your own WhatsApp.</p>
            <div className="mt-5 flex flex-wrap gap-6">
              {[
                { icon: Lock, t: "Private", b: "Your data stays on your device" },
                { icon: ScanLine, t: "AI Powered", b: "Advanced visual analysis" },
              ].map(({ icon: Icon, t, b }) => (
                <div key={t} className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-full bg-fox-500/10 text-fox-500"><Icon size={18} /></span>
                  <div><p className="text-sm font-extrabold text-ink">{t}</p><p className="text-xs text-muted">{b}</p></div>
                </div>
              ))}
            </div>
            <button className="btn-cta cta-pulse mt-7 text-base" onClick={startScan}><Camera size={18} /> Start AI Skin Scan</button>
            <p className="mt-3 text-xs text-muted">Takes about 30 seconds  •  Camera required</p>
          </div>
          <div className="hidden justify-center md:flex">
            <img src="/logo_full.png" alt="Foxtale" className="float max-h-64 object-contain drop-shadow-[0_18px_28px_rgba(229,74,0,0.18)]" />
          </div>
        </div>
      </section>

      {/* feature tiles */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {FEATURES.map(({ icon: Icon, tone, title, body, to }, i) => (
          <Reveal key={title} index={i} className="h-full">
          <Link to={to} className="card lift group block h-full p-5 hover:border-fox-300">
            <span className={`flex h-11 w-11 items-center justify-center rounded-full transition-transform duration-500 group-hover:rotate-[10deg] group-hover:scale-110 ${tone}`}><Icon size={20} /></span>
            <h3 className="mt-3 font-extrabold text-ink">{title}</h3>
            <p className="mt-1 text-sm text-muted">{body}</p>
            <span className="mt-3 inline-block text-sm font-bold text-fox-text transition-transform group-hover:translate-x-1 dark:text-fox-300">Learn more →</span>
          </Link>
          </Reveal>
        ))}
      </div>

      <Reveal><WeatherCard /></Reveal>

      {/* stats */}
      <div className="grid gap-4 sm:grid-cols-3">
        {[
          { icon: Calendar, label: "Scans analysed", value: <CountUp value={total} />, flame: false },
          { icon: Flame, label: "Current streak", value: data && data.streak > 1 ? <><CountUp value={data.streak} /> scans</> : "No streak yet", flame: !!data && data.streak > 1 },
          { icon: Trophy, label: "Last scan", value: data?.lastScan ? formatDate(data.lastScan, false) : "Never", flame: false },
        ].map(({ icon: Icon, label, value, flame }, i) => (
          <Reveal key={label} index={i}>
            <div className="card lift flex items-center gap-4 p-5">
              <span className="flex h-12 w-12 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15"><Icon size={20} className={flame ? "flicker" : ""} /></span>
              <div><p className="text-xl font-extrabold text-ink">{value}</p><p className="text-sm text-muted">{label}</p></div>
            </div>
          </Reveal>
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        {/* journey */}
        <section className="card lift p-6">
          <div className="flex items-center justify-between">
            <h2 className="font-extrabold text-ink">Your Skin Journey</h2>
            <span className="flex h-8 w-8 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15"><Crown size={15} /></span>
          </div>
          <div className="mt-5 flex items-center justify-between">
            {MILESTONES.map((m) => (
              <div key={m} className="flex flex-col items-center gap-1.5">
                <span className={`flex h-9 w-9 items-center justify-center rounded-full text-xs font-extrabold transition-all duration-500 ${total >= m ? "pop bg-fox-600 text-white shadow-glow" : "border border-line bg-soft text-muted"}`}>{m}</span>
              </div>
            ))}
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-line" role="progressbar" aria-valuemin={0} aria-valuemax={target} aria-valuenow={current}>
            <div className="h-full rounded-full bg-gradient-to-r from-fox-400 to-fox-600 transition-all duration-1000 ease-out" style={{ width: mounted ? `${Math.min(100, (current / target) * 100)}%` : "0%" }} />
          </div>
          <p className="mt-3 text-center text-sm"><b className="text-fox-text dark:text-fox-300">{current} / {target}</b> scans completed</p>
          <p className="mt-1 text-center text-xs text-muted">{maxed ? "You've unlocked every milestone so far!" : "Keep scanning to track changes and unlock new insights."}</p>
        </section>

        {/* latest analysis */}
        <section className="card lift p-6">
          <h2 className="font-extrabold text-ink">Latest Analysis</h2>
          {latest ? (
            <>
              <p className="mt-1 text-sm text-muted">{formatDate(latest.timestamp)}</p>
              {latest.analysis.overall_score != null && (
                <p className="mt-3 text-3xl font-extrabold" style={{ color: scoreColor(latest.analysis.overall_score) }}>
                  <CountUp value={latest.analysis.overall_score} duration={1100} /><span className="text-sm font-semibold text-muted"> / 100</span>
                </p>
              )}
              <ul className="mt-3 space-y-2">
                {([["Acne-like spots", latest.analysis.acne_like_spots], ["Visible redness", latest.analysis.redness], ["Skin texture", latest.analysis.texture], ["Dryness indicators", latest.analysis.dryness_indicators]] as const).map(([label, r]) => (
                  <li key={label} className="flex items-center gap-2.5 text-sm">
                    <span className="h-2.5 w-2.5 rounded-full" style={{ background: LEVEL_DOT[r.level] }} />
                    <span className="flex-1 text-ink">{label}</span>
                    <LevelPill level={r.level} />
                  </li>
                ))}
              </ul>
              <Link to={`/analysis/${latest.id}`} className="btn-soft mt-4 w-full"><BarChart3 size={15} /> View Full Analysis</Link>
            </>
          ) : (
            data === null ? <div className="mt-4 space-y-3"><Skeleton className="h-8 w-24" /><Skeleton className="h-24" /></div>
            : <p className="mt-3 text-sm text-muted">No scans yet. Start your first scan to see insights here.</p>
          )}
        </section>

        {/* achievements */}
        <section className="card lift p-6">
          <h2 className="font-extrabold text-ink">Achievements</h2>
          <ul className="mt-4 grid grid-cols-2 gap-2.5">
            {(data?.badges ?? []).map((b, i) => (
              <li key={b.label} style={{ animationDelay: `${i * 60}ms` }} className={`flex items-center gap-2 rounded-2xl border p-2.5 text-xs font-bold ${b.earned ? "pop" : ""} ${b.earned ? "border-fox-300 bg-fox-50 text-fox-text dark:bg-fox-500/15 dark:text-fox-300" : "border-line bg-soft text-muted"}`}>
                {b.kind === "streak" ? <Flame size={15} /> : <Award size={15} />} {b.label}
              </li>
            ))}
          </ul>
          {data && data.badges.find((b) => !b.earned) && (
            <p className="mt-3 text-xs text-muted">Next up: <b className="text-ink">{data.badges.find((b) => !b.earned)?.label}</b></p>
          )}
        </section>
      </div>

      {data && data.trends.length > 0 && (
        <p className="card p-5 text-sm text-ink"><b>Trend:</b> {data.headline}</p>
      )}
    </div>
  );
}
