import { describe, expect, it } from "vitest";
import { initialVoiceMachineState, parseYesNo, voiceReducer } from "../voiceMachine";

describe("voiceReducer: basic turn-taking", () => {
  it("push-to-talk from idle goes to listening", () => {
    const s = voiceReducer(initialVoiceMachineState, { type: "PUSH_TO_TALK" });
    expect(s.state).toBe("listening");
    expect(s.justBargedIn).toBe(false);
  });

  it("a final transcript while listening moves to thinking, carrying the text", () => {
    const listening = voiceReducer(initialVoiceMachineState, { type: "PUSH_TO_TALK" });
    const thinking = voiceReducer(listening, { type: "FINAL", text: "start a scan" });
    expect(thinking.state).toBe("thinking");
    expect(thinking.liveCaption).toBe("start a scan");
  });

  it("a reply with no confirmation and speech moves to speaking", () => {
    const thinking = { state: "thinking", liveCaption: "hi", justBargedIn: false } as const;
    const s = voiceReducer(thinking, { type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: true });
    expect(s.state).toBe("speaking");
  });

  it("a reply with no confirmation and no speech returns straight to idle", () => {
    const thinking = { state: "thinking", liveCaption: "mute", justBargedIn: false } as const;
    const s = voiceReducer(thinking, { type: "REPLY_RECEIVED", needsConfirmation: false, hasSpeech: false });
    expect(s.state).toBe("idle");
  });

  it("a reply needing confirmation moves to confirming regardless of hasSpeech", () => {
    const thinking = { state: "thinking", liveCaption: "wipe my data", justBargedIn: false } as const;
    const s = voiceReducer(thinking, { type: "REPLY_RECEIVED", needsConfirmation: true, hasSpeech: false });
    expect(s.state).toBe("confirming");
  });

  it("speech done returns to idle only while speaking", () => {
    const speaking = { state: "speaking", liveCaption: "", justBargedIn: false } as const;
    expect(voiceReducer(speaking, { type: "SPEECH_DONE" }).state).toBe("idle");
    const idle = voiceReducer(initialVoiceMachineState, { type: "SPEECH_DONE" });
    expect(idle.state).toBe("idle"); // no-op, stays idle
  });
});

describe("voiceReducer: barge-in", () => {
  it("a partial transcript while speaking cuts to listening and flags justBargedIn", () => {
    const speaking = { state: "speaking", liveCaption: "", justBargedIn: false } as const;
    const s = voiceReducer(speaking, { type: "PARTIAL", text: "wait" });
    expect(s.state).toBe("listening");
    expect(s.justBargedIn).toBe(true);
    expect(s.liveCaption).toBe("wait");
  });

  it("an explicit BARGE_IN event does the same thing", () => {
    const speaking = { state: "speaking", liveCaption: "", justBargedIn: false } as const;
    const s = voiceReducer(speaking, { type: "BARGE_IN" });
    expect(s.state).toBe("listening");
    expect(s.justBargedIn).toBe(true);
  });

  it("push-to-talk while speaking is also treated as a barge-in", () => {
    const speaking = { state: "speaking", liveCaption: "", justBargedIn: false } as const;
    const s = voiceReducer(speaking, { type: "PUSH_TO_TALK" });
    expect(s.state).toBe("listening");
    expect(s.justBargedIn).toBe(true);
  });

  it("a partial transcript while idle or thinking is ignored", () => {
    expect(voiceReducer(initialVoiceMachineState, { type: "PARTIAL", text: "x" }).state).toBe("idle");
    const thinking = { state: "thinking", liveCaption: "", justBargedIn: false } as const;
    expect(voiceReducer(thinking, { type: "PARTIAL", text: "x" }).state).toBe("thinking");
  });
});

describe("voiceReducer: timeouts, stop and error", () => {
  it("a silence timeout while listening returns to idle", () => {
    const listening = { state: "listening", liveCaption: "", justBargedIn: false } as const;
    expect(voiceReducer(listening, { type: "SILENCE_TIMEOUT" }).state).toBe("idle");
  });

  it("a silence timeout outside listening is a no-op", () => {
    const speaking = { state: "speaking", liveCaption: "", justBargedIn: false } as const;
    expect(voiceReducer(speaking, { type: "SILENCE_TIMEOUT" }).state).toBe("speaking");
  });

  it("STOP always returns to idle from any state", () => {
    for (const state of ["idle", "listening", "thinking", "speaking", "confirming"] as const) {
      expect(voiceReducer({ state, liveCaption: "x", justBargedIn: false }, { type: "STOP" }).state).toBe("idle");
    }
  });

  it("ERROR always returns to idle", () => {
    const confirming = { state: "confirming", liveCaption: "", justBargedIn: false } as const;
    expect(voiceReducer(confirming, { type: "ERROR" }).state).toBe("idle");
  });
});

describe("voiceReducer: confirmation turn accepts a yes/no answer", () => {
  it("a final transcript while confirming moves to thinking (to be parsed as yes/no)", () => {
    const confirming = { state: "confirming", liveCaption: "", justBargedIn: false } as const;
    const s = voiceReducer(confirming, { type: "FINAL", text: "yes" });
    expect(s.state).toBe("thinking");
    expect(s.liveCaption).toBe("yes");
  });
});

describe("parseYesNo", () => {
  it.each([
    ["yes", "en", true], ["Yeah sure", "en", true], ["go ahead", "en", true],
    ["no", "en", false], ["nope, cancel that", "en", false],
    ["purple elephant", "en", null],
  ] as const)("en: %s -> %s", (text, lang, expected) => {
    expect(parseYesNo(text, lang)).toBe(expected);
  });

  it("recognises Hindi yes/no", () => {
    expect(parseYesNo("हाँ कर दो", "hi")).toBe(true);
    expect(parseYesNo("नहीं रद्द करो", "hi")).toBe(false);
  });

  it("recognises Marathi yes/no", () => {
    expect(parseYesNo("हो करा", "mr")).toBe(true);
    expect(parseYesNo("नको रद्द करा", "mr")).toBe(false);
  });

  it("a no-match phrase returns null in every language", () => {
    expect(parseYesNo("banana", "en")).toBeNull();
    expect(parseYesNo("केळी", "hi")).toBeNull();
    expect(parseYesNo("केळी", "mr")).toBeNull();
  });
});
