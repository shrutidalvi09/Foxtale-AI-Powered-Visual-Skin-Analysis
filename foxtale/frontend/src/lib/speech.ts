/**
 * Swappable speech interfaces for Fox, the voice assistant. `WebSpeechRecognizer`/`WebSpeaker` wrap
 * the browser's Web Speech API (SpeechRecognition + speechSynthesis) -- the only
 * implementation that ships today. `MockRecognizer`/`MockSpeaker` exist so the whole voice
 * flow (intent matching, the turn-taking state machine, barge-in, app actions) can be unit-
 * and integration-tested, and so it can be driven from a headless browser with no real
 * microphone (see components/VoiceAssistant.tsx's `?voiceMock=1` hook).
 *
 * No raw audio ever leaves this module: SpeechRecognition does on-device (or browser-vendor)
 * recognition and hands back text only, which is all that is ever sent to the backend.
 */

export type VoiceLang = "en" | "hi" | "mr";

export const LANG_TAG: Record<VoiceLang, string> = { en: "en-IN", hi: "hi-IN", mr: "mr-IN" };

export interface RecognitionResult {
  text: string;
  isFinal: boolean;
}

export interface SpeechRecognizer {
  readonly supported: boolean;
  start(lang: VoiceLang): void;
  stop(): void;
  onResult(cb: (r: RecognitionResult) => void): void;
  onEnd(cb: () => void): void;
  onError(cb: (err: string) => void): void;
}

export interface SpeakOptions {
  lang?: VoiceLang;
  rate?: number;
  volume?: number;
}

export interface Speaker {
  readonly supported: boolean;
  readonly speaking: boolean;
  speak(text: string, opts?: SpeakOptions): Promise<void>;
  stop(): void;
  onSpeakingChange(cb: (speaking: boolean) => void): void;
}

// ------------------------------------------------------------------------- Web Speech API

type SpeechRecognitionCtor = new () => SpeechRecognitionLike;
interface SpeechRecognitionLike extends EventTarget {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  onresult: ((event: unknown) => void) | null;
  onend: (() => void) | null;
  onerror: ((event: { error?: string }) => void) | null;
}

function getRecognitionCtor(): SpeechRecognitionCtor | null {
  const w = window as unknown as Record<string, unknown>;
  return (w.SpeechRecognition || w.webkitSpeechRecognition || null) as SpeechRecognitionCtor | null;
}

export class WebSpeechRecognizer implements SpeechRecognizer {
  private ctor = getRecognitionCtor();
  private instance: SpeechRecognitionLike | null = null;
  private resultCb: ((r: RecognitionResult) => void) | null = null;
  private endCb: (() => void) | null = null;
  private errorCb: ((err: string) => void) | null = null;

  get supported(): boolean {
    return this.ctor !== null;
  }

  start(lang: VoiceLang): void {
    if (!this.ctor) {
      this.errorCb?.("not_supported");
      return;
    }
    this.instance = new this.ctor();
    this.instance.continuous = true;
    this.instance.interimResults = true;
    this.instance.lang = LANG_TAG[lang];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    this.instance.onresult = (event: any) => {
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        this.resultCb?.({ text: r[0].transcript as string, isFinal: Boolean(r.isFinal) });
      }
    };
    this.instance.onend = () => this.endCb?.();
    this.instance.onerror = (event) => this.errorCb?.(event.error || "unknown");
    try {
      this.instance.start();
    } catch {
      this.errorCb?.("start_failed");
    }
  }

  stop(): void {
    this.instance?.stop();
  }

  onResult(cb: (r: RecognitionResult) => void): void {
    this.resultCb = cb;
  }

  onEnd(cb: () => void): void {
    this.endCb = cb;
  }

  onError(cb: (err: string) => void): void {
    this.errorCb = cb;
  }
}

// The Web Speech API has no standard gender field on SpeechSynthesisVoice -- only `name`,
// `lang`, `voiceURI`, `default`, `localService`. Some platforms label it directly ("Google UK
// English Female"); most don't, so this also matches well-known female voice names shipped by
// Chrome/Edge (Google/Microsoft), Windows SAPI and macOS across English, Hindi and Marathi.
// Best-effort: if nothing on the matching-language voice list is recognisably female, the
// first available voice for that language is used rather than leaving speech silent.
const FEMALE_VOICE_HINTS = [
  "female", "zira", "samantha", "susan", "linda", "heera", "veena", "kalpana", "lekha",
  "swara", "aarohi", "hazel", "karen", "moira", "tessa", "fiona", "victoria", "salli",
  "joanna", "kendra", "ivy", "neerja", "aditi", "raveena", "priya",
];

function pickVoice(voices: SpeechSynthesisVoice[], lang: VoiceLang): SpeechSynthesisVoice | undefined {
  const tag = LANG_TAG[lang];
  const base = tag.slice(0, 2).toLowerCase();
  const exact = voices.filter((v) => v.lang === tag);
  const pool = exact.length ? exact : voices.filter((v) => v.lang.toLowerCase().startsWith(base));
  if (!pool.length) return undefined;
  return pool.find((v) => FEMALE_VOICE_HINTS.some((hint) => v.name.toLowerCase().includes(hint))) ?? pool[0];
}

/** `getVoices()` returns an empty list until the browser has asynchronously loaded its voice
 * catalogue (most noticeably in Chrome) -- calling it synchronously right before the first
 * `speak()` routinely returns nothing, silently skipping voice selection (and the female-voice
 * preference with it). Cached across calls since the catalogue doesn't change at runtime. */
let voicesPromise: Promise<SpeechSynthesisVoice[]> | null = null;
function loadVoices(): Promise<SpeechSynthesisVoice[]> {
  if (!voicesPromise) {
    voicesPromise = new Promise((resolve) => {
      const existing = window.speechSynthesis.getVoices();
      if (existing.length > 0) {
        resolve(existing);
        return;
      }
      const onChange = () => {
        const v = window.speechSynthesis.getVoices();
        if (v.length > 0) {
          window.speechSynthesis.removeEventListener("voiceschanged", onChange);
          resolve(v);
        }
      };
      window.speechSynthesis.addEventListener("voiceschanged", onChange);
      window.setTimeout(() => resolve(window.speechSynthesis.getVoices()), 1000);
    });
  }
  return voicesPromise;
}

export class WebSpeaker implements Speaker {
  private _speaking = false;
  private changeCb: ((speaking: boolean) => void) | null = null;

  get supported(): boolean {
    return typeof window !== "undefined" && "speechSynthesis" in window;
  }

  get speaking(): boolean {
    return this._speaking;
  }

  private setSpeaking(v: boolean) {
    this._speaking = v;
    this.changeCb?.(v);
  }

  async speak(text: string, opts: SpeakOptions = {}): Promise<void> {
    if (!this.supported || !text) return;
    const voices = await loadVoices();
    return new Promise((resolve) => {
      const lang = opts.lang ?? "en";
      const utter = new SpeechSynthesisUtterance(text);
      utter.lang = LANG_TAG[lang];
      utter.rate = opts.rate ?? 1.0;
      utter.volume = opts.volume ?? 1.0;
      const match = pickVoice(voices, lang);
      if (match) utter.voice = match;
      utter.onstart = () => this.setSpeaking(true);
      const finish = () => {
        this.setSpeaking(false);
        resolve();
      };
      utter.onend = finish;
      utter.onerror = finish;
      window.speechSynthesis.speak(utter);
    });
  }

  stop(): void {
    if (this.supported) window.speechSynthesis.cancel();
    this.setSpeaking(false);
  }

  onSpeakingChange(cb: (speaking: boolean) => void): void {
    this.changeCb = cb;
  }
}

// --------------------------------------------------------------------------------- Mocks

/** Driven by tests and by the `?voiceMock=1` CDP/headless-browser test hook -- see
 * components/VoiceAssistant.tsx. `inject()` simulates what a real microphone would have
 * produced, with no browser speech API involved. */
export class MockRecognizer implements SpeechRecognizer {
  readonly supported = true;
  listening = false;
  private resultCb: ((r: RecognitionResult) => void) | null = null;
  private endCb: (() => void) | null = null;
  private errorCb: ((err: string) => void) | null = null;

  start(): void {
    this.listening = true;
  }

  stop(): void {
    if (this.listening) {
      this.listening = false;
      this.endCb?.();
    }
  }

  onResult(cb: (r: RecognitionResult) => void): void {
    this.resultCb = cb;
  }

  onEnd(cb: () => void): void {
    this.endCb = cb;
  }

  onError(cb: (err: string) => void): void {
    this.errorCb = cb;
  }

  /** Test-only: simulate a partial or final transcript arriving from the "microphone". */
  inject(text: string, isFinal = true): void {
    this.resultCb?.({ text, isFinal });
  }

  injectError(err: string): void {
    this.errorCb?.(err);
  }
}

export class MockSpeaker implements Speaker {
  readonly supported = true;
  spoken: string[] = [];
  private _speaking = false;
  private changeCb: ((speaking: boolean) => void) | null = null;

  get speaking(): boolean {
    return this._speaking;
  }

  speak(text: string): Promise<void> {
    this.spoken.push(text);
    this._speaking = true;
    this.changeCb?.(true);
    return new Promise((resolve) => {
      setTimeout(() => {
        this._speaking = false;
        this.changeCb?.(false);
        resolve();
      }, 0);
    });
  }

  stop(): void {
    this._speaking = false;
    this.changeCb?.(false);
  }

  onSpeakingChange(cb: (speaking: boolean) => void): void {
    this.changeCb = cb;
  }
}
