from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import Optional
from datetime import date
import csv, io
from ..database import get_db
from ..models.telephonie import NumeroSIM, SiteGSM, Vehicule, AffectationSIM, CategorieSimEnum, StatutSimEnum
from sqlalchemy import and_
from ..schemas.telephonie import (
    NumeroSIMCreate, NumeroSIMUpdate, NumeroSIMOut,
    SiteGSMCreate, SiteGSMOut,
    VehiculeCreate, VehiculeOut,
    AffectationSIMCreate, AffectationSIMOut, DesaffectationSIMIn,
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
    q = db.query(NumeroSIM).options(joinedload(NumeroSIM.affectation_active))
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


@router.get("/sims/export")
def export_sims(
    categorie: Optional[CategorieSimEnum] = None,
    statut:    Optional[StatutSimEnum]    = None,
    search:    Optional[str]              = None,
    db: Session = Depends(get_db),
):
    q = db.query(NumeroSIM).options(joinedload(NumeroSIM.affectation_active))
    if categorie: q = q.filter(NumeroSIM.categorie == categorie)
    if statut:    q = q.filter(NumeroSIM.statut == statut)
    if search:    q = q.filter(NumeroSIM.numero.ilike(f"%{search}%"))
    sims = q.order_by(NumeroSIM.numero).all()

    rows = []
    rows.append(["Numero", "Categorie", "Operateur", "Statut", "Description",
                 "Affecte a", "Matricule", "Date affectation"])
    for s in sims:
        aff = s.affectation_active
        rows.append([
            s.numero,
            s.categorie.value,
            s.operateur or "",
            s.statut.value,
            s.description or "",
            aff.employee_nom        if aff and aff.employee_nom        else "",
            aff.employee_matricule  if aff and aff.employee_matricule  else "",
            aff.date_debut.strftime("%d/%m/%Y") if aff else "",
        ])

    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerows(rows)

    # BOM UTF-8 (chr(0xFEFF)) pour ouverture correcte dans Excel
    content = chr(0xFEFF) + output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=numeros_sim.csv"},
    )


@router.post("/sims/import")
async def import_sims(file: UploadFile = File(...), db: Session = Depends(get_db)):
    CAT_MAP = {
        "EMPLOYE": "EMPLOYE", "EMPLOYÉ": "EMPLOYE", "EMPLOYE": "EMPLOYE",
        "M2M_SITE": "M2M_SITE", "M2M SITE": "M2M_SITE", "SITE": "M2M_SITE",
        "M2M_VEHICULE": "M2M_VEHICULE", "M2M VEHICULE": "M2M_VEHICULE",
        "M2M VÉHICULE": "M2M_VEHICULE", "VEHICULE": "M2M_VEHICULE",
    }

    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    def norm(s: str) -> str:
        import unicodedata
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s.strip().upper().replace(" ", "_")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    created, updated, errors = 0, 0, []

    for i, raw_row in enumerate(reader, start=2):
        row = {norm(k): (v.strip() if v else "") for k, v in raw_row.items()}

        numero = row.get("NUMERO", row.get("NUM", "")).strip()
        if not numero:
            errors.append({"ligne": i, "message": "Numéro manquant"}); continue

        cat_raw = row.get("CATEGORIE", "EMPLOYE").strip().upper()
        cat_val = CAT_MAP.get(norm(cat_raw))
        if not cat_val:
            errors.append({"ligne": i, "message": f"Catégorie inconnue : '{cat_raw}'"}); continue

        operateur   = row.get("OPERATEUR", row.get("OPERATEUR_", "")) or None
        description = row.get("DESCRIPTION", "") or None

        existing = db.query(NumeroSIM).filter(NumeroSIM.numero == numero).first()
        if existing:
            existing.operateur   = operateur   if operateur   else existing.operateur
            existing.description = description if description else existing.description
            updated += 1
        else:
            db.add(NumeroSIM(
                numero=numero,
                categorie=CategorieSimEnum(cat_val),
                operateur=operateur,
                description=description,
            ))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "errors": errors,
            "total_lignes": created + updated + len(errors)}


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
    active = db.query(AffectationSIM).filter(
        AffectationSIM.sim_id == sim_id, AffectationSIM.is_active == True
    ).first()
    if active:
        who = active.employee_nom or (f"Site #{active.site_id}" if active.site_id else f"Véhicule #{active.vehicule_id}")
        raise HTTPException(409, f"Ce numéro est déjà affecté à {who}. Veuillez d'abord le désaffecter.")

    payload = data.model_dump()
    payload["sim_id"] = sim_id
    obj = AffectationSIM(**payload)
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.patch("/sims/{sim_id}/desaffecter", response_model=AffectationSIMOut)
def desaffecter_sim(sim_id: int, data: DesaffectationSIMIn, db: Session = Depends(get_db)):
    active = db.query(AffectationSIM).filter(
        AffectationSIM.sim_id == sim_id, AffectationSIM.is_active == True
    ).first()
    if not active:
        raise HTTPException(404, "Aucune affectation active pour ce numéro")
    active.is_active = False
    active.date_fin  = date.today()
    active.motif_fin = data.motif
    db.commit(); db.refresh(active)
    return active


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
    rows = (
        db.query(SiteGSM, NumeroSIM.numero)
        .outerjoin(AffectationSIM, and_(
            AffectationSIM.site_id == SiteGSM.id,
            AffectationSIM.is_active == True,
        ))
        .outerjoin(NumeroSIM, NumeroSIM.id == AffectationSIM.sim_id)
        .order_by(SiteGSM.nom)
        .all()
    )
    result = []
    for site, sim_numero in rows:
        item = SiteGSMOut.model_validate(site)
        item.sim_numero = sim_numero
        result.append(item)
    return result


@router.post("/sites", response_model=SiteGSMOut, status_code=201)
def create_site(data: SiteGSMCreate, db: Session = Depends(get_db)):
    obj = SiteGSM(**data.model_dump())
    db.add(obj); db.commit(); db.refresh(obj)
    return obj


@router.get("/sites/export")
def export_sites(db: Session = Depends(get_db)):
    rows_db = (
        db.query(SiteGSM, NumeroSIM.numero)
        .outerjoin(AffectationSIM, and_(
            AffectationSIM.site_id == SiteGSM.id,
            AffectationSIM.is_active == True,
        ))
        .outerjoin(NumeroSIM, NumeroSIM.id == AffectationSIM.sim_id)
        .order_by(SiteGSM.nom)
        .all()
    )
    rows = [["SiteID", "IMSI", "Nom du site", "Localisation", "Numero SIM"]]
    for site, sim_numero in rows_db:
        rows.append([
            site.code_site    or "",
            site.imsi         or "",
            site.nom,
            site.localisation or "",
            sim_numero        or "",
        ])
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerows(rows)
    content = chr(0xFEFF) + output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode("utf-8")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=sites_gsm.csv"},
    )


@router.post("/sites/import")
async def import_sites(file: UploadFile = File(...), db: Session = Depends(get_db)):
    content = await file.read()
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1")

    def norm(s: str) -> str:
        import unicodedata
        s = unicodedata.normalize("NFD", s)
        s = "".join(c for c in s if unicodedata.category(c) != "Mn")
        return s.strip().upper().replace(" ", "_")

    reader = csv.DictReader(io.StringIO(text), delimiter=";")
    created, updated, errors = 0, 0, []

    for i, raw_row in enumerate(reader, start=2):
        row = {norm(k): (v.strip() if v else "") for k, v in raw_row.items()}

        nom = row.get("NOM_DU_SITE", row.get("NOM", "")).strip()
        if not nom:
            errors.append({"ligne": i, "message": "Nom du site manquant"}); continue

        code_site   = row.get("SITEID", row.get("CODE_SITE", "")) or None
        localisation = row.get("LOCALISATION", "") or None
        description  = row.get("DESCRIPTION", "") or None

        existing = db.query(SiteGSM).filter(SiteGSM.nom == nom).first()
        if existing:
            if code_site:    existing.code_site    = code_site
            if localisation: existing.localisation = localisation
            if description:  existing.description  = description
            updated += 1
        else:
            db.add(SiteGSM(nom=nom, code_site=code_site,
                           localisation=localisation, description=description))
            created += 1

    db.commit()
    return {"created": created, "updated": updated, "errors": errors,
            "total_lignes": created + updated + len(errors)}


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
