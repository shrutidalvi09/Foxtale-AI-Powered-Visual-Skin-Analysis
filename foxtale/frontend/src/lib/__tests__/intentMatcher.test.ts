import { describe, expect, it } from "vitest";
import { INTENT_CONFIDENCE_THRESHOLD, matchLocal, normalize } from "../intentMatcher";

describe("normalize", () => {
  it("lowercases and strips punctuation", () => {
    expect(normalize("Stop, please!")).toBe("stop please");
  });

  it("leaves Devanagari text intact", () => {
    expect(normalize("रुको!")).toBe("रुको");
  });
});

describe("matchLocal: English playback controls", () => {
  it.each([
    ["repeat that", "repeat"], ["say that again", "repeat"],
    ["louder", "louder"], ["turn it up", "louder"],
    ["quieter", "quieter"], ["lower your voice", "quieter"],
    ["stop", "stop_speaking"], ["be quiet", "stop_speaking"],
    ["mute", "mute"], ["turn off voice", "mute"],
    ["unmute", "unmute"],
    ["skip the guide", "skip_guide"], ["no thanks", "skip_guide"],
  ] as const)("'%s' matches %s", (text, expected) => {
    const m = matchLocal(text, "en");
    expect(m).not.toBeNull();
    expect(m?.type).toBe(expected);
    expect(m?.confidence).toBeGreaterThanOrEqual(INTENT_CONFIDENCE_THRESHOLD);
  });

  it("tolerates a noisy/partial transcript with extra filler words", () => {
    const m = matchLocal("um could you please repeat that for me", "en");
    expect(m?.type).toBe("repeat");
  });
});

describe("matchLocal: Hindi and Marathi", () => {
  it("matches a Hindi mute command", () => {
    expect(matchLocal("आवाज़ बंद करो", "hi")?.type).toBe("mute");
  });

  it("matches a Marathi louder command", () => {
    expect(matchLocal("आवाज वाढवा", "mr")?.type).toBe("louder");
  });

  it("does not cross-match a Hindi phrase against English lists", () => {
    // "आवाज़ बंद करो" has no English phrase overlap, so no English-language match should fire.
    expect(matchLocal("आवाज़ बंद करो", "en")).toBeNull();
  });
});

describe("matchLocal: things it must NOT catch", () => {
  it("does not match app-content commands (those belong to the backend matcher)", () => {
    // "start a scan" isn't a playback-control intent, so the client matcher must return
    // null (or something below threshold) and let the caller send it to the backend.
    const m = matchLocal("start a scan", "en");
    expect(m === null || m.confidence < INTENT_CONFIDENCE_THRESHOLD).toBe(true);
  });

  it("returns null for empty or whitespace-only input", () => {
    expect(matchLocal("", "en")).toBeNull();
    expect(matchLocal("   ", "en")).toBeNull();
  });

  it("returns null for unrelated gibberish", () => {
    expect(matchLocal("purple elephant banana", "en")).toBeNull();
  });

  it("a weak partial-word overlap with 'repeat' phrases stays below threshold (regression)", () => {
    // "what does my score mean" shares only the word "what" with the "repeat" phrase
    // "what did you say" -- callers MUST check confidence, not just non-null, or this
    // gets misrouted to "repeat" instead of reaching the backend's explain_score intent.
    const m = matchLocal("what does my score mean", "en");
    expect(m === null || m.confidence < INTENT_CONFIDENCE_THRESHOLD).toBe(true);
  });
});
