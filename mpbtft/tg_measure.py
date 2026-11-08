"""
모델 없이 Source data에서 직접 TG 효과를 재는 스크립트.

1) Fig.3h/3i/3j: 같은 시점 '펄스 있음 − 없음' = 점프 → V_TG별 펄스 효과 배율 (→ mpbtft.py tg_table)
2) Fig.3h/3i/3j: 펄스 없는 3 ms 동안 남는 비율 → V_TG별 감쇠 (TG가 감쇠를 바꾸는지)
3) Fig.3g: V_TG 0~5 V 고정, 간격 1.1 ms 펄스열의 펄스 후 상태 (참고용, 조건이 달라 tg_table에는 안 씀)

  python tg_measure.py source_data.xlsx  → tg_measure.json
"""
import sys, json
import numpy as np, openpyxl

XLSX = sys.argv[1] if len(sys.argv) > 1 else "source_data.xlsx"
r = list(openpyxl.load_workbook(XLSX, data_only=True, read_only=True)["Fig.3"].iter_rows(values_only=True))
blk = lambda r0, n, c1: np.array([[r[i][c] for c in range(36, c1)] for i in range(r0, r0 + n)], float).T * 1e6
SETS = {"3h": (blk(2, 5, 52), [0, 0, 0, 0]), "3i": (blk(10, 5, 52), [5, 3, 1.5, 0]), "3j": (blk(18, 6, 68), [1, 5, 3, 2, 0])}
I0 = 1.0
out = {"jump": {}, "decay_ratio_3ms": {}}

jumps, decays = {}, {}
for name, (D, tg) in SETS.items():
    n = len(tg)
    for i in range(D.shape[0]):
        b = format(i, f"0{n}b")
        for k in range(n):
            if b[k] == "1":                                  # k번째 펄스만 없는 입력과 비교
                j = int(b[:k] + "0" + b[k + 1:], 2)
                jumps.setdefault(tg[k], []).append(D[i, k + 1] - D[j, k + 1])
            if k < n - 1 and b[k + 1] == "0":                # 다음 timeframe에 펄스 없음 → 순수 감쇠
                a, c = D[i, k + 1] - I0, D[i, k + 2] - I0
                if a > 0.25: decays.setdefault(tg[k], []).append(c / a)
j0 = np.mean(jumps[0])
print("V_TG | 점프 μA (0 V 대비) | 3 ms 뒤 남는 비율")
for v in sorted(jumps):
    q = np.array(jumps[v]); dd = np.array(decays.get(v, [np.nan]))
    out["jump"][str(v)] = {"mean_uA": float(q.mean()), "std": float(q.std()), "n": len(q), "relative_to_0V": float(q.mean() / j0)}
    out["decay_ratio_3ms"][str(v)] = {"mean": float(np.nanmean(dd)), "std": float(np.nanstd(dd)), "n": int(np.isfinite(dd).sum())}
    print(f"{v:>4} | {q.mean():.2f} ± {q.std():.2f} ({q.mean()/j0:.2f}) n={len(q)} | {np.nanmean(dd):.2f} ± {np.nanstd(dd):.2f} n={np.isfinite(dd).sum()}")

# Fig.3g
rows = r[2:]
t = np.array([x[27] for x in rows if isinstance(x[27], (int, float))])
P, W = [0.11e-3, 1.21e-3, 2.31e-3, 3.41e-3], 0.10e-3
win = [(P[k] + W + 0.05e-3, (P[k + 1] if k < 3 else t[-1])) for k in range(4)]
out["fig3g_levels_uA"] = {}
for v, c in zip([0, 1, 2, 3, 4, 5], range(28, 34)):
    y = np.array([x[c] for x in rows if isinstance(x[c], (int, float))]) * 1e6
    out["fig3g_levels_uA"][str(v)] = [float(y[(t >= a) & (t < b)].mean()) for a, b in win]
print("Fig.3g 펄스 후 상태(μA):", {k: [round(x, 2) for x in v] for k, v in out["fig3g_levels_uA"].items()})
json.dump(out, open("tg_measure.json", "w"), indent=2, ensure_ascii=False)
