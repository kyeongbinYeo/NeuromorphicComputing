"""
실제 시간으로 잊어버리는 MPBTFT를 키보드로 만져보는 데모.

소자 시간 = (time.perf_counter() 경과) / slow. 기본 slow 1000 → 실제 1초 = 소자 1 ms.

    python examples/realtime_demo.py                     # reservoir, 그래프 창
    python examples/realtime_demo.py --vtg 3             # 펄스와 함께 TG 3 V
    python examples/realtime_demo.py --mode lif          # LIF: 스페이스 = 흥분 펄스
    python examples/realtime_demo.py --mode lif --experimental   # i 키 = 억제 펄스 (experimental)
    python examples/realtime_demo.py --terminal          # 창 없이 터미널 (Enter = 펄스, q = 종료)

키: 스페이스 = 펄스, i = 억제(LIF, --experimental), r = 초기화
보정 범위 밖이 되거나(펄스를 너무 많이 줌) 펄스가 겹치면 그 펄스는 무시하고 이유를 출력한다.
"""
from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from domains import UncalibratedFeatureError  # noqa: E402
from lif import LIFNeuron  # noqa: E402
from model import MPBTFT  # noqa: E402
from parameters import MPBTFTParams  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--mode", choices=("reservoir", "lif"), default="reservoir")
ap.add_argument("--slow", type=float, default=1000.0, help="몇 배 느리게 볼지 (1000 → 실제 1초 = 소자 1 ms)")
ap.add_argument("--vtg", type=float, default=0.0, help="reservoir: 펄스와 함께 거는 TG 전압 (0~5 V)")
ap.add_argument("--experimental", action="store_true", help="LIF 억제 펄스(experimental) 허용")
ap.add_argument("--terminal", action="store_true")
a = ap.parse_args()
if a.mode == "lif" and a.slow == 1000.0:
    a.slow = 5000.0   # LIF는 감쇠가 0.1~1 ms라 더 느리게

p = MPBTFTParams.load()
T0 = time.perf_counter()
dev = MPBTFT(p, mode=a.mode, allow_experimental=a.experimental)
neuron = LIFNeuron(dev) if a.mode == "lif" else None
lock = threading.Lock()


def now():
    return (time.perf_counter() - T0) / a.slow


def safe_read():
    with lock:
        t = now()
        ev = dev.last_event
        if ev is not None and t < ev.end_s:
            t = ev.end_s
        return dev.read_current(t) * 1e6


def pulse():
    with lock:
        t = max(now(), dev.last_update_time_s)
        try:
            if neuron is None:
                dev.apply_bg_pulse(t, 4.0, 100e-6, a.vtg)
            elif neuron.excite(t):
                print(f"\n  spike! (current during pulse {dev.last_event.id_during_pulse_A * 1e6:.2f} uA)")
        except (ValueError, UncalibratedFeatureError) as e:
            print("\n  pulse ignored:", e)


def inhibit():
    if neuron is None:
        return
    with lock:
        t = max(now(), dev.last_update_time_s)
        try:
            neuron.inhibit(t)
        except (ValueError, UncalibratedFeatureError) as e:
            print("\n  inhibition ignored:", e)


def reset():
    with lock:
        dev.initialize(max(now(), dev.last_update_time_s))


if a.terminal:
    stop = False

    def show():
        while not stop:
            v = safe_read()
            bar = "█" * int((v - dev.baseline_current_A * 1e6) * 20)
            print(f"\rI_D = {v:5.2f} uA  {bar:<60}", end="", flush=True)
            time.sleep(0.05)

    threading.Thread(target=show, daemon=True).start()
    print(f"[{a.mode}] Enter = 펄스, i+Enter = 억제(LIF), r+Enter = 초기화, q+Enter = 종료")
    try:
        while True:
            s = input()
            if s == "q":
                break
            {"i": inhibit, "r": reset}.get(s, pulse)()
    except EOFError:
        pass
    stop = True
else:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation

    ts, ys = [], []
    fig, ax = plt.subplots(figsize=(8, 4))
    line, = ax.plot([], [], lw=2)
    top = 4 if a.mode == "reservoir" else 2.5
    ax.set(xlabel=f"real time (s)  [device time × {a.slow:g}]", ylabel="I_D at rest bias (uA)",
           title=f"{a.mode}: space = pulse | i = inhibit (LIF) | r = reset", ylim=(0, top))

    def on_key(e):
        {" ": pulse, "i": inhibit, "r": reset}.get(e.key, lambda: None)()

    fig.canvas.mpl_connect("key_press_event", on_key)

    def update(_):
        real = time.perf_counter() - T0
        ts.append(real)
        ys.append(safe_read())
        while ts and ts[0] < real - 60:
            ts.pop(0); ys.pop(0)
        line.set_data(ts, ys)
        ax.set_xlim(max(0, real - 60), max(60, real))
        return line,

    _anim = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    plt.show()
