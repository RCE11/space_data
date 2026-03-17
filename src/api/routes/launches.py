from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from src.api.rate_limit import rate_limit
from src.api.schemas import LaunchResponse, PaginatedLaunches
from src.db.connection import get_db
from src.db.models import Launch

router = APIRouter()


@router.get("/upcoming", response_model=PaginatedLaunches)
def get_upcoming_launches(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _api_key=Depends(rate_limit),
):
    now = datetime.now(timezone.utc)
    base = db.query(Launch).filter(
        Launch.status == "scheduled",
        Launch.launch_date > now,
    )
    total = base.count()
    results = (
        base.options(joinedload(Launch.operator))
        .order_by(Launch.launch_date.asc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedLaunches(
        total=total,
        limit=limit,
        offset=offset,
        results=[LaunchResponse.model_validate(r) for r in results],
    )


@router.get("/history", response_model=PaginatedLaunches)
def get_launch_history(
    year: int | None = Query(default=None, ge=1957, le=2100),
    site: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    _api_key=Depends(rate_limit),
):
    base = db.query(Launch).filter(Launch.status == "launched")
    if year is not None:
        base = base.filter(
            Launch.launch_date >= datetime(year, 1, 1, tzinfo=timezone.utc),
            Launch.launch_date < datetime(year + 1, 1, 1, tzinfo=timezone.utc),
        )
    if site is not None:
        base = base.filter(Launch.launch_site.ilike(f"%{site}%"))
    total = base.count()
    results = (
        base.options(joinedload(Launch.operator))
        .order_by(Launch.launch_date.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return PaginatedLaunches(
        total=total,
        limit=limit,
        offset=offset,
        results=[LaunchResponse.model_validate(r) for r in results],
    )
