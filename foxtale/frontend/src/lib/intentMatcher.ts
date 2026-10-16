/**
 * Client-only matcher for the small set of playback-control commands that must work with
 * zero network round trip, so they're instant even if the backend is slow or offline:
 * repeat / louder / quieter / stop talking / mute / unmute / skip guide. These only ever
 * change local playback state the frontend already owns (the current TTS utterance,
 * volume, mute flag), so there is nothing for the backend to validate or execute.
 *
 * Everything else (navigation, "start a scan", "what does my score mean", open-ended
 * questions, the irreversible wipe-data confirmation) is matched server-side by
 * backend/core/guide_intents.py, which is the single source of truth for that larger list.
 * The phrase lists below are a deliberately small, duplicated subset of that file's English/
 * Hindi/Marathi phrases -- kept in sync by hand; if you add a playback command on one side,
 * add it on the other.
 */

export type VoiceLang = "en" | "hi" | "mr";

export type LocalIntentType = "repeat" | "louder" | "quieter" | "stop_speaking" | "mute" | "unmute" | "skip_guide";

export interface LocalIntentMatch {
  type: LocalIntentType;
  confidence: number;
}

const PHRASES: Record<LocalIntentType, Record<VoiceLang, string[]>> = {
  repeat: {
    en: ["repeat that", "say that again", "repeat", "what did you say", "can you repeat that"],
    hi: ["फिर से कहो", "दोबारा कहो"],
    mr: ["पुन्हा सांगा"],
  },
  louder: {
    en: ["louder", "speak louder", "volume up", "turn it up"],
    hi: ["तेज आवाज़", "आवाज़ बढ़ाओ"],
    mr: ["आवाज वाढवा"],
  },
  quieter: {
    en: ["quieter", "speak softer", "volume down", "lower your voice", "turn it down"],
    hi: ["आवाज़ कम करो", "धीरे बोलो"],
    mr: ["आवाज कमी करा"],
  },
  stop_speaking: {
    en: ["stop", "stop talking", "be quiet", "stop speaking"],
    hi: ["रुको", "बंद करो", "चुप हो जाओ"],
    mr: ["थांबा", "बंद करा"],
  },
  mute: {
    en: ["mute", "turn off voice", "mute yourself", "mute the voice"],
    hi: ["म्यूट करो", "आवाज़ बंद करो"],
    mr: ["म्यूट करा", "आवाज बंद करा"],
  },
  unmute: {
    en: ["unmute", "turn on voice", "unmute yourself", "unmute the voice"],
    hi: ["अनम्यूट करो", "आवाज़ चालू करो"],
    mr: ["अनम्यूट करा", "आवाज सुरू करा"],
  },
  skip_guide: {
    en: ["skip guide", "skip the guide", "no thanks", "skip this"],
    hi: ["गाइड छोड़ो", "गाइड स्किप करो"],
    mr: ["गाईड वगळा"],
  },
};

export const INTENT_CONFIDENCE_THRESHOLD = 0.6;

export function normalize(text: string): string {
  // \p{M} keeps combining marks (e.g. Devanagari vowel signs) attached to their base letter --
  // without it, "रुको" (stop) would lose its matras and silently stop matching anything.
  return text
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\p{M}\s]/gu, "")
    .trim();
}

function score(normText: string, normPhrase: string): number {
  if (!normPhrase) return 0;
  if (normText === normPhrase) return 0.97;
  if (normText.includes(normPhrase)) return 0.85;
  if (normPhrase.includes(normText)) return 0.75;
  const phraseWords = new Set(normPhrase.split(/\s+/));
  const textWords = new Set(normText.split(/\s+/));
  if (phraseWords.size === 0) return 0;
  const allIn = [...phraseWords].every((w) => textWords.has(w));
  if (allIn) return 0.7;
  const overlap = [...phraseWords].filter((w) => textWords.has(w));
  return overlap.length ? 0.55 * (overlap.length / phraseWords.size) : 0;
}

/** Best-matching local playback-control intent for one transcript, or null. Only ever
 * returns the seven control types above -- anything else (including "no match") is null,
 * and the caller should send the transcript to the backend instead. */
export function matchLocal(text: string, lang: VoiceLang): LocalIntentMatch | null {
  const normText = normalize(text);
  if (!normText) return null;
  let best: LocalIntentMatch | null = null;
  for (const type of Object.keys(PHRASES) as LocalIntentType[]) {
    for (const phrase of PHRASES[type][lang] ?? []) {
      const conf = score(normText, normalize(phrase));
      if (conf > 0 && (!best || conf > best.confidence)) {
        best = { type, confidence: conf };
      }
    }
  }
  return best;
}
