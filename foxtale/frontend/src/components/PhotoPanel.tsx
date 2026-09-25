import { useMemo, useState } from "react";
import { Camera, Flame, ImageOff, Upload } from "lucide-react";
import { Link } from "react-router-dom";
import type { RegionObservation } from "../types/analysis";
import { CATEGORY_COLORS } from "../lib/format";

const CATEGORIES = [
  "Acne-like spots", "Blackheads", "Whiteheads", "Dark spots", "Redness", "Texture", "Dryness indicators",
  "Oiliness", "Tone evenness", "Under-eye", "Fine lines",
];

/** Filter choices: a group can cover several marker categories (all acne types together). */
export const PHOTO_GROUPS: Record<string, { label: string; categories: string[] }> = {
  acne: { label: "Acne (pimples, blackheads, whiteheads)", categories: ["Acne-like spots", "Blackheads", "Whiteheads"] },
  dark: { label: "Dark spots", categories: ["Dark spots"] },
  redness: { label: "Redness", categories: ["Redness"] },
  texture: { label: "Texture", categories: ["Texture"] },
  dryness: { label: "Dryness", categories: ["Dryness indicators"] },
  oiliness: { label: "Oiliness", categories: ["Oiliness"] },
  tone: { label: "Tone evenness", categories: ["Tone evenness"] },
  eye: { label: "Under-eye", categories: ["Under-eye"] },
  lines: { label: "Fine lines", categories: ["Fine lines"] },
};

export const REGION_BUCKETS = ["Forehead", "Cheeks", "Nose", "Chin", "Others"] as const;
export const BUCKET_COLORS = ["#e54a00", "#f5a524", "#3b8dff", "#12a06a", "#8b7fd6"];

export function regionBucket(name: string): (typeof REGION_BUCKETS)[number] {
  const n = name.toLowerCase();
  if (n.includes("forehead")) return "Forehead";
  if (n.includes("cheek")) return "Cheeks";
  if (n.includes("nose")) return "Nose";
  if (n.includes("chin")) return "Chin";
  return "Others";
}

export function RegionDonut({ regions }: { regions: RegionObservation[] }) {
  const counts = REGION_BUCKETS.map((b) => regions.filter((r) => regionBucket(r.region) === b).length);
  const total = counts.reduce((a, b) => a + b, 0);
  const R = 46;
  const C = 2 * Math.PI * R;
  let offset = 0;
  return (
    <div className="flex flex-wrap items-center gap-6">
      <svg width="130" height="130" viewBox="0 0 130 130" role="img" aria-label={`${total} observations by region`}>
        <circle cx="65" cy="65" r={R} fill="none" stroke="var(--line)" strokeWidth="16" />
        {total > 0 &&
          counts.map((c, i) => {
            if (!c) return null;
            const len = (c / total) * C;
            const el = (
              <circle
                key={REGION_BUCKETS[i]} cx="65" cy="65" r={R} fill="none" stroke={BUCKET_COLORS[i]} strokeWidth="16"
                strokeDasharray={`${len} ${C - len}`} strokeDashoffset={-offset} transform="rotate(-90 65 65)"
              />
            );
            offset += len;
            return el;
          })}
        <text x="65" y="72" textAnchor="middle" className="fill-ink text-[26px] font-extrabold">{total}</text>
      </svg>
      <ul className="space-y-1.5 text-sm">
        {REGION_BUCKETS.map((b, i) => (
          <li key={b} className="flex items-center gap-2.5">
            <span className="h-2.5 w-2.5 rounded-full" style={{ background: counts[i] ? BUCKET_COLORS[i] : "var(--line)" }} />
            <span className="w-16 text-ink">{b}</span>
            <span className="font-bold text-muted">{counts[i]}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

interface Props {
  image: string | null;
  regions: RegionObservation[];
  selected: RegionObservation | null;
  onSelect: (r: RegionObservation) => void;
  group: string;
  onGroupChange: (g: string) => void;
}

export default function PhotoPanel({ image, regions, selected, onSelect, group, onGroupChange }: Props) {
  const [heatmap, setHeatmap] = useState(false);
  const visible = useMemo(
    () => (group === "all" ? regions : regions.filter((r) => PHOTO_GROUPS[group]?.categories.includes(r.category))),
    [regions, group]
  );

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-3">
        <button className={`chip ${heatmap ? "chip-on" : ""}`} onClick={() => setHeatmap((h) => !h)} aria-pressed={heatmap}>
          <Flame size={16} className="text-fox-500" /> Heatmap
        </button>
        <select className="input !w-auto !rounded-full" value={group} onChange={(e) => onGroupChange(e.target.value)} aria-label="Category filter">
          <option value="all">All categories</option>
          {Object.entries(PHOTO_GROUPS).map(([k, g]) => <option key={k} value={k}>{g.label}</option>)}
        </select>
      </div>

      <div className="flex min-h-[320px] items-center justify-center overflow-hidden rounded-[20px] bg-[#0b1224] p-3">
        {image ? (
          <div className="relative inline-block max-w-full">
            <img src={image} alt="Your scan with markers" className="block max-h-[540px] max-w-full rounded-xl" />
            {heatmap &&
              visible.map((r, i) => (
                <span
                  key={`h${i}`} aria-hidden
                  className="pop pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full"
                  style={{ animationDelay: `${i * 40}ms`,
                    left: `${r.x * 100}%`, top: `${r.y * 100}%`, width: "22%", aspectRatio: "1",
                    background: `radial-gradient(circle, ${CATEGORY_COLORS[r.category] ?? "#3b8dff"}99 0%, transparent 70%)`,
                  }}
                />
              ))}
            {!heatmap &&
              visible.map((r, i) => {
                const active = selected === r;
                return (
                  <button
                    key={i} onClick={() => onSelect(r)} aria-label={`${r.category} in ${r.region}`}
                    className={`pop absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white transition-all duration-200 hover:scale-125 ${active ? "h-5 w-5 ring-4 ring-white/60" : "h-4 w-4"}`}
                    style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%`, background: CATEGORY_COLORS[r.category] ?? "#3b8dff", animationDelay: `${300 + i * 60}ms` }}
                  />
                );
              })}
          </div>
        ) : (
          <div className="flex max-w-xs flex-col items-center gap-3 px-6 py-10 text-center">
            <span className="flex h-16 w-16 items-center justify-center rounded-full border border-white/25 bg-white/10 text-fox-300">
              <ImageOff size={26} />
            </span>
            <p className="text-sm font-bold text-white">No photo for this scan</p>
            <p className="text-xs text-white/60">
              Photos are only kept when "Save scan photos" is on in Privacy. The findings still reflect what was measured.
            </p>
            <div className="mt-2 flex gap-2">
              <Link to="/scan" state={{ autostart: true }} className="btn-cta !px-4 !py-2 text-sm"><Camera size={15} /> Scan</Link>
              <Link to="/scan" className="btn-soft !px-4 !py-2"><Upload size={15} /> Upload</Link>
            </div>
          </div>
        )}
      </div>

      {image && (
        <ul className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
          {CATEGORIES.filter((c) => regions.some((r) => r.category === c)).map((c) => (
            <li key={c} className="flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full" style={{ background: CATEGORY_COLORS[c] }} /> {c}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
