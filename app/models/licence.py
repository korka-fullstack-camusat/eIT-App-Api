from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class Licence(Base):
    __tablename__ = "licences"

    id              = Column(Integer, primary_key=True, index=True)
    logiciel        = Column(String(200), nullable=False)
    editeur         = Column(String(150), nullable=True)
    version         = Column(String(50),  nullable=True)
    cle_licence     = Column(String(255), nullable=True)
    date_achat      = Column(Date, nullable=True)
    date_expiration = Column(Date, nullable=True)
    nb_postes_max   = Column(Integer, nullable=True)
    notes           = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    attributions    = relationship("LicenceAttribution", back_populates="licence", cascade="all, delete-orphan")


class LicenceAttribution(Base):
    __tablename__ = "licence_attributions"

    id                 = Column(Integer, primary_key=True, index=True)
    licence_id         = Column(Integer, ForeignKey("licences.id"), nullable=False)
    employee_nom       = Column(String(150), nullable=False)
    employee_prenom    = Column(String(150), nullable=True)
    employee_matricule = Column(String(50),  nullable=True)
    employee_service   = Column(String(150), nullable=True)
    materiel_id        = Column(Integer, nullable=True)
    date_attribution   = Column(Date, nullable=False)
    notes              = Column(Text, nullable=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now())

    licence = relationship("Licence", back_populates="attributions")
