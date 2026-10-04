-- Rôle PostgreSQL en LECTURE SEULE pour l'assistant IA.
-- À exécuter sur CHAQUE base de production (inventaire, RH, parc IT) avec un
-- compte administrateur, en remplaçant le mot de passe et le nom de la base.
--
--   psql "postgresql://ADMIN@HOTE:PORT/NOM_BASE" -v pwd="'MotDePasseFort'" -f create_readonly_role.sql
--
-- Ensuite : INVENTORY_DB_URL=postgresql://assistant_ro:MotDePasseFort@HOTE:PORT/NOM_BASE

CREATE ROLE assistant_ro LOGIN PASSWORD :pwd
  NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;

ALTER ROLE assistant_ro SET default_transaction_read_only = on;
ALTER ROLE assistant_ro SET statement_timeout = '15s';
ALTER ROLE assistant_ro CONNECTION LIMIT 10;

GRANT CONNECT ON DATABASE :"DBNAME" TO assistant_ro;
GRANT USAGE ON SCHEMA public TO assistant_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO assistant_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO assistant_ro;

-- Recommandé : retirer aussi l'accès aux tables sensibles au niveau de la base,
-- en plus du filtrage fait par l'assistant (sources.yaml). Exemples :
--
-- Base RH :
--   REVOKE SELECT ON hr_employees_disciplinaryrecord, hr_employees_infirmerieappointment,
--                    users_passwordresetotp, users_customuser FROM assistant_ro;
--   -- Masquer les colonnes bancaires : retirer le SELECT global sur la table puis
--   -- n'accorder que les colonnes utiles, par ex. :
--   REVOKE SELECT ON hr_employees_employee FROM assistant_ro;
--   GRANT SELECT (id, matricule, nom, prenom, sexe, fonction, categorie, service, projet,
--                 business_line, localisation, manager, email, status, date_embauche,
--                 date_sortie, type_contrat, n1_manager_id, n2_manager_id) ON hr_employees_employee TO assistant_ro;
--
-- Base Parc IT :
--   REVOKE SELECT ON users FROM assistant_ro;
