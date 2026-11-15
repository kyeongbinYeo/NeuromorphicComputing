"""Inspect LIF state after a 30-pulse train and compare Fig.18 references.

Run from mpbtft: python validation/diagnose_lif_residual_memory.py
The figure readings are approximate diagnostic references, not pass/fail criteria.
"""
from __future__ import annotations

import vcommon  # Set up the same import paths as the other validation scripts.
from lif import EXC_VOLTAGE_V, EXC_WIDTH_S, TG_BASE_V, LIFNeuron
from model import MPBTFT
from parameters import MPBTFTParams
from validate_lif_excitation import trend_reset_time


def diagnose(params):
    references = trend_reset_time(params)
    rows = []
    for reset_ms in (1, 2, 3):
        device = MPBTFT(params, mode="lif")
        neuron = LIFNeuron(device)
        _, end_s = neuron.excite_train(0.0, 30)
        start_s = end_s + reset_ms * 1e-3
        snapshot = device.state_snapshot(start_s)
        device.apply_bg_pulse(start_s, EXC_VOLTAGE_V, EXC_WIDTH_S, TG_BASE_V)
        event = device.last_event
        reference = references[f"t_reset_{reset_ms}ms"].get("figure_read_train2_first_pulse_uA")
        rows.append({
            "reset_ms": reset_ms,
            "snapshot": snapshot,
            "id_pre_A": event.id_pre_A,
            "id_post_A": event.id_post_A,
            "id_during_pulse_A": event.id_during_pulse_A,
            "delta_id_A": event.id_post_A - event.id_pre_A,
            "figure_reference_uA": reference,
        })
    return rows


def main():
    rows = diagnose(MPBTFTParams.load())
    print("State just before second train (uA)")
    print("reset ms | fast | slow | resting ID | ID - baseline")
    for row in rows:
        s = row["snapshot"]
        print(f"{row['reset_ms']:8d} | {s['fast_A']*1e6:.6f} | {s['slow_A']*1e6:.6f} | "
              f"{s['current_A']*1e6:.6f} | {(s['current_A']-s['baseline_A'])*1e6:.6f}")
    print("\nFirst excitation of second train (uA)")
    print("reset ms | pre ID | post resting ID | during pulse | delta ID")
    for row in rows:
        print(f"{row['reset_ms']:8d} | {row['id_pre_A']*1e6:.6f} | {row['id_post_A']*1e6:.6f} | "
              f"{row['id_during_pulse_A']*1e6:.6f} | {row['delta_id_A']*1e6:.6f}")
    print("\nSupp. Fig.18 approximate figure readings (diagnostic only; difference = model - reference, uA)")
    print("reset ms | model | figure reference | difference")
    for row in rows:
        ref = row["figure_reference_uA"]
        model = row["id_during_pulse_A"] * 1e6
        reference = f"{ref:.3f} | {model-ref:+.3f}" if ref is not None else "n/a | n/a"
        print(f"{row['reset_ms']:8d} | {model:.3f} | {reference}")


if __name__ == "__main__":
    main()
