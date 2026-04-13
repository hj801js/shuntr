from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CableSpec:
    code: str
    label: str
    capacitance_uf_per_km: float

    def __post_init__(self) -> None:
        if self.capacitance_uf_per_km <= 0:
            raise ValueError("capacitance_uf_per_km must be positive")


CABLE_LIBRARY = (
    CableSpec(code="xlpe_400", label="154kV XLPE 400 mm²", capacitance_uf_per_km=0.14),
    CableSpec(code="xlpe_600", label="154kV XLPE 600 mm²", capacitance_uf_per_km=0.19),
    CableSpec(code="xlpe_630", label="154kV XLPE 630 mm²", capacitance_uf_per_km=0.189),
    CableSpec(code="xlpe_800", label="154kV XLPE 800 mm²", capacitance_uf_per_km=0.22),
    CableSpec(code="xlpe_1200", label="154kV XLPE 1200 mm²", capacitance_uf_per_km=0.24),
    CableSpec(code="xlpe_2000", label="154kV XLPE 2000 mm²", capacitance_uf_per_km=0.29),
    CableSpec(code="xlpe_2500", label="154kV XLPE 2500 mm²", capacitance_uf_per_km=0.31),
)

DEFAULT_CABLE = next(spec for spec in CABLE_LIBRARY if spec.code == "xlpe_1200")


def get_cable_spec(code: str) -> CableSpec:
    for spec in CABLE_LIBRARY:
        if spec.code == code:
            return spec
    raise KeyError(f"unknown cable code: {code}")
