from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import StreamingResponse
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


@router.get("/export-excel")
def export_factures_excel(
    annee: Optional[int] = Query(None),
    mois:  Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Export Excel stylisé — une ligne par ligne de facture."""
    from datetime import datetime
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    MOIS_LABELS = ["","Janvier","Février","Mars","Avril","Mai","Juin",
                   "Juillet","Août","Septembre","Octobre","Novembre","Décembre"]

    q = db.query(FactureTelecom)
    if annee: q = q.filter(FactureTelecom.annee == annee)
    if mois:  q = q.filter(FactureTelecom.mois == mois)
    factures = q.order_by(FactureTelecom.annee.desc(), FactureTelecom.mois.desc()).all()

    BLUE_HDR = "1B3D6F"; WHITE = "FFFFFF"; ROW_EVEN = "EEF4FF"; BORDER_COL = "C5D3E8"
    thin = Side(style="thin", color=BORDER_COL)
    border_all = Border(left=thin, right=thin, top=thin, bottom=thin)

    wb = Workbook(); ws = wb.active; ws.title = "Factures Télécom"

    HEADERS = ["Période", "Opérateur", "Fichier", "Numéro", "Montant (FCFA)", "Reconnu", "Notes"]

    # Titre
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(HEADERS))
    tc = ws.cell(row=1, column=1, value="FACTURES TÉLÉCOM")
    tc.font = Font(name="Calibri", bold=True, size=14, color=WHITE)
    tc.fill = PatternFill("solid", fgColor=BLUE_HDR)
    tc.alignment = Alignment(horizontal="center", vertical="center")
    ws.row_dimensions[1].height = 32

    # Sous-titre
    parts = [f"Exporté le {datetime.now().strftime('%d/%m/%Y')}"]
    if annee: parts.append(f"Année {annee}")
    if mois:  parts.append(MOIS_LABELS[mois])
    total_lignes = sum(len(f.lignes) for f in factures)
    parts.append(f"{len(factures)} facture(s) · {total_lignes} ligne(s)")

    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(HEADERS))
    sc = ws.cell(row=2, column=1, value="  |  ".join(parts))
    sc.font = Font(name="Calibri", italic=True, size=9, color="5B7DB1")
    sc.fill = PatternFill("solid", fgColor="D9E6F7")
    sc.alignment = Alignment(horizontal="left", vertical="center", indent=1)
    ws.row_dimensions[2].height = 18
    ws.row_dimensions[3].height = 6

    # En-têtes
    HDR_ROW = 4
    for ci, h in enumerate(HEADERS, start=1):
        c = ws.cell(row=HDR_ROW, column=ci, value=h)
        c.font = Font(name="Calibri", bold=True, size=10, color=WHITE)
        c.fill = PatternFill("solid", fgColor=BLUE_HDR)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = border_all
    ws.row_dimensions[HDR_ROW].height = 24
    ws.freeze_panes = ws.cell(row=HDR_ROW + 1, column=1)

    ri = 0
    for f in factures:
        periode = f"{MOIS_LABELS[f.mois]} {f.annee}"
        for l in f.lignes:
            row_num  = HDR_ROW + 1 + ri
            row_fill = PatternFill("solid", fgColor=(ROW_EVEN if ri % 2 == 0 else WHITE))
            vals = [
                periode,
                f.operateur or "",
                f.nom_fichier or "",
                l.numero_raw or "",
                float(l.montant) if l.montant else 0,
                "Oui" if l.sim_id else "Non",
                f.notes or "",
            ]
            for ci, v in enumerate(vals, start=1):
                c = ws.cell(row=row_num, column=ci, value=v)
                c.fill = row_fill
                c.font = Font(name="Calibri", size=10)
                c.alignment = Alignment(vertical="center", horizontal="left", indent=1)
                c.border = border_all
                # Montant aligné à droite
                if ci == 5:
                    c.alignment = Alignment(vertical="center", horizontal="right")
                    c.number_format = "#,##0"
                # Reconnu coloré
                if ci == 6 and not l.sim_id:
                    c.font = Font(name="Calibri", size=10, color="D97706")
            ws.row_dimensions[row_num].height = 18
            ri += 1

    # Largeurs
    widths = [16, 12, 28, 18, 16, 10, 20]
    for ci, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(ci)].width = w

    ws.oddFooter.center.text = "&\"Calibri\"&8 CAMUSAT — Factures Télécom  |  Page &P / &N"

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    fname = f"factures_{annee or 'all'}"
    if mois: fname += f"_{mois:02d}"
    fname += ".xlsx"

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={fname}"},
    )


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
