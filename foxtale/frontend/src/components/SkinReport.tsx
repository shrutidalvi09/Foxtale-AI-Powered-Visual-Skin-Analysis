import { useState } from "react";
import { X } from "lucide-react";
import type { RegionObservation } from "../types/analysis";

const CATEGORY_DOT_COLOR: Record<string, string> = {
  "Acne-like spots": "bg-rose-500",
  Redness: "bg-orange-500",
  Texture: "bg-amber-500",
  "Dryness indicators": "bg-sky-500",
};

interface SkinReportProps {
  capturedImage: string | null;
  regions: RegionObservation[];
}

export default function SkinReport({ capturedImage, regions }: SkinReportProps) {
  const [selected, setSelected] = useState<RegionObservation | null>(null);

  const grouped = regions.reduce<Record<string, RegionObservation[]>>((acc, r) => {
    (acc[r.region] ??= []).push(r);
    return acc;
  }, {});

  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-700">Face Visualization</h3>

        {capturedImage ? (
          <div className="relative mx-auto aspect-square w-full max-w-sm overflow-hidden rounded-2xl">
            <img src={capturedImage} alt="Analyzed face" className="h-full w-full object-cover" />
            {regions.map((r, idx) => (
              <button
                key={idx}
                onClick={() => setSelected(r)}
                style={{ left: `${r.x * 100}%`, top: `${r.y * 100}%` }}
                className={`absolute h-4 w-4 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-white shadow-md ring-2 ring-black/10 transition hover:scale-125 ${
                  CATEGORY_DOT_COLOR[r.category] ?? "bg-accent-500"
                }`}
                aria-label={`${r.category} at ${r.region}`}
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-navy-500">No captured image available for this scan.</p>
        )}

        {selected && (
          <div className="mt-4 rounded-2xl border border-navy-900/10 bg-navy-900/[0.03] p-4">
            <div className="mb-2 flex items-start justify-between">
              <h4 className="text-sm font-semibold text-navy-800">Visible observation</h4>
              <button onClick={() => setSelected(null)} aria-label="Close">
                <X size={16} className="text-navy-500" />
              </button>
            </div>
            <dl className="space-y-1.5 text-sm">
              <div className="flex justify-between">
                <dt className="text-navy-500">Area</dt>
                <dd className="font-medium text-navy-800">{selected.region}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-navy-500">Observation</dt>
                <dd className="font-medium text-navy-800">{selected.observation}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-navy-500">Confidence</dt>
                <dd className="font-medium text-navy-800">
                  {Math.round(selected.confidence * 100)}%
                </dd>
              </div>
            </dl>
            <p className="mt-3 text-xs text-navy-500">
              This is a visual observation and does not establish a medical diagnosis.
            </p>
          </div>
        )}
      </div>

      <div className="card p-5">
        <h3 className="mb-4 text-sm font-semibold text-navy-700">Region Breakdown</h3>
        {Object.keys(grouped).length === 0 ? (
          <p className="text-sm text-navy-500">No notable visible observations in any region.</p>
        ) : (
          <div className="space-y-4">
            {Object.entries(grouped).map(([region, obs]) => (
              <div key={region}>
                <h4 className="text-xs font-bold uppercase tracking-wide text-navy-500">
                  {region}
                </h4>
                <ul className="mt-1.5 space-y-1">
                  {obs.map((o, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm text-navy-700">
                      <span
                        className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${
                          CATEGORY_DOT_COLOR[o.category] ?? "bg-accent-500"
                        }`}
                      />
                      {o.observation}
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
