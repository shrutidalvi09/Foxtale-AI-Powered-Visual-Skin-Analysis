"""Turn the ACNE04 parquet shards into face crops + a labels CSV for train.py.

Each photo is cropped the same way the app crops a scan at inference time (YuNet face box,
converted to the square Haar-style box, padded by CROP_PAD) so the model trains on what it will
see in production. ACNE04 photos are clinical close-ups and often show only part of a face; when
no face is found the whole photo is used, padded to a square.

    .venv/Scripts/python.exe prepare.py --src data/acne04 --out data/acne04_crops
"""

import argparse
import csv
import glob
import io
import os
import sys

import cv2
import numpy as np
import pyarrow.parquet as pq

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from engine.face_detection import detect_face, _detect_yunet  # noqa: E402
from engine.ml_acne import crop_for_model, MODEL_INPUT  # noqa: E402

SAVE_SIZE = 384  # stored a little larger than MODEL_INPUT so train-time random crops have room


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/acne04")
    ap.add_argument("--out", default="data/acne04_crops")
    args = ap.parse_args()
    os.makedirs(os.path.join(args.out, "img"), exist_ok=True)

    rows, n_face = [], 0
    for shard in sorted(glob.glob(os.path.join(args.src, "*.parquet"))):
        table = pq.read_table(shard, columns=["image", "file_name", "level", "num_lesions_annotated",
                                              "split", "fold_1_split"])
        for r in table.to_pylist():
            img = cv2.imdecode(np.frombuffer(r["image"]["bytes"], np.uint8), cv2.IMREAD_COLOR)
            if img is None:
                continue
            scale = 900 / max(img.shape[:2])  # the app resizes scans to max 900px before detecting
            if scale < 1:
                img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            face = detect_face(img)
            box = face.box if face.ok else None
            if box is None:  # close-ups: accept the largest YuNet face even if "too close"/"multiple"
                dets = _detect_yunet(img)
                box = dets[0][0] if dets else None
            n_face += box is not None
            crop = crop_for_model(img, box, size=SAVE_SIZE)
            name = os.path.splitext(r["file_name"])[0] + ".jpg"
            cv2.imwrite(os.path.join(args.out, "img", name), crop, [cv2.IMWRITE_JPEG_QUALITY, 92])
            rows.append({"file": name, "level": r["level"], "lesions": r["num_lesions_annotated"],
                         "split": r["split"], "face_found": int(box is not None)})
        print(f"{shard}: {len(rows)} images so far, face found in {n_face}", flush=True)

    with open(os.path.join(args.out, "labels.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"done: {len(rows)} images, face found in {n_face} ({100 * n_face / len(rows):.0f}%), input {MODEL_INPUT}px")


if __name__ == "__main__":
    main()
