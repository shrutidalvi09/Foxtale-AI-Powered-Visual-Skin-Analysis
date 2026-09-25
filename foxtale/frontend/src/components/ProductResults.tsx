import { useCallback, useEffect, useState } from "react";
import { ArrowDown, ArrowUp, Clock, Minus, TrendingUp } from "lucide-react";
import { useApp } from "../context/AppContext";
import { getEffects, productImageUrl, setProductStart } from "../services/api";
import type { ProductEffect } from "../services/api";
import { Reveal, Skeleton } from "../lib/motion";
import { SectionTitle } from "./ui";

const STATUS = {
  improving: { label: "Working", cls: "lvl-minimal" },
  steady: { label: "No clear change", cls: "bg-soft text-muted" },
  mixed: { label: "Mixed", cls: "lvl-mild" },
  worse: { label: "Looks worse", cls: "lvl-noticeable" },
  collecting: { label: "Collecting data", cls: "bg-blue-50 text-blue-700 dark:bg-blue-500/15 dark:text-blue-300" },
} as const;

function StartDate({ effect, onSaved }: { effect: ProductEffect; onSaved: () => void }) {
  const { toast } = useApp();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(effect.startedAt);
  const save = async () => {
    try {
      await setProductStart(effect.productId, value);
      setEditing(false);
      onSaved();
      toast("Start date updated");
    } catch {
      toast("Could not update that date");
    }
  };
  if (!editing) {
    return (
      <button className="text-xs font-semibold text-fox-text underline dark:text-fox-300" onClick={() => setEditing(true)}>
        Started {effect.startedAt} · change
      </button>
    );
  }
  return (
    <span className="flex items-center gap-2">
      <input type="date" className="input !w-auto !py-1 text-xs" value={value} max={new Date().toISOString().slice(0, 10)} onChange={(e) => setValue(e.target.value)} aria-label="Start date" />
      <button className="btn-soft !px-3 !py-1 text-xs" onClick={save}>Save</button>
    </span>
  );
}

/** "Is it working?": compares your scans from before and after you started each product. */
export default function ProductResults() {
  const { dataVersion } = useApp();
  const [items, setItems] = useState<ProductEffect[] | null>(null);
  const load = useCallback(() => {
    getEffects().then(setItems).catch(() => setItems([]));
  }, []);
  useEffect(load, [load, dataVersion]);

  return (
    <div>
      <SectionTitle
        title="Is it working?" icon={<TrendingUp size={18} />}
        subtitle="For each product you marked 'I use this', we compare your scans from before you started with your latest scans, on the things it is meant to help."
      />
      {items === null && <div className="mt-4 grid gap-4 md:grid-cols-2"><Skeleton className="h-40" /><Skeleton className="h-40" /></div>}
      {items && items.length === 0 && (
        <p className="mt-4 rounded-2xl bg-soft p-4 text-sm text-muted">
          Mark a product as "I use this" on the Analysis page and scan every week or two. After about two weeks we show whether it is helping.
        </p>
      )}
      <div className="mt-4 grid gap-4 md:grid-cols-2">
        {items?.map((e, i) => {
          const st = STATUS[e.status];
          const src = productImageUrl(e.image);
          return (
            <Reveal key={e.productId} index={i} className="h-full">
              <article className="card lift h-full p-4">
                <div className="flex items-start gap-3">
                  <span className="h-14 w-14 shrink-0 overflow-hidden rounded-xl bg-soft">{src && <img src={src} alt="" className="h-full w-full object-cover" loading="lazy" onError={(ev) => ((ev.target as HTMLImageElement).style.display = "none")} />}</span>
                  <div className="min-w-0 flex-1">
                    <p className="text-[13.5px] font-extrabold leading-snug text-ink">{e.name}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-2"><span className={`pill ${st.cls}`}>{st.label}</span><span className="flex items-center gap-1 text-xs text-muted"><Clock size={12} /> {e.days} day{e.days === 1 ? "" : "s"}</span></div>
                  </div>
                </div>
                <p className="mt-3 text-[12.5px] leading-relaxed text-muted">{e.message}</p>
                {e.metrics.length > 0 && (
                  <ul className="mt-3 space-y-1.5">
                    {e.metrics.map((m) => (
                      <li key={m.target} className="flex items-center justify-between gap-3 text-[12.5px]">
                        <span className="text-ink">{m.label}</span>
                        <span className="flex items-center gap-1.5 font-bold text-ink">
                          {m.before}{m.unit === "%" || m.unit === "% of skin" ? "%" : ""} → {m.after}{m.unit === "%" || m.unit === "% of skin" ? "%" : ""}
                          {m.verdict === "improved" ? <ArrowDown size={13} className="text-emerald-500" /> : m.verdict === "worse" ? <ArrowUp size={13} className="text-rose-500" /> : <Minus size={13} className="text-muted" />}
                        </span>
                      </li>
                    ))}
                  </ul>
                )}
                {e.startedWith.length > 0 && <p className="mt-3 rounded-xl bg-soft p-2.5 text-[11.5px] text-muted">Started around the same time as {e.startedWith.join(", ")}, so their effects cannot be told apart.</p>}
                <div className="mt-3"><StartDate effect={e} onSaved={load} /></div>
              </article>
            </Reveal>
          );
        })}
      </div>
      {items && items.length > 0 && <p className="mt-4 text-[11.5px] text-muted">This shows a pattern in your own photos, not proof. Lighting, season, other products and camera angle also move these numbers, so scan in similar light each time.</p>}
    </div>
  );
}
