import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowUp, BarChart3, Camera, CheckCircle2, GitCompare, History as HistoryIcon, Home, Info, Lock, Menu, Moon, ScanFace, Sun, X, WifiOff,
} from "lucide-react";
import { useApp } from "../context/AppContext";

const LINKS = [
  { to: "/", label: "Dashboard", icon: Home, end: true, title: "Dashboard" },
  { to: "/scan", label: "Scan", icon: Camera, title: "Skin scan" },
  { to: "/analysis", label: "Analysis", icon: BarChart3, title: "Analysis" },
  { to: "/history", label: "History", icon: HistoryIcon, title: "History" },
  { to: "/compare", label: "Compare", icon: GitCompare, title: "Compare scans" },
  { to: "/privacy", label: "Privacy", icon: Lock, title: "Privacy" },
  { to: "/about", label: "About", icon: Info, title: "About" },
];

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1">
      {LINKS.map(({ to, label, icon: Icon, end }) => (
        <NavLink
          key={to} to={to} end={end} onClick={onNavigate}
          className={({ isActive }) =>
            `nav-link relative flex items-center gap-3 overflow-hidden rounded-2xl px-4 py-3 text-sm font-semibold transition-colors ${
              isActive
                ? "bg-fox-50 text-fox-text shadow-sm dark:bg-fox-500/15 dark:text-fox-300"
                : "text-muted hover:bg-soft hover:text-ink"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span
                aria-hidden
                className={`absolute left-0 top-1/2 h-6 w-1 -translate-y-1/2 rounded-r-full bg-fox-500 transition-all duration-300 ${
                  isActive ? "scale-y-100 opacity-100" : "scale-y-0 opacity-0"
                }`}
              />
              <Icon size={18} />
              {label}
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand() {
  return (
    <NavLink to="/" className="group flex items-center gap-2.5 px-2">
      <img src="/logo_mark.png" alt="" className="h-9 w-9 object-contain transition-transform duration-500 group-hover:-rotate-6 group-hover:scale-110" />
      <span className="text-xl font-extrabold text-ink">
        fox<span className="text-fox-500">tale</span>
      </span>
    </NavLink>
  );
}

/** Thin orange bar at the top that fills as the page is scrolled, plus a back-to-top button. */
function ScrollAids() {
  const [progress, setProgress] = useState(0);
  const [showTop, setShowTop] = useState(false);
  useEffect(() => {
    const onScroll = () => {
      const max = document.documentElement.scrollHeight - window.innerHeight;
      setProgress(max > 0 ? Math.min(1, window.scrollY / max) : 0);
      setShowTop(window.scrollY > 700);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
    };
  }, []);
  return (
    <>
      <div className="pointer-events-none fixed inset-x-0 top-0 z-[60] h-[3px]" aria-hidden>
        <div className="h-full origin-left bg-gradient-to-r from-fox-400 to-fox-600" style={{ transform: `scaleX(${progress})` }} />
      </div>
      {showTop && (
        <button
          className="pop fixed bottom-6 right-6 z-40 flex h-12 w-12 items-center justify-center rounded-full bg-fox-600 text-white shadow-glow transition hover:-translate-y-1 hover:bg-fox-700 active:scale-90"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to top"
        >
          <ArrowUp size={20} />
        </button>
      )}
    </>
  );
}

export default function Layout({ children }: { children: ReactNode }) {
  const { settings, updateSettings, backendOnline, recheckBackend, toastMessage } = useApp();
  const navigate = useNavigate();
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  const dark = settings.theme === "dark";

  // new page: back to the top, update the tab title, close the mobile menu
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "auto" });
    const match = LINKS.find((l) => (l.end ? pathname === l.to : pathname.startsWith(l.to)));
    document.title = `${match?.title ?? "Foxtale"} · Foxtale`;
    setOpen(false);
  }, [pathname]);

  return (
    <div className="min-h-screen bg-app lg:flex">
      <ScrollAids />

      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 flex-col justify-between border-r border-line bg-card p-5 lg:flex">
        <div className="space-y-8">
          <Brand />
          <NavItems />
        </div>
        <div className="space-y-3">
          <button className="btn-cta w-full" onClick={() => navigate("/scan", { state: { autostart: true } })}>
            <ScanFace size={18} /> Start New Scan
          </button>
          <button
            className="btn-soft w-full" onClick={() => updateSettings({ theme: dark ? "light" : "dark" })}
            aria-label="Toggle light and dark theme"
          >
            <span key={settings.theme} className="pop flex">{dark ? <Sun size={16} /> : <Moon size={16} />}</span>
            {dark ? "Light mode" : "Dark mode"}
          </button>
          <p className="flex items-center justify-center gap-1.5 text-center text-[11px] text-muted">
            <Lock size={12} /> Private. Analysed on this computer.
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile top bar */}
        <header className="sticky top-0 z-40 flex items-center justify-between border-b border-line bg-card/90 px-4 py-3 backdrop-blur lg:hidden">
          <Brand />
          <div className="flex items-center gap-1">
            <button className="rounded-full p-2 text-ink transition active:scale-90" onClick={() => updateSettings({ theme: dark ? "light" : "dark" })} aria-label="Toggle theme">
              <span key={settings.theme} className="pop flex">{dark ? <Sun size={20} /> : <Moon size={20} />}</span>
            </button>
            <button className="rounded-full p-2 text-ink transition active:scale-90" onClick={() => setOpen((o) => !o)} aria-label="Toggle navigation" aria-expanded={open}>
              <span key={String(open)} className="pop flex">{open ? <X size={22} /> : <Menu size={22} />}</span>
            </button>
          </div>
        </header>
        <div className={`drawer border-b border-line bg-card lg:hidden ${open ? "open" : "border-transparent"}`}>
          <div><div className="p-3"><NavItems onNavigate={() => setOpen(false)} /></div></div>
        </div>

        {backendOnline === false && (
          <div className="page-enter flex flex-wrap items-center justify-between gap-3 bg-rose-600 px-5 py-2.5 text-sm text-white" role="alert">
            <span className="flex items-center gap-2">
              <WifiOff size={16} /> Cannot reach the Foxtale server. Start the backend (uvicorn main:app) and try again.
            </span>
            <button className="rounded-full bg-white/20 px-3 py-1 font-semibold transition hover:bg-white/30 active:scale-95" onClick={recheckBackend}>Retry</button>
          </div>
        )}

        <main className="mx-auto w-full max-w-[1200px] flex-1 px-4 py-6 sm:px-8 sm:py-8">
          <div key={pathname} className="page-enter">{children}</div>
        </main>
        <footer className="border-t border-line py-5 text-center text-xs text-muted">
          Foxtale · AI-powered visual skin analysis. Not a medical diagnosis.
        </footer>
      </div>

      {toastMessage && (
        <div
          key={toastMessage}
          className="toast-in fixed bottom-6 left-1/2 z-50 min-w-[240px] overflow-hidden rounded-2xl bg-ink px-5 py-3.5 text-sm font-semibold text-card shadow-card"
          role="status"
        >
          <span className="flex items-center gap-2.5"><CheckCircle2 size={17} className="text-emerald-400" /> {toastMessage}</span>
          <span className="toast-bar absolute inset-x-0 bottom-0 h-[3px] bg-fox-500" aria-hidden />
        </div>
      )}
    </div>
  );
}
