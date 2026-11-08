"""
논문 Source data에서 MPBTFT 모델 파라미터를 피팅하고, 그림별 오차를 출력/저장.

  python fit_from_paper.py source_data.xlsx
  → params.json, fit_report.json, fit_fig3.png
"""
import sys, json
import numpy as np, openpyxl
from scipy.optimize import least_squares
from mpbtft import MPBTFT, MPBTFTParams

XLSX = sys.argv[1] if len(sys.argv) > 1 else "source_data.xlsx"
rows = list(openpyxl.load_workbook(XLSX, data_only=True, read_only=True)["Fig.3"].iter_rows(values_only=True))
num = lambda x: isinstance(x, (int, float))

def column(c, r0=2):
    return np.array([r[c] for r in rows[r0:] if c < len(r) and num(r[c])], float)

# Fig.3f: 단일 PGM 펄스 후 감쇠 (VPGM = 3, 4, 5 V)
t3f = column(22)[::25]
dec = {v: column(c)[::25] for v, c in zip((3.5, 4.0, 4.5), (23, 24, 25))}

# Fig.3h / 3i: 16가지 4-bit 입력 (열 순서 = 0000, 0001, ..., 1111; 첫 비트가 첫 timeframe)
def block(r_start, n_rows):
    return np.array([[rows[r][c] for c in range(36, 52)] for r in range(r_start, r_start + n_rows)], float).T
fig3h = block(2, 5)   # (16 입력, pulse number 0..4)
fig3i = block(10, 5)
BITS = [format(i, "04b") for i in range(16)]
INTERVAL = 3e-3

def sim_train(p, bits, tg=None):
    d = MPBTFT(p)
    return [d.read()] + d.run_train(bits, INTERVAL, tg_gains=tg)

def sim_decay(p, vpgm, t, I0_dev, start_excess):
    """Fig.3f는 별도 측정(초기 전류가 다름) → 감쇠 '모양'(τ, w)만 공유하고 기준/진폭은 곡선별."""
    d = MPBTFT(p); d.f, d.s = p.w_fast * start_excess, (1 - p.w_fast) * start_excess
    out, prev = [], t[0]
    for ti in t:
        d.advance(ti - prev); prev = ti
        out.append(d.f + d.s)
    return I0_dev + np.array(out)

def unpack(x):
    I0, lt1, lt2, w, k, Isat, beta = x[:7]
    p = MPBTFTParams(I0=I0 * 1e-6, tau_fast=10**lt1, tau_slow=10**lt2, w_fast=w, k=k, Isat=Isat * 1e-6, beta=beta)
    return p, x[7:]

def residuals(x):
    p, extra = unpack(x)
    r = []
    for i, b in enumerate(BITS):          # Fig.3h 80점
        r.extend((np.array(sim_train(p, b)) - fig3h[i]) * 1e6)
    for j, v in enumerate((3.5, 4.0, 4.5)):  # Fig.3f 감쇠 곡선 (점이 많으니 가중치 낮춤)
        I0d, A = extra[2 * j: 2 * j + 2]
        y = dec[v][: len(t3f)]
        pred = sim_decay(p, v, t3f[: len(y)], I0d * 1e-6, A * 1e-6)
        r.extend(((pred - y) * 1e6) * 0.5)
    return np.array(r)

x0 = [1.0, -3.2, -1.8, 0.2, 0.3, 4.0, 0.3] + [0.8, 0.4, 0.8, 1.3, 0.9, 2.8]
lb = [0.5, -5, -3, 0, 0.01, 1.5, 0] + [0, 0, 0, 0, 0, 0]
ub = [1.5, -1.5, 0, 1, 1, 20, 5] + [3, 5, 3, 5, 3, 8]
sol = least_squares(residuals, x0, bounds=(lb, ub))
p, extra = unpack(sol.x)

# VPGM 배율: 같은 감쇠 모양에서 Fig.3f 곡선별 '펄스 직후 증가분' 비율 (4 V = 1)
amp = {v: extra[2 * j + 1] for j, v in enumerate((3.5, 4.0, 4.5))}
p.vpgm_gain = {v: float(amp[v] / amp[4.0]) for v in amp}
p.save("params.json")

# --- 검증 1: Fig.3h 재현 ---
pred3h = np.array([sim_train(p, b) for b in BITS])
err3h = (pred3h - fig3h) * 1e6

# --- 검증 2: Fig.3i (TG 사용) — 소자 파라미터는 고정, timeframe별 TG 배율 4개만 피팅 ---
def r_tg(g):
    return np.concatenate([(np.array(sim_train(p, b, list(g))) - fig3i[i]) * 1e6 for i, b in enumerate(BITS)])
tg = least_squares(r_tg, [1, 1, 1, 1], bounds=(0, 3)).x
pred3i = np.array([sim_train(p, b, list(tg)) for b in BITS])
err3i = (pred3i - fig3i) * 1e6

# --- 검증 3: 마지막 상태로 16개 입력이 구분되는가 (reservoir로서 핵심) ---
def separability(final):
    s = np.sort(final); return float(np.min(np.diff(s)) * 1e6)

report = {
    "params": {"I0_uA": p.I0 * 1e6, "tau_fast_ms": p.tau_fast * 1e3, "tau_slow_ms": p.tau_slow * 1e3,
               "w_fast": p.w_fast, "k": p.k, "Isat_uA": p.Isat * 1e6, "beta": p.beta, "vpgm_gain": p.vpgm_gain},
    "fig3h_rmse_uA": float(np.sqrt((err3h ** 2).mean())),
    "fig3h_max_abs_err_uA": float(np.abs(err3h).max()),
    "fig3h_final_state_rmse_uA": float(np.sqrt((err3h[:, -1] ** 2).mean())),
    "fig3i_tg_gains": tg.tolist(),
    "fig3i_rmse_uA": float(np.sqrt((err3i ** 2).mean())),
    "fig3h_rank_order_match": bool((np.argsort(pred3h[:, -1]) == np.argsort(fig3h[:, -1])).all()),
    "fig3h_spearman": float(np.corrcoef(np.argsort(np.argsort(pred3h[:, -1])), np.argsort(np.argsort(fig3h[:, -1])))[0, 1]),
    "min_gap_final_uA": {"data_3h": separability(fig3h[:, -1]), "model_3h": separability(pred3h[:, -1]),
                         "data_3i": separability(fig3i[:, -1]), "model_3i": separability(pred3i[:, -1])},
}
json.dump(report, open("fit_report.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(report, indent=2, ensure_ascii=False))

# --- 그림 ---
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 3, figsize=(15, 4.3))
for j, v in enumerate((3.5, 4.0, 4.5)):
    y = dec[v]; tt = t3f[: len(y)]
    ax[0].plot(tt * 1e3, y * 1e6, ".", ms=2, alpha=.35, label=f"data {v:.1f} V")
    ax[0].plot(tt * 1e3, sim_decay(p, v, tt, extra[2*j]*1e-6, extra[2*j+1]*1e-6) * 1e6, "k-", lw=1)
ax[0].set(title="Fig.3f decay (dots=data, line=model)", xlabel="time (ms)", ylabel="ID (μA)"); ax[0].legend(fontsize=8)
for a, data, pred, name in ((ax[1], fig3h, pred3h, "Fig.3h (no TG)"), (ax[2], fig3i, pred3i, "Fig.3i (TG)")):
    for i in range(16):
        c = plt.cm.viridis(i / 15)
        a.plot(range(5), data[i] * 1e6, "o", color=c, ms=4)
        a.plot(range(5), pred[i] * 1e6, "-", color=c, lw=1)
    a.set(title=f"{name}: dots=data, line=model", xlabel="pulse number", ylabel="ID (μA)")
plt.tight_layout(); plt.savefig("fit_fig3.png", dpi=130)
