# MPBTFT v1 Behavioral Model 구현 사양서

> 대상 논문: **Analog reservoir computing via ferroelectric mixed phase boundary transistors**  
> Nature Communications 15, 9147 (2024)  
> DOI: 10.1038/s41467-024-53321-2

---

# 1. 이 문서의 목적

이 문서는 volatile Double-Gate MPBTFT를 Python behavioral model로 구현하기 위한 **공식 v1 사양서**이다.

이 문서를 읽는 개발자는 다음을 명확히 이해해야 한다.

1. 왜 이 모델을 만드는가
2. v1에서 반드시 구현해야 하는 기능은 무엇인가
3. v1에서 일부러 구현하지 않는 기능은 무엇인가
4. 입력, 출력, state, hidden state가 각각 무엇인가
5. Reservoir와 LIF가 같은 MPBTFT core를 어떻게 공유하는가
6. 어떤 논문 데이터를 사용하여 각 기능을 fitting/validation해야 하는가
7. 구현 완료를 어떤 기준으로 판정하는가

이번 v1의 목표는 **모든 전압과 모든 pulse width를 지원하는 완전한 compact model**이 아니다.

가장 중요한 목표는 다음이다.

\[
\boxed{
\text{현재 state + 경과시간 + gate event}
\rightarrow
\text{다음 } I_D
}
\]

를 논문에서 충분히 검증된 operating condition 안에서 신뢰성 있게 계산하는 것이다.

---

# 2. 프로젝트 전체에서 MPBTFT의 역할

같은 MPBTFT 소자 모델을 두 곳에 사용한다.

## 2.1 Physical Reservoir

MPBTFT는 시간에 따른 입력 history를 \(I_D\)에 반영하는 volatile reservoir로 동작한다.

```text
BG input pulse
    ↓
ID 증가
    ↓
시간 경과
    ↓
ID relaxation
    ↓
다음 BG input
    ↓
history-dependent ID
```

TG는 BG pulse의 programming efficiency를 조절하여 reservoir state separation을 향상시킨다.

---

## 2.2 LIF Neuron

같은 MPBTFT를 LIF device core로 사용한다.

```text
BG excitatory pulse
    ↓
ID 증가 = integration

시간 경과
    ↓
ID 감소 = leak

TG inhibitory pulse
    ↓
ID 감소 = inhibition
```

단, **firing/spike generation은 MPBTFT core의 역할이 아니다.**

MPBTFT의 출력은 항상 \(I_D\)이다.

Comparator, threshold, firing은 별도의 `LIFNeuron` wrapper에서 구현한다.

---

# 3. 가장 중요한 설계 원칙

## 반드시 지킬 것

- 하나의 `MPBTFT` class를 만든다.
- Reservoir와 LIF는 다른 인스턴스를 사용하되 같은 class를 사용한다.
- Figure 결과를 lookup하지 않는다.
- 현재 state와 event로 다음 state를 계산한다.
- 모든 timestep을 저장하지 않는다.
- event-driven / lazy relaxation 방식을 사용한다.
- 논문에서 검증되지 않은 영역을 extrapolation하지 않는다.
- fitted parameter와 raw/derived data의 출처를 기록한다.
- 지원하지 않는 입력은 조용히 계산하지 말고 error를 발생시킨다.

## 절대 하지 말 것

- `0000 -> 1.2 uA`, `0001 -> 1.4 uA`처럼 Fig.3h를 sequence lookup table로 구현
- Fig.3i의 16개 결과를 직접 저장해서 반환
- TG inhibition 데이터를 임의 식으로 가정
- arbitrary voltage/width를 근거 없이 허용
- software reset을 physical self-reset으로 해석
- comparator/spike를 MPBTFT core 안에 넣기

---

# 4. 한눈에 보는 입력 / 출력 / State

## 4.1 외부 입력

MPBTFT가 받는 입력은 크게 3종류다.

### 시간

```text
time_s
```

절대 simulation time.

모든 event는 시간 순서대로 입력해야 한다.

---

### BG pulse

```text
BG voltage amplitude
BG pulse width
동시에 적용되는 TG bias
```

개념적으로

\[
(V_{BG}, t_{BG}, V_{TG})
\]

---

### TG inhibitory pulse

LIF에서 사용한다.

\[
(V_{TG,\mathrm{inh}}, t_{TG,\mathrm{inh}})
\]

---

# 4.2 외부 출력

외부 출력은 하나다.

\[
\boxed{I_D(t)}
\]

단위는 Ampere [A].

예:

```python
id_A = device.read_current(time_s=0.013)
```

다음은 MPBTFT core의 출력이 아니다.

```text
spike
firing 여부
class
membrane voltage
classification result
```

---

# 4.3 Observable State

외부에서 보는 state는

\[
\boxed{I_D}
\]

이다.

물리적으로 실제 internal memory state는 HZO polarization, trapped charge 등과 관련되지만 behavioral model에서는 \(I_D\)를 state proxy로 사용한다.

중요한 한계:

> 동일한 \(I_D\)라도 과거 polarization/trap history가 완전히 같다고 보장할 수는 없다.  
> 따라서 `state = ID`는 v1의 behavioral modeling assumption이다.

README의 known limitation에 반드시 기록한다.

---

# 4.4 Hidden State

double-exponential relaxation을 표현하기 위해 내부적으로 다음과 같은 hidden state를 사용할 수 있다.

```python
baseline_current_A
fast_component_A
slow_component_A
last_update_time_s
```

또는 동등한 parameterization을 사용할 수 있다.

외부 API에서는 hidden state를 직접 조작하지 않는다.

---

# 5. v1에서 구현할 세 가지 핵심 물리 관계

## 5.1 BG Update

\[
\boxed{
I_D^+
=
U_{BG}(I_D^-,V_{BG},t_{BG},V_{TG})
}
\]

- \(I_D^-\): pulse 직전 current
- \(I_D^+\): pulse 직후 current

v1에서는 이 완전 일반식을 모두 지원하지 않는다.

검증된 operating point만 구현한다.

---

## 5.2 Relaxation

\[
\boxed{
I_D(t+\Delta t)=R(I_D(t),\Delta t)
}
\]

논문의 기본 형태:

\[
I_D(t)
=
I_0
+
A_1e^{-t/\tau_1}
+
A_2e^{-t/\tau_2}
\]

- \(\tau_1\): rapid decay
- \(\tau_2\): gradual decay
- \(A_1,A_2\): 각 decay component
- \(I_0\): 충분히 긴 시간이 지난 후 current

---

## 5.3 TG Inhibition

\[
\boxed{
I_D^+
=
U_{TG}(I_D^-,V_{TG},t_{TG})
}
\]

LIF에서 TG inhibitory pulse가 current를 감소시키는 동작이다.

이 기능이 v1에서 가장 데이터가 제한적인 부분이다.

---

# 6. v1 Operating Mode A — Reservoir

가장 먼저 완성해야 할 mode이다.

## 기본 조건

\[
\boxed{V_{BG}=4.0~V}
\]

\[
\boxed{t_{BG}=100~\mu s}
\]

\[
\boxed{V_{DS}=0.1~V}
\]

Fig.3h/3i validation에서 기본 pulse interval:

\[
\boxed{3~ms}
\]

단, relaxation 함수 자체를 3 ms에 고정하지 않는다.

---

# 6.1 Binary input

초기 baseline에서는 binary input을 사용한다.

```text
bit = 1
→ BG 4.0 V / 100 μs pulse

bit = 0
→ BG pulse 없음
```

---

# 6.2 Reservoir에서 TG의 의미

TG는 inhibitory pulse가 아니다.

Reservoir에서는 BG programming efficiency를 조절한다.

\[
V_{TG}\uparrow
\Rightarrow
\Delta I_D^{BG}\downarrow
\]

즉 TG는 BG sensitivity modulation 용도이다.

---

# 6.3 Reservoir v1에서 필요한 함수

조건이 고정되어 있으므로 실제 핵심은

\[
\boxed{
\Delta I_D^{BG}
=
F(I_{D,\mathrm{pre}},V_{TG})
}
\]

이다.

여기서

\[
V_{BG}=4.0~V,\quad t_{BG}=100~\mu s
\]

는 고정이다.

---

# 7. v1 Operating Mode B — LIF Excitation

동일한 `MPBTFT` class를 사용한다.

대표 operating point:

\[
\boxed{V_{BG}:0~V\rightarrow2.5~V}
\]

\[
\boxed{t_{\mathrm{exc}}=500~\mu s}
\]

\[
\boxed{V_{TG,\mathrm{baseline}}=-3.0~V}
\]

\[
\boxed{V_{DS}=0.1~V}
\]

Supplementary Fig.18/19의 대표 조건을 우선 활용한다.

반복 BG excitation에서

\[
I_D\uparrow
\]

해야 하고 pulse 사이에서는 relaxation에 의해

\[
I_D\downarrow
\]

해야 한다.

즉

```text
BG excitation → integration
no input      → leak
```

를 재현해야 한다.

---

# 8. v1 Operating Mode C — TG Inhibition

TG inhibition은 LIF에서만 사용한다.

대표 조건:

\[
\boxed{V_{\mathrm{inh}}=5.0~V}
\]

\[
\boxed{t_{\mathrm{inh}}=100~\mu s}
\]

TG baseline:

\[
-3.0~V
\]

waveform 개념:

```text
-3 V  →  +5 V  →  -3 V
          100 μs
```

지원되는 LIF state 범위에서

\[
I_D^+ < I_D^-
\]

가 되어야 한다.

단, arbitrary initial \(I_D\) 전체 범위에 대해 완전한 일반화를 주장하면 안 된다.

---

# 9. v1 지원 범위 / 비지원 범위

## 반드시 지원

### Reservoir

- 4.0 V BG
- 100 μs BG pulse
- arbitrary event timing
- 현재 \(I_D\)에 의존하는 BG update
- volatile relaxation
- TG modulation
- Fig.3h/3i validation

### LIF

- 2.5 V / 500 μs BG excitation
- TG baseline -3 V
- integration
- leak
- 대표 5 V / 100 μs TG inhibition
- \(I_D(t)\) 출력

---

## v1에서 지원하지 않아도 됨

```text
임의 VBG
임의 BG pulse width
임의 TG inhibitory amplitude
임의 TG inhibitory width
모든 initial ID에서 정확한 TG inhibition
pulse 내부 transient
pulse overlap
측정 범위 밖 extrapolation
완전한 physical compact model
```

---

# 10. Event-Driven / Lazy Relaxation 규칙

이 부분은 반드시 지킨다.

매 timestep마다 current를 계산하고 history array에 저장하지 않는다.

객체는 마지막 committed state와 시간만 기억한다.

---

# 10.1 Read

```python
device.read_current(time_s=t)
```

호출 시:

\[
\Delta t=t-t_{\mathrm{last}}
\]

를 계산하고 relaxation을 적용해 현재 current를 반환한다.

중요:

**read 자체가 physical trajectory를 변경하면 안 된다.**

같은 state에서 같은 time을 두 번 읽으면 같은 값이 나와야 한다.

---

# 10.2 BG pulse event

권장 API:

```python
device.apply_bg_pulse(
    time_s=t_start,
    voltage_V=4.0,
    width_s=100e-6,
    tg_voltage_V=...
)
```

`time_s`는 pulse 시작 시각이다.

처리 순서:

```text
1. 마지막 committed state에서 t_start까지 relaxation
2. pulse 직전 ID_pre 계산
3. BG update 계산
4. pulse 종료 직후 ID_post 계산
5. ID_post를 새 state로 commit
6. last_update_time = t_start + width
```

---

# 10.3 TG inhibitory event

```python
device.apply_tg_inhibition(
    time_s=t_start,
    voltage_V=5.0,
    width_s=100e-6
)
```

처리 순서:

```text
1. t_start까지 relaxation
2. ID_pre 계산
3. TG inhibitory update 계산
4. ID_post 계산
5. pulse 종료 시점에 state commit
```

---

# 10.4 Pulse 도중 read

v1은 intra-pulse dynamics를 모델링하지 않는다.

따라서 pulse 시작과 종료 사이를 읽으려 하면 error를 발생시키는 것을 권장한다.

---

# 10.5 Pulse overlap

v1은 overlapping pulse를 지원하지 않는다.

새 event가 이전 pulse 종료 전 시작하면:

```python
ValueError("Overlapping gate events are not supported in MPBTFT v1.")
```

---


# 10.6 ID는 입력이 없어도 원하는 시점에 언제든 확인 가능

MPBTFT의 \(I_D\)는 BG 또는 TG pulse가 새로 들어오지 않더라도 사용자가 원하는 시점에 바로 확인할 수 있어야 한다.

예를 들어 마지막 pulse가

\[
t=10~ms
\]

에 종료되었고 이후 아무 gate input이 없었다고 하자.

사용자가

```python
device.read_current(time_s=13e-3)
```

를 호출하면 모델은 내부적으로

\[
\Delta t = 13~ms - 10~ms = 3~ms
\]

를 계산하고, 마지막 committed state에서 3 ms 동안의 relaxation을 적용하여

\[
\boxed{I_D(13~ms)}
\]

를 반환한다.

즉 동작 흐름은 다음과 같다.

```text
마지막 committed state
        ↓
새로운 BG/TG 입력 없음
        ↓
시간만 경과
        ↓
사용자가 원하는 시점에 read_current(t)
        ↓
마지막 update 이후 경과시간 계산
        ↓
relaxation 계산
        ↓
현재 ID 반환
```

여기서 `read_current()`는 **state를 바꾸는 gate input이 아니라 관측(query)** 이다.

따라서 동일한 state와 동일한 시각에서 여러 번 `read_current()`를 호출하더라도 결과가 달라지면 안 된다.

실제 소자에서는 current를 측정하기 위해 read bias가 필요하지만, v1에서는

\[
V_{DS}=0.1~V
\]

를 fixed device parameter로 두고 사용자가 매번 입력하지 않아도 되도록 한다.

즉 v1에서 다음이 가능해야 한다.

\[
\boxed{
\text{BG/TG 입력이 없어도 원하는 시각의 } I_D \text{를 언제든 확인 가능}
}
\]

---

# 10.7 Reservoir와 LIF에서 BG/TG의 시간 관계를 구분한다

BG와 TG가 같은 gate pair를 사용하더라도, Reservoir와 LIF에서는 시간적 사용 방식이 다르다.

## Reservoir

Reservoir에서는 BG pulse가 들어오는 동안 TG bias가 **동시에 적용될 수 있어야 한다.**

예:

```text
t = 0 ms

BG = 4.0 V
width = 100 μs

동시에
TG = 3.0 V
```

이 경우 TG는 별도의 inhibitory event가 아니라 BG programming efficiency를 조절하는 modulation bias이다.

즉 Reservoir에서는 다음과 같은 동시 입력이 정상 동작이다.

\[
\boxed{
BG\ pulse + TG\ modulation\ bias
}
\]

따라서 `apply_bg_pulse()`의 `tg_voltage_V`는 pulse가 진행되는 동안 동시에 적용되는 TG bias를 의미한다.

---

## LIF

LIF에서는 BG와 TG가 서로 다른 기능을 수행한다.

```text
BG → excitatory input
TG → inhibitory input
```

따라서 v1에서는 BG excitation과 TG inhibition을 **서로 독립된 시간 event**로 처리한다.

예:

```text
0.0 ms ~ 0.5 ms
BG excitation

0.8 ms ~ 1.3 ms
BG excitation

1.5 ms ~ 1.6 ms
TG inhibition

2.0 ms ~ 2.5 ms
BG excitation
```

이처럼 BG와 TG event는 서로 다른 시점에 자유롭게 배치할 수 있다.

---

## LIF v1에서는 BG excitation과 TG inhibition의 overlap을 허용하지 않는다

다음과 같은 경우는 허용한다.

```text
BG: 0.0 ms ~ 0.5 ms
TG: 0.5 ms ~ 0.6 ms
```

두 event가 정확히 이어지지만 겹치지 않기 때문이다.

반면 다음은 허용하지 않는다.

```text
BG: 0.0 ms ~ 0.5 ms
TG: 0.3 ms ~ 0.4 ms
```

BG excitation과 TG inhibition이 같은 시간 구간에 동시에 존재하기 때문이다.

이 경우 실제 response는 개념적으로

\[
I_D^+
=
F(
I_D^-,
V_{BG},
V_{TG},
t_{BG},
t_{TG},
\text{overlap timing}
)
\]

과 같은 joint response가 필요하지만, 논문에는 LIF mode에서 BG excitation과 TG inhibitory pulse가 겹쳤을 때의 정량적 \(I_D\) response가 충분히 제공되어 있지 않다.

따라서 v1에서는 근거 없는 모델을 만들지 않고 overlap을 금지한다.

권장 error:

```python
ValueError(
    "Overlapping BG excitation and TG inhibition "
    "are not supported in MPBTFT v1 LIF mode."
)
```

---

## 최종 시간 규칙 요약

### Reservoir

\[
\boxed{
BG\ pulse와 TG\ modulation\ bias는 동시에 적용 가능
}
\]

### LIF

\[
\boxed{
BG\ excitation과 TG\ inhibition은 독립적인 event로 자유롭게 배치 가능
}
\]

단,

\[
\boxed{
v1에서는 두 event의 시간적 overlap은 금지
}
\]

한다.

이 구조는 후반 연구에서 context 정보를 TG inhibition으로 사용할 때도 유리하다.

예를 들어 context가 특정 시점에 들어오면 그 시점에 TG inhibitory event를 삽입할 수 있으므로, 향후에는

```text
언제 inhibition을 넣을 것인가
얼마나 강한 inhibition을 넣을 것인가
```

를 별도의 알고리즘 변수로 확장할 수 있다.

---

# 11. BG Update fitting

Reservoir 핵심 조건:

\[
4.0~V,\quad100~\mu s
\]

에서

\[
\Delta I_D
=
F(I_{D,\mathrm{pre}})
\]

를 구한다.

논문 Supplementary Note 4의 중요한 trend:

- 같은 \(V_{PGM}\)에서 initial \(I_D\) 증가
- \(\Delta I_D\) 감소
- saturation tendency 존재

따라서

\[
I_D^+=I_D^-+C
\]

같은 constant increment 모델은 금지한다.

---

## 권장 방식

### 1순위: PCHIP / piecewise interpolation

source data 또는 digitized data에서

```text
ID_pre
ΔID
```

pair를 만든다.

장점:

- data 범위 내부에서만 계산
- 불필요한 analytic assumption 감소
- monotonic trend 보존 가능

### 2순위: simple saturation model

예:

\[
\Delta I_D=a(I_{\mathrm{sat}}-I_D)^b
\]

단, measured data보다 충분히 잘 맞을 때만 허용한다.

---

# 12. TG Reservoir Modulation fitting

초기 후보 모델:

\[
\Delta I_D(I_D,V_{TG})
=
\Delta I_D(I_D,V_{TG}=0)
\cdot M(V_{TG})
\]

단,

\[
M(0)\approx1
\]

이고 positive \(V_{TG}\)가 증가하면 감소해야 한다.

중요:

이 multiplicative 형태는 **가정**이다.

Fig.3g/3i validation이 충분히 좋지 않으면

\[
\Delta I_D=F(I_D,V_{TG})
\]

2D interpolation으로 확장한다.

---

# 13. Relaxation fitting

논문 기본식:

\[
I_D(t)
=
I_0+
A_1e^{-t/\tau_1}
+
A_2e^{-t/\tau_2}
\]

가능하면 각 available relaxation curve를 독립 fitting한다.

그 후

\[
(A_1,A_2,\tau_1,\tau_2,I_0)
\]

를 pulse 직후 current 또는 source data가 제공하는 initial-state variable에 대해 interpolation한다.

모든 state에 동일한 relaxation parameter를 무조건 적용하지 않는다.

---

# 14. LIF BG Excitation fitting

Reservoir의 4 V / 100 μs kernel을 LIF에 그대로 사용하지 않는다.

LIF 조건은 별도 calibration한다.

\[
V_{BG}=2.5~V
\]

\[
t_{BG}=500~\mu s
\]

\[
V_{TG}=-3~V
\]

외부 API는 같은 `apply_bg_pulse()`를 사용하되 내부 calibrated domain이 다르다.

---

# 15. TG Inhibition 구현 규칙

TG inhibition은 가장 보수적으로 구현한다.

## 먼저 확인할 data

Fig.4e-g / source data에서 가능한 한 다음을 추출한다.

```text
inhibitory pulse 직전 ID
inhibitory pulse 직후 ID
Vinh
pulse width
pulse number
```

---

## quantitative data가 충분하면

5 V / 100 μs condition에서

\[
I_D^+=U_{TG}(I_D^-)
\]

를 fitting한다.

---

## quantitative data가 부족하면

임의 decrement를 만들지 않는다.

예:

```text
ID -= 0.5 uA
```

같은 식을 근거 없이 넣으면 안 된다.

이 경우 TG inhibition 기능은:

```text
experimental / limited
```

로 표시하고, 무엇이 부족한지 명확히 보고한다.

---

# 16. LIF firing은 별도 wrapper

권장 구조:

```python
class LIFNeuron:
    def __init__(self, device: MPBTFT, threshold=...):
        self.device = device
```

MPBTFT core는 \(I_D\)까지만 계산한다.

다음은 wrapper에서 처리한다.

```text
amplifier abstraction
threshold
comparator
firing
spike
```

---

# 17. 초기화와 physical reset 구분

simulation/test용 초기화 method는 허용한다.

```python
device.initialize()
```

하지만 이는 physical self-reset이 아니다.

논문의 self-reset은 volatility와 relaxation에 의해 발생한다.

---

# 18. 권장 Public API

```python
class MPBTFT:

    def read_current(self, time_s: float) -> float:
        ...

    def apply_bg_pulse(
        self,
        time_s: float,
        voltage_V: float,
        width_s: float,
        tg_voltage_V: float,
    ) -> float:
        ...

    def apply_tg_inhibition(
        self,
        time_s: float,
        voltage_V: float,
        width_s: float,
    ) -> float:
        ...

    def initialize(self, time_s: float = 0.0) -> None:
        ...
```

private helper 예:

```python
_relax_state_to(...)
_lookup_bg_update(...)
_lookup_relaxation_parameters(...)
_lookup_tg_modulation(...)
_lookup_tg_inhibition(...)
_validate_domain(...)
```

---

# 19. Domain Check

지원 영역을 명시적으로 관리한다.

예:

```python
RESERVOIR_BG_DOMAIN = {
    "voltage_V": [4.0],
    "width_s": [100e-6],
}
```

측정 범위 밖은 silent extrapolation하지 않는다.

예:

```text
4.0 V / 100 μs → supported

4.37 V / 73 μs → unsupported in v1
```

---

# 20. Data provenance

모든 fitting data의 출처를 기록한다.

예:

```csv
source,figure,method
main_paper,Fig3f,source_data
supplement,SFig11,digitized
```

`data/README.md`에 최소한 다음을 기록한다.

- Figure 번호
- source-data.xlsx 사용 여부
- digitization 여부
- 단위 변환
- interpolation 방식
- fitting script

코드 내부 magic number로 출처를 잃지 않는다.

---

# 21. Figure → 기능 매핑

| 논문 자료 | 모델에서의 용도 |
|---|---|
| Main Fig.3f | volatile relaxation, VPGM dependence |
| Main Fig.3g | TG modulation |
| Main Fig.3h | reservoir without TG validation |
| Main Fig.3i | TG-assisted reservoir validation |
| Main Fig.3j | 가능하면 hold-out validation |
| Supp. Fig.10 | consecutive BG pulse dynamics |
| Supp. Fig.11 | state-dependent update / relaxation parameter |
| Supp. Fig.12 | 향후 voltage/width/TG 확장 |
| Supp. Fig.13 | pulse interval effect |
| Main Fig.4b-d | LIF excitation / leak |
| Main Fig.4e-g | TG inhibition |
| Supp. Fig.18 | reset-time behavior |
| Supp. Fig.19 | pulse-delay dependence |
| Supp. Note 4 | reservoir device 해석 |
| Supp. Note 5 | excitatory/inhibitory 동작 해석 |

---

# 22. Validation

모델 완료 여부는 validation으로 판단한다.

## 22.1 Fig.3f

```text
Measured ID(t)
vs
Model ID(t)
```

가능하면 다음 metric 보고:

```text
RMSE
R²
max absolute error
```

---

## 22.2 Supplementary Fig.11

state-dependent update와 random pulse sequence를 검증한다.

핵심 질문:

```text
이전 ID가 달라져도
현재 ID + pulse
만으로 다음 ID를 합리적으로 예측하는가?
```

---

## 22.3 Fig.3h

16개 sequence:

```text
0000
0001
...
1111
```

모두 simulation한다.

조건:

```text
BG = 4 V
width = 100 μs
TG = 0 V
interval = 3 ms
```

결과는 lookup이 아니라 event transition의 반복으로 생성되어야 한다.

---

## 22.4 Fig.3i

논문의 실제 TG schedule을 정확히 추출해서 사용한다.

추측해서 voltage schedule을 만들지 않는다.

16개 reservoir state를 비교한다.

---

## 22.5 가능하면 Fig.3j

Fig.3i fitting에 직접 쓰지 않았다면 hold-out validation으로 사용한다.

---

## 22.6 LIF excitation

Fig.4b / SFig.18 / SFig.19를 이용해 확인한다.

```text
반복 excitation → ID 증가
pulse 사이 시간 증가 → leak 증가
긴 delay → 이전 정보 감소
```

---

## 22.7 TG inhibition

Fig.4e-g에서 확인한다.

최소한 지원 domain에서

\[
I_D^+ < I_D^-
\]

여야 한다.

---

# 23. Unit Test

최소 다음을 포함한다.

## 시간

- 과거 time 입력 → error
- overlapping event → error

## Read purity

```python
a = device.read_current(t)
b = device.read_current(t)
```

일 때 `a == b`.

read 횟수가 trajectory를 바꾸면 안 된다.

## Relaxation

충분히 긴 시간이 지나면 baseline 방향으로 이동.

## BG

지원 operating point에서

\[
I_D^+ > I_D^-
\]

## State dependence

같은 BG pulse에서 높은 initial current일수록 update magnitude 감소 trend.

## TG modulation

같은 pre-state/BG pulse에서 positive TG 증가 → BG update 감소 trend.

## TG inhibition

지원되는 LIF domain에서

\[
I_D^+ < I_D^-
\]

## Domain

지원하지 않는 voltage/width → error.

---

# 24. 권장 디렉터리 구조

```text
mpbtft/
├─ model.py
├─ parameters.py
├─ domains.py
│
├─ data/
│  ├─ README.md
│  ├─ relaxation/
│  ├─ bg_update/
│  ├─ tg_modulation/
│  ├─ lif_excitation/
│  └─ tg_inhibition/
│
├─ fitting/
│  ├─ fit_relaxation.py
│  ├─ fit_bg_update.py
│  ├─ fit_tg_modulation.py
│  ├─ fit_lif_excitation.py
│  └─ fit_tg_inhibition.py
│
├─ validation/
│  ├─ validate_fig3f.py
│  ├─ validate_sfig11.py
│  ├─ validate_fig3h.py
│  ├─ validate_fig3i.py
│  ├─ validate_lif_excitation.py
│  └─ validate_tg_inhibition.py
│
└─ tests/
   └─ test_mpbtft.py
```

기존 repository 구조가 이미 있다면 전체를 갈아엎지 말고 의미만 유지한다.

---

# 25. 구현 우선순위

## Milestone 1 — Data 정리

데이터를 네 그룹으로 분리한다.

```text
1. relaxation
2. BG update
3. TG reservoir modulation
4. LIF / TG inhibition
```

각각 raw source data인지 digitization인지 표시한다.

---

## Milestone 2 — Reservoir core

먼저

\[
U_{BG}(I_D)
\]

at 4 V / 100 μs / TG=0

와

\[
R(I_D,\Delta t)
\]

를 구현한다.

Fig.3h를 재현한다.

---

## Milestone 3 — TG reservoir modulation

\[
U_{BG}(I_D,V_{TG})
\]

로 확장한다.

Fig.3i를 재현한다.

**이 단계까지가 가장 중요한 v1 reservoir milestone이다.**

---

## Milestone 4 — LIF excitation

2.5 V / 500 μs BG protocol을 추가한다.

Fig.4b/SFig.18/19 trend를 검증한다.

---

## Milestone 5 — TG inhibition

5 V / 100 μs 대표 condition을 구현한다.

단, data가 부족하면 임의 parameter를 만들지 말고 limitation을 보고한다.

---

# 26. Definition of Done

## Architecture

- [ ] 하나의 `MPBTFT` class
- [ ] Reservoir와 LIF가 같은 class 사용
- [ ] event-driven/lazy relaxation
- [ ] figure lookup 없음
- [ ] parameter/data 분리
- [ ] domain check 존재

## Reservoir

- [ ] 4 V / 100 μs state-dependent BG update
- [ ] arbitrary event timing
- [ ] relaxation
- [ ] TG modulation
- [ ] Fig.3h validation
- [ ] Fig.3i validation

## LIF

- [ ] 2.5 V / 500 μs BG excitation
- [ ] leak
- [ ] representative TG inhibition 또는 데이터 부족을 명시적으로 보고
- [ ] firing logic은 core 밖

## Quality

- [ ] unit tests
- [ ] validation scripts
- [ ] validation metrics
- [ ] data provenance
- [ ] known limitations
- [ ] extrapolation 금지

---

# 27. 후반 연구를 고려한 구조적 요구사항

후반 연구의 핵심 아이디어:

```text
FeTFT readout evidence
          │
          ▼
      BG excitation
          │
          ▼
      MPBTFT LIF
          ▲
          │
      TG inhibition
          ▲
          │
Low-dimensional context
```

즉

\[
\boxed{\text{BG = task/evidence channel}}
\]

\[
\boxed{\text{TG = context/control channel}}
\]

로 사용한다.

BG는 가능하면 고정 amplitude/width의 excitatory pulse로 유지한다.

Context에 따라 TG inhibitory input을 조절한다.

따라서 `apply_tg_inhibition()`은 BG update와 분리된 독립 API로 설계한다.

---

# 28. 후반 연구에서 비교할 세 구조

## Baseline

```text
Context 없음
Readout → BG → LIF
```

## Comparison

```text
Context가 BG excitation을 조절
```

## Proposed

```text
Evidence → BG
Context  → TG inhibition
```

이 비교를 통해 Double-Gate를 이용한 evidence/context 분리가 실제 장점을 주는지 평가할 수 있어야 한다.

---

# 29. 향후 확장 순서

v1이 검증된 후에만 확장한다.

## v1.1

여러 BG amplitude:

```text
3.5 / 4.0 / 4.5 / 5.0 V
```

## v1.2

BG pulse width dependence

Supplementary Fig.12 활용.

## v1.3

\[
U_{BG}(I_D,V_{BG},t_{BG},V_{TG})
\]

joint interpolation.

## v1.4

TG inhibition amplitude/width generalization.

---

# 30. 알려진 핵심 한계

반드시 README에 포함한다.

1. `state = ID`는 behavioral approximation이다.
2. 동일 \(I_D\)가 완전히 동일한 microscopic state를 의미한다고 보장할 수 없다.
3. BG amplitude와 pulse width를 모든 조합에서 측정한 데이터가 없다.
4. TG inhibition은 arbitrary initial \(I_D\)에 대한 데이터가 특히 부족하다.
5. v1은 intra-pulse transient를 모델링하지 않는다.
6. 측정 범위 밖 extrapolation은 지원하지 않는다.
7. v1은 physical compact model이 아니라 experimentally grounded behavioral model이다.

---

# 31. Agent에게 그대로 전달할 핵심 지시

> **Do not broaden the scope.**  
> First implement a trustworthy, experimentally grounded MPBTFT v1 at the validated operating points.  
> Do not invent missing physical behavior.  
> Do not use figure-level lookup tables as the device model.  
> Use state transitions and lazy relaxation.  
> Keep every fitted parameter traceable to a paper figure, supplementary figure, or source-data file.  
> If a behavior cannot be quantitatively supported by the available data, explicitly report the missing evidence instead of fabricating a model.

---

# 32. 최종 제출물

개발 완료 후 다음을 제출한다.

1. MPBTFT core code
2. parameter/data files
3. fitting scripts
4. validation scripts
5. unit tests
6. validation plots
7. metric summary
8. README
9. Known Limitations
10. parameter provenance table

README 첫 부분에는 최소 다음을 표시한다.

```text
Validated
- Reservoir 4.0 V / 100 μs BG mode
- TG reservoir modulation within calibrated domain
- Event-driven volatile relaxation
- LIF representative excitation protocol

Limited / Experimental
- TG inhibitory transition

Not supported
- arbitrary amplitude/width generalization
- extrapolation beyond measured domain
- intra-pulse dynamics
```

---

# 33. 최종 성공 기준

이번 v1의 성공 기준은 **입력 parameter가 많은 것**이 아니다.

다음이 정확히 되는 것이 성공이다.

\[
\boxed{
\text{현재 } I_D
+
\text{경과시간}
+
\text{검증된 gate event}
\rightarrow
\text{다음 } I_D
}
\]

그리고 이 동일한 MPBTFT core를 이용하여

\[
\boxed{
\text{Physical Reservoir}
+
\text{LIF device core}
}
\]

를 모두 구성할 수 있어야 한다.

범용 voltage/width support는 이 기반이 검증된 뒤 추가한다.
