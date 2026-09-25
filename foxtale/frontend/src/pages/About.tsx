import { Cpu, Eye, Lock, ShieldAlert, Sparkles } from "lucide-react";
import { Disclaimer, IconBadge, PageHeader } from "../components/ui";
import { Reveal } from "../lib/motion";

const CARDS = [
  { icon: Eye, title: "Visual observations only", body: "Every result is phrased as a visible observation, not a clinical finding." },
  { icon: Cpu, title: "Explainable computer vision", body: "Foxtale measures colour and brightness on your skin pixels (CIELAB) with classic image processing, not an opaque black-box model." },
  { icon: Lock, title: "Privacy-first", body: "Photos are analysed on your own computer. They are saved only if you turn on Save scan photos." },
  { icon: ShieldAlert, title: "Not a medical device", body: "Foxtale does not diagnose conditions and does not infer age, ethnicity or health status from your face." },
  { icon: Sparkles, title: "Skincare matched to you", body: "Suggestions come from what your scan measured, with the reason and how each product works. They are cosmetic guidance, not treatment." },
];

export default function About() {
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader title="About Foxtale" />
      <p className="text-muted">
        Foxtale is an AI-powered visual skin analysis tool. It uses your camera to capture a photo, finds your face locally, isolates
        the skin, and measures visible characteristics: acne-like spots, redness, texture, dryness, oiliness and tone evenness, then
        turns them into a score, a report and a matching skincare routine.
      </p>
      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {CARDS.map(({ icon: Icon, title, body }, i) => (
          <Reveal key={title} index={i} className="h-full">
          <div className="card lift h-full p-5">
            <IconBadge><Icon size={18} /></IconBadge>
            <h3 className="mt-3 font-extrabold text-ink">{title}</h3>
            <p className="mt-1 text-sm text-muted">{body}</p>
          </div>
          </Reveal>
        ))}
      </div>
      <div className="mt-8"><Disclaimer /></div>
    </div>
  );
}
