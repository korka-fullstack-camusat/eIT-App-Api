"""
Service de remplissage de templates Word (.docx).

L'utilisateur upload un fichier .docx contenant des balises {{CHAMP}}.
Ce service détecte automatiquement toutes les balises présentes et les
remplace avec les données de l'attribution / de la décharge.

Balises disponibles — Attestation :
  {{NOM}}              Nom de l'employé
  {{PRENOM}}           Prénom
  {{MATRICULE}}        Matricule
  {{SERVICE}}          Service / département
  {{POSTE}}            Poste / fonction
  {{DATE_JOUR}}        Date du jour (dd/mm/yyyy)
  {{DATE_ATTRIBUTION}} Date de la première attribution
  {{NB_MATERIELS}}     Nombre de matériels attribués
  {{MATERIELS_LISTE}}  Liste des matériels (une ligne par matériel)
  Pour chaque matériel (N = 1, 2, 3…) :
    {{MATERIEL_N}}     Libellé complet du matériel
    {{MARQUE_N}}       Marque
    {{MODELE_N}}       Modèle
    {{TYPE_N}}         Type (PC Portable, Écran…)
    {{SERIE_N}}        N° Série
    {{MAC_N}}          Adresse MAC
    {{ETAT_N}}         État (Neuf, Bon, Usagé…)
    {{DATE_ATTR_N}}    Date d'attribution (dd/mm/yyyy)

Balises disponibles — Décharge :
  (toutes les balises employé ci-dessus)
  {{MATERIEL}}         Libellé complet du matériel
  {{MARQUE}}           Marque
  {{MODELE}}           Modèle
  {{TYPE}}             Type
  {{SERIE}}            N° Série
  {{MAC}}              Adresse MAC
  {{ETAT_REMISE}}      État à la remise
  {{DATE_ATTRIBUTION}} Date d'attribution
  {{DATE_RESTITUTION}} Date de restitution
  {{MOTIF}}            Motif de restitution
  {{NOTES}}            Notes
"""
import re
import io
import os
from pathlib import Path
from datetime import date as dt_date, datetime

TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"
TEMPLATE_DIR.mkdir(exist_ok=True)

# Chemin des templates stockés
TEMPLATE_PATHS = {
    "attestation": TEMPLATE_DIR / "attestation.docx",
    "decharge":    TEMPLATE_DIR / "decharge.docx",
}

TYPE_LABELS = {
    "ORDINATEUR_PORTABLE": "PC Portable",
    "ORDINATEUR_FIXE":     "PC Bureau",
    "ECRAN":               "Écran",
    "SOURIS":              "Souris",
    "CLAVIER":             "Clavier",
    "TELEPHONE":           "Téléphone",
    "IMPRIMANTE":          "Imprimante",
    "SWITCH":              "Switch réseau",
    "ROUTEUR":             "Routeur",
    "ONDULEUR":            "Onduleur",
    "AUTRE":               "Matériel informatique",
}


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _fmt_date(d) -> str:
    if not d:
        return ""
    if isinstance(d, (dt_date, datetime)):
        return d.strftime("%d/%m/%Y")
    return str(d)


def _mat_label(m) -> str:
    """Libellé court d'un matériel : 'PC Portable Dell Latitude 5420'."""
    parts = [TYPE_LABELS.get(m.type_materiel, m.type_materiel), m.marque]
    if m.modele:
        parts.append(m.modele)
    return " ".join(parts)


def scan_placeholders(docx_bytes: bytes) -> list[str]:
    """Extrait toutes les balises {{...}} présentes dans le template."""
    from docx import Document
    doc = Document(io.BytesIO(docx_bytes))
    found: set[str] = set()
    pattern = re.compile(r"\{\{([A-Z0-9_]+(?:_\d+)?)\}\}")

    def scan_para(para):
        full = "".join(r.text for r in para.runs)
        for m in pattern.finditer(full):
            found.add(m.group(1))

    for para in doc.paragraphs:
        scan_para(para)
    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    scan_para(para)
    # En-têtes / pieds de page
    for section in doc.sections:
        for para in section.header.paragraphs:
            scan_para(para)
        for para in section.footer.paragraphs:
            scan_para(para)

    return sorted(found)


def _replace_in_doc(doc, fields: dict[str, str]):
    """Remplace toutes les balises {{CLE}} dans le document par leur valeur.
    Les paragraphes dont TOUT le contenu est une balise vide sont supprimés."""
    from docx.oxml.ns import qn as _qn
    pattern      = re.compile(r"\{\{([A-Z0-9_]+(?:_\d+)?)\}\}")
    only_pattern = re.compile(r"^\s*\{\{([A-Z0-9_]+(?:_\d+)?)\}\}\s*$")

    def _replace_para(para) -> bool:
        """Retourne True si le paragraphe doit être supprimé (balise vide)."""
        if not para.runs:
            return False
        full_text = "".join(r.text for r in para.runs)
        # Si le paragraphe ne contient qu'une balise → vérifier si elle est vide
        m = only_pattern.match(full_text)
        if m:
            val = fields.get(m.group(1), None)
            if val is not None and val.strip() == "":
                return True   # supprimer ce paragraphe
        new_text = pattern.sub(
            lambda mx: fields.get(mx.group(1), mx.group(0)),
            full_text,
        )
        if new_text != full_text:
            para.runs[0].text = new_text
            for r in para.runs[1:]:
                r.text = ""
        return False

    def _remove_para(para):
        """Supprime physiquement un paragraphe du XML."""
        p = para._p
        p.getparent().remove(p)

    to_remove = []
    for para in doc.paragraphs:
        if _replace_para(para):
            to_remove.append(para)
    for para in to_remove:
        _remove_para(para)

    for table in doc.tables:
        for row in table.rows:
            for cell in row.cells:
                cell_remove = []
                for para in cell.paragraphs:
                    if _replace_para(para):
                        cell_remove.append(para)
                for para in cell_remove:
                    _remove_para(para)

    for section in doc.sections:
        for para in section.header.paragraphs:
            _replace_para(para)
        for para in section.footer.paragraphs:
            _replace_para(para)


# ── Générateurs ───────────────────────────────────────────────────────────────

def generate_attestation_from_template(attributions: list) -> bytes:
    """
    Génère l'attestation en remplissant le template uploadé.
    `attributions` : liste d'attributions ACTIVES d'un même employé.
    """
    from docx import Document
    template_path = TEMPLATE_PATHS["attestation"]
    if not template_path.exists():
        raise FileNotFoundError("Aucun template d'attestation uploadé")

    doc = Document(str(template_path))
    a0  = attributions[0]  # référence employé

    fields: dict[str, str] = {
        "NOM":              a0.employee_nom or "",
        "PRENOM":           a0.employee_prenom or "",
        "MATRICULE":        a0.employee_matricule or "",
        "SERVICE":          a0.employee_service or "",
        "POSTE":            a0.employee_poste or "",
        "DATE_JOUR":        datetime.now().strftime("%d/%m/%Y"),
        "DATE_ATTRIBUTION": _fmt_date(min(a.date_attribution for a in attributions)),
        "NB_MATERIELS":     str(len(attributions)),
        "MATERIELS_LISTE":  "\n".join(
            f"• {_mat_label(a.materiel)}" for a in attributions if a.materiel
        ),
    }

    # Remplir les slots de matériels (1 à 10) — les slots vides seront supprimés
    for i in range(1, 11):
        if i <= len(attributions):
            a_i = attributions[i - 1]
            m   = a_i.materiel
            if m:
                # Construire la description complète selon le type d'identifiant
                desc = _mat_label(m)
                if m.adresse_mac:
                    desc += f", Mac Address : {m.adresse_mac}"
                elif m.numero_serie:
                    desc += f", S/N : {m.numero_serie}"
                fields[f"MATERIEL_{i}"]  = desc
                fields[f"MARQUE_{i}"]    = m.marque or ""
                fields[f"MODELE_{i}"]    = m.modele or ""
                fields[f"TYPE_{i}"]      = TYPE_LABELS.get(m.type_materiel, m.type_materiel or "")
                fields[f"SERIE_{i}"]     = m.numero_serie or ""
                fields[f"MAC_{i}"]       = m.adresse_mac or ""
                fields[f"ETAT_{i}"]      = m.etat or ""
                fields[f"DATE_ATTR_{i}"] = _fmt_date(a_i.date_attribution)
            else:
                fields[f"MATERIEL_{i}"] = ""
        else:
            # Slot vide → sera supprimé par _replace_in_doc
            fields[f"MATERIEL_{i}"] = ""

    _replace_in_doc(doc, fields)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_decharge_from_template(attribution) -> bytes:
    """
    Génère la décharge en remplissant le template uploadé.
    `attribution` : une attribution (active ou clôturée).
    """
    from docx import Document
    template_path = TEMPLATE_PATHS["decharge"]
    if not template_path.exists():
        raise FileNotFoundError("Aucun template de décharge uploadé")

    doc = Document(str(template_path))
    a = attribution
    m = a.materiel

    MOTIF_LABELS = {
        "DEPART": "Départ", "CHANGEMENT": "Changement", "PANNE": "Panne",
        "FIN_CONTRAT": "Fin de contrat", "AUTRE": "Autre",
    }

    fields: dict[str, str] = {
        "NOM":               a.employee_nom or "",
        "PRENOM":            a.employee_prenom or "",
        "MATRICULE":         a.employee_matricule or "",
        "SERVICE":           a.employee_service or "",
        "POSTE":             a.employee_poste or "",
        "DATE_JOUR":         datetime.now().strftime("%d/%m/%Y"),
        "DATE_ATTRIBUTION":  _fmt_date(a.date_attribution),
        "DATE_RESTITUTION":  _fmt_date(a.date_restitution),
        "MOTIF":             MOTIF_LABELS.get(a.motif_restitution or "", a.motif_restitution or ""),
        "ETAT_REMISE":       a.etat_remise or "",
        "NOTES":             a.notes or "",
        # Matériel
        "MATERIEL":  _mat_label(m) if m else "",
        "MARQUE":    m.marque or "" if m else "",
        "MODELE":    m.modele or "" if m else "",
        "TYPE":      TYPE_LABELS.get(m.type_materiel, m.type_materiel or "") if m else "",
        "SERIE":     m.numero_serie or "" if m else "",
        "MAC":       m.adresse_mac or "" if m else "",
    }

    _replace_in_doc(doc, fields)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def template_exists(doc_type: str) -> bool:
    return TEMPLATE_PATHS.get(doc_type, Path("")).exists()


def save_template(doc_type: str, content: bytes) -> None:
    path = TEMPLATE_PATHS.get(doc_type)
    if not path:
        raise ValueError(f"Type inconnu : {doc_type}")
    path.write_bytes(content)
