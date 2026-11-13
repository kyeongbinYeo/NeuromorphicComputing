"""검증 스크립트 공통: 경로 설정, 지표 계산, 결과 저장."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT, ROOT / "fitting"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402,F401

RESULTS = ROOT / "validation" / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
METRICS = RESULTS / "metrics.json"


def metrics(pred, data, scale=1e6):
    pred = np.asarray(pred, float) * scale
    data = np.asarray(data, float) * scale
    e = pred - data
    ss = np.sum((data - data.mean()) ** 2)
    return {
        "rmse": float(np.sqrt(np.mean(e ** 2))),
        "max_abs_err": float(np.abs(e).max()),
        "r2": float(1 - np.sum(e ** 2) / ss) if ss > 0 else None,
        "n": int(e.size),
    }


def rank_corr(a, b):
    ra = np.argsort(np.argsort(a))
    rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])


def min_gap(values, scale=1e6):
    s = np.sort(np.asarray(values) * scale)
    return float(np.min(np.diff(s)))


def save(section: str, result: dict):
    allm = json.loads(METRICS.read_text(encoding="utf-8")) if METRICS.exists() else {}
    allm[section] = result
    METRICS.write_text(json.dumps(allm, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[{section}]")
    print(json.dumps(result, indent=2, ensure_ascii=False))
