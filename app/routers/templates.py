"""
Gestion des templates Word pour attestation et décharge.
"""
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload
from typing import Literal
from ..database import get_db
from ..models.attribution import Attribution, StatutAttribution
from ..services.template_service import (
    save_template, scan_placeholders, template_exists,
    generate_attestation_from_template, generate_decharge_from_template,
    TEMPLATE_PATHS,
)
from ..models.user import User
from ..services.auth_service import require_editor

router = APIRouter(prefix="/api/templates", tags=["Templates"])

DOC_TYPES = {"attestation", "decharge"}


@router.post("/{doc_type}/upload")
async def upload_template(doc_type: str, file: UploadFile = File(...), _: User = Depends(require_editor)):
    """Upload un template Word (.docx) pour attestation ou décharge."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, f"Type invalide. Valeurs acceptées : {', '.join(DOC_TYPES)}")
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "Le fichier doit être un .docx")

    content = await file.read()
    try:
        placeholders = scan_placeholders(content)
    except Exception as e:
        raise HTTPException(400, f"Impossible de lire le fichier : {e}")

    save_template(doc_type, content)
    return {
        "message":      f"Template '{doc_type}' enregistré",
        "filename":     file.filename,
        "placeholders": placeholders,
    }


@router.get("/info")
def get_templates_info():
    """Retourne l'état des templates uploadés et leurs balises détectées."""
    result = {}
    for doc_type, path in TEMPLATE_PATHS.items():
        if path.exists():
            content = path.read_bytes()
            try:
                placeholders = scan_placeholders(content)
            except Exception:
                placeholders = []
            result[doc_type] = {
                "uploaded":     True,
                "size_kb":      round(path.stat().st_size / 1024, 1),
                "placeholders": placeholders,
            }
        else:
            result[doc_type] = {"uploaded": False, "placeholders": []}
    return result


@router.delete("/{doc_type}")
def delete_template(doc_type: str, _: User = Depends(require_editor)):
    """Supprime un template uploadé (revient au PDF généré par défaut)."""
    if doc_type not in DOC_TYPES:
        raise HTTPException(400, "Type invalide")
    path = TEMPLATE_PATHS.get(doc_type)
    if path and path.exists():
        path.unlink()
        return {"message": f"Template '{doc_type}' supprimé"}
    raise HTTPException(404, "Aucun template trouvé")


@router.get("/attestation/employee/{employee_id}")
def attestation_custom(employee_id: int, db: Session = Depends(get_db)):
    """Génère l'attestation en utilisant le template Word si disponible, sinon PDF par défaut."""
    attrs = (
        db.query(Attribution)
        .options(joinedload(Attribution.materiel))
        .filter(
            Attribution.employee_id == employee_id,
            Attribution.statut == StatutAttribution.ACTIVE,
        )
        .order_by(Attribution.date_attribution.asc())
        .all()
    )
    if not attrs:
        raise HTTPException(404, "Aucune attribution active pour cet employé")

    if template_exists("attestation"):
        import io
        docx_bytes = generate_attestation_from_template(attrs)
        nom = f"{attrs[0].employee_prenom or ''} {attrs[0].employee_nom}".strip().replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=attestation_{nom}.docx"},
        )
    else:
        # Fallback : PDF par défaut
        import io
        from ..services.pdf_service import generate_attestation_pdf
        pdf_bytes = generate_attestation_pdf(attrs)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"inline; filename=attestation_{employee_id}.pdf"},
        )


@router.get("/decharge/{attribution_id}")
def decharge_custom(attribution_id: int, db: Session = Depends(get_db)):
    """Génère la décharge en utilisant le template Word si disponible, sinon PDF par défaut."""
    attr = (
        db.query(Attribution)
        .options(joinedload(Attribution.materiel))
        .filter(Attribution.id == attribution_id)
        .first()
    )
    if not attr:
        raise HTTPException(404, "Attribution introuvable")

    if template_exists("decharge"):
        import io
        docx_bytes = generate_decharge_from_template(attr)
        nom = f"{attr.employee_prenom or ''} {attr.employee_nom}".strip().replace(" ", "_")
        return StreamingResponse(
            io.BytesIO(docx_bytes),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment; filename=decharge_{nom}.docx"},
        )
    else:
        import io
        from ..services.pdf_service import generate_decharge_pdf
        pdf_bytes = generate_decharge_pdf(attr)
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename=decharge_{attribution_id}.pdf"},
        )
