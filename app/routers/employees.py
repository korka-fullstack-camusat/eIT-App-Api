from fastapi import APIRouter, Query, HTTPException
from typing import Optional
from ..services.erh_client import erh_client

router = APIRouter(prefix="/api/employees", tags=["Employés (API externe Camusat)"])


@router.get("/")
async def search_employees(
    search:    Optional[str] = Query(None),
    status:    Optional[str] = Query("ACTIVE"),
    service:   Optional[str] = Query(None),
    page_size: int           = Query(50, le=200),
):
    """Proxy vers l'API externe Camusat eRh — lecture seule."""
    try:
        return await erh_client.get_employees(
            search=search or "",
            status=status or "ACTIVE",
            service=service or "",
            page_size=page_size,
        )
    except Exception as e:
        raise HTTPException(502, f"API eRh inaccessible : {e}")


@router.get("/{matricule}")
async def get_employee(matricule: int):
    try:
        emp = await erh_client.get_employee(matricule)
        if not emp:
            raise HTTPException(404, "Employé introuvable")
        return emp
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(502, f"API eRh inaccessible : {e}")
