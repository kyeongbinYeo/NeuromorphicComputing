"""
Source data 엑셀에서 v1 모델에 쓰는 데이터를 CSV로 뽑는다.

    python data/extract_source_data.py <source_data.xlsx>

엑셀은 논문(Nat. Commun. 15, 9147 (2024))의 Source data 파일.
결과 CSV는 이미 data/ 아래에 들어 있으므로 다시 뽑을 때만 실행하면 된다.
모든 값은 SI 단위(s, A, V)로 저장한다.
"""
import csv
import sys
from pathlib import Path

import openpyxl

HERE = Path(__file__).resolve().parent


def _num(x):
    return isinstance(x, (int, float))


def _write(path, header, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _xy(rows, ct, ci, r0=2):
    out = []
    for r in rows[r0:]:
        if ci < len(r) and _num(r[ct]) and _num(r[ci]):
            out.append((float(r[ct]), float(r[ci])))
    return out


def main(xlsx):
    wb = openpyxl.load_workbook(xlsx, data_only=True, read_only=True)
    f3 = list(wb["Fig.3"].iter_rows(values_only=True))
    f4 = list(wb["Fig.4"].iter_rows(values_only=True))

    # Fig.3f: single 100 us PGM pulse, then read at V_read = 0 V, V_DS = 0.1 V
    for v, c in zip(("3.5", "4.0", "4.5"), (23, 24, 25)):
        _write(HERE / "relaxation" / f"fig3f_vpgm_{v}V.csv", ["t_s", "id_A"], _xy(f3, 22, c))

    # Fig.3g: 4.0 V / 100 us pulses every ~1.1 ms with constant V_TG
    for v, c in zip(range(6), range(28, 34)):
        _write(HERE / "tg_modulation" / f"fig3g_vtg_{v}V.csv", ["t_s", "id_A"], _xy(f3, 27, c))

    # Fig.3h / 3i / 3j: reservoir states; column order = binary count, first bit = first timeframe
    def block(r0, n_pulse, n_seq, n_bits):
        out = []
        for s in range(n_seq):
            bits = format(s, f"0{n_bits}b")
            for k in range(n_pulse):
                out.append((bits, k, float(f3[r0 + k][36 + s])))
        return out

    _write(HERE / "bg_update" / "fig3h_states.csv", ["bits", "pulse_number", "id_A"], block(2, 5, 16, 4))
    _write(HERE / "tg_modulation" / "fig3i_states.csv", ["bits", "pulse_number", "id_A"], block(10, 5, 16, 4))
    _write(HERE / "tg_modulation" / "fig3j_states.csv", ["bits", "pulse_number", "id_A"], block(18, 6, 32, 5))

    # Fig.4b: LIF excitation, V_BG 0 -> 2.5 V, 500 us, delay 10 us, 30 + 30 pulses, t_reset 3 ms
    _write(HERE / "lif_excitation" / "fig4b.csv", ["t_s", "id_A"], _xy(f4, 0, 1))
    # Fig.4c, V_base = 0 V curve: same protocol as Fig.4b, separate measurement (hold-out)
    _write(HERE / "lif_excitation" / "fig4c_vbase_0V.csv", ["t_s", "id_A"], _xy(f4, 5, 6))

    # Fig.4e: 1 inhibitory pulse, t_width,inh = 500 us, V_inh = 1..5 V (characterization only)
    for v, c in zip(range(1, 6), range(25, 35, 2)):
        _write(HERE / "tg_inhibition" / f"fig4e_vinh_{v}V.csv", ["t_s", "id_A"], _xy(f4, c, c + 1))
    # Fig.4f: 1 inhibitory pulse, V_inh = 3.0 V, widths 10/50/100/500 us (characterization only)
    for w, c in zip((10, 50, 100, 500), range(36, 44, 2)):
        _write(HERE / "tg_inhibition" / f"fig4f_width_{w}us.csv", ["t_s", "id_A"], _xy(f4, c, c + 1))
    # Fig.4g: N inhibitory pulses, V_inh = 5.0 V, 100 us, delay 10 us  (v1 calibration)
    for n, c in zip(range(1, 6), range(45, 55, 2)):
        _write(HERE / "tg_inhibition" / f"fig4g_N{n}.csv", ["t_s", "id_A"], _xy(f4, c, c + 1))

    print("CSV files written under", HERE)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "source_data.xlsx")
