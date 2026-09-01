from sqlalchemy import Column, Integer, String, Text, Date, DateTime, Enum, ForeignKey, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base


class StatutProjet(str, enum.Enum):
    EN_ATTENTE = "EN_ATTENTE"
    EN_COURS   = "EN_COURS"
    TERMINE    = "TERMINE"
    SUSPENDU   = "SUSPENDU"


class StatutEtape(str, enum.Enum):
    A_FAIRE  = "A_FAIRE"
    EN_COURS = "EN_COURS"
    TERMINE  = "TERMINE"


class TypeChangement(str, enum.Enum):
    FEATURE      = "FEATURE"
    AMELIORATION = "AMELIORATION"
    BUGFIX       = "BUGFIX"
    AUTRE        = "AUTRE"


class StatutDeploiement(str, enum.Enum):
    PREVU   = "PREVU"
    EN_TEST = "EN_TEST"
    DEPLOYE = "DEPLOYE"


class Projet(Base):
    __tablename__ = "projets"

    id          = Column(Integer, primary_key=True, index=True)
    nom         = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    statut      = Column(Enum(StatutProjet, native_enum=False), default=StatutProjet.EN_COURS, nullable=False)
    responsable = Column(String(150), nullable=True)
    date_debut   = Column(Date, nullable=True)
    date_fin     = Column(Date, nullable=True)
    pourcentage  = Column(Integer, default=0, nullable=False)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    etapes      = relationship("ProjetEtape",       back_populates="projet", cascade="all, delete-orphan", order_by="ProjetEtape.ordre")
    changements = relationship("ProjetChangement",  back_populates="projet", cascade="all, delete-orphan", order_by="ProjetChangement.date.desc()")
    pays        = relationship("ProjetPays",         back_populates="projet", cascade="all, delete-orphan")


class ProjetEtape(Base):
    __tablename__ = "projet_etapes"

    id          = Column(Integer, primary_key=True, index=True)
    projet_id   = Column(Integer, ForeignKey("projets.id", ondelete="CASCADE"), nullable=False)
    titre       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    statut      = Column(Enum(StatutEtape, native_enum=False), default=StatutEtape.A_FAIRE, nullable=False)
    ordre       = Column(Integer, default=0, nullable=False)
    projet      = relationship("Projet", back_populates="etapes")


class ProjetChangement(Base):
    __tablename__ = "projet_changements"

    id          = Column(Integer, primary_key=True, index=True)
    projet_id   = Column(Integer, ForeignKey("projets.id", ondelete="CASCADE"), nullable=False)
    titre       = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    type        = Column(Enum(TypeChangement, native_enum=False), default=TypeChangement.FEATURE, nullable=False)
    date        = Column(Date, nullable=False)
    auteur      = Column(String(150), nullable=True)
    projet      = relationship("Projet", back_populates="changements")


class ProjetPays(Base):
    __tablename__ = "projet_pays"

    id               = Column(Integer, primary_key=True, index=True)
    projet_id        = Column(Integer, ForeignKey("projets.id", ondelete="CASCADE"), nullable=False)
    pays             = Column(String(100), nullable=False)
    date_deploiement = Column(Date, nullable=True)
    statut           = Column(Enum(StatutDeploiement, native_enum=False), default=StatutDeploiement.DEPLOYE, nullable=False)
    notes            = Column(Text, nullable=True)
    projet           = relationship("Projet", back_populates="pays")
