import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Loader2, MessageCircle, RotateCw, Send, ShieldCheck } from "lucide-react";
import { useApp } from "../context/AppContext";
import {
  ApiError, getDelivery, registerWhatsApp, resendWhatsApp, skipWhatsApp, verifyWhatsApp,
} from "../services/api";
import type { WhatsAppDelivery } from "../services/api";

const COUNTRIES = [
  ["+91", "India"], ["+1", "USA / Canada"], ["+44", "United Kingdom"], ["+971", "UAE"], ["+65", "Singapore"],
  ["+61", "Australia"], ["+92", "Pakistan"], ["+880", "Bangladesh"], ["+94", "Sri Lanka"], ["+977", "Nepal"],
  ["+966", "Saudi Arabia"], ["+49", "Germany"], ["+33", "France"], ["+27", "South Africa"],
] as const;

const RESEND_SECONDS = 30;

/** Shown before the first scan: register and verify the WhatsApp number that reports are sent to. */
export function WhatsAppGate() {
  const { whatsapp, setWhatsapp, toast } = useApp();
  const [cc, setCc] = useState("+91");
  const [digits, setDigits] = useState("");
  const [consent, setConsent] = useState(false);
  const [step, setStep] = useState<"phone" | "code">("phone");
  const [masked, setMasked] = useState("");
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [cooldown, setCooldown] = useState(0);
  const codeRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (cooldown <= 0) return;
    const t = setTimeout(() => setCooldown((c) => c - 1), 1000);
    return () => clearTimeout(t);
  }, [cooldown]);

  useEffect(() => {
    if (step === "code") codeRef.current?.focus();
  }, [step]);

  const fail = (err: unknown) => setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");

  const sendCode = useCallback(async () => {
    setError(null);
    const clean = digits.replace(/\D/g, "").replace(/^0+/, "");
    if (clean.length < 6) {
      setError("Enter your WhatsApp number.");
      return;
    }
    setBusy(true);
    try {
      const res = await registerWhatsApp(`${cc}${clean}`);
      setMasked(res.masked);
      setStep("code");
      setCode("");
      setCooldown(RESEND_SECONDS);
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  }, [cc, digits]);

  const verify = async () => {
    setError(null);
    setBusy(true);
    try {
      setWhatsapp(await verifyWhatsApp(code.trim()));
      toast("WhatsApp number verified");
    } catch (err) {
      fail(err);
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    try {
      setWhatsapp(await skipWhatsApp());
    } catch (err) {
      fail(err);
    }
  };

  const notConfigured = whatsapp && !whatsapp.configured;

  return (
    <div className="card page-enter mx-auto w-full max-w-xl p-6 sm:p-8">
      <div className="flex items-center gap-4">
        <span className="pop flex h-14 w-14 items-center justify-center rounded-full bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15">
          <MessageCircle size={26} />
        </span>
        <div>
          <h2 className="text-xl font-extrabold text-ink">Get your report on WhatsApp</h2>
          <p className="text-sm text-muted">Register your number once. Every scan report is then sent to it automatically.</p>
        </div>
      </div>

      {notConfigured ? (
        <div className="mt-6 space-y-4">
          <div className="flex items-start gap-3 rounded-2xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100" role="alert">
            <AlertTriangle size={18} className="mt-0.5 shrink-0" />
            <p>
              WhatsApp sending is not set up on this server yet. Add your Meta WhatsApp Cloud API details to{" "}
              <code className="rounded bg-black/10 px-1">backend/.env</code> (see the README), then restart the backend. To try
              the flow first, set <code className="rounded bg-black/10 px-1">WHATSAPP_DRY_RUN=1</code>.
            </p>
          </div>
          <button className="btn-soft w-full" onClick={skip}>Continue without WhatsApp</button>
          <p className="text-center text-xs text-muted">Your reports will stay in the app. You can register a number later in Privacy.</p>
        </div>
      ) : step === "phone" ? (
        <form key="phone" className="page-enter mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); if (consent) sendCode(); }}>
          {whatsapp?.dryRun && (
            <p className="rounded-2xl bg-soft p-3 text-xs text-muted">Test mode: no message is sent. The verification code is printed in the backend console.</p>
          )}
          <div>
            <label className="label-caps" htmlFor="wa-number">WhatsApp number</label>
            <div className="mt-1.5 flex gap-2">
              <select className="input !w-[128px] shrink-0" value={cc} onChange={(e) => setCc(e.target.value)} aria-label="Country code">
                {COUNTRIES.map(([code2, name]) => <option key={code2 + name} value={code2}>{code2} {name}</option>)}
              </select>
              <input
                id="wa-number" className="input" inputMode="tel" autoComplete="tel-national" placeholder="98765 43210"
                value={digits} onChange={(e) => setDigits(e.target.value)} maxLength={16}
              />
            </div>
          </div>
          <label className="flex cursor-pointer items-start gap-3 rounded-2xl bg-soft p-3 text-[13px] leading-relaxed text-ink">
            <input type="checkbox" className="mt-1 h-4 w-4 accent-fox-500" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
            <span>
              I agree to receive my Foxtale reports on this WhatsApp number. I understand each report (scores, findings, product
              suggestions and a PDF that can include my scan photo) is sent through WhatsApp, which is run by Meta.
            </span>
          </label>
          {error && <p key={error} className="shake text-sm font-semibold text-rose-600" role="alert">{error}</p>}
          <button className="btn-cta w-full" type="submit" disabled={busy || !consent || digits.replace(/\D/g, "").length < 6}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />} Send verification code
          </button>
        </form>
      ) : (
        <form key="code" className="page-enter mt-6 space-y-4" onSubmit={(e) => { e.preventDefault(); if (code.length === 6) verify(); }}>
          <p className="text-sm text-ink">We sent a 6-digit code to <b>{masked}</b> on WhatsApp. It is valid for 10 minutes.</p>
          <input
            ref={codeRef} className="input text-center text-2xl font-extrabold tracking-[0.5em]" inputMode="numeric"
            autoComplete="one-time-code" maxLength={6} placeholder="••••••" value={code} aria-label="Verification code"
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
          />
          {error && <p key={error} className="shake text-sm font-semibold text-rose-600" role="alert">{error}</p>}
          <button className="btn-cta w-full" type="submit" disabled={busy || code.length !== 6}>
            {busy ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />} Verify and continue
          </button>
          <div className="flex items-center justify-between text-sm">
            <button type="button" className="font-semibold text-muted hover:text-ink" onClick={() => { setStep("phone"); setError(null); }}>Change number</button>
            <button type="button" className="flex items-center gap-1.5 font-semibold text-fox-text disabled:text-muted dark:text-fox-300" disabled={cooldown > 0 || busy} onClick={sendCode}>
              <RotateCw size={14} /> {cooldown > 0 ? `Resend in ${cooldown}s` : "Resend code"}
            </button>
          </div>
        </form>
      )}

      <p className="mt-6 flex items-start gap-2 text-xs text-muted">
        <ShieldCheck size={14} className="mt-0.5 shrink-0 text-emerald-600" />
        Your number is stored only on this computer and used only to send your own reports. You can remove it any time in Privacy.
      </p>
    </div>
  );
}

/** Delivery status of a scan's report: sending / sent / failed (with retry). */
export function DeliveryStatus({ scanId }: { scanId: string }) {
  const { whatsapp } = useApp();
  const [delivery, setDelivery] = useState<WhatsAppDelivery | null>(null);
  const [retrying, setRetrying] = useState(false);

  const load = useCallback(() => getDelivery(scanId).then(setDelivery).catch(() => undefined), [scanId]);

  useEffect(() => {
    setDelivery(null);
    load();
  }, [load]);

  useEffect(() => {
    if (!delivery || (delivery.status !== "pending" && delivery.status !== "sending")) return;
    const t = setInterval(load, 1800);
    return () => clearInterval(t);
  }, [delivery, load]);

  if (!whatsapp?.registered) return null;

  const send = async () => {
    setRetrying(true);
    try {
      await resendWhatsApp(scanId);
      setDelivery({ status: "pending", error: null, updatedAt: null });
    } catch {
      setDelivery({ status: "failed", error: "Could not start sending. Is the server running?", updatedAt: null });
    } finally {
      setRetrying(false);
    }
  };

  const status = delivery?.status ?? "none";
  const tone =
    status === "sent" ? "border-emerald-300 bg-emerald-50 text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-500/10 dark:text-emerald-100"
    : status === "failed" ? "border-rose-300 bg-rose-50 text-rose-900 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-100"
    : "border-line bg-soft text-ink";

  return (
    <div key={status} className={`page-enter mb-5 flex flex-wrap items-center justify-between gap-3 rounded-2xl border p-3.5 text-sm ${tone}`} role="status">
      <p className="flex items-center gap-2.5">
        {status === "sent" ? <Check size={18} className="pop" /> : status === "failed" ? <AlertTriangle size={18} /> : status === "none" ? <MessageCircle size={18} /> : <Loader2 size={18} className="animate-spin" />}
        {status === "sent" && <span><b>Report sent to WhatsApp</b> ({whatsapp.masked}).</span>}
        {(status === "pending" || status === "sending") && <span>Sending your report to WhatsApp ({whatsapp.masked})...</span>}
        {status === "failed" && <span><b>Could not send to WhatsApp.</b> {delivery?.error}</span>}
        {status === "none" && <span>This report has not been sent to WhatsApp ({whatsapp.masked}).</span>}
      </p>
      {(status === "failed" || status === "none" || status === "sent") && (
        <button className="btn-soft !py-1.5 text-[13px]" onClick={send} disabled={retrying}>
          <Send size={14} /> {status === "sent" ? "Send again" : status === "failed" ? "Try again" : "Send to WhatsApp"}
        </button>
      )}
    </div>
  );
}
