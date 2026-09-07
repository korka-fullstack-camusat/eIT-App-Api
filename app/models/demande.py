from sqlalchemy import Column, Integer, String, Text, DateTime, Enum, ForeignKey
from sqlalchemy.sql import func
import enum
from ..database import Base


class StatutDemande(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    VALIDEE    = "VALIDEE"
    REJETEE    = "REJETEE"


class DemandeAmelioration(Base):
    __tablename__ = "demandes_amelioration"

    id              = Column(Integer, primary_key=True, index=True)
    titre           = Column(String(300), nullable=False)
    description     = Column(Text, nullable=False)
    projet          = Column(String(200), nullable=True)   # nom libre du projet concerné
    demandeur       = Column(String(150), nullable=False)  # nom de l'utilisateur
    statut          = Column(Enum(StatutDemande, native_enum=False), default=StatutDemande.EN_ATTENTE, nullable=False)
    commentaire_dg  = Column(Text, nullable=True)          # commentaire du directeur lors de la décision
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
