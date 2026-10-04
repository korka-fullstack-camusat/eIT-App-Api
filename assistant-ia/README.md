# Assistant IA Camusat

Agent conversationnel qui répond aux questions des collaborateurs en interrogeant
directement les bases de données des plateformes, **en lecture seule**, et qui
**cite ses sources** (plateforme, tables et requête SQL exécutée).

Plateformes connectées au départ :

| Source (`id`) | Plateforme | Dépôt |
|---|---|---|
| `inventory` | Inventaire : stock, sorties magasin, transferts, fournisseurs | `inventory_backend` |
| `rh` | RH : employés, congés, présences, planning | `erh-app-backend` |
| `parc_it` | Parc IT : matériel, licences, téléphonie | `eIT-App-Api` |

## Fonctionnement

```
Navigateur ──► FastAPI (/api/chat) ──► Claude (API Anthropic)
                                         │ outils : list_tables / describe_table / run_sql
                                         ▼
                       PostgreSQL Inventaire · RH · Parc IT  (rôle lecture seule)
```

1. L'utilisateur pose une question dans l'interface web.
2. Claude choisit la ou les sources, explore le schéma, puis exécute des requêtes `SELECT`.
3. Chaque requête exécutée reçoit une référence (`S1`, `S2`…). La réponse cite ces
   références, et l'interface affiche pour chacune la plateforme, les tables, le nombre de
   lignes et la requête SQL exacte.

## Sécurité : les protections en place

- **Lecture seule à 3 niveaux** : le rôle Postgres `assistant_ro` (que des `GRANT SELECT`),
  des sessions en `default_transaction_read_only`, et une analyse SQL (sqlglot) qui
  refuse tout ce qui n'est pas un `SELECT` unique.
- **Données sensibles masquées** (`sources.yaml`) : mots de passe, jetons, coordonnées
  bancaires, pièces d'identité, famille, dossiers disciplinaires, infirmerie, bulletins.
  Ces tables et colonnes sont invisibles pour l'agent, toute requête qui les cite est
  refusée, et elles sont retirées des résultats d'un `SELECT *`.
- **Limites** : 200 lignes par requête, 15 s maximum par requête.
- **Accès** par identifiant et mot de passe (HTTP Basic, mots de passe hachés en bcrypt).
- **Journal d'audit** `logs/audit.jsonl` : qui a posé quelle question, et quelles requêtes
  ont été exécutées ou refusées.

> ⚠️ Les questions et les résultats des requêtes sont envoyés à l'API Anthropic pour
> générer les réponses. Validez ce point avec la DSI et le DPO avant d'ouvrir l'accès,
> en particulier pour les données RH.

## Installation

### 1. Créer un rôle en lecture seule sur chaque base

Sur le serveur de chaque base (Inventaire, RH, Parc IT), avec un compte administrateur :

```bash
psql "postgresql://ADMIN@HOTE:PORT/NOM_BASE" -v pwd="'UnMotDePasseFort'" \
     -f scripts/create_readonly_role.sql
```

Le script contient aussi, en commentaire, des exemples de `REVOKE` pour retirer
l'accès aux tables et colonnes sensibles directement dans Postgres. C'est recommandé
en production.

### 2. Configurer

```bash
cp .env.example .env
# compléter ANTHROPIC_API_KEY, INVENTORY_DB_URL, RH_DB_URL, PARC_IT_DB_URL

# créer un compte utilisateur (à répéter pour chaque personne) :
pip install bcrypt && python scripts/hash_password.py prenom.nom
# coller la ligne obtenue dans ASSISTANT_USERS (séparer plusieurs comptes par des virgules)
```

### 3. Lancer

```bash
docker compose up -d --build
# puis ouvrir http://SERVEUR:8050
```

Sans Docker :

```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --port 8050
```

> Garder **un seul worker**, car les conversations sont gardées en mémoire. Si le service
> est exposé hors du réseau interne, le placer derrière le Nginx existant **en HTTPS**.

## Ajouter une plateforme

1. Créer le rôle `assistant_ro` sur sa base (étape 1).
2. Ajouter un bloc dans `sources.yaml` :

   ```yaml
     - id: flotte
       name: Flotte véhicules
       dsn_env: FLOTTE_DB_URL
       description: |
         Ce que contient la plateforme, en quelques lignes.
       hints: |
         - Tables principales et statuts utiles.
       exclude_tables: []
       exclude_columns: []
   ```

3. Ajouter `FLOTTE_DB_URL=...` dans `.env`, puis redémarrer le service (`docker compose restart`).

Aucune modification de code n'est nécessaire. Les champs `description` et `hints` aident
l'agent à trouver les bonnes tables, donc plus ils sont précis, meilleures sont les réponses.

## Tests

```bash
pip install -r requirements-dev.txt
pytest                                   # tests unitaires (analyse SQL)
TEST_DB_URL=postgresql://... pytest      # + tests d'intégration sur une base de TEST
```

## Paramètres (`.env`)

| Variable | Défaut | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Clé API Claude |
| `CLAUDE_MODEL` | `claude-opus-5-5` | Modèle utilisé |
| `CLAUDE_EFFORT` | `medium` | Profondeur de raisonnement (`low` … `max`) |
| `MAX_AGENT_STEPS` | `12` | Nombre maximal d'allers-retours avec les outils par question |
| `SQL_MAX_ROWS` | `200` | Lignes maximum par requête |
| `SQL_TIMEOUT_MS` | `15000` | Durée maximum d'une requête |
| `ASSISTANT_USERS` | — | Comptes `identifiant:hash_bcrypt,…` |
