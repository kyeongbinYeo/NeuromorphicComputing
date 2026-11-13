"""
TG 억제 검증 (experimental).

  1. 기본 설정(allow_experimental=False)에서는 오류로 막히는지
  2. allow_experimental=True일 때 지원 범위에서 I_D+ < I_D− 인지 (사양서 22.7)
  3. Fig.4g: N = 2..5 곡선과 N = 1 곡선의 두 번째 펄스열 차이 — 데이터 vs 모델
     (모델이 차이를 얼마나 재현하지 못하는지 그대로 보여준다)

    python validation/validate_tg_inhibition.py
"""
from __future__ import annotations

import numpy as np

from vcommon import RESULTS, plt, save

from domains import UncalibratedFeatureError
from fit_tg_inhibition import fig4g
from common import simulate_lif_protocol
from lif import LIFNeuron
from model import MPBTFT
from parameters import MPBTFTParams


def main():
    p = MPBTFTParams.load()
    inh = p.lif.tg_inhibition

    blocked = False
    try:
        d = MPBTFT(p, mode="lif")
        LIFNeuron(d).excite_train(0.0, 10)
        d.apply_tg_inhibition(6e-3, 5.0, 100e-6)
    except UncalibratedFeatureError:
        blocked = True

    # 지원 범위 안의 여러 직전 상태에서 I+ < I−
    lo, hi = inh.id_pre_domain_A
    pairs = []
    for n_exc in range(1, 31):
        d = MPBTFT(p, mode="lif", allow_experimental=True)
        _, t_end = LIFNeuron(d).excite_train(0.0, n_exc)
        for wait in (0.2e-3, 0.5e-3, 1.0e-3):
            t = t_end + wait
            pre = d.read_current(t)
            if lo <= pre <= hi:
                dd = MPBTFT(p, mode="lif", allow_experimental=True)
                _, te = LIFNeuron(dd).excite_train(0.0, n_exc)
                post = dd.apply_tg_inhibition(te + wait, 5.0, 100e-6)
                pairs.append((pre, post))
    pairs = np.array(pairs)
    decreases = bool(np.all(pairs[:, 1] < pairs[:, 0])) if len(pairs) else None

    data = {n: fig4g(n) for n in range(1, 6)}
    sims = {}
    for n in range(1, 6):
        env, _, _ = simulate_lif_protocol(p, data[n][0], inh=(n, 1))
        sims[n] = env[1]
    diff = {}
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    for n in range(2, 6):
        dd_ = (data[n][1][1] - data[1][1][1]) * 1e6
        dm_ = (sims[n] - sims[1]) * 1e6
        diff[f"N{n}_minus_N1"] = {"data_first_pulse_uA": float(dd_[0]), "model_first_pulse_uA": float(dm_[0]),
                                  "data_mean_uA": float(dd_.mean()), "model_mean_uA": float(dm_.mean())}
        ax[0].plot(range(1, 14), dd_, "o-", ms=3, label=f"data N={n}")
        ax[0].plot(range(1, 14), dm_, "--", color=ax[0].lines[-1].get_color(), lw=1)
    ax[0].set(title="Fig.4g second train: (N) − (N=1)   solid = data, dashed = model",
              xlabel="excitation pulse in second train", ylabel="difference (uA)")
    ax[0].legend(fontsize=8)
    if len(pairs):
        ax[1].plot(pairs[:, 0] * 1e6, pairs[:, 1] * 1e6, "o", ms=3)
        ax[1].plot([lo * 1e6, hi * 1e6], [lo * 1e6, hi * 1e6], "k--", lw=0.8)
    ax[1].set(title=f"one 5 V / 100 us inhibitory pulse (retention {inh.retention:.2f}, experimental)",
              xlabel="I_D before (uA)", ylabel="I_D after (uA)")
    plt.tight_layout()
    plt.savefig(RESULTS / "validate_tg_inhibition.png", dpi=130)
    plt.close(fig)

    save("tg_inhibition", {
        "status": inh.status,
        "blocked_without_allow_experimental": blocked,
        "id_post_less_than_id_pre_in_domain": decreases,
        "n_checked_states": int(len(pairs)),
        "retention": inh.retention,
        "id_pre_domain_A": inh.id_pre_domain_A,
        "fig4g_second_train_differences": diff,
        "missing_evidence": inh.note,
    })


if __name__ == "__main__":
    main()
