from __future__ import annotations

from dataclasses import dataclass
from math import pi, sqrt


@dataclass(frozen=True, slots=True)
class ShuntReactorRating:
    """Basic electrical quantities for a three-phase shunt reactor."""

    voltage_kv: float
    reactive_power_mvar: float
    frequency_hz: float = 60.0

    def __post_init__(self) -> None:
        if self.voltage_kv <= 0:
            raise ValueError("voltage_kv must be positive")
        if self.reactive_power_mvar <= 0:
            raise ValueError("reactive_power_mvar must be positive")
        if self.frequency_hz <= 0:
            raise ValueError("frequency_hz must be positive")

    @property
    def voltage_v(self) -> float:
        return self.voltage_kv * 1_000.0

    @property
    def reactive_power_var(self) -> float:
        return self.reactive_power_mvar * 1_000_000.0

    @property
    def phase_voltage_v(self) -> float:
        return self.voltage_v / sqrt(3.0)

    @property
    def line_current_a(self) -> float:
        return self.reactive_power_var / (sqrt(3.0) * self.voltage_v)

    @property
    def reactance_ohm(self) -> float:
        return (self.voltage_v ** 2) / self.reactive_power_var

    @property
    def inductance_h(self) -> float:
        return self.reactance_ohm / (2.0 * pi * self.frequency_hz)


def summarize_rating(voltage_kv: float, reactive_power_mvar: float, frequency_hz: float = 60.0) -> dict[str, float]:
    rating = ShuntReactorRating(
        voltage_kv=voltage_kv,
        reactive_power_mvar=reactive_power_mvar,
        frequency_hz=frequency_hz,
    )
    return {
        "voltage_kv": rating.voltage_kv,
        "reactive_power_mvar": rating.reactive_power_mvar,
        "frequency_hz": rating.frequency_hz,
        "line_current_a": rating.line_current_a,
        "reactance_ohm": rating.reactance_ohm,
        "inductance_h": rating.inductance_h,
    }
