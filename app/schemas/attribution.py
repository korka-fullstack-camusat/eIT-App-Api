from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from ..models.attribution import StatutAttribution, MotifRestitution
from .materiel import MaterielOut


class AttributionCreate(BaseModel):
    materiel_id:        int
    employee_id:        int
    employee_nom:       str
    employee_prenom:    Optional[str] = None
    employee_matricule: Optional[str] = None
    employee_service:   Optional[str] = None
    employee_poste:     Optional[str] = None
    date_attribution:   date
    etat_remise:        Optional[str] = None
    notes:              Optional[str] = None


class RestitutionCreate(BaseModel):
    date_restitution:  date
    motif_restitution: MotifRestitution
    notes_restitution: Optional[str] = None


class AttributionOut(BaseModel):
    id:                 int
    materiel_id:        int
    materiel:           Optional[MaterielOut] = None
    employee_id:        int
    employee_nom:       str
    employee_prenom:    Optional[str]
    employee_matricule: Optional[str]
    employee_service:   Optional[str]
    employee_poste:     Optional[str]
    date_attribution:   date
    etat_remise:        Optional[str]
    statut:             StatutAttribution
    notes:              Optional[str]
    date_restitution:   Optional[date]
    motif_restitution:  Optional[MotifRestitution]
    notes_restitution:  Optional[str]
    created_at:         datetime

    class Config:
        from_attributes = True
