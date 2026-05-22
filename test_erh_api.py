"""
Test de connexion à l'API externe eRh Camusat.
Lancer avec : docker exec backend-web-1 python test_erh_api.py
"""
import httpx
import asyncio
import json

API_URL = "https://apierh.camusatsn.com/api/employees/external/internes/"
API_KEY = "SpnGUEJvZ3ygl1WEBLW1l2Ki5kj739j09aa50D6FLbs"


async def main():
    print("=" * 60)
    print("Test API eRh Camusat")
    print("=" * 60)

    # ── Test 1 : connectivité de base ──────────────────────────────
    print("\n[1] Recherche employés actifs (search=diallo)...")
    try:
        async with httpx.AsyncClient(timeout=15, verify=True) as client:
            r = await client.get(
                API_URL,
                params={
                    "api_key":   API_KEY,
                    "search":    "diallo",
                    "status":    "ACTIVE",
                    "page_size": 5,
                },
            )
        print(f"    Status HTTP : {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            employees = data.get("results", data) if isinstance(data, dict) else data
            print(f"    Résultats   : {len(employees)} employé(s)")
            if employees:
                print(f"    Premier     : {json.dumps(employees[0], ensure_ascii=False, indent=6)}")
        else:
            print(f"    Réponse     : {r.text[:500]}")
    except httpx.ConnectError as e:
        print(f"    ✗ Erreur connexion (DNS / réseau) : {e}")
    except httpx.TimeoutException:
        print("    ✗ Timeout — serveur inaccessible depuis Docker")
    except Exception as e:
        print(f"    ✗ Erreur inattendue : {type(e).__name__}: {e}")

    # ── Test 2 : sans SSL verify (si certificat invalide) ──────────
    print("\n[2] Même appel sans vérification SSL...")
    try:
        async with httpx.AsyncClient(timeout=15, verify=False) as client:
            r = await client.get(
                API_URL,
                params={"api_key": API_KEY, "page_size": 3},
            )
        print(f"    Status HTTP : {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            employees = data.get("results", data) if isinstance(data, dict) else data
            print(f"    ✓ Fonctionne sans SSL verify — {len(employees)} résultat(s)")
            print("    → Solution : ajouter verify=False dans erh_client.py")
        else:
            print(f"    Réponse : {r.text[:300]}")
    except httpx.ConnectError as e:
        print(f"    ✗ Erreur connexion : {e}")
    except httpx.TimeoutException:
        print("    ✗ Timeout")
    except Exception as e:
        print(f"    ✗ {type(e).__name__}: {e}")

    # ── Test 3 : résolution DNS ────────────────────────────────────
    print("\n[3] Résolution DNS de apierh.camusatsn.com...")
    import socket
    try:
        ip = socket.gethostbyname("apierh.camusatsn.com")
        print(f"    ✓ Résolu → {ip}")
    except socket.gaierror as e:
        print(f"    ✗ Échec DNS : {e}")
        print("    → Le container Docker n'a pas accès à internet ou au DNS")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
