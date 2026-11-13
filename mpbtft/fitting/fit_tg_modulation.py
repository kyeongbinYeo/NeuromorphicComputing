"""
Reservoir 모드 TG 변조 배율 M(V_TG) 피팅:  ΔI_D(I_D, V_TG) = ΔI_D(I_D, 0 V) × M(V_TG),  M(0) = 1.

이 곱셈 형태는 가정이다 (사양서 12장). Fig.3j hold-out 오차로 이 가정을 검증한다.

학습: Fig.3i (TG 5.0 → 3.0 → 1.5 → 0 V). 소자 파라미터(BG 표, 감쇠)는 고정하고 M(1.5), M(3), M(5)만 푼다.
Hold-out: Fig.3j (TG 1.0 → 5.0 → 3.0 → 2.0 → 0 V) — 1.0 V, 2.0 V는 학습에 없는 전압이라 보간도 함께 검증.
모델 없는 검사: 같은 펄스 직전 전류에서 (TG 있는 증가분) / (TG 0 V 표 값) 비율을 데이터에서 직접 잰다.

    python fitting/fit_tg_modulation.py
"""
from __future__ import annotations

import json

import numpy as np
from scipy.optimize import least_squares

from common import ROOT, load_states, pair_jumps, simulate_states
from parameters import MPBTFTParams, Table

KNOTS_V = [0.0, 1.5, 3.0, 5.0]       # Fig.3i에 쓰인 V_TG


def fit(params: MPBTFTParams):
    _, data3i = load_states("fig3i")

    def set_gain(g):
        params.reservoir.tg_modulation = Table(KNOTS_V, [1.0] + [float(v) for v in g])

    def residuals(g):
        set_gain(g)
        return ((simulate_states(params, "fig3i", strict=False) - data3i) * 1e6).ravel()

    sol = least_squares(residuals, [0.8, 0.6, 0.5], bounds=(0.05, 1.5), diff_step=1e-3)
    set_gain(sol.x)
    err = residuals(sol.x)

    # 모델 없는 비율: 데이터 증가분 / 같은 직전 전류의 TG 0 V 증가분(데이터 pair에서 직선 근사)
    p0 = pair_jumps("fig3h", params.reservoir.baseline_A)
    slope, icpt = np.polyfit(p0[:, 1], p0[:, 2], 1)
    ratios = {}
    for name in ("fig3h", "fig3i", "fig3j"):
        pj = pair_jumps(name, params.reservoir.baseline_A)
        for k, pre, d, v in pj:
            ratios.setdefault(float(v), []).append(d / (icpt + slope * pre))
    measured = {f"{v:g}": {"mean": float(np.mean(r)), "std": float(np.std(r)), "n": len(r)}
                for v, r in sorted(ratios.items())}

    report = {
        "knots_vtg_V": KNOTS_V,
        "gain": params.reservoir.tg_modulation.y,
        "fig3i_fit_rmse_uA": float(np.sqrt(np.mean(err ** 2))),
        "fig3i_fit_max_abs_err_uA": float(np.abs(err).max()),
        "model_free_gain_by_vtg": measured,
        "model_free_tg0_line": {"intercept_A": float(icpt), "slope": float(slope),
                                "note": "Fig.3h pair jumps vs I_pre, straight-line fit; used only for this check"},
    }
    return params, report


def main():
    params = MPBTFTParams.load()
    params, rep = fit(params)
    params.save()
    out = ROOT / "fitting" / "results" / "tg_modulation.json"
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
