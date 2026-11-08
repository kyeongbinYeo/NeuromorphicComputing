import csv
import json
from pathlib import Path
from models.devices import FeTFT, MPBTFT

ROOT = Path(__file__).resolve().parent
c = json.loads((ROOT / 'configs/demo.json').read_text())
out = ROOT / 'outputs'
out.mkdir(exist_ok=True)
fe = FeTFT(c['fetft'])
with (out / 'fetft_demo.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['status', 'branch', 'pulse_index', 'conductance_S', 'current_A'])
    for branch in ['ltp', 'ltd']:
        fe.reset(branch)
        for n in range(len(c['fetft'][branch + '_conductance_S'])):
            if n: fe.apply_next_protocol_pulse()
            writer.writerow(['synthetic_demo', branch, n, fe.g, fe.read_current_A()])
with (out / 'mpbtft_demo.csv').open('w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['status', 'condition', 'time_s', 'bit', 'tg_V', 'current_A'])
    for use_tg in [False, True]:
        mp, t = MPBTFT(c['mpbtft']), 0.0
        for bit, tg in zip(c['protocol']['bits'], c['protocol']['tg_V']):
            tg = tg if use_tg else 0.0
            # A zero bit occupies the same slot duration, but applies no pulse.
            if bit: mp.pulse(4.0, tg, 100e-6)
            else: mp.advance(100e-6)
            t += 100e-6
            writer.writerow(['synthetic_demo', 'tg' if use_tg else 'no_tg', t, bit, tg, mp.read_current_A()])
            for _ in range(30):
                mp.advance(c['protocol']['gap_s'] / 30)
                t += c['protocol']['gap_s'] / 30
                writer.writerow(['synthetic_demo', 'tg' if use_tg else 'no_tg', t, bit, tg, mp.read_current_A()])
(out / 'run_config.json').write_text(json.dumps(c, indent=2))
print('SYNTHETIC DEMO ONLY. CSV and run configuration saved in outputs/.')
