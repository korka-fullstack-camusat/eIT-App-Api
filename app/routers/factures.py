from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional
from decimal import Decimal
import io
import pandas as pd
from ..database import get_db
from ..models.facture import FactureTelecom, LigneFacture
from ..models.telephonie import NumeroSIM
from ..schemas.facture import FactureOut, ImportResult

router = APIRouter(prefix="/api/factures", tags=["Factures télécom"])


@router.get("/", response_model=list[FactureOut])
def list_factures(annee: Optional[int] = None, db: Session = Depends(get_db)):
    q = db.query(FactureTelecom)
    if annee:
        q = q.filter(FactureTelecom.annee == annee)
    return q.order_by(FactureTelecom.annee.desc(), FactureTelecom.mois.desc()).all()


@router.get("/{facture_id}", response_model=FactureOut)
def get_facture(facture_id: int, db: Session = Depends(get_db)):
    obj = db.query(FactureTelecom).filter(FactureTelecom.id == facture_id).first()
    if not obj:
        raise HTTPException(404, "Facture introuvable")
    return obj


@router.post("/import", response_model=ImportResult)
async def import_facture(
    mois:      int = Form(...),
    annee:     int = Form(...),
    operateur: Optional[str] = Form(None),
    notes:     Optional[str] = Form(None),
    file:      UploadFile = File(...),
    db:        Session = Depends(get_db),
):
    # Vérifier doublon
    existing = db.query(FactureTelecom).filter(
        FactureTelecom.mois == mois, FactureTelecom.annee == annee
    ).first()
    if existing:
        raise HTTPException(400, f"Une facture existe déjà pour {mois:02d}/{annee}")

    # Lire le fichier Excel / CSV
    content = await file.read()
    try:
        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(content), sep=";", dtype=str)
        else:
            df = pd.read_excel(io.BytesIO(content), dtype=str)
    except Exception as e:
        raise HTTPException(400, f"Impossible de lire le fichier : {e}")

    # Normaliser les colonnes — chercher NUMERO et MONTANT (insensible à la casse)
    df.columns = [c.strip().upper() for c in df.columns]
    col_num    = next((c for c in df.columns if "NUM" in c or "TEL" in c), None)
    col_mont   = next((c for c in df.columns if "MONT" in c or "COUT" in c or "AMOUNT" in c), None)
    if not col_num or not col_mont:
        raise HTTPException(400, "Colonnes NUMERO et MONTANT introuvables dans le fichier")

    # Charger tous les numéros SIM connus
    sims_map = {s.numero: s.id for s in db.query(NumeroSIM).all()}

    facture = FactureTelecom(mois=mois, annee=annee, operateur=operateur, notes=notes, nom_fichier=file.filename)
    db.add(facture)
    db.flush()

    reconnus = 0
    non_reconnus_list = []
    montant_total = Decimal("0")

    for _, row in df.iterrows():
        numero_raw = str(row[col_num]).strip()
        try:
            montant = Decimal(str(row[col_mont]).replace(" ", "").replace(",", "."))
        except Exception:
            continue

        sim_id = sims_map.get(numero_raw)
        non_reconnu = "N" if sim_id else "O"
        if sim_id:
            reconnus += 1
        else:
            non_reconnus_list.append(numero_raw)

        db.add(LigneFacture(
            facture_id=facture.id,
            sim_id=sim_id,
            numero_raw=numero_raw,
            montant=montant,
            non_reconnu=non_reconnu,
        ))
        montant_total += montant

    db.commit()

    return ImportResult(
        facture_id=facture.id,
        total_lignes=reconnus + len(non_reconnus_list),
        reconnus=reconnus,
        non_reconnus=len(non_reconnus_list),
        montant_total=montant_total,
        numeros_inconnus=non_reconnus_list,
    )


@router.delete("/{facture_id}", status_code=204)
def delete_facture(facture_id: int, db: Session = Depends(get_db)):
    obj = db.query(FactureTelecom).filter(FactureTelecom.id == facture_id).first()
    if not obj:
        raise HTTPException(404, "Facture introuvable")
    db.delete(obj); db.commit()


@router.get("/stats/mensuel")
def stats_mensuel(annee: int, db: Session = Depends(get_db)):
    from ..models.telephonie import CategorieSimEnum
    rows = (
        db.query(
            FactureTelecom.mois,
            NumeroSIM.categorie,
            func.sum(LigneFacture.montant).label("total"),
        )
        .join(LigneFacture, FactureTelecom.id == LigneFacture.facture_id)
        .join(NumeroSIM, LigneFacture.sim_id == NumeroSIM.id)
        .filter(FactureTelecom.annee == annee, LigneFacture.sim_id.isnot(None))
        .group_by(FactureTelecom.mois, NumeroSIM.categorie)
        .order_by(FactureTelecom.mois)
        .all()
    )
    result: dict = {}
    for r in rows:
        m = str(r.mois)
        if m not in result:
            result[m] = {}
        result[m][r.categorie] = float(r.total)
    return result
