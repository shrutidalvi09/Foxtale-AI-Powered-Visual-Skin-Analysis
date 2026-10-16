import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { NavLink, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowUp, BarChart3, Camera, CheckCircle2, ChevronRight, GitCompare, History as HistoryIcon, Home, ListChecks, Lock, Menu, Moon,
  ScanFace, Settings as SettingsIcon, Sun, X, WifiOff, FlaskConical, NotebookPen, Store,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import { getProfile } from "../services/api";

const LINKS = [
  { to: "/", label: "Dashboard", icon: Home, end: true, title: "Dashboard" },
  { to: "/scan", label: "Scan", icon: Camera, title: "Skin scan" },
  { to: "/analysis", label: "Analysis", icon: BarChart3, title: "Analysis" },
  { to: "/routine", label: "Routine", icon: ListChecks, title: "My routine" },
  { to: "/diary", label: "Skin diary", icon: NotebookPen, title: "Skin diary" },
  { to: "/shop", label: "Shop", icon: Store, title: "Shop" },
  { to: "/ingredients", label: "Ingredient check", icon: FlaskConical, title: "Ingredient check" },
  { to: "/history", label: "History", icon: HistoryIcon, title: "History" },
  { to: "/compare", label: "Compare", icon: GitCompare, title: "Compare scans" },
  { to: "/privacy", label: "Privacy", icon: Lock, title: "Privacy" },
  { to: "/settings", label: "Settings", icon: SettingsIcon, title: "Settings" },
];

const PAGE_TITLES: Record<string, string> = {
  "/welcome": "Welcome", "/how-it-works": "How it works", "/privacy-policy": "Privacy policy", "/terms": "Terms of use", "/about": "About",
};

/** Sidebar / drawer links. Between md and lg the sidebar is an icon rail, so labels go screen-reader-only there. */
function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <nav className="flex flex-col gap-1.5" aria-label="Main">
      {LINKS.map(({ to, label, icon: Icon, end, title }) => (
        <NavLink
          key={to} to={to} end={end} onClick={onNavigate} title={title}
          className={({ isActive }) =>
            `nav-link relative flex h-12 items-center gap-4 overflow-hidden rounded-[14px] px-4 text-[15px] transition-colors duration-200 md:max-lg:justify-center md:max-lg:px-0 ${
              isActive
                ? "bg-peach font-semibold text-fox-text dark:text-fox-300"
                : "font-medium text-ink/75 hover:bg-soft hover:text-ink"
            }`
          }
        >
          {({ isActive }) => (
            <>
              <span
                aria-hidden
                className={`absolute inset-y-2.5 left-0 w-[3px] rounded-r-full bg-fox-500 transition-opacity duration-200 ${isActive ? "opacity-100" : "opacity-0"}`}
              />
              <Icon size={20} strokeWidth={1.5} className={`shrink-0 ${isActive ? "text-fox-500" : ""}`} />
              <span className="md:max-lg:sr-only">{label}</span>
            </>
          )}
        </NavLink>
      ))}
    </nav>
  );
}

function Brand({ compact = false }: { compact?: boolean }) {
  return (
    <NavLink to="/" className="group flex items-center gap-2.5 px-2" aria-label="Foxtale home">
      <img src="/logo_mark.png" alt="" className="h-9 w-auto object-contain transition-transform duration-500 group-hover:-rotate-6" />
      <span className={`flex flex-col leading-none ${compact ? "md:max-lg:hidden" : ""}`}>
        <span className="font-display text-[28px] font-medium tracking-tight text-fox-500">foxtale</span>
        <span className="mt-1 text-[8.5px] font-semibold tracking-[0.2em] text-fox-text dark:text-fox-300">YOU GLOW DIFFERENT</span>
      </span>
    </NavLink>
  );
}

/** Sidebar profile chip: initial avatar + name, opens Settings where the profile is edited. */
function ProfileChip() {
  const { dataVersion } = useApp();
  const [name, setName] = useState("");
  useEffect(() => {
    getProfile().then((p) => setName((p.name ?? "").trim())).catch(() => undefined);
  }, [dataVersion]);
  return (
    <NavLink
      to="/settings" title="View profile"
      className="flex items-center gap-3 rounded-2xl border border-line bg-card p-2.5 transition hover:border-fox-300 md:max-lg:justify-center md:max-lg:p-1.5"
    >
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-fox-50 text-[15px] font-bold text-fox-text dark:bg-fox-500/15 dark:text-fox-300">
        {(name.charAt(0) || "Y").toUpperCase()}
      </span>
      <span className="min-w-0 flex-1 md:max-lg:hidden">
        <span className="block truncate text-[13.5px] font-bold text-ink">{name || "Your profile"}</span>
        <span className="block text-[11.5px] text-muted">View profile</span>
      </span>
      <ChevronRight size={16} className="shrink-0 text-muted md:max-lg:hidden" />
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
          className="pop fixed bottom-[164px] right-5 z-40 flex h-12 w-12 md:bottom-6 md:right-6 items-center justify-center rounded-full bg-fox-600 text-white shadow-glow transition hover:-translate-y-1 hover:bg-fox-700 active:scale-90"
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })} aria-label="Back to top"
        >
          <ArrowUp size={20} />
        </button>
      )}
    </>
  );
}

/** Phone bottom tab bar: the things you do most, with Scan as a raised centre button. */
function MobileTabs({ onMore }: { onMore: () => void }) {
  const navigate = useNavigate();
  const tab = (to: string, label: string, Icon: typeof Home, end = false) => (
    <NavLink
      to={to} end={end}
      className={({ isActive }) => `flex flex-1 flex-col items-center gap-0.5 py-2 text-[10.5px] font-bold transition-colors ${isActive ? "text-fox-text dark:text-fox-300" : "text-muted"}`}
    >
      <Icon size={20} /> {label}
    </NavLink>
  );
  return (
    <nav className="fixed inset-x-0 bottom-0 z-40 flex items-end border-t border-line bg-card/95 px-1 pb-[env(safe-area-inset-bottom)] backdrop-blur md:hidden" aria-label="Quick navigation">
      {tab("/", "Home", Home, true)}
      {tab("/analysis", "Analysis", BarChart3)}
      <button
        onClick={() => navigate("/scan", { state: { autostart: true } })} aria-label="Start new scan"
        className="-mt-5 mb-2 flex h-14 w-14 shrink-0 items-center justify-center rounded-full bg-fox-600 text-white shadow-glow transition active:scale-90"
      >
        <ScanFace size={26} />
      </button>
      {tab("/routine", "Routine", ListChecks)}
      <button onClick={onMore} className="flex flex-1 flex-col items-center gap-0.5 py-2 text-[10.5px] font-bold text-muted" aria-label="More menu">
        <Menu size={20} /> More
      </button>
    </nav>
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
    const match = LINKS.find((l) => (l.end ? pathname === l.to : pathname === l.to || pathname.startsWith(l.to + "/")));
    document.title = `${match?.title ?? PAGE_TITLES[pathname] ?? "Foxtale"} · Foxtale`;
    setOpen(false);
  }, [pathname]);

  if (pathname === "/welcome") {
    return (
      <div className="min-h-screen bg-app px-4 py-6">
        <div className="page-enter">{children}</div>
        {toastMessage && <div className="toast-in fixed bottom-6 left-1/2 z-50 rounded-2xl bg-ink px-5 py-3 text-sm font-semibold text-card shadow-card" role="status">{toastMessage}</div>}
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-app md:flex">
      <ScrollAids />

      {/* sidebar: full on desktop, icon rail on tablet, replaced by the top bar + bottom tabs on phones */}
      <aside className="no-scrollbar sticky top-0 hidden h-screen w-[88px] shrink-0 flex-col overflow-y-auto border-r border-line bg-sidebar px-3 py-7 md:flex lg:w-[264px] lg:px-4">
        <div className="md:max-lg:flex md:max-lg:justify-center"><Brand compact /></div>
        <div className="mt-10"><NavItems /></div>
        <div className="mt-auto space-y-3 pt-8">
          <button
            className="btn-cta w-full md:max-lg:!px-0" title="Start New Scan"
            onClick={() => navigate("/scan", { state: { autostart: true } })}
          >
            <Camera size={18} /> <span className="md:max-lg:sr-only">Start New Scan</span>
          </button>
          <button
            role="switch" aria-checked={dark} aria-label="Dark mode" title="Dark mode"
            onClick={() => updateSettings({ theme: dark ? "light" : "dark" })}
            className="flex h-12 w-full items-center gap-3 rounded-full border border-line bg-card px-4 text-sm font-medium text-ink transition duration-200 hover:border-fox-300 md:max-lg:justify-center md:max-lg:px-0"
          >
            <span key={settings.theme} className="pop flex text-muted">{dark ? <Sun size={18} strokeWidth={1.5} /> : <Moon size={18} strokeWidth={1.5} />}</span>
            <span className="flex-1 text-left md:max-lg:hidden">Dark mode</span>
            <span className={`relative h-5 w-9 shrink-0 rounded-full transition-colors duration-200 md:max-lg:hidden ${dark ? "bg-fox-600" : "bg-line"}`} aria-hidden>
              <span className={`absolute top-0.5 h-4 w-4 rounded-full bg-white shadow transition-all duration-200 ${dark ? "left-[18px]" : "left-0.5"}`} />
            </span>
          </button>
          <ProfileChip />
          <p className="flex items-center gap-1.5 px-2 pt-1 text-xs text-muted md:max-lg:justify-center" title="Private. Analysed on this computer.">
            <Lock size={12} className="shrink-0" /> <span className="md:max-lg:sr-only">Private. Analysed on this computer.</span>
          </p>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        {/* phone top bar */}
        <header className="sticky top-0 z-40 flex items-center justify-between border-b border-line bg-card/90 px-4 py-3 backdrop-blur md:hidden">
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
        <div className={`drawer border-b border-line bg-card md:hidden ${open ? "open" : "border-transparent"}`}>
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

        <main className="mx-auto w-full max-w-[1320px] flex-1 px-4 py-6 pb-28 sm:px-8 sm:py-8 md:pb-10">
          <div key={pathname} className="page-enter">{children}</div>
        </main>
        <footer className="border-t border-line px-4 py-5 pb-24 text-center text-xs text-muted md:pb-5">
          <p>Foxtale · AI-powered visual skin analysis. Not a medical diagnosis.</p>
          <p className="mt-2 flex flex-wrap justify-center gap-x-4 gap-y-1">
            <NavLink className="hover:text-ink hover:underline" to="/how-it-works">How it works &amp; FAQ</NavLink>
            <NavLink className="hover:text-ink hover:underline" to="/privacy-policy">Privacy Policy</NavLink>
            <NavLink className="hover:text-ink hover:underline" to="/terms">Terms</NavLink>
            <NavLink className="hover:text-ink hover:underline" to="/about">About</NavLink>
          </p>
        </footer>
      </div>

      <MobileTabs onMore={() => setOpen((o) => !o)} />

      {toastMessage && (
        <div
          key={toastMessage}
          className="toast-in fixed bottom-24 left-1/2 z-50 min-w-[240px] md:bottom-6 overflow-hidden rounded-2xl bg-ink px-5 py-3.5 text-sm font-semibold text-card shadow-card"
          role="status"
        >
          <span className="flex items-center gap-2.5"><CheckCircle2 size={17} className="text-emerald-400" /> {toastMessage}</span>
          <span className="toast-bar absolute inset-x-0 bottom-0 h-[3px] bg-fox-500" aria-hidden />
        </div>
      )}
    </div>
  );
}
