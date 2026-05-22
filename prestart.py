"""
Script d'initialisation exécuté UNE FOIS avant le démarrage de gunicorn.
Crée les tables et l'utilisateur admin par défaut.
"""
import time
import sqlalchemy
from app.database import Base, engine, SessionLocal
from app.models import Materiel, Attribution, NumeroSIM, SiteGSM, Vehicule, AffectationSIM, FactureTelecom, LigneFacture, User
from app.services.auth_service import hash_password

print("→ Attente de la base de données...")
for attempt in range(30):
    try:
        with engine.connect() as conn:
            conn.execute(sqlalchemy.text("SELECT 1"))
        print("✓ Base de données disponible.")
        break
    except Exception:
        print(f"  Base non prête, nouvelle tentative ({attempt + 1}/30)...")
        time.sleep(2)
else:
    print("✗ Impossible de se connecter à la base de données après 30 tentatives.")
    raise SystemExit(1)

print("→ Création des tables...")
Base.metadata.create_all(bind=engine)
print("✓ Tables prêtes.")

# ── Migrations manuelles (colonnes ajoutées après la création initiale) ──
print("→ Application des migrations...")
with engine.connect() as conn:
    migrations = [
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS adresse_ip VARCHAR(50)",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email) WHERE email IS NOT NULL",
    ]
    for sql in migrations:
        try:
            conn.execute(sqlalchemy.text(sql))
            conn.commit()
        except Exception as e:
            print(f"  [WARN] {e}")
print("✓ Migrations OK.")

db = SessionLocal()
try:
    if not db.query(User).first():
        db.add(User(
            username="admin",
            full_name="Administrateur",
            hashed_password=hash_password("admin123"),
            is_active=True,
        ))
        db.commit()
        print("✓ Utilisateur admin créé (admin / admin123).")
    else:
        print("✓ Utilisateur admin déjà existant.")
finally:
    db.close()

print("→ Démarrage du serveur...")
