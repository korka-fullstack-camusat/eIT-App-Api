from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from ..database import get_db
from ..models.demande import DemandeAmelioration, StatutDemande
from ..models.user import User
from ..services.auth_service import get_current_user, require_directeur

router = APIRouter(prefix="/api/demandes", tags=["Demandes"])


# ── Schemas ───────────────────────────────────────────────────────────────────

class DemandeIn(BaseModel):
    titre:       str
    description: str
    projet:      Optional[str] = None

class DecisionIn(BaseModel):
    statut:         StatutDemande   # VALIDEE ou REJETEE
    commentaire_dg: Optional[str] = None


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/")
def list_demandes(
    statut: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(DemandeAmelioration)
    # DIRECTEUR et ADMIN voient tout ; les autres voient seulement leurs demandes
    if current_user.role not in ("DIRECTEUR", "ADMIN"):
        q = q.filter(DemandeAmelioration.demandeur == current_user.full_name or current_user.username)
    if statut:
        q = q.filter(DemandeAmelioration.statut == statut)
    return q.order_by(DemandeAmelioration.created_at.desc()).all()


@router.post("/", status_code=201)
def create_demande(
    data: DemandeIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = DemandeAmelioration(
        **data.model_dump(),
        demandeur=current_user.full_name or current_user.username,
    )
    db.add(d); db.commit(); db.refresh(d)
    return d


@router.patch("/{demande_id}/decision")
def decide_demande(
    demande_id: int,
    data: DecisionIn,
    db: Session = Depends(get_db),
    _: User = Depends(require_directeur),
):
    """Valider ou rejeter une demande — réservé DIRECTEUR / ADMIN."""
    d = db.query(DemandeAmelioration).filter(DemandeAmelioration.id == demande_id).first()
    if not d:
        raise HTTPException(404, "Demande introuvable")
    if data.statut not in (StatutDemande.VALIDEE, StatutDemande.REJETEE):
        raise HTTPException(400, "Statut invalide pour une décision")
    d.statut = data.statut
    d.commentaire_dg = data.commentaire_dg
    db.commit(); db.refresh(d)
    return d


@router.delete("/{demande_id}", status_code=204)
def delete_demande(
    demande_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    d = db.query(DemandeAmelioration).filter(DemandeAmelioration.id == demande_id).first()
    if not d:
        raise HTTPException(404, "Demande introuvable")
    # Seul le demandeur ou un admin peut supprimer
    if d.demandeur != (current_user.full_name or current_user.username) and current_user.role not in ("ADMIN", "DIRECTEUR"):
        raise HTTPException(403, "Non autorisé")
    db.delete(d); db.commit()
