from sqlalchemy import Column, Integer, String, Date, Numeric, DateTime
from sqlalchemy.sql import func
from ..database import Base


class FlotteMobile(Base):
    """SIMs employés — onglet ORANGE-mobiles."""
    __tablename__ = "flotte_mobile"

    id                = Column(Integer, primary_key=True, index=True)
    matricule         = Column(String(50),  nullable=True)
    beneficiaire      = Column(String(150), nullable=True)
    service           = Column(String(100), nullable=True)
    business_line     = Column(String(50),  nullable=True)
    fonction          = Column(String(150), nullable=True)
    numero_ligne      = Column(String(30),  nullable=False, index=True)
    engagement        = Column(Integer,     nullable=True)
    date_activation   = Column(Date,        nullable=True)
    formule           = Column(String(150), nullable=True)
    forfait_internet  = Column(String(100), nullable=True)
    total_positionne  = Column(Numeric(10, 2), nullable=True)
    created_at        = Column(DateTime(timezone=True), server_default=func.now())
    updated_at        = Column(DateTime(timezone=True), onupdate=func.now())


class FlotteGps(Base):
    """SIMs GPS véhicules — onglet ORANGE-Gps_Vehicules."""
    __tablename__ = "flotte_gps"

    id              = Column(Integer, primary_key=True, index=True)
    numero_sim      = Column(String(30),  nullable=False, index=True)
    engagement      = Column(Integer,     nullable=True)
    date_activation = Column(Date,        nullable=True)
    immatriculation = Column(String(30),  nullable=True)
    modele          = Column(String(100), nullable=True)
    imei            = Column(String(30),  nullable=True)
    facturation     = Column(Numeric(10, 2), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


class FlotteRmsOrange(Base):
    """SIMs RMS réseau Orange — onglet RMS_Orange."""
    __tablename__ = "flotte_rms_orange"

    id              = Column(Integer, primary_key=True, index=True)
    numero          = Column(String(30),  nullable=False, index=True)
    engagement      = Column(Integer,     nullable=True)
    date_activation = Column(Date,        nullable=True)
    imsi            = Column(String(20),  nullable=True)
    site_id         = Column(String(50),  nullable=True)
    nom_site        = Column(String(150), nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


class FlotteRmsFree(Base):
    """SIMs RMS réseau Free — onglet RMS_Free."""
    __tablename__ = "flotte_rms_free"

    id         = Column(Integer, primary_key=True, index=True)
    numero     = Column(String(30),  nullable=False, index=True)
    imsi       = Column(String(20),  nullable=True)
    site_id    = Column(String(50),  nullable=True)
    nom_site   = Column(String(150), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
