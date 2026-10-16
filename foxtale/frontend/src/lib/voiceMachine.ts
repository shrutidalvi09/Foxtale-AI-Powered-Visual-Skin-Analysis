/**
 * Pure turn-taking state machine for Fox, the voice assistant, kept separate from React/DOM/network
 * so it is trivially unit-testable (see lib/__tests__/voiceMachine.test.ts). All side effects
 * (starting the recognizer, calling the backend, speaking) live in context/VoiceContext.tsx,
 * which drives this reducer and reacts to its output.
 *
 * States:
 *   idle       -- not listening, not speaking, nothing pending.
 *   listening  -- mic is active, waiting for a final transcript.
 *   thinking   -- a final transcript was captured and is being matched/sent to the backend.
 *   speaking   -- TTS is playing Fox's reply.
 *   confirming -- an irreversible action was proposed; the next transcript is a yes/no answer.
 *
 * Barge-in: a PARTIAL result while speaking immediately cuts to "listening" -- the caller
 * (VoiceContext) is responsible for actually stopping the TTS when it sees this transition.
 */

export type VoiceState = "idle" | "listening" | "thinking" | "speaking" | "confirming";

export type VoiceEvent =
  | { type: "PUSH_TO_TALK" }
  | { type: "WAKE_DETECTED" }
  | { type: "PARTIAL"; text: string }
  | { type: "FINAL"; text: string }
  | { type: "SILENCE_TIMEOUT" }
  | { type: "REPLY_RECEIVED"; needsConfirmation: boolean; hasSpeech: boolean }
  | { type: "SPEECH_DONE" }
  | { type: "BARGE_IN" }
  | { type: "STOP" }
  | { type: "ERROR" };

export interface VoiceMachineState {
  state: VoiceState;
  liveCaption: string;
  /** True only on the transition into "listening" caused by a barge-in -- lets the caller
   * know it must call speaker.stop() as a side effect of this transition. */
  justBargedIn: boolean;
}

export const initialVoiceMachineState: VoiceMachineState = { state: "idle", liveCaption: "", justBargedIn: false };

export function voiceReducer(s: VoiceMachineState, e: VoiceEvent): VoiceMachineState {
  switch (e.type) {
    case "PUSH_TO_TALK": {
      if (s.state === "speaking") return { state: "listening", liveCaption: "", justBargedIn: true };
      if (s.state === "idle" || s.state === "confirming") return { state: "listening", liveCaption: "", justBargedIn: false };
      return s;
    }
    case "WAKE_DETECTED":
      return s.state === "idle" ? { state: "listening", liveCaption: "", justBargedIn: false } : s;
    case "PARTIAL": {
      if (s.state === "speaking") return { state: "listening", liveCaption: e.text, justBargedIn: true };
      if (s.state === "listening" || s.state === "confirming") return { ...s, liveCaption: e.text, justBargedIn: false };
      return s;
    }
    case "FINAL":
      if (s.state === "listening" || s.state === "confirming")
        return { state: "thinking", liveCaption: e.text, justBargedIn: false };
      return s;
    case "SILENCE_TIMEOUT":
      return s.state === "listening" ? { state: "idle", liveCaption: "", justBargedIn: false } : s;
    case "REPLY_RECEIVED": {
      if (e.needsConfirmation) return { state: "confirming", liveCaption: s.liveCaption, justBargedIn: false };
      return e.hasSpeech
        ? { state: "speaking", liveCaption: s.liveCaption, justBargedIn: false }
        : { state: "idle", liveCaption: "", justBargedIn: false };
    }
    case "SPEECH_DONE":
      return s.state === "speaking" ? { state: "idle", liveCaption: "", justBargedIn: false } : s;
    case "BARGE_IN":
      return s.state === "speaking" ? { state: "listening", liveCaption: "", justBargedIn: true } : s;
    case "STOP":
      return { state: "idle", liveCaption: "", justBargedIn: false };
    case "ERROR":
      return { state: "idle", liveCaption: "", justBargedIn: false };
    default:
      return s;
  }
}

/** Loose, intentionally simple yes/no detector for answering a spoken confirmation
 * question -- a best-effort heuristic, not a trained classifier (see README TODO note). */
export function parseYesNo(text: string, lang: "en" | "hi" | "mr"): boolean | null {
  const t = text.toLowerCase();
  const YES: Record<string, RegExp> = {
    en: /\b(yes|yeah|yep|sure|confirm|do it|go ahead|okay|ok)\b/,
    hi: /(हाँ|हां|ठीक है|कर दो|हा)/,
    mr: /(हो|ठीक आहे|करा)/,
  };
  const NO: Record<string, RegExp> = {
    en: /\b(no|nope|cancel|stop|never ?mind|don'?t)\b/,
    hi: /(नहीं|रद्द|मत करो)/,
    mr: /(नको|रद्द)/,
  };
  if (NO[lang].test(t)) return false;
  if (YES[lang].test(t)) return true;
  return null;
}
