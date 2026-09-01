from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date
from pydantic import BaseModel
from ..database import get_db
from ..models.projet import Projet, ProjetEtape, ProjetChangement, ProjetPays
from ..models.projet import StatutProjet, StatutEtape, TypeChangement, StatutDeploiement
from ..models.user import User
from ..services.auth_service import require_editor

router = APIRouter(prefix="/api/projets", tags=["Projets"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class ProjetIn(BaseModel):
    nom:          str
    description:  Optional[str]        = None
    statut:       StatutProjet          = StatutProjet.EN_COURS
    responsable:  Optional[str]        = None
    date_debut:   Optional[date]       = None
    date_fin:     Optional[date]       = None
    pourcentage:  int                  = 0

class ProjetPatch(BaseModel):
    nom:          Optional[str]        = None
    description:  Optional[str]        = None
    statut:       Optional[StatutProjet] = None
    responsable:  Optional[str]        = None
    date_debut:   Optional[date]       = None
    date_fin:     Optional[date]       = None
    pourcentage:  Optional[int]        = None

class EtapeIn(BaseModel):
    titre:       str
    description: Optional[str]       = None
    statut:      StatutEtape          = StatutEtape.A_FAIRE
    ordre:       int                  = 0

class EtapePatch(BaseModel):
    titre:       Optional[str]       = None
    description: Optional[str]       = None
    statut:      Optional[StatutEtape] = None
    ordre:       Optional[int]       = None

class ChangementIn(BaseModel):
    titre:       str
    description: Optional[str]       = None
    type:        TypeChangement        = TypeChangement.FEATURE
    date:        date
    auteur:      Optional[str]       = None

class ChangementPatch(BaseModel):
    titre:       Optional[str]           = None
    description: Optional[str]           = None
    type:        Optional[TypeChangement] = None
    date:        Optional[date]          = None
    auteur:      Optional[str]           = None

class PaysIn(BaseModel):
    pays:             str
    date_deploiement: Optional[date]          = None
    statut:           StatutDeploiement        = StatutDeploiement.DEPLOYE
    notes:            Optional[str]           = None

class PaysPatch(BaseModel):
    pays:             Optional[str]               = None
    date_deploiement: Optional[date]              = None
    statut:           Optional[StatutDeploiement] = None
    notes:            Optional[str]               = None


# ── Projets CRUD ──────────────────────────────────────────────────────────────

def _get_projet(db, projet_id):
    p = (db.query(Projet)
         .options(
             joinedload(Projet.etapes),
             joinedload(Projet.changements),
             joinedload(Projet.pays),
         )
         .filter(Projet.id == projet_id).first())
    if not p: raise HTTPException(404, "Projet introuvable")
    return p


@router.get("/")
def list_projets(
    statut: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    q = db.query(Projet).options(
        joinedload(Projet.etapes),
        joinedload(Projet.changements),
        joinedload(Projet.pays),
    )
    if statut:
        q = q.filter(Projet.statut == statut)
    return q.order_by(Projet.created_at.desc()).all()


@router.post("/", status_code=201)
def create_projet(data: ProjetIn, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    p = Projet(**data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return p


@router.get("/{projet_id}")
def get_projet(projet_id: int, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    return _get_projet(db, projet_id)


@router.patch("/{projet_id}")
def update_projet(projet_id: int, data: ProjetPatch, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    p = db.query(Projet).filter(Projet.id == projet_id).first()
    if not p: raise HTTPException(404, "Projet introuvable")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return p


@router.delete("/{projet_id}", status_code=204)
def delete_projet(projet_id: int, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    p = db.query(Projet).filter(Projet.id == projet_id).first()
    if not p: raise HTTPException(404, "Projet introuvable")
    db.delete(p); db.commit()


# ── Étapes ────────────────────────────────────────────────────────────────────

@router.post("/{projet_id}/etapes", status_code=201)
def add_etape(projet_id: int, data: EtapeIn, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    if not db.query(Projet).filter(Projet.id == projet_id).first():
        raise HTTPException(404, "Projet introuvable")
    e = ProjetEtape(projet_id=projet_id, **data.model_dump())
    db.add(e); db.commit(); db.refresh(e)
    return e


@router.patch("/{projet_id}/etapes/{etape_id}")
def update_etape(projet_id: int, etape_id: int, data: EtapePatch, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    e = db.query(ProjetEtape).filter(ProjetEtape.id == etape_id, ProjetEtape.projet_id == projet_id).first()
    if not e: raise HTTPException(404, "Étape introuvable")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(e, k, v)
    db.commit(); db.refresh(e)
    return e


@router.delete("/{projet_id}/etapes/{etape_id}", status_code=204)
def delete_etape(projet_id: int, etape_id: int, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    e = db.query(ProjetEtape).filter(ProjetEtape.id == etape_id, ProjetEtape.projet_id == projet_id).first()
    if not e: raise HTTPException(404, "Étape introuvable")
    db.delete(e); db.commit()


# ── Changements ───────────────────────────────────────────────────────────────

@router.post("/{projet_id}/changements", status_code=201)
def add_changement(projet_id: int, data: ChangementIn, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    if not db.query(Projet).filter(Projet.id == projet_id).first():
        raise HTTPException(404, "Projet introuvable")
    c = ProjetChangement(projet_id=projet_id, **data.model_dump())
    db.add(c); db.commit(); db.refresh(c)
    return c


@router.patch("/{projet_id}/changements/{chg_id}")
def update_changement(projet_id: int, chg_id: int, data: ChangementPatch, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    c = db.query(ProjetChangement).filter(ProjetChangement.id == chg_id, ProjetChangement.projet_id == projet_id).first()
    if not c: raise HTTPException(404, "Changement introuvable")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(c, k, v)
    db.commit(); db.refresh(c)
    return c


@router.delete("/{projet_id}/changements/{chg_id}", status_code=204)
def delete_changement(projet_id: int, chg_id: int, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    c = db.query(ProjetChangement).filter(ProjetChangement.id == chg_id, ProjetChangement.projet_id == projet_id).first()
    if not c: raise HTTPException(404, "Changement introuvable")
    db.delete(c); db.commit()


# ── Pays ──────────────────────────────────────────────────────────────────────

@router.post("/{projet_id}/pays", status_code=201)
def add_pays(projet_id: int, data: PaysIn, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    if not db.query(Projet).filter(Projet.id == projet_id).first():
        raise HTTPException(404, "Projet introuvable")
    p = ProjetPays(projet_id=projet_id, **data.model_dump())
    db.add(p); db.commit(); db.refresh(p)
    return p


@router.patch("/{projet_id}/pays/{pays_id}")
def update_pays(projet_id: int, pays_id: int, data: PaysPatch, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    p = db.query(ProjetPays).filter(ProjetPays.id == pays_id, ProjetPays.projet_id == projet_id).first()
    if not p: raise HTTPException(404, "Pays introuvable")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(p, k, v)
    db.commit(); db.refresh(p)
    return p


@router.delete("/{projet_id}/pays/{pays_id}", status_code=204)
def delete_pays(projet_id: int, pays_id: int, db: Session = Depends(get_db), _: User = Depends(require_editor)):
    p = db.query(ProjetPays).filter(ProjetPays.id == pays_id, ProjetPays.projet_id == projet_id).first()
    if not p: raise HTTPException(404, "Pays introuvable")
    db.delete(p); db.commit()
