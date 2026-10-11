# configs/demo.json 설명

## 이 파일의 역할
모델에 쓰이는 숫자(소자 파라미터, 실험 조건)를 모아둔 설정 파일.
코드에는 숫자를 직접 넣지 않고 이 파일에서 읽어온다.
→ 코드를 고치지 않고 숫자만 바꿔서 실험할 수 있다.

**주의:** 모든 값은 예시값(synthetic)이다. 실제 측정값이나 논문 피팅값이 아니다.

## 단위 읽는 법
키 이름 끝에 단위가 붙어 있다.

| 접미사 | 단위 |
|---|---|
| `_S` | 지멘스 (conductance) |
| `_A` | 암페어 (전류) |
| `_V` | 볼트 (전압) |
| `_s` | 초 (시간) |

숫자 표기: `1e-06` = 1×10⁻⁶ → 1 µS, 1 µA 등

## 구조: 4개 구역

### ① `metadata`: 설명서
- `status: SYNTHETIC_DEMO_NOT_CALIBRATED` → 예시값이라는 표시
- 계산에는 쓰이지 않는다.
- `plot_results.py`가 이 값을 확인한다. 바꾸면 그림 그리기가 멈춘다.

### ② `fetft`: FeTFT 소자 데이터
| 키 | 값 | 뜻 |
|---|---|---|
| `read_vds_V` | 0.1 V | 전류를 읽을 때 거는 전압 |
| `ltp_conductance_S` | 1→2→3→4→5 µS | LTP: 펄스마다 한 칸씩 증가 |
| `ltd_conductance_S` | 5→4→3→2→1 µS | LTD: 펄스마다 한 칸씩 감소 |

- 표의 0번째 값 = 펄스를 주기 전 초기 상태
- 전류 = G × 0.1 V
- 표가 끝나면 더 이상 펄스를 줄 수 없다(오류 발생).

### ③ `mpbtft`: MPBTFT 소자 파라미터
| 키 | 값 | 뜻 |
|---|---|---|
| `baseline_A` | 1 µA | 아무것도 안 했을 때의 기본 전류 |
| `tau_fast_s` | 1 ms | 빨리 사라지는 성분의 시간상수 |
| `tau_slow_s` | 10 ms | 천천히 사라지는 성분의 시간상수 |
| `increment_A` | 0.8 µA | 펄스 1번에 올라가는 양(최대치) |
| `capacity_A` | 4 µA | 최대로 쌓일 수 있는 양(포화) |
| `fast_fraction` | 0.5 | 증가량 중 fast로 가는 비율 (나머지는 slow) |
| `tg_suppression_per_V` | 0.15 | TG 전압이 증가량을 얼마나 줄이는지 |
| `reference_width_s` | 100 µs | 기준 펄스 폭 |
| `reference_bg_V` | 4 V | 기준 BG 펄스 전압 (4 V 이외는 오류) |

- 전류 = baseline + fast + slow
- 오래 기다리면 fast, slow 모두 0으로 감쇠 → 전류는 baseline(1 µA)으로 돌아간다.

### ④ `protocol`: 실험 순서
| 키 | 값 | 뜻 |
|---|---|---|
| `bits` | [1, 0, 1, 1] | 4-bit 입력. 1 = 펄스, 0 = 펄스 없이 대기 |
| `tg_V` | [5.0, 3.0, 1.5, 0.0] | 각 bit에서 쓰는 TG 전압 |
| `gap_s` | 3 ms | 각 bit 뒤에 쉬는 시간 |
| `timing_convention` | (메모) | 3 ms를 "펄스 끝 → 다음 시작"으로 해석한 것은 임시 가정 |

## 누가 이 숫자를 쓰나
```
demo.json
 ├─ "fetft"    → FeTFT(c['fetft'])
 ├─ "mpbtft"   → MPBTFT(c['mpbtft'])
 └─ "protocol" → demo.py의 for 반복문
```
`demo.py` 7번째 줄에서 파일 전체를 읽고, 구역별로 나눠서 넘겨준다.

## JSON 작성 시 주의
- 주석(`//`, `#`)을 쓸 수 없다 → 메모는 `"_note": "..."` 같은 키로 넣는다.
- 항목 사이에는 쉼표 `,`가 필요하고, 마지막 항목 뒤에는 쉼표가 없어야 한다.
- 수정 후 `python demo.py`가 오류 없이 돌아가면 제대로 쓴 것이다.
- 원래대로 되돌리기: `git checkout configs/demo.json`

## 확인 문제
1. FeTFT가 LTP 3번째 펄스 후일 때 읽히는 전류는?
2. MPBTFT에서 펄스 없이 아주 오래 기다리면 전류는?
3. `bits`가 `[1,0,1,1]`일 때 실제로 들어가는 펄스 수는?

<details>
<summary>정답</summary>

1. 표의 3번째 값 4 µS × 0.1 V = **0.4 µA** (0번째가 초기 상태라서 3번째 펄스 후 = index 3)
2. **1 µA** (baseline)
3. **3번**
</details>
