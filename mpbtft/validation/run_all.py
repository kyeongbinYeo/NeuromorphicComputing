"""
모든 검증을 실행하고 validation/results/metrics.json, *.png, metric_summary.md 를 만든다.

    python validation/run_all.py
"""
from __future__ import annotations

import json

import vcommon
import validate_fig3f
import validate_fig3h
import validate_fig3i
import validate_fig3j
import validate_lif_excitation
import validate_state_dependence
import validate_tg_inhibition
from reservoir_states import validate as validate_states

_ = (validate_fig3h, validate_fig3i, validate_fig3j)


def summary_md(m):
    def r(x):
        return f"{x:.3f}"
    rows = [
        ("Fig.3h, 4-bit, TG 없음", "fit", r(m["fig3h"]["all_points_uA"]["rmse"]), r(m["fig3h"]["final_state_uA"]["rmse"]),
         r(m["fig3h"]["final_state_rank_correlation"])),
        ("Fig.3i, 4-bit, TG 5→3→1.5→0 V", "fit (TG 배율만)", r(m["fig3i"]["all_points_uA"]["rmse"]),
         r(m["fig3i"]["final_state_uA"]["rmse"]), r(m["fig3i"]["final_state_rank_correlation"])),
        ("Fig.3j, 5-bit, TG 1→5→3→2→0 V", "**hold-out**", r(m["fig3j"]["all_points_uA"]["rmse"]),
         r(m["fig3j"]["final_state_uA"]["rmse"]), r(m["fig3j"]["final_state_rank_correlation"])),
    ]
    lif = m["lif_excitation"]
    lines = [
        "# Validation metric summary (MPBTFT v1)",
        "",
        "자동 생성: `python validation/run_all.py`. 단위 uA. 자세한 값은 `metrics.json`.",
        "",
        "## Reservoir",
        "| 데이터 | 역할 | 전체 RMSE | 마지막 상태 RMSE | 마지막 상태 순위 상관 |",
        "|---|---|---|---|---|",
    ] + [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in rows] + [
        "",
        f"- Fig.3f 감쇠 모양(정규화) R²: 4.0 V {m['fig3f']['normalized_shape']['4.0']['r2']:.3f}, "
        f"4.5 V {m['fig3f']['normalized_shape']['4.5']['r2']:.3f}",
        f"- Fig.3f 절대값 RMSE {m['fig3f']['absolute_4p0V_uA']['rmse']:.3f} (3f와 3h는 다른 측정 — 소자 간 차이)",
        f"- 펄스 효과(pair jump) RMSE: 3h {m['state_dependence']['fig3h']['pair_jump_uA']['rmse']:.3f}, "
        f"3i {m['state_dependence']['fig3i']['pair_jump_uA']['rmse']:.3f}, "
        f"3j {m['state_dependence']['fig3j']['pair_jump_uA']['rmse']:.3f}",
        "",
        "## LIF",
        "| 데이터 | 역할 | 펄스 중 전류 RMSE | self-reset RMSE | 첫 발화 펄스 (data / model) |",
        "|---|---|---|---|---|",
        f"| Fig.4b | fit | {r(lif['fig4b_fit']['envelope_uA']['rmse'])} | {r(lif['fig4b_fit']['self_reset_uA']['rmse'])} | "
        f"{lif['fig4b_fit']['first_fire_pulse_index_data']} / {lif['fig4b_fit']['first_fire_pulse_index_model']} |",
        f"| Fig.4c V_base 0 V | **hold-out** | {r(lif['fig4c_vbase0_holdout']['envelope_uA']['rmse'])} | "
        f"{r(lif['fig4c_vbase0_holdout']['self_reset_uA']['rmse'])} | "
        f"{lif['fig4c_vbase0_holdout']['first_fire_pulse_index_data']} / {lif['fig4c_vbase0_holdout']['first_fire_pulse_index_model']} |",
        f"| Fig.4g 첫 펄스열 (N=1) | **hold-out, 다른 소자 상태** | {r(lif['fig4g_train1_holdout']['N1']['rmse'])} | — | — |",
        "",
        f"- Supp. Fig.18 경향 (t_reset 짧을수록 적은 펄스로 발화): {lif['trend_checks_pass']['shorter_reset_fires_with_fewer_or_equal_pulses']}",
        f"- Supp. Fig.19 경향 (지연 길수록 적분 감소): {lif['trend_checks_pass']['longer_delay_less_integration']}"
        f" — 0.5 ms: 모델 {lif['trend_supp_fig19_pulse_delay']['delay_0.5ms']['last_pulse_uA']:.2f} / 그림 약 4.9,"
        f" 1.0 ms: 모델 {lif['trend_supp_fig19_pulse_delay']['delay_1ms']['last_pulse_uA']:.2f} / 그림 약 4.6",
        "",
        "## TG inhibition (experimental)",
        f"- 기본 설정에서 막힘: {m['tg_inhibition']['blocked_without_allow_experimental']}",
        f"- allow_experimental=True에서 I_D+ < I_D−: {m['tg_inhibition']['id_post_less_than_id_pre_in_domain']}"
        f" ({m['tg_inhibition']['n_checked_states']} 상태)",
        f"- Fig.4g N=5 − N=1, 두 번째 펄스열 첫 펄스: 데이터 "
        f"{m['tg_inhibition']['fig4g_second_train_differences']['N5_minus_N1']['data_first_pulse_uA']:.3f}, 모델 "
        f"{m['tg_inhibition']['fig4g_second_train_differences']['N5_minus_N1']['model_first_pulse_uA']:.3f} → 재현 못 함",
    ]
    return "\n".join(lines) + "\n"


def main():
    if vcommon.METRICS.exists():
        vcommon.METRICS.unlink()
    validate_fig3f.main()
    validate_state_dependence.main()
    for n in ("fig3h", "fig3i", "fig3j"):
        validate_states(n)
    validate_lif_excitation.main()
    validate_tg_inhibition.main()
    m = json.loads(vcommon.METRICS.read_text(encoding="utf-8"))
    (vcommon.RESULTS / "metric_summary.md").write_text(summary_md(m), encoding="utf-8")
    print("\n" + summary_md(m))


if __name__ == "__main__":
    main()
