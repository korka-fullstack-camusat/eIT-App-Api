"""
Import Excel de la flotte SIM (SUIVI_FLOTTE_CAMUSAT_2025_2.xlsx).
Onglets traités :
  - ORANGE-mobiles        → flotte_mobile
  - ORANGE-Gps_Vehicules  → flotte_gps
  - RMS_Orange            → flotte_rms_orange
  - RMS_Free              → flotte_rms_free
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date, datetime, timedelta
import io, math

import openpyxl

from ..database import get_db
from ..models.flotte_sim import FlotteMobile, FlotteGps, FlotteRmsOrange, FlotteRmsFree
from ..models.user import User
from ..services.auth_service import require_editor

try:
    from dateutil.relativedelta import relativedelta
    _HAS_DATEUTIL = True
except ImportError:
    _HAS_DATEUTIL = False

router = APIRouter(prefix="/api/sims", tags=["Flotte SIM (import)"])


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _to_str(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return None if s in ("", "nan", "None", "NaT", "-", "—") else s


def _to_date(val) -> Optional[date]:
    if val is None:
        return None
    if isinstance(val, date) and not isinstance(val, datetime):
        return val
    if isinstance(val, datetime):
        return val.date()
    s = str(val).strip()
    if not s or s in ("nan", "None", "NaT"):
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s[:10], fmt).date()
        except ValueError:
            continue
    return None


def _to_int(val) -> Optional[int]:
    if val is None:
        return None
    try:
        f = float(str(val))
        return None if math.isnan(f) else int(f)
    except (ValueError, TypeError):
        return None


def _to_decimal(val):
    if val is None:
        return None
    try:
        f = float(str(val))
        return None if math.isnan(f) else f
    except (ValueError, TypeError):
        return None


def _header_map(row) -> dict[str, int]:
    return {str(h or "").strip().lower(): i for i, h in enumerate(row)}


def _find_header_row(rows: list, keywords: list[str], max_scan: int = 4) -> int:
    """
    Retourne l'index de la première ligne contenant ≥ 2 mots-clés parmi keywords.
    Repli sur la première ligne avec ≥ 1 mot-clé, puis sur 0.
    """
    for threshold in (2, 1):
        for i, row in enumerate(rows[:max_scan]):
            row_str = [str(v or "").strip().lower() for v in row]
            matches = sum(1 for cell in row_str if any(kw in cell for kw in keywords))
            if matches >= threshold:
                return i
    return 0


def _end_date(d: Optional[date], months: Optional[int]) -> Optional[date]:
    """Calcule la date de fin d'engagement."""
    if d is None or months is None:
        return None
    if _HAS_DATEUTIL:
        from dateutil.relativedelta import relativedelta
        return d + relativedelta(months=months)
    # Fallback approximatif si dateutil absent
    import calendar
    month = d.month - 1 + months
    year  = d.year + month // 12
    month = month % 12 + 1
    day   = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


# ── Parseurs par onglet ────────────────────────────────────────────────────────

def _parse_mobiles(ws) -> list[dict]:
    """En-têtes en ligne 2 (index 1)."""
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    hm = _header_map(rows[1])

    def _col(name: str) -> Optional[int]:
        for k, v in hm.items():
            if name in k:
                return v
        return None

    col_matricule    = _col("matricule")
    col_benef        = _col("beneficiaire") if _col("beneficiaire") is not None else _col("bénéficiaire")
    col_service      = next((v for k, v in hm.items() if k not in ("matricule",) and ("service" in k or k == "")), None)
    col_bl           = next((v for k, v in hm.items() if k in ("bl", "business line", "b.l")), None)
    col_fonction     = _col("fonction")
    col_numero       = next((v for k, v in hm.items() if "ligne" in k or "n° ligne" in k or "numéro" in k), None)
    col_engagement   = _col("engagement")
    col_activation   = next((v for k, v in hm.items() if "activation" in k), None)
    col_formule      = _col("formule") if _col("formule") is not None else _col("forfait")
    col_internet     = next((v for k, v in hm.items() if "internet" in k), None)
    col_total        = next((v for k, v in hm.items() if "total" in k and "positionn" in k), None)

    records = []
    for row in rows[2:]:
        if col_numero is None:
            continue
        numero = _to_str(row[col_numero] if col_numero < len(row) else None)
        if not numero:
            continue
        records.append(dict(
            matricule        = _to_str(row[col_matricule]  if col_matricule  is not None and col_matricule  < len(row) else None),
            beneficiaire     = _to_str(row[col_benef]      if col_benef      is not None and col_benef      < len(row) else None),
            service          = _to_str(row[col_service]    if col_service    is not None and col_service    < len(row) else None),
            business_line    = _to_str(row[col_bl]         if col_bl         is not None and col_bl         < len(row) else None),
            fonction         = _to_str(row[col_fonction]   if col_fonction   is not None and col_fonction   < len(row) else None),
            numero_ligne     = numero,
            engagement       = _to_int(row[col_engagement] if col_engagement is not None and col_engagement < len(row) else None),
            date_activation  = _to_date(row[col_activation]if col_activation is not None and col_activation < len(row) else None),
            formule          = _to_str(row[col_formule]    if col_formule    is not None and col_formule    < len(row) else None),
            forfait_internet = _to_str(row[col_internet]   if col_internet   is not None and col_internet   < len(row) else None),
            total_positionne = _to_decimal(row[col_total]  if col_total      is not None and col_total      < len(row) else None),
        ))
    return records


def _parse_gps(ws) -> list[dict]:
    """En-têtes auto-détectés dans les 4 premières lignes."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    h_idx = _find_header_row(rows, ["sim", "immatr", "engagement", "imei", "activation", "modèle", "modele"], max_scan=4)
    hm = _header_map(rows[h_idx])

    def _col(name: str) -> Optional[int]:
        for k, v in hm.items():
            if name in k:
                return v
        return None

    col_sim        = next((v for k, v in hm.items() if "sim" in k or "n°" in k or "numéro" in k or "numero" in k), None)
    col_engagement = next((v for k, v in hm.items() if "engagement" in k or "durée" in k), None)
    col_activation = next((v for k, v in hm.items() if "activation" in k), None)
    col_immat      = next((v for k, v in hm.items() if "immatr" in k), None)
    col_modele     = next((v for k, v in hm.items() if "modèle" in k or "model" in k), None)
    col_imei       = _col("imei")
    col_fact       = next((v for k, v in hm.items() if "factur" in k), None)

    records = []
    for row in rows[h_idx + 1:]:
        if col_sim is None:
            continue
        sim = _to_str(row[col_sim] if col_sim < len(row) else None)
        if not sim:
            continue
        records.append(dict(
            numero_sim      = sim,
            engagement      = _to_int(row[col_engagement] if col_engagement is not None and col_engagement < len(row) else None),
            date_activation = _to_date(row[col_activation]if col_activation is not None and col_activation < len(row) else None),
            immatriculation = _to_str(row[col_immat]      if col_immat      is not None and col_immat      < len(row) else None),
            modele          = _to_str(row[col_modele]     if col_modele     is not None and col_modele     < len(row) else None),
            imei            = _to_str(row[col_imei]       if col_imei       is not None and col_imei       < len(row) else None),
            facturation     = _to_decimal(row[col_fact]   if col_fact       is not None and col_fact       < len(row) else None),
        ))
    return records


def _parse_rms_orange(ws) -> list[dict]:
    """En-têtes auto-détectés dans les 4 premières lignes."""
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []
    h_idx = _find_header_row(rows, ["numéro", "numero", "imsi", "site", "engagement", "activation", "n°"], max_scan=4)
    hm = _header_map(rows[h_idx])

    def _col(name: str) -> Optional[int]:
        for k, v in hm.items():
            if name in k:
                return v
        return None

    # Numéro : plusieurs variantes possibles dans les fichiers Orange
    col_numero = next((
        v for k, v in hm.items()
        if k in ("numéro", "numero", "n°", "no") or
           ("numéro" in k) or ("numero" in k) or ("n°" in k and "sim" not in k)
    ), None)
    # Dernier recours positonnel : première colonne non vide avec une valeur ressemblant à un n° (à l'import)
    if col_numero is None:
        col_numero = 1  # fallback position

    col_engagement = next((v for k, v in hm.items() if "engagement" in k or ("mois" in k and "activation" not in k)), None)
    col_activation = next((v for k, v in hm.items() if "activation" in k), None)
    col_imsi       = _col("imsi")
    col_site_id    = next((v for k, v in hm.items() if "site" in k and ("id" in k or "code" in k or "réf" in k or "ref" in k)), None)
    col_nom_site   = next((v for k, v in hm.items() if "nom" in k and "site" in k), None)
    # Si site_id non trouvé, prendre la colonne "site" seule
    if col_site_id is None:
        col_site_id = next((v for k, v in hm.items() if k == "site"), None)

    records = []
    for row in rows[h_idx + 1:]:
        if col_numero is None or col_numero >= len(row):
            continue
        numero = _to_str(row[col_numero])
        if not numero:
            continue
        records.append(dict(
            numero          = numero,
            engagement      = _to_int(row[col_engagement] if col_engagement is not None and col_engagement < len(row) else None),
            date_activation = _to_date(row[col_activation]if col_activation is not None and col_activation < len(row) else None),
            imsi            = _to_str(row[col_imsi]       if col_imsi       is not None and col_imsi       < len(row) else None),
            site_id         = _to_str(row[col_site_id]    if col_site_id    is not None and col_site_id    < len(row) else None),
            nom_site        = _to_str(row[col_nom_site]   if col_nom_site   is not None and col_nom_site   < len(row) else None),
        ))
    return records


def _parse_rms_free(ws) -> list[dict]:
    """En-têtes en ligne 2 (index 1) — ligne 0 est un titre."""
    rows = list(ws.iter_rows(values_only=True))
    if len(rows) < 2:
        return []
    hm = _header_map(rows[1])

    # Colonnes sans nom clair : on prend les 3 premières non-vides
    indexed = [(i, k) for i, k in enumerate(rows[1]) if k is not None and str(k).strip()]
    col_numero  = indexed[1][0] if len(indexed) > 1 else None
    col_imsi    = indexed[2][0] if len(indexed) > 2 else None
    col_site_id = next((v for k, v in hm.items() if "site" in k and "id" in k), None)
    col_nom     = next((v for k, v in hm.items() if "nom" in k), None)

    records = []
    for row in rows[2:]:
        if col_numero is None or col_numero >= len(row):
            continue
        numero = _to_str(row[col_numero])
        if not numero:
            continue
        records.append(dict(
            numero   = numero,
            imsi     = _to_str(row[col_imsi]    if col_imsi    is not None and col_imsi    < len(row) else None),
            site_id  = _to_str(row[col_site_id] if col_site_id is not None and col_site_id < len(row) else None),
            nom_site = _to_str(row[col_nom]     if col_nom     is not None and col_nom     < len(row) else None),
        ))
    return records


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/import", status_code=200, summary="Importer le fichier Suivi Flotte SIM (.xlsx)")
async def import_flotte(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    if not (file.filename or "").lower().endswith(".xlsx"):
        raise HTTPException(400, "Seuls les fichiers .xlsx sont acceptés")

    content = await file.read()
    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    sheets = {n.lower(): n for n in wb.sheetnames}

    stats: dict[str, int] = {}

    # ORANGE-mobiles
    key = next((k for k in sheets if "mobile" in k or "orange-mobile" in k), None)
    mobiles = _parse_mobiles(wb[sheets[key]]) if key else []
    db.query(FlotteMobile).delete()
    db.flush()
    for rec in mobiles:
        db.add(FlotteMobile(**rec))
    stats["mobiles"] = len(mobiles)

    # ORANGE-Gps_Vehicules
    key = next((k for k in sheets if "gps" in k or "vehicule" in k or "véhicule" in k), None)
    gps = _parse_gps(wb[sheets[key]]) if key else []
    db.query(FlotteGps).delete()
    db.flush()
    for rec in gps:
        db.add(FlotteGps(**rec))
    stats["gps"] = len(gps)

    # RMS_Orange
    key = next((k for k in sheets if "rms" in k and "orange" in k), None)
    rms_orange = _parse_rms_orange(wb[sheets[key]]) if key else []
    db.query(FlotteRmsOrange).delete()
    db.flush()
    for rec in rms_orange:
        db.add(FlotteRmsOrange(**rec))
    stats["rms_orange"] = len(rms_orange)

    # RMS_Free
    key = next((k for k in sheets if "rms" in k and "free" in k), None)
    rms_free = _parse_rms_free(wb[sheets[key]]) if key else []
    db.query(FlotteRmsFree).delete()
    db.flush()
    for rec in rms_free:
        db.add(FlotteRmsFree(**rec))
    stats["rms_free"] = len(rms_free)

    db.commit()
    return {"message": "Import terminé", "stats": stats, "total": sum(stats.values())}


# ── Lecture ────────────────────────────────────────────────────────────────────

@router.get("/mobiles", summary="SIMs employés (ORANGE-mobiles)")
def list_mobiles(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    from sqlalchemy import or_
    q = db.query(FlotteMobile)
    if search:
        q = q.filter(or_(
            FlotteMobile.numero_ligne.ilike(f"%{search}%"),
            FlotteMobile.beneficiaire.ilike(f"%{search}%"),
            FlotteMobile.matricule.ilike(f"%{search}%"),
            FlotteMobile.service.ilike(f"%{search}%"),
        ))
    return q.order_by(FlotteMobile.beneficiaire).all()


@router.get("/gps", summary="SIMs GPS véhicules")
def list_gps(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    from sqlalchemy import or_
    q = db.query(FlotteGps)
    if search:
        q = q.filter(or_(
            FlotteGps.numero_sim.ilike(f"%{search}%"),
            FlotteGps.immatriculation.ilike(f"%{search}%"),
        ))
    return q.order_by(FlotteGps.immatriculation).all()


@router.get("/rms-orange", summary="SIMs RMS réseau Orange")
def list_rms_orange(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    from sqlalchemy import or_
    q = db.query(FlotteRmsOrange)
    if search:
        q = q.filter(or_(
            FlotteRmsOrange.numero.ilike(f"%{search}%"),
            FlotteRmsOrange.nom_site.ilike(f"%{search}%"),
            FlotteRmsOrange.site_id.ilike(f"%{search}%"),
        ))
    return q.order_by(FlotteRmsOrange.numero).all()


@router.get("/rms-free", summary="SIMs RMS réseau Free")
def list_rms_free(
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    from sqlalchemy import or_
    q = db.query(FlotteRmsFree)
    if search:
        q = q.filter(or_(
            FlotteRmsFree.numero.ilike(f"%{search}%"),
            FlotteRmsFree.nom_site.ilike(f"%{search}%"),
            FlotteRmsFree.site_id.ilike(f"%{search}%"),
        ))
    return q.order_by(FlotteRmsFree.numero).all()


# ── Alertes ────────────────────────────────────────────────────────────────────

@router.get("/alertes", summary="SIMs dont le contrat expire dans 3 mois")
def get_alertes(
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    """
    Retourne les SIMs (mobiles + GPS + RMS Orange) dont la date de fin d'engagement
    (date_activation + engagement mois) est dans les 90 prochains jours ou déjà dépassée.
    RMS Free est exclu (pas de champ engagement).
    """
    today     = date.today()
    seuil     = today + timedelta(days=90)
    alertes   = []

    def _make_alerte(categorie: str, numero: str, d_act: Optional[date], eng: Optional[int], extra: dict) -> Optional[dict]:
        fin = _end_date(d_act, eng)
        if fin is None:
            return None
        if fin > seuil:
            return None
        return {
            "categorie":      categorie,
            "numero":         numero,
            "date_activation": d_act.isoformat() if d_act else None,
            "engagement":     eng,
            "date_fin":       fin.isoformat(),
            "expire":         fin < today,
            **extra,
        }

    for row in db.query(FlotteMobile).all():
        a = _make_alerte(
            "MOBILE", row.numero_ligne, row.date_activation, row.engagement,
            {"beneficiaire": row.beneficiaire, "matricule": row.matricule, "service": row.service},
        )
        if a:
            alertes.append(a)

    for row in db.query(FlotteGps).all():
        a = _make_alerte(
            "GPS", row.numero_sim, row.date_activation, row.engagement,
            {"immatriculation": row.immatriculation, "modele": row.modele},
        )
        if a:
            alertes.append(a)

    for row in db.query(FlotteRmsOrange).all():
        a = _make_alerte(
            "RMS_ORANGE", row.numero, row.date_activation, row.engagement,
            {"site_id": row.site_id, "nom_site": row.nom_site},
        )
        if a:
            alertes.append(a)

    alertes.sort(key=lambda x: x["date_fin"])
    return {
        "total":   len(alertes),
        "seuil":   seuil.isoformat(),
        "alertes": alertes,
    }


# ── Stats globales ─────────────────────────────────────────────────────────────

@router.get("/stats", summary="Compteurs globaux de la flotte SIM")
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_editor),
):
    today = date.today()
    seuil = today + timedelta(days=90)

    nb_alertes = 0
    for table, num_field, act_field, eng_field in [
        (FlotteMobile,    "numero_ligne",  "date_activation", "engagement"),
        (FlotteGps,       "numero_sim",    "date_activation", "engagement"),
        (FlotteRmsOrange, "numero",        "date_activation", "engagement"),
    ]:
        for row in db.query(table).all():
            fin = _end_date(getattr(row, act_field), getattr(row, eng_field))
            if fin and fin <= seuil:
                nb_alertes += 1

    return {
        "mobiles":    db.query(FlotteMobile).count(),
        "gps":        db.query(FlotteGps).count(),
        "rms_orange": db.query(FlotteRmsOrange).count(),
        "rms_free":   db.query(FlotteRmsFree).count(),
        "alertes":    nb_alertes,
    }
