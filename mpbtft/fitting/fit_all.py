"""
모든 피팅을 순서대로 실행하고 params/v1_params.json 과 fitting/results/*.json 을 만든다.

    python fitting/fit_all.py

순서: Fig.3f 감쇠(특성화) → reservoir BG 표 + 감쇠 → TG 변조 → LIF 흥분 + leak → TG 억제(experimental)
엑셀 없이 data/ 의 CSV만 쓴다. 무작위 요소가 없어 같은 CSV면 같은 숫자가 나온다.
"""
from __future__ import annotations

import json

import fit_bg_update
import fit_lif_excitation
import fit_relaxation
import fit_tg_inhibition
import fit_tg_modulation
from common import ROOT
from template import starting_params

RESULTS = ROOT / "fitting" / "results"


def provenance(reports):
    bg, tg, lif, inh = reports["bg_update"], reports["tg_modulation"], reports["lif_excitation"], reports["tg_inhibition"]
    return {
        "paper": "Analog reservoir computing via ferroelectric mixed phase boundary transistors, "
                 "Nat. Commun. 15, 9147 (2024), doi:10.1038/s41467-024-53321-2",
        "source_data_file": "Analog reservoir computing via ferroelectric_Source data.xlsx (sheets Fig.3, Fig.4) "
                            "→ data/*.csv via data/extract_source_data.py",
        "reservoir.baseline_A": {"figure": "Fig.3h/3i/3j pulse number 0", "method": "mean (measured)",
                                 "data": ["data/bg_update/fig3h_states.csv", "data/tg_modulation/fig3i_states.csv",
                                          "data/tg_modulation/fig3j_states.csv"]},
        "reservoir.relaxation": {"figure": "Fig.3h (16x5 states) + Fig.3f 4.0/4.5 V decay shape",
                                 "method": "joint least squares with reservoir.bg_update; tau_slow is a PCHIP table "
                                           "over post-event excess current",
                                 "script": "fitting/fit_bg_update.py",
                                 "fig3f_shape_rmse": bg["fig3f_shape_rmse"]},
        "reservoir.bg_update.delta_id_A": {"figure": "Fig.3h", "method": "PCHIP table over I_D before the pulse, "
                                           "constrained non-increasing, fitted jointly",
                                           "script": "fitting/fit_bg_update.py",
                                           "fig3h_fit_rmse_uA": bg["fig3h_fit_rmse_uA"]},
        "reservoir.tg_modulation": {"figure": "Fig.3i (TG 5.0/3.0/1.5/0 V schedule)",
                                    "method": "multiplicative gain M(V_TG), M(0)=1, PCHIP; device fixed",
                                    "script": "fitting/fit_tg_modulation.py",
                                    "fig3i_fit_rmse_uA": tg["fig3i_fit_rmse_uA"],
                                    "hold_out": "Fig.3j (validation/validate_fig3j.py)"},
        "lif.baseline_A": {"figure": "Fig.4b", "method": "mean rest current before the first train (measured)"},
        "lif.relaxation + lif.bg_update + lif.on_state_offset_A": {
            "figure": "Fig.4b (envelope of 60 pulses + two self-reset curves)",
            "method": "joint least squares; on-state current = rest current + constant offset (assumption)",
            "script": "fitting/fit_lif_excitation.py",
            "fig4b_envelope_rmse_uA": lif["fig4b_envelope_rmse_uA"],
            "fig4b_self_reset_rmse_uA": lif["fig4b_self_reset_rmse_uA"],
            "hold_out": "Fig.4c V_base = 0 V, Fig.4g first train (validation/validate_lif_excitation.py)"},
        "lif.tg_inhibition": {"figure": "Fig.4g (N = 1..5, 5.0 V, 100 us)",
                              "method": "best-fit retention from N-vs-N=1 differences of the second train",
                              "status": inh["status"], "enabled_by_default": False,
                              "identifiability": inh["identifiability"],
                              "script": "fitting/fit_tg_inhibition.py"},
        "constants_from_paper_text": {
            "V_DS_V": "0.1 (Fig.3, Fig.4 captions)",
            "reservoir_pulse": "4.0 V, 100 us, timeframe 3 ms (Fig.3h-j captions)",
            "fig3i_tg_schedule_V": "[5.0, 3.0, 1.5, 0.0] (Fig.3i drawing)",
            "fig3j_tg_schedule_V": "[1.0, 5.0, 3.0, 2.0, 0.0] (Fig.3j drawing)",
            "lif_excitation": "2.5 V, 500 us, delay 10 us, TG baseline -3.0 V (Fig.4a,b)",
            "lif_inhibition": "5.0 V, 100 us, delay 10 us (Fig.4g)",
            "lif_I_th": "5.83 uA read from the Fig.4b dashed line (lif.py FIG4B_ITH_A)",
            "read_delay_after_pulse": "0.2 ms (assumption: first Fig.3f sample)",
        },
    }


def main():
    RESULTS.mkdir(parents=True, exist_ok=True)
    reports = {}
    reports["relaxation_fig3f"] = fit_relaxation.fit()
    params = starting_params()
    params, reports["bg_update"] = fit_bg_update.fit(params)
    params, reports["tg_modulation"] = fit_tg_modulation.fit(params)
    params, reports["lif_excitation"] = fit_lif_excitation.fit(params)
    params, reports["tg_inhibition"] = fit_tg_inhibition.fit(params)
    params.provenance = provenance(reports)
    params.save()
    for k, v in reports.items():
        (RESULTS / f"{k}.json").write_text(json.dumps(v, indent=2, ensure_ascii=False), encoding="utf-8")
    print("params/v1_params.json written")
    print(f"  Fig.3h fit RMSE        {reports['bg_update']['fig3h_fit_rmse_uA']:.3f} uA")
    print(f"  Fig.3i fit RMSE        {reports['tg_modulation']['fig3i_fit_rmse_uA']:.3f} uA")
    print(f"  Fig.4b envelope RMSE   {reports['lif_excitation']['fig4b_envelope_rmse_uA']:.3f} uA")
    print(f"  Fig.4b self-reset RMSE {reports['lif_excitation']['fig4b_self_reset_rmse_uA']:.3f} uA")
    print(f"  TG inhibition retention (experimental, off by default) "
          f"{reports['tg_inhibition']['retention_best_fit']:.3f}")


if __name__ == "__main__":
    main()
