# Validation metric summary (MPBTFT v1)

자동 생성: `python validation/run_all.py`. 단위 uA. 자세한 값은 `metrics.json`.

## Reservoir
| 데이터 | 역할 | 전체 RMSE | 마지막 상태 RMSE | 마지막 상태 순위 상관 |
|---|---|---|---|---|
| Fig.3h, 4-bit, TG 없음 | fit | 0.035 | 0.043 | 0.997 |
| Fig.3i, 4-bit, TG 5→3→1.5→0 V | fit (TG 배율만) | 0.061 | 0.072 | 0.997 |
| Fig.3j, 5-bit, TG 1→5→3→2→0 V | **hold-out** | 0.087 | 0.064 | 0.995 |

- Fig.3f 감쇠 모양(정규화) R²: 4.0 V 0.990, 4.5 V 0.997
- Fig.3f 절대값 RMSE 0.091 (3f와 3h는 다른 측정 — 소자 간 차이)
- 펄스 효과(pair jump) RMSE: 3h 0.042, 3i 0.082, 3j 0.110

## LIF
| 데이터 | 역할 | 펄스 중 전류 RMSE | self-reset RMSE | 첫 발화 펄스 (data / model) |
|---|---|---|---|---|
| Fig.4b | fit | 0.025 | 0.047 | [28, 25] / [27, 27] |
| Fig.4c V_base 0 V | **hold-out** | 0.091 | 0.226 | [None, None] / [27, 27] |
| Fig.4g 첫 펄스열 (N=1) | **hold-out, 다른 소자 상태** | 0.434 | — | — |

- Supp. Fig.18 경향 (t_reset 짧을수록 적은 펄스로 발화): True
- Supp. Fig.19 경향 (지연 길수록 적분 감소): True — 0.5 ms: 모델 4.79 / 그림 약 4.9, 1.0 ms: 모델 4.77 / 그림 약 4.6

## TG inhibition (experimental)
- 기본 설정에서 막힘: True
- allow_experimental=True에서 I_D+ < I_D−: True (71 상태)
- Fig.4g N=5 − N=1, 두 번째 펄스열 첫 펄스: 데이터 -0.478, 모델 -0.030 → 재현 못 함
