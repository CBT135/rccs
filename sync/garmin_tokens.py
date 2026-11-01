#!/usr/bin/env python3
"""À lancer sur ton ordinateur (pas sur GitHub) si la connexion Garmin échoue
depuis GitHub (validation en deux étapes, blocage de connexion).

    pip install garminconnect==0.3.20
    python sync/garmin_tokens.py

Le script demande l'e-mail, le mot de passe et, si besoin, le code de validation,
puis affiche les jetons. Copie-les dans le secret GitHub GARMIN_TOKENS.
Les jetons restent valables environ un an ; ne les partage pas.
"""
import getpass

from garminconnect import Garmin

email = input("E-mail Garmin : ").strip()
pwd = getpass.getpass("Mot de passe Garmin : ")
g = Garmin(email=email, password=pwd, prompt_mfa=lambda: input("Code de validation : ").strip())
g.login()
print("\n--- Contenu du secret GARMIN_TOKENS (une seule ligne) ---\n")
print(g.client.dumps())
