from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from ..models.telephonie import CategorieSimEnum, StatutSimEnum


class SiteGSMCreate(BaseModel):
    code_site:    Optional[str] = None
    imsi:         Optional[str] = None
    nom:          str
    localisation: Optional[str] = None


class SiteGSMOut(SiteGSMCreate):
    id:          int
    created_at:  datetime
    sim_numero:  Optional[str] = None
    class Config:
        from_attributes = True


class VehiculeCreate(BaseModel):
    immatriculation: str
    marque:          Optional[str] = None
    modele:          Optional[str] = None
    affectation:     Optional[str] = None


class VehiculeOut(VehiculeCreate):
    id:         int
    created_at: datetime
    class Config:
        from_attributes = True


class NumeroSIMCreate(BaseModel):
    numero:      str
    imsi:        Optional[str] = None
    categorie:   CategorieSimEnum
    operateur:   Optional[str] = None
    description: Optional[str] = None


class NumeroSIMUpdate(BaseModel):
    imsi:        Optional[str] = None
    categorie:   Optional[CategorieSimEnum] = None
    statut:      Optional[StatutSimEnum] = None
    operateur:   Optional[str] = None
    description: Optional[str] = None


class NumeroSIMOut(NumeroSIMCreate):
    id:                 int
    statut:             StatutSimEnum
    created_at:         datetime
    affectation_active: Optional["AffectationSIMOut"] = None
    class Config:
        from_attributes = True


class AffectationSIMCreate(BaseModel):
    date_debut:         date
    employee_id:        Optional[int] = None
    employee_nom:       Optional[str] = None
    employee_matricule: Optional[str] = None
    site_id:            Optional[int] = None
    vehicule_id:        Optional[int] = None
    notes:              Optional[str] = None


class DesaffectationSIMIn(BaseModel):
    motif: Optional[str] = None


class AffectationSIMOut(AffectationSIMCreate):
    id:         int
    sim_id:     int
    date_fin:   Optional[date]
    is_active:  bool
    motif_fin:  Optional[str] = None
    created_at: datetime
    class Config:
        from_attributes = True


NumeroSIMOut.model_rebuild()
