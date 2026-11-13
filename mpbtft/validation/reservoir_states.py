"""Fig.3h / 3i / 3j 공통 검증: 그림과 같은 비트열을 상태 전이로 시뮬레이션해서 비교한다."""
from __future__ import annotations

import numpy as np

from vcommon import RESULTS, metrics, min_gap, plt, rank_corr, save

from common import load_states, reservoir_schedule, simulate_states
from parameters import MPBTFTParams

ROLE = {
    "fig3h": "fit (BG table and relaxation were fitted to this figure)",
    "fig3i": "fit (only the TG gain M(1.5/3/5 V) was fitted to this figure)",
    "fig3j": "hold-out (not used in any fit; 1.0 V and 2.0 V TG are interpolated)",
}


def validate(name: str):
    p = MPBTFTParams.load()
    seqs, data = load_states(name)
    sim = simulate_states(p, name, strict=True)
    m = metrics(sim, data)
    m_final = metrics(sim[:, -1], data[:, -1])
    per_pulse = [metrics(sim[:, k], data[:, k])["rmse"] for k in range(data.shape[1])]
    worst = int(np.argmax(np.abs(sim[:, -1] - data[:, -1])))
    result = {
        "role": ROLE[name],
        "tg_schedule_V": reservoir_schedule(name),
        "all_points_uA": m,
        "final_state_uA": m_final,
        "rmse_by_pulse_number_uA": per_pulse,
        "final_state_rank_correlation": rank_corr(sim[:, -1], data[:, -1]),
        "min_gap_between_final_states_uA": {"data": min_gap(data[:, -1]), "model": min_gap(sim[:, -1])},
        "worst_final_sequence": {"bits": seqs[worst], "data_uA": float(data[worst, -1] * 1e6),
                                 "model_uA": float(sim[worst, -1] * 1e6)},
    }
    save(name, result)

    fig, ax = plt.subplots(1, 2, figsize=(12, 4.4))
    n_k = data.shape[1]
    for i, b in enumerate(seqs):
        c = plt.cm.viridis(i / max(len(seqs) - 1, 1))
        ax[0].plot(range(n_k), data[i] * 1e6, "o", color=c, ms=3.5)
        ax[0].plot(range(n_k), sim[i] * 1e6, "-", color=c, lw=1)
    ax[0].set(title=f"{name}: dots = data, lines = model", xlabel="pulse number", ylabel="I_D (uA)")
    ax[1].plot(data[:, -1] * 1e6, sim[:, -1] * 1e6, "o", ms=4)
    lo, hi = data[:, -1].min() * 1e6 - 0.1, data[:, -1].max() * 1e6 + 0.1
    ax[1].plot([lo, hi], [lo, hi], "k--", lw=0.8)
    for i, b in enumerate(seqs):
        ax[1].annotate(b, (data[i, -1] * 1e6, sim[i, -1] * 1e6), fontsize=6, alpha=0.7)
    ax[1].set(title=f"final state  RMSE {m_final['rmse']:.3f} uA ({ROLE[name].split(' ')[0]})",
              xlabel="data (uA)", ylabel="model (uA)")
    plt.tight_layout()
    plt.savefig(RESULTS / f"validate_{name}.png", dpi=130)
    plt.close(fig)
    return result
