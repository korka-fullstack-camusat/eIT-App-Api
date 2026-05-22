from pydantic import BaseModel
from datetime import date, datetime
from typing import Optional
from ..models.materiel import TypeMateriel, EtatMateriel, StatutMateriel


class MaterielBase(BaseModel):
    type_materiel:    TypeMateriel
    marque:           str
    modele:           Optional[str] = ""
    numero_serie:     Optional[str] = None
    adresse_ip:       Optional[str] = None
    numero_bon_cmd:   Optional[str] = None
    etat:             EtatMateriel = EtatMateriel.BON
    date_acquisition: Optional[date] = None
    description:      Optional[str] = None


class MaterielCreate(MaterielBase):
    pass


class MaterielUpdate(BaseModel):
    type_materiel:    Optional[TypeMateriel] = None
    marque:           Optional[str] = None
    modele:           Optional[str] = None
    numero_serie:     Optional[str] = None
    numero_bon_cmd:   Optional[str] = None
    etat:             Optional[EtatMateriel] = None
    statut:           Optional[StatutMateriel] = None
    date_acquisition: Optional[date] = None
    description:      Optional[str] = None


class AttributionActiveInfo(BaseModel):
    employee_nom:       str
    employee_prenom:    Optional[str] = None
    employee_matricule: Optional[str] = None
    employee_service:   Optional[str] = None
    employee_poste:     Optional[str] = None

    class Config:
        from_attributes = True


class MaterielOut(MaterielBase):
    id:                 int
    statut:             StatutMateriel
    created_at:         datetime
    adresse_ip:         Optional[str] = None
    attribution_active: Optional[AttributionActiveInfo] = None

    class Config:
        from_attributes = True
