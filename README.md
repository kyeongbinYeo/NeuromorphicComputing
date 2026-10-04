# FeTFT / MPBTFT behavioral model 스터디 시작안

## 목적과 현재 상태
일요일 스터디에서 코드 구조와 측정 데이터 연결 방식을 논의하기 위한 Python 스켈레톤입니다.
**논문 결과를 재현한 모델이 아닙니다.** 실제 곡선 수치 추출과 피팅은 아직 수행하지 않았습니다.
첨부된 본문을 확인했으며 Supplementary Information(SI)과 Source Data는 현재 패키지에 없습니다.
모든 실행 출력은 synthetic_demo입니다. 실험 데이터나 검증된 성능으로 사용하지 마세요.

## 시작하기
Python 3.10 이상 권장. 외부 라이브러리 없이 실행됩니다.

```bash
python demo.py
python -m unittest discover -s tests -v
```

Windows에서는 `python` 대신 `py`를 사용할 수 있습니다.
VS Code + 프로젝트별 가상환경 + Git 사용을 제안합니다.
Colab을 쓰는 팀원도 동일한 Python 모듈을 가져다 사용하고, 노트북은 실행/시각화 용도로 둡니다.
추후 곡선 피팅은 NumPy/SciPy, 시각화는 Matplotlib을 추가하면 됩니다.
PyTorch나 snnTorch는 소자 모델 확인 후 시스템 학습에 필요할 때 도입합니다.

## 논문 근거와 모델 선택
핵심 소자 모델 근거: Kim et al., Analog reservoir computing via ferroelectric mixed phase boundary transistors,
Nature Communications 15, 9147 (2024), DOI: 10.1038/s41467-024-53321-2.

- FeTFT: Fig. 2f,g의 LTP/LTD, Fig. 2h의 retention.
  본문 p.3에서 LTP/LTD 펄스 폭 10 us, PGM 3.5→4.1 V (0.04 V 증가),
  ERS -4.35→-5.1 V (-0.05 V 변화)를 기술합니다.
  해당 전압열을 일정 전압 반복 펄스와 혼동하면 안 됩니다. 정확한 개수/끝점은 원 데이터에서 확인합니다.
  p.3의 beta_p=0.04, beta_d=1.956은 식의 정의와 정규화 기준 확인 없이 모델 계수로 복사하지 않습니다.
  Fig. 2g cycle-to-cycle sigma/mu<0.025는 모든 상태/소자의 공통 Gaussian noise로 바로 적용하지 않습니다.
  retention은 약간의 감소를 포함하며, 현재 코드의 완전 유지 가정은 1차 근사입니다.
- MPBTFT: Fig. 3f는 I(t)=I0+A1 exp(-t/tau1)+A2 exp(-t/tau2)로 감소 곡선을 피팅합니다.
  본문 p.5는 피팅 파라미터가 Supplementary Fig. 11에 있다고 설명합니다.
  Fig. 3g 및 Supplementary Fig. 12는 TG가 BG programming 효율에 미치는 영향을 다룹니다.
  따라서 TG를 단순히 출력 전류에 곱하는 모델로만 두지 않습니다.
  Fig. 3h,i는 BG 4 V, 폭 100 us, 간격 3 ms의 4-bit 입력입니다.
  Fig. 3i 상단의 TG 스케줄은 5,3,1.5,0 V입니다. read bias와 TG의 시간 중첩은 SI에서 확인해야 합니다.
- 별도 첨부 Advanced Science의 3D Flash ECG 논문은 시스템 연결 참고자료입니다.
  3D Flash 수치와 FeTFT/MPBTFT 수치를 동일 소자의 파라미터로 섞지 않습니다.

## 구현한 범위
`models/devices.py`: 소자 상태와 상태 업데이트.
`configs/demo.json`: 계수와 펄스 조건. 코드 수정 없이 바꿀 수 있습니다.
`data/raw/`: 원본 보관. `data/processed/`: 단위 변환/정제 데이터.
`demo.py`: LTP/LTD 프로토콜 재생과 MPBTFT 1011 입력 예시.
`outputs/`: 실행 결과 및 당시 config 복사. `tests/`: 상태 유지/감쇠/범위 확인.

FeTFT의 첫 버전은 lookup table(측정값 표)입니다.
고정된 조건에서 얻은 LTP/LTD 곡선을 그대로 재생합니다.
임의의 중간 상태에서 LTP→LTD 전환하거나 임의 전압을 넣는 기능은 제공하지 않습니다.
그 기능은 전이 데이터가 확보된 뒤 별도로 구현해야 합니다.
read_current_A는 고정 read bias에서 I=G*VDS를 이용하며, 전체 I-V 선형성을 가정하지 않습니다.
현재 표는 실제 측정값 대신 예시값입니다.

MPBTFT는 fast/slow 두 상태가 각 시간상수로 감쇠합니다.
펄스에 따른 포화 업데이트와 TG gain의 지수식은 **구조 확인용 가정**입니다.
시간상수, baseline, 증가량, 포화전류, fast_fraction, TG 계수는 모두 예시값입니다.
4 V 이외 BG는 오류 처리합니다. 펄스 폭 비례식도 검증된 소자 법칙이 아닙니다.
펄스 구간 내부의 decay와 TG의 직접적인 read modulation은 현재 생략했습니다.
펄스 이벤트는 펄스 끝에서 상태를 업데이트하며 이후 idle gap을 명시적으로 계산합니다.
3 ms를 펄스 끝→다음 시작으로 해석한 것은 임시 가정입니다. SI와 일치시키세요.
LIF 발화/리셋 회로와 readout 학습은 이번 버전에 포함하지 않습니다.

## 데이터와 파라미터 관리 제안
시간 s, 전압 V, 전류 A, conductance S를 내부 단위로 통일합니다.
그림의 ms/us/uA를 변환할 때 원본 단위도 별도 기록합니다.
measurement_template.csv의 열을 기반으로 곡선 ID와 조건을 구분하세요.
미확인 read bias는 추측해 채우지 않고 비워둡니다.
G=I/VDS는 해당 read 조건에서의 유효 conductance로만 해석합니다.

실제 파라미터 파일을 만들 때 각 계수에 다음 메타데이터를 붙이는 방식을 제안합니다:
- value, unit, status: paper / digitized / fitted / assumed
- source: 논문 DOI, Figure/패널, SI 번호, 원본 파일 이름
- conditions: BG/TG, 펄스 폭, 간격, read bias, 초기 상태
- fit_dataset, fit_error, valid_range, extraction_uncertainty

예시 config의 metadata는 파일 전체를 synthetic으로 표시합니다.
논문에서 확인한 조건은 read_vds_V=0.1, reference_bg_V=4.0,
reference_width_s=100e-6 및 Fig. 3i TG 스케줄뿐입니다.
3 ms의 정확한 timing definition은 아직 확인하지 않았습니다.

## 일요일 논의 순서 (약 90분 제안)
1. 10분: 이번 목표를 Fig. 2 LTP/LTD와 Fig. 3f decay의 1차 근사로 정하기.
2. 15분: Python/VS Code/Colab, Git 저장소, SI/Source Data 확보 담당 정하기.
3. 15분: 측정 조건/단위/곡선 ID/출처 관리 규칙 정하기.
4. 30분: 스켈레톤 실행, FeTFT 표 교체, MPBTFT decay 계수 연결 실습.
5. 15분: 실제 곡선과 예측을 겹쳐 보고 오차와 미지원 조건 기록하기.
6. 5분: 다음 주까지 추출/피팅/검증 담당과 완료 기준 정하기.

Source Data를 먼저 확인하고 없으면 그래프 좌표를 추출합니다.
Fig. 3f 단일 펄스 감소를 먼저 피팅한 뒤 Fig. 3g 반복 펄스/TG를 검증합니다.
단일 펄스 피팅 성공만으로 반복 입력 성능을 검증했다고 판단하지 않습니다.
Fig. 3h,i의 16개 입력열을 모두 비교할 때 reset 조건과 final sample 시간을 고정하세요.
피팅한 곡선과 검증할 곡선을 구분하고 조건별 RMSE, baseline, peak,
최종 상태 및 시간상수를 비교합니다. 합격 기준은 추출 오차를 본 뒤 정합니다.
두 지수 감쇠의 계수는 서로 바뀌어도 같으므로 tau_fast<tau_slow 제약을 두세요.
감쇠 데이터만으로 TG programming 효율이나 모든 전압 의존성이 정해지지는 않습니다.

## 교수님께 추가 요청을 검토할 때
먼저 SI/Source Data를 확인한 뒤 공개 자료에 없는 부분만 요청합니다.
- LTP/LTD 원본 pulse schedule와 read 조건, 중간 상태에서의 전이 데이터.
- VPGM/VTG 조건별 decay 계수와 반복 펄스 응답, sampling 시점, 초기화 조건.
- device-to-device와 cycle-to-cycle 구분 데이터.
- 코드가 공유되면 상태변수/단위/시간 업데이트 순서/학습과 readout 인터페이스 확인.
본문 p.10의 Code availability는 관련 코드가 본문/SI에 있고 기타 코드는
교신저자에게 요청 가능하다고 명시합니다. 실제 파일 포함 여부는 아직 확인하지 않았습니다.

## 지금 준비해갈 메모
“소자 모델, 입력 프로토콜, 데이터, 시스템 학습을 분리하고 싶다.
FeTFT는 고정 조건 LTP/LTD 표부터, MPBTFT는 두 지수 감쇠부터 구현하자.
실측/피팅/가정 파라미터를 표시하고, 첫 완료 기준은 분류 정확도가 아니라
소자 측정 곡선을 조건에 맞게 따라가는 것으로 잡자.”
