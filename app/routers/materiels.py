from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional
from ..database import get_db
from ..models.materiel import Materiel, StatutMateriel
from ..models.attribution import Attribution, StatutAttribution
from ..schemas.materiel import MaterielCreate, MaterielUpdate, MaterielOut, AttributionActiveInfo

router = APIRouter(prefix="/api/materiels", tags=["Matériels"])


@router.get("/", response_model=list[MaterielOut])
def list_materiels(
    statut: Optional[StatutMateriel] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Materiel).options(joinedload(Materiel.attributions))
    if statut:
        q = q.filter(Materiel.statut == statut)
    if search:
        term = f"%{search}%"
        q = q.filter(
            Materiel.marque.ilike(term) |
            Materiel.modele.ilike(term) |
            Materiel.numero_serie.ilike(term)
        )
    materiels = q.order_by(Materiel.marque, Materiel.modele).all()

    result = []
    for m in materiels:
        item = MaterielOut.model_validate(m)
        active = next(
            (a for a in m.attributions if a.statut == StatutAttribution.ACTIVE),
            None,
        )
        if active:
            item.attribution_active = AttributionActiveInfo.model_validate(active)
        result.append(item)
    return result


@router.post("/", response_model=MaterielOut, status_code=201)
def create_materiel(data: MaterielCreate, db: Session = Depends(get_db)):
    obj = Materiel(**data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


@router.get("/{materiel_id}", response_model=MaterielOut)
def get_materiel(materiel_id: int, db: Session = Depends(get_db)):
    obj = db.query(Materiel).filter(Materiel.id == materiel_id).first()
    if not obj:
        raise HTTPException(404, "Matériel introuvable")
    return obj


@router.patch("/{materiel_id}", response_model=MaterielOut)
def update_materiel(materiel_id: int, data: MaterielUpdate, db: Session = Depends(get_db)):
    obj = db.query(Materiel).filter(Materiel.id == materiel_id).first()
    if not obj:
        raise HTTPException(404, "Matériel introuvable")
    for k, v in data.model_dump(exclude_none=True).items():
        setattr(obj, k, v)
    db.commit()
    db.refresh(obj)
    return obj


@router.delete("/{materiel_id}", status_code=204)
def delete_materiel(materiel_id: int, db: Session = Depends(get_db)):
    obj = db.query(Materiel).filter(Materiel.id == materiel_id).first()
    if not obj:
        raise HTTPException(404, "Matériel introuvable")
    if obj.statut == StatutMateriel.ATTRIBUE:
        raise HTTPException(400, "Impossible de supprimer un matériel attribué")
    db.delete(obj)
    db.commit()


@router.post("/import")
async def import_materiels(file: UploadFile = File(...), db: Session = Depends(get_db)):
    import csv, io
    from ..models.materiel import TypeMateriel, EtatMateriel

    TYPE_MAP = {
        "PC PORTABLE": "ORDINATEUR_PORTABLE", "PC FIXE": "ORDINATEUR_FIXE",
        "ORDINATEUR PORTABLE": "ORDINATEUR_PORTABLE", "ORDINATEUR FIXE": "ORDINATEUR_FIXE",
        "ORDINATEUR_PORTABLE": "ORDINATEUR_PORTABLE", "ORDINATEUR_FIXE": "ORDINATEUR_FIXE",
        "ECRAN": "ECRAN", "ÉCRAN": "ECRAN", "SOURIS": "SOURIS", "CLAVIER": "CLAVIER",
        "TELEPHONE": "TELEPHONE", "TÉLÉPHONE": "TELEPHONE", "IMPRIMANTE": "IMPRIMANTE",
        "SWITCH": "SWITCH", "ROUTEUR": "ROUTEUR", "ONDULEUR": "ONDULEUR", "AUTRE": "AUTRE",
    }
    ETAT_MAP = {
        "NEUF": "NEUF", "BON": "BON", "USAGE": "USAGE", "USAGÉ": "USAGE",
        "DEFECTUEUX": "DEFECTUEUX", "DÉFECTUEUX": "DEFECTUEUX",
    }

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    # Normalize header keys
    def norm(s: str) -> str:
        return s.strip().upper().replace("°", "").replace(" ", "_").replace("É", "E").replace("È", "E")

    created, errors = 0, []
    for i, raw_row in enumerate(reader, start=2):
        row = {norm(k): (v.strip() if v else "") for k, v in raw_row.items()}
        type_raw  = row.get("TYPE", "")
        type_val  = TYPE_MAP.get(type_raw.upper(), None)
        if not type_val:
            errors.append({"ligne": i, "message": f"Type inconnu : '{type_raw}'"})
            continue
        marque = row.get("MARQUE", "").strip()
        if not marque:
            errors.append({"ligne": i, "message": "Marque manquante"})
            continue
        etat_raw = row.get("ETAT", row.get("ÉTAT", "BON")).upper()
        etat_val = ETAT_MAP.get(etat_raw, "BON")

        acq_raw = row.get("ACQUISITION", row.get("DATE", "")).strip()
        acq = None
        if acq_raw:
            from datetime import date as dt_date, datetime as dt_datetime
            for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
                try:
                    acq = dt_datetime.strptime(acq_raw, fmt).date()
                    break
                except ValueError:
                    pass

        obj = Materiel(
            type_materiel    = TypeMateriel(type_val),
            marque           = marque,
            modele           = row.get("MODELE", row.get("MODÈLE", "")) or None,
            numero_serie     = row.get("N_SERIE", row.get("N__SERIE", "")) or None,
            adresse_ip       = row.get("ADRESSE_IP", "") or None,
            numero_bon_cmd   = row.get("N_PO", row.get("N__PO", "")) or None,
            etat             = EtatMateriel(etat_val),
            date_acquisition = acq,
        )
        db.add(obj)
        created += 1

    db.commit()
    return {"created": created, "errors": errors, "total_lignes": created + len(errors)}


@router.get("/stats/summary")
def stats_summary(db: Session = Depends(get_db)):
    total       = db.query(Materiel).count()
    disponible  = db.query(Materiel).filter(Materiel.statut == StatutMateriel.DISPONIBLE).count()
    attribue    = db.query(Materiel).filter(Materiel.statut == StatutMateriel.ATTRIBUE).count()
    maintenance = db.query(Materiel).filter(Materiel.statut == StatutMateriel.MAINTENANCE).count()
    reforme     = db.query(Materiel).filter(Materiel.statut == StatutMateriel.REFORME).count()
    return {
        "total": total, "disponible": disponible, "attribue": attribue,
        "maintenance": maintenance, "reforme": reforme,
    }


@router.get("/stats/par-type")
def stats_par_type(db: Session = Depends(get_db)):
    rows = (
        db.query(Materiel.type_materiel, func.count(Materiel.id))
        .group_by(Materiel.type_materiel)
        .order_by(func.count(Materiel.id).desc())
        .all()
    )
    return [{"type": r[0], "count": r[1]} for r in rows]


@router.get("/stats/par-marque")
def stats_par_marque(db: Session = Depends(get_db)):
    rows = (
        db.query(Materiel.marque, func.count(Materiel.id))
        .group_by(Materiel.marque)
        .order_by(func.count(Materiel.id).desc())
        .limit(8)
        .all()
    )
    return [{"marque": r[0], "count": r[1]} for r in rows]
