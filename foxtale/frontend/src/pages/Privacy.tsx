import { useEffect, useRef, useState } from "react";
import { Bell, Database, MessageCircle, Download, HardDrive, Image, Lock, Moon, Server, ShieldCheck, Trash2, Upload } from "lucide-react";
import { useApp } from "../context/AppContext";
import { API_BASE_URL, exportUrl, getPrivacy, importData, removeWhatsApp, setWhatsAppAuto, wipeData } from "../services/api";
import { useNavigate } from "react-router-dom";
import type { PrivacyStats } from "../types/analysis";
import { IconBadge, Modal, PageHeader, SectionTitle } from "../components/ui";
import { formatBytes } from "../lib/format";
import { CountUp, Reveal } from "../lib/motion";

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

export default function Privacy() {
  const { settings, updateSettings, toast, bumpData, dataVersion, backendOnline, whatsapp, setWhatsapp } = useApp();
  const navigate = useNavigate();
  const [stats, setStats] = useState<PrivacyStats | null>(null);
  const [confirmWipe, setConfirmWipe] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    getPrivacy().then(setStats).catch(() => setStats(null));
  }, [dataVersion]);

  const wipe = async () => {
    setConfirmWipe(false);
    try {
      await wipeData();
      toast("All personal data deleted");
      bumpData();
    } catch {
      toast("Could not delete data. Is the server running?");
    }
  };

  const onImport = async (file: File | undefined) => {
    if (!file) return;
    try {
      const { imported } = await importData(file);
      toast(`Imported ${imported} scan${imported === 1 ? "" : "s"}`);
      bumpData();
    } catch {
      toast("That file is not a valid Foxtale export");
    }
  };

  return (
    <div className="animate-fade-up space-y-6">
      <PageHeader title="Privacy Dashboard" subtitle="Your data stays on your computer. No tracking, no third-party services." />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {[
          { icon: Database, label: "Saved scans", value: stats ? <CountUp value={stats.scanCount} /> : "--" },
          { icon: Image, label: "Saved photos", value: stats ? <CountUp value={stats.imageCount} /> : "--" },
          { icon: Trash2, label: "Recently deleted", value: stats ? <CountUp value={stats.trashCount} /> : "--" },
          { icon: HardDrive, label: "Storage used", value: stats ? formatBytes(stats.diskBytes) : "--" },
        ].map(({ icon: Icon, label, value }, i) => (
          <Reveal key={label} index={i}>
            <div className="card lift flex items-center gap-4 p-5">
              <IconBadge><Icon size={18} /></IconBadge>
              <div><p className="text-xl font-extrabold text-ink">{value}</p><p className="text-sm text-muted">{label}</p></div>
            </div>
          </Reveal>
        ))}
      </div>

      <Reveal as="section" className="card p-5 sm:p-6">
        <SectionTitle title="Where your data is processed" icon={<Server size={18} />} subtitle="Your photo goes from this browser to the Foxtale server on your own computer, and nowhere else." />
        <dl className="mt-4 grid gap-3 text-sm sm:grid-cols-3">
          <div className="rounded-2xl bg-soft p-4"><dt className="label-caps">Analysis location</dt><dd className="mt-1 font-bold text-ink">This computer only</dd></div>
          <div className="rounded-2xl bg-soft p-4"><dt className="label-caps">Server address</dt><dd className="mt-1 break-all font-bold text-ink">{API_BASE_URL}</dd></div>
          <div className="rounded-2xl bg-soft p-4"><dt className="label-caps">Server status</dt><dd className={`mt-1 font-bold ${backendOnline ? "text-emerald-600" : "text-rose-600"}`}>{backendOnline == null ? "Checking..." : backendOnline ? "Running" : "Not reachable"}</dd></div>
        </dl>
        {stats && <p className="mt-3 text-xs text-muted">Stored in: {stats.dataDir}</p>}
        <p className="mt-2 flex items-center gap-2 text-sm text-ink"><ShieldCheck size={16} className="text-emerald-600" /> {whatsapp?.registered && whatsapp.auto
          ? "Analysis uses OpenCV on your machine. The one thing that leaves this computer is the report sent to your WhatsApp (through Meta's WhatsApp Business service), plus any product link you click."
          : "The server makes no cloud calls: analysis uses OpenCV on your machine. Opening a product link is the only time your browser leaves the app, and only when you click it."}</p>
      </Reveal>

      <Reveal as="section" className="card p-5 sm:p-6">
        <SectionTitle title="WhatsApp reports" icon={<MessageCircle size={18} />} subtitle="Where your analysis report is sent after every scan." />
        {whatsapp?.registered ? (
          <>
            <p className="mt-4 text-sm text-ink">Verified number: <b>{whatsapp.masked}</b></p>
            <div className="mt-2 divide-y divide-line">
              <Toggle checked={whatsapp.auto} onChange={async (v) => { try { setWhatsapp(await setWhatsAppAuto(v)); } catch { toast("Could not change that setting"); } }} label="Send reports automatically" hint="A PDF report and summary are sent to WhatsApp right after each scan." />
            </div>
            <p className="mt-2 text-xs text-muted">Reports (scores, findings, product suggestions and a PDF that can include your scan photo) travel through WhatsApp, which is run by Meta.</p>
            <div className="mt-4 flex flex-wrap gap-3">
              <button className="btn-soft" onClick={async () => { try { setWhatsapp(await removeWhatsApp()); toast("WhatsApp number removed. Enter a new one to keep scanning."); navigate("/scan"); } catch { toast("Could not remove the number"); } }}>Change number</button>
              <button className="btn-danger" onClick={async () => { try { setWhatsapp(await removeWhatsApp()); toast("WhatsApp number removed"); } catch { toast("Could not remove the number"); } }}>Remove number</button>
            </div>
          </>
        ) : (
          <p className="mt-4 text-sm text-muted">
            No WhatsApp number registered. {whatsapp?.configured ? "You will be asked for it before your next scan." : "WhatsApp sending is not set up on the server yet (see the README)."}
          </p>
        )}
      </Reveal>

      <Reveal as="section" className="card p-5 sm:p-6">
        <SectionTitle title="Preferences" icon={<Lock size={18} />} />
        <div className="mt-2 divide-y divide-line">
          <Toggle checked={settings.save_history} onChange={(v) => updateSettings({ save_history: v })} label="Save scan history" hint="Keep results so you can track changes, add notes and compare scans." />
          <Toggle checked={settings.save_images} onChange={(v) => updateSettings({ save_images: v })} label="Save scan photos" hint="Store the photo with each scan (needed for photos in History and before/after Compare). Off by default." />
          <Toggle checked={settings.theme === "dark"} onChange={(v) => updateSettings({ theme: v ? "dark" : "light" })} label="Dark mode" hint="Easier on the eyes in low light." />
          <div className="flex items-center justify-between gap-4 py-3">
            <div>
              <p className="flex items-center gap-2 font-bold text-ink"><Bell size={15} /> Scan reminder</p>
              <p className="text-sm text-muted">Show a reminder on the dashboard when it has been a while.</p>
            </div>
            <select className="input !w-auto !rounded-full" value={settings.reminder_days} onChange={(e) => updateSettings({ reminder_days: Number(e.target.value) })} aria-label="Reminder interval">
              <option value={0}>Off</option><option value={3}>Every 3 days</option><option value={7}>Every week</option><option value={14}>Every 2 weeks</option><option value={30}>Every month</option>
            </select>
          </div>
        </div>
        <p className="mt-2 flex items-center gap-2 text-xs text-muted"><Moon size={12} /> Theme is remembered in this browser; other preferences are saved on the server.</p>
      </Reveal>

      <Reveal as="section" className="card p-5 sm:p-6">
        <SectionTitle title="Your data" subtitle="Export everything, restore from a backup, or delete it all." icon={<Database size={18} />} />
        <div className="mt-4 flex flex-wrap gap-3">
          <a className="btn-soft" href={exportUrl()} download><Download size={15} /> Export everything</a>
          <button className="btn-soft" onClick={() => fileRef.current?.click()}><Upload size={15} /> Import backup</button>
          <input ref={fileRef} type="file" accept=".zip" className="hidden" onChange={(e) => { onImport(e.target.files?.[0]); e.target.value = ""; }} />
          <button className="btn-danger" onClick={() => setConfirmWipe(true)}><Trash2 size={15} /> Delete all data</button>
        </div>
      </Reveal>

      <Modal open={confirmWipe} onClose={() => setConfirmWipe(false)} title="Delete all data?">
        <p className="text-sm text-muted">This permanently deletes your scan history, saved photos, notes and preferences from the server. Export first if you want a backup. This cannot be undone.</p>
        <div className="mt-5 flex justify-end gap-2">
          <button className="btn-soft" onClick={() => setConfirmWipe(false)}>Cancel</button>
          <button className="btn-danger" onClick={wipe}>Delete everything</button>
        </div>
      </Modal>
    </div>
  );
}
