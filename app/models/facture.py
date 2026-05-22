from sqlalchemy import Column, Integer, String, Date, DateTime, Text, ForeignKey, Numeric, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from ..database import Base


class FactureTelecom(Base):
    __tablename__ = "factures_telecom"

    id          = Column(Integer, primary_key=True, index=True)
    mois        = Column(Integer, nullable=False)   # 1-12
    annee       = Column(Integer, nullable=False)
    operateur   = Column(String(100), nullable=True)
    nom_fichier = Column(String(255), nullable=True)
    notes       = Column(Text, nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("mois", "annee", name="uq_facture_mois_annee"),)

    lignes = relationship("LigneFacture", back_populates="facture", cascade="all, delete-orphan")


class LigneFacture(Base):
    __tablename__ = "lignes_facture"

    id          = Column(Integer, primary_key=True, index=True)
    facture_id  = Column(Integer, ForeignKey("factures_telecom.id", ondelete="CASCADE"), nullable=False)
    sim_id      = Column(Integer, ForeignKey("numeros_sim.id"), nullable=True)   # null si non reconnu
    numero_raw  = Column(String(20), nullable=False)   # numéro tel que dans le fichier
    montant     = Column(Numeric(10, 2), nullable=False)
    non_reconnu = Column(String(1), default="N")       # "O" si introuvable dans le système

    facture = relationship("FactureTelecom", back_populates="lignes")
    sim     = relationship("NumeroSIM", back_populates="lignes_facture")
