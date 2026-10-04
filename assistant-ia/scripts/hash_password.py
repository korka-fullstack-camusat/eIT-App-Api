"""Génère une entrée pour ASSISTANT_USERS.

Usage : python scripts/hash_password.py <identifiant>
(le mot de passe est demandé de façon masquée)
"""
import getpass
import sys

import bcrypt

if len(sys.argv) != 2:
    sys.exit("Usage : python scripts/hash_password.py <identifiant>")
user = sys.argv[1]
if ":" in user or "," in user:
    sys.exit("L'identifiant ne doit contenir ni « : » ni « , ».")
pwd = getpass.getpass("Mot de passe : ")
if len(pwd) < 10:
    sys.exit("Mot de passe trop court (10 caractères minimum).")
if pwd != getpass.getpass("Confirmer : "):
    sys.exit("Les mots de passe ne correspondent pas.")
print(f"{user}:{bcrypt.hashpw(pwd.encode(), bcrypt.gensalt()).decode()}")
