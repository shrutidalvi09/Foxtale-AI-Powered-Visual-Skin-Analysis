import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { getSettings, getWhatsApp, health, putSettings } from "../services/api";
import type { WhatsAppStatus } from "../services/api";
import type { Scan, Settings } from "../types/analysis";

const DEFAULT_SETTINGS: Settings = {
  save_history: true,
  save_images: false,
  theme: "light",
  reminder_days: 7,
  min_confidence: 0,
  owned_products: [],
  onboarding_complete: false,
};

/** The scan on screen right now, plus its photo (kept in memory only, so scans that are not saved still show it). */
export interface CurrentScan {
  scan: Scan;
  imageDataUrl: string | null;
}

interface AppContextValue {
  settings: Settings;
  updateSettings: (patch: Partial<Settings>) => Promise<void>;
  backendOnline: boolean | null;
  recheckBackend: () => void;
  whatsapp: WhatsAppStatus | null;
  setWhatsapp: (s: WhatsAppStatus) => void;
  refreshWhatsapp: () => void;
  current: CurrentScan | null;
  setCurrent: (c: CurrentScan | null) => void;
  toast: (message: string) => void;
  toastMessage: string | null;
  /** bumps whenever scans change, so pages that list scans can refetch */
  dataVersion: number;
  bumpData: () => void;
}

const AppContext = createContext<AppContextValue | undefined>(undefined);

const THEME_KEY = "foxtale_theme";

function initialTheme(): "light" | "dark" {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    // storage may be blocked
  }
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>({ ...DEFAULT_SETTINGS, theme: initialTheme() });
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);
  const [whatsapp, setWhatsapp] = useState<WhatsAppStatus | null>(null);
  const [current, setCurrent] = useState<CurrentScan | null>(null);
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [dataVersion, setDataVersion] = useState(0);
  const toastTimer = useRef<number | undefined>(undefined);

  const refreshWhatsapp = useCallback(() => {
    getWhatsApp().then(setWhatsapp).catch(() => undefined);
  }, []);

  const recheckBackend = useCallback(() => {
    health()
      .then(() => {
        setBackendOnline(true);
        refreshWhatsapp();
      })
      .catch(() => setBackendOnline(false));
  }, [refreshWhatsapp]);

  useEffect(() => {
    recheckBackend();
    getSettings()
      .then((s) => setSettings((prev) => ({ ...s, theme: prev.theme })))
      .catch(() => undefined);
  }, [recheckBackend]);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", settings.theme === "dark");
    try {
      localStorage.setItem(THEME_KEY, settings.theme);
    } catch {
      // ignore
    }
  }, [settings.theme]);

  const updateSettings = useCallback(async (patch: Partial<Settings>) => {
    setSettings((prev) => ({ ...prev, ...patch }));
    try {
      const saved = await putSettings(patch);
      setSettings((prev) => ({ ...saved, theme: patch.theme ?? prev.theme }));
    } catch {
      // the UI keeps the change; it syncs the next time the server is reachable
    }
  }, []);

  const toast = useCallback((message: string) => {
    setToastMessage(message);
    window.clearTimeout(toastTimer.current);
    toastTimer.current = window.setTimeout(() => setToastMessage(null), 3200);
  }, []);

  const bumpData = useCallback(() => setDataVersion((v) => v + 1), []);

  const value = useMemo(
    () => ({
      settings, updateSettings, backendOnline, recheckBackend, whatsapp, setWhatsapp, refreshWhatsapp, current, setCurrent,
      toast, toastMessage, dataVersion, bumpData,
    }),
    [settings, updateSettings, backendOnline, recheckBackend, whatsapp, refreshWhatsapp, current, toast, toastMessage, dataVersion, bumpData]
  );

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppContextValue {
  const ctx = useContext(AppContext);
  if (!ctx) throw new Error("useApp must be used inside <AppProvider>");
  return ctx;
}
