import { useCallback, useEffect, useMemo, useState } from "react";
import { ChevronLeft, ChevronRight, Check, Flame, Loader2, Minus, NotebookPen, Plus, TrendingDown, TrendingUp } from "lucide-react";
import { PageHeader, SectionTitle } from "../components/ui";
import { useApp } from "../context/AppContext";
import { getDiary, getDiaryPatterns, saveDiary, ApiError } from "../services/api";
import type { DiaryEntry, DiaryPatterns } from "../services/api";
import { Reveal, Skeleton } from "../lib/motion";

const FEELS = [["😣", "Bad"], ["😕", "Meh"], ["😐", "Okay"], ["🙂", "Good"], ["😄", "Great"]];
const STRESS = [["😌", "Calm"], ["🙂", "Low"], ["😐", "Medium"], ["😟", "High"], ["😫", "Very high"]];
const FEEL_BG = ["", "bg-rose-400", "bg-orange-300", "bg-amber-300", "bg-lime-400", "bg-emerald-500"];

const iso = (d: Date) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
const addDays = (day: string, n: number) => { const d = new Date(day + "T12:00:00"); d.setDate(d.getDate() + n); return iso(d); };
const pretty = (day: string) => new Date(day + "T12:00:00").toLocaleDateString(undefined, { weekday: "long", month: "short", day: "numeric" });

function Stepper({ label, value, unit, step, min, max, start, onChange }: { label: string; value: number | undefined; unit: string; step: number; min: number; max: number; start: number; onChange: (v: number) => void }) {
  const v = value ?? 0;
  return (
    <div>
      <p className="label-caps">{label}</p>
      <div className="mt-2 flex items-center gap-3">
        <button type="button" className="chip !h-10 !w-10 justify-center !p-0" aria-label={`Less ${label}`} onClick={() => onChange(value === undefined ? start : Math.max(min, v - step))}><Minus size={16} /></button>
        <span className="min-w-[80px] text-center text-2xl font-extrabold text-ink">{value === undefined ? "--" : value}<span className="ml-1 text-xs font-semibold text-muted">{unit}</span></span>
        <button type="button" className="chip !h-10 !w-10 justify-center !p-0" aria-label={`More ${label}`} onClick={() => onChange(value === undefined ? start : Math.min(max, v + step))}><Plus size={16} /></button>
      </div>
    </div>
  );
}

export default function Diary() {
  const { toast } = useApp();
  const today = iso(new Date());
  const [day, setDay] = useState(today);
  const [entries, setEntries] = useState<Record<string, DiaryEntry>>({});
  const [flagLabels, setFlagLabels] = useState<Record<string, string>>({});
  const [form, setForm] = useState<Omit<DiaryEntry, "day">>({ flags: [], note: "" });
  const [patterns, setPatterns] = useState<DiaryPatterns | null>(null);
  const [saving, setSaving] = useState(false);
  const [loaded, setLoaded] = useState(false);

  const load = useCallback(() => {
    getDiary(60).then((r) => { setEntries(Object.fromEntries(r.entries.map((e) => [e.day, e]))); setFlagLabels(r.flags); setLoaded(true); }).catch(() => setLoaded(true));
    getDiaryPatterns().then(setPatterns).catch(() => undefined);
  }, []);
  useEffect(load, [load]);

  // switch the form to the chosen day
  useEffect(() => {
    const e = entries[day];
    setForm(e ? { sleep_hours: e.sleep_hours, water_glasses: e.water_glasses, stress: e.stress, skin_feel: e.skin_feel, flags: e.flags ?? [], note: e.note ?? "" } : { flags: [], note: "" });
  }, [day, entries]);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(entries[day] ? { sleep_hours: entries[day].sleep_hours, water_glasses: entries[day].water_glasses, stress: entries[day].stress, skin_feel: entries[day].skin_feel, flags: entries[day].flags ?? [], note: entries[day].note ?? "" } : { flags: [], note: "" }), [form, entries, day]);

  const save = async () => {
    setSaving(true);
    try {
      const saved = await saveDiary(day, form);
      setEntries((prev) => ({ ...prev, [day]: saved }));
      toast("Diary saved");
      getDiaryPatterns().then(setPatterns).catch(() => undefined);
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not save your diary");
    } finally {
      setSaving(false);
    }
  };

  const toggleFlag = (f: string) => setForm((p) => ({ ...p, flags: p.flags.includes(f) ? p.flags.filter((x) => x !== f) : [...p.flags, f] }));
  const strip = Array.from({ length: 30 }, (_, i) => addDays(today, i - 29));

  return (
    <div>
      <PageHeader title="Skin Diary" subtitle="A minute a day: how your skin felt and what your day was like. After a couple of weeks, patterns start to show." />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
        <div className="space-y-6">
          <Reveal>
            <section className="card p-5 sm:p-6">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <SectionTitle title={day === today ? "Today" : pretty(day)} subtitle={day === today ? pretty(day) : undefined} icon={<NotebookPen size={18} />} />
                <div className="flex gap-2">
                  <button className="btn-soft !px-3" aria-label="Previous day" onClick={() => setDay(addDays(day, -1))}><ChevronLeft size={16} /></button>
                  <button className="btn-soft !px-3" aria-label="Next day" disabled={day >= today} onClick={() => setDay(addDays(day, 1))}><ChevronRight size={16} /></button>
                </div>
              </div>

              <div className="mt-6">
                <p className="label-caps">How does your skin feel?</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {FEELS.map(([e, l], i) => (
                    <button key={l} type="button" aria-pressed={form.skin_feel === i + 1} onClick={() => setForm((p) => ({ ...p, skin_feel: p.skin_feel === i + 1 ? undefined : i + 1 }))}
                      className={`chip flex-col !gap-0.5 !px-4 !py-2 ${form.skin_feel === i + 1 ? "chip-on" : ""}`}>
                      <span className={`text-2xl transition-transform ${form.skin_feel === i + 1 ? "scale-125" : ""}`}>{e}</span><span className="text-[11px]">{l}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-6 grid gap-6 sm:grid-cols-2">
                <Stepper label="Sleep last night" value={form.sleep_hours} unit="h" step={0.5} min={0} max={14} start={7} onChange={(v) => setForm((p) => ({ ...p, sleep_hours: v }))} />
                <Stepper label="Water" value={form.water_glasses} unit="glasses" step={1} min={0} max={30} start={6} onChange={(v) => setForm((p) => ({ ...p, water_glasses: v }))} />
              </div>

              <div className="mt-6">
                <p className="label-caps">Stress today</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {STRESS.map(([e, l], i) => (
                    <button key={l} type="button" aria-pressed={form.stress === i + 1} onClick={() => setForm((p) => ({ ...p, stress: p.stress === i + 1 ? undefined : i + 1 }))}
                      className={`chip flex-col !gap-0.5 !px-3 !py-2 ${form.stress === i + 1 ? "chip-on" : ""}`}><span className="text-xl">{e}</span><span className="text-[11px]">{l}</span></button>
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <p className="label-caps">What was in your day?</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {Object.entries(flagLabels).map(([k, label]) => (
                    <button key={k} type="button" aria-pressed={form.flags.includes(k)} className={`chip !py-1.5 text-[13px] ${form.flags.includes(k) ? "chip-on" : ""}`} onClick={() => toggleFlag(k)}>
                      {form.flags.includes(k) && <Check size={13} />} {label.charAt(0).toUpperCase() + label.slice(1)}
                    </button>
                  ))}
                </div>
              </div>

              <div className="mt-6">
                <label className="label-caps" htmlFor="diary-note">Note (optional)</label>
                <textarea id="diary-note" className="input mt-2 min-h-[70px] resize-y" maxLength={500} placeholder="New product, breakout, anything worth remembering..." value={form.note} onChange={(e) => setForm((p) => ({ ...p, note: e.target.value }))} />
              </div>

              <button className="btn-cta mt-6" onClick={save} disabled={saving || !dirty}>{saving ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />} {entries[day] ? "Update entry" : "Save entry"}</button>
            </section>
          </Reveal>
        </div>

        <div className="space-y-6">
          <Reveal index={1}>
            <section className="card p-5 sm:p-6">
              <div className="flex items-center justify-between">
                <h2 className="text-[15px] font-extrabold text-ink">Last 30 days</h2>
                <span className="flex items-center gap-1.5 text-sm font-bold text-ink"><Flame size={16} className={patterns && patterns.streak > 0 ? "flicker text-fox-500" : "text-muted"} /> {patterns?.streak ?? 0} day streak</span>
              </div>
              {!loaded ? <Skeleton className="mt-4 h-24" /> : (
                <div className="mt-4 grid grid-cols-10 gap-1.5" role="group" aria-label="Skin feel by day">
                  {strip.map((d) => {
                    const e = entries[d];
                    return (
                      <button key={d} onClick={() => setDay(d)} title={`${pretty(d)}${e?.skin_feel ? `: ${FEELS[e.skin_feel - 1][1]}` : e ? ": logged" : ": nothing logged"}`}
                        aria-label={pretty(d)} className={`aspect-square rounded-lg transition active:scale-90 ${e?.skin_feel ? FEEL_BG[e.skin_feel] : e ? "bg-fox-300" : "bg-line"} ${d === day ? "ring-2 ring-fox-600 ring-offset-2 ring-offset-card" : ""}`} />
                    );
                  })}
                </div>
              )}
              <p className="mt-3 text-[11.5px] text-muted">Greener days are days your skin felt better. Tap a day to see or edit it.</p>
            </section>
          </Reveal>

          <Reveal index={2}>
            <section className="card p-5 sm:p-6">
              <SectionTitle title="What we noticed" subtitle="Patterns between your habits and how your skin felt." icon={<TrendingUp size={18} />} />
              {!patterns ? <Skeleton className="mt-4 h-28" /> : (
                <>
                  {patterns.message && <p className="mt-4 rounded-2xl bg-soft p-4 text-sm text-muted">{patterns.message}</p>}
                  <ul className="mt-4 space-y-3">
                    {[...patterns.insights, ...patterns.scanInsights].map((i) => (
                      <li key={i.factor} className="page-enter flex gap-3 rounded-2xl border border-line p-3.5">
                        <span className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-full ${i.direction === "worse" ? "bg-rose-50 text-rose-500 dark:bg-rose-500/15" : "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15"}`}>
                          {i.direction === "worse" ? <TrendingDown size={17} /> : <TrendingUp size={17} />}
                        </span>
                        <span className="text-[13px] leading-relaxed">
                          <b className="text-ink">{i.title}</b> <span className="pill bg-soft text-muted">{i.confidence === "medium" ? "Fairly consistent" : "Early sign"} · {i.n} days</span>
                          <span className="mt-0.5 block text-muted">{i.text}</span>
                        </span>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-4 text-[11.5px] leading-relaxed text-muted">{patterns.caveat} Logged {patterns.daysLogged} day{patterns.daysLogged === 1 ? "" : "s"}, {patterns.daysWithFeel} with a skin rating.</p>
                </>
              )}
            </section>
          </Reveal>
        </div>
      </div>
    </div>
  );
}
