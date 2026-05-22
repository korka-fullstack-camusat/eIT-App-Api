"""
Client HTTP vers l'API externe Camusat eRh.
Authentification par api_key en query param.
"""
import httpx
from typing import Optional
from ..config import settings


def _map_employee(raw: dict) -> dict:
    """Normalise un employé de l'API externe vers notre format interne."""
    return {
        "id":           raw.get("id", 0),
        "nom":          raw.get("nom", ""),
        "prenom":       raw.get("prenom", ""),
        "matricule":    str(raw.get("matricule", "")),
        "service":      raw.get("service"),
        "fonction":     raw.get("fonction"),
        "email":        raw.get("email"),
        "status":       raw.get("status"),
        "type_contrat": raw.get("type_contrat"),
        "business_line": raw.get("business_line"),
        "manager":      raw.get("manager"),
    }


class ErhClient:
    @property
    def _base(self) -> str:
        return settings.erh_external_api_url.rstrip("/") + "/"

    @property
    def _key(self) -> str:
        return settings.erh_api_key

    async def get_employees(
        self,
        search: str = "",
        status: str = "ACTIVE",
        service: str = "",
        page_size: int = 50,
    ) -> list[dict]:
        params: dict = {"api_key": self._key, "page_size": page_size}
        if search:
            params["search"] = search
        if status:
            params["status"] = status
        if service:
            params["service"] = service

        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(self._base, params=params)
            res.raise_for_status()
            data = res.json()

        employees = data.get("results", data) if isinstance(data, dict) else data
        return [_map_employee(e) for e in employees]

    async def get_employee(self, employee_id: int) -> Optional[dict]:
        """Récupère un employé par son id Django (PK)."""
        url = f"{self._base}{employee_id}/"
        async with httpx.AsyncClient(timeout=15) as client:
            res = await client.get(url, params={"api_key": self._key})
            if res.status_code == 404:
                return None
            res.raise_for_status()
            return _map_employee(res.json())


erh_client = ErhClient()
