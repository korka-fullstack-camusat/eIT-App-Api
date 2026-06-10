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
        "ALTER TABLE materiels RENAME COLUMN adresse_ip TO adresse_mac",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS email VARCHAR(255)",
        "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_email ON users(email) WHERE email IS NOT NULL",
        "ALTER TABLE affectations_sim ADD COLUMN IF NOT EXISTS motif_fin VARCHAR(300)",
        "ALTER TABLE sites_gsm ADD COLUMN IF NOT EXISTS code_site VARCHAR(50)",
        "ALTER TABLE sites_gsm ADD COLUMN IF NOT EXISTS imsi VARCHAR(20)",
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS imsi VARCHAR(20)",
        # Ajout de la valeur EN_PANNE dans le type enum PostgreSQL
        "ALTER TYPE statutmateriel ADD VALUE IF NOT EXISTS 'EN_PANNE'",
        # Nouveaux statuts SIM
        "ALTER TYPE statutsimenum ADD VALUE IF NOT EXISTS 'RESILIE'",
        "ALTER TYPE statutsimenum ADD VALUE IF NOT EXISTS 'CEDE'",
        "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS imsi VARCHAR(20)",
        # Rôles utilisateurs (ADMIN / EDITOR / VIEWER)
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(20) NOT NULL DEFAULT 'EDITOR'",
        "UPDATE users SET role = 'ADMIN' WHERE username = 'admin'",
        # Récapitulatif facture télécom (import au format opérateur)
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS numero_compte VARCHAR(50)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS reference_facture VARCHAR(50)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS montant_ht NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS rutel NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS montant_ht_rutel NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS tva NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS montant_ttc NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS arrondi_precedent NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS arrondi_encours NUMERIC(14,2)",
        "ALTER TABLE factures_telecom ADD COLUMN IF NOT EXISTS solde_facture NUMERIC(14,2)",
        # Détail récapitulatif par ligne (par numéro)
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS reference_facture VARCHAR(50)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS montant_ht NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS rutel NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS montant_ht_rutel NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS tva NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS montant_ttc NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS arrondi_precedent NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS arrondi_encours NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS solde_facture NUMERIC(14,2)",
        "ALTER TABLE lignes_facture ADD COLUMN IF NOT EXISTS type_ligne VARCHAR(50)",
    ]
    for sql in migrations:
        try:
            conn.execute(sqlalchemy.text(sql))
            conn.commit()
        except Exception as e:
            print(f"  [WARN] {e}")
            conn.rollback()
print("✓ Migrations OK.")

db = SessionLocal()
try:
    if not db.query(User).first():
        db.add(User(
            username="admin",
            full_name="Administrateur",
            hashed_password=hash_password("admin123"),
            is_active=True,
            role="ADMIN",
        ))
        db.commit()
        print("✓ Utilisateur admin créé (admin / admin123).")
    else:
        print("✓ Utilisateur admin déjà existant.")
finally:
    db.close()

print("→ Démarrage du serveur...")
