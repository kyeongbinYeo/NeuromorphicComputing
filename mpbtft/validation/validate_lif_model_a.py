"""Evaluate nominal Model A against Fig.4g; only pulse 1 was used to fit."""
from __future__ import annotations

import json

import numpy as np

from vcommon import RESULTS
from fit_tg_inhibition import fig4g
from lif import INH_DELAY_S, INH_WIDTH_S, LIFNeuron
from model import MPBTFT
from parameters import MPBTFTParams


def evaluate(params):
    rows = {}
    first_excitation_gains = params.load_model_a_gains()
    if first_excitation_gains[0] == 0:
        raise ValueError("Relative gain is undefined when the N=1 gain is zero.")
    for n in range(1, 6):
        trains, measured = fig4g(n)
        device = MPBTFT(params, mode="lif", allow_experimental=True, inhibition_model="model_a")
        neuron = LIFNeuron(device)
        neuron.excite_train(*trains[0])
        second_start, count = trains[1]
        inh_start = second_start - INH_DELAY_S - n * INH_WIDTH_S - (n - 1) * INH_DELAY_S
        neuron.inhibit_train(inh_start, n)
        predicted, _ = neuron.excite_train(second_start, count)
        data = np.asarray(measured[1]) * 1e6
        model = np.asarray(predicted) * 1e6
        err = model - data
        rows[f"N{n}"] = {
            "first_excitation_gain": first_excitation_gains[n - 1],
            "relative_first_excitation_gain": first_excitation_gains[n - 1] / first_excitation_gains[0],
            "measured_first_uA": float(data[0]), "model_first_uA": float(model[0]),
            "first_error_uA": float(err[0]), "rmse_13_uA": float(np.sqrt(np.mean(err ** 2))),
            "rmse_pulses_2_to_13_uA": float(np.sqrt(np.mean(err[1:] ** 2))),
            "measured_final_uA": float(data[-1]), "model_final_uA": float(model[-1]),
            "measured_train_uA": data.tolist(), "model_train_uA": model.tolist(),
        }
    return rows


def main():
    rows = evaluate(MPBTFTParams.load())
    (RESULTS / "lif_model_a.json").write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    print("N | gain | relative gain H(N) | measured first | model first | error | RMSE 13 | RMSE 2-13 | measured final | model final (uA)")
    for name, r in rows.items():
        print(f"{name} | {r['first_excitation_gain']:.6f} | {r['relative_first_excitation_gain']:.6f} | "
              f"{r['measured_first_uA']:.6f} | {r['model_first_uA']:.6f} | "
              f"{r['first_error_uA']:+.6f} | {r['rmse_13_uA']:.6f} | {r['rmse_pulses_2_to_13_uA']:.6f} | "
              f"{r['measured_final_uA']:.6f} | {r['model_final_uA']:.6f}")


if __name__ == "__main__":
    main()
