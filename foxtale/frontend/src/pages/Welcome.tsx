import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Camera, ClipboardList, ShieldCheck, Sparkles } from "lucide-react";
import ProfileForm from "../components/ProfileForm";
import { useApp } from "../context/AppContext";
import type { Profile } from "../services/api";

const SLIDES = [
  { icon: Camera, title: "Scan your face", body: "Take a quick photo. Foxtale spots acne, dark spots, texture, pores, under-eye darkness, redness and more, live on your camera and in a full report.", tone: "bg-orange-50 text-fox-500 dark:bg-fox-500/15" },
  { icon: Sparkles, title: "Understand your skin", body: "You get an overall score, your skin type and tone, and a plain-words explanation of every finding, with where on your face it is.", tone: "bg-violet-50 text-violet-600 dark:bg-violet-500/15" },
  { icon: ClipboardList, title: "Get a routine that fits", body: "A simple Foxtale routine matched to your scan and your answers, with why each product helps. Track it daily and watch your progress.", tone: "bg-emerald-50 text-emerald-600 dark:bg-emerald-500/15" },
];

export default function Welcome() {
  const navigate = useNavigate();
  const { saveProfile, toast, profile } = useApp();
  const [step, setStep] = useState(0); // 0..2 slides, 3 questionnaire
  const [busy, setBusy] = useState(false);

  const finish = async (p: Profile) => {
    setBusy(true);
    try {
      await saveProfile(p);
      toast("You're all set");
      navigate("/", { replace: true });
    } catch {
      toast("Could not save your answers. Is the server running?");
    } finally {
      setBusy(false);
    }
  };

  const skip = async () => {
    await finish({ name: "", age_range: "", gender: "", goals: [], sensitive_skin: false, pregnant: false, allergies: "", budget: "any", onboarded: true });
  };

  return (
    <div className="mx-auto flex min-h-[80vh] max-w-2xl flex-col justify-center py-4">
      <div className="mb-8 flex items-center justify-center gap-2.5">
        <img src="/logo_mark.png" alt="" className="h-10 w-10 object-contain" />
        <span className="text-2xl font-extrabold text-ink">fox<span className="text-fox-500">tale</span></span>
      </div>

      {step < 3 ? (
        <div key={step} className="card page-enter p-8 text-center sm:p-10">
          {(() => {
            const s = SLIDES[step];
            const Icon = s.icon;
            return (
              <>
                <span className={`pop float mx-auto flex h-20 w-20 items-center justify-center rounded-full ${s.tone}`}><Icon size={34} /></span>
                <h1 className="mt-6 text-2xl font-extrabold text-ink sm:text-3xl">{s.title}</h1>
                <p className="mx-auto mt-3 max-w-md text-muted">{s.body}</p>
              </>
            );
          })()}
          <div className="mt-6 flex justify-center gap-2" aria-hidden>
            {SLIDES.map((_, i) => <span key={i} className={`h-2 rounded-full transition-all duration-300 ${i === step ? "w-7 bg-fox-500" : "w-2 bg-line"}`} />)}
          </div>
          <div className="mt-8 flex flex-col items-center gap-3">
            <button className="btn-cta" onClick={() => setStep(step + 1)}>{step < 2 ? "Next" : "Set up my profile"} <ArrowRight size={18} /></button>
            <button className="text-sm font-semibold text-muted hover:text-ink" onClick={skip}>Skip for now</button>
          </div>
        </div>
      ) : (
        <div className="card page-enter p-6 sm:p-8">
          <h1 className="text-2xl font-extrabold text-ink">A few quick questions</h1>
          <p className="mt-1 text-sm text-muted">This makes your product suggestions safer and more personal. You can change any answer later in Settings.</p>
          <div className="mt-6"><ProfileForm initial={profile} onSubmit={finish} submitLabel="Finish and go to my dashboard" busy={busy} /></div>
          <p className="mt-5 flex items-start gap-2 text-xs text-muted"><ShieldCheck size={14} className="mt-0.5 shrink-0 text-emerald-600" /> Your answers are stored only on your own server and used only to personalise suggestions.</p>
        </div>
      )}
    </div>
  );
}
