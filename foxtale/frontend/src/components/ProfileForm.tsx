import { useState } from "react";
import { Check, Loader2 } from "lucide-react";
import type { Profile } from "../services/api";

export const GOALS: { key: string; label: string; emoji: string }[] = [
  { key: "acne", label: "Clear acne", emoji: "🔴" },
  { key: "dark_spots", label: "Fade dark spots", emoji: "🟤" },
  { key: "anti_aging", label: "Fine lines", emoji: "😌" },
  { key: "hydration", label: "Hydration", emoji: "💧" },
  { key: "oil_control", label: "Oil control", emoji: "✨" },
  { key: "redness", label: "Calm redness", emoji: "🌸" },
  { key: "texture", label: "Smoother texture", emoji: "🧱" },
  { key: "under_eye", label: "Under-eye care", emoji: "👁️" },
  { key: "brightening", label: "Brighter skin", emoji: "☀️" },
];

const AGES = ["Under 18", "18-24", "25-34", "35-44", "45+"];
const BUDGETS: { key: Profile["budget"]; label: string }[] = [
  { key: "any", label: "No limit" },
  { key: "mid", label: "Up to ₹600 each" },
  { key: "low", label: "Up to ₹400 each" },
];

export const EMPTY_PROFILE: Profile = {
  name: "", age_range: "", gender: "", goals: [], sensitive_skin: false, pregnant: false, allergies: "", budget: "any", onboarded: true,
};

function Toggle({ on, onChange, label, hint }: { on: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <button
      type="button" role="switch" aria-checked={on} onClick={() => onChange(!on)}
      className={`flex w-full items-center justify-between gap-4 rounded-2xl border p-4 text-left transition ${on ? "border-fox-500 bg-fox-50 dark:bg-fox-500/10" : "border-line bg-card hover:border-fox-300"}`}
    >
      <span>
        <span className="block text-sm font-bold text-ink">{label}</span>
        <span className="block text-xs text-muted">{hint}</span>
      </span>
      <span className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${on ? "pop border-fox-500 bg-fox-500 text-white" : "border-line"}`}>
        {on && <Check size={14} />}
      </span>
    </button>
  );
}

export default function ProfileForm({
  initial, onSubmit, submitLabel, busy,
}: { initial?: Partial<Profile> | null; onSubmit: (p: Profile) => void; submitLabel: string; busy?: boolean }) {
  const [p, setP] = useState<Profile>({ ...EMPTY_PROFILE, ...(initial ?? {}), onboarded: true });
  const set = <K extends keyof Profile>(k: K, v: Profile[K]) => setP((prev) => ({ ...prev, [k]: v }));
  const toggleGoal = (g: string) => set("goals", p.goals.includes(g) ? p.goals.filter((x) => x !== g) : [...p.goals, g]);

  return (
    <form className="space-y-7" onSubmit={(e) => { e.preventDefault(); onSubmit(p); }}>
      <div>
        <label className="label-caps" htmlFor="pf-name">What should we call you? (optional)</label>
        <input id="pf-name" className="input mt-2" maxLength={60} placeholder="Your first name" value={p.name} onChange={(e) => set("name", e.target.value)} />
      </div>

      <div>
        <p className="label-caps">Age range</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {AGES.map((a) => (
            <button key={a} type="button" aria-pressed={p.age_range === a} className={`chip ${p.age_range === a ? "chip-on" : ""}`} onClick={() => set("age_range", p.age_range === a ? "" : a)}>{a}</button>
          ))}
        </div>
      </div>

      <div>
        <p className="label-caps">What would you like to improve? (pick any)</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {GOALS.map((g) => (
            <button key={g.key} type="button" aria-pressed={p.goals.includes(g.key)} className={`chip ${p.goals.includes(g.key) ? "chip-on" : ""}`} onClick={() => toggleGoal(g.key)}>
              <span aria-hidden>{g.emoji}</span> {g.label}
            </button>
          ))}
        </div>
      </div>

      <div className="space-y-3">
        <p className="label-caps">Safety, so we do not suggest the wrong thing</p>
        <Toggle on={p.sensitive_skin} onChange={(v) => set("sensitive_skin", v)} label="My skin is sensitive or reactive" hint="We leave out strong actives like exfoliating acids, retinol and vitamin C." />
        <Toggle on={p.pregnant} onChange={(v) => set("pregnant", v)} label="I am pregnant or breastfeeding" hint="We leave out retinol and exfoliating acids. Please also ask your doctor." />
        <div>
          <label className="text-sm font-bold text-ink" htmlFor="pf-allergy">Allergies or ingredients to avoid</label>
          <input id="pf-allergy" className="input mt-2" maxLength={200} placeholder="e.g. niacinamide, salicylic acid" value={p.allergies} onChange={(e) => set("allergies", e.target.value)} />
          <p className="mt-1 text-xs text-muted">Separate with commas. Products containing them are left out.</p>
        </div>
      </div>

      <div>
        <p className="label-caps">Budget per product</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {BUDGETS.map((b) => (
            <button key={b.key} type="button" aria-pressed={p.budget === b.key} className={`chip ${p.budget === b.key ? "chip-on" : ""}`} onClick={() => set("budget", b.key)}>{b.label}</button>
          ))}
        </div>
      </div>

      <button className="btn-cta w-full sm:w-auto" type="submit" disabled={busy}>
        {busy ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />} {submitLabel}
      </button>
    </form>
  );
}
