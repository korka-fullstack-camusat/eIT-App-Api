from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base


class StatutTache(str, enum.Enum):
    A_FAIRE    = "A_FAIRE"
    EN_COURS   = "EN_COURS"
    TERMINE    = "TERMINE"
    ANNULE     = "ANNULE"


class PrioriteTache(str, enum.Enum):
    BASSE   = "BASSE"
    NORMALE = "NORMALE"
    HAUTE   = "HAUTE"
    URGENTE = "URGENTE"


class Tache(Base):
    __tablename__ = "taches"

    id              = Column(Integer, primary_key=True, index=True)
    titre           = Column(String(200), nullable=False)
    description     = Column(Text, nullable=True)
    date_planifiee  = Column(Date, nullable=False)
    date_fin        = Column(Date, nullable=True)
    statut          = Column(Enum(StatutTache,   native_enum=False), default=StatutTache.A_FAIRE,   nullable=False)
    priorite        = Column(Enum(PrioriteTache, native_enum=False), default=PrioriteTache.NORMALE, nullable=False)
    responsable     = Column(String(150), nullable=True)
    notes           = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())


class Checklist(Base):
    __tablename__ = "checklists"

    id          = Column(Integer, primary_key=True, index=True)
    nom         = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    responsable = Column(String(150), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    items       = relationship("ChecklistItem", back_populates="checklist", cascade="all, delete-orphan", order_by="ChecklistItem.ordre")


class ChecklistItem(Base):
    __tablename__ = "checklist_items"

    id           = Column(Integer, primary_key=True, index=True)
    checklist_id = Column(Integer, ForeignKey("checklists.id", ondelete="CASCADE"), nullable=False)
    titre        = Column(String(300), nullable=False)
    cochee       = Column(Boolean, default=False, nullable=False)
    ordre        = Column(Integer, default=0, nullable=False)
    checklist    = relationship("Checklist", back_populates="items")
