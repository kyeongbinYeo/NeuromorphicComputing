"""
MPBTFT v1 단위 테스트 (사양서 23장).

    python -m pytest tests -q
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from domains import OutOfCalibratedStateError, UncalibratedFeatureError, UnsupportedOperatingPointError  # noqa: E402
from lif import LIFNeuron  # noqa: E402
from model import MPBTFT  # noqa: E402
from parameters import MPBTFTParams  # noqa: E402
from reservoir import Reservoir, run_bit_train  # noqa: E402

P = MPBTFTParams.load()
W_RES = 100e-6
W_EXC = 500e-6


def res():
    return MPBTFT(P, mode="reservoir")


def lif(**kw):
    return MPBTFT(P, mode="lif", **kw)


# ------------------------------------------------------------------ 시간
def test_past_time_read_raises():
    d = res()
    d.apply_bg_pulse(1e-3, 4.0, W_RES, 0.0)
    with pytest.raises(ValueError):
        d.read_current(0.5e-3)


def test_past_time_event_raises():
    d = res()
    d.apply_bg_pulse(3e-3, 4.0, W_RES, 0.0)
    with pytest.raises(ValueError):
        d.apply_bg_pulse(1e-3, 4.0, W_RES, 0.0)


def test_overlapping_events_raise():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    with pytest.raises(ValueError, match="Overlapping"):
        d.apply_bg_pulse(50e-6, 4.0, W_RES, 0.0)


def test_lif_bg_tg_overlap_message():
    d = lif(allow_experimental=True)
    d.apply_bg_pulse(0.0, 2.5, W_EXC, -3.0)
    with pytest.raises(ValueError, match="Overlapping BG excitation and TG inhibition"):
        d.apply_tg_inhibition(0.3e-3, 5.0, 100e-6)


def test_touching_events_are_allowed():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    d.apply_bg_pulse(W_RES, 4.0, W_RES, 0.0)
    e = lif(allow_experimental=True)
    e.apply_bg_pulse(0.0, 2.5, W_EXC, -3.0)
    e.apply_tg_inhibition(W_EXC, 5.0, 100e-6)
    e.apply_bg_pulse(W_EXC + 100e-6, 2.5, W_EXC, -3.0)


def test_inhibition_outside_calibrated_state_raises():
    d = lif(allow_experimental=True)
    LIFNeuron(d).excite_train(0.0, 30)
    with pytest.raises(OutOfCalibratedStateError):
        d.apply_tg_inhibition(d.last_update_time_s, 5.0, 100e-6)


def test_read_during_pulse_raises():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    with pytest.raises(ValueError, match="in progress"):
        d.read_current(50e-6)


# ------------------------------------------------------------- read purity
def test_read_is_pure():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    a = d.read_current(1e-3)
    b = d.read_current(1e-3)
    assert a == b


def test_number_of_reads_does_not_change_trajectory():
    d1, d2 = res(), res()
    for d in (d1, d2):
        d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    for k in range(100):
        d2.read_current(W_RES + k * 25e-6)
    for d in (d1, d2):
        d.apply_bg_pulse(3e-3, 4.0, W_RES, 0.0)
    assert d1.read_current(6e-3) == d2.read_current(6e-3)


def test_read_any_time_without_input():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    i1, i2 = d.read_current(1e-3), d.read_current(13e-3)
    assert i2 < i1


# ------------------------------------------------------------- relaxation
@pytest.mark.parametrize("mode,args", [("reservoir", (4.0, W_RES, 0.0)), ("lif", (2.5, W_EXC, -3.0))])
def test_relaxation_moves_to_baseline(mode, args):
    d = MPBTFT(P, mode=mode)
    d.apply_bg_pulse(0.0, *args)
    i_soon = d.read_current(args[1] + 1e-4)
    i_late = d.read_current(1.0)
    base = d.baseline_current_A
    assert i_soon > i_late
    assert abs(i_late - base) < 1e-3 * (i_soon - base)


# --------------------------------------------------------------------- BG
@pytest.mark.parametrize("mode,args", [("reservoir", (4.0, W_RES, 0.0)), ("lif", (2.5, W_EXC, -3.0))])
def test_bg_pulse_increases_id(mode, args):
    d = MPBTFT(P, mode=mode)
    pre = d.read_current(0.0)
    post = d.apply_bg_pulse(0.0, *args)
    assert post > pre


def test_state_dependence_higher_current_smaller_update():
    tab = P.reservoir.bg_update.delta_id_A
    lo, hi = tab.lo, tab.hi
    assert tab(lo) > tab(hi)
    ys = [tab(lo + k * (hi - lo) / 20) for k in range(21)]
    assert all(b <= a + 1e-15 for a, b in zip(ys, ys[1:]))


def test_no_constant_increment():
    tab = P.reservoir.bg_update.delta_id_A
    assert len(set(round(v, 12) for v in tab.y)) > 1


def test_lif_update_depends_on_state():
    tab = P.lif.bg_update.delta_id_A
    assert tab(tab.lo) > tab(tab.hi)


# ------------------------------------------------------------ TG modulation
def test_positive_tg_reduces_bg_update():
    jumps = []
    for v in (0.0, 1.0, 2.0, 3.0, 5.0):
        d = res()
        pre = d.read_current(0.0)
        jumps.append(d.apply_bg_pulse(0.0, 4.0, W_RES, v) - pre)
    assert all(b < a for a, b in zip(jumps, jumps[1:]))


def test_tg_gain_is_one_at_zero():
    assert P.reservoir.tg_modulation(0.0) == pytest.approx(1.0)


# ----------------------------------------------------------- TG inhibition
def test_tg_inhibition_blocked_by_default():
    d = lif()
    LIFNeuron(d).excite_train(0.0, 10)
    with pytest.raises(UncalibratedFeatureError):
        d.apply_tg_inhibition(d.last_update_time_s + 0.5e-3, 5.0, 100e-6)


def test_tg_inhibition_decreases_id_when_enabled():
    d = lif(allow_experimental=True)
    _, t_end = LIFNeuron(d).excite_train(0.0, 10)
    t = t_end + 0.5e-3
    pre = d.read_current(t)
    lo, hi = P.lif.tg_inhibition.id_pre_domain_A
    assert lo <= pre <= hi
    post = d.apply_tg_inhibition(t, 5.0, 100e-6)
    assert post < pre


def test_tg_inhibition_not_in_reservoir_mode():
    with pytest.raises(UnsupportedOperatingPointError):
        res().apply_tg_inhibition(0.0, 5.0, 100e-6)


# ------------------------------------------------------------------ domain
@pytest.mark.parametrize("v,w,tg", [(4.5, W_RES, 0.0), (4.0, 73e-6, 0.0), (4.37, 73e-6, 0.0), (4.0, W_RES, 6.0),
                                    (4.0, W_RES, -1.0)])
def test_reservoir_unsupported_inputs(v, w, tg):
    with pytest.raises(UnsupportedOperatingPointError):
        res().apply_bg_pulse(0.0, v, w, tg)


@pytest.mark.parametrize("v,w,tg", [(4.0, W_RES, 0.0), (2.5, W_RES, -3.0), (2.5, W_EXC, 0.0), (3.0, W_EXC, -3.0)])
def test_lif_unsupported_inputs(v, w, tg):
    with pytest.raises(UnsupportedOperatingPointError):
        lif().apply_bg_pulse(0.0, v, w, tg)


@pytest.mark.parametrize("v,w", [(3.0, 100e-6), (5.0, 500e-6)])
def test_unsupported_inhibition(v, w):
    with pytest.raises(UnsupportedOperatingPointError):
        lif(allow_experimental=True).apply_tg_inhibition(0.0, v, w)


def test_state_outside_calibration_raises():
    d = res()
    with pytest.raises(OutOfCalibratedStateError):
        for k in range(8):
            d.apply_bg_pulse(k * 3e-3, 4.0, W_RES, 0.0)


def test_non_strict_warns_instead():
    d = MPBTFT(P, mode="reservoir", strict=False)
    with pytest.warns(RuntimeWarning):
        for k in range(8):
            d.apply_bg_pulse(k * 3e-3, 4.0, W_RES, 0.0)


# ------------------------------------------------------------ architecture
def test_same_class_both_modes():
    assert type(res()) is type(lif())


def test_lif_firing_is_outside_core():
    assert not hasattr(MPBTFT, "fire")
    d = lif()
    n = LIFNeuron(d)
    on, _ = n.excite_train(0.0, 30)
    assert len(n.spikes_s) > 0
    assert max(on) >= n.threshold_A


def test_initialize_is_simulation_reset():
    d = res()
    d.apply_bg_pulse(0.0, 4.0, W_RES, 0.0)
    d.initialize(1.0)
    assert d.read_current(1.0) == pytest.approx(d.baseline_current_A)


def test_reservoir_helper_runs_paper_schedule():
    d = res()
    out = run_bit_train(d, "1011", tg_voltages_V=[5.0, 3.0, 1.5, 0.0])
    assert len(out) == 4 and out[-1] > out[1]
    feats = Reservoir(2, P, tg_voltages_V=[5.0, 3.0, 1.5, 0.0]).encode(["1011", "0001"])
    assert feats[0] != feats[1]
