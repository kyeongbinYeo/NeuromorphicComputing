"""
점과 점 사이의 실제 전류 궤적, 그리고 아무 시각·아무 전압에서 펄스를 줘도 계산되는지 보여주는 그림.
  python continuous_state.py source_data.xlsx  → continuous_state.png
"""
import sys
import numpy as np, openpyxl, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from mpbtft import MPBTFT, MPBTFTParams

XLSX = sys.argv[1] if len(sys.argv) > 1 else "source_data.xlsx"
p = MPBTFTParams.load("params.json")
r = list(openpyxl.load_workbook(XLSX, data_only=True, read_only=True)["Fig.3"].iter_rows(values_only=True))
h = np.array([[r[i][c] for c in range(36, 52)] for i in range(2, 7)], float).T * 1e6

def traj(events, T=13e-3, dt=2e-5):
    """events: [(시각 s, V_PGM, V_TG)] — 아무 시각에나 펄스. 연속 궤적 반환"""
    d = MPBTFT(p); ts = [0]; ys = [d.read() * 1e6]; t = 0; ev = sorted(events)
    while t < T:
        if ev and ev[0][0] <= t + 1e-12:
            _, v, tg = ev.pop(0); d.pulse(v, vtg=tg); ts.append(t); ys.append(d.read() * 1e6)
        d.advance(dt); t += dt; ts.append(t); ys.append(d.read() * 1e6)
    return np.array(ts) * 1e3, np.array(ys)

fig, ax = plt.subplots(1, 2, figsize=(13, 4.3))
b = "1101"
t, y = traj([(k * 3e-3, 4.0, 0.0) for k in range(4) if b[k] == "1"])
ax[0].plot(t, y, "b-", lw=1.5, label="model: continuous ID(t)")
xs = [k * 3 + 0.2 for k in range(4)]
ax[0].plot(xs, h[int(b, 2)][1:], "ko", ms=7, label="Fig.3h data (read 0.2 ms after pulse)")
ax[0].plot(xs, h[int(b, 2)][1:], "k--", lw=.8, alpha=.5, label="paper's connecting line (just drawn)")
ax[0].set(title="input '1101' (3 ms grid)", xlabel="time (ms)", ylabel="ID (μA)"); ax[0].legend(fontsize=8)
for evs, lab, c in (([(0, 4.0, 0), (1.1e-3, 4.0, 0), (5.7e-3, 4.0, 0)], "4.0 V @ 0, 1.1, 5.7 ms", "tab:green"),
                    ([(0, 4.0, 1.0), (2.0e-3, 4.0, 5.0), (7.3e-3, 4.0, 2.5)], "4.0 V, V_TG 1.0 / 5.0 / 2.5 V @ 0, 2.0, 7.3 ms", "tab:red")):
    t, y = traj(evs); ax[1].plot(t, y, c=c, lw=1.5, label=lab)
    for te, *_ in evs: ax[1].axvline(te * 1e3, c=c, ls=":", lw=.8)
ax[1].set(title="off-grid: pulse at any time / any state / any V_TG", xlabel="time (ms)", ylabel="ID (μA)"); ax[1].legend(fontsize=8)
plt.tight_layout(); plt.savefig("continuous_state.png", dpi=120)
print("saved continuous_state.png")
