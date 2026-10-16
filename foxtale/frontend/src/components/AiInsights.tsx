import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle, Bot, Camera, ChevronDown, Eye, Loader2, Lock, RotateCw, Sparkles, ThumbsDown, ThumbsUp,
  TriangleAlert,
} from "lucide-react";
import { useApp } from "../context/AppContext";
import {
  ApiError, getAiAnalysis, getAiStatus, runAiAnalysis, sendAiFeedback, setAiStatus,
} from "../services/api";
import type { AiAnalysis, AiConsentStatus, AiFinding, AiReferral } from "../types/analysis";
import { SectionTitle } from "./ui";

const SEVERITY_LEVEL = { none: "minimal", mild: "mild", moderate: "moderate", marked: "noticeable" } as const;
const SEVERITY_LABEL = { none: "Not seen", mild: "Mild", moderate: "Moderate", marked: "Prominent" } as const;
const POLL_MS = 1800;

function SeverityPill({ s }: { s: AiFinding["severity"] }) {
  return <span className={`pill lvl-${SEVERITY_LEVEL[s]}`}>{SEVERITY_LABEL[s]}</span>;
}

function FindingCard({ finding, feedbackEnabled, scanId }: { finding: AiFinding; feedbackEnabled: boolean; scanId: string }) {
  const { toast } = useApp();
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const [open, setOpen] = useState(false);

  const send = async (v: "up" | "down") => {
    setVote(v);
    try {
      await sendAiFeedback(scanId, finding.id, v);
      toast("Thanks -- that helps improve Foxtale AI.");
    } catch {
      setVote(null);
      toast("Could not save your feedback");
    }
  };

  return (
    <div className="page-enter rounded-2xl border border-line bg-card p-3.5">
      <button type="button" className="flex w-full items-start justify-between gap-3 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
        <span>
          <span className="block text-[13px] font-bold capitalize text-ink">{finding.type.replace(/_/g, " ")} <span className="font-normal text-muted">· {finding.region}</span></span>
          <span className="mt-1 flex items-center gap-2">
            <SeverityPill s={finding.severity} />
            <span className="text-[11px] text-muted">{Math.round(finding.confidence * 100)}% confidence</span>
          </span>
        </span>
        <ChevronDown size={16} className={`mt-1 shrink-0 text-muted transition-transform duration-300 ${open ? "rotate-180" : ""}`} />
      </button>
      <div className={`drawer ${open ? "open" : ""}`}>
        <div className="mt-2.5 space-y-2 text-[12.5px] leading-relaxed">
          <p className="text-ink">{finding.evidence}</p>
          {finding.uncertain_reason && <p className="flex items-start gap-1.5 text-muted"><Eye size={13} className="mt-0.5 shrink-0" /> {finding.uncertain_reason}</p>}
          {feedbackEnabled ? (
            <div className="flex items-center gap-2 pt-1">
              <span className="text-[11px] text-muted">Does this look right?</span>
              <button className={`chip !px-2.5 !py-1 ${vote === "up" ? "chip-on" : ""}`} aria-pressed={vote === "up"} onClick={() => send("up")}><ThumbsUp size={12} /></button>
              <button className={`chip !px-2.5 !py-1 ${vote === "down" ? "chip-on" : ""}`} aria-pressed={vote === "down"} onClick={() => send("down")}><ThumbsDown size={12} /></button>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}

function ReferralNote({ referral }: { referral: AiReferral }) {
  if (!referral.recommended) return null;
  return (
    <div className={`mt-4 rounded-2xl border p-4 ${referral.urgent ? "border-amber-300 bg-amber-50 dark:border-amber-500/40 dark:bg-amber-500/10" : "border-line bg-soft"}`} role="status">
      <p className="flex items-center gap-2 text-sm font-bold text-ink"><TriangleAlert size={16} className="text-amber-500" /> A dermatologist's opinion might help</p>
      <ul className="mt-2 space-y-1 text-[12.5px] text-muted">
        {referral.reasons.map((r) => <li key={r}>• {r}</li>)}
      </ul>
      <p className="mt-2 text-[11px] text-muted">{referral.disclaimer}</p>
    </div>
  );
}

function ConsentGate({ status, onEnable }: { status: AiConsentStatus; onEnable: (improve: boolean) => void }) {
  const [improve, setImprove] = useState(false);
  return (
    <div className="page-enter rounded-2xl border border-line bg-soft p-5">
      <p className="flex items-center gap-2.5 text-[14px] font-bold text-ink"><Bot size={18} className="text-fox-500" /> AI insights (beta)</p>
      <p className="mt-2 text-[12.5px] leading-relaxed text-muted">{status.disclosure}</p>
      {!status.configured && (
        <p className="mt-2 flex items-center gap-2 text-[12px] text-amber-600"><AlertTriangle size={14} /> Not set up on this server yet (see backend/.env.example). You can still turn this on to see the dry-run demo if AI_DRY_RUN is set.</p>
      )}
      <label className="mt-3 flex cursor-pointer items-start gap-2.5 text-[12.5px] text-ink">
        <input type="checkbox" className="mt-0.5 h-4 w-4 accent-fox-500" checked={improve} onChange={(e) => setImprove(e.target.checked)} />
        Also let me send thumbs up/down feedback on findings, to help improve Foxtale AI (stores the vote only, never the photo).
      </label>
      <button className="btn-cta mt-4 !py-2 text-[13px]" onClick={() => onEnable(improve)}>
        <Sparkles size={15} /> Turn on AI insights
      </button>
    </div>
  );
}

export default function AiInsights({ scanId, persisted, hasImage }: { scanId: string; persisted: boolean; hasImage: boolean }) {
  const { toast } = useApp();
  const [status, setStatus] = useState<AiConsentStatus | null>(null);
  const [ai, setAi] = useState<AiAnalysis | null>(null);
  const [busy, setBusy] = useState(false);
  const triedAuto = useRef(false);
  const timer = useRef<number | undefined>(undefined);

  const load = useCallback(() => {
    getAiAnalysis(scanId).then(setAi).catch(() => undefined);
  }, [scanId]);

  useEffect(() => {
    getAiStatus().then(setStatus).catch(() => undefined);
    setAi(null);
    triedAuto.current = false;
    load();
  }, [scanId, load]);

  // poll while a run is in flight
  useEffect(() => {
    window.clearTimeout(timer.current);
    if (ai && (ai.status === "pending")) {
      timer.current = window.setTimeout(load, POLL_MS);
    }
    return () => window.clearTimeout(timer.current);
  }, [ai, load]);

  // if AI is already on and this scan has never been analysed, kick off a run automatically
  // (covers an older scan viewed after turning AI on, or a saved scan that predates this feature)
  useEffect(() => {
    if (!status?.enabled || !ai || triedAuto.current) return;
    if (ai.status !== "none") return;
    triedAuto.current = true;
    if (!hasImage) return; // nothing to analyse -- stays "none", explained in the UI below
    runAiAnalysis(scanId).then(() => setAi({ status: "pending" })).catch(() => undefined);
  }, [status, ai, hasImage, scanId]);

  const enable = async (improve: boolean) => {
    setBusy(true);
    try {
      const next = await setAiStatus(true, improve);
      setStatus(next);
      toast("AI insights turned on");
    } catch {
      toast("Could not turn that on. Is the server running?");
    } finally {
      setBusy(false);
    }
  };

  const rerun = async () => {
    setBusy(true);
    try {
      await runAiAnalysis(scanId);
      setAi({ status: "pending" });
    } catch (err) {
      toast(err instanceof ApiError ? err.message : "Could not start the AI analysis");
    } finally {
      setBusy(false);
    }
  };

  if (!status) return null;

  return (
    <section className="card mt-6 scroll-mt-24 p-5 sm:p-6">
      <SectionTitle title="AI Insights" subtitle="A written description from a vision AI, grounded in the measurements above. Separate from your visible-skin score." icon={<Bot size={18} />} />

      <div className="mt-4">
        {!status.enabled ? (
          <ConsentGate status={status} onEnable={enable} />
        ) : ai === null ? (
          <div className="flex items-center gap-2 text-sm text-muted" aria-busy="true"><Loader2 size={16} className="animate-spin" /> Loading...</div>
        ) : ai.status === "none" ? (
          !hasImage ? (
            <p className="flex items-start gap-2 rounded-2xl bg-soft p-3.5 text-[12.5px] text-muted">
              <Camera size={15} className="mt-0.5 shrink-0" /> {persisted
                ? "No photo was saved for this scan, so there is nothing to send for AI insights. Turn on \"Save scan photos\" in Privacy before your next scan."
                : "This scan is not saved, so AI insights were not kept for it."}
            </p>
          ) : (
            <div className="flex items-center gap-2 text-sm text-muted" aria-busy="true"><Loader2 size={16} className="animate-spin" /> Starting the AI analysis...</div>
          )
        ) : ai.status === "pending" || ai.status === "rate_limited" ? (
          <p className="flex items-center gap-2.5 rounded-2xl bg-soft p-3.5 text-sm text-ink" role="status">
            {ai.status === "pending" ? <><Loader2 size={16} className="animate-spin" /> Analysing with AI...</> : <><AlertTriangle size={16} className="text-amber-500" /> A few AI calls were made recently -- this will retry shortly.</>}
          </p>
        ) : ai.status === "failed" ? (
          <div className="rounded-2xl border border-rose-300 bg-rose-50 p-4 text-sm text-rose-900 dark:border-rose-500/40 dark:bg-rose-500/10 dark:text-rose-100">
            <p className="flex items-center gap-2 font-bold"><AlertTriangle size={16} /> The AI call did not complete.</p>
            {ai.error && <p className="mt-1 text-[12.5px]">{ai.error}</p>}
            {hasImage && <button className="btn-soft mt-3 !py-1.5 text-[13px]" onClick={rerun} disabled={busy}><RotateCw size={14} /> Try again</button>}
          </div>
        ) : ai.result ? (
          <div className="space-y-4">
            {ai.status === "fallback" && (
              <p className="flex items-start gap-2 rounded-2xl bg-soft p-3 text-[12px] text-muted"><Bot size={14} className="mt-0.5 shrink-0" /> The written AI description was not available this time, so this is built from the on-device measurements only.</p>
            )}
            <p className="text-sm leading-relaxed text-ink">{ai.result.overall_summary}</p>

            {ai.result.retake_advice && (
              <p className="flex items-start gap-2 rounded-2xl border border-amber-300 bg-amber-50 p-3 text-[12.5px] text-amber-900 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-100">
                <Camera size={14} className="mt-0.5 shrink-0" /> {ai.result.retake_advice}
              </p>
            )}

            {ai.result.findings.length > 0 && (
              <div className="grid gap-2.5 sm:grid-cols-2">
                {ai.result.findings.map((f) => <FindingCard key={f.id} finding={f} feedbackEnabled={status.improveConsent} scanId={scanId} />)}
              </div>
            )}

            {ai.result.routine_suggestions.length > 0 && (
              <div>
                <p className="label-caps mb-2">AI routine suggestions</p>
                <ul className="space-y-1.5 text-[12.5px] text-ink">
                  {ai.result.routine_suggestions.map((s) => <li key={s.suggestion} className="flex gap-2"><span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fox-500" /> {s.suggestion}</li>)}
                </ul>
              </div>
            )}
            {ai.result.lifestyle_notes.length > 0 && (
              <p className="text-[12px] text-muted">{ai.result.lifestyle_notes.join(" ")}</p>
            )}

            {ai.referral && <ReferralNote referral={ai.referral} />}

            {ai.result.moderation_redacted && (
              <p className="text-[11px] text-muted">Part of this response was removed by the app's safety filter before being shown.</p>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 border-t border-line pt-3">
              <p className="text-[11px] text-muted">
                {ai.provider && ai.provider !== "mock" ? `${ai.provider} · ${ai.model}` : "Local test mode"}
                {ai.fromCache ? " · cached" : ""}
              </p>
              {hasImage && (
                <button className="btn-soft !py-1.5 text-[13px]" onClick={rerun} disabled={busy}>
                  {busy ? <Loader2 size={14} className="animate-spin" /> : <RotateCw size={14} />} Re-run
                </button>
              )}
            </div>
          </div>
        ) : null}
      </div>

      {status.enabled && (
        <p className="mt-4 flex items-center gap-2 text-[11px] text-muted"><Lock size={12} /> AI insights can be turned off any time in Settings. <Link to="/settings" className="font-bold text-fox-text underline dark:text-fox-300">Open Settings</Link></p>
      )}
    </section>
  );
}
