"""
Reservoir 모드의 BG 증가 표 ΔI_D(I_D,pre) 와 감쇠 파라미터를 함께 피팅한다 (TG = 0 V, 4.0 V / 100 us).

목표 데이터
  - Fig.3h: 16개 4-bit 입력 × 5 시점 (같은 소자, TG 없음)
  - Fig.3f 4.0 V, 4.5 V: 펄스 1개 뒤 감쇠 '모양' (초과 전류 / 펄스 직후 초과 전류).
    Fig.3f는 3h와 소자·기준 전류가 달라 절대값은 쓰지 않는다. 3.5 V 곡선은 R² 0.86으로 노이즈가 커서 뺀다.

자유 변수
  - fast_share, τ_fast, τ_slow 표(초과 전류 0.5 / 1.5 / 3.0 uA에서의 값)
  - ΔI 표: 펄스 직전 I_D = baseline + 0, 0.6, 1.2, 1.8 uA 에서의 값 (PCHIP, 단조 비증가로 제약)
고정
  - baseline = Fig.3h/3i/3j의 pulse number 0 평균 (펄스 전 전류)

모델과 무관한 검사: 같은 펄스 직전 전류에서 데이터로 직접 잰 증가분(pair_jumps)과 표를 비교해
fitting/results/bg_update.json에 남긴다.

    python fitting/fit_bg_update.py
"""
from __future__ import annotations

import json

import numpy as np
from scipy.optimize import least_squares

from common import ROOT, load_states, pair_jumps, simulate_states
from fit_relaxation import fit as fit_fig3f, load_fig3f
from parameters import MPBTFTParams, DEFAULT_PARAMS_PATH
from template import RES_DELTA_KNOTS_REL_A, reservoir_mode, starting_params

SHAPE_WEIGHT_UA = 1.0      # 3f 모양 오차(무차원)를 uA 단위 오차와 같은 무게로 두기 위한 배율
SHAPE_STRIDE = 10          # 3f 곡선은 2,451점 → 10점마다 1개


def baseline_from_data():
    vals = [load_states(n)[1][:, 0] for n in ("fig3h", "fig3i", "fig3j")]
    return float(np.mean(np.concatenate(vals)))


def unpack(x, base, tg_gain):
    w, lt_f, lt1, lt2, lt3 = x[:5]
    # ΔI 표는 단조 비증가: 첫 값 − 누적 감소량 (감소량 ≥ 0)
    d0, decs = x[5], x[6:]
    delta = [(d0 - float(np.sum(decs[:k]))) * 1e-6 for k in range(len(decs) + 1)]
    return reservoir_mode(base, float(w), 10 ** lt_f, [10 ** lt1, 10 ** lt2, 10 ** lt3], delta, tg_gain)


def shape_targets():
    rep = fit_fig3f()
    curves = load_fig3f()
    out = []
    for v in ("4.0", "4.5"):
        t, i = curves[v]
        e0 = rep["curves"][v]["excess_at_pulse_end_A"]
        y = (i - rep["shared_I0_A"]) / e0
        out.append((t[::SHAPE_STRIDE], y[::SHAPE_STRIDE], e0))
    return out, rep


def model_shape(mode, t, e0):
    rp = mode.relaxation
    w = rp.fast_share
    ts = rp.tau_slow_s(e0)
    return w * np.exp(-t / rp.tau_fast_s) + (1 - w) * np.exp(-t / ts)


def fit(params: MPBTFTParams):
    base = baseline_from_data()
    _, data3h = load_states("fig3h")
    shapes, rep3f = shape_targets()
    tg_gain = params.reservoir.tg_modulation

    def residuals(x):
        params.reservoir = unpack(x, base, tg_gain)
        sim = simulate_states(params, "fig3h", strict=False)
        r = [((sim - data3h) * 1e6).ravel()]
        for t, y, e0 in shapes:
            r.append((model_shape(params.reservoir, t, e0) - y) * SHAPE_WEIGHT_UA)
        return np.concatenate(r)

    x0 = [0.15, -3.0, -1.7, -1.7, -1.8] + [0.9, 0.03, 0.03, 0.03]
    lb = [0.0, -4.5, -2.7, -2.7, -2.7] + [0.1, 0.0, 0.0, 0.0]
    ub = [0.9, -2.0, -0.5, -0.5, -0.5] + [3.0, 0.5, 0.5, 0.5]
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sol = least_squares(residuals, x0, bounds=(lb, ub), diff_step=1e-3)
    params.reservoir = unpack(sol.x, base, tg_gain)

    sim = simulate_states(params, "fig3h", strict=False)
    err = (sim - data3h) * 1e6
    pj = pair_jumps("fig3h", base)
    table = params.reservoir.bg_update.delta_id_A
    m = params.reservoir.relaxation
    report = {
        "baseline_A": base,
        "fast_share": m.fast_share, "tau_fast_s": m.tau_fast_s,
        "tau_slow_knots": {"excess_A": m.tau_slow_s.x, "tau_s": m.tau_slow_s.y},
        "delta_table": {"id_pre_A": table.x, "delta_A": table.y},
        "fig3h_fit_rmse_uA": float(np.sqrt(np.mean(err ** 2))),
        "fig3h_fit_max_abs_err_uA": float(np.abs(err).max()),
        "fig3f_shape_rmse": {
            v: float(np.sqrt(np.mean((model_shape(params.reservoir, t, e0) - y) ** 2)))
            for v, (t, y, e0) in zip(("4.0", "4.5"), shapes)
        },
        "model_free_pair_check": {
            "n": int(len(pj)),
            "note": "ΔI measured as (sequence with pulse) − (same history, no pulse) at the read point; "
                    "I_pre ≈ the no-pulse value. Compared with the read-point jump the model produces.",
        },
        "fig3f_per_curve": rep3f,
    }
    return params, report


def main():
    params = MPBTFTParams.load() if DEFAULT_PARAMS_PATH.exists() else starting_params()
    params, rep = fit(params)
    params.save()
    out = ROOT / "fitting" / "results" / "bg_update.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "fig3f_per_curve"}, indent=2))


if __name__ == "__main__":
    main()
