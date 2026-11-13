"""
v1에서 지원하는 동작 조건(operating point)과 그 검사.

측정 데이터가 있는 조건만 허용하고, 그 밖의 입력은 계산하지 않고 오류를 낸다.
"""
from __future__ import annotations

import math


class UnsupportedOperatingPointError(ValueError):
    """v1이 지원하지 않는 전압·펄스 폭·모드 조합."""


class OutOfCalibratedStateError(ValueError):
    """현재 I_D가 해당 동작의 보정(calibration) 범위 밖이라 외삽이 필요한 경우."""


class UncalibratedFeatureError(RuntimeError):
    """데이터로 정량 보정되지 않은 기능을 명시적 허용 없이 쓰려는 경우."""


_ABS_TOL_V = 1e-6
_REL_TOL_S = 1e-6

# Reservoir: Fig.3f/3h/3i/3j 조건 (본문 Fig.3 캡션)
RESERVOIR_BG_DOMAIN = {
    "voltage_V": [4.0],
    "width_s": [100e-6],
    "tg_voltage_V_range": [0.0, 5.0],
}

# LIF 흥분: Fig.4b / Supp. Fig.18, 19 조건 (V_base = 0 V, V_high = 2.5 V, TG 기본 -3 V)
LIF_BG_DOMAIN = {
    "voltage_V": [2.5],
    "width_s": [500e-6],
    "tg_voltage_V": [-3.0],
}

# LIF 억제: Fig.4g 조건 (V_inh = 5.0 V, t_width,inh = 100 us)
LIF_TG_INHIBITION_DOMAIN = {
    "voltage_V": [5.0],
    "width_s": [100e-6],
}

MODES = ("reservoir", "lif")


def _in_list(value, allowed, kind):
    for a in allowed:
        if kind == "V" and abs(value - a) <= _ABS_TOL_V:
            return True
        if kind == "s" and math.isclose(value, a, rel_tol=_REL_TOL_S, abs_tol=0.0):
            return True
    return False


def check_bg_pulse(mode: str, voltage_V: float, width_s: float, tg_voltage_V: float) -> None:
    if mode == "reservoir":
        d = RESERVOIR_BG_DOMAIN
        lo, hi = d["tg_voltage_V_range"]
        ok = (_in_list(voltage_V, d["voltage_V"], "V") and _in_list(width_s, d["width_s"], "s")
              and lo - _ABS_TOL_V <= tg_voltage_V <= hi + _ABS_TOL_V)
        if not ok:
            raise UnsupportedOperatingPointError(
                f"Reservoir BG pulse ({voltage_V} V, {width_s * 1e6:.3g} us, TG {tg_voltage_V} V) is unsupported in "
                f"MPBTFT v1. Supported: 4.0 V, 100 us, TG bias 0..5 V.")
    elif mode == "lif":
        d = LIF_BG_DOMAIN
        ok = (_in_list(voltage_V, d["voltage_V"], "V") and _in_list(width_s, d["width_s"], "s")
              and _in_list(tg_voltage_V, d["tg_voltage_V"], "V"))
        if not ok:
            raise UnsupportedOperatingPointError(
                f"LIF BG excitation ({voltage_V} V, {width_s * 1e6:.3g} us, TG {tg_voltage_V} V) is unsupported in "
                f"MPBTFT v1. Supported: 2.5 V, 500 us, TG baseline -3.0 V.")
    else:
        raise UnsupportedOperatingPointError(f"Unknown mode '{mode}'. Use one of {MODES}.")


def check_tg_inhibition(mode: str, voltage_V: float, width_s: float) -> None:
    if mode != "lif":
        raise UnsupportedOperatingPointError(
            "TG inhibitory pulses are only defined for LIF mode. In reservoir mode TG is a bias "
            "applied together with a BG pulse (apply_bg_pulse(..., tg_voltage_V=...)).")
    d = LIF_TG_INHIBITION_DOMAIN
    if not (_in_list(voltage_V, d["voltage_V"], "V") and _in_list(width_s, d["width_s"], "s")):
        raise UnsupportedOperatingPointError(
            f"TG inhibition ({voltage_V} V, {width_s * 1e6:.3g} us) is unsupported in MPBTFT v1. "
            f"Supported: 5.0 V, 100 us.")
