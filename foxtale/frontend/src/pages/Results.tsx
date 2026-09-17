import { useMemo } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Sparkles, Droplets, Flame, Grid3x3, Trash2, ScanFace, Lock } from "lucide-react";
import AnalysisCard from "../components/AnalysisCard";
import SkinReport from "../components/SkinReport";
import Disclaimer from "../components/Disclaimer";
import { useScan } from "../context/ScanContext";
import type { SkinAnalysis } from "../types/analysis";

function buildRecommendations(analysis: SkinAnalysis): string[] {
  const tips: string[] = [];

  if (analysis.acne_like_spots.level !== "minimal") {
    tips.push(
      "Keep the face clean with a gentle cleanser.",
      "Avoid picking or squeezing spots.",
      "Use non-comedogenic skincare products.",
      "Consider professional advice if spots are persistent or worsening."
    );
  }
  if (analysis.redness.level !== "minimal") {
    tips.push(
      "Avoid harsh skincare products.",
      "Use gentle, fragrance-free products.",
      "Protect exposed skin from excessive sun.",
      "Consult a dermatologist if redness persists or worsens."
    );
  }
  if (analysis.dryness_indicators.level !== "minimal") {
    tips.push(
      "Use a gentle cleanser.",
      "Apply a moisturizer regularly.",
      "Avoid very hot water.",
      "Consider fragrance-free products."
    );
  }
  if (tips.length === 0) {
    tips.push(
      "Keep up a gentle, consistent skincare routine.",
      "Use sun protection daily.",
      "Stay hydrated and moisturized."
    );
  }
  return Array.from(new Set(tips));
}

export default function Results() {
  const navigate = useNavigate();
  const { capturedImage, latestAnalysis, latestRegions, clearScan } = useScan();

  const recommendations = useMemo(
    () => (latestAnalysis ? buildRecommendations(latestAnalysis) : []),
    [latestAnalysis]
  );

  if (!latestAnalysis) {
    return (
      <div className="mx-auto max-w-lg px-6 py-24 text-center">
        <h1 className="text-2xl font-bold text-navy-900">No analysis yet</h1>
        <p className="mt-2 text-navy-600">Run a face scan to see your skin analysis here.</p>
        <Link to="/scan" className="btn-primary mt-6">
          <ScanFace size={18} />
          Start Face Scan
        </Link>
      </div>
    );
  }

  const acneCount = latestRegions.filter((r) => r.category === "Acne-like spots").length;
  const rednessCount = latestRegions.filter((r) => r.category === "Redness").length;
  const dryCount = latestRegions.filter((r) => r.category === "Dryness indicators").length;

  const handleDelete = () => {
    clearScan();
    navigate("/scan");
  };

  return (
    <div className="mx-auto max-w-5xl px-6 py-12">
      <div className="mb-8 text-center">
        <h1 className="text-3xl font-extrabold text-navy-900">Your Skin Analysis</h1>
        <p className="mt-1 text-navy-600">AI-powered visual skin observations</p>
      </div>

      <div className="mb-8">
        <Disclaimer />
      </div>

      <div className="mb-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <AnalysisCard
          icon={Sparkles}
          title="Acne-like Spots"
          level={latestAnalysis.acne_like_spots.level}
          confidence={latestAnalysis.acne_like_spots.confidence}
          detail={`${latestAnalysis.acne_like_spots.count ?? acneCount} area(s) flagged`}
        />
        <AnalysisCard
          icon={Flame}
          title="Visible Redness"
          level={latestAnalysis.redness.level}
          confidence={latestAnalysis.redness.confidence}
          detail={`${rednessCount} area(s) found`}
        />
        <AnalysisCard
          icon={Grid3x3}
          title="Skin Texture"
          level={latestAnalysis.texture.level}
          confidence={latestAnalysis.texture.confidence}
          detail="Facial areas assessed"
        />
        <AnalysisCard
          icon={Droplets}
          title="Dryness Indicators"
          level={latestAnalysis.dryness_indicators.level}
          confidence={latestAnalysis.dryness_indicators.confidence}
          detail={`${dryCount} area(s) found`}
        />
      </div>

      <SkinReport capturedImage={capturedImage} regions={latestRegions} />

      <div className="mt-10 card p-6">
        <h3 className="mb-4 text-lg font-bold text-navy-900">Recommendations</h3>
        <ul className="grid gap-2 sm:grid-cols-2">
          {recommendations.map((tip) => (
            <li key={tip} className="flex items-start gap-2 text-sm text-navy-700">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-fox-500" />
              {tip}
            </li>
          ))}
        </ul>
      </div>

      <div className="mt-8 flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-navy-900/5 bg-navy-900/[0.02] p-4">
        <p className="flex items-center gap-2 text-xs text-navy-500">
          <Lock size={14} />
          Your face image is processed only for this analysis.
        </p>
        <div className="flex gap-3">
          <button onClick={handleDelete} className="btn-secondary !py-2 !px-4 text-sm">
            <Trash2 size={16} />
            Delete Scan
          </button>
          <Link to="/scan" className="btn-primary !py-2 !px-4 text-sm">
            <ScanFace size={16} />
            New Scan
          </Link>
        </div>
      </div>
    </div>
  );
}
