# mpbtft — 휘발성 MPBTFT 소자 모델 사용법

논문 *Analog reservoir computing via ferroelectric mixed phase boundary transistors* (Nat. Commun. 2024)의
**휘발성 DG MPBTFT**를 Source data에 맞춰 Python으로 만든 모델입니다.

- 펄스를 주면 전류 I_D가 오르고, 시간이 지나면 다시 내려갑니다(휘발).
- 시뮬레이션 시계로도, 실제 시계(`time.perf_counter`)로도 돌아갑니다.
- 배경 설명, 피팅 결과, 한계는 `MPBTFT_volatile_model_notes.md`에 있습니다.

---

## 1. 준비

### 1-1. 설치
```bash
pip install numpy scipy openpyxl matplotlib
```
Windows에서 `python`이 안 되면 `py`로 바꿔 쓰세요 (예: `py fit_from_paper.py`).

### 1-2. 폴더 구성
**모든 명령은 이 `mpbtft` 폴더 안에서 실행합니다.** (`params.json`을 현재 폴더에서 읽기 때문)
```bash
cd mpbtft
```

### 1-3. 필요한 데이터 파일
| 파일 | 필요한 스크립트 | 없으면 |
|---|---|---|
| `params.json` | 거의 전부 | 들어 있음. 지웠다면 `fit_from_paper.py`로 다시 생성 |
| `source_data.xlsx` | 피팅·검증 스크립트 | 논문의 Source data 엑셀을 이 이름으로 이 폴더에 넣기 |
| `telemetry.csv` | `telemetry_reservoir.py` | 들어 있음 (line_cnn 주행 로그) |

---

## 2. 파일 설명

### 코드
| 파일 | 하는 일 | 엑셀 필요? |
|---|---|---|
| `mpbtft.py` | **소자 모델 본체.** 다른 스크립트가 전부 이걸 불러다 씀. 직접 실행하는 파일 아님 | ✗ |
| `fit_from_paper.py` | Source data(Fig.3f, 3h, 3i)로 모델 파라미터를 피팅해서 `params.json` 생성 | ✓ |
| `tg_measure.py` | **모델 없이** 데이터에서 TG 전압별 점프·감쇠를 직접 측정 (TG 표의 근거) | ✓ |
| `tg_test_fig3j.py` | TG 규칙 3가지 비교: 3i로 학습 → 3j를 처음 보는 데이터로 예측 | ✓ |
| `continuous_state.py` | 펄스 사이 실제 전류 궤적 + 아무 시각·상태·TG에서 펄스 주는 예시 그림 | ✓ |
| `telemetry_reservoir.py` | line_cnn 주행 로그를 소자에 흘려보내기 (카메라 시계 vs 소자 시계 비교) | ✗ |
| `realtime_demo.py` | 실제 시간으로 잊어버리는 소자를 키보드로 직접 조작 | ✗ |

### 데이터·결과
| 파일 | 내용 | 만드는 스크립트 |
|---|---|---|
| `params.json` | 모델 파라미터 (I₀, τ, 점프 규칙, V_PGM 배율, TG 표) | `fit_from_paper.py` |
| `fit_report.json` | 피팅 결과 수치 (Fig.3h/3i 오차 등) | `fit_from_paper.py` |
| `fit_fig3.png` | Fig.3f / 3h / 3i 데이터 vs 모델 그림 | `fit_from_paper.py` |
| `tg_measure.json` | TG 전압별 점프·감쇠 측정값, Fig.3g 상태값 | `tg_measure.py` |
| `tg_test_report.json` | TG 모델 A/B/C의 3i·3j 오차 | `tg_test_fig3j.py` |
| `tg_test_fig3j.png` | 3j 예측 그림 (모델 A vs B) | `tg_test_fig3j.py` |
| `continuous_state.png` | 연속 궤적 그림 | `continuous_state.py` |
| `telemetry_reservoir.png` | line_cnn 조향 → 소자 전류 그림 | `telemetry_reservoir.py` |
| `fig3g_tg_gain.json` | Fig.3g 기반 TG 배율 (참고용, 조건이 달라 기본값엔 안 씀) | 초기 분석 |
| `telemetry.csv` | line_cnn 주행 로그 (입력 데이터) | — |

### 문서
| 파일 | 내용 |
|---|---|
| `README.md` | 이 문서 (사용법) |
| `MPBTFT_volatile_model_notes.md` | 토의 정리: 진행 현황, 논문 그림 해설, 피팅·검증 결과, 한계, 다음 할 일 |

---

## 3. 명령어

### 3-1. 처음 한 번: 파라미터 피팅
```bash
python fit_from_paper.py source_data.xlsx
```
- 걸리는 시간: 약 30초
- 만드는 것: `params.json`, `fit_report.json`, `fit_fig3.png`
- 화면 출력: 파라미터와 오차. 정상이면 `fig3h_rmse_uA`가 약 0.044
- `params.json`이 이미 있으면 **안 돌려도 됩니다.**

### 3-2. TG 효과 직접 측정
```bash
python tg_measure.py source_data.xlsx
```
- 만드는 것: `tg_measure.json`
- 화면 출력 예:
  ```
  V_TG | 점프 μA (0 V 대비) | 3 ms 뒤 남는 비율
     0 | 0.84 ± 0.05 (1.00) n=56 | 0.81 ± 0.05 n=17
     5 | 0.43 ± 0.06 (0.51) n=24 | 0.82 ± 0.03 n=16
  ```
  → 점프는 TG에 따라 줄고, 남는 비율은 TG와 무관하다는 근거

### 3-3. TG 모델 검증 (3i 학습 → 3j 예측)
```bash
python tg_test_fig3j.py source_data.xlsx
```
- 걸리는 시간: 약 15초
- 만드는 것: `tg_test_report.json`, `tg_test_fig3j.png`
- 확인할 값: `C_measured_table`의 `3j` → `rmse_uA` 약 0.091

### 3-4. 연속 궤적 그림
```bash
python continuous_state.py source_data.xlsx
```
- 만드는 것: `continuous_state.png`

### 3-5. line_cnn 연동
```bash
python telemetry_reservoir.py telemetry.csv
```
- 만드는 것: `telemetry_reservoir.png`
- 화면 출력 예:
  ```
  A) 실제 간격  : 기억 ≈ 1 프레임
  B) 3 ms 압축 : 기억 ≈ 13 프레임
  ```
- 다른 주행 로그를 쓰려면 경로만 바꾸면 됩니다 (`steer_norm`, `t` 열 필요).

### 3-6. 실시간 데모
```bash
python realtime_demo.py                 # 그래프 창
python realtime_demo.py --terminal      # 창 없이 터미널
python realtime_demo.py --vtg 3         # TG 3 V 걸린 상태
python realtime_demo.py --slow 100      # 덜 느리게 (실제 1초 = 소자 10 ms)
```

| 옵션 | 기본값 | 뜻 |
|---|---|---|
| `--slow` | 1000 | 몇 배 느리게 볼지. 1000이면 실제 1초 = 소자 1 ms |
| `--vtg` | 0 | TG 전압 (V). 펄스 효과만 줄이고 감쇠는 그대로 |
| `--terminal` | 꺼짐 | 그래프 창 없이 터미널에서 실행 |
| `--params` | `params.json` | 다른 파라미터 파일 쓰기 |

조작키:
| 모드 | 키 | 동작 |
|---|---|---|
| 그래프 창 | `스페이스` | 4.0 V 펄스 |
| 그래프 창 | `5` | 4.5 V 펄스 |
| 그래프 창 | `r` | 리셋 (다 잊게) |
| 터미널 | `Enter` | 4.0 V 펄스 |
| 터미널 | `q` + `Enter` | 종료 |

### 3-7. 전체 한 번에 다시 돌리기
```bash
python fit_from_paper.py source_data.xlsx
python tg_measure.py source_data.xlsx
python tg_test_fig3j.py source_data.xlsx
python continuous_state.py source_data.xlsx
python telemetry_reservoir.py telemetry.csv
```

---

## 4. 내 코드에서 모델 쓰기

같은 폴더에서 `mpbtft.py`를 import 하면 됩니다.

### 4-1. 기본: 펄스 주고 읽기
```python
from mpbtft import MPBTFT, MPBTFTParams

p = MPBTFTParams.load("params.json")
d = MPBTFT(p)                 # 시뮬레이션 시계 (시간은 advance로 직접 진행)

d.pulse(4.0)                  # 4.0 V 펄스 1개 (폭 100 μs 전제)
d.advance(0.2e-3)             # 0.2 ms 지나기
print(d.read() * 1e6, "μA")   # 전류 읽기 (A 단위로 나오므로 ×1e6)
d.advance(3e-3)               # 3 ms 더 지나기 → 잊음
print(d.read() * 1e6, "μA")
```

### 4-2. 논문 방식 펄스열 (Fig.3h / 3i / 3j)
```python
d = MPBTFT(p)
print(d.run_train("1011"))                                   # Fig.3h: TG 없음, 간격 3 ms

d = MPBTFT(p)
print(d.run_train("1011", vtgs=[5.0, 3.0, 1.5, 0.0]))        # Fig.3i 방식 TG

d = MPBTFT(p)
print(d.run_train("11010", vtgs=[1.0, 5.0, 3.0, 2.0, 0.0]))  # Fig.3j 방식 TG
```
- 반환값: timeframe마다 펄스 0.2 ms 뒤 읽은 전류 (A) 리스트
- `interval=1e-3`처럼 간격도 바꿀 수 있음 (3 ms가 아닌 간격은 검증 범위 밖)

### 4-3. 펄스 하나씩 세밀하게
```python
d = MPBTFT(p)
d.pulse(4.0, vtg=1.0)     # TG 1 V에서 펄스 (점프 0.75배)
d.advance(1.1e-3)
d.pulse(4.5)              # 4.5 V 펄스 (검증 약함, notes 참고)
d.advance(5e-3)
d.reset()                 # 즉시 초기 상태로
```

### 4-4. 실제 시계로 (time 사용)
```python
import time
rt = MPBTFT(p, clock=time.perf_counter, time_scale=1/1000)   # 실제 1초 = 소자 1 ms
rt.pulse(4.0)
time.sleep(3)             # 실제 3초 = 소자 3 ms
print(rt.read() * 1e6)    # 기다린 만큼 잊은 전류
```
- 실시간 모드에서는 `advance()`를 쓰지 않습니다. 진짜로 기다리면 됩니다.
- `time_scale=1`이면 실제 시간 그대로 (소자는 수십 ms 안에 거의 다 잊음).

### 4-5. 여러 소자 = reservoir
```python
from mpbtft import Reservoir
res = Reservoir(4, p, vtgs=[5.0, 3.0, 1.5, 0.0])
feats = res.encode(["1011", "0001", "1111", "0100"])   # 소자 4개에 각각 입력
print([f * 1e6 for f in feats])                          # 마지막 전류 = 특징값
```

### 주요 함수 정리
| 함수 | 뜻 |
|---|---|
| `MPBTFTParams.load(path)` | 파라미터 불러오기 |
| `MPBTFT(p, clock=None, time_scale=1)` | 소자 만들기. `clock`을 주면 실시간 모드 |
| `pulse(vpgm=4.0, vtg=None, tg_gain=None)` | BG 펄스. `vtg`로 TG 전압, `tg_gain`으로 배율 직접 지정 |
| `advance(dt)` | 시뮬레이션 시간 dt초 진행 |
| `read()` | 지금 전류 (A) |
| `reset()` | 상태 초기화 |
| `run_train(bits, interval=3e-3, vpgm=4.0, vtgs=None)` | 비트열 펄스열 실행 |
| `p.tg_gain_for(vtg)` | TG 전압 → 펄스 효과 배율 |

---

## 5. 믿을 수 있는 범위
| 상황 | 신뢰도 |
|---|---|
| 4.0 V, 100 μs, 3 ms 간격, 전류 1~3.5 μA | 높음 (Fig.3h 오차 약 2%) |
| TG 0~5 V (3 ms 간격) | 높음~중간 (3j 예측 오차 0.091 μA) |
| 3 ms가 아닌 간격 | 중간 |
| 3.5 / 4.5 / 5.0 V 펄스 | 낮음 (펄스열 데이터 없음) |
| 펄스 5개 이상 연속, 3.5 μA 이상 | 낮음 (과소평가 경향) |
| 펄스 폭 100 μs 아닌 경우 | 지원 안 함 |

자세한 이유는 `MPBTFT_volatile_model_notes.md` 0장, 7장 참고.

---

## 6. 자주 나는 오류
| 증상 | 원인 / 해결 |
|---|---|
| `FileNotFoundError: params.json` | `mpbtft` 폴더 안에서 실행하지 않음 → `cd mpbtft` |
| `FileNotFoundError: source_data.xlsx` | 엑셀이 없음 → Source data 엑셀을 이 이름으로 폴더에 넣기 |
| `ModuleNotFoundError: openpyxl` 등 | 1-1의 `pip install` 실행 |
| 그래프 창이 안 뜸 | 서버/원격 환경 → `--terminal` 옵션 사용 |
| `RuntimeError: 실시간 모드에서는 advance()...` | `clock`을 준 소자에 `advance()` 호출 → 실제로 기다리기 |
