"""
Fig.3i 검증 (TG 5.0 → 3.0 → 1.5 → 0 V): 같은 비트열을 MPBTFT 상태 전이로 시뮬레이션해서 그림 데이터와 비교한다.
결과를 그림에서 찾아 돌려주는 표(lookup)는 쓰지 않는다.

    python validation/validate_fig3i.py
"""
from reservoir_states import validate

if __name__ == "__main__":
    validate("fig3i")
