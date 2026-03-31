from datetime import datetime

from pydantic import BaseModel


class OperatorSummary(BaseModel):
    id: int
    name: str
    country: str | None

    model_config = {"from_attributes": True}


class LaunchResponse(BaseModel):
    id: int
    launch_date: datetime | None
    launch_site: str | None
    vehicle: str | None
    status: str | None
    payload_description: str | None
    launch_window: str | None
    operator: OperatorSummary | None

    model_config = {"from_attributes": True}


class PaginatedLaunches(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[LaunchResponse]


class OrbitSummary(BaseModel):
    orbit_class: str | None
    apogee_km: float | None
    perigee_km: float | None
    inclination_deg: float | None
    period_min: float | None

    model_config = {"from_attributes": True}


class SatelliteResponse(BaseModel):
    id: int
    name: str
    norad_id: int | None
    intl_designator: str | None
    object_type: str | None
    purpose: str | None
    constellation: str | None
    status: str | None
    operator: OperatorSummary | None
    orbit: OrbitSummary | None

    model_config = {"from_attributes": True}


class PaginatedSatellites(BaseModel):
    total: int
    limit: int
    offset: int
    results: list[SatelliteResponse]
