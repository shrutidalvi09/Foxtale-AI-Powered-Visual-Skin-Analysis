import { createContext, useCallback, useContext, useEffect, useMemo, useReducer, useRef, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { INTENT_CONFIDENCE_THRESHOLD, matchLocal } from "../lib/intentMatcher";
import { MockRecognizer, MockSpeaker, WebSpeechRecognizer, WebSpeaker } from "../lib/speech";
import type { Speaker, SpeechRecognizer } from "../lib/speech";
import { initialVoiceMachineState, parseYesNo, voiceReducer } from "../lib/voiceMachine";
import { askGuide, getInsights, getVoiceStatus, setVoiceStatus as apiSetVoiceStatus, wipeData } from "../services/api";
import type { VoiceAction, VoiceActionType, VoiceLang, VoiceStatus } from "../types/analysis";
import { useApp } from "./AppContext";

const SESSION_KEY = "foxtale_voice_session";
const WAKE_PHRASES: Record<VoiceLang, string[]> = {
  en: ["hey fox", "ok fox", "okay fox", "hey foxtale", "ok foxtale"],
  hi: ["हे फॉक्स", "ओके फॉक्स", "हे फॉक्सटेल"],
  mr: ["हे फॉक्स", "ओके फॉक्स", "हे फॉक्सटेल"],
};

const ACTION_PATH: Partial<Record<VoiceActionType, string>> = {
  navigate_dashboard: "/",
  navigate_scan: "/scan",
  navigate_analysis: "/analysis",
  navigate_routine: "/routine",
  navigate_diary: "/diary",
  navigate_shop: "/shop",
  navigate_ingredient_check: "/ingredients",
  navigate_history: "/history",
  navigate_compare: "/compare",
  navigate_privacy: "/privacy",
  navigate_settings: "/settings",
  start_scan: "/scan",
  retake_photo: "/scan",
  show_last_scan: "/analysis",
  compare_last_week: "/compare",
};

const DONE_SPEECH: Record<VoiceLang, string> = {
  en: "All done -- everything's cleared out, just like we agreed.",
  hi: "हो गया -- जैसा तय किया था, सब कुछ साफ़ कर दिया।",
  mr: "झालं -- ठरल्याप्रमाणे सगळं साफ केलं.",
};
const CLARIFY_YES_NO: Record<VoiceLang, string> = {
  en: "Just say yes or no for me, okay?",
  hi: "बस हां या नहीं बोल दो, ठीक है?",
  mr: "फक्त हो किंवा नाही सांग, ठीक आहे?",
};
const MIC_DENIED: Record<VoiceLang, string> = {
  en: "I need microphone access to hear you! You can turn it on in your browser's site settings.",
  hi: "तुम्हें सुनने के लिए मुझे माइक्रोफ़ोन चाहिए! तुम इसे ब्राउज़र की साइट सेटिंग्स में चालू कर सकते हो।",
  mr: "तुला ऐकण्यासाठी मला मायक्रोफोन हवा आहे! तू तो ब्राउझरच्या साइट सेटिंग्जमध्ये सुरू करू शकतोस.",
};
const SCORE_DETAIL = (score: number, lang: VoiceLang): string => {
  if (lang === "hi") return `तुम्हारा नया स्कोर सौ में से ${score} है। बस याद रखना, ये सिर्फ़ फोटो में जो दिखा उस पर आधारित है, कोई असली जांच नहीं।`;
  if (lang === "mr") return `तुझा नवीन स्कोर शंभरपैकी ${score} आहे. लक्षात ठेव, हे फक्त फोटोत दिसलेल्यावर आधारित आहे, खरी तपासणी नाही.`;
  return `Your latest score is ${score} out of a hundred. Just remember, this is only based on what's visible in the photo, not a real check-up, okay?`;
};
const NO_HISTORY_LOCAL: Record<VoiceLang, string> = {
  en: "I haven't said anything yet!",
  hi: "मैंने अभी तक कुछ कहा ही नहीं!",
  mr: "मी अजून काहीच सांगितलेलं नाही!",
};
const NO_SCORE_YET: Record<VoiceLang, string> = {
  en: "You haven't done a scan yet, so there's nothing for me to tell you! Want to do one together?",
  hi: "तुमने अभी तक कोई स्कैन नहीं किया, तो बताने के लिए कुछ है ही नहीं! साथ में एक करें?",
  mr: "तू अजून स्कॅन केलेला नाहीस, त्यामुळे सांगायला काही नाही! एकत्र करूया का?",
};

export type VoicePlaybackState = "idle" | "listening" | "thinking" | "speaking" | "confirming";

interface VoiceContextValue {
  status: VoiceStatus | null;
  state: VoicePlaybackState;
  liveCaption: string;
  muted: boolean;
  micError: string | null;
  recognizerSupported: boolean;
  pushToTalk: () => void;
  stopAll: () => void;
  toggleMute: () => void;
  setLanguage: (lang: VoiceLang) => Promise<void>;
  setSpeed: (speed: number) => Promise<void>;
  setVolume: (volume: number) => Promise<void>;
  setEnabled: (enabled: boolean) => Promise<void>;
  setWakeWordEnabled: (enabled: boolean) => Promise<void>;
  setCaptionsEnabled: (enabled: boolean) => Promise<void>;
  setTranscriptsConsent: (enabled: boolean) => Promise<void>;
  /** For other components (Analysis "read aloud", hands-free scan coaching) to speak
   * without going through the mic/intent pipeline. */
  speakDirect: (text: string) => Promise<void>;
}

const VoiceContext = createContext<VoiceContextValue | undefined>(undefined);

function sessionId(): string {
  try {
    let id = localStorage.getItem(SESSION_KEY);
    if (!id) {
      id = crypto.randomUUID();
      localStorage.setItem(SESSION_KEY, id);
    }
    return id;
  } catch {
    return "session-fallback";
  }
}

function useMockMode(): boolean {
  // Frozen at first mount: client-side navigation (react-router's navigate()) drops the
  // query string from the URL, and re-reading it on every render would silently flip the
  // test hooks off after the very first <Link>/navigate() call.
  const [mockMode] = useState(() => {
    try {
      return new URLSearchParams(window.location.search).get("voiceMock") === "1";
    } catch {
      return false;
    }
  });
  return mockMode;
}

export function VoiceProvider({ children }: { children: ReactNode }) {
  const { profile, toast, dataVersion } = useApp();
  const navigate = useNavigate();
  const mockMode = useMockMode();

  const [status, setStatus] = useState<VoiceStatus | null>(null);
  const [muted, setMuted] = useState(false);
  const [micError, setMicError] = useState<string | null>(null);
  const [machine, dispatch] = useReducer(voiceReducer, initialVoiceMachineState);
  const [insightsCache, setInsightsCache] = useState<{ score: number | null; lastScan: string | null }>({ score: null, lastScan: null });

  const recognizerRef = useRef<SpeechRecognizer>(mockMode ? new MockRecognizer() : new WebSpeechRecognizer());
  const speakerRef = useRef<Speaker>(mockMode ? new MockSpeaker() : new WebSpeaker());
  const awaitingConfirmRef = useRef(false);
  const pendingActionRef = useRef<VoiceAction | null>(null);
  const clarifyAttemptsRef = useRef(0);
  const pageRef = useRef<string>(window.location.pathname);
  const replySpeechRef = useRef<string>("");
  const replyActionRef = useRef<VoiceAction | null>(null);
  const lastSpokenRef = useRef<string>("");
  const idRef = useRef(sessionId());

  useEffect(() => {
    pageRef.current = window.location.pathname;
  });

  useEffect(() => {
    getVoiceStatus().then(setStatus).catch(() => undefined);
  }, []);

  useEffect(() => {
    getInsights()
      .then((i) => setInsightsCache({ score: i.latest?.analysis.overall_score ?? null, lastScan: i.latest?.timestamp ?? null }))
      .catch(() => undefined);
  }, [dataVersion]);

  // dev/test hook: drive the whole voice flow from a headless browser with no real mic.
  useEffect(() => {
    if (!mockMode) return;
    const mock = recognizerRef.current as MockRecognizer;
    const speakerMock = speakerRef.current as MockSpeaker;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    (window as any).__voiceTestHooks__ = {
      say: (text: string, isFinal = true) => mock.inject(text, isFinal),
      micError: (err: string) => mock.injectError(err),
      getState: () => machine.state,
      getCaption: () => machine.liveCaption,
      getSpoken: () => speakerMock.spoken.slice(),
      getStatus: () => status,
      getMuted: () => muted,
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mockMode, machine.state, machine.liveCaption, status, muted]);

  const lang = status?.language ?? "en";
  const speed = status?.speed ?? 1.0;
  const volume = muted ? 0 : status?.volume ?? 1.0;

  const speak = useCallback(
    (text: string): Promise<void> => {
      if (!text || muted) return Promise.resolve();
      return speakerRef.current.speak(text, { lang, rate: speed, volume });
    },
    [lang, speed, volume, muted]
  );

  const speakDirect = useCallback((text: string) => speak(text), [speak]);

  const runAction = useCallback(
    async (action: VoiceAction | null) => {
      if (!action || action.type === "none") return;
      switch (action.type) {
        case "mute":
          setMuted(true);
          return;
        case "unmute":
          setMuted(false);
          return;
        case "skip_guide":
          toast("Fox will stay quiet unless you ask.");
          return;
        case "wipe_data":
          try {
            await wipeData();
            await speak(DONE_SPEECH[lang]);
          } catch {
            toast("Could not delete your data just now.");
          }
          navigate("/privacy");
          return;
        case "explain_score": {
          if (insightsCache.score == null) {
            await speak(NO_SCORE_YET[lang]);
          } else {
            await speak(SCORE_DETAIL(insightsCache.score, lang));
          }
          return;
        }
        case "retake_photo":
          window.dispatchEvent(new CustomEvent("foxtale:voice-retake"));
          navigate("/scan");
          return;
        default: {
          const path = ACTION_PATH[action.type];
          if (path) navigate(path);
        }
      }
    },
    [lang, navigate, speak, toast, insightsCache.score]
  );

  const stateSummary = useCallback(() => {
    const onboarded = profile?.onboarded ? "yes" : "no";
    const score = insightsCache.score != null ? String(insightsCache.score) : "none";
    return `onboarded=${onboarded}; lastScanScore=${score}; lastScanAt=${insightsCache.lastScan ?? "none"}`;
  }, [profile?.onboarded, insightsCache]);

  const handleTranscript = useCallback(
    async (text: string) => {
      if (!text.trim()) {
        dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
        return;
      }

      if (awaitingConfirmRef.current) {
        const yn = parseYesNo(text, lang);
        if (yn === null) {
          if (clarifyAttemptsRef.current >= 1) {
            awaitingConfirmRef.current = false;
            pendingActionRef.current = null;
            replySpeechRef.current = "";
            dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
            return;
          }
          clarifyAttemptsRef.current += 1;
          awaitingConfirmRef.current = true;
          replySpeechRef.current = CLARIFY_YES_NO[lang];
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: true, hasSpeech: true });
          return;
        }
        awaitingConfirmRef.current = false;
        clarifyAttemptsRef.current = 0;
        try {
          const reply = await askGuide({
            sessionId: idRef.current, text, lang, page: pageRef.current, stateSummary: stateSummary(), confirm: yn,
          });
          replySpeechRef.current = reply.speech;
          replyActionRef.current = reply.action;
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: Boolean(reply.speech) });
        } catch {
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
        }
        return;
      }

      const local = matchLocal(text, lang);
      if (local && local.confidence >= INTENT_CONFIDENCE_THRESHOLD) {
        if (local.type === "stop_speaking") {
          speakerRef.current.stop();
          replySpeechRef.current = "";
          replyActionRef.current = null;
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
          return;
        }
        if (local.type === "repeat") {
          replySpeechRef.current = lastSpokenRef.current || NO_HISTORY_LOCAL[lang];
          replyActionRef.current = null;
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: true });
          return;
        }
        if (local.type === "louder" || local.type === "quieter") {
          const current = status?.volume ?? 1;
          const next = local.type === "louder" ? Math.min(1, current + 0.2) : Math.max(0, current - 0.2);
          apiSetVoiceStatus({ volume: next }).then(setStatus).catch(() => undefined);
          replySpeechRef.current = "";
          replyActionRef.current = null;
          dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
          return;
        }
        replyActionRef.current = { type: local.type, params: {} };
        replySpeechRef.current = "";
        dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
        await runAction(replyActionRef.current);
        return;
      }

      try {
        const reply = await askGuide({
          sessionId: idRef.current, text, lang, page: pageRef.current, stateSummary: stateSummary(),
        });
        replySpeechRef.current = reply.speech;
        replyActionRef.current = reply.needs_confirmation ? null : reply.action;
        if (reply.needs_confirmation) {
          pendingActionRef.current = reply.action;
          awaitingConfirmRef.current = true;
        }
        dispatch({ type: "REPLY_RECEIVED", needsConfirmation: reply.needs_confirmation, hasSpeech: Boolean(reply.speech) });
      } catch {
        replySpeechRef.current = "";
        dispatch({ type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
      }
    },
    [lang, runAction, speak, stateSummary, status?.volume]
  );

  // ----------------------------------------------------------------- recognizer lifecycle

  useEffect(() => {
    const rec = recognizerRef.current;
    rec.onResult(({ text, isFinal }) => {
      if (!isFinal) {
        dispatch({ type: "PARTIAL", text });
        return;
      }
      dispatch({ type: "FINAL", text });
    });
    rec.onError((err) => {
      if (err === "not-allowed" || err === "not_supported") {
        setMicError(MIC_DENIED[lang]);
      }
      dispatch({ type: "ERROR" });
    });
    rec.onEnd(() => {
      // no-op: state transitions drive whether we restart, below
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const rec = recognizerRef.current;
    // The mic stays open during "speaking" too, so a barge-in (the user talking over Fox)
    // can be detected -- on real hardware without echo cancellation this can pick up
    // Fox's own voice as a false trigger; see README TODO note.
    if (machine.state === "listening" || machine.state === "confirming" || machine.state === "speaking") {
      setMicError(null);
      rec.start(lang);
    } else if (machine.state === "idle" && status?.wakeWordEnabled) {
      rec.start(lang); // passive, foreground-only wake-phrase listening
    } else if (machine.state === "idle") {
      rec.stop();
    }
  }, [machine.state, lang, status?.wakeWordEnabled]);

  // wake-phrase detection while idle
  useEffect(() => {
    if (machine.state !== "idle" || !status?.wakeWordEnabled) return;
    if (machine.liveCaption) {
      const normalized = machine.liveCaption.toLowerCase();
      const hit = WAKE_PHRASES[lang].find((p) => normalized.includes(p));
      if (hit) {
        const rest = normalized.slice(normalized.indexOf(hit) + hit.length).trim();
        dispatch({ type: "WAKE_DETECTED" });
        if (rest) dispatch({ type: "FINAL", text: rest });
      }
    }
  }, [machine.liveCaption, machine.state, status?.wakeWordEnabled, lang]);

  // "thinking" -> process the final transcript
  useEffect(() => {
    if (machine.state === "thinking") {
      handleTranscript(machine.liveCaption);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machine.state]);

  // "speaking"/"confirming" -> actually speak, then settle
  useEffect(() => {
    if (machine.state === "speaking") {
      lastSpokenRef.current = replySpeechRef.current || lastSpokenRef.current;
      speak(replySpeechRef.current).then(() => {
        const action = replyActionRef.current;
        replyActionRef.current = null;
        dispatch({ type: "SPEECH_DONE" });
        if (action) runAction(action);
      });
    } else if (machine.state === "confirming" && replySpeechRef.current) {
      speak(replySpeechRef.current);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [machine.state]);

  const pushToTalk = useCallback(() => {
    if (!status?.enabled) {
      toast("Turn on the voice assistant in Settings first.");
      return;
    }
    dispatch({ type: "PUSH_TO_TALK" });
  }, [status?.enabled, toast]);

  const stopAll = useCallback(() => {
    speakerRef.current.stop();
    recognizerRef.current.stop();
    awaitingConfirmRef.current = false;
    dispatch({ type: "STOP" });
  }, []);

  const toggleMute = useCallback(() => {
    setMuted((m) => {
      if (!m) speakerRef.current.stop();
      return !m;
    });
  }, []);

  const applyStatusPatch = useCallback(async (patch: Parameters<typeof apiSetVoiceStatus>[0]) => {
    const next = await apiSetVoiceStatus(patch);
    setStatus(next);
  }, []);

  const value = useMemo<VoiceContextValue>(
    () => ({
      status,
      state: machine.state,
      liveCaption: machine.liveCaption,
      muted,
      micError,
      recognizerSupported: recognizerRef.current.supported,
      pushToTalk,
      stopAll,
      toggleMute,
      setLanguage: (l) => applyStatusPatch({ language: l }),
      setSpeed: (s) => applyStatusPatch({ speed: s }),
      setVolume: (v) => applyStatusPatch({ volume: v }),
      setEnabled: (e) => applyStatusPatch({ enabled: e }),
      setWakeWordEnabled: (e) => applyStatusPatch({ wakeWordEnabled: e }),
      setCaptionsEnabled: (e) => applyStatusPatch({ captionsEnabled: e }),
      setTranscriptsConsent: (e) => applyStatusPatch({ transcriptsConsent: e }),
      speakDirect,
    }),
    [status, machine.state, machine.liveCaption, muted, micError, pushToTalk, stopAll, toggleMute, applyStatusPatch, speakDirect]
  );

  return <VoiceContext.Provider value={value}>{children}</VoiceContext.Provider>;
}

export function useVoice(): VoiceContextValue {
  const ctx = useContext(VoiceContext);
  if (!ctx) throw new Error("useVoice must be used inside <VoiceProvider>");
  return ctx;
}
