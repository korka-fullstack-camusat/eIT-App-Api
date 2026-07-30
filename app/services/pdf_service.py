"""Génération des documents PDF — Décharge et Attestation de mise à disposition (ReportLab)."""
import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, ListFlowable, ListItem,
)

# ── Couleurs Camusat ───────────────────────────────────────────────────────────
BLUE  = colors.HexColor("#003c71")
RED   = colors.HexColor("#c0392b")
GREY  = colors.HexColor("#64748b")
LGREY = colors.HexColor("#f1f5f9")

# ── Mapping type matériel → libellé français ──────────────────────────────────
TYPE_LABELS = {
    "ORDINATEUR_PORTABLE": ("Un ordinateur portable",   "m"),
    "ORDINATEUR_FIXE":     ("Un ordinateur de bureau",  "m"),
    "ECRAN":               ("Un écran",                 "m"),
    "SOURIS":              ("Une souris",               "f"),
    "CLAVIER":             ("Un clavier",               "m"),
    "TELEPHONE":           ("Un téléphone portable",    "m"),
    "TABLETTE":            ("Une tablette",             "f"),
    "IMPRIMANTE":          ("Une imprimante",           "f"),
    "SWITCH":              ("Un switch réseau",         "m"),
    "ROUTEUR":             ("Un routeur",               "m"),
    "ONDULEUR":            ("Un onduleur",              "m"),
    "AP":                  ("Un point d'accès",         "m"),
    "SERVEUR":             ("Un serveur",               "m"),
    "PARE_FEU":            ("Un pare-feu",              "m"),
    "AUTRE":               ("Un matériel informatique", "m"),
}


def _mat_description(m) -> str:
    """Retourne la ligne bullet d'un matériel : type marque modele, identifiant."""
    label, _ = TYPE_LABELS.get(m.type_materiel, ("Un matériel", "m"))
    base = f"{label} {m.marque}"
    if m.modele:
        base += f" {m.modele}"

    # Identifiant le plus pertinent
    ident = None
    if m.adresse_mac:
        ident = f"Adresse MAC : {m.adresse_mac}"
    if m.numero_serie:
        sn_label = "S/N"
        ident = f"{sn_label} : {m.numero_serie}" if not ident else f"{ident} — {sn_label} : {m.numero_serie}"

    return f"{base}, {ident}" if ident else base


# ── Styles communs ─────────────────────────────────────────────────────────────
def _build_styles():
    base = getSampleStyleSheet()

    header_co = ParagraphStyle(
        "header_co", fontName="Helvetica-Bold", fontSize=9,
        textColor=BLUE, leading=13,
    )
    header_addr = ParagraphStyle(
        "header_addr", fontName="Helvetica", fontSize=8,
        textColor=GREY, leading=12, alignment=2,
    )
    date_style = ParagraphStyle(
        "date_s", fontName="Helvetica", fontSize=10,
        alignment=2, spaceAfter=6,
    )
    objet_style = ParagraphStyle(
        "objet_s", fontName="Helvetica-Bold", fontSize=11,
        spaceBefore=4, spaceAfter=10,
        borderPad=6,
    )
    body_style = ParagraphStyle(
        "body_s", fontName="Helvetica", fontSize=10,
        leading=15, spaceAfter=8, alignment=4,  # 4 = justify
    )
    bold_inline = ParagraphStyle(
        "bold_inline", fontName="Helvetica-Bold", fontSize=10,
        leading=15, spaceAfter=8, alignment=4,
    )
    bullet_style = ParagraphStyle(
        "bullet_s", fontName="Helvetica", fontSize=10,
        leading=15, leftIndent=0,
    )
    sig_label = ParagraphStyle(
        "sig_label", fontName="Helvetica-Bold", fontSize=10,
        alignment=1, spaceAfter=2,
    )
    sig_name = ParagraphStyle(
        "sig_name", fontName="Helvetica-Bold", fontSize=10,
        alignment=1, textColor=BLUE,
    )
    footer_style = ParagraphStyle(
        "footer_s", fontName="Helvetica", fontSize=8,
        textColor=GREY, alignment=1,
    )
    return dict(
        header_co=header_co, header_addr=header_addr,
        date_style=date_style, objet_style=objet_style,
        body_style=body_style, bold_inline=bold_inline,
        bullet_style=bullet_style,
        sig_label=sig_label, sig_name=sig_name,
        footer_style=footer_style,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# ATTESTATION DE MISE À DISPOSITION (1 ou N matériels d'un même employé)
# ═══════════════════════════════════════════════════════════════════════════════
def generate_attestation_pdf(attributions: list) -> bytes:
    """
    Génère l'attestation de mise à disposition pour TOUTES les attributions
    actives d'un employé (liste d'objets Attribution avec .materiel chargé).
    """
    if not attributions:
        raise ValueError("Aucune attribution fournie")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,
    )

    st  = _build_styles()
    ref = attributions[0]          # référence pour les infos employé
    today = datetime.date.today()

    story = []

    # ── En-tête : 2 colonnes ──────────────────────────────────────────────────
    header_data = [[
        Paragraph(
            "<b>CAMUSAT SENEGAL</b><br/>"
            "00 (221) 33 865 10 01<br/>"
            "contact@camusat.com<br/>"
            "www.camusat.com",
            st["header_co"],
        ),
        Paragraph(
            "10083 Sacré Cœur 3, VDN - Immeuble<br/>"
            "Sourok 9 - 1er Etage, Dakar BP 45923,<br/>"
            "Sénégal",
            st["header_addr"],
        ),
    ]]
    ht = Table(header_data, colWidths=[9 * cm, 8 * cm])
    ht.setStyle(TableStyle([
        ("VALIGN",  (0, 0), (-1, -1), "TOP"),
        ("PADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(ht)
    story.append(Spacer(1, 0.3 * cm))

    # Filet rouge + bleu (imite le bas de page camusat en haut)
    story.append(HRFlowable(width="100%", thickness=2, color=RED,   spaceAfter=1))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE,  spaceAfter=8))
    story.append(Spacer(1, 0.4 * cm))

    # ── Date ──────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        f"Date, le {today.strftime('%d/%m/%Y')}",
        st["date_style"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Objet ─────────────────────────────────────────────────────────────────
    story.append(Paragraph(
        "<u><b>Objet</b></u> : Attestation de mise à disposition de matériels informatiques",
        st["objet_style"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    # ── Corps — intro ─────────────────────────────────────────────────────────
    nom_complet = f"{ref.employee_prenom or ''} {ref.employee_nom}".strip()
    story.append(Paragraph(
        f"Je soussigné(e) <b>{nom_complet}</b> certifie avoir reçu les matériels suivants :",
        st["body_style"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    # ── Liste à puces des matériels ───────────────────────────────────────────
    items = [
        ListItem(
            Paragraph(_mat_description(a.materiel), st["bullet_style"]),
            bulletColor=BLUE, bulletType="bullet", leftIndent=20, bulletFontSize=12,
        )
        for a in attributions if a.materiel
    ]
    story.append(ListFlowable(items, bulletType="bullet", leftIndent=10))
    story.append(Spacer(1, 0.5 * cm))

    # ── Paragraphes légaux ────────────────────────────────────────────────────
    story.append(Paragraph(
        "Nous vous rappelons que les matériels susvisés mis à votre disposition ce jour "
        "ne peuvent en aucun cas être utilisés pour des raisons personnelles. "
        "Leur usage doit en effet rester strictement professionnel.",
        st["body_style"],
    ))

    story.append(Paragraph(
        "Par la présente attestation contre signée de remise du matériel informatique, "
        "vous vous engagez à restituer ces matériels à <b>CAMUSAT SENEGAL</b> "
        "à la fin de votre contrat de travail.",
        st["body_style"],
    ))

    story.append(Paragraph(
        "Nous vous prions d'agréer, Monsieur/Madame, nos salutations distinguées.",
        st["body_style"],
    ))
    story.append(Spacer(1, 1.2 * cm))

    # ── Bloc signatures ───────────────────────────────────────────────────────
    sig_data = [[
        Paragraph("L'intéressé(e) :", st["sig_label"]),
        Paragraph("L'Assistant Informatique", st["sig_label"]),
    ]]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 50),  # espace pour signature
    ]))
    story.append(sig_table)

    # Nom responsable IT sous la colonne droite
    name_data = [["", Paragraph("Libasse SARR", st["sig_name"])]]
    name_table = Table(name_data, colWidths=[8.5 * cm, 8.5 * cm])
    name_table.setStyle(TableStyle([("PADDING", (0, 0), (-1, -1), 0)]))
    story.append(name_table)

    story.append(Spacer(1, 1 * cm))

    # ── Filets bas de page + logo texte ───────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=2, color=RED,  spaceAfter=1))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=6))

    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# DÉCHARGE (inchangée, par attribution)
# ═══════════════════════════════════════════════════════════════════════════════
def generate_decharge_pdf(attribution) -> bytes:
    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=2 * cm, rightMargin=2 * cm,
                            topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story  = []

    title_style = ParagraphStyle("title", parent=styles["Heading1"],
                                 fontSize=16, alignment=1, spaceAfter=12)
    normal = styles["Normal"]

    story.append(Paragraph("CAMUSAT SÉNÉGAL", title_style))
    story.append(Paragraph("Décharge de Remise de Matériel Informatique", title_style))
    story.append(Spacer(1, 0.5 * cm))

    emp_data = [
        ["Nom & Prénom :", f"{attribution.employee_nom} {attribution.employee_prenom or ''}".strip()],
        ["Matricule :",    attribution.employee_matricule or "—"],
        ["Service :",      attribution.employee_service   or "—"],
        ["Poste :",        attribution.employee_poste     or "—"],
        ["Date de remise :", str(attribution.date_attribution)],
    ]
    t = Table(emp_data, colWidths=[5 * cm, 12 * cm])
    t.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.grey),
        ("BACKGROUND",    (0, 0), (0, -1), LGREY),
    ]))
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph("<b>Matériel remis :</b>", normal))
    story.append(Spacer(1, 0.2 * cm))
    m = attribution.materiel
    mat_data = [
        ["Type", "Marque", "Modèle", "N° Série", "État"],
        [
            m.type_materiel.replace("_", " ").title() if m else "—",
            m.marque  if m else "—",
            m.modele  if m else "—",
            m.numero_serie or "—",
            m.etat    if m else "—",
        ],
    ]
    mt = Table(mat_data, colWidths=[3.5 * cm, 3 * cm, 4 * cm, 4 * cm, 2.5 * cm])
    mt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR",  (0, 0), (-1, 0), colors.white),
        ("FONTNAME",   (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",   (0, 0), (-1, -1), 9),
        ("GRID",       (0, 0), (-1, -1), 0.5, colors.grey),
        ("ALIGN",      (0, 0), (-1, -1), "CENTER"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LGREY]),
    ]))
    story.append(mt)
    story.append(Spacer(1, 1.5 * cm))

    sig_data = [["Signature Employé", "Signature Responsable IT"]]
    st2 = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    st2.setStyle(TableStyle([
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 40),
        ("BOX",           (0, 0), (0, 0), 0.5, colors.grey),
        ("BOX",           (1, 0), (1, 0), 0.5, colors.grey),
    ]))
    story.append(st2)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph(
        f"<font size=8 color='grey'>Généré le {datetime.date.today()} — Camusat Sénégal Direction IT</font>",
        ParagraphStyle("footer", alignment=1),
    ))

    doc.build(story)
    return buf.getvalue()


# ═══════════════════════════════════════════════════════════════════════════════
# ATTESTATION DE RÉCUPÉRATION (1 ou N matériels d'un même employé)
# ═══════════════════════════════════════════════════════════════════════════════
def generate_recuperation_pdf(attributions: list, date_recuperation=None) -> bytes:
    if not attributions:
        raise ValueError("Aucune attribution fournie")

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        leftMargin=2.5 * cm, rightMargin=2.5 * cm,
        topMargin=2 * cm, bottomMargin=2.5 * cm,
    )

    st   = _build_styles()
    ref  = attributions[0]
    today = date_recuperation or datetime.date.today()

    story = []

    header_data = [[
        Paragraph(
            "<b>CAMUSAT SENEGAL</b><br/>"
            "00 (221) 33 865 10 01<br/>"
            "contact@camusat.com<br/>"
            "www.camusat.com",
            st["header_co"],
        ),
        Paragraph(
            "10083 Sacré Cœur 3, VDN - Immeuble<br/>"
            "Sourok 9 - 1er Etage, Dakar BP 45923,<br/>"
            "Sénégal",
            st["header_addr"],
        ),
    ]]
    ht = Table(header_data, colWidths=[9 * cm, 8 * cm])
    ht.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("PADDING", (0, 0), (-1, -1), 0)]))
    story.append(ht)
    story.append(Spacer(1, 0.3 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=RED,  spaceAfter=1))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=8))
    story.append(Spacer(1, 0.4 * cm))

    story.append(Paragraph(
        f"Date, le {today.strftime('%d/%m/%Y') if hasattr(today, 'strftime') else today}",
        st["date_style"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    story.append(Paragraph(
        "<u><b>Objet</b></u> : Attestation de récupération de matériels informatiques",
        st["objet_style"],
    ))
    story.append(Spacer(1, 0.3 * cm))

    nom_complet = f"{ref.employee_prenom or ''} {ref.employee_nom}".strip()
    story.append(Paragraph(
        f"Je soussigné(e) <b>Libasse SARR</b>, Assistant Informatique, certifie avoir récupéré "
        f"les matériels suivants de <b>{nom_complet}</b> :",
        st["body_style"],
    ))
    story.append(Spacer(1, 0.2 * cm))

    bullet_items = [
        ListItem(
            Paragraph(_mat_description(a.materiel), st["bullet_style"]),
            bulletColor=BLUE, bulletType="bullet", leftIndent=20, bulletFontSize=12,
        )
        for a in attributions if a.materiel
    ]
    story.append(ListFlowable(bullet_items, bulletType="bullet", leftIndent=10))
    story.append(Spacer(1, 0.5 * cm))

    story.append(Paragraph(
        "Le(s) matériel(s) susvisé(s) a/ont été restitué(s) et réintégré(s) au stock du parc informatique de CAMUSAT SENEGAL.",
        st["body_style"],
    ))
    story.append(Paragraph(
        "Nous vous remercions de votre collaboration.",
        st["body_style"],
    ))
    story.append(Spacer(1, 1.2 * cm))

    sig_data = [[
        Paragraph("L'intéressé(e) :", st["sig_label"]),
        Paragraph("L'Assistant Informatique", st["sig_label"]),
    ]]
    sig_table = Table(sig_data, colWidths=[8.5 * cm, 8.5 * cm])
    sig_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 50),
    ]))
    story.append(sig_table)

    name_data = [["", Paragraph("Libasse SARR", st["sig_name"])]]
    name_table = Table(name_data, colWidths=[8.5 * cm, 8.5 * cm])
    name_table.setStyle(TableStyle([("PADDING", (0, 0), (-1, -1), 0)]))
    story.append(name_table)

    story.append(Spacer(1, 1 * cm))
    story.append(HRFlowable(width="100%", thickness=2, color=RED,  spaceAfter=1))
    story.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceAfter=6))

    doc.build(story)
    return buf.getvalue()
