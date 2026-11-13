"""
line_cnn 주행 로그(telemetry.csv)를 reservoir 모드 MPBTFT에 흘려보내기.

매 프레임: |steer_norm| > 0.3 이면 4.0 V / 100 us 펄스 1개.
소자 전류 I_D = 최근에 얼마나 자주 꺾었는지를 기억하는 값.

두 가지 시간 매핑 비교
  A) 카메라 실제 간격(프레임당 약 42 ms) 그대로 → 다음 프레임 전에 거의 다 잊음
  B) 프레임 1개 = timeframe 1개(3 ms, 논문 방식)로 압축 → 최근 몇 프레임을 기억

B는 연속 펄스가 많으면 I_D가 보정 범위(약 2.8 uA) 위로 올라간다. v1은 외삽하지 않으므로
strict=False로 돌려 가장자리 값을 쓰고, 범위를 벗어난 펄스 수를 같이 출력한다.

    python examples/telemetry_reservoir.py [examples/telemetry.csv]
"""
from __future__ import annotations

import csv
import sys
import warnings
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from model import MPBTFT  # noqa: E402
from parameters import MPBTFTParams  # noqa: E402
from reservoir import BG_WIDTH_S, READ_DELAY_S  # noqa: E402

path = sys.argv[1] if len(sys.argv) > 1 else str(HERE / "telemetry.csv")
rows = list(csv.DictReader(open(path, encoding="utf-8")))
t = np.array([float(r["t"]) for r in rows])
steer = np.array([float(r["steer_norm"] or 0) for r in rows])
bits = np.abs(steer) > 0.3
p = MPBTFTParams.load()


def run(frame_times):
    d = MPBTFT(p, mode="reservoir", strict=False)
    out, n_out = [], 0
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always", RuntimeWarning)
        for tf, b in zip(frame_times, bits):
            if b:
                d.apply_bg_pulse(tf, 4.0, BG_WIDTH_S, 0.0)
            out.append(d.read_current(tf + BG_WIDTH_S + READ_DELAY_S) * 1e6)
        n_out = len(w)
    return np.array(out), n_out


def memory_frames(interval):
    """펄스 1개의 흔적이 처음 크기의 10% 아래로 떨어질 때까지 프레임 수."""
    d = MPBTFT(p, mode="reservoir")
    d.apply_bg_pulse(0.0, 4.0, BG_WIDTH_S, 0.0)
    t_read = BG_WIDTH_S + READ_DELAY_S
    first = d.read_current(t_read) - d.baseline_current_A
    for n in range(1, 500):
        if d.read_current(t_read + n * interval) - d.baseline_current_A < 0.1 * first:
            return n
    return None


real, out_a = run(t)
comp, out_b = run(np.arange(len(t)) * 3e-3)
print(f"프레임 {len(t)}개, 평균 간격 {np.diff(t).mean() * 1e3:.1f} ms, 펄스 {bits.sum()}개")
print(f"A) 실제 간격  : 기억 ≈ {memory_frames(np.diff(t).mean())} 프레임, I_D {real.min():.2f}–{real.max():.2f} uA, "
      f"보정 범위 밖 펄스 {out_a}개")
print(f"B) 3 ms 압축 : 기억 ≈ {memory_frames(3e-3)} 프레임, I_D {comp.min():.2f}–{comp.max():.2f} uA, "
      f"보정 범위 밖 펄스 {out_b}개")

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

fig, ax = plt.subplots(3, 1, figsize=(11, 6.5), sharex=True)
ax[0].plot(steer, lw=0.8)
ax[0].axhline(0.3, ls="--", c="gray")
ax[0].axhline(-0.3, ls="--", c="gray")
ax[0].set(ylabel="steer_norm", title="line_cnn steering → pulse when |steer| > 0.3")
ax[1].plot(real, c="tab:red", lw=0.8)
ax[1].set(ylabel="I_D (uA)", title="A) real frame timing (~42 ms): forgets between frames")
ax[2].plot(comp, c="tab:green", lw=0.8)
hi = p.reservoir.bg_update.delta_id_A.hi * 1e6
ax[2].axhline(hi, ls=":", c="k", lw=0.8)
ax[2].set(ylabel="I_D (uA)", xlabel="frame",
          title=f"B) 1 frame = 3 ms (paper scheme); dotted = calibrated I_D limit for a new pulse ({hi:.2f} uA)")
plt.tight_layout()
plt.savefig(HERE / "telemetry_reservoir.png", dpi=120)
print("saved examples/telemetry_reservoir.png")
