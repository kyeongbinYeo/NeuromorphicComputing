"""Analyze the paper's 20 cycles; retain the extra 160 points separately."""
from __future__ import annotations

import csv
import json
import math
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def analyze():
    with (ROOT / 'fetft/data/fig2g_cycles.csv').open(encoding='utf-8', newline='') as f:
        rows = list(csv.DictReader(f))
    if len(rows) != 800 or any(int(r['pulse_number']) != i + 1 for i, r in enumerate(rows)):
        raise ValueError('Fig.2g must contain sequential pulses 1..800')
    if any(r['scope'] != ('paper_20_cycles' if i < 640 else 'extra_uninterpreted') for i, r in enumerate(rows)):
        raise ValueError('Fig.2g scope labels do not match the 640/160 split')
    values = [float(r['conductance_S']) for r in rows[:640]]
    blocks = [values[i:i+32] for i in range(0, 640, 32)]
    per_index = []
    for i in range(32):
        sample = [block[i] for block in blocks]
        mean = statistics.fmean(sample)
        sd = statistics.pstdev(sample)
        per_index.append({'pulse_in_cycle': i + 1, 'mean_S': mean, 'sigma_population_S': sd,
                          'cv_population': sd / mean,
                          'cycle_20_minus_cycle_1_S': sample[-1] - sample[0]})
    rmse = math.sqrt(statistics.fmean((b-a)**2 for a, b in zip(blocks[0], blocks[-1])))
    cvs = [r['cv_population'] for r in per_index]
    return {'scope': 'first 640 points, 20 blocks of 32; Fig.2g variability reference',
            'extra_points': 160, 'extra_point_interpretation': 'unknown; excluded from statistics',
            'cycle_1_vs_20_rmse_S': rmse, 'cv_min': min(cvs), 'cv_max': max(cvs),
            'per_pulse_index': per_index}


if __name__ == '__main__':
    result = analyze()
    out = ROOT / 'fetft/validation/results'
    out.mkdir(parents=True, exist_ok=True)
    (out / 'fig2g_variability.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))
