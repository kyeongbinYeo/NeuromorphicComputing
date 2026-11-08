"""
line_cnn 주행 로그(telemetry.csv)를 MPBTFT에 흘려보내기.

매 프레임: |steer_norm| > 임계값이면 펄스 1개 (= "지금 꺾는 중").
소자 전류 ID = "최근에 얼마나 자주 꺾었나"를 기억하는 값.

두 가지 시간 매핑 비교:
  A) 카메라 실제 간격(프레임당 ~42 ms) 그대로 → τ(≈17 ms)보다 길어서 다음 프레임 전에 거의 다 잊음
  B) 논문 방식처럼 프레임 1개 = timeframe 1개(3 ms)로 압축해서 펄스 구동 → 최근 몇 프레임을 기억

  python telemetry_reservoir.py telemetry.csv
"""
import sys, csv
import numpy as np
from mpbtft import MPBTFT, MPBTFTParams

path = sys.argv[1] if len(sys.argv) > 1 else "telemetry.csv"
rows = list(csv.DictReader(open(path)))
t = np.array([float(r["t"]) for r in rows])
steer = np.array([float(r["steer_norm"] or 0) for r in rows])
bits = np.abs(steer) > 0.3
p = MPBTFTParams.load("params.json")

def run(interval_fn):
    d, out = MPBTFT(p), []
    for i, b in enumerate(bits):
        if b: d.pulse(4.0)
        d.advance(p.t_read); out.append(d.read() * 1e6)
        d.advance(max(interval_fn(i) - p.t_read, 0))
    return np.array(out)

real = run(lambda i: (t[i + 1] - t[i]) if i + 1 < len(t) else 0.04)
comp = run(lambda i: 3e-3)

# "몇 프레임 전까지 기억하나": 펄스 1개의 흔적이 처음 크기의 10% 아래로 떨어지는 프레임 수
def memory_frames(interval):
    d = MPBTFT(p); d.pulse(); d.advance(p.t_read); first = d.read() - p.I0
    for n in range(1, 200):
        d.advance(interval)
        if d.read() - p.I0 < 0.1 * first: return n
print(f"프레임 {len(t)}개, 평균 간격 {np.diff(t).mean()*1e3:.1f} ms, 펄스 {bits.sum()}개")
print(f"A) 실제 간격  : 기억 ≈ {memory_frames(np.diff(t).mean())} 프레임, ID 범위 {real.min():.2f}–{real.max():.2f} μA")
print(f"B) 3 ms 압축 : 기억 ≈ {memory_frames(3e-3)} 프레임, ID 범위 {comp.min():.2f}–{comp.max():.2f} μA")

import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(3, 1, figsize=(11, 6.5), sharex=True)
ax[0].plot(steer, lw=.8); ax[0].axhline(.3, ls="--", c="gray"); ax[0].axhline(-.3, ls="--", c="gray")
ax[0].set_ylabel("steer_norm"); ax[0].set_title("line_cnn steering → pulse when |steer| > 0.3")
ax[1].plot(real, c="tab:red", lw=.8); ax[1].set_ylabel("ID (μA)"); ax[1].set_title("A) real frame timing (~42 ms): forgets between frames")
ax[2].plot(comp, c="tab:green", lw=.8); ax[2].set_ylabel("ID (μA)"); ax[2].set_title("B) 1 frame = 3 ms timeframe (paper scheme): remembers recent turning")
ax[2].set_xlabel("frame")
plt.tight_layout(); plt.savefig("telemetry_reservoir.png", dpi=120)
