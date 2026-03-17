from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from src.api.rate_limit import rate_limit
from src.api.schemas import PaginatedSatellites, SatelliteResponse
from src.db.connection import get_db
from src.db.models import Operator, Orbit, Satellite

router = APIRouter()


@router.get("/by-operator", response_model=PaginatedSatellites)
def get_satellites_by_operator(
    operator: str = Query(description="Operator name (partial match)"),
    object_type: str | None = Query(default=None, description="PAYLOAD, DEBRIS, ROCKET BODY, or UNKNOWN"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _api_key=Depends(rate_limit),
):
    base = (
        db.query(Satellite)
        .join(Satellite.operator)
        .filter(Operator.name.ilike(f"%{operator}%"))
    )
    if object_type is not None:
        base = base.filter(Satellite.object_type == object_type.upper())
    total = base.count()
    results = (
        base.options(joinedload(Satellite.operator), joinedload(Satellite.orbit))
        .order_by(Satellite.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedSatellites(
        total=total,
        limit=limit,
        offset=offset,
        results=[SatelliteResponse.model_validate(r) for r in results],
    )


@router.get("/by-orbit", response_model=PaginatedSatellites)
def get_satellites_by_orbit(
    orbit_class: str = Query(description="Orbit classification: LEO, MEO, GEO, HEO, or SSO"),
    operator: str | None = Query(default=None, description="Filter by operator name (partial match)"),
    object_type: str | None = Query(default=None, description="PAYLOAD, DEBRIS, ROCKET BODY, or UNKNOWN"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _api_key=Depends(rate_limit),
):
    base = (
        db.query(Satellite)
        .join(Satellite.orbit)
        .filter(Orbit.orbit_class == orbit_class.upper())
    )
    if operator is not None:
        base = base.join(Satellite.operator).filter(Operator.name.ilike(f"%{operator}%"))
    if object_type is not None:
        base = base.filter(Satellite.object_type == object_type.upper())
    total = base.count()
    results = (
        base.options(joinedload(Satellite.operator), joinedload(Satellite.orbit))
        .order_by(Satellite.name.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedSatellites(
        total=total,
        limit=limit,
        offset=offset,
        results=[SatelliteResponse.model_validate(r) for r in results],
    )
