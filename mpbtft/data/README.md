# data — 출처와 처리 기록

원본: 논문 Source data `Analog reservoir computing via ferroelectric_Source data.xlsx`
(Nat. Commun. 15, 9147 (2024)). `extract_source_data.py`가 시트 `Fig.3`, `Fig.4`에서 값만 읽어 CSV로 저장한다.

- 모든 CSV는 **source_data** (디지타이즈 없음). 단위 SI: 시간 s, 전류 A.
- 그림 라벨(전압, 순서)은 엑셀에 없어 본문 그림 범례·캡션에서 정했다 (아래 표 "라벨 근거").
- 보간: 모델 표는 모두 PCHIP (`parameters.Table`), 표 범위 밖은 외삽하지 않음.

## provenance

| 파일 | 그림 | 엑셀 위치 (0부터 센 열) | 조건 | 라벨 근거 | 쓰는 곳 |
|---|---|---|---|---|---|
| `relaxation/fig3f_vpgm_{3.5,4.0,4.5}V.csv` | Fig.3f | 열 22 시간, 23/24/25 I_D | 100 μs PGM 1개 후 감쇠, V_DS 0.1 V | 범례 3.5/4.0/4.5 V (전류 큰 순서와 일치) | `fit_relaxation.py`, `fit_bg_update.py` (모양), `validate_fig3f.py` |
| `bg_update/fig3h_states.csv` | Fig.3h | 행 2–6, 열 36–51 | 4.0 V / 100 μs, 3 ms, TG 없음 | 열 순서 = 0000…1111, 첫 비트 = 첫 timeframe (데이터에서 확인) | `fit_bg_update.py`, `validate_fig3h.py` |
| `tg_modulation/fig3i_states.csv` | Fig.3i | 행 10–14, 열 36–51 | + TG 5.0/3.0/1.5/0 V | 그림 상단 TG 펄스 | `fit_tg_modulation.py`, `validate_fig3i.py` |
| `tg_modulation/fig3j_states.csv` | Fig.3j | 행 18–23, 열 36–67 | 5-bit, TG 1.0/5.0/3.0/2.0/0 V | 그림 상단 TG 펄스 | `validate_fig3j.py` (hold-out) |
| `tg_modulation/fig3g_vtg_{0..5}V.csv` | Fig.3g | 열 27 시간, 28–33 I_D | 펄스 간격 약 1.1 ms, TG 일정 | 범례 0–5 V | 참고용 (v1 피팅에 안 씀) |
| `lif_excitation/fig4b.csv` | Fig.4b | 열 0, 1 | 2.5 V / 500 μs, 간격 10 μs, 30+30, t_reset 3 ms, TG −3 V | 그림 상단 | `fit_lif_excitation.py` |
| `lif_excitation/fig4c_vbase_0V.csv` | Fig.4c | 열 5, 6 | 같은 프로토콜, V_base 0 V | 범례 순서 −0.5/0/0.5/1.0/1.5 V | `validate_lif_excitation.py` (hold-out) |
| `tg_inhibition/fig4g_N{1..5}.csv` | Fig.4g | 열 45–54 | 30 펄스 → 억제 N개 (5.0 V / 100 μs, 간격 10 μs) → 13 펄스, t_reset 1 ms | 범례 N = 1…5 | `fit_tg_inhibition.py`, `validate_tg_inhibition.py` |
| `tg_inhibition/fig4e_vinh_{1..5}V.csv` | Fig.4e | 열 25–34 | 억제 1개, 500 μs | 범례 1–5 V | 경향 기록만 (지원 조건 아님) |
| `tg_inhibition/fig4f_width_{10,50,100,500}us.csv` | Fig.4f | 열 36–43 | 억제 1개, 3.0 V | 범례 | 경향 기록만 |

Fig.4d V_high 2.5 V 곡선(열 20, 21)은 Fig.4b와 값이 완전히 같아 따로 저장하지 않았다.

## 처리 규칙

- **LIF 펄스 중 전류(envelope)**: 펄스 k 시작 = 펄스열 시작 + k × 510 μs. 펄스 끝 직전 15–110 μs 구간의 중앙값.
- **펄스열 시작**: I_D > 2.5 μA인 첫 샘플 − 5 μs (샘플 간격 10 μs).
- **억제 직전·직후 I_D**: Fig.4e–g에서 첫 펄스열 뒤 1 ms 구간 값이 0 A로 비어 있어 **얻을 수 없다**.
- **Fig.3h–j 읽기 시각**: 엑셀에 없다. 펄스 끝 0.2 ms 뒤로 가정 (Fig.3f 첫 샘플 시점).
- Supp. Fig.11, 12, 13, 18, 19: Source data에 없음. v1에서는 디지타이즈하지 않았고, Fig.18/19는 캡션 서술과
  그림에서 읽은 대략값(±0.1 μA)으로 경향만 비교한다 (`validate_lif_excitation.py`).
