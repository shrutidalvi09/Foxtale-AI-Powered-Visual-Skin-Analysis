import { Link } from "react-router-dom";
import { Camera, Eye, Lock, FileText, ArrowRight } from "lucide-react";
import Disclaimer from "../components/Disclaimer";

const FEATURES = [
  { icon: Camera, text: "Camera-based analysis" },
  { icon: Eye, text: "Visual skin observations" },
  { icon: Lock, text: "Private processing" },
  { icon: FileText, text: "Easy-to-understand report" },
];

export default function Home() {
  return (
    <div>
      <section className="relative overflow-hidden bg-gradient-to-b from-accent-500/5 via-white to-white">
        <div className="mx-auto flex max-w-4xl flex-col items-center px-6 py-20 text-center sm:py-28">
          <span className="mb-5 inline-flex items-center gap-2 rounded-full border border-fox-500/20 bg-fox-500/10 px-4 py-1.5 text-xs font-semibold text-fox-600">
            🦊 Foxtale
          </span>
          <h1 className="text-4xl font-extrabold tracking-tight text-navy-900 sm:text-6xl">
            Understand Your Skin
            <br />
            <span className="bg-gradient-to-r from-accent-500 to-fox-500 bg-clip-text text-transparent">
              Through AI Vision
            </span>
          </h1>
          <p className="mt-6 max-w-xl text-lg text-navy-600">
            Scan your face with your webcam and get an easy-to-understand, visual skin
            observation report — powered by on-device-friendly computer vision.
          </p>

          <Link to="/scan" className="btn-primary mt-8 text-base">
            Start Face Scan
            <ArrowRight size={18} />
          </Link>

          <div className="mt-12 grid w-full grid-cols-2 gap-4 sm:grid-cols-4">
            {FEATURES.map(({ icon: Icon, text }) => (
              <div key={text} className="glass-panel flex flex-col items-center gap-2 rounded-2xl p-4">
                <Icon className="text-accent-500" size={22} />
                <span className="text-xs font-medium text-navy-700">{text}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-4xl px-6 pb-20">
        <Disclaimer />
      </section>
    </div>
  );
}
