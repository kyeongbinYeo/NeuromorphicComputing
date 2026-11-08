"""
MPBTFT 휘발성(volatile) 소자 모델 — 논문 Source data(Fig.3f, 3h, 3i)에 맞춰 피팅.

소자가 하는 일 (직관):
  - 펄스를 주면 전류 ID가 올라간다 (분극이 일부 정렬됨).
  - 이미 많이 올라가 있으면 덜 올라간다 (포화).
  - 펄스가 없으면 시간이 지나며 원래 전류로 돌아간다 (휘발 = 잊어버림).
    잊는 속도는 두 가지: 빨리 잊는 부분(τ_fast ≈ 1 ms 이하) + 천천히 잊는 부분(τ_slow ≈ 10 ms대).
    논문 보충자료 식 (1): ID = I0 + A1·e^(−t/t1) + A2·e^(−t/t2)

TG(top gate):
  - TG는 기억을 만들지 않고, BG 펄스가 얼마나 먹히는지만 줄인다 (tg_table, 3h/3i/3j 직접 측정).
  - 감쇠 속도는 TG와 무관 (V_TG 0~5 V에서 동일).

구현 핵심:
  "지난 시간만큼 감쇠"를 매 step마다 계산하지 않고, 읽거나 펄스를 줄 때
  마지막 사건 이후 경과 시간 Δt로 한 번에 e^(−Δt/τ)를 곱한다 (해석해).
  → 시뮬레이션 시계(sim time)든 실제 벽시계(time.perf_counter)든 같은 코드로 동작.
"""
from __future__ import annotations
import json, math, time
from dataclasses import dataclass, asdict, field
from pathlib import Path


@dataclass
class MPBTFTParams:
    I0: float = 1.0e-6        # 완전히 잊었을 때 전류 (A)
    tau_fast: float = 7.6e-4  # 빠른 감쇠 시간상수 (s)
    tau_slow: float = 1.76e-2 # 느린 감쇠 시간상수 (s)
    w_fast: float = 0.1       # 펄스로 생긴 전류 증가분 중 '빠르게 잊는' 몫
    k: float = 0.3            # 펄스 1개가 (Isat − ID) 중 얼마를 채우는지 (4.0 V, 100 μs 기준)
    Isat: float = 4.0e-6      # 포화 전류 (A)
    beta: float = 0.0         # 전류가 클수록 더 빨리 잊는 정도 (보충자료: "ID decays more rapidly as its magnitude increases")
                              # 감쇠 속도 배율 = 1 + beta × (ID − I0)/1μA
    t_read: float = 2.0e-4    # 펄스 후 읽기까지 지연 (s) — Fig.3f 첫 샘플이 0.2 ms
    # VPGM별 펄스 세기 배율 (4.0 V = 1). Fig.3f의 3.5/4.0/4.5 V 곡선 진폭비로 추정
    vpgm_gain: dict = field(default_factory=lambda: {3.5: 0.26, 4.0: 1.0, 4.5: 2.6})
    # V_TG별 펄스 효과 배율 (0 V = 1). Fig.3h/3i/3j에서 '펄스 있음 − 없음' 점프를 직접 잰 값 (3 ms 간격 기준)
    # TG는 감쇠 속도를 바꾸지 않음 (V_TG 0~5 V에서 3 ms 뒤 남는 비율 0.80~0.84로 동일)
    tg_table: dict = field(default_factory=lambda: {0.0: 1.00, 1.0: 0.75, 1.5: 0.77, 2.0: 0.72, 3.0: 0.59, 5.0: 0.51})

    @staticmethod
    def _interp(table: dict, x: float) -> float:
        pts = sorted(table.items())
        if x <= pts[0][0]: return pts[0][1]
        if x >= pts[-1][0]: return pts[-1][1]
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if x0 <= x <= x1:
                return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    def tg_gain_for(self, vtg: float) -> float:
        """V_TG → 펄스 효과 배율. 0~5 V 밖은 끝값 고정(측정 범위 밖)."""
        return self._interp(self.tg_table, vtg)

    def gain_for(self, vpgm: float) -> float:
        pts = sorted(self.vpgm_gain.items())
        if vpgm <= pts[0][0]: return pts[0][1]
        if vpgm >= pts[-1][0]: return pts[-1][1]
        for (v0, g0), (v1, g1) in zip(pts, pts[1:]):
            if v0 <= vpgm <= v1:
                return g0 + (g1 - g0) * (vpgm - v0) / (v1 - v0)

    def save(self, path):
        Path(path).write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path):
        d = json.loads(Path(path).read_text())
        d["vpgm_gain"] = {float(k): v for k, v in d["vpgm_gain"].items()}
        if "tg_table" in d:
            d["tg_table"] = {float(k): v for k, v in d["tg_table"].items()}
        return cls(**d)


class MPBTFT:
    """소자 1개. 상태 = 빠른 성분 f, 느린 성분 s (I0 위로 얹힌 전류, A)."""

    def __init__(self, p: MPBTFTParams | None = None, clock=None, time_scale: float = 1.0):
        """
        clock: None이면 시뮬레이션 시계(advance()로 직접 진행).
               time.perf_counter 같은 함수를 주면 실제 경과 시간으로 감쇠.
        time_scale: 실시간 모드에서 '실제 1초 = 소자 시간 몇 초'.
               소자는 ms 단위로 잊으니, 사람이 보려면 0.001(= 1000배 느리게)이 적당.
        """
        self.p = p or MPBTFTParams()
        self.clock = clock
        self.time_scale = time_scale
        self.f = 0.0
        self.s = 0.0
        self.t = 0.0                                   # 소자 시간 (s)
        self.rate_scale = 1.0                          # 감쇠 속도 배율 (TG가 감쇠를 바꾸는 효과용, 1 = 그대로)
        self._last_wall = clock() if clock else None

    # --- 시간 ---------------------------------------------------------------
    def _sync(self):
        """실시간 모드: 벽시계 경과분을 소자 시간으로 반영."""
        if self.clock is not None:
            now = self.clock()
            self._decay((now - self._last_wall) * self.time_scale)
            self._last_wall = now

    def _decay(self, dt: float):
        if dt <= 0: return
        self.t += dt
        p = self.p
        r = self.rate_scale
        if p.beta == 0:                       # 상태 무관 → 한 번에 정확히 계산
            self.f *= math.exp(-dt * r / p.tau_fast)
            self.s *= math.exp(-dt * r / p.tau_slow)
            return
        left = dt                             # 상태 의존 → 짧은 구간으로 나눠 계산
        while left > 0:
            ex = self.f + self.s
            if ex < 1e-13:                    # 사실상 다 잊음 → 계산 생략
                self.f = self.s = 0.0; return
            m = (1 + p.beta * ex * 1e6) * r
            h = min(left, 0.2 * p.tau_fast / m)
            self.f *= math.exp(-h * m / p.tau_fast)
            self.s *= math.exp(-h * m / p.tau_slow)
            left -= h

    def advance(self, dt: float):
        """시뮬레이션 모드에서 dt초 흘려보내기."""
        if self.clock is not None:
            raise RuntimeError("실시간 모드에서는 advance() 대신 실제로 기다리면 됨")
        self._decay(dt)

    # --- 입력/출력 -----------------------------------------------------------
    def pulse(self, vpgm: float = 4.0, tg_gain: float | None = None, vtg: float | None = None):
        """BG에 PGM 펄스 1개 (폭 100 μs 고정 전제).
        vtg: 그때의 TG 전압 (V) → tg_table로 배율 계산.  tg_gain: 배율을 직접 지정(vtg보다 우선).
        둘 다 없으면 TG = 0 V (배율 1)."""
        self._sync()
        if tg_gain is None:
            tg_gain = self.p.tg_gain_for(vtg) if vtg is not None else 1.0
        ID = self.p.I0 + self.f + self.s
        d = self.p.k * self.p.gain_for(vpgm) * tg_gain * max(self.p.Isat - ID, 0.0)
        self.f += self.p.w_fast * d
        self.s += (1 - self.p.w_fast) * d

    def read(self) -> float:
        self._sync()
        return self.p.I0 + self.f + self.s

    def reset(self):
        self.f = self.s = 0.0

    # --- 편의: 논문 방식 펄스열 ----------------------------------------------
    def run_train(self, bits, interval=3e-3, vpgm=4.0, tg_gains=None, vtgs=None):
        """bits 예: '1011'. 각 timeframe: (1이면 펄스) → t_read 후 읽기 → 다음 timeframe까지 대기.
        vtgs: timeframe별 TG 전압 (예: Fig.3i [5.0, 3.0, 1.5, 0.0], Fig.3j [1.0, 5.0, 3.0, 2.0, 0.0])
        tg_gains: timeframe별 배율 직접 지정 (vtgs보다 우선)
        반환: timeframe별 ID 리스트 (Fig.3h의 pulse number 1..N 값에 대응)."""
        out = []
        for i, b in enumerate(bits):
            if b in "1":
                if tg_gains: self.pulse(vpgm, tg_gain=tg_gains[i])
                elif vtgs:   self.pulse(vpgm, vtg=vtgs[i])
                else:        self.pulse(vpgm)
            self.advance(self.p.t_read)
            out.append(self.read())
            self.advance(interval - self.p.t_read)
        return out


class Reservoir:
    """MPBTFT N개 = 물리적 reservoir. 각 소자에 입력의 한 조각(비트열)을 넣고 마지막 ID를 특징으로."""

    def __init__(self, n, p=None, interval=3e-3, tg_gains=None, vtgs=None):
        self.devs = [MPBTFT(p) for _ in range(n)]
        self.interval, self.tg_gains, self.vtgs = interval, tg_gains, vtgs

    def encode(self, chunks):
        feats = []
        for d, bits in zip(self.devs, chunks):
            d.reset()
            d.advance(1.0)  # 충분히 기다려 초기화 (τ_slow의 50배 이상)
            feats.append(d.run_train(bits, self.interval, tg_gains=self.tg_gains, vtgs=self.vtgs)[-1])
        return feats
