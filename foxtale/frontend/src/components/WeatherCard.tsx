import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Cloud, Droplets, Loader2, MapPin, Sun, Thermometer, Wind } from "lucide-react";
import { useApp } from "../context/AppContext";
import { clearLocation, getWeather, setLocation, ApiError } from "../services/api";
import type { SkinWeather } from "../services/api";
import { Skeleton } from "../lib/motion";

const ICONS: Record<string, typeof Sun> = { sun: Sun, wind: Wind, droplets: Droplets, thermometer: Thermometer, cloud: Cloud };
const TONE = { good: "border-emerald-300 bg-emerald-50 dark:border-emerald-500/40 dark:bg-emerald-500/10", ok: "border-line bg-soft", warn: "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" } as const;

function uvColor(uv?: number | null) {
  if (uv == null) return "text-muted";
  return uv >= 8 ? "text-rose-500" : uv >= 6 ? "text-orange-500" : uv >= 3 ? "text-amber-500" : "text-emerald-500";
}

/** "Skin weather": today's UV, humidity, temperature and air quality for your city, with tips. */
export default function WeatherCard() {
  const { toast } = useApp();
  const [w, setW] = useState<SkinWeather | null>(null);
  const [editing, setEditing] = useState(false);
  const [city, setCity] = useState("");
  const [busy, setBusy] = useState(false);

  const load = useCallback(() => {
    getWeather().then(setW).catch(() => setW({ configured: false }));
  }, []);
  useEffect(load, [load]);

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    try {
      const loc = await setLocation(city);
      toast(`Location set to ${loc.name}`);
      setEditing(false);
      setCity("");
      setW(null);
      load();
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not set that city");
    } finally {
      setBusy(false);
    }
  };

  const form = (
    <form onSubmit={save} className="mt-3 flex flex-wrap gap-2">
      <input className="input min-w-[180px] flex-1" placeholder="Your city, e.g. Pune" value={city} onChange={(e) => setCity(e.target.value)} aria-label="Your city" maxLength={80} />
      <button className="btn-cta !py-2.5 text-sm" type="submit" disabled={busy || city.trim().length < 2}>{busy ? <Loader2 size={16} className="animate-spin" /> : <MapPin size={16} />} Save city</button>
      {w?.configured && <button type="button" className="btn-soft" onClick={() => setEditing(false)}>Cancel</button>}
    </form>
  );

  if (w === null) return <Skeleton className="h-44" />;

  if (!w.configured) {
    return (
      <section className="card p-5 sm:p-6">
        <h2 className="flex items-center gap-2.5 text-[15px] font-extrabold text-ink"><Sun size={18} className="text-fox-500" /> Skin weather</h2>
        <p className="mt-1 text-sm text-muted">Add your city to see today's UV, humidity and air quality with skincare tips that fit them. Only the city name is used.</p>
        {form}
      </section>
    );
  }

  return (
    <section className="card p-5 sm:p-6">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <h2 className="flex items-center gap-2.5 text-[15px] font-extrabold text-ink"><Sun size={18} className="text-fox-500" /> Skin weather today</h2>
        <div className="flex items-center gap-3 text-xs">
          <span className="flex items-center gap-1 text-muted"><MapPin size={12} /> {w.city}</span>
          <button className="font-bold text-fox-text underline dark:text-fox-300" onClick={() => setEditing((v) => !v)}>Change</button>
          <button className="font-bold text-muted underline" onClick={async () => { await clearLocation(); setW({ configured: false }); }}>Remove</button>
        </div>
      </div>
      {editing && form}
      {w.error ? <p className="mt-3 text-sm text-muted">{w.error}</p> : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
            {[
              { label: "UV index", value: w.uv != null ? Math.round(w.uv) : "--", sub: w.uvLabel, cls: uvColor(w.uv) },
              { label: "Temperature", value: w.temp != null ? `${Math.round(w.temp)}°C` : "--", sub: "", cls: "text-ink" },
              { label: "Humidity", value: w.humidity != null ? `${Math.round(w.humidity)}%` : "--", sub: "", cls: "text-ink" },
              { label: "Air quality", value: w.aqi != null ? Math.round(w.aqi) : "--", sub: w.aqiLabel, cls: w.aqi != null && w.aqi > 100 ? "text-rose-500" : "text-ink" },
            ].map((m) => (
              <div key={m.label} className="rounded-2xl bg-soft p-3.5">
                <p className="label-caps">{m.label}</p>
                <p className={`mt-1 text-2xl font-extrabold ${m.cls}`}>{m.value}</p>
                {m.sub && <p className="text-[11px] text-muted">{m.sub}</p>}
              </div>
            ))}
          </div>
          <ul className="mt-4 space-y-2.5">
            {(w.tips ?? []).map((t) => {
              const Icon = ICONS[t.icon] ?? Sun;
              return (
                <li key={t.title} className={`page-enter rounded-2xl border p-3.5 ${TONE[t.tone]}`}>
                  <p className="flex items-center gap-2 text-sm font-extrabold text-ink"><Icon size={16} className="text-fox-500" /> {t.title}</p>
                  <p className="mt-1 text-[13px] leading-relaxed text-muted">{t.text}</p>
                  {t.productNames.length > 0 && <p className="mt-1.5 text-[12px] text-ink">Try: {t.productNames.join(" · ")} <Link to="/shop" className="font-bold text-fox-text underline dark:text-fox-300">Shop</Link></p>}
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-[11px] text-muted">Weather from Open-Meteo. Tips are general skincare guidance for your latest skin type ({w.skinType}).</p>
        </>
      )}
    </section>
  );
}
