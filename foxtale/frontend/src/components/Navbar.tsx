import { NavLink } from "react-router-dom";
import { ScanFace, Menu, X } from "lucide-react";
import { useState } from "react";

const links = [
  { to: "/", label: "Home" },
  { to: "/scan", label: "Scan" },
  { to: "/results", label: "Analysis" },
  { to: "/history", label: "History" },
  { to: "/about", label: "About" },
];

export default function Navbar() {
  const [open, setOpen] = useState(false);

  return (
    <header className="sticky top-0 z-40 border-b border-navy-900/5 bg-white/80 backdrop-blur-lg">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-4 py-3 sm:px-6">
        <NavLink to="/" className="flex items-center gap-2 font-extrabold text-lg">
          <span className="text-2xl leading-none" aria-hidden>
            🦊
          </span>
          <span>
            Fox<span className="text-fox-500">tale</span>
          </span>
        </NavLink>

        <nav className="hidden items-center gap-1 md:flex">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              className={({ isActive }) =>
                `rounded-full px-4 py-2 text-sm font-medium transition ${
                  isActive
                    ? "bg-navy-900 text-white"
                    : "text-navy-700 hover:bg-navy-900/5"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>

        <NavLink to="/scan" className="btn-primary hidden md:inline-flex text-sm !px-5 !py-2.5">
          <ScanFace size={16} />
          Start Scan
        </NavLink>

        <button
          className="rounded-lg p-2 text-navy-800 md:hidden"
          onClick={() => setOpen((o) => !o)}
          aria-label="Toggle navigation"
        >
          {open ? <X size={22} /> : <Menu size={22} />}
        </button>
      </div>

      {open && (
        <nav className="flex flex-col gap-1 border-t border-navy-900/5 bg-white px-4 py-3 md:hidden">
          {links.map((l) => (
            <NavLink
              key={l.to}
              to={l.to}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                `rounded-lg px-3 py-2 text-sm font-medium ${
                  isActive ? "bg-navy-900 text-white" : "text-navy-700 hover:bg-navy-900/5"
                }`
              }
            >
              {l.label}
            </NavLink>
          ))}
        </nav>
      )}
    </header>
  );
}
