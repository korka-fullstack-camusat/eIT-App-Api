from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base


class StatutAttribution(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    CLOTUREE  = "CLOTUREE"


class MotifRestitution(str, enum.Enum):
    DEPART          = "DEPART"
    CHANGEMENT      = "CHANGEMENT"
    PANNE           = "PANNE"
    FIN_CONTRAT     = "FIN_CONTRAT"
    AUTRE           = "AUTRE"


class Attribution(Base):
    __tablename__ = "attributions"

    id              = Column(Integer, primary_key=True, index=True)
    materiel_id     = Column(Integer, ForeignKey("materiels.id"), nullable=False)
    # Référence employé depuis eRh-App (pas de FK locale)
    employee_id     = Column(Integer, nullable=False, index=True)
    employee_nom    = Column(String(200), nullable=False)
    employee_prenom = Column(String(200), nullable=True)
    employee_matricule = Column(String(50), nullable=True)
    employee_service   = Column(String(200), nullable=True)
    employee_poste     = Column(String(200), nullable=True)

    date_attribution  = Column(Date, nullable=False)
    etat_remise       = Column(String(50), nullable=True)
    statut            = Column(Enum(StatutAttribution), default=StatutAttribution.ACTIVE, index=True)
    notes             = Column(Text, nullable=True)

    # Restitution
    date_restitution  = Column(Date, nullable=True)
    motif_restitution = Column(Enum(MotifRestitution), nullable=True)
    notes_restitution = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    materiel = relationship("Materiel", back_populates="attributions")
