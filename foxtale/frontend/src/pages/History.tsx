import { Link } from "react-router-dom";
import { Trash2, ScanFace, ShieldCheck } from "lucide-react";
import { useScan } from "../context/ScanContext";
import type { SeverityLevel } from "../types/analysis";

const LEVEL_DOT: Record<SeverityLevel, string> = {
  minimal: "bg-emerald-500",
  mild: "bg-amber-500",
  moderate: "bg-orange-500",
  noticeable: "bg-rose-500",
};

export default function History() {
  const { history, deleteScan, clearHistory, saveHistoryEnabled, setSaveHistoryEnabled } =
    useScan();

  return (
    <div className="mx-auto max-w-3xl px-6 py-12">
      <div className="mb-8 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-extrabold text-navy-900">Scan History</h1>
          <p className="mt-1 text-navy-600">Only analysis summaries are stored — never images.</p>
        </div>
        {history.length > 0 && (
          <button onClick={clearHistory} className="btn-secondary !py-2 !px-4 text-sm">
            <Trash2 size={16} />
            Delete All History
          </button>
        )}
      </div>

      <div className="mb-8 card flex items-center justify-between p-4">
        <div className="flex items-center gap-3">
          <ShieldCheck className="text-accent-500" size={20} />
          <div>
            <p className="text-sm font-semibold text-navy-800">Save scan history</p>
            <p className="text-xs text-navy-500">Store analysis summaries locally in this browser.</p>
          </div>
        </div>
        <button
          onClick={() => setSaveHistoryEnabled(!saveHistoryEnabled)}
          role="switch"
          aria-checked={saveHistoryEnabled}
          className={`relative h-6 w-11 rounded-full transition ${
            saveHistoryEnabled ? "bg-accent-500" : "bg-navy-900/15"
          }`}
        >
          <span
            className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition ${
              saveHistoryEnabled ? "left-5" : "left-0.5"
            }`}
          />
        </button>
      </div>

      {history.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 p-12 text-center">
          <p className="text-navy-600">No scans saved yet.</p>
          <Link to="/scan" className="btn-primary">
            <ScanFace size={18} />
            Start Face Scan
          </Link>
        </div>
      ) : (
        <div className="space-y-3">
          {history.map((record) => (
            <div key={record.id} className="card flex items-center justify-between gap-4 p-4">
              <div className="flex-1">
                <p className="text-sm font-semibold text-navy-800">
                  {new Date(record.timestamp).toLocaleString()}
                </p>
                <div className="mt-2 flex flex-wrap gap-3 text-xs text-navy-600">
                  <span className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${LEVEL_DOT[record.analysis.acne_like_spots.level]}`} />
                    Spots: {record.analysis.acne_like_spots.level}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${LEVEL_DOT[record.analysis.redness.level]}`} />
                    Redness: {record.analysis.redness.level}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${LEVEL_DOT[record.analysis.texture.level]}`} />
                    Texture: {record.analysis.texture.level}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className={`h-2 w-2 rounded-full ${LEVEL_DOT[record.analysis.dryness_indicators.level]}`} />
                    Dryness: {record.analysis.dryness_indicators.level}
                  </span>
                </div>
              </div>
              <button
                onClick={() => deleteScan(record.id)}
                className="shrink-0 rounded-full p-2 text-navy-400 hover:bg-rose-50 hover:text-rose-500"
                aria-label="Delete scan"
              >
                <Trash2 size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
