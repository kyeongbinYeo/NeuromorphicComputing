"""Run from the project root: python plot_results.py [--no-show]."""
import argparse
import csv
import itertools
import json
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--no-show', action='store_true', help='Save figures without opening windows')
args = parser.parse_args()
import matplotlib
if args.no_show:
    matplotlib.use('Agg')
import matplotlib.pyplot as plt
from models.devices import MPBTFT

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'outputs'
required = ['fetft_demo.csv', 'mpbtft_demo.csv', 'run_config.json']
if not all((OUT / f).exists() for f in required):
    raise SystemExit('Run python demo.py first, then python plot_results.py.')
config = json.loads((OUT / 'run_config.json').read_text(encoding='utf-8'))
if config.get('metadata', {}).get('status') != 'SYNTHETIC_DEMO_NOT_CALIBRATED':
    raise SystemExit('This plot script expects the original synthetic demo schema. Review before using fitted data.')
FIGS = OUT / 'figures'
FIGS.mkdir(exist_ok=True)
plt.rcParams.update({'font.size': 10, 'axes.spines.top': False,
                     'axes.spines.right': False, 'figure.dpi': 120})
BLUE, RED = '#2463A6', '#CF6548'

def rows(name):
    with (OUT / name).open(newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def save(fig, name):
    fig.text(.5, .015, 'SYNTHETIC DEMO | illustrative parameters; not paper reproduction',
             ha='center', fontsize=9, color='#9A462F')
    fig.tight_layout(rect=(0, .055, 1, .96))
    fig.savefig(FIGS / (name + '.png'), dpi=220)
    fig.savefig(FIGS / (name + '.svg'))
    if args.no_show:
        plt.close(fig)

# 1. Measured-protocol-style plot: distinct LTP and LTD initializations.
fe = rows('fetft_demo.csv')
fig, axs = plt.subplots(1, 2, figsize=(9, 3.8))
for branch, color in [('ltp', BLUE), ('ltd', RED)]:
    r = [x for x in fe if x['branch'] == branch]
    n = [int(x['pulse_index']) for x in r]
    axs[0].plot(n, [float(x['conductance_S'])*1e6 for x in r], 'o-', color=color, label=branch.upper())
    axs[1].plot(n, [float(x['current_A'])*1e6 for x in r], 'o-', color=color, label=branch.upper())
for ax in axs:
    ax.set_xlabel('Pulse index (0 = initial state)')
    ax.set_xticks(n)
    ax.grid(alpha=.2)
    ax.legend()
axs[0].set_ylabel('Conductance (uS)')
axs[1].set_ylabel('Read current (uA)')
fig.suptitle('FeTFT | LTP and LTD protocol replay (separate initial states)')
save(fig, '01_fetft_ltp_ltd')

# 2. Plot saved current traces, reconstruct the exact input slots from run config.
mp = rows('mpbtft_demo.csv')
p = config['protocol']
width = config['mpbtft']['reference_width_s']
slot = width + p['gap_s']
fig, axs = plt.subplots(3, 1, figsize=(9, 7), sharex=True,
                        gridspec_kw={'height_ratios': [1, 1, 2]})
for idx, (bit, tg) in enumerate(zip(p['bits'], p['tg_V'])):
    start, end = idx*slot*1e3, (idx*slot+width)*1e3
    axs[0].plot([start, start, end, end], [0, 4*bit, 4*bit, 0], color=BLUE)
    axs[1].plot([start, start, end, end], [0, tg, tg, 0], color=RED)
    axs[0].text(start+slot*1e3/2, 4.5, str(bit), ha='center')
    for ax in axs:
        ax.axvspan(start, end, color='grey', alpha=.09)
for condition, label, color in [('no_tg', 'Without TG', BLUE), ('tg', 'With TG', RED)]:
    r = [x for x in mp if x['condition'] == condition]
    axs[2].plot([float(x['time_s'])*1e3 for x in r],
                [float(x['current_A'])*1e6 for x in r], color=color, label=label)
axs[0].set_ylim(-.3, 5.3)
axs[0].set_ylabel('BG (V)')
axs[1].set_ylabel('TG (V)\nTG condition')
axs[2].set_ylabel('Read current (uA)')
axs[2].set_xlabel('Time (ms)')
axs[2].legend()
for ax in axs: ax.grid(alpha=.2)
fig.suptitle('MPBTFT | input ' + ''.join(map(str, p['bits'])) + ' and current response')
save(fig, '02_mpbtft_input_response')

# 3. Isolate pulse-end decay; time zero here is immediately after pulse end.
d = MPBTFT(config['mpbtft'])
d.pulse(config['mpbtft']['reference_bg_V'], 0, width)
ts, total, fast, slow = [], [], [], []
for k in range(301):
    if k: d.advance(.0001)
    ts.append(k*.1)
    total.append(d.read_current_A()*1e6)
    fast.append(d.fast*1e6)
    slow.append(d.slow*1e6)
fig, ax = plt.subplots(figsize=(8, 4.3))
ax.plot(ts, total, color=BLUE, label='Total current')
ax.plot(ts, fast, '--', color=RED, label='Fast excess component')
ax.plot(ts, slow, '--', color='#6E8A4C', label='Slow excess component')
ax.axhline(config['mpbtft']['baseline_A']*1e6, color='grey', ls=':', label='Baseline')
ax.set(xlabel='Time after pulse end (ms)', ylabel='Current (uA)',
       title='MPBTFT | two-exponential relaxation')
ax.grid(alpha=.2)
ax.legend()
save(fig, '03_mpbtft_decay')

# 4. All 16 words. Final read is at pulse end of the final slot (no final gap).
words = list(itertools.product([0, 1], repeat=4))
values = {'no_tg': [], 'tg': []}
for use_tg in (False, True):
    for bits in words:
        d = MPBTFT(config['mpbtft'])
        for i, bit in enumerate(bits):
            if bit: d.pulse(4, p['tg_V'][i] if use_tg else 0, width)
            else: d.advance(width)
            if i < 3: d.advance(p['gap_s'])
        values['tg' if use_tg else 'no_tg'].append(d.read_current_A()*1e6)
fig, ax = plt.subplots(figsize=(10, 4.5))
for key, color, label in [('no_tg', BLUE, 'Without TG'), ('tg', RED, 'With TG')]:
    ax.plot(range(16), values[key], 'o-', color=color, label=label)
ax.set_xticks(range(16), [''.join(map(str, b)) for b in words], rotation=55)
ax.set(xlabel='4-bit input word', ylabel='Final read current (uA)',
       title='MPBTFT | 16 input words, each starting from reset')
ax.grid(alpha=.2)
ax.legend()
save(fig, '04_mpbtft_final_states')
with (FIGS / 'final_states_synthetic.csv').open('w', newline='', encoding='utf-8') as f:
    w = csv.writer(f)
    w.writerow(['status', 'input_word', 'no_tg_current_A', 'tg_current_A'])
    for i, bits in enumerate(words):
        w.writerow(['synthetic_demo', ''.join(map(str,bits)), values['no_tg'][i]*1e-6, values['tg'][i]*1e-6])
(FIGS / 'figure_config.json').write_text(json.dumps(config, indent=2), encoding='utf-8')
print('Saved 4 synthetic-demo figures (PNG + SVG) in outputs/figures/.')
if not args.no_show: plt.show()
