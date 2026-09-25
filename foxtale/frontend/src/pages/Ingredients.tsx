import { useState } from "react";
import { Link } from "react-router-dom";
import { CheckCircle2, FlaskConical, Loader2, ShieldAlert, ShieldCheck, ShieldQuestion, Sparkles } from "lucide-react";
import { PageHeader, SectionTitle } from "../components/ui";
import { useApp } from "../context/AppContext";
import { checkIngredients, ApiError } from "../services/api";
import type { IngredientResult } from "../services/api";
import { Reveal } from "../lib/motion";

const EXAMPLE = "Aqua, Glycerin, Niacinamide, Retinol, Parfum, Alcohol Denat., Cocos Nucifera (Coconut) Oil, Sodium Hyaluronate, Limonene, Tocopherol, Panthenol";

const VERDICT = {
  good: { icon: ShieldCheck, box: "border-emerald-300 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-500/10", tone: "text-emerald-600", title: "Looks good for you" },
  caution: { icon: ShieldQuestion, box: "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10", tone: "text-amber-600", title: "Use with care" },
  avoid: { icon: ShieldAlert, box: "border-rose-300 bg-rose-50 dark:border-rose-500/40 dark:bg-rose-500/10", tone: "text-rose-600", title: "Not a good fit" },
} as const;

const SEV = { avoid: "bg-rose-100 text-rose-700 dark:bg-rose-500/20 dark:text-rose-300", caution: "bg-amber-100 text-amber-800 dark:bg-amber-500/20 dark:text-amber-200", info: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300" } as const;

export default function Ingredients() {
  const { profile, toast } = useApp();
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<IngredientResult | null>(null);

  const run = async () => {
    setBusy(true);
    try {
      setResult(await checkIngredients(text));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not check that list");
    } finally {
      setBusy(false);
    }
  };

  const v = result?.ok && result.verdict ? VERDICT[result.verdict] : null;
  const VIcon = v?.icon;

  return (
    <div>
      <PageHeader title="Ingredient Check" subtitle="Paste a product's ingredient list and see how it fits your skin, your profile and what you already use." />

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="card p-5 sm:p-6">
          <SectionTitle title="Ingredient list" subtitle="Copy it from the back of the pack or the product page, separated by commas." icon={<FlaskConical size={18} />} />
          <textarea
            className="input mt-4 min-h-[190px] resize-y font-mono text-[13px]" value={text} onChange={(e) => setText(e.target.value)}
            placeholder="Aqua, Glycerin, Niacinamide, ..." aria-label="Ingredient list"
          />
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-cta" onClick={run} disabled={busy || text.trim().length < 5}>
              {busy ? <Loader2 size={18} className="animate-spin" /> : <Sparkles size={18} />} Check ingredients
            </button>
            <button className="btn-soft" onClick={() => setText(EXAMPLE)}>Try an example</button>
          </div>
          <p className="mt-4 text-xs text-muted">
            {profile?.onboarded
              ? "Checked against your profile answers (pregnancy, sensitivity, allergies, goals) and your latest scan."
              : <>Answer the <Link to="/settings" className="font-bold text-fox-text underline dark:text-fox-300">profile questions</Link> for a check that fits you.</>}
          </p>
        </div>

        <div>
          {!result && (
            <div className="card flex h-full min-h-[260px] flex-col items-center justify-center p-8 text-center">
              <span className="pop float mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-fox-50 text-fox-500 dark:bg-fox-500/15"><FlaskConical size={24} /></span>
              <p className="font-extrabold text-ink">Your result appears here</p>
              <p className="mt-1 max-w-xs text-sm text-muted">We flag allergens, ingredients to avoid in pregnancy, irritants for sensitive skin, pore-cloggers for acne-prone skin, and clashes with your routine.</p>
            </div>
          )}

          {result && !result.ok && <p className="card page-enter p-5 text-sm font-semibold text-rose-600" role="alert">{result.message}</p>}

          {result?.ok && v && VIcon && (
            <div className="space-y-4">
              <div className={`page-enter rounded-[20px] border p-5 ${v.box}`} role="status">
                <p className="flex items-center gap-3 text-lg font-extrabold text-ink"><VIcon size={26} className={v.tone} /> {v.title}</p>
                <p className="mt-2 text-sm text-ink">{result.summary}</p>
                <p className="mt-2 text-xs text-muted">{result.counts?.recognised} of {result.counts?.ingredients} ingredients recognised.</p>
              </div>

              {(result.conflicts?.length ?? 0) > 0 && (
                <Reveal>
                  <div className="card p-5">
                    <p className="label-caps mb-2">Clashes with what you already use</p>
                    <ul className="space-y-2.5">
                      {result.conflicts!.map((c) => (
                        <li key={c.with + c.detail} className="rounded-xl bg-soft p-3 text-sm"><b className="text-ink">{c.with}</b><span className="mt-0.5 block text-muted">{c.detail}</span></li>
                      ))}
                    </ul>
                  </div>
                </Reveal>
              )}

              {(result.findings?.length ?? 0) > 0 && (
                <Reveal index={1}>
                  <div className="card p-5">
                    <p className="label-caps mb-2">What we found</p>
                    <ul className="space-y-3">
                      {result.findings!.map((f) => (
                        <li key={f.label + f.ingredient + f.severity} className="flex gap-3 text-sm">
                          <span className={`pill h-fit shrink-0 ${SEV[f.severity]}`}>{f.severity === "avoid" ? "Avoid" : f.severity === "caution" ? "Careful" : "Note"}</span>
                          <span><b className="text-ink">{f.label}</b> <span className="text-muted">({f.ingredient})</span><span className="mt-0.5 block text-muted">{f.why}</span></span>
                        </li>
                      ))}
                    </ul>
                  </div>
                </Reveal>
              )}

              {(result.positives?.length ?? 0) > 0 && (
                <Reveal index={2}>
                  <div className="card p-5">
                    <p className="label-caps mb-2">Helpful ingredients</p>
                    <ul className="space-y-2">
                      {result.positives!.map((p) => <li key={p} className="flex gap-2 text-sm text-ink"><CheckCircle2 size={16} className="mt-0.5 shrink-0 text-emerald-500" /> {p}</li>)}
                    </ul>
                  </div>
                </Reveal>
              )}
              <p className="text-[11.5px] leading-relaxed text-muted">{result.note}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
