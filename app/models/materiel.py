from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base


class TypeMateriel(str, enum.Enum):
    ORDINATEUR_PORTABLE = "ORDINATEUR_PORTABLE"
    ORDINATEUR_FIXE     = "ORDINATEUR_FIXE"
    ECRAN               = "ECRAN"
    SOURIS              = "SOURIS"
    CLAVIER             = "CLAVIER"
    TELEPHONE           = "TELEPHONE"
    IMPRIMANTE          = "IMPRIMANTE"
    SWITCH              = "SWITCH"
    ROUTEUR             = "ROUTEUR"
    ONDULEUR            = "ONDULEUR"
    AUTRE               = "AUTRE"


class EtatMateriel(str, enum.Enum):
    NEUF         = "NEUF"
    BON          = "BON"
    USAGE        = "USAGE"
    DEFECTUEUX   = "DEFECTUEUX"


class StatutMateriel(str, enum.Enum):
    DISPONIBLE   = "DISPONIBLE"
    ATTRIBUE     = "ATTRIBUE"
    MAINTENANCE  = "MAINTENANCE"
    REFORME      = "REFORME"


class Materiel(Base):
    __tablename__ = "materiels"

    id              = Column(Integer, primary_key=True, index=True)
    type_materiel   = Column(Enum(TypeMateriel), nullable=False)
    marque          = Column(String(100), nullable=False)
    modele          = Column(String(150), nullable=True, default="")
    numero_serie    = Column(String(100), unique=True, nullable=True)
    adresse_ip      = Column(String(50), nullable=True)
    numero_bon_cmd  = Column(String(100), nullable=True)
    etat            = Column(Enum(EtatMateriel), default=EtatMateriel.BON)
    statut          = Column(Enum(StatutMateriel), default=StatutMateriel.DISPONIBLE, index=True)
    date_acquisition = Column(Date, nullable=True)
    description     = Column(Text, nullable=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())

    attributions = relationship("Attribution", back_populates="materiel")
