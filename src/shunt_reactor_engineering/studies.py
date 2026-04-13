from __future__ import annotations

from dataclasses import dataclass
from math import ceil, pi, sqrt

from .cables import DEFAULT_CABLE

DEFAULT_PROJECT_NAME = "재생에너지 연계 변전소"


@dataclass(frozen=True, slots=True)
class ChargingCurrentStudyInput:
    project_name: str = DEFAULT_PROJECT_NAME
    line_voltage_kv: float = 154.0
    frequency_hz: float = 60.0
    cable_name: str = DEFAULT_CABLE.label
    capacitance_uf_per_km: float = DEFAULT_CABLE.capacitance_uf_per_km
    route_length_km: float = 0.5
    circuit_count: int = 1
    switching_limit_a: float = 400.0
    compensation_mvar: float | None = None

    def __post_init__(self) -> None:
        if not self.project_name.strip():
            raise ValueError("project_name must not be blank")
        if self.line_voltage_kv <= 0:
            raise ValueError("line_voltage_kv must be positive")
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")
        if self.capacitance_uf_per_km <= 0:
            raise ValueError("capacitance_uf_per_km must be positive")
        if self.route_length_km <= 0:
            raise ValueError("route_length_km must be positive")
        if self.circuit_count <= 0:
            raise ValueError("circuit_count must be positive")
        if self.switching_limit_a <= 0:
            raise ValueError("switching_limit_a must be positive")
        if self.compensation_mvar is not None and self.compensation_mvar <= 0:
            raise ValueError("compensation_mvar must be positive when provided")


@dataclass(frozen=True, slots=True)
class ChargingCurrentStudyResult:
    study_input: ChargingCurrentStudyInput
    total_length_km: float
    charging_current_per_km_a: float
    charging_current_a: float
    reactive_power_mvar: float
    recommended_compensation_mvar: float
    switching_margin_a: float
    switching_utilization_pct: float
    max_total_length_km: float
    max_route_length_per_circuit_km: float
    switching_limit_exceeded: bool


def calculate_charging_current_per_km(
    voltage_kv: float,
    capacitance_uf_per_km: float,
    frequency_hz: float = 60.0,
) -> float:
    if voltage_kv <= 0 or capacitance_uf_per_km <= 0 or frequency_hz <= 0:
        raise ValueError("voltage_kv, capacitance_uf_per_km, and frequency_hz must be positive")
    return (2.0 * pi * frequency_hz * capacitance_uf_per_km * voltage_kv) / (sqrt(3.0) * 1_000.0)


def evaluate_study(study_input: ChargingCurrentStudyInput) -> ChargingCurrentStudyResult:
    charging_current_per_km_a = calculate_charging_current_per_km(
        voltage_kv=study_input.line_voltage_kv,
        capacitance_uf_per_km=study_input.capacitance_uf_per_km,
        frequency_hz=study_input.frequency_hz,
    )
    total_length_km = study_input.route_length_km * study_input.circuit_count
    charging_current_a = charging_current_per_km_a * total_length_km
    reactive_power_mvar = sqrt(3.0) * study_input.line_voltage_kv * charging_current_a * 1e-3
    recommended_compensation_mvar = (
        float(study_input.compensation_mvar)
        if study_input.compensation_mvar is not None
        else float(ceil(reactive_power_mvar))
    )
    switching_margin_a = study_input.switching_limit_a - charging_current_a
    switching_utilization_pct = (charging_current_a / study_input.switching_limit_a) * 100.0
    max_total_length_km = study_input.switching_limit_a / charging_current_per_km_a
    max_route_length_per_circuit_km = max_total_length_km / study_input.circuit_count

    return ChargingCurrentStudyResult(
        study_input=study_input,
        total_length_km=total_length_km,
        charging_current_per_km_a=charging_current_per_km_a,
        charging_current_a=charging_current_a,
        reactive_power_mvar=reactive_power_mvar,
        recommended_compensation_mvar=recommended_compensation_mvar,
        switching_margin_a=switching_margin_a,
        switching_utilization_pct=switching_utilization_pct,
        max_total_length_km=max_total_length_km,
        max_route_length_per_circuit_km=max_route_length_per_circuit_km,
        switching_limit_exceeded=charging_current_a > study_input.switching_limit_a,
    )
