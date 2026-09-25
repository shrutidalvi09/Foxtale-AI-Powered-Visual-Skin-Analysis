import { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowDown, ArrowRight, ArrowUp, Camera, GitCompare, Info } from "lucide-react";
import { useApp } from "../context/AppContext";
import { listScans, scanImageUrl } from "../services/api";
import type { Scan } from "../types/analysis";
import { LEVEL_SCORE, formatDate, scoreColor } from "../lib/format";
import { EmptyState, LevelPill, PageHeader, ScoreBar, SectionTitle } from "../components/ui";
import { Reveal, Skeleton } from "../lib/motion";

const CATEGORIES = [
  { label: "Acne-like Spots", get: (s: Scan) => s.analysis.acne_like_spots },
  { label: "Visible Redness", get: (s: Scan) => s.analysis.redness },
  { label: "Skin Texture", get: (s: Scan) => s.analysis.texture },
  { label: "Dryness Indicators", get: (s: Scan) => s.analysis.dryness_indicators },
  { label: "Oiliness / Shine", get: (s: Scan) => s.analysis.oiliness },
  { label: "Tone Evenness", get: (s: Scan) => s.analysis.tone_evenness },
];

function BeforeAfter({ before, after }: { before: string; after: string }) {
  const [pos, setPos] = useState(50);
  const [touched, setTouched] = useState(false);
  const box = useRef<HTMLDivElement>(null);
  const drag = (clientX: number) => {
    setTouched(true);
    const r = box.current?.getBoundingClientRect();
    if (r) setPos(Math.min(100, Math.max(0, ((clientX - r.left) / r.width) * 100)));
  };
  return (
    <div
      ref={box} className="relative mx-auto aspect-square w-full max-w-[460px] cursor-ew-resize touch-none select-none overflow-hidden rounded-[20px] bg-[#0b1224]"
      onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); drag(e.clientX); }}
      onPointerMove={(e) => e.buttons && drag(e.clientX)}
    >
      <img src={after} alt="Later scan" className="absolute inset-0 h-full w-full object-cover" draggable={false} />
      <img src={before} alt="Earlier scan" className="absolute inset-0 h-full w-full object-cover" style={{ clipPath: `inset(0 ${100 - pos}% 0 0)` }} draggable={false} />
      <span className="absolute left-3 top-3 rounded-full bg-black/60 px-3 py-1 text-xs font-bold text-white">Before</span>
      <span className="absolute right-3 top-3 rounded-full bg-black/60 px-3 py-1 text-xs font-bold text-white">After</span>
      <div className="absolute inset-y-0 w-0.5 bg-white shadow" style={{ left: `${pos}%` }}>
        <span className={`absolute left-1/2 top-1/2 flex h-9 w-9 -translate-x-1/2 -translate-y-1/2 items-center justify-center rounded-full bg-white text-[#0b1224] shadow-lg transition-transform hover:scale-110 ${touched ? "" : "cta-pulse"}`}>⇄</span>
      </div>
    </div>
  );
}

export default function Compare() {
  const { dataVersion } = useApp();
  const [scans, setScans] = useState<Scan[] | null>(null);
  const [aId, setAId] = useState("");
  const [bId, setBId] = useState("");

  useEffect(() => {
    listScans().then((all) => {
      setScans(all);
      // default: oldest as start, newest as end
      if (all.length >= 2) {
        setAId((cur) => (all.some((s) => s.id === cur) ? cur : all[all.length - 1].id));
        setBId((cur) => (all.some((s) => s.id === cur) ? cur : all[0].id));
      }
    }).catch(() => setScans([]));
  }, [dataVersion]);

  const a = useMemo(() => scans?.find((s) => s.id === aId) ?? null, [scans, aId]);
  const b = useMemo(() => scans?.find((s) => s.id === bId) ?? null, [scans, bId]);

  if (scans === null) return <div className="space-y-4" aria-busy="true"><Skeleton className="h-10 w-64" /><Skeleton className="h-24" /><Skeleton className="h-96" /></div>;
  if (scans.length < 2) {
    return (
      <div className="animate-fade-up">
        <PageHeader title="Compare Scans" subtitle="Compare your skin scans to track changes and progress over time." />
        <EmptyState
          icon={<GitCompare size={28} />} title="Need at least two saved scans"
          body="Save two or more scans (Save scan history must be on in Privacy) and you can compare them here."
          action={<Link to="/scan" state={{ autostart: true }} className="btn-cta"><Camera size={18} /> Start New Scan</Link>}
        />
      </div>
    );
  }

  const same = a && b && a.id === b.id;
  const scoreDelta = a?.analysis.overall_score != null && b?.analysis.overall_score != null ? b.analysis.overall_score - a.analysis.overall_score : null;
  const options = scans.map((s) => <option key={s.id} value={s.id}>{formatDate(s.timestamp)}</option>);

  return (
    <div className="animate-fade-up space-y-6">
      <PageHeader title="Compare Scans" subtitle="Compare your skin scans to track changes and progress over time." />

      <div className="card grid items-end gap-4 p-5 sm:grid-cols-[1fr_auto_1fr]">
        <label className="block"><span className="label-caps">Start scan</span>
          <select className="input mt-1.5" value={aId} onChange={(e) => setAId(e.target.value)}>{options}</select></label>
        <span className="hidden pb-2.5 text-sm font-extrabold text-muted sm:block">VS</span>
        <label className="block"><span className="label-caps">End scan</span>
          <select className="input mt-1.5" value={bId} onChange={(e) => setBId(e.target.value)}>{options}</select></label>
      </div>

      {same ? (
        <p className="card p-8 text-center text-sm text-muted">Choose two different scans to compare.</p>
      ) : a && b ? (
        <>
          <Reveal as="section" className="card p-5 sm:p-6">
            <SectionTitle title="Before / After Photo" subtitle="Drag the divider to compare the two photos." />
            <div className="mt-4">
              {a.hasImage && b.hasImage ? (
                <BeforeAfter before={scanImageUrl(a.id)} after={scanImageUrl(b.id)} />
              ) : (
                <p className="flex items-start gap-2 rounded-2xl bg-soft p-4 text-sm text-muted"><Info size={16} className="mt-0.5 shrink-0" /> Both scans need a saved photo to compare visually. Turn on "Save scan photos" in Privacy before your next scans.</p>
              )}
            </div>
          </Reveal>

          <Reveal as="section" className="card p-5 sm:p-6">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <SectionTitle title="Category Comparison" subtitle="How each visible category changed between the two scans." />
              {scoreDelta != null && (
                <div className="flex items-center gap-3 rounded-2xl bg-soft px-4 py-2">
                  <span className="text-sm text-muted">Overall</span>
                  <b style={{ color: scoreColor(a!.analysis.overall_score!) }}>{a!.analysis.overall_score}</b><ArrowRight size={14} className="text-muted" />
                  <b style={{ color: scoreColor(b.analysis.overall_score!) }}>{b.analysis.overall_score}</b>
                  <span className={`text-sm font-extrabold ${scoreDelta > 0 ? "text-emerald-600" : scoreDelta < 0 ? "text-rose-600" : "text-muted"}`}>{scoreDelta > 0 ? "+" : ""}{scoreDelta}</span>
                </div>
              )}
            </div>
            <div className="mt-4 divide-y divide-line">
              {CATEGORIES.map(({ label, get }) => {
                const ra = get(a);
                const rb = get(b);
                if (!ra || !rb) return null;
                const d = LEVEL_SCORE[rb.level] - LEVEL_SCORE[ra.level];
                return (
                  <div key={label} className="page-enter grid grid-cols-[1fr_auto] items-center gap-3 py-3 sm:grid-cols-[200px_1fr_120px]">
                    <span className="font-bold text-ink">{label}</span>
                    <div className="flex items-center gap-2 sm:justify-center"><LevelPill level={ra.level} /><ArrowRight size={14} className="text-muted" /><LevelPill level={rb.level} /></div>
                    <span className={`col-span-2 text-sm font-bold sm:col-span-1 sm:text-right ${d < 0 ? "text-emerald-600" : d > 0 ? "text-amber-600" : "text-muted"}`}>
                      {d < 0 ? <><ArrowDown size={13} className="inline" /> Improved</> : d > 0 ? <><ArrowUp size={13} className="inline" /> More visible</> : "No change"}
                    </span>
                  </div>
                );
              })}
            </div>
          </Reveal>

          {a.analysis.region_scores && b.analysis.region_scores && (
            <Reveal as="section" className="card p-5 sm:p-6">
              <SectionTitle title="Facial Region Comparison" subtitle="Region scores (higher is clearer)." />
              <ul className="mt-4 space-y-4">
                {Object.keys(b.analysis.region_scores).filter((r) => a.analysis.region_scores?.[r]).map((r) => {
                  const sa = a.analysis.region_scores![r].score;
                  const sb = b.analysis.region_scores![r].score;
                  return (
                    <li key={r}>
                      <div className="mb-1 flex items-baseline justify-between text-sm"><span className="font-bold capitalize text-ink">{r}</span>
                        <span className="text-muted">{sa} → <b className="text-ink">{sb}</b> <span className={sb > sa ? "text-emerald-600" : sb < sa ? "text-rose-600" : ""}>({sb - sa > 0 ? "+" : ""}{sb - sa})</span></span></div>
                      <div className="grid gap-1"><ScoreBar score={sa} /><ScoreBar score={sb} /></div>
                    </li>
                  );
                })}
              </ul>
            </Reveal>
          )}

          <p className="text-xs text-muted">
            We compare the visible skin observations stored with each scan, by category and by facial region. Differences can also come from lighting or angle, so compare scans taken in similar conditions.
          </p>
        </>
      ) : null}
    </div>
  );
}
