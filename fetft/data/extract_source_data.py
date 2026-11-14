"""Extract Fig.2f and 2g from the original XLSX, checking study transcription.

Usage: python fetft/data/extract_source_data.py [path_to_source_data.xlsx]
Requires openpyxl. Voltage/read conditions come from the paper, not XLSX.
"""
from __future__ import annotations

import csv
import json
import sys
from decimal import Decimal
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
DEFAULT_SOURCE = ROOT / 'references' / 'Analog reservoir computing via ferroelectric_Source data.xlsx'


def extract(source=DEFAULT_SOURCE):
    workbook = openpyxl.load_workbook(source, read_only=True, data_only=True)
    try:
        rows = list(workbook['Fig.2'].iter_rows(min_row=3, max_row=802, values_only=True))
    finally:
        workbook.close()
    f = [(r[8], r[9]) for r in rows[:32]]
    g = [(r[11], r[12]) for r in rows]
    if [p for p, _ in f] != list(range(1, 33)) or [p for p, _ in g] != list(range(1, 801)):
        raise ValueError('Unexpected Fig.2 pulse numbers')
    study = json.loads((ROOT / 'study' / 'configs' / 'demo.json').read_text(encoding='utf-8'))['fetft']
    transcribed = study['ltp_conductance_S'] + study['ltd_conductance_S'][1:]
    if [x for _, x in f] != transcribed:
        raise ValueError('Fig.2f source and study transcription differ')
    with (HERE / 'fig2f_protocol.csv').open('w', encoding='utf-8', newline='') as out:
        wr = csv.writer(out)
        wr.writerow(['pulse_number', 'operation', 'pulse_voltage_V', 'pulse_width_s',
                     'conductance_before_S', 'conductance_after_S', 'delta_conductance_S',
                     'read_vgs_V', 'read_vds_V'])
        for i, (pulse, value) in enumerate(f):
            v = Decimal('3.50') + Decimal('.04') * i if i < 16 else Decimal('-4.35') - Decimal('.05') * (i - 16)
            before = '' if i == 0 else str(Decimal(str(f[i-1][1])))
            delta = '' if i == 0 else str(Decimal(str(value)) - Decimal(before))
            wr.writerow([pulse, 'PGM' if i < 16 else 'ERS', str(v), '0.00001', before,
                         str(value), delta, '1.0', '0.1'])
    with (HERE / 'fig2g_cycles.csv').open('w', encoding='utf-8', newline='') as out:
        wr = csv.writer(out)
        wr.writerow(['pulse_number', 'cycle_block', 'pulse_in_block', 'conductance_S', 'scope'])
        for pulse, value in g:
            wr.writerow([pulse, (pulse - 1) // 32 + 1, (pulse - 1) % 32 + 1,
                         str(value), 'paper_20_cycles' if pulse <= 640 else 'extra_uninterpreted'])
    print('Fig.2f: 32 points, exact study match; Fig.2g: 800 points (640 + 160).')


if __name__ == '__main__':
    extract(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE)
