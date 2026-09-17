import React, { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { RegionObservation, ScanRecord, SkinAnalysis } from "../types/analysis";

const HISTORY_KEY = "foxtale_history_v1";
const SAVE_HISTORY_PREF_KEY = "foxtale_save_history_pref";

interface ScanContextValue {
  capturedImage: string | null;
  setCapturedImage: (dataUrl: string | null) => void;
  latestAnalysis: SkinAnalysis | null;
  latestRegions: RegionObservation[];
  setLatestResult: (analysis: SkinAnalysis, regions: RegionObservation[]) => void;
  clearScan: () => void;

  history: ScanRecord[];
  deleteScan: (id: string) => void;
  clearHistory: () => void;

  saveHistoryEnabled: boolean;
  setSaveHistoryEnabled: (v: boolean) => void;
}

const ScanContext = createContext<ScanContextValue | undefined>(undefined);

function loadHistory(): ScanRecord[] {
  try {
    const raw = localStorage.getItem(HISTORY_KEY);
    return raw ? (JSON.parse(raw) as ScanRecord[]) : [];
  } catch {
    return [];
  }
}

function loadSaveHistoryPref(): boolean {
  try {
    const raw = localStorage.getItem(SAVE_HISTORY_PREF_KEY);
    return raw === null ? true : raw === "true";
  } catch {
    return true;
  }
}

export function ScanProvider({ children }: { children: React.ReactNode }) {
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [latestAnalysis, setLatestAnalysis] = useState<SkinAnalysis | null>(null);
  const [latestRegions, setLatestRegions] = useState<RegionObservation[]>([]);
  const [history, setHistory] = useState<ScanRecord[]>(() => loadHistory());
  const [saveHistoryEnabled, setSaveHistoryEnabledState] = useState<boolean>(() =>
    loadSaveHistoryPref()
  );

  useEffect(() => {
    localStorage.setItem(HISTORY_KEY, JSON.stringify(history));
  }, [history]);

  useEffect(() => {
    localStorage.setItem(SAVE_HISTORY_PREF_KEY, String(saveHistoryEnabled));
  }, [saveHistoryEnabled]);

  const setLatestResult = useCallback(
    (analysis: SkinAnalysis, regions: RegionObservation[]) => {
      setLatestAnalysis(analysis);
      setLatestRegions(regions);

      if (saveHistoryEnabled) {
        const record: ScanRecord = {
          id: crypto.randomUUID(),
          timestamp: new Date().toISOString(),
          analysis,
          regions,
        };
        // Note: only the analysis summary is persisted, never the captured
        // image, in line with the app's "no images stored" privacy default.
        setHistory((prev) => [record, ...prev].slice(0, 50));
      }
    },
    [saveHistoryEnabled]
  );

  const clearScan = useCallback(() => {
    setCapturedImage(null);
    setLatestAnalysis(null);
    setLatestRegions([]);
  }, []);

  const deleteScan = useCallback((id: string) => {
    setHistory((prev) => prev.filter((r) => r.id !== id));
  }, []);

  const clearHistory = useCallback(() => {
    setHistory([]);
  }, []);

  return (
    <ScanContext.Provider
      value={{
        capturedImage,
        setCapturedImage,
        latestAnalysis,
        latestRegions,
        setLatestResult,
        clearScan,
        history,
        deleteScan,
        clearHistory,
        saveHistoryEnabled,
        setSaveHistoryEnabled: setSaveHistoryEnabledState,
      }}
    >
      {children}
    </ScanContext.Provider>
  );
}

export function useScan(): ScanContextValue {
  const ctx = useContext(ScanContext);
  if (!ctx) throw new Error("useScan must be used within a ScanProvider");
  return ctx;
}
