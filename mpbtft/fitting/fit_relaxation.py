"""
Fig.3f 감쇠 곡선을 곡선마다 따로 이중 지수로 피팅한다 (reservoir 모드, 모델 없이).

    I_D(t) = I0 + A1·e^(−t/τ1) + A2·e^(−t/τ2)       (보충자료 식 (1))

세 곡선은 같은 소자에서 연달아 잰 것으로 보고 I0를 공유한다. t = 0은 펄스 끝으로 둔다.
결과는 bg_update 피팅에서 감쇠 모양 목표로 쓰고, data/README.md 표의 근거가 된다.

    python fitting/fit_relaxation.py
"""
from __future__ import annotations

import json

import numpy as np
from scipy.optimize import least_squares

from common import DATA, ROOT

VPGMS = ("3.5", "4.0", "4.5")


def load_fig3f():
    out = {}
    for v in VPGMS:
        d = np.loadtxt(DATA / "relaxation" / f"fig3f_vpgm_{v}V.csv", delimiter=",", skiprows=1)
        out[v] = (d[:, 0], d[:, 1])
    return out


def fit():
    curves = load_fig3f()

    def res(x):
        i0 = x[0]
        r = []
        for j, v in enumerate(VPGMS):
            a1, t1, a2, t2 = x[1 + 4 * j: 5 + 4 * j]
            t, i = curves[v]
            r.append((i0 + a1 * np.exp(-t / t1) + a2 * np.exp(-t / t2) - i) * 1e6)
        return np.concatenate(r)

    x0 = [0.8e-6] + [0.3e-6, 5e-4, 1e-6, 0.015] * 3
    lb = [0.0] + [0.0, 2e-5, 0.0, 1e-3] * 3
    ub = [2e-6] + [5e-6, 5e-3, 10e-6, 0.5] * 3
    sol = least_squares(res, x0, bounds=(lb, ub), x_scale=[1e-6] + [1e-6, 1e-3, 1e-6, 1e-2] * 3)
    x = sol.x
    report = {"shared_I0_A": float(x[0]), "curves": {}}
    for j, v in enumerate(VPGMS):
        a1, t1, a2, t2 = (float(q) for q in x[1 + 4 * j: 5 + 4 * j])
        if t1 > t2:
            a1, t1, a2, t2 = a2, t2, a1, t1
        t, i = curves[v]
        pred = x[0] + a1 * np.exp(-t / t1) + a2 * np.exp(-t / t2)
        err = (pred - i) * 1e6
        r2 = 1 - np.sum(err ** 2) / np.sum(((i - i.mean()) * 1e6) ** 2)
        report["curves"][v] = {
            "A1_A": a1, "tau1_s": t1, "A2_A": a2, "tau2_s": t2,
            "excess_at_pulse_end_A": a1 + a2, "fast_fraction": a1 / (a1 + a2),
            "rmse_uA": float(np.sqrt(np.mean(err ** 2))), "max_abs_err_uA": float(np.abs(err).max()),
            "r2": float(r2),
        }
    return report


def main():
    rep = fit()
    out = ROOT / "fitting" / "results" / "relaxation_fig3f.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
