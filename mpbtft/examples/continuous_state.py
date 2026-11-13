"""
펄스 사이의 실제 전류 궤적과, 3 ms 격자 밖 아무 시각·TG 전압에서 펄스를 줘도 계산되는지 보여주는 그림.
LIF 모드의 흥분 → leak → 발화 궤적도 함께 그린다.

    python examples/continuous_state.py   → examples/continuous_state.png
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "fitting"))

from common import load_states  # noqa: E402
from lif import EXC_DELAY_S, EXC_WIDTH_S, LIFNeuron  # noqa: E402
from model import MPBTFT  # noqa: E402
from parameters import MPBTFTParams  # noqa: E402
from reservoir import BG_WIDTH_S, READ_DELAY_S  # noqa: E402

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

p = MPBTFTParams.load()


def reservoir_traj(events, t_stop=13e-3, dt=20e-6):
    """events: [(시작 시각 s, V_TG)] — 4.0 V / 100 us 펄스. 펄스 밖 시각만 읽는다."""
    d = MPBTFT(p, mode="reservoir")
    ts, ys = [], []
    ev = sorted(events)
    t = 0.0
    while t < t_stop:
        if ev and ev[0][0] <= t + 1e-12:
            t0, vtg = ev.pop(0)
            d.apply_bg_pulse(t0, 4.0, BG_WIDTH_S, vtg)
            t = t0 + BG_WIDTH_S
        ts.append(t)
        ys.append(d.read_current(t))
        t += dt
    return np.array(ts) * 1e3, np.array(ys) * 1e6


fig, ax = plt.subplots(1, 3, figsize=(17, 4.3))
seqs, h = load_states("fig3h")
b = "1101"
t, y = reservoir_traj([(k * 3e-3, 0.0) for k in range(4) if b[k] == "1"])
ax[0].plot(t, y, "b-", lw=1.5, label="model: continuous I_D(t)")
xs = [(k * 3e-3 + BG_WIDTH_S + READ_DELAY_S) * 1e3 for k in range(4)]
ax[0].plot(xs, h[seqs.index(b)][1:] * 1e6, "ko", ms=7, label="Fig.3h data (read 0.2 ms after pulse)")
ax[0].set(title="reservoir: input '1101' (3 ms grid)", xlabel="time (ms)", ylabel="I_D (uA)")
ax[0].legend(fontsize=8)

for evs, lab, c in (([(0.0, 0.0), (1.1e-3, 0.0), (5.7e-3, 0.0)], "TG 0 V @ 0, 1.1, 5.7 ms", "tab:green"),
                    ([(0.0, 1.0), (2.0e-3, 5.0), (7.3e-3, 2.5)], "TG 1.0 / 5.0 / 2.5 V @ 0, 2.0, 7.3 ms", "tab:red")):
    t, y = reservoir_traj(evs)
    ax[1].plot(t, y, c=c, lw=1.5, label=lab)
    for te, _ in evs:
        ax[1].axvline(te * 1e3, c=c, ls=":", lw=0.8)
ax[1].set(title="reservoir: pulses at any time / any TG bias (0–5 V)", xlabel="time (ms)", ylabel="I_D (uA)")
ax[1].legend(fontsize=8)

d = MPBTFT(p, mode="lif")
n = LIFNeuron(d)
t_on, i_on, t_rest, i_rest = [], [], [], []
t = 0.0
for k in range(30):
    n.excite(t)
    t_on.append((t + EXC_WIDTH_S) * 1e3)
    i_on.append(d.last_event.id_during_pulse_A * 1e6)
    t += EXC_WIDTH_S + EXC_DELAY_S
for tt in np.linspace(t - EXC_DELAY_S, t + 3e-3, 200):
    t_rest.append(tt * 1e3)
    i_rest.append(d.read_current(tt) * 1e6)
ax[2].plot(t_on, i_on, "o-", ms=3, label="current during excitation pulse")
ax[2].plot(t_rest, i_rest, "-", label="rest current after the train (leak / self-reset)")
ax[2].axhline(n.threshold_A * 1e6, ls="--", c="r", lw=0.8, label=f"I_th {n.threshold_A * 1e6:.2f} uA")
for s in n.spikes_s:
    ax[2].axvline(s * 1e3, c="r", lw=0.5, alpha=0.5)
ax[2].set(title=f"LIF: 30 excitatory pulses, spikes = {len(n.spikes_s)}", xlabel="time (ms)", ylabel="I_D (uA)")
ax[2].legend(fontsize=8)
plt.tight_layout()
plt.savefig(HERE / "continuous_state.png", dpi=120)
print("saved examples/continuous_state.png")
