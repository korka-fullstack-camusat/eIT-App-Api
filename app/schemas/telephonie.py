from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from ..models.telephonie import CategorieSimEnum, StatutSimEnum


class SiteGSMCreate(BaseModel):
    nom:          str
    localisation: Optional[str] = None
    description:  Optional[str] = None


class SiteGSMOut(SiteGSMCreate):
    id:         int
    created_at: datetime
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
    categorie:   CategorieSimEnum
    operateur:   Optional[str] = None
    description: Optional[str] = None


class NumeroSIMUpdate(BaseModel):
    categorie:   Optional[CategorieSimEnum] = None
    statut:      Optional[StatutSimEnum] = None
    operateur:   Optional[str] = None
    description: Optional[str] = None


class NumeroSIMOut(NumeroSIMCreate):
    id:         int
    statut:     StatutSimEnum
    created_at: datetime
    class Config:
        from_attributes = True


class AffectationSIMCreate(BaseModel):
    sim_id:            int
    date_debut:        date
    employee_id:       Optional[int] = None
    employee_nom:      Optional[str] = None
    employee_matricule: Optional[str] = None
    site_id:           Optional[int] = None
    vehicule_id:       Optional[int] = None
    notes:             Optional[str] = None


class AffectationSIMOut(AffectationSIMCreate):
    id:         int
    date_fin:   Optional[date]
    is_active:  bool
    created_at: datetime
    class Config:
        from_attributes = True
