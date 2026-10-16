import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, Bot, Lock, Mic, MessageCircle, Moon, Palette, Sun, User } from "lucide-react";
import DigestCard from "../components/DigestCard";
import ProfileForm from "../components/ProfileForm";
import { PageHeader, SectionTitle } from "../components/ui";
import { useApp } from "../context/AppContext";
import { useVoice } from "../context/VoiceContext";
import { Reveal } from "../lib/motion";
import { getAiStatus, setAiStatus } from "../services/api";
import type { Profile } from "../services/api";
import type { AiConsentStatus, VoiceLang } from "../types/analysis";

function Toggle({ checked, onChange, label, hint }: { checked: boolean; onChange: (v: boolean) => void; label: string; hint: string }) {
  return (
    <div className="flex items-center justify-between gap-4 py-3">
      <div>
        <p className="font-bold text-ink">{label}</p>
        <p className="text-sm text-muted">{hint}</p>
      </div>
      <button
        role="switch" aria-checked={checked} aria-label={label} onClick={() => onChange(!checked)}
        className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-300 active:scale-95 ${checked ? "bg-fox-600" : "bg-line"}`}
      >
        <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all duration-300 [transition-timing-function:cubic-bezier(0.34,1.56,0.64,1)] ${checked ? "left-[22px]" : "left-0.5"}`} />
      </button>
    </div>
  );
}

function AiSection() {
  const { toast } = useApp();
  const [status, setStatus] = useState<AiConsentStatus | null>(null);

  useEffect(() => {
    getAiStatus().then(setStatus).catch(() => undefined);
  }, []);

  const update = async (enabled: boolean, improveConsent: boolean) => {
    try {
      setStatus(await setAiStatus(enabled, improveConsent));
    } catch {
      toast("Could not save that setting");
    }
  };

  if (!status) return null;
  return (
    <>
      <SectionTitle title="AI Insights (beta)" icon={<Bot size={18} />} />
      <p className="mt-2 text-sm leading-relaxed text-muted">{status.disclosure}</p>
      {!status.configured && (
        <p className="mt-2 text-xs text-amber-600">Not set up on this server yet -- an administrator needs to add an AI provider key (see backend/.env.example).</p>
      )}
      <div className="mt-2 divide-y divide-line">
        <Toggle checked={status.enabled} onChange={(v) => update(v, status.improveConsent)} label="Turn on AI insights" hint="Sends a cropped, resized copy of your face photo to the AI provider for a written description, on every new scan." />
        <Toggle checked={status.improveConsent} onChange={(v) => update(status.enabled, v)} label="Help improve Foxtale AI" hint="Lets you send thumbs up/down feedback on findings. Stores the vote and an optional short comment only -- never the photo." />
      </div>
      <p className="mt-2 text-xs text-muted">Provider: {status.provider} · Model: {status.model}{status.dryRun ? " · test mode (no network call)" : ""}</p>
    </>
  );
}

const LANG_LABEL: Record<VoiceLang, string> = { en: "English", hi: "हिंदी (Hindi)", mr: "मराठी (Marathi)" };

function VoiceSection() {
  const voice = useVoice();
  const { toast } = useApp();
  const { status, recognizerSupported } = voice;

  if (!status) return null;

  const update = async (fn: () => Promise<unknown>, failMessage: string) => {
    try {
      await fn();
    } catch {
      toast(failMessage);
    }
  };

  return (
    <>
      <SectionTitle title="Fox, your voice companion (beta)" icon={<Mic size={18} />} />
      <p className="mt-2 text-sm leading-relaxed text-muted">{status.disclosure}</p>
      {!recognizerSupported && (
        <p className="mt-2 text-xs text-amber-600">This browser does not support speech recognition -- try Chrome or Edge.</p>
      )}
      {!status.configured && (
        <p className="mt-2 text-xs text-amber-600">Open-ended questions aren't set up on this server yet, but fixed commands (like "start a scan") still work.</p>
      )}
      <div className="mt-2 divide-y divide-line">
        <Toggle checked={status.enabled} onChange={(v) => update(() => voice.setEnabled(v), "Could not save that setting")} label="Turn on Fox" hint="Adds a mic button so you can talk to Fox -- she'll start scans, find your way around, and cheer you on, just like a big sister would." />
        <Toggle checked={status.wakeWordEnabled} onChange={(v) => update(() => voice.setWakeWordEnabled(v), "Could not save that setting")} label="Listen for a wake phrase" hint={'Best-effort: say "Hey Fox" to start listening without tapping the mic. Only while this tab is open and in front.'} />
        <Toggle checked={status.captionsEnabled} onChange={(v) => update(() => voice.setCaptionsEnabled(v), "Could not save that setting")} label="Show captions" hint="Shows what you said and what Fox says as on-screen text, for accessibility or a quiet room." />
        <Toggle checked={status.transcriptsConsent} onChange={(v) => update(() => voice.setTranscriptsConsent(v), "Could not save that setting")} label="Save voice transcripts" hint="Keeps a text log of what you said and Fox's reply (never audio), so you can review or delete it. Off by default." />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3 border-t border-line pt-4">
        <label className="text-sm font-bold text-ink" htmlFor="voice-lang">Spoken language</label>
        <select
          id="voice-lang" className="input !w-auto !rounded-full" value={status.language}
          onChange={(e) => update(() => voice.setLanguage(e.target.value as VoiceLang), "Could not save that setting")}
        >
          {(Object.keys(LANG_LABEL) as VoiceLang[]).map((l) => (
            <option key={l} value={l}>{LANG_LABEL[l]}</option>
          ))}
        </select>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-4">
        <label className="flex items-center gap-2 text-sm font-bold text-ink">
          Speed
          <input type="range" min={0.5} max={2} step={0.1} value={status.speed}
            onChange={(e) => update(() => voice.setSpeed(Number(e.target.value)), "Could not save that setting")} />
        </label>
        <label className="flex items-center gap-2 text-sm font-bold text-ink">
          Volume
          <input type="range" min={0} max={1} step={0.1} value={status.volume}
            onChange={(e) => update(() => voice.setVolume(Number(e.target.value)), "Could not save that setting")} />
        </label>
      </div>
      <p className="mt-3 text-xs text-muted">Provider: {status.provider} · Model: {status.model}{status.dryRun ? " · test mode (no network call)" : ""}</p>
    </>
  );
}

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
      <PageHeader page="settings" title="Settings" subtitle="Your profile, preferences and notifications in one place." />

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
        <AiSection />
      </Reveal>

      <Reveal as="section" index={4} className="card p-5 sm:p-6">
        <VoiceSection />
      </Reveal>

      <Reveal as="section" index={5} className="card p-5 sm:p-6">
        <DigestCard />
      </Reveal>

      <Reveal as="section" index={6} className="card p-5 sm:p-6">
        <SectionTitle title="Your data" subtitle="Saving history and photos, export, import and deletion." icon={<Lock size={18} />} />
        <Link to="/privacy" className="btn-soft mt-4">Open privacy controls</Link>
      </Reveal>
    </div>
  );
}
