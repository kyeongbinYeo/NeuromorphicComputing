"""
실제 시간(time.perf_counter)으로 '잊어버리는' MPBTFT를 직접 만져보는 데모.

소자는 ms 단위로 잊기 때문에 사람 눈으로 보려면 느리게 돌려야 함.
  --slow 1000 → 실제 1초 = 소자 1 ms  (기본값)

  python realtime_demo.py            # matplotlib 창: 스페이스=4V 펄스, 5=4.5V 펄스, r=리셋
  python realtime_demo.py --terminal # 창 없이 터미널: Enter=펄스, q=종료
  python realtime_demo.py --vtg 3    # TG 3 V 걸린 상태 (펄스 효과 약 0.59배)
"""
import argparse, threading, time
from mpbtft import MPBTFT, MPBTFTParams

ap = argparse.ArgumentParser()
ap.add_argument("--params", default="params.json")
ap.add_argument("--slow", type=float, default=1000.0, help="몇 배 느리게 볼지")
ap.add_argument("--terminal", action="store_true")
ap.add_argument("--vtg", type=float, default=0.0, help="TG 전압 (V). 펄스 효과만 줄이고 감쇠는 그대로")
a = ap.parse_args()

p = MPBTFTParams.load(a.params)
dev = MPBTFT(p, clock=time.perf_counter, time_scale=1.0 / a.slow)
uA = lambda: dev.read() * 1e6

if a.terminal:
    stop = False
    def show():
        while not stop:
            v = uA()
            bar = "█" * int((v - p.I0 * 1e6) * 20)
            print(f"\rID = {v:5.2f} μA  {bar:<60}", end="", flush=True)
            time.sleep(0.05)
    threading.Thread(target=show, daemon=True).start()
    print(f"Enter = 펄스(4 V, V_TG {a.vtg} V), q+Enter = 종료")
    try:
        while input() != "q":
            dev.pulse(4.0, vtg=a.vtg)
    except EOFError:
        pass
    stop = True
else:
    import matplotlib.pyplot as plt
    from matplotlib.animation import FuncAnimation
    ts, ys, t0 = [], [], time.perf_counter()
    fig, ax = plt.subplots(figsize=(8, 4))
    line, = ax.plot([], [], lw=2)
    ax.set(xlabel=f"real time (s)  [= device ms × {a.slow:g}/1000]", ylabel="ID (μA)",
           title="space: 4V pulse | 5: 4.5V pulse | r: reset", ylim=(0.8, 5))

    def on_key(e):
        if e.key == " ": dev.pulse(4.0, vtg=a.vtg)
        elif e.key == "5": dev.pulse(4.5, vtg=a.vtg)
        elif e.key == "r": dev.reset()
    fig.canvas.mpl_connect("key_press_event", on_key)

    def update(_):
        now = time.perf_counter() - t0
        ts.append(now); ys.append(uA())
        while ts and ts[0] < now - 60: ts.pop(0); ys.pop(0)
        line.set_data(ts, ys); ax.set_xlim(max(0, now - 60), max(60, now))
        return line,
    _anim = FuncAnimation(fig, update, interval=50, cache_frame_data=False)
    plt.show()
