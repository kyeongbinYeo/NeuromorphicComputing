"""피팅 시작점이 되는 파라미터 묶음과, 벡터 → 모드 파라미터 변환."""
from __future__ import annotations

import numpy as np

import common  # noqa: F401  (sys.path 설정)
from parameters import (BGUpdateParams, ModeParams, MPBTFTParams, RelaxationParams, Table,
                        TGInhibitionParams)

RES_TAU_SLOW_KNOTS_A = [0.5e-6, 1.5e-6, 3.0e-6]          # 초과 전류
RES_DELTA_KNOTS_REL_A = [0.0, 0.6e-6, 1.2e-6, 1.8e-6]   # baseline 기준 펄스 직전 I_D (최대 = 측정된 직전 전류 범위)
LIF_DELTA_KNOTS_A = [None, 0.6e-6, 0.9e-6, 1.2e-6, 1.5e-6, 1.8e-6, 2.1e-6]  # 첫 칸 = baseline


def reservoir_mode(baseline_A, fast_share, tau_fast_s, tau_slow_s, delta_A, tg_gain=None):
    tg = tg_gain if tg_gain is not None else Table([0.0, 5.0], [1.0, 1.0])
    return ModeParams(
        name="reservoir",
        baseline_A=baseline_A,
        relaxation=RelaxationParams(fast_share, tau_fast_s, Table(RES_TAU_SLOW_KNOTS_A, tau_slow_s)),
        bg_update=BGUpdateParams(4.0, 100e-6,
                                 Table([baseline_A + d for d in RES_DELTA_KNOTS_REL_A], delta_A)),
        tg_modulation=tg,
    )


def lif_mode(baseline_A, fast_share, tau_fast_s, tau_slow_s, delta_A, on_offset_A, inhibition=None):
    xs = [baseline_A] + LIF_DELTA_KNOTS_A[1:]
    return ModeParams(
        name="lif",
        baseline_A=baseline_A,
        relaxation=RelaxationParams(fast_share, tau_fast_s, Table([0.0, 3.0e-6], [tau_slow_s, tau_slow_s])),
        bg_update=BGUpdateParams(2.5, 500e-6, Table(xs, delta_A)),
        on_state_offset_A=on_offset_A,
        tg_inhibition=inhibition,
    )


def starting_params() -> MPBTFTParams:
    res = reservoir_mode(1.0e-6, 0.2, 8e-4, [17e-3, 17e-3, 17e-3],
                         [0.9e-6, 0.86e-6, 0.82e-6, 0.78e-6],
                         Table([0.0, 1.5, 3.0, 5.0], [1.0, 0.77, 0.59, 0.51]))
    lif = lif_mode(0.06e-6, 0.25, 2e-4, 0.9e-3, list(np.linspace(0.7e-6, 0.02e-6, 7)), 4.0e-6,
                   TGInhibitionParams(5.0, 100e-6, 0.8, [0.0, 2.0e-6]))
    return MPBTFTParams(reservoir=res, lif=lif)
