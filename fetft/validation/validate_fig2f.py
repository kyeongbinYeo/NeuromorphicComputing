"""Check replay fidelity, not independent predictive performance."""
from __future__ import annotations

import csv
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from fetft import FeTFT, StateUnavailableError, ProtocolExhaustedError


def validate():
    with (ROOT / 'fetft/data/fig2f_protocol.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    d = FeTFT()
    try:
        d.read_conductance()
        raise AssertionError('pre-pulse state should be unavailable')
    except StateUnavailableError:
        pass
    events = [d.apply_next_protocol_pulse() for _ in range(32)]
    expected = [float(r['conductance_after_S']) for r in rows]
    errors = [e.conductance_after_S - x for e, x in zip(events, expected)]
    assert len(rows) == len(events) == 32
    for i, e in enumerate(events):
        assert e.pulse_number == i + 1
        assert e.operation == ('PGM' if i < 16 else 'ERS')
        voltage = 3.5 + .04 * i if i < 16 else -4.35 - .05 * (i - 16)
        assert math.isclose(e.pulse_voltage_V, voltage, abs_tol=1e-12)
        assert e.pulse_width_s == 1e-5 and e.read_vgs_V == 1 and e.read_vds_V == .1
        if i:
            assert e.conductance_before_S == events[i-1].conductance_after_S
            assert math.isclose(e.delta_conductance_S, e.conductance_after_S - e.conductance_before_S,
                                rel_tol=1e-12, abs_tol=1e-22)
            assert e.delta_conductance_S > 0 if i < 16 else e.delta_conductance_S < 0
        else:
            assert e.conductance_before_S is None and e.delta_conductance_S is None
    try:
        d.apply_next_protocol_pulse()
        raise AssertionError('protocol should be exhausted')
    except ProtocolExhaustedError:
        pass
    source = ROOT / 'references/Analog reservoir computing via ferroelectric_Source data.xlsx'
    source_match = None
    if source.exists():
        import openpyxl
        w = openpyxl.load_workbook(source, data_only=True, read_only=True)
        try:
            source_rows = list(w['Fig.2'].iter_rows(min_row=3, max_row=34, min_col=9, max_col=10, values_only=True))
        finally:
            w.close()
        source_match = source_rows == [(i + 1, expected[i]) for i in range(32)]
        if not source_match:
            raise AssertionError('CSV and original source workbook differ')
    return {'kind': 'replay fidelity, not independent predictive validation', 'states': len(events),
            'transitions': 31, 'rmse_S': math.sqrt(sum(e*e for e in errors) / len(errors)),
            'source_xlsx_match': source_match, 'first_pre_state_unavailable': True,
            'pgm_direction_checked_transitions': 15, 'ers_direction_checked_transitions': 16}


if __name__ == '__main__':
    result = validate()
    out = ROOT / 'fetft/validation/results'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'fig2f_validation.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
