from pydantic import BaseModel
from datetime import datetime
from typing import Optional
from decimal import Decimal


class FactureCreate(BaseModel):
    mois:       int
    annee:      int
    operateur:  Optional[str] = None
    notes:      Optional[str] = None


class LigneFactureOut(BaseModel):
    id:          int
    sim_id:      Optional[int]
    numero_raw:  str
    montant:     Decimal
    non_reconnu: str

    # ── Détail récapitulatif (extrait tel quel du fichier) ──
    reference_facture: Optional[str] = None
    montant_ht:        Optional[Decimal] = None
    rutel:             Optional[Decimal] = None
    montant_ht_rutel:  Optional[Decimal] = None
    tva:               Optional[Decimal] = None
    montant_ttc:       Optional[Decimal] = None
    arrondi_precedent: Optional[Decimal] = None
    arrondi_encours:   Optional[Decimal] = None
    solde_facture:     Optional[Decimal] = None
    type_ligne:        Optional[str] = None

    class Config:
        from_attributes = True


class FactureOut(FactureCreate):
    id:          int
    nom_fichier: Optional[str]
    created_at:  datetime
    lignes:      list[LigneFactureOut] = []

    # ── Récapitulatif facture ──
    numero_compte:     Optional[str] = None
    reference_facture: Optional[str] = None
    montant_ht:        Optional[Decimal] = None
    rutel:             Optional[Decimal] = None
    montant_ht_rutel:  Optional[Decimal] = None
    tva:               Optional[Decimal] = None
    montant_ttc:       Optional[Decimal] = None
    arrondi_precedent: Optional[Decimal] = None
    arrondi_encours:   Optional[Decimal] = None
    solde_facture:     Optional[Decimal] = None

    # ── Écart vs mois précédent (calculé) ──
    ecart:             Optional[Decimal] = None
    ecart_pct:         Optional[float] = None

    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    facture_id:     int
    total_lignes:   int
    reconnus:       int
    non_reconnus:   int
    montant_total:  Decimal
    numeros_inconnus: list[str] = []
