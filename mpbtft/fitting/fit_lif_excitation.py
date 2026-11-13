"""
LIF 모드 흥분 펄스(2.5 V / 500 us, 간격 10 us, TG -3 V)와 휴지 상태 감쇠(leak)를 피팅한다.

데이터: Fig.4b (30 + 30 펄스, t_reset 3 ms). Hold-out은 validation/validate_lif_excitation.py
(Fig.4c V_base = 0 V 곡선, Fig.4g 첫 펄스열 5개).

관측되는 두 가지 전류
  - 휴지 전류 I_D (V_BG = 0 V, V_TG = -3 V): 펄스열이 끝난 뒤 self-reset 곡선. 모델의 상태값.
  - 펄스 중 전류 (V_BG = 2.5 V): 펄스열 동안의 윗선(envelope). 뉴런이 문턱과 비교하는 값.
  펄스 사이 간격(10 us)이 샘플 1개라 펄스열 도중의 휴지 전류는 직접 읽을 수 없다.

가정 (README Known limitations에 기록)
  펄스 중 전류 = 휴지 전류 + on_state_offset (상수).
  분극이 문턱 전압만 옮기고 transconductance는 그대로라는 선형 영역 근사.
  on_state_offset은 펄스열 끝에서 (마지막 펄스 중 전류) − (감쇠 곡선을 펄스 끝으로 외삽한 휴지 전류)로 정해진다.

자유 변수: fast_share, τ_fast, τ_slow, on_state_offset, ΔI 표 7점(단조 비증가)
고정: baseline = 첫 펄스열 직전 휴지 전류 평균

    python fitting/fit_lif_excitation.py
"""
from __future__ import annotations

import json
import warnings

import numpy as np
from scipy.optimize import least_squares

from common import ROOT, envelope, find_trains, load_curve, rest_current, simulate_lif_protocol
from parameters import MPBTFTParams
from template import LIF_DELTA_KNOTS_A, lif_mode

DECAY_WINDOW_S = (20e-6, 2.9e-3)
DECAY_STRIDE = 2


def fig4b_targets():
    t, i = load_curve("lif_excitation/fig4b.csv")
    trains = find_trains(t, i)
    envs = [envelope(t, i, tr["t0"], tr["n"]) for tr in trains]
    decay_t, decay_i = [], []
    for tr in trains:
        m = (t > tr["t_end"] + DECAY_WINDOW_S[0]) & (t < tr["t_end"] + DECAY_WINDOW_S[1])
        decay_t.append(t[m][::DECAY_STRIDE]); decay_i.append(i[m][::DECAY_STRIDE])
    base = rest_current(t, i, trains[0]["t0"])
    return trains, envs, np.concatenate(decay_t), np.concatenate(decay_i), base


def unpack(x, base, inhibition):
    w, lt_f, lt_s, off = x[:4]
    d0, decs = x[4], x[5:]
    delta = [(d0 - float(np.sum(decs[:k]))) * 1e-6 for k in range(len(decs) + 1)]
    return lif_mode(base, float(w), 10 ** lt_f, 10 ** lt_s, delta, off * 1e-6, inhibition)


def fit(params: MPBTFTParams):
    trains, envs, dt_, di_, base = fig4b_targets()
    inhibition = params.lif.tg_inhibition
    tr_list = [(tr["t0"], tr["n"]) for tr in trains]
    env_data = np.concatenate(envs)

    def residuals(x):
        params.lif = unpack(x, base, inhibition)
        sim_env, reads, _ = simulate_lif_protocol(params, tr_list, decay_times=list(dt_), strict=False)
        return np.concatenate([(np.concatenate(sim_env) - env_data) * 1e6, (reads - di_) * 1e6])

    n_dec = len(LIF_DELTA_KNOTS_A) - 1
    x0 = [0.25, -3.7, -3.05, 4.1, 0.7] + [0.05] * n_dec
    lb = [0.0, -5.0, -3.7, 3.0, 0.05] + [0.0] * n_dec
    ub = [0.9, -2.7, -2.0, 5.5, 2.0] + [1.0] * n_dec
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sol = least_squares(residuals, x0, bounds=(lb, ub), diff_step=1e-3)
    params.lif = unpack(sol.x, base, inhibition)

    sim_env, reads, _ = simulate_lif_protocol(params, tr_list, decay_times=list(dt_), strict=False)
    e_env = (np.concatenate(sim_env) - env_data) * 1e6
    e_dec = (reads - di_) * 1e6
    rl = params.lif.relaxation
    report = {
        "baseline_A": base,
        "fast_share": rl.fast_share, "tau_fast_s": rl.tau_fast_s, "tau_slow_s": rl.tau_slow_s.y[0],
        "on_state_offset_A": params.lif.on_state_offset_A,
        "delta_table": {"id_pre_A": params.lif.bg_update.delta_id_A.x, "delta_A": params.lif.bg_update.delta_id_A.y},
        "fig4b_trains": [{"t0_s": a, "n": n} for a, n in tr_list],
        "fig4b_envelope_rmse_uA": float(np.sqrt(np.mean(e_env ** 2))),
        "fig4b_envelope_max_abs_err_uA": float(np.abs(e_env).max()),
        "fig4b_self_reset_rmse_uA": float(np.sqrt(np.mean(e_dec ** 2))),
        "fig4b_self_reset_max_abs_err_uA": float(np.abs(e_dec).max()),
    }
    return params, report


def main():
    params = MPBTFTParams.load()
    params, rep = fit(params)
    params.save()
    out = ROOT / "fitting" / "results" / "lif_excitation.json"
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps(rep, indent=2))


if __name__ == "__main__":
    main()
