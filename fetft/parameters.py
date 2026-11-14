"""Load the measured Fig.2f protocol and its fixed read conditions."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent


@dataclass(frozen=True)
class ProtocolStep:
    pulse_number: int
    operation: str
    pulse_voltage_V: float
    pulse_width_s: float
    conductance_before_S: float | None
    conductance_after_S: float
    delta_conductance_S: float | None
    read_vgs_V: float
    read_vds_V: float


def load_protocol():
    """Load and verify the entire fixed protocol without extrapolation."""
    with (ROOT / "params" / "v1_params.json").open(encoding="utf-8") as f:
        metadata = json.load(f)
    with (ROOT / "data" / "fig2f_protocol.csv").open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 32:
        raise ValueError("Fig.2f requires exactly 32 measured states")
    steps = []
    for k, r in enumerate(rows, 1):
        number = int(r['pulse_number'])
        before = float(r['conductance_before_S']) if r['conductance_before_S'] else None
        delta = float(r['delta_conductance_S']) if r['delta_conductance_S'] else None
        step = ProtocolStep(number, r['operation'], float(r['pulse_voltage_V']), float(r['pulse_width_s']),
                            before, float(r['conductance_after_S']), delta,
                            float(r['read_vgs_V']), float(r['read_vds_V']))
        expected_v = 3.5 + (k - 1) * .04 if k <= 16 else -4.35 - (k - 17) * .05
        valid = (number == k and step.operation == ('PGM' if k <= 16 else 'ERS')
                 and math.isclose(step.pulse_voltage_V, expected_v, abs_tol=1e-12)
                 and step.pulse_width_s == metadata['pulse_width_s']
                 and step.read_vgs_V == metadata['read_vgs_V']
                 and step.read_vds_V == metadata['read_vds_V']
                 and math.isfinite(step.conductance_after_S) and step.conductance_after_S > 0)
        if k == 1:
            valid = valid and before is None and delta is None
        else:
            valid = (valid and before is not None and delta is not None
                     and before == steps[-1].conductance_after_S
                     and math.isclose(delta, step.conductance_after_S - before, rel_tol=1e-12, abs_tol=1e-22)
                     and (delta > 0 if k <= 16 else delta < 0))
        if not valid:
            raise ValueError(f"Invalid Fig.2f protocol row {k}")
        steps.append(step)
    return tuple(steps), metadata
