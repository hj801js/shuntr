from __future__ import annotations

from pydantic import BaseModel, Field, ValidationError, field_validator
from pydantic_core import PydanticCustomError

from ..cables import CABLE_LIBRARY, get_cable_spec
from ..studies import DEFAULT_PROJECT_NAME, ChargingCurrentStudyInput


class StudyInputForm(BaseModel):
    project_name: str = Field(default=DEFAULT_PROJECT_NAME, min_length=1, max_length=120)
    line_voltage_kv: float = Field(default=154.0, gt=0, le=1000)
    frequency_hz: float = Field(default=60.0, gt=0, le=1000)
    cable_code: str = Field(default=CABLE_LIBRARY[0].code)
    capacitance_uf_per_km: float = Field(default=CABLE_LIBRARY[0].capacitance_uf_per_km, gt=0, le=100)
    route_length_km: float = Field(default=0.5, gt=0, le=1000)
    circuit_count: int = Field(default=1, gt=0, le=100)
    switching_limit_a: float = Field(default=400.0, gt=0, le=50000)
    compensation_mvar: float | None = Field(default=None, gt=0, le=100000)

    @field_validator("project_name")
    @classmethod
    def validate_project_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("프로젝트명은 비워둘 수 없습니다.")
        return value

    @field_validator("cable_code")
    @classmethod
    def validate_cable_code(cls, value: str) -> str:
        value = value.strip()
        try:
            get_cable_spec(value)
        except KeyError as exc:
            raise PydanticCustomError("cable_code", "지원하지 않는 케이블입니다.") from exc
        return value

    @classmethod
    def from_form_data(cls, form_data: dict[str, str]) -> "StudyInputForm":
        cleaned = dict(form_data)
        if cleaned.get("compensation_mvar", "").strip() == "":
            cleaned["compensation_mvar"] = None
        return cls.model_validate(cleaned)

    def to_study_input(self) -> ChargingCurrentStudyInput:
        cable = get_cable_spec(self.cable_code)
        return ChargingCurrentStudyInput(
            project_name=self.project_name,
            line_voltage_kv=self.line_voltage_kv,
            frequency_hz=self.frequency_hz,
            cable_name=cable.label,
            capacitance_uf_per_km=self.capacitance_uf_per_km,
            route_length_km=self.route_length_km,
            circuit_count=self.circuit_count,
            switching_limit_a=self.switching_limit_a,
            compensation_mvar=self.compensation_mvar,
        )


def default_form() -> StudyInputForm:
    default_cable = CABLE_LIBRARY[0]
    return StudyInputForm(
        project_name=DEFAULT_PROJECT_NAME,
        cable_code=default_cable.code,
        capacitance_uf_per_km=default_cable.capacitance_uf_per_km,
    )


def validation_errors_as_dict(exc: ValidationError) -> dict[str, str]:
    errors: dict[str, str] = {}
    for item in exc.errors():
        field = str(item.get("loc", ["form"])[0])
        errors[field] = item.get("msg", "입력값을 확인해 주세요.")
    return errors
