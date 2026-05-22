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
    class Config:
        from_attributes = True


class FactureOut(FactureCreate):
    id:          int
    nom_fichier: Optional[str]
    created_at:  datetime
    lignes:      list[LigneFactureOut] = []
    class Config:
        from_attributes = True


class ImportResult(BaseModel):
    facture_id:     int
    total_lignes:   int
    reconnus:       int
    non_reconnus:   int
    montant_total:  Decimal
    numeros_inconnus: list[str] = []
