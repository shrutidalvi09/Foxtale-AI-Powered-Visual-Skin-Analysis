import { Loader2, Mic, MicOff, Volume2, VolumeX } from "lucide-react";
import { useVoice } from "../context/VoiceContext";

const STATE_LABEL: Record<string, string> = {
  idle: "Talk to Fox",
  listening: "Listening…",
  thinking: "Thinking…",
  speaking: "Speaking…",
  confirming: "Waiting for yes or no",
};

/** Floating, opt-in widget for Fox, the voice assistant: a push-to-talk mic button plus a
 * captions panel for accessibility (also usable by anyone who prefers reading over audio).
 * Only rendered once the user has turned her on in Settings -- fully absent otherwise, so
 * the rest of the app is unaffected by this feature when it's off. */
export default function VoiceAssistant() {
  const voice = useVoice();

  if (!voice.status?.enabled) return null;

  const { state, liveCaption, muted, micError, pushToTalk, stopAll, toggleMute } = voice;
  const showCaptions = voice.status.captionsEnabled;
  const isBusy = state === "thinking";
  const isActive = state !== "idle";

  const Icon = state === "thinking" ? Loader2 : state === "speaking" ? Volume2 : muted ? MicOff : Mic;

  return (
    // Bottom-right, raised well above the back-to-top button's corner (components/Layout.tsx:
    // ScrollAids, fixed bottom-6 right-6) so the two floating controls never overlap, and kept
    // off the left side entirely so it never sits on top of the desktop sidebar's own bottom
    // controls (Start New Scan / theme toggle / privacy caption).
    <div className="fixed bottom-24 right-4 z-40 flex flex-col items-end gap-2 md:right-6">
      {(showCaptions && (liveCaption || micError)) && (
        <div
          role="status" aria-live="polite"
          className="toast-in max-w-[260px] rounded-2xl bg-ink px-4 py-2.5 text-xs font-medium text-card shadow-card"
        >
          {micError || liveCaption || STATE_LABEL[state]}
        </div>
      )}
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={isActive ? stopAll : pushToTalk}
          aria-label={isActive ? "Stop Fox" : "Talk to Fox"}
          aria-pressed={isActive}
          title={STATE_LABEL[state]}
          className={`pop flex h-14 w-14 items-center justify-center rounded-full text-white shadow-glow transition active:scale-90 ${
            state === "listening" || state === "confirming"
              ? "animate-pulse bg-rose-500"
              : state === "speaking"
              ? "bg-emerald-600"
              : "bg-fox-600 hover:bg-fox-700"
          }`}
        >
          <Icon size={24} className={isBusy ? "animate-spin" : undefined} />
        </button>
        {/* Kept out of the idle layout: a single small FAB sits over far less page content
            than a two-button row, and the mute control only matters once there's something
            to mute (mid-conversation) or it's already on (so it's reachable to turn back off). */}
        {(isActive || muted) && (
          <button
            type="button"
            onClick={toggleMute}
            aria-label={muted ? "Unmute Fox" : "Mute Fox"}
            aria-pressed={muted}
            className="pop flex h-9 w-9 items-center justify-center rounded-full bg-card text-ink shadow-card transition active:scale-90"
          >
            {muted ? <VolumeX size={16} /> : <Volume2 size={16} />}
          </button>
        )}
      </div>
    </div>
  );
}
