"""Fine-tune an ImageNet MobileNetV3-Large on ACNE04 face crops (from prepare.py) and export to ONNX.

Two heads on one backbone:
  * severity_logits -- 4-way Hayashi grade (mild / moderate / severe / very_severe), weighted CE
  * log_lesions     -- log1p(annotated lesion count), smooth-L1

Splits: ACNE04's canonical `split` column (fold 0) -- its 'test' rows are held out and only touched
once, for the final report; 15% of 'train' (stratified) is used for model selection.

    .venv/Scripts/python.exe train.py --data data/acne04_crops --epochs 14
"""

import argparse
import csv
import datetime as dt
import json
import os
import sys
import time

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from sklearn.metrics import confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from torch.utils.data import DataLoader, Dataset
from torchvision import models
from torchvision.transforms import v2 as T

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))
from engine.ml_acne import MODEL_INPUT, SEVERITY  # noqa: E402

MEAN = torch.tensor([0.485, 0.456, 0.406]).view(1, 3, 1, 1)
STD = torch.tensor([0.229, 0.224, 0.225]).view(1, 3, 1, 1)


class Crops(Dataset):
    def __init__(self, root, rows, train):
        self.root, self.rows = root, rows
        aug = [T.RandomResizedCrop(MODEL_INPUT, scale=(0.65, 1.0), ratio=(0.9, 1.1), antialias=True),
               T.RandomHorizontalFlip(),
               T.RandomApply([T.RandomRotation(12)], p=0.5),
               T.ColorJitter(0.25, 0.25, 0.15, 0.02)]
        self.tf = T.Compose(aug if train else [T.Resize(MODEL_INPUT, antialias=True)])

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = cv2.cvtColor(cv2.imread(os.path.join(self.root, "img", r["file"])), cv2.COLOR_BGR2RGB)
        x = self.tf(torch.from_numpy(img).permute(2, 0, 1)).float()  # 0-255, normalised inside the model
        return x, int(r["level"]), float(np.log1p(int(r["lesions"])))


class AcneNet(nn.Module):
    def __init__(self, pretrained=True):
        super().__init__()
        m = models.mobilenet_v3_large(weights=models.MobileNet_V3_Large_Weights.IMAGENET1K_V2 if pretrained else None)
        self.features, self.pool = m.features, m.avgpool
        self.neck = nn.Sequential(nn.Linear(960, 1280), nn.Hardswish(), nn.Dropout(0.3))
        self.severity = nn.Linear(1280, len(SEVERITY))
        self.lesions = nn.Linear(1280, 1)

    def forward(self, x):  # x: Nx3xHxW RGB, 0-255
        x = (x / 255.0 - MEAN.to(x.device)) / STD.to(x.device)
        h = self.neck(torch.flatten(self.pool(self.features(x)), 1))
        return self.severity(h), self.lesions(h).squeeze(1)


def run_epoch(model, loader, opt=None, cls_w=None, sched=None):
    train = opt is not None
    model.train(train)
    tot, n, preds, gold, lp, lg = 0.0, 0, [], [], [], []
    with torch.set_grad_enabled(train):
        for x, y, l in loader:
            logits, ll = model(x)
            loss = F.cross_entropy(logits, y, weight=cls_w, label_smoothing=0.1) + 0.5 * F.smooth_l1_loss(ll, l.float())
            if train:
                opt.zero_grad()
                loss.backward()
                opt.step()
                sched.step()
            tot += loss.item() * len(y)
            n += len(y)
            preds += logits.argmax(1).tolist()
            gold += y.tolist()
            lp += torch.expm1(ll).clamp(min=0).tolist()
            lg += torch.expm1(l).tolist()
    p, g = np.array(preds), np.array(gold)
    return {"loss": tot / n, "acc": float((p == g).mean()), "macro_f1": float(f1_score(g, p, average="macro")),
            "within_one": float((abs(p - g) <= 1).mean()),
            "lesion_mae": float(np.mean(np.abs(np.array(lp) - np.array(lg)))), "_p": p, "_g": g}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/acne04_crops")
    ap.add_argument("--epochs", type=int, default=14)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--lr", type=float, default=6e-4)
    ap.add_argument("--out", default=os.path.join("..", "backend", "assets", "models", "acne_severity.onnx"))
    ap.add_argument("--workers", type=int, default=3)
    args = ap.parse_args()
    torch.manual_seed(0)

    with open(os.path.join(args.data, "labels.csv")) as f:
        rows = list(csv.DictReader(f))
    train_all = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    train, val = train_test_split(train_all, test_size=0.15, random_state=0, stratify=[r["level"] for r in train_all])
    print(f"train {len(train)}  val {len(val)}  test {len(test)}", flush=True)

    counts = np.bincount([int(r["level"]) for r in train], minlength=len(SEVERITY))
    cls_w = torch.tensor(counts.sum() / (len(SEVERITY) * counts), dtype=torch.float32)
    print("train class counts", counts.tolist(), "weights", [round(w, 2) for w in cls_w.tolist()], flush=True)

    mk = lambda rs, tr: DataLoader(Crops(args.data, rs, tr), batch_size=args.batch, shuffle=tr,
                                   num_workers=args.workers, persistent_workers=args.workers > 0)
    dl_train, dl_val, dl_test = mk(train, True), mk(val, False), mk(test, False)

    model = AcneNet()
    opt = torch.optim.AdamW(model.parameters(), lr=args.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=args.lr, total_steps=args.epochs * len(dl_train), pct_start=0.15)

    best, best_state = -1.0, None
    for ep in range(1, args.epochs + 1):
        t0 = time.time()
        tr = run_epoch(model, dl_train, opt, cls_w, sched)
        va = run_epoch(model, dl_val)
        sel = va["macro_f1"] + 0.5 * va["acc"]
        mark = ""
        if sel > best:
            best, best_state, mark = sel, {k: v.clone() for k, v in model.state_dict().items()}, "  *best"
        print(f"ep {ep:2d}  train loss {tr['loss']:.3f} acc {tr['acc']:.3f} | val loss {va['loss']:.3f} "
              f"acc {va['acc']:.3f} f1 {va['macro_f1']:.3f} lesionMAE {va['lesion_mae']:.1f}  ({time.time() - t0:.0f}s){mark}",
              flush=True)

    model.load_state_dict(best_state)
    te = run_epoch(model, dl_test)
    cm = confusion_matrix(te["_g"], te["_p"], labels=list(range(len(SEVERITY)))).tolist()
    report = {k: round(v, 4) for k, v in te.items() if not k.startswith("_")}
    print("TEST", report)
    print("confusion (rows = true mild..very_severe, cols = predicted):")
    for name, row in zip(SEVERITY, cm):
        print(f"  {name:12s} {row}")

    # ---- export ----
    model.eval()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    dummy = torch.zeros(1, 3, MODEL_INPUT, MODEL_INPUT)
    torch.onnx.export(model, dummy, args.out, input_names=["input"], output_names=["severity_logits", "log_lesions"],
                      opset_version=17, dynamo=False)
    meta = {
        "name": "acne_severity_mobilenetv3",
        "version": dt.date.today().isoformat(),
        "input_size": MODEL_INPUT,
        "architecture": "MobileNetV3-Large (ImageNet) + severity / lesion-count heads",
        "dataset": "ACNE04 (Wu et al., ICCV 2019), canonical fold-0 split; academic use only",
        "classes": SEVERITY,
        "train_images": len(train), "val_images": len(val), "test_images": len(test),
        "test_metrics": report,
        "test_confusion": cm,
    }
    with open(os.path.splitext(args.out)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2)

    # ---- parity check: the exported graph through OpenCV DNN must match PyTorch ----
    net = cv2.dnn.readNetFromONNX(args.out)
    x = torch.rand(1, 3, MODEL_INPUT, MODEL_INPUT) * 255
    with torch.no_grad():
        ref = model(x)
    net.setInput(x.numpy())
    got = net.forward(["severity_logits", "log_lesions"])
    diff = max(float(np.abs(got[0] - ref[0].numpy()).max()), float(np.abs(got[1].reshape(-1) - ref[1].numpy()).max()))
    print(f"exported {args.out} ({os.path.getsize(args.out) / 2**20:.1f} MB); OpenCV-vs-PyTorch max diff {diff:.2e}")


if __name__ == "__main__":
    main()
