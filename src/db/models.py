from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Operator(Base):
    __tablename__ = "operators"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False, unique=True)
    country = Column(String(100))
    operator_type = Column(String(50))  # commercial, government, military
    website = Column(String(500))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    satellites = relationship("Satellite", back_populates="operator")
    launches = relationship("Launch", back_populates="operator")


class Launch(Base):
    __tablename__ = "launches"

    id = Column(Integer, primary_key=True)
    launch_date = Column(DateTime)
    launch_site = Column(String(255))
    vehicle = Column(String(255))  # Falcon 9, Ariane 6, etc.
    operator_id = Column(Integer, ForeignKey("operators.id"))
    status = Column(String(50))  # scheduled, launched, failed, scrubbed
    payload_description = Column(Text)
    source = Column(String(100))  # space_track, faa, manual
    source_id = Column(String(255))  # ID from the original source
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    operator = relationship("Operator", back_populates="launches")
    satellites = relationship("Satellite", back_populates="launch")

    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_launch_source"),
    )


class Satellite(Base):
    __tablename__ = "satellites"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    norad_id = Column(Integer, unique=True)  # NORAD catalog number
    intl_designator = Column(String(20))  # e.g. 2024-001A
    operator_id = Column(Integer, ForeignKey("operators.id"))
    launch_id = Column(Integer, ForeignKey("launches.id"))
    object_type = Column(String(50))  # PAYLOAD, DEBRIS, ROCKET BODY, UNKNOWN
    purpose = Column(String(100))  # communications, earth observation, navigation
    constellation = Column(String(100))  # Starlink, OneWeb, Kuiper
    status = Column(String(50))  # active, inactive, decayed, deorbited
    source = Column(String(100))
    source_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    operator = relationship("Operator", back_populates="satellites")
    launch = relationship("Launch", back_populates="satellites")
    orbit = relationship("Orbit", back_populates="satellite", uselist=False)


class Orbit(Base):
    __tablename__ = "orbits"

    id = Column(Integer, primary_key=True)
    satellite_id = Column(Integer, ForeignKey("satellites.id"), unique=True)
    orbit_class = Column(String(10))  # LEO, MEO, GEO, HEO, SSO
    apogee_km = Column(Float)
    perigee_km = Column(Float)
    inclination_deg = Column(Float)
    period_min = Column(Float)
    epoch = Column(DateTime)  # when this orbital data was measured
    tle_line1 = Column(String(70))
    tle_line2 = Column(String(70))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    satellite = relationship("Satellite", back_populates="orbit")
