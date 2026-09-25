import { useEffect, useState } from "react";
import { CalendarClock, Loader2, Send } from "lucide-react";
import { Link } from "react-router-dom";
import { useApp } from "../context/AppContext";
import { getDigest, putDigest, sendDigestNow, ApiError } from "../services/api";
import type { DigestState } from "../services/api";
import { formatDate } from "../lib/format";
import { SectionTitle } from "./ui";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
const HOURS = [7, 8, 9, 10, 12, 15, 18, 20, 21];
const hourLabel = (h: number) => `${((h + 11) % 12) + 1}:00 ${h < 12 ? "AM" : "PM"}`;

/** Weekly WhatsApp check-in: choose the day and time, preview it, or send one now. */
export default function DigestCard() {
  const { toast } = useApp();
  const [d, setD] = useState<DigestState | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    getDigest().then(setD).catch(() => undefined);
  }, []);

  const update = async (enabled: boolean, day: number, hour: number) => {
    try {
      setD(await putDigest(enabled, day, hour));
    } catch {
      toast("Could not save that setting");
    }
  };

  const sendNow = async () => {
    setBusy(true);
    try {
      await sendDigestNow();
      toast("Check-in sent to your WhatsApp");
      setD(await getDigest());
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not send the check-in");
    } finally {
      setBusy(false);
    }
  };

  if (!d) return null;
  return (
    <div>
      <SectionTitle title="Weekly WhatsApp check-in" icon={<CalendarClock size={18} />} subtitle="A short summary of your week: how your skin changed, your routine streak and one tip." />
      {!d.registered ? (
        <p className="mt-4 rounded-2xl bg-soft p-4 text-sm text-muted">Register your WhatsApp number first: <Link to="/scan" className="font-bold text-fox-text underline dark:text-fox-300">verify it here</Link>.</p>
      ) : (
        <>
          <div className="mt-4 flex flex-wrap items-center justify-between gap-4">
            <button
              role="switch" aria-checked={d.enabled} aria-label="Send a weekly check-in" onClick={() => update(!d.enabled, d.day, d.hour)}
              className={`relative h-7 w-12 shrink-0 rounded-full transition-colors duration-300 active:scale-95 ${d.enabled ? "bg-fox-600" : "bg-line"}`}
            >
              <span className={`absolute top-0.5 h-6 w-6 rounded-full bg-white shadow transition-all duration-300 [transition-timing-function:cubic-bezier(0.34,1.56,0.64,1)] ${d.enabled ? "left-[22px]" : "left-0.5"}`} />
            </button>
            <div className="flex flex-1 flex-wrap items-center justify-end gap-2 text-sm">
              <span className="text-muted">Every</span>
              <select className="input !w-auto !rounded-full" value={d.day} onChange={(e) => update(d.enabled, Number(e.target.value), d.hour)} aria-label="Day of the week">
                {DAYS.map((n, i) => <option key={n} value={i}>{n}</option>)}
              </select>
              <span className="text-muted">at</span>
              <select className="input !w-auto !rounded-full" value={d.hour} onChange={(e) => update(d.enabled, d.day, Number(e.target.value))} aria-label="Time">
                {HOURS.map((h) => <option key={h} value={h}>{hourLabel(h)}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-4 rounded-2xl bg-soft p-4 text-[13px] leading-relaxed">
            <p className="label-caps mb-1.5">Preview of this week's message</p>
            <p className="text-ink"><b>Hi {d.preview.name},</b> {d.preview.skin}</p>
            <p className="mt-1 text-ink">{d.preview.routine}</p>
            <p className="mt-1 text-muted">Tip: {d.preview.tip}</p>
          </div>
          <div className="mt-4 flex flex-wrap items-center gap-3">
            <button className="btn-soft" onClick={sendNow} disabled={busy}>{busy ? <Loader2 size={15} className="animate-spin" /> : <Send size={15} />} Send one now</button>
            <p className="text-xs text-muted">{d.lastSent ? `Last sent ${formatDate(d.lastSent)}.` : "Not sent yet."} Sent only while the Foxtale server is running.</p>
          </div>
        </>
      )}
    </div>
  );
}
