"""피팅·검증 스크립트가 함께 쓰는 데이터 로더와 시뮬레이션 도우미."""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from lif import EXC_DELAY_S, EXC_WIDTH_S, INH_DELAY_S, INH_WIDTH_S, LIFNeuron  # noqa: E402
from model import MPBTFT  # noqa: E402
from reservoir import FIG3I_TG_V, FIG3J_TG_V, run_bit_train  # noqa: E402

DATA = ROOT / "data"
EXC_PERIOD_S = EXC_WIDTH_S + EXC_DELAY_S


# ----------------------------------------------------------------- reservoir
def load_states(name: str):
    """fig3h / fig3i / fig3j → (bits 리스트, 배열 [n_seq, n_pulse+1]) (A)."""
    sub = "bg_update" if name == "fig3h" else "tg_modulation"
    rows = list(csv.DictReader(open(DATA / sub / f"{name}_states.csv", encoding="utf-8")))
    seqs = sorted({r["bits"] for r in rows})
    n_k = max(int(r["pulse_number"]) for r in rows) + 1
    arr = np.zeros((len(seqs), n_k))
    idx = {b: i for i, b in enumerate(seqs)}
    for r in rows:
        arr[idx[r["bits"]], int(r["pulse_number"])] = float(r["id_A"])
    return seqs, arr


def reservoir_schedule(name: str):
    return {"fig3h": None, "fig3i": FIG3I_TG_V, "fig3j": FIG3J_TG_V}[name]


def simulate_states(params, name: str, strict: bool = True):
    """그림과 같은 비트열을 모델에 넣어 [n_seq, n_pulse+1] 배열을 만든다 (0번 = 펄스 전)."""
    seqs, _ = load_states(name)
    sched = reservoir_schedule(name)
    out = []
    for b in seqs:
        d = MPBTFT(params, mode="reservoir", strict=strict)
        out.append([d.read_current(0.0)] + run_bit_train(d, b, 0.0, tg_voltages_V=sched))
    return np.array(out)


def pair_jumps(name: str, i0_A: float):
    """모델 없이 데이터에서 펄스 1개의 효과를 잰다.

    k번째 timeframe에서만 다른 두 비트열 (A: 펄스 있음, B: 없음, 앞부분 같음)을 같은 시점에서 빼면
    그 펄스로 생긴 증가분. B의 값이 '펄스 직전 상태'의 근사.
    반환: 배열 [n, 4] = (pulse index k, I_pre ≈ B_k, ΔI = A_k − B_k, V_TG)
    """
    seqs, arr = load_states(name)
    sched = reservoir_schedule(name)
    idx = {b: i for i, b in enumerate(seqs)}
    out = []
    for b in seqs:
        for k, c in enumerate(b):
            if c != "1":
                continue
            other = b[:k] + "0" + b[k + 1:]
            ia, ib = idx[b], idx[other]
            vtg = 0.0 if sched is None else sched[k]
            out.append((k, arr[ib, k + 1], arr[ia, k + 1] - arr[ib, k + 1], vtg))
    return np.array(out)


# ----------------------------------------------------------------------- LIF
def load_curve(rel_path: str):
    d = np.loadtxt(DATA / rel_path, delimiter=",", skiprows=1)
    return d[:, 0], d[:, 1]


def find_trains(t, i, thr_A=2.5e-6, min_samples=20):
    """흥분 펄스열 시작 시각들을 찾는다. 펄스 사이 10 us 간격은 샘플 1개 정도로만 보인다."""
    on = i > thr_A
    starts, ends = [], []
    st = None
    for k in range(len(t)):
        if on[k] and st is None:
            st = k
        if not on[k] and st is not None:
            if k - st >= min_samples:
                starts.append(t[st]); ends.append(t[k - 1])
            st = None
    # 연속 구간 사이 간격이 짧으면(펄스 사이 10 us 간격) 같은 펄스열. 간격 샘플이 빠져 두 펄스가
    # 한 구간으로 이어 보이는 경우도 있으므로, 펄스 수는 길이를 주기로 나눠 센다.
    trains = []
    for a, e in zip(starts, ends):
        if trains and a - trains[-1]["last_end"] < 100e-6:
            trains[-1]["last_end"] = e
        else:
            trains.append({"t0": a - 5e-6, "last_end": e})
    for tr in trains:
        tr["n"] = int(round((tr["last_end"] + 10e-6 - tr["t0"] + EXC_DELAY_S) / EXC_PERIOD_S))
        tr["t_end"] = tr["t0"] + (tr["n"] - 1) * EXC_PERIOD_S + EXC_WIDTH_S
    return trains


def envelope(t, i, t0, n):
    """펄스 k의 '펄스 끝 무렵 전류' = 펄스 끝 직전 ~100 us 구간의 중앙값."""
    out = []
    for k in range(n):
        a = t0 + k * EXC_PERIOD_S
        m = (t >= a + EXC_WIDTH_S - 110e-6) & (t <= a + EXC_WIDTH_S - 15e-6)
        out.append(float(np.median(i[m])) if m.any() else np.nan)
    return np.array(out)


def rest_current(t, i, t0):
    m = (t > t0 - 300e-6) & (t < t0 - 20e-6)
    return float(np.mean(i[m]))


def simulate_lif_protocol(params, trains, inh=None, decay_times=None, strict=True):
    """LIF 프로토콜 시뮬레이션.

    trains: [(t0, n), ...] 흥분 펄스열
    inh: (n_inh, t_end_before_train_index) 또는 None — 억제 펄스 n_inh개를 해당 펄스열 시작
         10 us 전에 끝나도록 배치 (Fig.4g 그림의 배치)
    decay_times: 마지막 펄스열 뒤 등에서 휴지 전류를 읽을 시각 리스트
    반환: (펄스열별 펄스 중 전류 리스트, decay_times에서 읽은 전류, 억제 직전 I_D 리스트)
    """
    dev = MPBTFT(params, mode="lif", time_s=0.0, strict=strict, allow_experimental=True)
    neuron = LIFNeuron(dev)
    envs, inh_pre = [], []
    reads = []
    pending = sorted(decay_times) if decay_times is not None else []
    for j, (t0, n) in enumerate(trains):
        if inh is not None and inh[1] == j and inh[0] > 0:
            n_inh = inh[0]
            t_first = t0 - INH_DELAY_S - n_inh * INH_WIDTH_S - (n_inh - 1) * INH_DELAY_S
            # 앞 펄스열 뒤의 읽기 먼저
            while pending and pending[0] <= t_first:
                reads.append(dev.read_current(pending.pop(0)))
            tt = t_first
            for _ in range(n_inh):
                inh_pre.append(dev.read_current(tt))
                neuron.inhibit(tt)
                tt += INH_WIDTH_S + INH_DELAY_S
        while pending and pending[0] <= t0:
            reads.append(dev.read_current(pending.pop(0)))
        on, _ = neuron.excite_train(t0, n)
        envs.append(np.array(on))
    for tr in pending:
        reads.append(dev.read_current(tr))
    return envs, np.array(reads), inh_pre
