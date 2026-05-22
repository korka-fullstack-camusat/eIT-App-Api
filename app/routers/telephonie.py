from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date
from ..database import get_db
from ..models.telephonie import NumeroSIM, SiteGSM, Vehicule, AffectationSIM, CategorieSimEnum, StatutSimEnum
from ..schemas.telephonie import (
    NumeroSIMCreate, NumeroSIMUpdate, NumeroSIMOut,
    SiteGSMCreate, SiteGSMOut,
    VehiculeCreate, VehiculeOut,
    AffectationSIMCreate, AffectationSIMOut,
)

router = APIRouter(prefix="/api/telephonie", tags=["Téléphonie"])

# ── SIMs ──────────────────────────────────────────────────────────────────────

@router.get("/sims", response_model=list[NumeroSIMOut])
def list_sims(
    categorie: Optional[CategorieSimEnum] = None,
    statut:    Optional[StatutSimEnum] = None,
    search:    Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(NumeroSIM)
    if categorie: q = q.filter(NumeroSIM.categorie == categorie)
    if statut:    q = q.filter(NumeroSIM.statut == statut)
    if search:    q = q.filter(NumeroSIM.numero.ilike(f"%{search}%"))
    return q.order_by(NumeroSIM.numero).all()


@router.post("/sims", response_model=NumeroSIMOut, status_code=201)
def create_sim(data: NumeroSIMCreate, db: Session = Depends(get_db)):
    if db.query(NumeroSIM).filter(NumeroSIM.numero == data.numero).first():
        raise HTTPException(400, "Ce numéro existe déjà")
    obj = NumeroSIM(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/sims/{sim_id}", response_model=NumeroSIMOut)
def update_sim(sim_id: int, data: NumeroSIMUpdate, db: Session = Depends(get_db)):
    obj = db.query(NumeroSIM).filter(NumeroSIM.id == sim_id).first()
    if not obj: raise HTTPException(404, "SIM introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/sims/{sim_id}", status_code=204)
def delete_sim(sim_id: int, db: Session = Depends(get_db)):
    obj = db.query(NumeroSIM).filter(NumeroSIM.id == sim_id).first()
    if not obj: raise HTTPException(404, "SIM introuvable")
    db.delete(obj); db.commit()


# ── Affectations SIM ──────────────────────────────────────────────────────────

@router.post("/sims/{sim_id}/affecter", response_model=AffectationSIMOut, status_code=201)
def affecter_sim(sim_id: int, data: AffectationSIMCreate, db: Session = Depends(get_db)):
    # Clôturer l'affectation active précédente
    active = db.query(AffectationSIM).filter(
        AffectationSIM.sim_id == sim_id, AffectationSIM.is_active == True
    ).first()
    if active:
        active.is_active = False
        active.date_fin  = date.today()

    payload = data.model_dump()
    payload["sim_id"] = sim_id
    obj = AffectationSIM(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/sims/{sim_id}/historique", response_model=list[AffectationSIMOut])
def historique_sim(sim_id: int, db: Session = Depends(get_db)):
    return (
        db.query(AffectationSIM)
        .filter(AffectationSIM.sim_id == sim_id)
        .order_by(AffectationSIM.date_debut.desc())
        .all()
    )


# ── Sites GSM ─────────────────────────────────────────────────────────────────

@router.get("/sites", response_model=list[SiteGSMOut])
def list_sites(db: Session = Depends(get_db)):
    return db.query(SiteGSM).order_by(SiteGSM.nom).all()


@router.post("/sites", response_model=SiteGSMOut, status_code=201)
def create_site(data: SiteGSMCreate, db: Session = Depends(get_db)):
    obj = SiteGSM(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/sites/{site_id}", response_model=SiteGSMOut)
def update_site(site_id: int, data: SiteGSMCreate, db: Session = Depends(get_db)):
    obj = db.query(SiteGSM).filter(SiteGSM.id == site_id).first()
    if not obj: raise HTTPException(404, "Site introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/sites/{site_id}", status_code=204)
def delete_site(site_id: int, db: Session = Depends(get_db)):
    obj = db.query(SiteGSM).filter(SiteGSM.id == site_id).first()
    if not obj: raise HTTPException(404, "Site introuvable")
    db.delete(obj); db.commit()


# ── Véhicules ─────────────────────────────────────────────────────────────────

@router.get("/vehicules", response_model=list[VehiculeOut])
def list_vehicules(db: Session = Depends(get_db)):
    return db.query(Vehicule).order_by(Vehicule.immatriculation).all()


@router.post("/vehicules", response_model=VehiculeOut, status_code=201)
def create_vehicule(data: VehiculeCreate, db: Session = Depends(get_db)):
    if db.query(Vehicule).filter(Vehicule.immatriculation == data.immatriculation).first():
        raise HTTPException(400, "Immatriculation déjà enregistrée")
    obj = Vehicule(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/vehicules/{vehicule_id}", response_model=VehiculeOut)
def update_vehicule(vehicule_id: int, data: VehiculeCreate, db: Session = Depends(get_db)):
    obj = db.query(Vehicule).filter(Vehicule.id == vehicule_id).first()
    if not obj: raise HTTPException(404, "Véhicule introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    db.commit(); db.refresh(obj)
    return obj


@router.delete("/vehicules/{vehicule_id}", status_code=204)
def delete_vehicule(vehicule_id: int, db: Session = Depends(get_db)):
    obj = db.query(Vehicule).filter(Vehicule.id == vehicule_id).first()
    if not obj: raise HTTPException(404, "Véhicule introuvable")
    db.delete(obj); db.commit()
