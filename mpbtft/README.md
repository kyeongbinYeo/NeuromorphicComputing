# mpbtft — MPBTFT v1 behavioral model

> v0에서 바뀐 점: [CHANGES_v1.md](CHANGES_v1.md)

Volatile Double-Gate MPBTFT를 논문 Source data에 맞춰 만든 Python 모델.
대상 논문: *Analog reservoir computing via ferroelectric mixed phase boundary transistors*, Nat. Commun. 15, 9147 (2024), doi:10.1038/s41467-024-53321-2

```text
Validated
- Reservoir 4.0 V / 100 μs BG mode            (Fig.3h fit RMSE 0.035 μA, Fig.3j hold-out RMSE 0.087 μA)
- TG reservoir modulation within calibrated domain (TG 0–5 V, multiplicative gain)
- Event-driven volatile relaxation             (lazy, read는 상태를 바꾸지 않음)
- LIF representative excitation protocol       (2.5 V / 500 μs, TG −3 V; Fig.4b fit, Fig.4c hold-out)

Limited / Experimental
- TG inhibitory transition (5.0 V / 100 μs) — 데이터로 식별 불가, 기본값에서 꺼져 있음

Not supported
- arbitrary amplitude/width generalization
- extrapolation beyond measured domain (I_D가 보정 범위 밖이면 오류)
- intra-pulse dynamics, overlapping pulses
```

사양: `docs/MPBTFT_v1_model_specification_revised.md`, 입출력 정리: `docs/MPBTFT_input_output_characteristics.pdf`

---

## 1. 설치와 실행 위치

```bash
pip install -r requirements.txt
```
모든 명령은 이 `mpbtft` 폴더에서 실행한다. Windows에서 `python`이 안 되면 `py`로 바꾼다.
엑셀 없이 돌아간다. 필요한 데이터는 `data/` 아래 CSV로 들어 있다.

## 2. 명령어

| 하는 일 | 명령 | 결과 |
|---|---|---|
| 단위 테스트 (39개) | `python -m pytest tests -q` | 통과/실패 |
| 전체 피팅 (약 2초) | `python fitting/fit_all.py` | `params/v1_params.json`, `fitting/results/*.json` |
| 전체 검증 (약 5초) | `python validation/run_all.py` | `validation/results/*.png`, `metrics.json`, `metric_summary.md` |
| 엑셀에서 CSV 다시 뽑기 | `python data/extract_source_data.py <source_data.xlsx>` | `data/**/*.csv` |
| line_cnn 주행 로그 연동 | `python examples/telemetry_reservoir.py` | `examples/telemetry_reservoir.png` |
| 연속 궤적 그림 | `python examples/continuous_state.py` | `examples/continuous_state.png` |
| 실시간 데모 | `python examples/realtime_demo.py [--mode lif] [--vtg 3] [--terminal]` | 그래프 창 / 터미널 |

`params/v1_params.json`은 이미 들어 있으므로 피팅을 다시 돌리지 않아도 모델을 쓸 수 있다.

## 3. 코드에서 쓰기

```python
from model import MPBTFT
from parameters import MPBTFTParams

p = MPBTFTParams.load()                      # params/v1_params.json

# Reservoir: BG 4.0 V / 100 μs, TG는 펄스와 함께 거는 변조 바이어스 (0~5 V)
d = MPBTFT(p, mode="reservoir")
d.apply_bg_pulse(time_s=0.0,   voltage_V=4.0, width_s=100e-6, tg_voltage_V=0.0)
d.apply_bg_pulse(time_s=3e-3,  voltage_V=4.0, width_s=100e-6, tg_voltage_V=3.0)
print(d.read_current(time_s=13e-3))          # 아무 때나 읽기 (A). 같은 시각은 몇 번 읽어도 같은 값
```

```python
from reservoir import run_bit_train, Reservoir, FIG3I_TG_V
d = MPBTFT(p, mode="reservoir")
run_bit_train(d, "1011", tg_voltages_V=FIG3I_TG_V)      # timeframe마다 읽은 I_D 리스트
Reservoir(4, p, tg_voltages_V=FIG3I_TG_V).encode(["1011", "0001", "1111", "0100"])
```

```python
# LIF: 같은 MPBTFT 클래스, 다른 인스턴스. 발화는 LIFNeuron이 한다.
from lif import LIFNeuron
d = MPBTFT(p, mode="lif")
n = LIFNeuron(d)                     # 문턱 = Fig.4b I_th 5.83 μA (threshold_A로 바꿀 수 있음)
n.excite_train(t0_s=0.0, n=30)       # 2.5 V / 500 μs, 간격 10 μs, TG −3 V
print(n.spikes_s)                    # 발화 시각
print(d.read_current(20e-3))         # 휴지 상태 I_D (leak 후)

# TG 억제는 experimental: 명시적으로 허용해야 동작
d2 = MPBTFT(p, mode="lif", allow_experimental=True)
```

| API | 뜻 |
|---|---|
| `MPBTFT(params, mode, time_s=0, strict=True, allow_experimental=False)` | 소자 1개. `strict=False`면 보정 범위 밖 I_D에서 경고 후 가장자리 값 |
| `read_current(time_s)` | 그 시각의 I_D (A). 상태를 바꾸지 않음 |
| `apply_bg_pulse(time_s, voltage_V, width_s, tg_voltage_V)` | BG 펄스. 반환 = 펄스 직후 I_D. `last_event.id_during_pulse_A` = LIF 펄스 중 전류 |
| `apply_tg_inhibition(time_s, voltage_V, width_s)` | LIF 억제 펄스 (experimental) |
| `initialize(time_s)` | 시뮬레이션 초기화. 물리적 self-reset이 아님 |

오류 종류 (`domains.py`)
- `UnsupportedOperatingPointError`: 지원하지 않는 전압·폭·TG·모드 (예: 4.37 V / 73 μs)
- `OutOfCalibratedStateError`: 펄스 직전 I_D가 보정 범위 밖 (reservoir 1.01~2.81 μA, LIF 0.06~2.1 μA)
- `UncalibratedFeatureError`: `allow_experimental` 없이 TG 억제 사용
- `ValueError`: 시간 역행, 펄스 겹침, 펄스 도중 읽기

## 4. 모델 구조

```
I_D = baseline + fast + slow            (hidden state: fast, slow, 마지막 확정 시각)

감쇠    fast·e^(−Δt/τ_fast) + slow·e^(−Δt/τ_slow)    읽을 때 한 번에 계산 (lazy)
        τ_slow는 사건 직후 초과 전류(I_D − baseline)로 표에서 고르고 다음 사건까지 유지
BG     ΔI = F(I_D,pre) × M(V_TG)          F: PCHIP 표, 단조 비증가 / M: reservoir만, M(0)=1
       ΔI를 fast_share : (1 − fast_share)로 나눠 더하고, 펄스 끝 시각에 확정
TG 억제 초과 전류 × retention               LIF만, experimental
LIF 펄스 중 전류 = 휴지 I_D + on_state_offset
```

| 모드 | baseline | τ_fast | τ_slow | BG 증가 ΔI | 기타 |
|---|---|---|---|---|---|
| reservoir | 1.009 μA | 1.31 ms | 6.3 / 20.9 / 11.6 ms (초과 0.5 / 1.5 / 3.0 μA) | 0.89 → 0.77 μA (직전 1.01 → 2.81 μA) | M(1.5/3/5 V) = 0.84 / 0.70 / 0.60 |
| lif | 0.063 μA | 0.072 ms | 0.74 ms | 0.69 → 0.06 μA (직전 0.06 → 2.1 μA) | on_state_offset 4.01 μA |

숫자의 출처는 `params/v1_params.json`의 `provenance`와 `data/README.md`.

## 5. 검증 결과

`validation/results/metric_summary.md` (자동 생성)의 요약. 단위 μA.

| 데이터 | 역할 | RMSE | 비고 |
|---|---|---|---|
| Fig.3h 16×5 | fit | 0.035 | 마지막 상태 순위 상관 0.997 |
| Fig.3i 16×5 | fit (TG 배율 3개만) | 0.061 | |
| Fig.3j 32×6 | **hold-out** | 0.087 | 1.0, 2.0 V TG는 보간 |
| Fig.3f 감쇠 모양 | fit 일부 | R² 0.990 (4.0 V), 0.997 (4.5 V) | 절대값은 소자 차이로 0.091 |
| Fig.4b 펄스 중 전류 60개 | fit | 0.025 | self-reset 곡선 0.047 |
| Fig.4c V_base 0 V | **hold-out** | 0.091 | self-reset 0.226 (이 소자는 휴지 전류가 더 낮음) |
| Fig.4g 첫 펄스열 | **hold-out**, 다른 소자 상태 | 0.43 | 첫 펄스가 3.8 vs 4.7 μA — 소자 상태 차이 |
| Supp. Fig.19 (그림만) | 경향 | 지연 0.5 ms: 4.79 vs 그림 약 4.9, 1.0 ms: 4.77 vs 약 4.6 | 둘 다 발화 안 함 ✓ |
| 상태 의존성 (Supp. Fig.11 대신) | 모델 없는 pair 검사 | 3h 0.042 | 같은 직전 전류에서 이력이 달라도 증가분 차이 ≤ 0.06 |

## 6. Known limitations

1. `state = I_D`는 behavioral 근사다. 같은 I_D라도 분극·trap 이력이 같다고 보장할 수 없다.
   - LIF에서 실제로 드러난다. 휴지 전류는 1 ms 안에 거의 다 빠지지만, 1 ms 뒤 다시 흥분시키면
     첫 펄스열보다 높게 시작한다 (Supp. Fig.18a, Fig.4g). 모델은 이 숨은 잔류를 과소평가한다.
2. TG 억제는 정량 보정되지 않았다 (experimental, 기본 꺼짐).
   - Fig.4e–g Source data는 억제 펄스 전후 1 ms 구간이 0으로 비어 있어 억제 직전·직후 I_D가 없다.
   - 같은 소자에서 억제 없이 1 ms 쉰 대조 측정도 없다.
   - Fig.4g에서 N=5와 N=1의 두 번째 펄스열 차이는 데이터 −0.48 μA, 모델 −0.03 μA. retention 0.64는 best-fit일 뿐 식별되지 않는다.
   - 필요한 데이터: 억제 펄스 직전·직후 휴지 I_D, 또는 같은 소자의 억제 없는 t_reset 1 ms 측정.
3. BG 전압·폭은 측정된 두 조건만 지원한다 (reservoir 4.0 V / 100 μs, LIF 2.5 V / 500 μs).
4. 보정 범위 밖 I_D에서는 펄스를 받지 않는다. TG 0 V로 4.0 V 펄스를 연속 5개 이상 주면 범위를 넘는다.
   line_cnn 주행 로그를 3 ms로 압축하면 펄스 506개 중 439개가 범위 밖이다 (`examples/telemetry_reservoir.py`).
5. 펄스 내부 과도 응답은 모델링하지 않는다. 펄스 도중 읽기와 펄스 겹침은 오류.
6. 측정 범위 밖 외삽은 하지 않는다. 단, τ_slow 표는 초과 전류 0.5 μA 아래·3.0 μA 위에서 가장자리 값을 쓴다
   (감쇠 모양 파라미터라 상태값 외삽과 다름).
7. 소자 간 차이: Fig.3f와 Fig.3h, Fig.4b와 Fig.4c/4g는 다른 측정이다. 모델은 Fig.3h(reservoir), Fig.4b(LIF) 기준.
8. Reservoir TG: 곱셈형 M(V_TG)는 가정이다. 데이터에서 직접 잰 배율(0.77/0.59/0.51)보다 피팅값(0.84/0.70/0.60)이 크다.
   TG를 건 3i/3j의 상태가 3h보다 조금 덜 감쇠하는 경향이 있어, TG 의존 감쇠나 소자 drift 가능성이 남아 있다.
9. 읽기 시점은 펄스 끝 0.2 ms 뒤로 가정했다 (Fig.3f 첫 샘플). Fig.3h–j Source data에는 읽기 시각이 없다.
10. v1은 physical compact model이 아니라 experimentally grounded behavioral model이다.

## 7. 폴더 구조

```
mpbtft/
├─ model.py            MPBTFT core (Reservoir/LIF 공용)
├─ parameters.py       파라미터 dataclass, JSON 입출력, PCHIP 표
├─ domains.py          지원 조건과 오류 종류
├─ reservoir.py        비트열 → 펄스열 도우미, Reservoir
├─ lif.py              LIFNeuron (증폭·문턱·발화)
├─ params/v1_params.json   피팅된 파라미터 + provenance
├─ data/               Source data에서 뽑은 CSV + README (출처)
├─ fitting/            fit_relaxation / fit_bg_update / fit_tg_modulation / fit_lif_excitation / fit_tg_inhibition / fit_all
├─ validation/         validate_fig3f / 3h / 3i / 3j / state_dependence / lif_excitation / tg_inhibition / run_all
├─ tests/test_mpbtft.py
├─ examples/           realtime_demo, telemetry_reservoir (+ telemetry.csv), continuous_state
└─ docs/               사양서, 입출력 정리, v0 토의 기록
```

v0 파일(`mpbtft.py`, `params.json`, `fit_from_paper.py`, `tg_measure.py`, `tg_test_fig3j.py`)은 v1로 대체했다.
v0의 TG 직접 측정은 `fitting/fit_tg_modulation.py`의 model-free 검사로, 3j 예측은 `validation/validate_fig3j.py`로 옮겼다.
