"""
MPBTFT 기반 LIF 뉴런 wrapper.

MPBTFT core는 I_D까지만 계산한다. 증폭기, 문턱값 비교, 발화(spike)는 여기서 한다.

논문 Fig.4a 회로: 소자 전류를 증폭기(R = 500 kΩ)로 전압(node A)으로 바꾸고,
comparator가 문턱 전압과 비교한다. 비교 대상은 흥분 펄스가 들어와 있는 동안의 전류다
(Fig.4b에서 I_th와 비교되는 곡선이 펄스 중 전류의 윗선).
"""
from __future__ import annotations

from model import MPBTFT

EXC_VOLTAGE_V = 2.5
EXC_WIDTH_S = 500e-6
EXC_DELAY_S = 10e-6          # Fig.4b t_delay,exc
TG_BASE_V = -3.0
INH_VOLTAGE_V = 5.0
INH_WIDTH_S = 100e-6
INH_DELAY_S = 10e-6          # Fig.4g t_delay,inh

AMP_GAIN_OHM = 500e3         # Fig.4a R = 500 kΩ
FIG4B_ITH_A = 5.83e-6        # Fig.4b 빨간 점선 I_th (그림에서 읽은 값, ±0.05 uA)


class LIFNeuron:
    """threshold_A: 펄스 중 전류의 발화 문턱. 기본값은 Fig.4b의 I_th.
    v_threshold_V를 주면 이상적 증폭기 기준으로 threshold_A = v_threshold_V / amp_gain_ohm.
    (본문 Fig.4h의 3.0 V를 쓰면 6.0 uA가 되는데, Fig.4b I_th와 다르므로 기본값으로 쓰지 않는다.)
    """

    def __init__(self, device: MPBTFT, threshold_A: float | None = None,
                 amp_gain_ohm: float = AMP_GAIN_OHM, v_threshold_V: float | None = None):
        if device.mode != "lif":
            raise ValueError("LIFNeuron needs an MPBTFT created with mode='lif'.")
        self.device = device
        self.amp_gain_ohm = amp_gain_ohm
        if threshold_A is not None:
            self.threshold_A = threshold_A
        elif v_threshold_V is not None:
            self.threshold_A = v_threshold_V / amp_gain_ohm
        else:
            self.threshold_A = FIG4B_ITH_A
        self.spikes_s: list[float] = []

    def node_voltage(self, current_A: float) -> float:
        """증폭기 출력 (node A) — 이상적 transimpedance 증폭기로 둔다."""
        return current_A * self.amp_gain_ohm

    def excite(self, time_s: float) -> bool:
        """흥분 펄스 1개. 펄스 중 전류가 문턱을 넘으면 발화(True)하고 spike 시각을 기록한다."""
        self.device.apply_bg_pulse(time_s, EXC_VOLTAGE_V, EXC_WIDTH_S, tg_voltage_V=TG_BASE_V)
        i_on = self.device.last_event.id_during_pulse_A
        fired = i_on >= self.threshold_A
        if fired:
            self.spikes_s.append(time_s + EXC_WIDTH_S)
        return fired

    def inhibit(self, time_s: float) -> float:
        """억제 펄스 1개 (experimental). 반환: 펄스 직후 휴지 상태 I_D (A)."""
        return self.device.apply_tg_inhibition(time_s, INH_VOLTAGE_V, INH_WIDTH_S)

    def excite_train(self, t0_s: float, n: int, delay_s: float = EXC_DELAY_S):
        """n개 흥분 펄스 (주기 = 500 us + delay). 반환: (펄스별 펄스 중 전류 리스트, 마지막 펄스 끝 시각)."""
        on = []
        t = t0_s
        for _ in range(n):
            self.excite(t)
            on.append(self.device.last_event.id_during_pulse_A)
            t += EXC_WIDTH_S + delay_s
        return on, t - delay_s

    def inhibit_train(self, t0_s: float, n: int, delay_s: float = INH_DELAY_S) -> float:
        """n개 억제 펄스. 반환: 마지막 펄스 끝 시각."""
        t = t0_s
        for _ in range(n):
            self.inhibit(t)
            t += INH_WIDTH_S + delay_s
        return t - delay_s
