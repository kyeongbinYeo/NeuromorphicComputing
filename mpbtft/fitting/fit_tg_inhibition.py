"""
LIF 억제 펄스 (TG: -3 V → 5.0 V → -3 V, 100 us) — 상태: experimental (데이터 부족).

데이터 사정
  Fig.4e–g Source data는 첫 펄스열이 끝난 뒤 1 ms(t_reset) 동안 휴지 전류가 0으로 비어 있다.
  억제 펄스 직전·직후 I_D를 직접 읽을 수 없고, 억제 효과는 두 번째 펄스열(13개)의
  펄스 중 전류에서만 보인다. 같은 소자에서 '억제 없이 t_reset 1 ms'인 대조 측정도 Source data에 없다
  (Supp. Fig.18a는 그림만 있음). 그래서 N = 1 억제의 절대 효과는 분리할 수 없다.

이 스크립트가 하는 일
  1. 모델 없는 경향: 각 곡선의 두 번째 펄스열 처음 3개 평균 (Fig.4e, 4f, 4g)
  2. 같은 소자 안의 상대 효과: (N개 억제 곡선) − (N = 1 곡선)의 두 번째 펄스열 차이로
     retention(억제 펄스 1개 뒤 남는 초과 전류 비율)을 best-fit
  3. 식별성 검사: best-fit retention과 retention = 1(효과 없음)의 오차 비교,
     모델이 내는 차이 크기와 데이터 차이 크기 비교
  결과 retention은 enabled_by_default = False 로 저장한다 (MPBTFT(..., allow_experimental=True)일 때만 사용).

가정
  - 억제 펄스 N개를 10 us 간격으로 놓고, 마지막 펄스가 두 번째 펄스열 시작 10 us 전에 끝난다 (그림 4g 배치)
  - 억제 펄스 1개 = 초과 전류(I_D − baseline)를 retention 배

    python fitting/fit_tg_inhibition.py
"""
from __future__ import annotations

import json
import warnings

import numpy as np
from scipy.optimize import least_squares

from common import EXC_PERIOD_S, ROOT, envelope, find_trains, load_curve, simulate_lif_protocol
from lif import EXC_WIDTH_S
from parameters import MPBTFTParams, TGInhibitionParams

NOTE = ("Fig.4e-g source data are blank (0 A) during the 1 ms reset window, so I_D right before/after the "
        "inhibitory pulse is not measured, and there is no no-inhibition control at t_reset = 1 ms. "
        "Retention was fitted to N-vs-N=1 differences of the second excitation train; the v1 state model "
        "reproduces only a small part of the measured difference, so the value is not identifiable.")


def fig4g(n):
    t, i = load_curve(f"tg_inhibition/fig4g_N{n}.csv")
    trains = find_trains(t, i)
    envs = [envelope(t, i, tr["t0"], tr["n"]) for tr in trains]
    return [(tr["t0"], tr["n"]) for tr in trains], envs


def _set(params, r, domain=(0.0, 1.0)):
    params.lif.tg_inhibition = TGInhibitionParams(5.0, 100e-6, float(r), list(domain), "experimental", False, NOTE)


def simulate_train2(params, n, r):
    _set(params, r)
    trains, _ = fig4g(n)
    env, _, pre = simulate_lif_protocol(params, trains, inh=(n, 1), strict=False)
    return env[1], pre


def model_free_trend():
    trend = {}
    for tag, files in (("fig4e_500us_by_vinh", [f"fig4e_vinh_{v}V" for v in range(1, 6)]),
                       ("fig4f_3V_by_width", [f"fig4f_width_{w}us" for w in (10, 50, 100, 500)]),
                       ("fig4g_5V_100us_by_N", [f"fig4g_N{n}" for n in range(1, 6)])):
        trend[tag] = {}
        for fn in files:
            t, i = load_curve(f"tg_inhibition/{fn}.csv")
            tr = find_trains(t, i)
            # 억제 펄스 동안 전류가 문턱을 넘어 두 펄스열이 이어 보이는 곡선이 있으므로
            # 두 번째 펄스열 시작은 프로토콜(첫 펄스열 끝 + t_reset 1.0 ms)로 정한다.
            t0_1 = tr[0]["t0"]
            t0_2 = t0_1 + 29 * EXC_PERIOD_S + EXC_WIDTH_S + 1.0e-3
            e1 = envelope(t, i, t0_1, 30)
            e2 = envelope(t, i, t0_2, 13)
            trend[tag][fn] = {"train1_last_uA": float(e1[-1] * 1e6),
                              "train2_first3_mean_uA": float(np.mean(e2[:3]) * 1e6),
                              "train2_last_uA": float(e2[-1] * 1e6)}
    return trend


def fit(params: MPBTFTParams):
    data = {n: fig4g(n)[1][1] for n in range(1, 6)}

    def diff_res(r, ns):
        base_sim, _ = simulate_train2(params, 1, r)
        out = []
        for n in ns:
            sim, _ = simulate_train2(params, n, r)
            out.append(((sim - base_sim) - (data[n] - data[1])) * 1e6)
        return np.concatenate(out)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        sol = least_squares(lambda x: diff_res(x[0], [2, 3, 4, 5]), [0.8], bounds=(0.0, 1.0))
        r_best = float(sol.x[0])
        rmse_best = float(np.sqrt(np.mean(diff_res(r_best, [2, 3, 4, 5]) ** 2)))
        rmse_none = float(np.sqrt(np.mean(diff_res(1.0, [2, 3, 4, 5]) ** 2)))
        rmse_zero = float(np.sqrt(np.mean(diff_res(0.0, [2, 3, 4, 5]) ** 2)))

        per_n, pre_all = {}, []
        base_sim, _ = simulate_train2(params, 1, r_best)
        for n in range(1, 6):
            sim, pre = simulate_train2(params, n, r_best)
            pre_all.extend(pre)
            per_n[f"N{n}"] = {
                "id_pre_A": [float(v) for v in pre],
                "train2_first_pulse_diff_vs_N1_uA": {
                    "data": float((data[n][0] - data[1][0]) * 1e6),
                    "model": float((sim[0] - base_sim[0]) * 1e6),
                },
                "train2_last_pulse_diff_vs_N1_uA": {
                    "data": float((data[n][-1] - data[1][-1]) * 1e6),
                    "model": float((sim[-1] - base_sim[-1]) * 1e6),
                },
            }

    lo, hi = float(min(pre_all)), float(max(pre_all))
    domain = [max(params.lif.baseline_A, lo - 0.02e-6), hi + 0.02e-6]
    _set(params, r_best, domain)

    report = {
        "status": "experimental (not identifiable from source data)",
        "retention_best_fit": r_best,
        "enabled_by_default": False,
        "id_pre_domain_A": domain,
        "identifiability": {
            "diff_rmse_uA_best_fit": rmse_best,
            "diff_rmse_uA_retention_1_no_effect": rmse_none,
            "diff_rmse_uA_retention_0_full_reset": rmse_zero,
        },
        "per_N": per_n,
        "data_trend_model_free": model_free_trend(),
        "missing_evidence": NOTE,
    }
    return params, report


def main():
    params = MPBTFTParams.load()
    params, rep = fit(params)
    params.save()
    out = ROOT / "fitting" / "results" / "tg_inhibition.json"
    out.write_text(json.dumps(rep, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in rep.items() if k != "data_trend_model_free"}, indent=2))


if __name__ == "__main__":
    main()
