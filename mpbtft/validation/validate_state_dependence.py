"""
상태 의존 BG 업데이트 검증 (사양서 22.2, Supp. Fig.11 대신).

질문: 이전 이력이 달라도 '현재 I_D + 펄스'만으로 다음 I_D를 예측할 수 있는가?

Supp. Fig.11은 Source data가 없고 그림만 있어 v1에서는 디지타이즈하지 않았다.
대신 Fig.3h/3i/3j에서 모델 없이 잰 펄스 효과(pair jump)를 쓴다:
  k번째 timeframe만 다른 두 비트열(펄스 있음/없음, 앞부분 같음)의 차이 = 그 펄스의 효과.
  같은 직전 전류에서 이력(k = 몇 번째 펄스인지)이 달라도 효과가 같은지 본다.

비교 대상
  - data: pair jump (읽기 시점 값)
  - model: 같은 비트열 쌍을 모델로 시뮬레이션한 pair jump

    python validation/validate_state_dependence.py
"""
from __future__ import annotations

import numpy as np

from vcommon import RESULTS, metrics, plt, save

from common import pair_jumps, simulate_states, load_states
from parameters import MPBTFTParams


def model_pairs(p, name):
    seqs, _ = load_states(name)
    sim = simulate_states(p, name)
    idx = {b: i for i, b in enumerate(seqs)}
    out = []
    for b in seqs:
        for k, c in enumerate(b):
            if c == "1":
                o = b[:k] + "0" + b[k + 1:]
                out.append(sim[idx[b], k + 1] - sim[idx[o], k + 1])
    return np.array(out)


def main():
    p = MPBTFTParams.load()
    res = {}
    fig, ax = plt.subplots(1, 3, figsize=(15, 4.2))
    for a, name in zip(ax, ("fig3h", "fig3i", "fig3j")):
        pj = pair_jumps(name, p.reservoir.baseline_A)
        mj = model_pairs(p, name)
        m = metrics(mj, pj[:, 2])
        # 이력 의존성: TG 0 V(3h)에서 같은 직전 전류 구간(0.4 uA 폭)에 든 pair들의 k별 평균 차이
        hist = None
        if name == "fig3h":
            bins = np.arange(0.9e-6, 3.0e-6, 0.4e-6)
            spread = []
            for lo in bins:
                sel = (pj[:, 1] >= lo) & (pj[:, 1] < lo + 0.4e-6)
                ks = sorted(set(pj[sel, 0].astype(int)))
                if len(ks) >= 2:
                    means = [pj[sel & (pj[:, 0] == k), 2].mean() for k in ks]
                    spread.append({"id_pre_bin_uA": [float(lo * 1e6), float((lo + 0.4e-6) * 1e6)], "pulse_index_k": [int(k) for k in ks],
                                   "mean_jump_uA": [float(v * 1e6) for v in means]})
            slope = np.polyfit(pj[:, 1] * 1e6, pj[:, 2] * 1e6, 1)[0]
            hist = {"same_state_different_history": spread,
                    "data_slope_jump_vs_id_pre": float(slope),
                    "model_table_slope_first_to_last_knot": float(
                        (p.reservoir.bg_update.delta_id_A.y[-1] - p.reservoir.bg_update.delta_id_A.y[0])
                        / (p.reservoir.bg_update.delta_id_A.x[-1] - p.reservoir.bg_update.delta_id_A.x[0]))}
        res[name] = {"pair_jump_uA": m, **({"history_check": hist} if hist else {})}
        sc = a.scatter(pj[:, 1] * 1e6, pj[:, 2] * 1e6, c=pj[:, 3], cmap="plasma", s=18, label="data")
        a.scatter(pj[:, 1] * 1e6, mj * 1e6, facecolors="none", edgecolors="k", s=22, label="model")
        a.set(title=f"{name}: pulse effect vs I_D before pulse", xlabel="I_D before pulse (uA)",
              ylabel="jump at read point (uA)")
        a.legend(fontsize=8)
        plt.colorbar(sc, ax=a, label="V_TG (V)")
    plt.tight_layout()
    plt.savefig(RESULTS / "validate_state_dependence.png", dpi=130)
    plt.close(fig)
    res["note"] = ("Supp. Fig.11 has no source data and was not digitized for v1; the pair-jump test on "
                   "Fig.3h/3i/3j replaces it.")
    save("state_dependence", res)


if __name__ == "__main__":
    main()
