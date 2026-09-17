import { Lock, Eye, Cpu, ShieldAlert } from "lucide-react";
import Disclaimer from "../components/Disclaimer";

export default function About() {
  return (
    <div className="mx-auto max-w-3xl px-6 py-14">
      <h1 className="text-3xl font-extrabold text-navy-900">About Foxtale</h1>
      <p className="mt-3 text-navy-600">
        Foxtale is an AI-powered visual skin analysis tool. It uses your webcam to capture a
        photo, detects your face locally, and runs computer-vision heuristics to surface visible
        skin characteristics — like acne-like spots, redness, texture, and dryness indicators.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="card p-5">
          <Eye className="mb-2 text-accent-500" size={20} />
          <h3 className="font-semibold text-navy-800">Visual observations only</h3>
          <p className="mt-1 text-sm text-navy-600">
            Every result is phrased as a visible observation, not a clinical finding.
          </p>
        </div>
        <div className="card p-5">
          <Cpu className="mb-2 text-accent-500" size={20} />
          <h3 className="font-semibold text-navy-800">Explainable computer vision</h3>
          <p className="mt-1 text-sm text-navy-600">
            The current prototype uses classic image-processing heuristics (color, contrast,
            texture) rather than an opaque black-box model.
          </p>
        </div>
        <div className="card p-5">
          <Lock className="mb-2 text-accent-500" size={20} />
          <h3 className="font-semibold text-navy-800">Privacy-first</h3>
          <p className="mt-1 text-sm text-navy-600">
            Your image is used only to generate the analysis. It is not stored by default —
            only the analysis summary is saved locally in your browser, if you opt in.
          </p>
        </div>
        <div className="card p-5">
          <ShieldAlert className="mb-2 text-accent-500" size={20} />
          <h3 className="font-semibold text-navy-800">Not a medical device</h3>
          <p className="mt-1 text-sm text-navy-600">
            Foxtale does not diagnose medical conditions and does not infer age, ethnicity,
            or health status from your face.
          </p>
        </div>
      </div>

      <div className="mt-10">
        <Disclaimer />
      </div>
    </div>
  );
}
