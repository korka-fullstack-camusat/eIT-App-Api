"""
Script d'initialisation exécuté UNE FOIS avant le démarrage de gunicorn.
Crée les tables et l'utilisateur admin par défaut.
"""
import time
import sqlalchemy
from app.database import Base, engine, SessionLocal
from app.models import Materiel, Attribution, NumeroSIM, SiteGSM, Vehicule, AffectationSIM, FactureTelecom, LigneFacture, User, ImportGlobalLog, ExportLog
from app.models.planning import Tache  # noqa: F401
from app.models.licence import Licence, LicenceAttribution  # noqa: F401
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
        # Champ Projet + nouveau type Tablette pour les matériels
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS projet VARCHAR(100)",
        "ALTER TYPE typemateriel ADD VALUE IF NOT EXISTS 'TABLETTE'",
        # Bénéficiaire (Matricule / Nom / Prénom) + remarque, repris du fichier de suivi
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS beneficiaire_matricule VARCHAR(50)",
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS beneficiaire_nom VARCHAR(100)",
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS beneficiaire_prenom VARCHAR(100)",
        "ALTER TABLE materiels DROP COLUMN IF EXISTS remarque",
        # Informations d'affectation (issues du fichier de suivi ORANGE-mobiles) pour les SIM employés
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS matricule VARCHAR(50)",
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS beneficiaire VARCHAR(150)",
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS service VARCHAR(100)",
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS business_line VARCHAR(50)",
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS fonction VARCHAR(150)",
        # Informations issues du fichier de suivi ORANGE-Gps_Vehicules pour les SIM M2M véhicules
        "ALTER TABLE numeros_sim ADD COLUMN IF NOT EXISTS forfait NUMERIC(10,2)",
        "ALTER TABLE vehicules ADD COLUMN IF NOT EXISTS imei VARCHAR(30)",
        # Référence d'identification du matériel (code interne distinct du n° série / MAC)
        "ALTER TABLE materiels ADD COLUMN IF NOT EXISTS reference VARCHAR(100)",
        "CREATE INDEX IF NOT EXISTS ix_materiels_reference ON materiels(reference)",
        # Nouveaux types matériel : AP, Serveur, Pare-feu
        "ALTER TYPE typemateriel ADD VALUE IF NOT EXISTS 'AP'",
        "ALTER TYPE typemateriel ADD VALUE IF NOT EXISTS 'SERVEUR'",
        "ALTER TYPE typemateriel ADD VALUE IF NOT EXISTS 'PARE_FEU'",
        # Planning journalier
        """CREATE TABLE IF NOT EXISTS taches (
            id SERIAL PRIMARY KEY,
            titre VARCHAR(200) NOT NULL,
            description TEXT,
            date_planifiee DATE NOT NULL,
            date_fin DATE,
            statut VARCHAR(20) NOT NULL DEFAULT 'A_FAIRE',
            priorite VARCHAR(20) NOT NULL DEFAULT 'NORMALE',
            responsable VARCHAR(150),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ
        )""",
        # Licences logicielles
        """CREATE TABLE IF NOT EXISTS licences (
            id SERIAL PRIMARY KEY,
            logiciel VARCHAR(200) NOT NULL,
            editeur VARCHAR(150),
            version VARCHAR(50),
            cle_licence VARCHAR(255),
            date_achat DATE,
            date_expiration DATE,
            nb_postes_max INTEGER,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now(),
            updated_at TIMESTAMPTZ
        )""",
        """CREATE TABLE IF NOT EXISTS licence_attributions (
            id SERIAL PRIMARY KEY,
            licence_id INTEGER NOT NULL REFERENCES licences(id) ON DELETE CASCADE,
            employee_nom VARCHAR(150) NOT NULL,
            employee_prenom VARCHAR(150),
            employee_matricule VARCHAR(50),
            employee_service VARCHAR(150),
            materiel_id INTEGER,
            date_attribution DATE NOT NULL,
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT now()
        )""",
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
