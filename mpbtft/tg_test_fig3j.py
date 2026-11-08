"""
TG가 '점프만' 줄이나(모델 A), '감쇠 속도'도 바꾸나(모델 B)를 Fig.3j로 검증.

- 3i(TG: 5.0→3.0→1.5→0 V)로 TG 규칙을 피팅 → 3j(TG: 1.0→5.0→3.0→2.0→0 V)를 '처음 보는 데이터'로 예측
- 3j의 1.0, 2.0 V는 3i에 없는 전압 → 보간이 맞는지도 같이 검증
- 각 timeframe의 TG 전압은 그 timeframe 펄스 시작부터 다음 펄스까지 유지된다고 가정
  python tg_test_fig3j.py source_data.xlsx
"""
import sys, json, math
import numpy as np, openpyxl
from scipy.optimize import least_squares
from mpbtft import MPBTFT, MPBTFTParams

XLSX = sys.argv[1] if len(sys.argv) > 1 else "source_data.xlsx"
r = list(openpyxl.load_workbook(XLSX, data_only=True, read_only=True)["Fig.3"].iter_rows(values_only=True))
F3I = np.array([[r[i][c] for c in range(36, 52)] for i in range(10, 15)], float).T * 1e6   # (16, 5)
F3J = np.array([[r[i][c] for c in range(36, 68)] for i in range(18, 24)], float).T * 1e6   # (32, 6)
TG3I, TG3J = [5.0, 3.0, 1.5, 0.0], [1.0, 5.0, 3.0, 2.0, 0.0]
p = MPBTFTParams.load("params.json")
INTERVAL = 3e-3

def gain(V, a, b):   return max(a + b * V, 0.0)       # 펄스 효과 배율: V_TG에 대해 직선
def rate(V, c):      return math.exp(c * V)            # 감쇠 속도 배율: c=0이면 TG가 감쇠에 영향 없음

def sim(bits, tgs, a, b, c):
    d = MPBTFT(p); out = [d.read() * 1e6]
    for k, bit in enumerate(bits):
        d.rate_scale = rate(tgs[k], c)                 # 이 timeframe 동안의 TG
        if bit == "1": d.pulse(4.0, gain(tgs[k], a, b))
        d.advance(p.t_read); out.append(d.read() * 1e6)
        d.advance(INTERVAL - p.t_read)
    return out

def predict(data, tgs, x):
    n = len(tgs)
    return np.array([sim(format(i, f"0{n}b"), tgs, *x) for i in range(len(data))])

def stats(pred, data):
    e = pred - data; fin = np.sort(pred[:, -1])
    return {"rmse_uA": float(np.sqrt((e ** 2).mean())), "max_err_uA": float(np.abs(e).max()),
            "final_rmse_uA": float(np.sqrt((e[:, -1] ** 2).mean())),
            "rank_corr_final": float(np.corrcoef(np.argsort(np.argsort(pred[:, -1])), np.argsort(np.argsort(data[:, -1])))[0, 1]),
            "min_gap_final_uA": float(np.diff(fin).min())}

def fit(data, tgs, use_c):
    f = lambda x: (predict(data, tgs, (x[0], x[1], x[2] if use_c else 0.0)) - data).ravel()
    x0 = [1.0, -0.1, 0.0] if use_c else [1.0, -0.1]
    lb = [0, -1, -1][: len(x0)]; ub = [2, 1, 1][: len(x0)]
    x = least_squares(f, x0, bounds=(lb, ub)).x
    return (x[0], x[1], x[2] if use_c else 0.0)

R = {"data_min_gap_final_uA": {"3i": float(np.diff(np.sort(F3I[:, -1])).min()), "3j": float(np.diff(np.sort(F3J[:, -1])).min())}}
# 0) 3g 사전값 그대로 (피팅 없음): 0 V 대비 배율 1 − 0.12×V_TG
x3g = (1.0, -0.12, 0.0)
R["3g_prior_zero_shot"] = {"params": x3g, "3i": stats(predict(F3I, TG3I, x3g), F3I), "3j": stats(predict(F3J, TG3J, x3g), F3J)}
for name, use_c in (("A_gain_only", False), ("B_gain_plus_decay", True)):
    x = fit(F3I, TG3I, use_c)
    R[name] = {"params(a,b,c)": x, "fit_on_3i": stats(predict(F3I, TG3I, x), F3I),
               "zero_shot_3j": stats(predict(F3J, TG3J, x), F3J)}
    xj = fit(F3J, TG3J, use_c)
    R[name]["refit_on_3j"] = {"params(a,b,c)": xj, **stats(predict(F3J, TG3J, xj), F3J)}
json.dump(R, open("tg_test_report.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(R, indent=2, ensure_ascii=False))

import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
fig, ax = plt.subplots(1, 2, figsize=(13, 4.5), sharey=True)
for a_, name in zip(ax, ("A_gain_only", "B_gain_plus_decay")):
    pr = predict(F3J, TG3J, R[name]["params(a,b,c)"])
    for i in range(32):
        c = plt.cm.viridis(i / 31)
        a_.plot(range(6), F3J[i], "o", color=c, ms=3.5); a_.plot(range(6), pr[i], "-", color=c, lw=.9)
    s = R[name]["zero_shot_3j"]
    a_.set(title=f"{name}: fit on 3i → predict 3j\nRMSE {s['rmse_uA']:.3f} μA, final {s['final_rmse_uA']:.3f} μA",
           xlabel="pulse number"); 
ax[0].set_ylabel("ID (μA)"); plt.tight_layout(); plt.savefig("tg_test_fig3j.png", dpi=125)

# ---------------------------------------------------------------------------
# 모델 C: 데이터에서 직접 잰 TG 점프 표(보간) + 감쇠 영향 없음
#   (점프 = 같은 시점에서 '펄스 있음 − 펄스 없음', 3h/3i/3j 합쳐서 V_TG별 평균 ÷ 0 V 점프)
#   → 이 표는 mpbtft.py의 MPBTFTParams.tg_table 기본값 (tg_measure.py로 재측정 가능)
TG_TABLE = p.tg_table
def sim_table(bits, tgs):
    d = MPBTFT(p); out = [d.read() * 1e6]
    for k, bit in enumerate(bits):
        if bit == "1": d.pulse(4.0, vtg=tgs[k])
        d.advance(p.t_read); out.append(d.read() * 1e6)
        d.advance(INTERVAL - p.t_read)
    return out
for nm, D, tg in (("3i", F3I, TG3I), ("3j", F3J, TG3J)):
    n = len(tg); pr = np.array([sim_table(format(i, f"0{n}b"), tg) for i in range(len(D))])
    R.setdefault("C_measured_table", {"table": {str(k): v for k, v in TG_TABLE.items()}})[nm] = stats(pr, D)
json.dump(R, open("tg_test_report.json", "w"), indent=2, ensure_ascii=False)
print(json.dumps(R["C_measured_table"], indent=2, ensure_ascii=False))
