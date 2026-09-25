import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowDownUp, Camera, ChevronLeft, ChevronRight, Download, History as HistoryIcon, RotateCcw, Search, Star, Trash2, Upload,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import {
  deleteForever, deleteScan, emptyTrash, exportUrl, getInsights, importData, listScans, listTrash, patchScan, restoreScan,
} from "../services/api";
import type { Insights, Scan } from "../types/analysis";
import { formatDate, scoreColor } from "../lib/format";
import { EmptyState, LevelPill, Modal, PageHeader, SectionTitle } from "../components/ui";
import { CountUp, Reveal, Skeleton, useInView } from "../lib/motion";

const PAGE_SIZE = 8;

function TrendChart({ series }: { series: { timestamp: string; score: number | null }[] }) {
  const [ref, seen] = useInView<SVGSVGElement>(0.3);
  const pts = series.filter((p) => p.score != null) as { timestamp: string; score: number }[];
  if (pts.length < 2) {
    return <p className="py-10 text-center text-sm text-muted">Two or more scans with an overall score are needed to draw a trend.</p>;
  }
  const W = 640;
  const H = 180;
  const pad = 28;
  const x = (i: number) => pad + (i * (W - pad * 2)) / (pts.length - 1);
  const y = (s: number) => H - pad - (s / 100) * (H - pad * 2);
  const path = pts.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p.score).toFixed(1)}`).join(" ");
  return (
    <svg ref={ref} viewBox={`0 0 ${W} ${H}`} className="h-auto w-full" role="img" aria-label="Overall skin score over time">
      {[0, 50, 100].map((g) => (
        <g key={g}>
          <line x1={pad} x2={W - pad} y1={y(g)} y2={y(g)} stroke="var(--line)" strokeDasharray="4 4" />
          <text x={4} y={y(g) + 4} className="fill-muted text-[10px]">{g}</text>
        </g>
      ))}
      <path
        d={path} fill="none" stroke="#e54a00" strokeWidth="2.5" strokeLinejoin="round" pathLength={1}
        strokeDasharray={1} strokeDashoffset={seen ? 0 : 1} style={{ transition: "stroke-dashoffset 1.4s cubic-bezier(0.22, 1, 0.36, 1)" }}
      />
      {pts.map((p, i) => (
        <circle
          key={p.timestamp} cx={x(i)} cy={y(p.score)} r={seen ? 4.5 : 0} fill={scoreColor(p.score)} stroke="var(--card)" strokeWidth="2"
          style={{ transition: `r .4s cubic-bezier(0.34, 1.56, 0.64, 1) ${0.5 + i * 0.12}s` }}
        >
          <title>{`${formatDate(p.timestamp, false)}: ${p.score}`}</title>
        </circle>
      ))}
    </svg>
  );
}

export default function History() {
  const navigate = useNavigate();
  const { toast, bumpData, dataVersion } = useApp();
  const [tab, setTab] = useState<"scans" | "trash">("scans");
  const [scans, setScans] = useState<Scan[] | null>(null);
  const [trash, setTrash] = useState<Scan[]>([]);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [query, setQuery] = useState("");
  const [starredOnly, setStarredOnly] = useState(false);
  const [sort, setSort] = useState<"newest" | "oldest" | "score">("newest");
  const [page, setPage] = useState(0);
  const [confirmEmpty, setConfirmEmpty] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(() => {
    listScans().then(setScans).catch(() => setScans([]));
    listTrash().then(setTrash).catch(() => setTrash([]));
    getInsights().then(setInsights).catch(() => undefined);
  }, []);
  useEffect(load, [load, dataVersion]);

  const filtered = useMemo(() => {
    let list = scans ?? [];
    if (starredOnly) list = list.filter((s) => s.starred);
    const q = query.trim().toLowerCase();
    if (q) {
      list = list.filter((s) =>
        `${formatDate(s.timestamp)} ${s.note} ${s.journal.routine.join(" ")} ${s.regions.map((r) => r.category).join(" ")}`.toLowerCase().includes(q)
      );
    }
    const sorted = [...list];
    if (sort === "oldest") sorted.reverse();
    if (sort === "score") sorted.sort((a, b) => (b.analysis.overall_score ?? -1) - (a.analysis.overall_score ?? -1));
    return sorted;
  }, [scans, query, starredOnly, sort]);

  const pages = Math.max(1, Math.ceil(filtered.length / PAGE_SIZE));
  const visible = filtered.slice(page * PAGE_SIZE, page * PAGE_SIZE + PAGE_SIZE);
  useEffect(() => setPage(0), [query, starredOnly, sort, tab]);

  const act = async (fn: () => Promise<unknown>, message: string) => {
    try {
      await fn();
      toast(message);
      bumpData();
    } catch {
      toast("Something went wrong. Please try again.");
    }
  };

  const onImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      const { imported } = await importData(file);
      toast(`Imported ${imported} scan${imported === 1 ? "" : "s"}`);
      bumpData();
    } catch {
      toast("That file is not a valid Foxtale export");
    }
  };

  if (scans === null) {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading your history">
        <Skeleton className="h-10 w-64" />
        <div className="grid gap-4 sm:grid-cols-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-20" />)}</div>
        <Skeleton className="h-56" />
        {[0, 1, 2].map((i) => <Skeleton key={i} className="h-20" />)}
      </div>
    );
  }

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Scan History" subtitle="Review your past skin scans and track changes over time."
        actions={
          <>
            <a className="btn-soft" href={exportUrl()} download><Download size={15} /> Export</a>
            <button className="btn-soft" onClick={() => fileRef.current?.click()}><Upload size={15} /> Import</button>
            <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={(e) => { onImport(e.target.files?.[0]); e.target.value = ""; }} />
          </>
        }
      />

      <div className="mb-5 flex gap-2" role="tablist">
        <button role="tab" aria-selected={tab === "scans"} className={`chip ${tab === "scans" ? "chip-on" : ""}`} onClick={() => setTab("scans")}><HistoryIcon size={14} /> Scans ({scans.length})</button>
        <button role="tab" aria-selected={tab === "trash"} className={`chip ${tab === "trash" ? "chip-on" : ""}`} onClick={() => setTab("trash")}><Trash2 size={14} /> Recently Deleted ({trash.length})</button>
      </div>

      {tab === "scans" && (
        <>
          {scans.length === 0 ? (
            <EmptyState
              icon={<HistoryIcon size={28} />} title="No scans yet"
              body="Your saved scans will appear here. Make sure Save scan history is on in Privacy."
              action={<Link to="/scan" state={{ autostart: true }} className="btn-cta"><Camera size={18} /> Start New Scan</Link>}
            />
          ) : (
            <>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                {[
                  { label: "Scans analysed", value: <CountUp value={insights?.totalScans ?? scans.length} /> },
                  { label: "Current streak", value: insights && insights.streak > 1 ? `${insights.streak} scans` : "No current streak" },
                  { label: "Most-flagged region", value: insights?.mostFrequentRegion ?? "None yet" },
                  { label: "Most-flagged category", value: insights?.mostFrequentCategory ?? "None yet" },
                ].map((s, i) => (
                  <Reveal key={s.label} index={i}><div className="card lift p-5"><p className="text-xl font-extrabold text-ink">{s.value}</p><p className="text-sm text-muted">{s.label}</p></div></Reveal>
                ))}
              </div>

              <Reveal as="section" className="card mt-5 p-5">
                <SectionTitle title="Overall score over time" subtitle={insights?.headline} />
                <div className="mt-3"><TrendChart series={insights?.scoreSeries ?? []} /></div>
              </Reveal>

              <div className="mt-5 flex flex-wrap items-center gap-3">
                <div className="relative min-w-[220px] flex-1">
                  <Search size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted" />
                  <input className="input !pl-10" placeholder="Search by date, note, or keyword..." value={query} onChange={(e) => setQuery(e.target.value)} aria-label="Search scans" />
                </div>
                <button className={`chip ${starredOnly ? "chip-on" : ""}`} aria-pressed={starredOnly} onClick={() => setStarredOnly((v) => !v)}><Star size={14} /> Starred</button>
                <label className="flex items-center gap-2 text-sm text-muted">
                  <ArrowDownUp size={14} />
                  <select className="input !w-auto !rounded-full" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)} aria-label="Sort scans">
                    <option value="newest">Newest first</option>
                    <option value="oldest">Oldest first</option>
                    <option value="score">Highest score</option>
                  </select>
                </label>
              </div>

              <ul className="mt-4 space-y-3">
                {visible.map((s, i) => (
                  <li key={s.id} className="card page-enter lift group flex flex-wrap items-center gap-x-5 gap-y-3 p-4" style={{ animationDelay: `${i * 55}ms` }}>
                    <button onClick={() => navigate(`/analysis/${s.id}`)} className="flex min-w-[200px] flex-1 items-center gap-4 text-left">
                      <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-soft text-lg font-extrabold transition-transform duration-300 group-hover:scale-105" style={{ color: s.analysis.overall_score != null ? scoreColor(s.analysis.overall_score) : "var(--muted)" }}>
                        {s.analysis.overall_score ?? "--"}
                      </span>
                      <span>
                        <span className="block font-extrabold text-ink">{formatDate(s.timestamp)}</span>
                        <span className="block max-w-[320px] truncate text-sm text-muted">{s.note || "No note"}</span>
                      </span>
                    </button>
                    <div className="flex flex-wrap gap-1.5">
                      <LevelPill level={s.analysis.acne_like_spots.level} />
                      <LevelPill level={s.analysis.redness.level} />
                      <LevelPill level={s.analysis.texture.level} />
                      <LevelPill level={s.analysis.dryness_indicators.level} />
                    </div>
                    <div className="flex items-center gap-1">
                      <button className="rounded-full p-2 hover:bg-soft" aria-label={s.starred ? "Unstar scan" : "Star scan"} onClick={() => act(() => patchScan(s.id, { starred: !s.starred }), s.starred ? "Scan unstarred" : "Scan starred")}>
                        <Star key={String(s.starred)} size={17} className={s.starred ? "star-burst fill-amber-400 text-amber-400" : "text-muted"} />
                      </button>
                      <button className="rounded-full p-2 text-muted hover:bg-soft hover:text-rose-600" aria-label="Delete scan" onClick={() => act(() => deleteScan(s.id), "Moved to Recently Deleted")}>
                        <Trash2 size={17} />
                      </button>
                    </div>
                  </li>
                ))}
                {visible.length === 0 && <li className="card p-8 text-center text-sm text-muted">No scans match your filters yet.</li>}
              </ul>

              {pages > 1 && (
                <div className="mt-5 flex items-center justify-center gap-3">
                  <button className="btn-soft" disabled={page === 0} onClick={() => setPage((p) => p - 1)}><ChevronLeft size={15} /> Prev</button>
                  <span className="text-sm text-muted">Page {page + 1} of {pages}</span>
                  <button className="btn-soft" disabled={page >= pages - 1} onClick={() => setPage((p) => p + 1)}>Next <ChevronRight size={15} /></button>
                </div>
              )}

              {insights && (
                <Reveal as="section" className="card mt-6 p-5">
                  <SectionTitle title="Your Personal Baseline" subtitle="Your most common visible level per category, across your own history." />
                  <div className="mt-3 flex flex-wrap gap-4">
                    {Object.entries(insights.baseline).map(([k, v]) => (
                      <div key={k} className="flex items-center gap-2 text-sm"><span className="text-muted">{k}</span><LevelPill level={v as never} /></div>
                    ))}
                  </div>
                  {insights.trends.length > 0 && (
                    <ul className="mt-4 space-y-1 border-t border-line pt-3 text-sm">
                      {insights.trends.map((t) => (
                        <li key={t.label} className="flex justify-between"><span className="text-ink">{t.label}</span>
                          <span className={t.direction === "improved" ? "font-bold text-emerald-600" : t.direction === "worsened" ? "font-bold text-amber-600" : "text-muted"}>
                            {t.direction === "improved" ? "↓ improved" : t.direction === "worsened" ? "↑ more noticeable" : "→ stable"}
                          </span>
                        </li>
                      ))}
                    </ul>
                  )}
                </Reveal>
              )}
            </>
          )}
        </>
      )}

      {tab === "trash" && (
        <>
          <div className="mb-4 flex items-center justify-between">
            <p className="text-sm text-muted">Deleted scans are kept for 30 days, then removed for good.</p>
            <button className="btn-danger" disabled={trash.length === 0} onClick={() => setConfirmEmpty(true)}><Trash2 size={15} /> Empty</button>
          </div>
          {trash.length === 0 ? (
            <p className="card p-8 text-center text-sm text-muted">Recently Deleted is empty.</p>
          ) : (
            <ul className="space-y-3">
              {trash.map((s) => (
                <li key={s.id} className="card flex flex-wrap items-center justify-between gap-3 p-4">
                  <div>
                    <p className="font-extrabold text-ink">{formatDate(s.timestamp)}</p>
                    <p className="text-sm text-muted">{s.daysLeft} day{s.daysLeft === 1 ? "" : "s"} left</p>
                  </div>
                  <div className="flex gap-2">
                    <button className="btn-soft" onClick={() => act(() => restoreScan(s.id), "Scan restored")}><RotateCcw size={15} /> Restore</button>
                    <button className="btn-danger" onClick={() => act(() => deleteForever(s.id), "Scan permanently deleted")}>Delete forever</button>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </>
      )}

      <Modal open={confirmEmpty} onClose={() => setConfirmEmpty(false)} title="Empty Recently Deleted?">
        <p className="text-sm text-muted">This permanently removes {trash.length} scan{trash.length === 1 ? "" : "s"} and their photos. It cannot be undone.</p>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-soft" onClick={() => setConfirmEmpty(false)}>Cancel</button>
          <button className="btn-danger" onClick={() => { setConfirmEmpty(false); act(() => emptyTrash(), "Recently Deleted emptied"); }}>Delete forever</button>
        </div>
      </Modal>
    </div>
  );
}
