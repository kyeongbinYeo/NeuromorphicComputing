import csv
import math
from pathlib import Path

import pytest

from fetft import FeTFT, ProtocolExhaustedError, StateUnavailableError
from fetft.parameters import load_protocol

ROOT = Path(__file__).resolve().parents[1]


def test_load_32_and_source_transcription():
    steps, _ = load_protocol()
    with (ROOT / 'data/fig2f_protocol.csv').open(newline='', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    assert len(steps) == len(rows) == 32
    assert [s.conductance_after_S for s in steps] == [float(r['conductance_after_S']) for r in rows]


def test_initial_state_unavailable_and_no_pulse_zero():
    d = FeTFT()
    assert d.protocol_position == 0 and d.last_event is None
    with pytest.raises(StateUnavailableError):
        d.read_conductance()
    with pytest.raises(StateUnavailableError):
        d.read_current()
    event = d.apply_next_protocol_pulse()
    assert event.pulse_number == 1 and event.conductance_before_S is None
    assert event.delta_conductance_S is None
    assert d.read_conductance() == event.conductance_after_S


def test_protocol_and_complete_replay():
    d = FeTFT()
    steps, metadata = load_protocol()
    assert metadata['read_vgs_V'] == 1 and metadata['read_vds_V'] == .1
    for i, expected in enumerate(steps):
        e = d.apply_next_protocol_pulse()
        assert e == expected and d.protocol_position == i + 1
        assert e.operation == ('PGM' if i < 16 else 'ERS')
        assert e.pulse_voltage_V == pytest.approx(3.5 + .04*i if i < 16 else -4.35 - .05*(i-16))
        assert e.pulse_width_s == 10e-6
        assert e.read_vgs_V == 1 and e.read_vds_V == .1
        assert d.read_conductance() == expected.conductance_after_S
        if i:
            assert e.conductance_before_S == steps[i-1].conductance_after_S
            assert math.isclose(e.delta_conductance_S, e.conductance_after_S - e.conductance_before_S, abs_tol=1e-22)
            assert e.delta_conductance_S > 0 if i < 16 else e.delta_conductance_S < 0


def test_read_is_pure_and_fixed_bias():
    a, b = FeTFT(), FeTFT()
    a.apply_next_protocol_pulse()
    b.apply_next_protocol_pulse()
    event = b.last_event
    for _ in range(20):
        assert b.read_conductance() == event.conductance_after_S
        assert b.read_current() == event.conductance_after_S * .1
    assert b.protocol_position == 1 and b.last_event is event
    assert a.apply_next_protocol_pulse() == b.apply_next_protocol_pulse()


def test_exhaustion_no_wrap_and_initialize():
    d = FeTFT()
    for _ in range(32):
        d.apply_next_protocol_pulse()
    last = d.read_conductance()
    for _ in range(2):
        with pytest.raises(ProtocolExhaustedError):
            d.apply_next_protocol_pulse()
        assert d.protocol_position == 32 and d.read_conductance() == last
    d.initialize()
    assert d.protocol_position == 0 and d.last_event is None
    with pytest.raises(StateUnavailableError):
        d.read_conductance()
    assert d.apply_next_protocol_pulse().pulse_number == 1


def test_unsupported_arbitrary_input_and_invalid_reset():
    d = FeTFT()
    assert not hasattr(d, 'apply_pgm_pulse') and not hasattr(d, 'apply_ers_pulse')
    with pytest.raises(TypeError):
        d.initialize(12)
    with pytest.raises(TypeError):
        d.apply_next_protocol_pulse(4.0)


def test_validation_and_variability():
    from fetft.validation.validate_fig2f import validate
    from fetft.validation.analyze_fig2g_variability import analyze
    r = validate()
    assert r['states'] == 32 and r['transitions'] == 31 and r['rmse_S'] == 0
    g = analyze()
    assert g['extra_points'] == 160 and len(g['per_pulse_index']) == 32
    assert g['cycle_1_vs_20_rmse_S'] * 1e9 == pytest.approx(9.056131117, rel=1e-8)
    assert g['cv_min'] == pytest.approx(0.01090930676, rel=1e-8)
    assert g['cv_max'] == pytest.approx(0.03333927369, rel=1e-8)
