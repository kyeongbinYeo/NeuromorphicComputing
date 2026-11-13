"""
MPBTFT v1 파라미터 (모드별) 와 JSON 입출력.

숫자는 코드에 넣지 않고 params/v1_params.json 에서 읽는다.
각 값의 출처(그림, 방법, 스크립트)는 같은 JSON의 "provenance" 와 data/README.md 에 있다.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

DEFAULT_PARAMS_PATH = Path(__file__).resolve().parent / "params" / "v1_params.json"


@dataclass
class Table:
    """단조성을 보존하는 PCHIP 보간 표. x 범위 밖은 호출 측에서 다룬다 (외삽하지 않음)."""
    x: list
    y: list

    def __post_init__(self):
        self.x = [float(v) for v in self.x]
        self.y = [float(v) for v in self.y]
        if len(self.x) != len(self.y) or len(self.x) < 2:
            raise ValueError("Table needs at least two (x, y) points of equal length.")
        if any(b <= a for a, b in zip(self.x, self.x[1:])):
            raise ValueError("Table x must be strictly increasing.")
        self._f = PchipInterpolator(np.array(self.x), np.array(self.y), extrapolate=False)

    @property
    def lo(self) -> float:
        return self.x[0]

    @property
    def hi(self) -> float:
        return self.x[-1]

    def contains(self, v: float, tol: float = 0.0) -> bool:
        return self.lo - tol <= v <= self.hi + tol

    def __call__(self, v: float) -> float:
        """범위 밖이면 가장자리 값 (호출 측이 범위 검사를 먼저 한다)."""
        v = min(max(float(v), self.lo), self.hi)
        return float(self._f(v))

    def to_dict(self):
        return {"x": self.x, "y": self.y}


@dataclass
class RelaxationParams:
    """I_D = baseline + fast + slow,  fast·e^(−t/τ_fast) + slow·e^(−t/τ_slow).

    tau_slow_s 는 사건(펄스) 직후의 초과 전류(excess = I_D − baseline)에 따라 표에서 고르고,
    다음 사건까지 고정한다.
    """
    fast_share: float          # 펄스로 생긴 증가분 중 fast 성분 몫 (0..1)
    tau_fast_s: float
    tau_slow_s: Table          # x = excess (A), y = τ_slow (s)


@dataclass
class BGUpdateParams:
    voltage_V: float
    width_s: float
    delta_id_A: Table          # x = 펄스 직전 I_D (A), y = 펄스로 인한 I_D 증가 (A)


@dataclass
class TGInhibitionParams:
    voltage_V: float
    width_s: float
    retention: float           # 억제 펄스 1개 뒤 남는 초과 전류 비율 (best-fit 값, 식별성 낮음)
    id_pre_domain_A: list      # 보정에 쓰인 펄스 직전 I_D 범위 [lo, hi]
    status: str = "experimental"
    enabled_by_default: bool = False   # False면 MPBTFT(..., allow_experimental=True)일 때만 동작
    note: str = ""


@dataclass
class ModeParams:
    name: str
    baseline_A: float
    relaxation: RelaxationParams
    bg_update: BGUpdateParams
    tg_modulation: Table | None = None          # reservoir: x = V_TG, y = BG 증가량 배율
    on_state_offset_A: float | None = None      # LIF: 흥분 펄스 중 전류 − 휴지 바이어스 전류
    tg_inhibition: TGInhibitionParams | None = None


@dataclass
class MPBTFTParams:
    reservoir: ModeParams
    lif: ModeParams
    provenance: dict = field(default_factory=dict)
    version: str = "v1"

    def mode(self, name: str) -> ModeParams:
        if name == "reservoir":
            return self.reservoir
        if name == "lif":
            return self.lif
        raise ValueError(f"Unknown mode '{name}'")

    # --- JSON ---------------------------------------------------------------
    @staticmethod
    def _mode_to_dict(m: ModeParams) -> dict:
        d = {
            "baseline_A": m.baseline_A,
            "relaxation": {
                "fast_share": m.relaxation.fast_share,
                "tau_fast_s": m.relaxation.tau_fast_s,
                "tau_slow_s": {"x_excess_A": m.relaxation.tau_slow_s.x, "y_s": m.relaxation.tau_slow_s.y},
            },
            "bg_update": {
                "voltage_V": m.bg_update.voltage_V,
                "width_s": m.bg_update.width_s,
                "delta_id_A": {"x_id_pre_A": m.bg_update.delta_id_A.x, "y_A": m.bg_update.delta_id_A.y},
            },
        }
        if m.tg_modulation is not None:
            d["tg_modulation"] = {"x_vtg_V": m.tg_modulation.x, "y_gain": m.tg_modulation.y}
        if m.on_state_offset_A is not None:
            d["on_state_offset_A"] = m.on_state_offset_A
        if m.tg_inhibition is not None:
            d["tg_inhibition"] = asdict(m.tg_inhibition)
        return d

    @staticmethod
    def _mode_from_dict(name: str, d: dict) -> ModeParams:
        r = d["relaxation"]
        b = d["bg_update"]
        tgm = d.get("tg_modulation")
        tgi = d.get("tg_inhibition")
        return ModeParams(
            name=name,
            baseline_A=float(d["baseline_A"]),
            relaxation=RelaxationParams(
                fast_share=float(r["fast_share"]),
                tau_fast_s=float(r["tau_fast_s"]),
                tau_slow_s=Table(r["tau_slow_s"]["x_excess_A"], r["tau_slow_s"]["y_s"]),
            ),
            bg_update=BGUpdateParams(
                voltage_V=float(b["voltage_V"]),
                width_s=float(b["width_s"]),
                delta_id_A=Table(b["delta_id_A"]["x_id_pre_A"], b["delta_id_A"]["y_A"]),
            ),
            tg_modulation=Table(tgm["x_vtg_V"], tgm["y_gain"]) if tgm else None,
            on_state_offset_A=float(d["on_state_offset_A"]) if "on_state_offset_A" in d else None,
            tg_inhibition=TGInhibitionParams(**tgi) if tgi else None,
        )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "units": "SI (s, A, V)",
            "modes": {"reservoir": self._mode_to_dict(self.reservoir), "lif": self._mode_to_dict(self.lif)},
            "provenance": self.provenance,
        }

    def save(self, path=DEFAULT_PARAMS_PATH) -> None:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    @classmethod
    def load(cls, path=DEFAULT_PARAMS_PATH) -> "MPBTFTParams":
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(
            reservoir=cls._mode_from_dict("reservoir", d["modes"]["reservoir"]),
            lif=cls._mode_from_dict("lif", d["modes"]["lif"]),
            provenance=d.get("provenance", {}),
            version=d.get("version", "v1"),
        )
