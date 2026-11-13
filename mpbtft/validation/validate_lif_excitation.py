"""
LIF 흥분 / leak 검증.

  1. Fig.4b (피팅에 사용): 펄스 중 전류(envelope) 60개, self-reset 곡선, 발화 펄스 번호
  2. Fig.4c V_base = 0 V (hold-out): 같은 프로토콜, 다른 측정
  3. Fig.4g 첫 펄스열 (hold-out): 같은 프로토콜, 다른 소자 상태 — 소자 간 차이를 보여준다
  4. 경향 검사 (Source data 없음, 캡션의 서술과 비교)
     - Supp. Fig.18: t_reset이 짧으면 두 번째 펄스열이 더 적은 펄스로 발화
     - Supp. Fig.19: 펄스 사이 지연(0.5, 1.0 ms)이 길면 leak 때문에 적분이 덜 됨

    python validation/validate_lif_excitation.py
"""
from __future__ import annotations

import numpy as np

from vcommon import RESULTS, metrics, plt, save

from common import EXC_PERIOD_S, envelope, find_trains, load_curve, simulate_lif_protocol
from lif import EXC_WIDTH_S, FIG4B_ITH_A, LIFNeuron
from model import MPBTFT
from parameters import MPBTFTParams


def first_fire(env, ith=FIG4B_ITH_A):
    idx = np.flatnonzero(np.asarray(env) >= ith)
    return int(idx[0]) + 1 if idx.size else None


def compare_curve(p, rel, label, ax=None, with_decay=True):
    t, i = load_curve(rel)
    trains = find_trains(t, i)
    tr = [(x["t0"], x["n"]) for x in trains]
    data_env = [envelope(t, i, a, n) for a, n in tr]
    dec_t = np.array([])
    if with_decay:
        sel = np.zeros_like(t, dtype=bool)
        for x in trains:
            sel |= (t > x["t_end"] + 20e-6) & (t < x["t_end"] + 2.9e-3)
        dec_t = t[sel]
    env, reads, _ = simulate_lif_protocol(p, tr, decay_times=list(dec_t))
    out = {
        "envelope_uA": metrics(np.concatenate(env), np.concatenate(data_env)),
        "first_fire_pulse_index_data": [first_fire(e) for e in data_env],
        "first_fire_pulse_index_model": [first_fire(e) for e in env],
    }
    if with_decay:
        out["self_reset_uA"] = metrics(reads, i[np.isin(t, dec_t)])
    if ax is not None:
        ax.plot(t * 1e3, i * 1e6, lw=0.3, color="0.6", label="data (raw)")
        for (a, n), e_d, e_m in zip(tr, data_env, env):
            tk = (a + np.arange(n) * EXC_PERIOD_S + EXC_WIDTH_S) * 1e3
            ax.plot(tk, e_d * 1e6, "o", ms=2.5, color="C0")
            ax.plot(tk, e_m * 1e6, "-", lw=1.2, color="C3")
        if with_decay:
            ax.plot(dec_t * 1e3, reads * 1e6, ".", ms=1.5, color="C3")
        ax.axhline(FIG4B_ITH_A * 1e6, ls="--", color="r", lw=0.8)
        ax.set(title=f"{label}: dots = data envelope, red = model", xlabel="time (ms)", ylabel="I_D (uA)")
    return out


def trend_reset_time(p):
    """Supp. Fig.18: 30 펄스 → t_reset → 30 펄스. 두 번째 펄스열의 첫 발화 펄스 번호."""
    out = {}
    for tr_ms in (1.0, 2.0, 3.0):
        dev = MPBTFT(p, mode="lif")
        nrn = LIFNeuron(dev)
        _, t_end = nrn.excite_train(0.0, 30)
        env2, _ = nrn.excite_train(t_end + tr_ms * 1e-3, 30)
        out[f"t_reset_{tr_ms:g}ms"] = {"train2_first_fire_pulse": first_fire(env2),
                                       "train2_first_pulse_uA": float(env2[0] * 1e6)}
    # Supp. Fig.18 그림에서 읽은 두 번째 펄스열 첫 펄스 전류 (다른 소자, ±0.1 uA).
    # 그림에서는 1 ms 뒤 두 번째 펄스열이 첫 펄스열보다 높게 시작한다 → 모델은 이 잔류를 과소평가.
    out["t_reset_1ms"]["figure_read_train2_first_pulse_uA"] = 5.6
    out["t_reset_2ms"]["figure_read_train2_first_pulse_uA"] = 5.3
    return out


def trend_delay(p):
    """Supp. Fig.19: 펄스 사이 지연 10 us / 0.5 ms / 1.0 ms에서 30 펄스 후 envelope."""
    out = {}
    for d in (10e-6, 0.5e-3, 1.0e-3):
        dev = MPBTFT(p, mode="lif")
        env, _ = LIFNeuron(dev).excite_train(0.0, 30, delay_s=d)
        out[f"delay_{d * 1e3:g}ms"] = {"last_pulse_uA": float(env[-1] * 1e6), "first_fire_pulse": first_fire(env)}
    # Supp. Fig.19 그림에서 눈으로 읽은 펄스 중 전류 윗선 (Source data 없음, ±0.1 uA)
    out["delay_0.5ms"]["figure_read_uA"] = 4.9
    out["delay_1ms"]["figure_read_uA"] = 4.6
    return out


def main():
    p = MPBTFTParams.load()
    fig, ax = plt.subplots(3, 1, figsize=(12, 11))
    res = {
        "fig4b_fit": compare_curve(p, "lif_excitation/fig4b.csv", "Fig.4b (fit)", ax[0]),
        "fig4c_vbase0_holdout": compare_curve(p, "lif_excitation/fig4c_vbase_0V.csv", "Fig.4c V_base=0 V (hold-out)", ax[1]),
        "fig4g_train1_holdout": {},
    }
    for n in range(1, 6):
        t, i = load_curve(f"tg_inhibition/fig4g_N{n}.csv")
        tr = find_trains(t, i)[0]
        d_env = envelope(t, i, tr["t0"], 30)
        env, _, _ = simulate_lif_protocol(p, [(tr["t0"], 30)])
        res["fig4g_train1_holdout"][f"N{n}"] = metrics(env[0], d_env)
        if n == 1:
            tk = (tr["t0"] + np.arange(30) * EXC_PERIOD_S + EXC_WIDTH_S) * 1e3
            ax[2].plot(tk, d_env * 1e6, "o", ms=3, label="Fig.4g N=1 first train (data)")
            ax[2].plot(tk, env[0] * 1e6, "-", color="C3", label="model")
    ax[2].set(title="Fig.4g first train (hold-out, different device state)", xlabel="time (ms)", ylabel="I_D (uA)")
    ax[2].legend(fontsize=8)
    res["trend_supp_fig18_reset_time"] = trend_reset_time(p)
    res["trend_supp_fig19_pulse_delay"] = trend_delay(p)
    r18 = res["trend_supp_fig18_reset_time"]
    fires = [r18[k]["train2_first_fire_pulse"] or 99 for k in ("t_reset_1ms", "t_reset_2ms", "t_reset_3ms")]
    r19 = res["trend_supp_fig19_pulse_delay"]
    lasts = [r19[k]["last_pulse_uA"] for k in ("delay_0.01ms", "delay_0.5ms", "delay_1ms")]
    res["trend_checks_pass"] = {
        "shorter_reset_fires_with_fewer_or_equal_pulses": bool(fires[0] <= fires[1] <= fires[2]),
        "longer_delay_less_integration": bool(lasts[0] > lasts[1] > lasts[2]),
    }
    plt.tight_layout()
    plt.savefig(RESULTS / "validate_lif_excitation.png", dpi=120)
    plt.close(fig)
    save("lif_excitation", res)


if __name__ == "__main__":
    main()
