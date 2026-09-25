import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Camera, Check, Flame, Moon, ShieldCheck, Sun } from "lucide-react";
import { useApp } from "../context/AppContext";
import { getReport, getRoutine, getRoutineCheck, listScans, productImageUrl, toggleRoutine } from "../services/api";
import type { RoutineCheck, RoutineState } from "../services/api";
import type { Report, Suggestion } from "../types/analysis";
import ConflictList from "../components/ConflictList";
import ProductResults from "../components/ProductResults";
import { EmptyState, PageHeader, SectionTitle } from "../components/ui";
import { CountUp, Reveal, Skeleton } from "../lib/motion";

function Slot({
  title, icon: Icon, slot, items, done, onToggle,
}: { title: string; icon: typeof Sun; slot: "AM" | "PM"; items: Suggestion[]; done: string[]; onToggle: (slot: "AM" | "PM", id: string, v: boolean) => void }) {
  const finished = items.length > 0 && items.every((s) => done.includes(s.id));
  return (
    <section className="card p-5 sm:p-6">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2.5 text-[15px] font-extrabold text-ink"><Icon size={18} className="text-fox-500" /> {title}</h2>
        <span className={`pill ${finished ? "pop lvl-minimal" : "bg-soft text-muted"}`}>{finished ? "All done" : `${done.filter((d) => items.some((s) => s.id === d)).length}/${items.length}`}</span>
      </div>
      <ul className="mt-4 space-y-2.5">
        {items.map((s) => {
          const on = done.includes(s.id);
          const src = productImageUrl(s.image);
          return (
            <li key={s.id}>
              <button
                onClick={() => onToggle(slot, s.id, !on)} aria-pressed={on}
                className={`flex w-full items-center gap-3 rounded-2xl border p-3 text-left transition active:scale-[0.99] ${on ? "border-emerald-400 bg-emerald-50 dark:border-emerald-500/50 dark:bg-emerald-500/10" : "border-line bg-card hover:border-fox-300"}`}
              >
                <span className="h-12 w-12 shrink-0 overflow-hidden rounded-xl bg-soft">{src && <img src={src} alt="" className="h-full w-full object-cover" />}</span>
                <span className="min-w-0 flex-1">
                  <span className="block text-[11px] font-extrabold uppercase tracking-widest text-fox-500">{s.stepLabel}</span>
                  <span className={`block truncate text-sm font-bold ${on ? "text-muted line-through" : "text-ink"}`}>{s.name}</span>
                </span>
                <span className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full border transition ${on ? "pop border-emerald-500 bg-emerald-500 text-white" : "border-line"}`}>{on && <Check size={15} />}</span>
              </button>
            </li>
          );
        })}
        {items.length === 0 && <li className="text-sm text-muted">Nothing for this part of the day.</li>}
      </ul>
    </section>
  );
}

export default function Routine() {
  const { dataVersion, toast } = useApp();
  const [report, setReport] = useState<Report | null | undefined>(undefined); // undefined = loading, null = no scans
  const [state, setState] = useState<RoutineState | null>(null);
  const [check, setCheck] = useState<RoutineCheck | null>(null);

  useEffect(() => {
    listScans()
      .then(async (all) => {
        if (all.length === 0) return setReport(null);
        setReport(await getReport({ analysis: all[0].analysis, regions: all[0].regions }));
      })
      .catch(() => setReport(null));
    getRoutine().then(setState).catch(() => undefined);
    getRoutineCheck().then(setCheck).catch(() => undefined);
  }, [dataVersion]);

  const suggestions = report?.skincare.suggestions ?? [];
  const am = useMemo(() => suggestions.filter((s) => s.when.includes("AM")), [suggestions]);
  const pm = useMemo(() => suggestions.filter((s) => s.when.includes("PM")), [suggestions]);

  const onToggle = useCallback(async (slot: "AM" | "PM", id: string, v: boolean) => {
    if (!state) return;
    setState({ ...state, today: { ...state.today, [slot]: v ? [...state.today[slot], id] : state.today[slot].filter((x) => x !== id) } });
    try {
      await toggleRoutine(state.todayDate, slot, id, v);
      setState(await getRoutine());
    } catch {
      toast("Could not save that. Is the server running?");
    }
  }, [state, toast]);

  if (report === undefined) return <div className="space-y-4"><Skeleton className="h-10 w-64" /><Skeleton className="h-28" /><div className="grid gap-4 md:grid-cols-2"><Skeleton className="h-72" /><Skeleton className="h-72" /></div></div>;
  if (report === null) {
    return (
      <EmptyState
        icon={<Flame size={28} />} title="Your routine starts with a scan"
        body="Scan your face and Foxtale builds a morning and evening routine for you, which you can tick off here every day."
        action={<Link to="/scan" state={{ autostart: true }} className="btn-cta"><Camera size={18} /> Start New Scan</Link>}
      />
    );
  }

  const total = am.length + pm.length;
  const doneToday = (state?.today.AM.length ?? 0) + (state?.today.PM.length ?? 0);
  const week = state?.history.slice(-14) ?? [];

  return (
    <div>
      <PageHeader title="My Routine" subtitle="Your morning and evening routine from your latest scan. Tick off each step as you do it." />

      <Reveal>
        <div className="card mb-6 grid gap-5 p-5 sm:grid-cols-[auto_1fr] sm:items-center sm:p-6">
          <div className="flex items-center gap-4">
            <span className="flex h-14 w-14 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15"><Flame size={26} className={state && state.streak > 0 ? "flicker" : ""} /></span>
            <div>
              <p className="text-3xl font-extrabold leading-none text-ink"><CountUp value={state?.streak ?? 0} /><span className="ml-1.5 text-base font-semibold text-muted">day streak</span></p>
              <p className="mt-1 text-sm text-muted">{doneToday}/{total} steps done today</p>
            </div>
          </div>
          <div>
            <p className="label-caps mb-2">Last 14 days</p>
            <div className="flex gap-1.5" role="img" aria-label="Routine completion for the last 14 days">
              {week.map((d) => {
                const n = d.am + d.pm;
                return <span key={d.day} title={`${d.day}: ${n} step${n === 1 ? "" : "s"}`} className={`h-7 flex-1 rounded-lg transition-colors ${n === 0 ? "bg-line" : n < 3 ? "bg-fox-300" : "bg-fox-600"}`} />;
              })}
            </div>
          </div>
        </div>
      </Reveal>

      <div className="grid gap-5 md:grid-cols-2">
        <Reveal index={1}><Slot title="Morning" icon={Sun} slot="AM" items={am} done={state?.today.AM ?? []} onToggle={onToggle} /></Reveal>
        <Reveal index={2}><Slot title="Evening" icon={Moon} slot="PM" items={pm} done={state?.today.PM ?? []} onToggle={onToggle} /></Reveal>
      </div>
      <Reveal as="section" index={3} className="card mt-6 p-5 sm:p-6">
        <SectionTitle title="Routine check" subtitle="Do the products you use clash with each other?" icon={<ShieldCheck size={18} />} />
        <div className="mt-4 space-y-4">
          {check && check.products.length > 0 ? (
            <div>
              <p className="label-caps mb-2">Your products ({check.products.length})</p>
              <ConflictList issues={check.issues} emptyText="No clashes found between the products you use." />
            </div>
          ) : (
            <p className="rounded-2xl bg-soft p-4 text-sm text-muted">Tap "I use this" on the products you already have (Analysis page) and we will check them for clashes.</p>
          )}
          {report.skincare.conflicts.length > 0 && (
            <div>
              <p className="label-caps mb-2">Your suggested routine</p>
              <ConflictList issues={report.skincare.conflicts} />
            </div>
          )}
        </div>
      </Reveal>

      <Reveal as="section" index={4} className="card mt-6 p-5 sm:p-6"><ProductResults /></Reveal>

      <p className="mt-5 text-xs text-muted">Routines come from your latest scan and your profile answers. Use sunscreen every morning, and add one new active product at a time.</p>
    </div>
  );
}
