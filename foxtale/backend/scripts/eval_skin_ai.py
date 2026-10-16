#!/usr/bin/env python
"""Evaluation harness for the Custom Skin AI module.

Runs every image in a folder through the real pipeline (face detection -> measurement layer
-> Skin Analyst) and reports:

  * schema-failure rate   -- how often the model's response could not be validated even after
                              the one retry (so the pipeline had to fall back to measurements only)
  * agreement             -- precision/recall/F1 of the finding *types* reported (severity !=
                              "none") against a hand-labelled expected set, per image and averaged
  * run-to-run consistency -- the same photo is sent N times; this is the average Jaccard
                              similarity of the (region, type) pairs reported each time, which
                              should be high (temperature is fixed at 0) but is not guaranteed to
                              be identical run to run with a real LLM

Usage:
    cd backend
    .venv/Scripts/python.exe scripts/eval_skin_ai.py --images-dir path/to/photos --labels path/to/labels.json
    .venv/Scripts/python.exe scripts/eval_skin_ai.py --images-dir path/to/photos --labels path/to/labels.json --dry-run

labels.json format -- one entry per image filename, listing the finding *types* (see
core/skin_ai_schema.py:FindingType for the allowed vocabulary) a human reviewer expects to see
reported somewhere in the photo (region is not compared, to keep hand-labelling fast):

    {
      "photo1.jpg": {"expected_types": ["redness", "acne_pimple"]},
      "photo2.jpg": {"expected_types": []}
    }

--dry-run forces the mock provider (no network call, no cost) so the harness itself can be
tried and smoke-tested without an API key; it will of course "agree" badly with real labels,
since the mock always returns the same two generic findings regardless of the photo.
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run as a plain script, not -m

import cv2  # noqa: E402

from core import skin_ai_analyst as analyst  # noqa: E402
from core import skin_ai_config as config  # noqa: E402
from core import skin_ai_provider as provider  # noqa: E402
from core.skin_ai_measurer import default_measurer  # noqa: E402
from engine.face_detection import detect_face  # noqa: E402
from engine.image_processing import split_regions  # noqa: E402
from engine.quality import compute_quality  # noqa: E402
from engine.skin_analysis import analyze_face  # noqa: E402
from utils.image_utils import resize_max_dim  # noqa: E402


def _prf(expected: Set[str], got: Set[str]) -> Tuple[float, float, float]:
    if not expected and not got:
        return 1.0, 1.0, 1.0
    tp = len(expected & got)
    precision = tp / len(got) if got else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1


def _jaccard(a: Set, b: Set) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else 1.0


def _run_once(image_bgr) -> Tuple[str, Set[str], Set[Tuple[str, str]]]:
    """Returns (status, finding_types_with_severity, (region, type) pairs), where "status" is
    'ready' or 'fallback' (schema failure after the retry)."""
    face = detect_face(image_bgr)
    if not face.ok:
        return "no_face", set(), set()
    regions = split_regions(image_bgr, face.box)
    analysis, _obs = analyze_face(regions)
    quality = compute_quality(image_bgr, face.box)
    measurements = default_measurer().measure(analysis, quality)
    result, status = analyst._call_model(measurements, analyst._prepare_image(image_bgr, face.box))  # noqa: SLF001
    if result is None:
        result = analyst._fallback_result(analysis, quality, reason="eval: schema failure")  # noqa: SLF001
        status = "fallback"
    types = {f.type for f in result.findings if f.severity != "none"}
    pairs = {(f.region, f.type) for f in result.findings if f.severity != "none"}
    return status, types, pairs


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--images-dir", required=True, type=Path)
    ap.add_argument("--labels", required=True, type=Path)
    ap.add_argument("--repeats", type=int, default=2, help="times to re-run each image for consistency (default 2)")
    ap.add_argument("--dry-run", action="store_true", help="force the mock provider; no network call, no cost")
    ap.add_argument("--out", type=Path, default=None, help="optional path to write the full JSON report")
    args = ap.parse_args()

    if args.dry_run:
        import dataclasses
        config.CONFIG = dataclasses.replace(config.CONFIG, dry_run=True)  # type: ignore[misc]

    labels: Dict[str, dict] = json.loads(args.labels.read_text(encoding="utf-8"))
    rows = []
    for filename, label in labels.items():
        path = args.images_dir / filename
        if not path.exists():
            print(f"  ! skipping {filename}: file not found in {args.images_dir}")
            continue
        image = cv2.imread(str(path))
        if image is None:
            print(f"  ! skipping {filename}: could not decode image")
            continue
        image = resize_max_dim(image, max_dim=900)
        expected = set(label.get("expected_types", []))

        runs = [_run_once(image) for _ in range(max(1, args.repeats))]
        statuses = [r[0] for r in runs]
        if all(s == "no_face" for s in statuses):
            print(f"  ! skipping {filename}: no face detected")
            continue
        schema_failures = sum(1 for s in statuses if s == "fallback")
        first_types = runs[0][1]
        precision, recall, f1 = _prf(expected, first_types)
        pair_sets = [r[2] for r in runs if r[0] != "no_face"]
        consistency = (
            sum(_jaccard(pair_sets[i], pair_sets[i + 1]) for i in range(len(pair_sets) - 1)) / (len(pair_sets) - 1)
            if len(pair_sets) > 1 else 1.0
        )
        rows.append({
            "file": filename, "expected": sorted(expected), "got": sorted(first_types),
            "precision": round(precision, 3), "recall": round(recall, 3), "f1": round(f1, 3),
            "schema_failures": schema_failures, "runs": len(runs), "consistency": round(consistency, 3),
        })
        print(f"  {filename:30s} P={precision:.2f} R={recall:.2f} F1={f1:.2f} "
              f"consistency={consistency:.2f} schema_failures={schema_failures}/{len(runs)}")

    if not rows:
        print("No images were evaluated.")
        return

    n = len(rows)
    print("\n--- summary -------------------------------------------------")
    print(f"images evaluated:        {n}")
    print(f"mean precision:          {sum(r['precision'] for r in rows) / n:.3f}")
    print(f"mean recall:             {sum(r['recall'] for r in rows) / n:.3f}")
    print(f"mean F1:                 {sum(r['f1'] for r in rows) / n:.3f}")
    print(f"schema-failure rate:     {sum(r['schema_failures'] for r in rows) / sum(r['runs'] for r in rows):.1%}")
    print(f"mean run-to-run consistency: {sum(r['consistency'] for r in rows) / n:.3f}")
    print(f"provider={config.CONFIG.provider} model={config.CONFIG.model} dry_run={config.CONFIG.dry_run}")

    if args.out:
        args.out.write_text(json.dumps({"rows": rows, "provider": config.CONFIG.provider,
                                        "model": config.CONFIG.model}, indent=2), encoding="utf-8")
        print(f"\nFull report written to {args.out}")


if __name__ == "__main__":
    main()
