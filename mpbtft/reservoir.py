"""
Physical reservoir 도우미: 비트열을 MPBTFT 펄스열로 넣고 timeframe마다 I_D를 읽는다.

소자 동작은 전부 MPBTFT의 상태 전이로 계산한다 (그림 결과를 표로 저장하지 않는다).
"""
from __future__ import annotations

from model import MPBTFT
from parameters import MPBTFTParams

BG_VOLTAGE_V = 4.0
BG_WIDTH_S = 100e-6
INTERVAL_S = 3e-3          # Fig.3h–j timeframe 간격 (펄스 시작 → 다음 펄스 시작으로 해석)
READ_DELAY_S = 200e-6      # 펄스 끝 → 읽기. Fig.3f 첫 샘플 시점(0.2 ms)을 따른 가정

FIG3I_TG_V = [5.0, 3.0, 1.5, 0.0]          # 본문 Fig.3i 상단 TG 펄스 그림
FIG3J_TG_V = [1.0, 5.0, 3.0, 2.0, 0.0]     # 본문 Fig.3j 상단 TG 펄스 그림


def run_bit_train(device: MPBTFT, bits: str, t0_s: float = 0.0, interval_s: float = INTERVAL_S,
                  tg_voltages_V=None, read_delay_s: float = READ_DELAY_S):
    """bits[k] == '1'이면 timeframe k 시작에 4.0 V / 100 us 펄스.

    timeframe k의 TG 전압은 tg_voltages_V[k] (없으면 0 V).
    반환: timeframe마다 (시작 + 100 us + read_delay) 시각에 읽은 I_D 리스트 (A).
    """
    out = []
    for k, b in enumerate(bits):
        t = t0_s + k * interval_s
        vtg = 0.0 if tg_voltages_V is None else float(tg_voltages_V[k])
        if b == "1":
            device.apply_bg_pulse(t, BG_VOLTAGE_V, BG_WIDTH_S, tg_voltage_V=vtg)
        elif b != "0":
            raise ValueError(f"bits must contain only '0' and '1', got {bits!r}")
        out.append(device.read_current(t + BG_WIDTH_S + read_delay_s))
    return out


class Reservoir:
    """MPBTFT N개. 각 소자에 비트열 하나씩 넣고, 마지막 timeframe의 I_D를 특징값으로 쓴다."""

    def __init__(self, n: int, params: MPBTFTParams | None = None, tg_voltages_V=None,
                 interval_s: float = INTERVAL_S, strict: bool = True):
        params = params if params is not None else MPBTFTParams.load()
        self.devices = [MPBTFT(params, mode="reservoir", strict=strict) for _ in range(n)]
        self.tg_voltages_V = tg_voltages_V
        self.interval_s = interval_s

    def encode(self, chunks):
        feats = []
        for dev, bits in zip(self.devices, chunks):
            dev.initialize(0.0)
            feats.append(run_bit_train(dev, bits, 0.0, self.interval_s, self.tg_voltages_V)[-1])
        return feats
