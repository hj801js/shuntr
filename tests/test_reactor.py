from math import isclose

import pytest

from shunt_reactor_engineering import ShuntReactorRating, summarize_rating


def test_rating_outputs_expected_values() -> None:
    rating = ShuntReactorRating(voltage_kv=154.0, reactive_power_mvar=50.0, frequency_hz=60.0)

    assert isclose(rating.line_current_a, 187.4513861005, rel_tol=1e-6)
    assert isclose(rating.reactance_ohm, 474.32, rel_tol=1e-6)
    assert isclose(rating.inductance_h, 1.2581728768, rel_tol=1e-6)


def test_summary_includes_core_fields() -> None:
    summary = summarize_rating(voltage_kv=154.0, reactive_power_mvar=50.0)

    assert summary["voltage_kv"] == pytest.approx(154.0)
    assert summary["reactance_ohm"] == pytest.approx(474.32)


@pytest.mark.parametrize(
    ("voltage_kv", "reactive_power_mvar", "frequency_hz"),
    [
        (0.0, 10.0, 60.0),
        (154.0, 0.0, 60.0),
        (154.0, 10.0, 0.0),
    ],
)
def test_invalid_inputs_raise_value_error(
    voltage_kv: float, reactive_power_mvar: float, frequency_hz: float
) -> None:
    with pytest.raises(ValueError):
        ShuntReactorRating(
            voltage_kv=voltage_kv,
            reactive_power_mvar=reactive_power_mvar,
            frequency_hz=frequency_hz,
        )
