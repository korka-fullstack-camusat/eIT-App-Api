from sqlalchemy import Column, Integer, String, Date, DateTime, Enum, Text, ForeignKey, Numeric, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from ..database import Base


class CategorieSimEnum(str, enum.Enum):
    EMPLOYE      = "EMPLOYE"       # Ligne personnelle employé
    M2M_SITE     = "M2M_SITE"     # Ligne M2M sur site
    M2M_VEHICULE = "M2M_VEHICULE"  # Ligne M2M véhicule GPS


class StatutSimEnum(str, enum.Enum):
    ACTIVE    = "ACTIVE"
    INACTIVE  = "INACTIVE"
    SUSPENDUE = "SUSPENDUE"
    RESILIE   = "RESILIE"
    CEDE      = "CEDE"


class SiteGSM(Base):
    __tablename__ = "sites_gsm"

    id           = Column(Integer, primary_key=True, index=True)
    code_site    = Column(String(50),  nullable=True, index=True)
    imsi         = Column(String(20),  nullable=True)
    nom          = Column(String(200), nullable=False)
    localisation = Column(String(300), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now())

    affectations = relationship("AffectationSIM", back_populates="site")


class Vehicule(Base):
    __tablename__ = "vehicules"

    id             = Column(Integer, primary_key=True, index=True)
    immatriculation = Column(String(20), unique=True, nullable=False)
    marque         = Column(String(100), nullable=True)
    modele         = Column(String(100), nullable=True)
    imsi           = Column(String(20),  nullable=True)
    imei           = Column(String(30),  nullable=True)
    affectation    = Column(String(200), nullable=True)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())

    affectations = relationship("AffectationSIM", back_populates="vehicule")


class NumeroSIM(Base):
    __tablename__ = "numeros_sim"

    id          = Column(Integer, primary_key=True, index=True)
    numero      = Column(String(20), unique=True, nullable=False, index=True)
    imsi        = Column(String(20), nullable=True)
    categorie   = Column(Enum(CategorieSimEnum), nullable=False, index=True)
    statut      = Column(Enum(StatutSimEnum), default=StatutSimEnum.ACTIVE, index=True)
    operateur   = Column(String(50), nullable=True)
    description = Column(Text, nullable=True)
    matricule     = Column(String(50), nullable=True)
    beneficiaire  = Column(String(150), nullable=True)
    service       = Column(String(100), nullable=True)
    business_line = Column(String(50), nullable=True)
    fonction      = Column(String(150), nullable=True)
    forfait       = Column(Numeric(10, 2), nullable=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    affectations      = relationship(
        "AffectationSIM",
        back_populates="sim",
        order_by="AffectationSIM.date_debut.desc()",
        foreign_keys="[AffectationSIM.sim_id]",
        overlaps="affectation_active",
    )
    affectation_active = relationship(
        "AffectationSIM",
        primaryjoin="and_(NumeroSIM.id == AffectationSIM.sim_id, AffectationSIM.is_active == True)",
        foreign_keys="[AffectationSIM.sim_id]",
        uselist=False,
        viewonly=True,
        overlaps="affectations",
    )
    lignes_facture    = relationship("LigneFacture", back_populates="sim")


class ImportGlobalLog(Base):
    __tablename__ = "import_global_logs"

    id           = Column(Integer, primary_key=True, index=True)
    nom_fichier  = Column(String(255), nullable=True)
    utilisateur  = Column(String(150), nullable=True)
    resultat     = Column(Text, nullable=True)  # JSON sérialisé du résumé d'import
    created_at   = Column(DateTime(timezone=True), server_default=func.now())


class AffectationSIM(Base):
    __tablename__ = "affectations_sim"

    id          = Column(Integer, primary_key=True, index=True)
    sim_id      = Column(Integer, ForeignKey("numeros_sim.id"), nullable=False)
    date_debut  = Column(Date, nullable=False)
    date_fin    = Column(Date, nullable=True)
    is_active   = Column(Boolean, default=True, index=True)

    # Cible : employé OU site OU véhicule (un seul renseigné)
    employee_id         = Column(Integer, nullable=True, index=True)
    employee_nom        = Column(String(200), nullable=True)
    employee_matricule  = Column(String(50), nullable=True)
    site_id             = Column(Integer, ForeignKey("sites_gsm.id"), nullable=True)
    vehicule_id         = Column(Integer, ForeignKey("vehicules.id"), nullable=True)

    motif_fin  = Column(String(300), nullable=True)
    notes      = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    sim      = relationship("NumeroSIM", back_populates="affectations", overlaps="affectation_active")
    site     = relationship("SiteGSM",   back_populates="affectations")
    vehicule = relationship("Vehicule",  back_populates="affectations")
