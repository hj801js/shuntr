from math import isclose

import pytest

from shunt_reactor_engineering import ChargingCurrentStudyInput, calculate_charging_current_per_km, evaluate_study


def test_calculate_charging_current_per_km_matches_reference_formula() -> None:
    current_per_km = calculate_charging_current_per_km(
        voltage_kv=154.0,
        capacitance_uf_per_km=0.24,
        frequency_hz=60.0,
    )

    assert isclose(current_per_km, 8.04456294, rel_tol=1e-6)


def test_evaluate_study_returns_expected_summary_values() -> None:
    study_input = ChargingCurrentStudyInput(
        project_name="재생에너지 연계 변전소",
        line_voltage_kv=154.0,
        frequency_hz=60.0,
        cable_name="154kV XLPE 1200 mm²",
        capacitance_uf_per_km=0.24,
        route_length_km=0.5,
        circuit_count=1,
        switching_limit_a=400.0,
    )

    result = evaluate_study(study_input)

    assert result.total_length_km == pytest.approx(0.5)
    assert result.charging_current_a == pytest.approx(4.02228147, rel=1e-6)
    assert result.reactive_power_mvar == pytest.approx(1.07288656, rel=1e-6)
    assert result.recommended_compensation_mvar == 2
    assert result.switching_limit_exceeded is False


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("project_name", " "),
        ("line_voltage_kv", 0.0),
        ("frequency_hz", 0.0),
        ("capacitance_uf_per_km", 0.0),
        ("route_length_km", 0.0),
        ("circuit_count", 0),
        ("switching_limit_a", 0.0),
    ],
)
def test_study_input_validation(field_name: str, value: object) -> None:
    payload = {
        "project_name": "재생에너지 연계 변전소",
        "line_voltage_kv": 154.0,
        "frequency_hz": 60.0,
        "cable_name": "154kV XLPE 1200 mm²",
        "capacitance_uf_per_km": 0.24,
        "route_length_km": 0.5,
        "circuit_count": 1,
        "switching_limit_a": 400.0,
    }
    payload[field_name] = value

    with pytest.raises(ValueError):
        ChargingCurrentStudyInput(**payload)
