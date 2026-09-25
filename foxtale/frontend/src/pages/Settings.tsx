import { useState } from "react";
import { Link } from "react-router-dom";
import { Bell, Lock, MessageCircle, Moon, Palette, Sun, User } from "lucide-react";
import DigestCard from "../components/DigestCard";
import ProfileForm from "../components/ProfileForm";
import { PageHeader, SectionTitle } from "../components/ui";
import { useApp } from "../context/AppContext";
import { Reveal } from "../lib/motion";
import type { Profile } from "../services/api";

export default function Settings() {
  const { profile, saveProfile, settings, updateSettings, whatsapp, toast } = useApp();
  const [busy, setBusy] = useState(false);
  const dark = settings.theme === "dark";

  const save = async (p: Profile) => {
    setBusy(true);
    try {
      await saveProfile(p);
      toast("Profile saved. Your suggestions will use it.");
    } catch {
      toast("Could not save your profile");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Settings" subtitle="Your profile, preferences and notifications in one place." />

      <Reveal as="section" className="card p-5 sm:p-6">
        <SectionTitle title="My profile" subtitle="These answers make your product suggestions safer and more personal." icon={<User size={18} />} />
        <div className="mt-5">
          <ProfileForm key={JSON.stringify(profile)} initial={profile} onSubmit={save} submitLabel="Save profile" busy={busy} />
        </div>
      </Reveal>

      <Reveal as="section" index={1} className="card p-5 sm:p-6">
        <SectionTitle title="Appearance" icon={<Palette size={18} />} />
        <div className="mt-4 flex gap-2">
          <button className={`chip ${!dark ? "chip-on" : ""}`} aria-pressed={!dark} onClick={() => updateSettings({ theme: "light" })}><Sun size={14} /> Light</button>
          <button className={`chip ${dark ? "chip-on" : ""}`} aria-pressed={dark} onClick={() => updateSettings({ theme: "dark" })}><Moon size={14} /> Dark</button>
        </div>
      </Reveal>

      <Reveal as="section" index={2} className="card p-5 sm:p-6">
        <SectionTitle title="Notifications" icon={<Bell size={18} />} />
        <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="flex items-center gap-2 text-sm font-bold text-ink"><MessageCircle size={16} className="text-emerald-600" /> WhatsApp reports</p>
            <p className="text-sm text-muted">{whatsapp?.registered ? `Reports go to ${whatsapp.masked}${whatsapp.auto ? "" : " (automatic sending is off)"}` : "No number registered yet."}</p>
          </div>
          <Link to="/privacy" className="btn-soft">Manage</Link>
        </div>
        <div className="mt-5 flex items-center justify-between gap-3 border-t border-line pt-4">
          <div>
            <p className="text-sm font-bold text-ink">Scan reminder</p>
            <p className="text-sm text-muted">Shown on your dashboard when it has been a while.</p>
          </div>
          <select className="input !w-auto !rounded-full" value={settings.reminder_days} onChange={(e) => updateSettings({ reminder_days: Number(e.target.value) })} aria-label="Reminder interval">
            <option value={0}>Off</option><option value={3}>Every 3 days</option><option value={7}>Every week</option><option value={14}>Every 2 weeks</option><option value={30}>Every month</option>
          </select>
        </div>
      </Reveal>

      <Reveal as="section" index={3} className="card p-5 sm:p-6">
        <DigestCard />
      </Reveal>

      <Reveal as="section" index={4} className="card p-5 sm:p-6">
        <SectionTitle title="Your data" subtitle="Saving history and photos, export, import and deletion." icon={<Lock size={18} />} />
        <Link to="/privacy" className="btn-soft mt-4">Open privacy controls</Link>
      </Reveal>
    </div>
  );
}
