"""
MPBTFT v1 behavioral model (volatile Double-Gate MPBTFT).

대상 논문: Analog reservoir computing via ferroelectric mixed phase boundary transistors,
Nat. Commun. 15, 9147 (2024), DOI 10.1038/s41467-024-53321-2

하나의 MPBTFT 클래스를 Reservoir 모드와 LIF 모드에서 함께 쓴다 (인스턴스만 다르게).

    현재 I_D + 경과 시간 + 검증된 gate event  →  다음 I_D

- 출력은 항상 I_D (A). spike, firing, class는 이 클래스가 만들지 않는다 (lif.LIFNeuron 담당).
- 사건 기반(event-driven) / 지연 감쇠(lazy relaxation): 매 timestep을 저장하지 않고,
  마지막으로 확정(commit)한 상태와 그 시각만 기억한다. 읽을 때 경과 시간만큼 해석적으로 감쇠시킨다.
- read_current()는 관측일 뿐이라 상태를 바꾸지 않는다 (같은 시각을 몇 번 읽어도 같은 값).
- 펄스는 시작 시각에 받고, 펄스가 끝나는 시각에 새 상태를 확정한다. 펄스 내부 과도 응답은 다루지 않는다.
- 지원하지 않는 전압·폭·모드, 보정 범위 밖 I_D, 시간 역행, 펄스 겹침은 모두 오류를 낸다.
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass

from domains import (
    MODES,
    OutOfCalibratedStateError,
    UncalibratedFeatureError,
    UnsupportedOperatingPointError,
    check_bg_pulse,
    check_tg_inhibition,
)
from parameters import MPBTFTParams

READ_VDS_V = 0.1          # 모든 측정의 V_DS (본문 Fig.3, Fig.4 캡션). v1에서는 고정 소자 조건
_TIME_TOL_S = 1e-12       # 부동소수점 반올림으로 생기는 가짜 겹침을 막기 위한 허용 오차
_STATE_TOL_A = 1e-12


@dataclass(frozen=True)
class GateEvent:
    kind: str                 # "bg" 또는 "tg_inhibition"
    start_s: float
    end_s: float
    voltage_V: float
    width_s: float
    tg_voltage_V: float | None
    id_pre_A: float
    id_post_A: float
    id_during_pulse_A: float | None   # LIF 흥분 펄스 끝 무렵 흐르는 전류 (V_BG = 2.5 V 상태). 그 외 None


class MPBTFT:
    """Volatile DG MPBTFT 1개.

    mode="reservoir": BG 4.0 V / 100 us 펄스, TG는 펄스와 함께 거는 변조 바이어스 (0~5 V).
                      휴지 상태 읽기 조건: V_BG = 0 V, V_TG = 0 V, V_DS = 0.1 V.
    mode="lif":       BG 2.5 V / 500 us 흥분 펄스, TG 5.0 V / 100 us 억제 펄스, TG 기본 바이어스 -3 V.
                      휴지 상태 읽기 조건: V_BG = 0 V, V_TG = -3 V, V_DS = 0.1 V.
    """

    def __init__(self, params: MPBTFTParams | None = None, mode: str = "reservoir",
                 time_s: float = 0.0, strict: bool = True, allow_experimental: bool = False):
        """strict=True: 보정 범위 밖 I_D에서 오류. False면 경고 후 가장자리 값 사용.
        allow_experimental=True: 데이터로 충분히 뒷받침되지 않는 기능(TG 억제)을 켠다.
        """
        if mode not in MODES:
            raise UnsupportedOperatingPointError(f"Unknown mode '{mode}'. Use one of {MODES}.")
        self.params = params if params is not None else MPBTFTParams.load()
        self.mode = mode
        self.strict = strict
        self.allow_experimental = allow_experimental
        self._p = self.params.mode(mode)
        self.initialize(time_s)

    # ------------------------------------------------------------------ public
    def initialize(self, time_s: float = 0.0) -> None:
        """시뮬레이션/테스트용 초기화: 완전히 이완된 상태(I_D = baseline)로 둔다.

        물리적 self-reset이 아니다. 논문의 self-reset은 휘발성 감쇠로 저절로 일어나며,
        이 모델에서는 시간을 충분히 흘려보내면 같은 결과가 나온다.
        """
        self._fast = 0.0
        self._slow = 0.0
        self._tau_slow = self._p.relaxation.tau_slow_s(0.0)
        self._t_last = float(time_s)
        self._last_event: GateEvent | None = None

    @property
    def baseline_current_A(self) -> float:
        return self._p.baseline_A

    @property
    def last_update_time_s(self) -> float:
        return self._t_last

    @property
    def last_event(self) -> GateEvent | None:
        return self._last_event

    def read_current(self, time_s: float) -> float:
        """time_s 시각의 I_D (A). 상태를 바꾸지 않는다."""
        dt = self._elapsed_for_read(time_s)
        f, s = self._relaxed(dt)
        return self._p.baseline_A + f + s

    def apply_bg_pulse(self, time_s: float, voltage_V: float, width_s: float,
                       tg_voltage_V: float | None = None) -> float:
        """BG 펄스. time_s = 펄스 시작 시각. 반환: 펄스가 끝난 직후의 I_D (A).

        reservoir: tg_voltage_V = 펄스 동안 함께 거는 TG 바이어스 (기본 0 V).
        lif:       tg_voltage_V = TG 기본 바이어스 (-3 V만 지원, 기본 -3 V).
        """
        if tg_voltage_V is None:
            tg_voltage_V = 0.0 if self.mode == "reservoir" else -3.0
        check_bg_pulse(self.mode, voltage_V, width_s, tg_voltage_V)
        self._check_event_start(time_s, "bg")

        f, s = self._relaxed(time_s - self._t_last)
        id_pre = self._p.baseline_A + f + s
        table = self._p.bg_update.delta_id_A
        self._check_state(id_pre, table.lo, table.hi, "BG update")

        gain = 1.0
        if self.mode == "reservoir":
            gain = self._p.tg_modulation(tg_voltage_V)
        delta = table(id_pre) * gain
        w = self._p.relaxation.fast_share
        self._commit(f + w * delta, s + (1.0 - w) * delta, time_s + width_s)

        id_post = self._p.baseline_A + self._fast + self._slow
        during = id_post + self._p.on_state_offset_A if self.mode == "lif" else None
        self._last_event = GateEvent("bg", time_s, time_s + width_s, voltage_V, width_s, tg_voltage_V,
                                     id_pre, id_post, during)
        return id_post

    def apply_tg_inhibition(self, time_s: float, voltage_V: float, width_s: float) -> float:
        """LIF 억제 펄스 (TG: -3 V → V_inh → -3 V). time_s = 펄스 시작. 반환: 펄스 직후 I_D (A).

        상태: experimental. Source data에 억제 직전·직후 I_D가 없어(Fig.4e–g의 해당 구간이 비어 있음)
        감소량을 데이터로 정할 수 없다. 파라미터 파일의 retention은 Fig.4g에서 얻은 best-fit 값이지만
        식별성이 낮아, allow_experimental=True일 때만 쓴다. README "Known limitations" 참고.
        """
        check_tg_inhibition(self.mode, voltage_V, width_s)
        self._check_event_start(time_s, "tg_inhibition")
        inh = self._p.tg_inhibition
        if inh is None:
            raise UnsupportedOperatingPointError("No TG inhibition entry in the parameter file.")
        if not (inh.enabled_by_default or self.allow_experimental):
            raise UncalibratedFeatureError(
                "TG inhibition is experimental in MPBTFT v1: the source data has no I_D right before/after the "
                "inhibitory pulse (Fig.4e-g blank that window), and the retention inferred from the following "
                "excitation train is not identifiable. Create the device with allow_experimental=True to use "
                f"the best-fit retention ({inh.retention:.3f}) anyway. Missing evidence: {inh.note}")

        f, s = self._relaxed(time_s - self._t_last)
        id_pre = self._p.baseline_A + f + s
        lo, hi = inh.id_pre_domain_A
        self._check_state(id_pre, lo, hi, "TG inhibition")

        r = inh.retention
        self._commit(f * r, s * r, time_s + width_s)
        id_post = self._p.baseline_A + self._fast + self._slow
        self._last_event = GateEvent("tg_inhibition", time_s, time_s + width_s, voltage_V, width_s,
                                     voltage_V, id_pre, id_post, None)
        return id_post

    # ----------------------------------------------------------------- private
    def _relaxed(self, dt: float):
        if dt <= 0.0:
            return self._fast, self._slow
        rp = self._p.relaxation
        return (self._fast * math.exp(-dt / rp.tau_fast_s),
                self._slow * math.exp(-dt / self._tau_slow))

    def _commit(self, fast: float, slow: float, t_end: float) -> None:
        self._fast = max(fast, 0.0)
        self._slow = max(slow, 0.0)
        # 느린 감쇠의 시간상수는 확정 시점의 초과 전류로 고르고, 다음 사건까지 유지한다
        self._tau_slow = self._p.relaxation.tau_slow_s(self._fast + self._slow)
        self._t_last = float(t_end)

    def _elapsed_for_read(self, time_s: float) -> float:
        ev = self._last_event
        if ev is not None and ev.start_s + _TIME_TOL_S < time_s < ev.end_s - _TIME_TOL_S:
            raise ValueError(
                f"Cannot read I_D at t = {time_s:.9g} s: a {ev.kind} pulse is in progress "
                f"({ev.start_s:.9g}..{ev.end_s:.9g} s). Intra-pulse dynamics are not modeled in MPBTFT v1.")
        dt = time_s - self._t_last
        if dt < -_TIME_TOL_S:
            raise ValueError(
                f"Time must not go backwards: read at {time_s:.9g} s is before the last committed "
                f"state at {self._t_last:.9g} s.")
        return max(dt, 0.0)

    def _check_event_start(self, time_s: float, kind: str) -> None:
        ev = self._last_event
        if time_s >= self._t_last - _TIME_TOL_S:
            return
        if ev is not None and time_s >= ev.start_s - _TIME_TOL_S:
            if self.mode == "lif" and ev.kind != kind:
                raise ValueError("Overlapping BG excitation and TG inhibition "
                                 "are not supported in MPBTFT v1 LIF mode.")
            raise ValueError("Overlapping gate events are not supported in MPBTFT v1.")
        raise ValueError(
            f"Events must be applied in time order: start {time_s:.9g} s is before the last committed "
            f"state at {self._t_last:.9g} s.")

    def _check_state(self, id_pre: float, lo: float, hi: float, what: str) -> None:
        if lo - _STATE_TOL_A <= id_pre <= hi + _STATE_TOL_A:
            return
        msg = (f"{what}: I_D before the pulse = {id_pre * 1e6:.4f} uA is outside the calibrated range "
               f"{lo * 1e6:.3f}..{hi * 1e6:.3f} uA ({self.mode} mode). MPBTFT v1 does not extrapolate.")
        if self.strict:
            raise OutOfCalibratedStateError(msg)
        warnings.warn(msg + " Using the edge value because strict=False.", RuntimeWarning, stacklevel=3)
