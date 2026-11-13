# MPBTFT 모델 v0 → v1 수정 정리

- 날짜: 2026-11-13
- 근거 문서: `docs/MPBTFT_v1_model_specification_revised.md`(v1 사양서), `docs/MPBTFT_input_output_characteristics.pdf`(입출력 정리)
- 대상 논문: *Analog reservoir computing via ferroelectric mixed phase boundary transistors*, Nat. Commun. 15, 9147 (2024)

---

## 1. 왜 바꿨나

v0는 reservoir 모드(Fig.3)만 다뤘고, 파일 하나(`mpbtft.py`)에 모델·파라미터·시간 처리가 섞여 있었다.
v1 사양서가 요구하는 다음 항목을 맞추기 위해 구조를 다시 짰다.

| 사양서 요구 | v0 | v1 |
|---|---|---|
| 하나의 클래스로 Reservoir + LIF | Reservoir만 | `MPBTFT(mode="reservoir" / "lif")` |
| 입력: 절대 시각 + gate event | `advance(dt)`로 시간을 직접 진행 | `apply_bg_pulse(time_s, ...)`, `read_current(time_s)` |
| read는 상태를 바꾸지 않음 | `read()`가 시계를 동기화하며 상태 갱신 | 순수 관측 (같은 시각 = 같은 값) |
| 지원 안 되는 입력은 오류 | 범위 밖 V_TG·V_PGM은 끝값으로 조용히 계산 | `UnsupportedOperatingPointError` |
| 외삽 금지 | 제한 없음 | 펄스 직전 I_D가 보정 범위 밖이면 `OutOfCalibratedStateError` |
| 펄스 겹침·도중 읽기·시간 역행 오류 | 검사 없음 | `ValueError` |
| BG 증가가 현재 I_D에 의존 | k·(Isat − I_D) 식 하나 | PCHIP 표, 단조 비증가 |
| 감쇠 파라미터가 상태에 의존 | 고정 τ + β 보정 | τ_slow 표 (사건 직후 초과 전류 기준) |
| 발화는 core 밖 | 해당 없음 | `LIFNeuron` (lif.py) |
| 파라미터 출처 기록 | 문서에만 | `params/v1_params.json`의 `provenance` + `data/README.md` |
| 단위 테스트 | 없음 | 39개 |

---

## 2. 파일이 어디로 갔나

v0 파일은 v1 파일로 **대체**되었다. 원본은 `학회\mpbtft_v0_backup.zip`과 git 커밋 `a35509a`에 남아 있다.

| v0 파일 | v1 |
|---|---|
| `mpbtft.py` | `model.py`(소자), `reservoir.py`(펄스열, Reservoir), `lif.py`(LIF 뉴런, 신규) |
| `params.json` | `params/v1_params.json` |
| `fit_from_paper.py` | `fitting/` 스크립트 6개 (`fit_all.py`로 한 번에 실행) |
| `tg_measure.py`, `tg_measure.json` | `fitting/fit_tg_modulation.py`의 model-free 배율 검사 |
| `tg_test_fig3j.py`, `tg_test_report.json`, `tg_test_fig3j.png` | `validation/validate_fig3j.py` |
| `fit_report.json`, `fit_fig3.png` | `fitting/results/*.json`, `validation/results/*.png` |
| `realtime_demo.py`, `telemetry_reservoir.py`, `continuous_state.py` | `examples/` (새 API로 수정, LIF 모드 추가) |
| `telemetry.csv` | `examples/telemetry.csv` |
| `MPBTFT_volatile_model_notes.md` | `docs/v0_volatile_model_notes.md` |
| `fig3g_tg_gain.json` | 없음 (Fig.3g는 참고용 CSV로만 보관) |
| 엑셀 `source_data.xlsx` 필요 | 필요 없음. `data/` CSV로 동작 (`data/extract_source_data.py`로 재생성 가능) |

### 새 폴더 구조
```
mpbtft/
├─ model.py, parameters.py, domains.py, reservoir.py, lif.py
├─ params/v1_params.json
├─ data/          Source data에서 뽑은 CSV 28개 + README(출처)
├─ fitting/       fit_relaxation, fit_bg_update, fit_tg_modulation, fit_lif_excitation, fit_tg_inhibition, fit_all
├─ validation/    validate_fig3f/3h/3i/3j, validate_state_dependence, validate_lif_excitation, validate_tg_inhibition, run_all
├─ tests/test_mpbtft.py
├─ examples/      realtime_demo, telemetry_reservoir, continuous_state
└─ docs/          사양서, 입출력 정리, v0 기록
```

---

## 3. 모델에서 바뀐 점

### 공통 구조
```
I_D = baseline + fast + slow        (hidden state: fast, slow, 마지막 확정 시각)
감쇠:   fast·e^(−Δt/τ_fast) + slow·e^(−Δt/τ_slow)   읽을 때 한 번에 계산
BG:     ΔI = F(펄스 직전 I_D) × M(V_TG)            펄스 끝 시각에 확정
```

### Reservoir 모드 (BG 4.0 V / 100 μs, TG 0~5 V)
- BG 증가: v0의 포화식 대신, 펄스 직전 I_D 1.01~2.81 μA에서 정의한 단조 비증가 표 (0.89 → 0.77 μA).
- 감쇠: τ_fast 1.31 ms, τ_slow는 초과 전류 0.5 / 1.5 / 3.0 μA에서 6.3 / 20.9 / 11.6 ms.
  Fig.3h와 Fig.3f(4.0, 4.5 V) 감쇠 모양을 함께 피팅했다.
- TG 배율: Fig.3i로만 피팅 (1.5 / 3 / 5 V → 0.84 / 0.70 / 0.60). Fig.3j는 hold-out으로 남겼다.
  v0는 3h/3i/3j 전부에서 잰 표를 기본값으로 써서 3j가 완전한 hold-out이 아니었다.
- 지원하지 않게 된 것: 3.5 / 4.5 V 펄스 (v0는 Fig.3f 진폭비로 추정 배율을 썼지만 펄스열 데이터가 없음).

### LIF 모드 (신규, BG 2.5 V / 500 μs, TG −3 V)
- Fig.4b로 피팅: baseline 0.063 μA, τ_fast 0.072 ms, τ_slow 0.74 ms, BG 증가 표 0.69 → 0.06 μA.
- 펄스 중 전류 = 휴지 I_D + 4.01 μA (상수 offset 가정). 뉴런은 이 값을 문턱(Fig.4b I_th 5.83 μA)과 비교한다.
- TG 억제(5.0 V / 100 μs): API는 있지만 **기본값에서 꺼져 있음**. 아래 5장 참고.

---

## 4. 검증 결과

| 데이터 | 역할 | 결과 (μA) |
|---|---|---|
| Fig.3h 16×5 | fit | RMSE 0.035, 마지막 상태 순위 상관 0.997 |
| Fig.3i 16×5 | fit (TG 배율 3개만) | RMSE 0.061 |
| Fig.3j 32×6 | **hold-out** | RMSE 0.087, 순위 상관 0.995 (v0 최고 0.091) |
| Fig.3f 감쇠 모양 | fit 일부 | R² 0.990 (4.0 V), 0.997 (4.5 V) |
| 펄스 효과 이력 의존성 | model-free 검사 | 같은 직전 전류면 이력이 달라도 차이 ≤ 0.06 |
| Fig.4b 펄스 중 전류 60개 | fit | RMSE 0.025, self-reset 0.047 |
| Fig.4c V_base 0 V | **hold-out** | RMSE 0.091 |
| Supp. Fig.19 지연 0.5 / 1.0 ms | 경향 (그림값) | 모델 4.79 / 4.77, 그림 약 4.9 / 4.6, 둘 다 발화 안 함 |
| Supp. Fig.18 t_reset 1 / 2 / 3 ms | 경향 | 짧을수록 적은 펄스로 발화 (23 / 26 / 27번째) |
| 단위 테스트 | | 39개 통과, 재피팅 시 파라미터 동일 |

---

## 5. 남은 한계

1. **TG 억제는 보정 불가.** Fig.4e–g Source data는 억제 펄스 전후 1 ms가 0으로 비어 있고, 같은 소자의 억제 없는 대조 측정도 없다.
   Fig.4g에서 N=5와 N=1의 두 번째 펄스열 차이가 데이터는 −0.48 μA, 모델은 −0.03 μA다.
   best-fit retention 0.64는 `MPBTFT(..., allow_experimental=True)`일 때만 쓴다.
2. **`state = I_D` 한계 (LIF).** 휴지 전류는 1 ms 안에 거의 다 빠지는데, 다시 흥분시키면 첫 펄스열보다 높게 시작한다 (Supp. Fig.18a, Fig.4g). 숨은 잔류 상태를 모델이 과소평가한다.
3. **소자 간 차이.** Fig.3f와 3h는 펄스 1개 증가분이 1.4 vs 0.86 μA. Fig.4g 첫 펄스열은 Fig.4b보다 낮게 시작한다 (RMSE 0.43).
4. **TG 변조는 곱셈형 가정.** 피팅 배율(0.84/0.70/0.60)이 데이터 직접 측정(0.77/0.59/0.51)보다 크다.
5. **보정 범위.** TG 0 V로 4.0 V 펄스를 5개 이상 연속으로 주면 오류가 난다.
   line_cnn 로그를 3 ms로 압축하면 펄스 506개 중 439개가 범위 밖이다.
6. **가정.** Fig.3h–j 읽기 시점은 펄스 끝 0.2 ms 뒤, Fig.4g 억제 펄스는 두 번째 펄스열 10 μs 전에 끝난다고 가정했다.

추가로 필요한 데이터: 억제 펄스 직전·직후 휴지 I_D, 같은 소자의 억제 없는 t_reset 1 ms 측정, Fig.3h–j 읽기 시점, Supp. Fig.11 수치.

---

## 6. 코드 사용법 변화

```python
# v0
from mpbtft import MPBTFT, MPBTFTParams
d = MPBTFT(MPBTFTParams.load("params.json"))
d.pulse(4.0, vtg=3.0); d.advance(0.2e-3); d.read()

# v1
from model import MPBTFT
from parameters import MPBTFTParams
d = MPBTFT(MPBTFTParams.load(), mode="reservoir")
d.apply_bg_pulse(time_s=0.0, voltage_V=4.0, width_s=100e-6, tg_voltage_V=3.0)
d.read_current(time_s=0.3e-3)
```

| v0 | v1 |
|---|---|
| `pulse(vpgm, vtg)` | `apply_bg_pulse(time_s, voltage_V, width_s, tg_voltage_V)` |
| `advance(dt)` + `read()` | `read_current(time_s)` |
| `reset()` | `initialize(time_s)` (시뮬레이션용, 물리적 self-reset 아님) |
| `run_train(bits, vtgs=...)` | `reservoir.run_bit_train(device, bits, tg_voltages_V=...)` |
| `MPBTFT(p, clock=time.perf_counter)` | 절대 시각을 직접 넘김 (`examples/realtime_demo.py` 참고) |
| 없음 | `MPBTFT(p, mode="lif")` + `lif.LIFNeuron` |

---

## 7. 실행 명령

```powershell
python -m pip install -r requirements.txt
python -m pytest tests -q              # 39 passed
python fitting/fit_all.py              # 파라미터 재생성 (약 2초)
python validation/run_all.py           # 그림 + metric_summary.md
python examples/telemetry_reservoir.py
python examples/continuous_state.py
python examples/realtime_demo.py --mode lif
```
