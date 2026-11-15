"""Fit effective first-BG-excitation multipliers from Fig.4g first pulses.

Run from mpbtft: python fitting/fit_lif_model_a.py
Reset-window zeros are never used. The unconstrained gains need not be <= 1:
they scale the baseline BG increment, not the total current.
"""
from __future__ import annotations

import json

import numpy as np

from common import ROOT
from fit_tg_inhibition import fig4g
from parameters import MPBTFTParams


def monotone_decreasing(values):
    """Equal-weight isotonic least squares via pool-adjacent-violators."""
    blocks = []
    for value in values:
        blocks.append([float(value), 1])
        while len(blocks) > 1 and blocks[-2][0] < blocks[-1][0]:
            b, nb = blocks.pop()
            a, na = blocks.pop()
            blocks.append([(a * na + b * nb) / (na + nb), na + nb])
    return np.array([max(0.0, mean) for mean, count in blocks for _ in range(count)])


def fit(params):
    p = params.lif
    raw = np.array([fig4g(n)[1][1][0] for n in range(1, 6)])
    baseline_on = p.baseline_A + p.on_state_offset_A
    delta = p.bg_update.delta_id_A(p.baseline_A)
    gains = monotone_decreasing((raw - baseline_on) / delta)
    return {
        "description": "Nominal experimental Model A; fit only second-train first-pulse envelope, N=1..5.",
        "gain_meaning": "Effective one-shot multiplier applied to the first BG update after inhibition; not a physical TG gain. Includes calibration between the Fig.4b nominal model and Fig.4g measurement.",
        "source": "data/tg_inhibition/fig4g_N1.csv through fig4g_N5.csv; existing find_trains/envelope",
        "method": "equal-weight non-increasing isotonic least squares, gains constrained nonnegative",
        "baseline_A": p.baseline_A,
        "on_state_offset_A": p.on_state_offset_A,
        "baseline_bg_delta_A": delta,
        "raw_first_pulse_A": raw.tolist(),
        "monotonic_fitted_first_pulse_A": (baseline_on + delta * gains).tolist(),
        "gain": gains.tolist(),
    }


def main():
    report = fit(MPBTFTParams.load())
    path = ROOT / "params" / "lif_model_a.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
