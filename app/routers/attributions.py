from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from datetime import date
from pydantic import BaseModel
from ..database import get_db
from ..models.attribution import Attribution, StatutAttribution
from ..models.materiel import Materiel, StatutMateriel
from ..schemas.attribution import AttributionCreate, AttributionOut, RestitutionCreate
from ..services.pdf_service import generate_decharge_pdf, generate_attestation_pdf


class AttributionUpdate(BaseModel):
    etat_remise: Optional[str] = None
    notes:       Optional[str] = None

router = APIRouter(prefix="/api/attributions", tags=["Attributions"])


def _get_or_404(db, attribution_id):
    obj = db.query(Attribution).options(joinedload(Attribution.materiel)).filter(Attribution.id == attribution_id).first()
    if not obj:
        raise HTTPException(404, "Attribution introuvable")
    return obj


@router.get("/stats/summary")
def attribution_stats(db: Session = Depends(get_db)):
    active    = db.query(func.count(Attribution.id)).filter(Attribution.statut == StatutAttribution.ACTIVE).scalar()
    cloturee  = db.query(func.count(Attribution.id)).filter(Attribution.statut == StatutAttribution.CLOTUREE).scalar()
    employees = db.query(func.count(func.distinct(Attribution.employee_id))).filter(Attribution.statut == StatutAttribution.ACTIVE).scalar()
    services  = (
        db.query(Attribution.employee_service, func.count(Attribution.id))
        .filter(Attribution.statut == StatutAttribution.ACTIVE)
        .group_by(Attribution.employee_service)
        .order_by(func.count(Attribution.id).desc())
        .limit(6)
        .all()
    )
    return {
        "active":           active,
        "cloturee":         cloturee,
        "employees_actifs": employees,
        "par_service":      [{"service": r[0] or "—", "count": r[1]} for r in services],
    }


@router.get("/", response_model=list[AttributionOut])
def list_attributions(
    employee_id: Optional[int] = None,
    statut: Optional[StatutAttribution] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Attribution).options(joinedload(Attribution.materiel))
    if employee_id:
        q = q.filter(Attribution.employee_id == employee_id)
    if statut:
        q = q.filter(Attribution.statut == statut)
    return q.order_by(Attribution.date_attribution.desc()).all()


@router.post("/", response_model=AttributionOut, status_code=201)
def create_attribution(data: AttributionCreate, db: Session = Depends(get_db)):
    materiel = db.query(Materiel).filter(Materiel.id == data.materiel_id).first()
    if not materiel:
        raise HTTPException(404, "Matériel introuvable")
    if materiel.statut == StatutMateriel.ATTRIBUE:
        raise HTTPException(400, "Ce matériel est déjà attribué")

    obj = Attribution(**data.model_dump())
    materiel.statut = StatutMateriel.ATTRIBUE
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{attribution_id}", response_model=AttributionOut)
def get_attribution(attribution_id: int, db: Session = Depends(get_db)):
    return _get_or_404(db, attribution_id)


@router.patch("/{attribution_id}", response_model=AttributionOut)
def update_attribution(attribution_id: int, data: AttributionUpdate, db: Session = Depends(get_db)):
    obj = db.query(Attribution).filter(Attribution.id == attribution_id).first()
    if not obj:
        raise HTTPException(404, "Attribution introuvable")
    if data.etat_remise is not None:
        obj.etat_remise = data.etat_remise
    if data.notes is not None:
        obj.notes = data.notes
    db.commit()
    db.refresh(obj)
    # Recharger avec le matériel pour la réponse
    return db.query(Attribution).options(joinedload(Attribution.materiel)).filter(Attribution.id == attribution_id).first()


@router.post("/{attribution_id}/restitution", response_model=AttributionOut)
def restituer(attribution_id: int, data: RestitutionCreate, db: Session = Depends(get_db)):
    obj = _get_or_404(db, attribution_id)
    if obj.statut == StatutAttribution.CLOTUREE:
        raise HTTPException(400, "Attribution déjà clôturée")

    obj.date_restitution  = data.date_restitution
    obj.motif_restitution = data.motif_restitution
    obj.notes_restitution = data.notes_restitution
    obj.statut            = StatutAttribution.CLOTUREE
    obj.materiel.statut   = StatutMateriel.DISPONIBLE
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{attribution_id}/decharge")
def download_decharge(attribution_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import io
    obj = _get_or_404(db, attribution_id)
    pdf_bytes = generate_decharge_pdf(obj)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=decharge_{attribution_id}.pdf"},
    )


@router.get("/attestation/employee/{employee_id}")
def attestation_employee(employee_id: int, db: Session = Depends(get_db)):
    from fastapi.responses import StreamingResponse
    import io
    attrs = (
        db.query(Attribution)
        .options(joinedload(Attribution.materiel))
        .filter(Attribution.employee_id == employee_id, Attribution.statut == StatutAttribution.ACTIVE)
        .order_by(Attribution.date_attribution.asc())
        .all()
    )
    if not attrs:
        raise HTTPException(404, "Aucune attribution active pour cet employé")
    pdf_bytes = generate_attestation_pdf(attrs)
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"inline; filename=attestation_{employee_id}.pdf"},
    )


@router.get("/employee/{employee_id}", response_model=list[AttributionOut])
def attributions_par_employee(employee_id: int, db: Session = Depends(get_db)):
    return (
        db.query(Attribution)
        .options(joinedload(Attribution.materiel))
        .filter(Attribution.employee_id == employee_id)
        .order_by(Attribution.date_attribution.desc())
        .all()
    )


@router.post("/{attribution_id}/transferer", status_code=201)
def transferer(attribution_id: int, data: dict, db: Session = Depends(get_db)):
    """Clôture l'attribution en cours et crée immédiatement la suivante."""
    from pydantic import BaseModel
    from typing import Optional as Opt
    from datetime import date as dt_date

    old = _get_or_404(db, attribution_id)
    if old.statut == StatutAttribution.CLOTUREE:
        raise HTTPException(400, "Attribution déjà clôturée")

    # Clôture
    old.date_restitution  = dt_date.fromisoformat(data["date_restitution"])
    old.motif_restitution = data.get("motif_restitution", "CHANGEMENT")
    old.notes_restitution = data.get("notes_restitution")
    old.statut            = StatutAttribution.CLOTUREE

    # Nouvelle attribution
    new_attr = Attribution(
        materiel_id        = old.materiel_id,
        employee_id        = data["employee_id"],
        employee_nom       = data["employee_nom"],
        employee_prenom    = data.get("employee_prenom"),
        employee_matricule = data.get("employee_matricule"),
        employee_service   = data.get("employee_service"),
        employee_poste     = data.get("employee_poste"),
        date_attribution   = dt_date.fromisoformat(data["date_attribution"]),
        etat_remise        = data.get("etat_remise"),
        notes              = data.get("notes"),
        statut             = StatutAttribution.ACTIVE,
    )
    db.add(new_attr)
    db.commit()
    db.refresh(new_attr)
    return {"old_id": attribution_id, "new_id": new_attr.id}


@router.get("/materiel/{materiel_id}", response_model=list[AttributionOut])
def attributions_par_materiel(materiel_id: int, db: Session = Depends(get_db)):
    """Historique complet (actives + clôturées) d'un matériel."""
    return (
        db.query(Attribution)
        .options(joinedload(Attribution.materiel))
        .filter(Attribution.materiel_id == materiel_id)
        .order_by(Attribution.date_attribution.desc())
        .all()
    )
