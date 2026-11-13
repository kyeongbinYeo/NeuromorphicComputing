"""
Fig.3f 검증: 4.0 V / 100 us 펄스 1개 뒤의 감쇠 I_D(t).

두 가지로 비교한다.
  (a) 절대값: 모델(3h 소자 기준)과 3f 측정값을 그대로 비교. 3f는 다른 소자·기준 전류라
      펄스 직후 증가분이 3h보다 크다(약 1.4 vs 0.86 uA). 이 차이는 소자 간 차이로 기록한다.
  (b) 모양: (I_D − 기준) / 펄스 직후 초과 전류. 4.0 V, 4.5 V 곡선. 감쇠 파라미터가 3f 모양을
      얼마나 따라가는지 본다 (4.5 V는 펄스 전압이 지원 범위 밖이지만, 감쇠 모양은 펄스 직후
      초과 전류만으로 정해지므로 높은 상태의 감쇠 검사로 쓴다).

    python validation/validate_fig3f.py
"""
from __future__ import annotations

import json

import numpy as np

from vcommon import RESULTS, metrics, plt, save

from fit_relaxation import load_fig3f
from model import MPBTFT
from parameters import MPBTFTParams
from reservoir import BG_WIDTH_S

ROOT_RESULTS = RESULTS.parent.parent / "fitting" / "results" / "relaxation_fig3f.json"


def main():
    p = MPBTFTParams.load()
    curves = load_fig3f()
    rep3f = json.loads(ROOT_RESULTS.read_text(encoding="utf-8"))

    # (a) 절대값
    t, i = curves["4.0"]
    d = MPBTFT(p, mode="reservoir")
    d.apply_bg_pulse(0.0, 4.0, BG_WIDTH_S, 0.0)
    pred = np.array([d.read_current(BG_WIDTH_S + tt) for tt in t])
    abs_m = metrics(pred, i)

    # (b) 모양
    shape = {}
    rl = p.reservoir.relaxation
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.2))
    ax[0].plot(t * 1e3, i * 1e6, ".", ms=1.5, alpha=0.4, label="Fig.3f 4.0 V data")
    ax[0].plot(t * 1e3, pred * 1e6, "k-", lw=1.2, label="model (Fig.3h device)")
    ax[0].set(title="(a) absolute I_D after one 4.0 V pulse", xlabel="time after pulse (ms)", ylabel="I_D (uA)")
    ax[0].legend(fontsize=8)
    for v, c in (("4.0", "C0"), ("4.5", "C3")):
        t, i = curves[v]
        e0 = rep3f["curves"][v]["excess_at_pulse_end_A"]
        y = (i - rep3f["shared_I0_A"]) / e0
        w = rl.fast_share
        ts = rl.tau_slow_s(e0)
        ym = w * np.exp(-t / rl.tau_fast_s) + (1 - w) * np.exp(-t / ts)
        shape[v] = metrics(ym, y, scale=1.0)
        ax[1].plot(t * 1e3, y, ".", ms=1.5, alpha=0.35, color=c, label=f"data {v} V")
        ax[1].plot(t * 1e3, ym, "-", color=c, lw=1.2, label=f"model, excess {e0 * 1e6:.2f} uA")
    ax[1].set(title="(b) normalized decay shape", xlabel="time after pulse (ms)", ylabel="excess / excess at pulse end")
    ax[1].legend(fontsize=8)
    plt.tight_layout()
    plt.savefig(RESULTS / "validate_fig3f.png", dpi=130)
    plt.close(fig)

    save("fig3f", {
        "absolute_4p0V_uA": abs_m,
        "absolute_note": "Fig.3f and Fig.3h are different measurements (jump ~1.4 vs ~0.86 uA); "
                         "the model follows Fig.3h, so the absolute offset is a device-to-device difference.",
        "normalized_shape": shape,
        "per_curve_double_exponential_fit": rep3f,
    })


if __name__ == "__main__":
    main()
