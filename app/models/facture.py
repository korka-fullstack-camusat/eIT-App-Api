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

    # ── Récapitulatif facture (extrait du fichier importé) ──
    numero_compte      = Column(String(50), nullable=True)   # "Numéro"
    reference_facture  = Column(String(50), nullable=True)   # "Référence Facture"
    montant_ht         = Column(Numeric(14, 2), nullable=True)  # "Montant Hors Taxe"
    rutel              = Column(Numeric(14, 2), nullable=True)  # "Rutel (5%)"
    montant_ht_rutel   = Column(Numeric(14, 2), nullable=True)  # "Hors TVA avec Rutel"
    tva                = Column(Numeric(14, 2), nullable=True)  # "TVA (18%)"
    montant_ttc        = Column(Numeric(14, 2), nullable=True)  # "Montant TTC"
    arrondi_precedent  = Column(Numeric(14, 2), nullable=True)  # "Arrondi Précédent"
    arrondi_encours    = Column(Numeric(14, 2), nullable=True)  # "Arrondi En cours"
    solde_facture      = Column(Numeric(14, 2), nullable=True)  # "Solde Facture"

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

    # ── Détail récapitulatif par numéro (extrait tel quel du fichier) ──
    reference_facture  = Column(String(50), nullable=True)   # "Référence Facture"
    montant_ht         = Column(Numeric(14, 2), nullable=True)  # "Montant Hors Taxe"
    rutel              = Column(Numeric(14, 2), nullable=True)  # "Rutel (5%)"
    montant_ht_rutel   = Column(Numeric(14, 2), nullable=True)  # "Hors TVA avec Rutel"
    tva                = Column(Numeric(14, 2), nullable=True)  # "TVA (18%)"
    montant_ttc        = Column(Numeric(14, 2), nullable=True)  # "Montant TTC"
    arrondi_precedent  = Column(Numeric(14, 2), nullable=True)  # "Arrondi Précédent"
    arrondi_encours    = Column(Numeric(14, 2), nullable=True)  # "Arrondi En cours"
    solde_facture      = Column(Numeric(14, 2), nullable=True)  # "Solde Facture"
    type_ligne         = Column(String(50), nullable=True)      # "Type" (ex: MOBILE, FIXE)

    facture = relationship("FactureTelecom", back_populates="lignes")
    sim     = relationship("NumeroSIM", back_populates="lignes_facture")
