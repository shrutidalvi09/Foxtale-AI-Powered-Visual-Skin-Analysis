import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  BarChart3, Camera, ChevronLeft, ChevronRight, ClipboardCheck, Download, Eye, FileText, Lightbulb, Lock, NotebookPen,
  Plus, Star, Trash2, Sparkles, LayoutGrid, Info, ScanSearch,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import {
  deleteScan, downloadPdf, getInsights, getOptions, getReport, listScans, patchScan, scanImageUrl,
} from "../services/api";
import type { Insights, Report, Scan } from "../types/analysis";
import { LEVEL_SCORE, formatDate, scoreColor } from "../lib/format";
import { Disclaimer, EmptyState, IconBadge, LevelPill, PageHeader, ScoreBar, ScoreRing, SectionTitle } from "../components/ui";
import { CountUp, Reveal, Skeleton, usePulseKey } from "../lib/motion";
import PhotoPanel, { RegionDonut } from "../components/PhotoPanel";
import { DeliveryStatus } from "../components/WhatsApp";
import Skincare from "../components/Skincare";
import type { Finding, RegionObservation } from "../types/analysis";

const CARD_KEYS = ["Acne-like spots", "Redness", "Texture", "Dryness indicators"];

type NavTarget = { key: string; label: string; icon: typeof Eye; ref: React.MutableRefObject<HTMLElement | null> };

/** Sticky jump bar; the chip for the section you are reading is highlighted. */
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
    <div className="sticky top-2 z-30 -mx-1 mb-5 overflow-x-auto rounded-full border border-line bg-card/85 px-2 py-1.5 shadow-card backdrop-blur lg:top-3">
      <div className="flex min-w-max gap-1.5">
        {targets.map(({ key, label, icon: Icon, ref }) => (
          <button
            key={key} aria-current={active === key}
            className={`inline-flex items-center gap-2 rounded-full px-4 py-2 text-[13px] font-semibold transition-all duration-300 ${
              active === key ? "bg-fox-600 text-white shadow-glow" : "text-muted hover:bg-soft hover:text-ink"
            }`}
            onClick={() => ref.current?.scrollIntoView({ behavior: "smooth", block: "start" })}
          >
            <Icon size={14} /> {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function ProfileTiles({ profile }: { profile: Report["profile"] }) {
  const cap = (t: string) => t.charAt(0).toUpperCase() + t.slice(1);
  return (
    <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {/* skin type */}
      <Reveal index={0} className="h-full">
        <div className="card lift h-full p-5">
          <p className="label-caps">Skin type</p>
          <p className="mt-2 text-2xl font-extrabold text-ink">{cap(profile.skinType)}</p>
          <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{profile.skinTypeReason}</p>
        </div>
      </Reveal>
      {/* skin tone */}
      <Reveal index={1} className="h-full">
        <div className="card lift h-full p-5">
          <p className="label-caps">Skin tone</p>
          {profile.tone ? (
            <>
              <div className="mt-2 flex items-center gap-3">
                <span className="pop h-11 w-11 shrink-0 rounded-full border-2 border-card shadow-card ring-1 ring-line" style={{ background: profile.tone.swatch }} aria-label={`Measured skin colour ${profile.tone.swatch}`} />
                <div>
                  <p className="text-2xl font-extrabold leading-tight text-ink">{profile.tone.label}</p>
                  <p className="text-xs font-semibold text-muted">{cap(profile.tone.undertone)} undertone</p>
                </div>
              </div>
              {profile.tone.note && <p className="mt-2 text-[12px] leading-relaxed text-muted">{profile.tone.note}</p>}
            </>
          ) : <p className="mt-2 text-sm text-muted">Not measured for this scan.</p>}
        </div>
      </Reveal>
      {/* spots */}
      <Reveal index={2} className="h-full">
        <div className="card lift h-full p-5">
          <p className="label-caps">Acne &amp; pimples</p>
          <div className="mt-2 flex items-end gap-2">
            <p className="text-3xl font-extrabold leading-none text-ink"><CountUp value={profile.spots.total} /></p>
            <span className="pb-0.5 text-sm text-muted">spotted</span>
            <LevelPill level={profile.spots.level} className="ml-auto" />
          </div>
          <div className="mt-3 flex flex-wrap gap-2 text-xs font-bold">
            <span className="pill bg-rose-50 text-rose-700 dark:bg-rose-500/15 dark:text-rose-300">{profile.spots.pimples} pimple-like</span>
            <span className="pill bg-amber-50 text-amber-800 dark:bg-amber-500/15 dark:text-amber-200">{profile.spots.marks} flat marks</span>
          </div>
          <p className="mt-2 text-[12px] text-muted">Pimple-like spots are small, strongly red and look inflamed. Marks are flatter and paler.</p>
        </div>
      </Reveal>
      {/* texture + evenness */}
      <Reveal index={3} className="h-full">
        <div className="card lift h-full p-5">
          <p className="label-caps">Texture &amp; evenness</p>
          <div className="mt-3 space-y-2.5 text-sm">
            <div className="flex items-center justify-between"><span className="font-bold text-ink">Skin texture</span><LevelPill level={profile.texture.level} /></div>
            {profile.toneEvenness.level && (
              <div className="flex items-center justify-between"><span className="font-bold text-ink">Tone evenness</span><LevelPill level={profile.toneEvenness.level} /></div>
            )}
          </div>
          <p className="mt-3 text-[12px] text-muted">Texture is how rough the surface looks at pore scale; evenness is how much colour and brightness vary.</p>
        </div>
      </Reveal>
    </div>
  );
}

const FINDING_GROUP: Record<string, string> = {
  acne: "acne", dark_spots: "dark", under_eye: "eye", fine_lines: "lines", sun_spots: "dark", scars: "dark",
  redness: "redness", texture: "texture", dryness: "dryness", oiliness: "oiliness", uniformity: "tone",
};

function FindingRow({ f, index, onOpen }: { f: Finding; index: number; onOpen: (key: string) => void }) {
  const clickable = !!FINDING_GROUP[f.key] && f.measured;
  const pct = f.key === "uniformity" || f.key === "symmetry" ? Number(f.headline.match(/(\d+)%/)?.[1] ?? NaN) : NaN;
  return (
    <Reveal index={index} className="h-full">
      <button
        type="button" disabled={!clickable} onClick={() => onOpen(f.key)}
        className={`card lift flex h-full w-full items-start gap-3 p-4 text-left ${clickable ? "cursor-pointer hover:border-fox-300" : "cursor-default"} ${f.measured ? "" : "opacity-70"}`}
        aria-label={clickable ? `${f.headline}. Show on photo` : f.headline}
      >
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-soft text-xl" aria-hidden>{f.icon}</span>
        <span className="min-w-0 flex-1">
          <span className="flex flex-wrap items-center justify-between gap-2">
            <span className="text-[14px] font-extrabold leading-snug text-ink">{f.headline}</span>
            {f.level && <LevelPill level={f.level} />}
          </span>
          {!Number.isNaN(pct) && <span className="mt-2 block"><ScoreBar score={pct} /></span>}
          <span className="mt-1.5 block text-[12px] leading-relaxed text-muted">{f.note}</span>
          {clickable && f.level && f.level !== "minimal" && <span className="mt-1.5 block text-[11.5px] font-bold text-fox-text dark:text-fox-300">Show on photo →</span>}
        </span>
      </button>
    </Reveal>
  );
}

function DetailedFindings({ findings, onOpen }: { findings: Finding[]; onOpen: (key: string) => void }) {
  return (
    <div>
      <SectionTitle title="Detailed Findings" subtitle="What the camera looked for, how much it found, and where. Tap a card to see it on your photo." icon={<ScanSearch size={18} />} />
      <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {findings.map((f, i) => <FindingRow key={f.key} f={f} index={i} onOpen={onOpen} />)}
      </div>
      <p className="mt-4 text-[11.5px] leading-relaxed text-muted">
        These are estimates from one photo using computer vision, not a clinical assessment. Lighting, makeup, hair, glasses and head angle
        change them, and things like scarring depth or puffiness need more than a flat photo to judge.
      </p>
    </div>
  );
}

function AnalysisSkeleton() {
  return (
    <div className="space-y-5" aria-busy="true" aria-label="Loading your analysis">
      <Skeleton className="h-10 w-72" />
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {[0, 1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-36" />)}
      </div>
      <Skeleton className="h-72" />
      <Skeleton className="h-96" />
    </div>
  );
}

export default function Analysis() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { current, setCurrent, settings, updateSettings, toast, bumpData, dataVersion } = useApp();

  const [scan, setScan] = useState<Scan | null>(null);
  const [saved, setSaved] = useState<Scan[]>([]);
  const [loading, setLoading] = useState(true);
  const [report, setReport] = useState<Report | null>(null);
  const [insights, setInsights] = useState<Insights | null>(null);
  const [selected, setSelected] = useState<RegionObservation | null>(null);
  const [photoGroup, setPhotoGroup] = useState<string>("all");
  const findingsRef = useRef<HTMLElement | null>(null);
  const [note, setNote] = useState("");
  const [options, setOptions] = useState<{ routine: string[]; environment: string[] }>({ routine: [], environment: [] });
  const [pdfBusy, setPdfBusy] = useState(false);
  const starKey = usePulseKey(scan?.starred);

  const reportRef = useRef<HTMLElement | null>(null);
  const skincareRef = useRef<HTMLElement | null>(null);
  const photoRef = useRef<HTMLElement | null>(null);
  const notesRef = useRef<HTMLElement | null>(null);
  const tipsRef = useRef<HTMLElement | null>(null);

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
    getInsights().then(setInsights).catch(() => undefined);
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
    },
    [owned, updateSettings]
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
    { key: "skincare", label: "Skincare", icon: Sparkles, ref: skincareRef },
    { key: "photo", label: "Photo & regions", icon: Camera, ref: photoRef },
    { key: "notes", label: "Notes & journal", icon: NotebookPen, ref: notesRef },
    { key: "tips", label: "Tips", icon: Lightbulb, ref: tipsRef },
  ];
  const a = scan.analysis;
  const baseline = insights?.baseline ?? {};
  const cardData = CARD_KEYS.map((label) => ({ label, row: report?.categories.find((c) => c.key === label) }));
  const detail = selected
    ? `${selected.region.toLowerCase().replace(/\b\w/g, (c) => c.toUpperCase())} · ${selected.observation} (${Math.round(selected.confidence * 100)}% confidence)`
    : "Click a marker on the photo to see details.";
  const startOfList = index >= 0 && index + 1 >= saved.length;
  const endOfList = index <= 0;

  return (
    <div className="animate-fade-up">
      <PageHeader
        title="Your Skin Analysis"
        subtitle={`AI-powered visual skin observations  ·  ${formatDate(scan.timestamp)}`}
        actions={
          <>
            <button className="btn-soft" disabled={index < 0 || startOfList} onClick={() => navigate(`/analysis/${saved[index + 1].id}`)}>
              <ChevronLeft size={16} /> Previous
            </button>
            <button className="btn-soft" disabled={index < 0 || endOfList} onClick={() => navigate(`/analysis/${saved[index - 1].id}`)}>
              Next <ChevronRight size={16} />
            </button>
            <button className="btn-soft" disabled={!scan.persisted} onClick={() => update({ starred: !scan.starred })} aria-pressed={scan.starred} title={scan.persisted ? "" : "Turn on Save scan history to star scans"}>
              <Star key={starKey} size={16} className={`${starKey ? "star-burst" : ""} ${scan.starred ? "fill-amber-400 text-amber-400" : ""}`} /> {scan.starred ? "Starred" : "Star"}
            </button>
            <button className="btn-cta !py-2.5 text-sm" onClick={exportPdf} disabled={pdfBusy}>
              <Download size={16} /> {pdfBusy ? "Building..." : "Save Report (PDF)"}
            </button>
          </>
        }
      />

      <DeliveryStatus key={scan.id} scanId={scan.id} />

      <SectionNav targets={navTargets} />
      <Disclaimer />

      {!scan.persisted && (
        <p className="mt-4 flex items-start gap-2 rounded-2xl bg-soft p-3 text-sm text-muted">
          <Info size={16} className="mt-0.5 shrink-0" /> This scan is not saved. Turn on "Save scan history" in Privacy to keep scans, add notes and compare over time.
        </p>
      )}

      {/* category cards */}
      <div className="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        {cardData.map(({ label, row }, ci) => {
          const usual = baseline[label];
          const cmp = row && usual ? LEVEL_SCORE[row.level] - LEVEL_SCORE[usual as keyof typeof LEVEL_SCORE] : 0;
          return (
            <Reveal key={label} index={ci}>
            <div className="card lift h-full p-4">
              <p className="text-[13px] font-extrabold uppercase tracking-wide text-ink">{label}</p>
              {row ? (
                <>
                  <LevelPill level={row.level} className="mt-2" />
                  <p className="mt-2 text-sm text-muted">
                    {row.key === "Acne-like spots" ? `${a.acne_like_spots.count ?? 0} area(s) flagged` : row.key === "Texture" ? "Facial areas assessed" : `${scan.regions.filter((r) => r.category === row.key).length} area(s) found`}
                  </p>
                  <p className="mt-1 text-xs text-muted">{Math.round(row.confidence * 100)}% confidence</p>
                  {usual && insights && insights.totalScans > 1 && (
                    <p className={`mt-1 text-xs font-bold ${cmp > 0 ? "text-amber-600" : cmp < 0 ? "text-emerald-600" : "text-blue-500"}`}>
                      {cmp > 0 ? "Higher than your usual" : cmp < 0 ? "Lower than your usual" : "About your usual"}
                    </p>
                  )}
                </>
              ) : (
                <Skeleton className="mt-3 h-16" />
              )}
            </div>
            </Reveal>
          );
        })}
        <Reveal index={4} className="h-full">
        <div className="card lift h-full p-4">
          <p className="text-[13px] font-extrabold uppercase tracking-wide text-ink">Scan quality</p>
          {scan.quality ? (
            <>
              <p className="mt-1 text-3xl font-extrabold" style={{ color: scoreColor(scan.quality.overall) }}>
                {scan.quality.overall}<span className="text-xs font-semibold text-muted"> / 100</span>
              </p>
              <dl className="mt-1 space-y-0.5 text-xs">
                {([["Position", scan.quality.position_score], ["Lighting", scan.quality.lighting_score], ["Distance", scan.quality.distance_score], ["Sharpness", scan.quality.sharpness_score], ["Angle", scan.quality.angle_score]] as const).map(([k, v]) => (
                  <div key={k} className="flex justify-between"><dt className="uppercase text-muted">{k}</dt><dd className="font-bold" style={{ color: scoreColor(v) }}>{v}</dd></div>
                ))}
              </dl>
            </>
          ) : <p className="mt-2 text-sm text-muted">Not recorded for this scan.</p>}
        </div>
        </Reveal>
      </div>

      {report && <ProfileTiles profile={report.profile} />}

      <Reveal as="section" innerRef={findingsRef} className="card mt-6 scroll-mt-24 p-5 sm:p-6">
        {report ? (
          <DetailedFindings
            findings={report.findings}
            onOpen={(key) => {
              setPhotoGroup(FINDING_GROUP[key] ?? "all");
              setSelected(null);
              setTimeout(() => photoRef.current?.scrollIntoView({ behavior: "smooth", block: "start" }), 60);
            }}
          />
        ) : <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{[0, 1, 2, 3, 4, 5].map((i) => <Skeleton key={i} className="h-28" />)}</div>}
      </Reveal>

      {/* Skin health report */}
      <Reveal as="section" innerRef={reportRef} className="card mt-6 scroll-mt-24 p-5 sm:p-6">
        <SectionTitle title="Skin Health Report" subtitle="Measured from the visible skin in your photo. Not a medical diagnosis." icon={<ClipboardCheck size={18} />} />
        {report ? (
          <>
            <div className="mt-5 flex flex-wrap items-start gap-6">
              <ScoreRing score={report.overallScore} />
              <div className="min-w-[240px] flex-1">
                {report.overallScore != null ? (
                  <p className="text-xl font-extrabold" style={{ color: scoreColor(report.overallScore) }}>{report.scoreLabel}</p>
                ) : (
                  <p className="text-lg font-extrabold text-ink">Detailed report unavailable</p>
                )}
                <p className="mt-1 text-sm leading-relaxed text-ink">{report.summary}</p>
                {report.changes.slice(0, 3).map((c) => <p key={c} className="mt-1.5 text-xs text-muted">{c}</p>)}
              </div>
              <div className="w-full sm:w-[330px]">
                <p className="label-caps mb-2">Region scores</p>
                {report.regionScores.length === 0 && <p className="text-sm text-muted">Region scores appear on new scans.</p>}
                <ul className="space-y-2.5">
                  {report.regionScores.map((r) => (
                    <li key={r.name}>
                      <div className="flex items-baseline justify-between text-[12.5px]">
                        <span className="font-bold text-ink">{r.name} <span className="text-[10.5px] font-normal text-muted">{r.concern}</span></span>
                        <span className="font-extrabold text-ink">{r.score}</span>
                      </div>
                      <ScoreBar score={r.score} />
                    </li>
                  ))}
                </ul>
              </div>
            </div>
            <div className="mt-5 divide-y divide-line border-t border-line">
              {report.categories.map((c) => (
                <div key={c.key} className="grid grid-cols-[150px_100px_1fr] items-center gap-3 py-2.5 text-sm sm:grid-cols-[170px_100px_1fr_auto]" title={c.meaning}>
                  <span className="font-bold text-ink">{c.label}</span>
                  <LevelPill level={c.level} className="justify-center" />
                  <span className="text-muted">{c.measurement}</span>
                  <span className="hidden text-xs text-muted sm:block">{Math.round(c.confidence * 100)}% confidence</span>
                </div>
              ))}
            </div>
          </>
        ) : <div className="mt-5 space-y-4" aria-busy="true"><Skeleton className="h-36" /><Skeleton className="h-40" /></div>}
      </Reveal>

      {/* Skincare */}
      <Reveal as="section" innerRef={skincareRef} className="card mt-6 scroll-mt-24 p-5 sm:p-6">
        <SectionTitle title="Recommended Skincare" subtitle="A simple Foxtale routine matched to what your scan measured, and why each step should help." icon={<Sparkles size={18} />} />
        <div className="mt-4">
          {report ? <Skincare skincare={report.skincare} onOwned={setOwned} wishlist={settings.wishlist ?? []} onWish={toggleWish} /> : <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4" aria-busy="true">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-72" />)}</div>}
        </div>
      </Reveal>

      {/* Photo + regions */}
      <Reveal as="section" innerRef={photoRef} className="mt-6 grid scroll-mt-24 gap-5 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="card p-5"><PhotoPanel image={image} regions={scan.regions} selected={selected} onSelect={setSelected} group={photoGroup} onGroupChange={setPhotoGroup} /></div>
        <div className="space-y-5">
          <div className="card p-5">
            <SectionTitle title="Visible Observation" subtitle={detail} icon={<Eye size={18} />} />
            {selected && <p className="mt-3 text-xs text-muted">A visual observation, not a medical diagnosis.</p>}
          </div>
          <div className="card p-5">
            <SectionTitle title="Region Breakdown" subtitle="Detailed breakdown of different facial regions." icon={<LayoutGrid size={18} />} />
            <div className="mt-4"><RegionDonut regions={scan.regions} /></div>
          </div>
        </div>
      </Reveal>

      {/* Notes + journal */}
      <Reveal as="section" innerRef={notesRef} className="card mt-6 scroll-mt-24 p-5 sm:p-6">
        <SectionTitle title="Notes" icon={<FileText size={18} />} />
        <div className="mt-3 flex gap-2">
          <input
            className="input" value={note} disabled={!scan.persisted} maxLength={2000}
            placeholder="Add a personal note (e.g. new product, routine change, skin concerns)..."
            onChange={(e) => setNote(e.target.value)} onKeyDown={(e) => e.key === "Enter" && update({ note })}
          />
          <button className="btn-soft" disabled={!scan.persisted || note === scan.note} onClick={() => update({ note })}>Save note</button>
        </div>
        {!scan.persisted && <p className="mt-2 text-xs text-muted">Notes and the journal are available for saved scans.</p>}

        <div className="mt-6 flex items-center gap-3">
          <IconBadge><NotebookPen size={18} /></IconBadge>
          <div>
            <h3 className="text-[15px] font-extrabold text-ink">Scan journal</h3>
            <p className="text-sm text-muted">Track your skincare routine and habits for better insights.</p>
          </div>
        </div>
        {(["routine", "environment"] as const).map((kind) => (
          <div key={kind} className="mt-4">
            <p className="label-caps mb-2">{kind === "routine" ? "Routine" : "Environment"}</p>
            <div className="flex flex-wrap gap-2">
              {options[kind].map((o) => (
                <button key={o} disabled={!scan.persisted} aria-pressed={scan.journal[kind].includes(o)}
                  className={`chip ${scan.journal[kind].includes(o) ? "chip-on" : ""}`} onClick={() => toggleJournal(kind, o)}>
                  {scan.journal[kind].includes(o) ? "✓" : <Plus size={13} />} {o}
                </button>
              ))}
            </div>
          </div>
        ))}
      </Reveal>

      {/* Tips */}
      <Reveal as="section" innerRef={tipsRef} className="card mt-6 scroll-mt-24 p-5 sm:p-6">
        <SectionTitle title="Recommendations" icon={<Lightbulb size={18} />} />
        <ul className="mt-3 space-y-2">
          {(report?.recommendations ?? []).map((t) => (
            <li key={t} className="flex gap-2.5 text-sm text-ink"><span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-fox-500" />{t}</li>
          ))}
        </ul>
        {report && (
          <details className="mt-5 rounded-2xl bg-soft p-4 text-sm">
            <summary className="cursor-pointer font-bold text-ink">How this was measured</summary>
            <ul className="mt-3 space-y-2 text-muted">
              {report.methodology.steps.map((s) => <li key={s.title}><b className="text-ink">{s.title}:</b> {s.body}</li>)}
            </ul>
            <p className="mt-3 text-muted">{report.methodology.scoreExplanation}</p>
            <p className="mt-2 text-muted">{report.methodology.limitations}</p>
          </details>
        )}
      </Reveal>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <p className="flex items-center gap-2 text-sm text-muted"><Lock size={14} /> Your face image is processed only for this analysis.</p>
        <div className="flex gap-2">
          <button className="btn-danger" onClick={remove}><Trash2 size={16} /> Delete Scan</button>
          <Link to="/scan" state={{ autostart: true }} className="btn-cta !py-2.5 text-sm"><Camera size={16} /> New Scan</Link>
        </div>
      </div>
    </div>
  );
}
