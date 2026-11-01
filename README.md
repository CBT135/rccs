# RCCS : traces Spond → Garmin

Ce dépôt récupère automatiquement les parcours Garmin publiés dans les événements Spond du
Running Club Colombier-Saugnieu. Chaque parcours est copié dans Garmin Connect sous le nom
**AAAAMMJJ-RCCS** et ajouté au calendrier. L'application **Trace RCCS** permet ensuite de le
charger sur la montre.

## Fonctionnement

1. **Tâche planifiée GitHub** (`.github/workflows/sync.yml`). Elle s'exécute le mercredi et le
   vendredi à 17h, et le samedi à 18h, heure de Paris (heure d'été et d'hiver gérées).
   - Elle lit les événements Spond à venir et cherche un lien `connect.garmin.com/.../course/<id>`
     dans la description ou les commentaires.
   - Pour chaque événement trouvé, elle crée dans ton compte Garmin une copie privée du parcours,
     nommée `AAAAMMJJ-RCCS` d'après la date de l'événement. Si deux événements tombent le même
     jour, le second reçoit le suffixe `-2`.
   - Elle ajoute ensuite un événement au calendrier Garmin à la date et à l'heure prévues.
   - Elle ne recrée rien si le parcours ou l'événement existe déjà.
   - Elle publie dans `trace/` la trace de l'événement à venir le plus proche (`.fit`, `.gpx`,
     `latest.txt`, `latest.json`). Les traces précédentes sont supprimées : le dossier n'en
     contient jamais qu'une.
   - Un résumé de chaque exécution s'affiche dans l'onglet **Actions**.
2. **Application montre** (`garmin-app/`). Au lancement, elle lit `trace/latest.txt`, télécharge
   le `.fit` correspondant via le téléphone et l'enregistre dans **Parcours**, sous le nom
   `AAAAMMJJ-RCCS`. Appuyer sur START lance la navigation sur ce parcours. Une trace déjà présente
   sur la montre n'est pas téléchargée une seconde fois.

## 1. Ajouter les secrets (une seule fois)

Les identifiants ne sont jamais écrits dans le dépôt. Ils sont stockés dans des secrets GitHub
chiffrés, accessibles uniquement à la tâche planifiée.

Dans **Settings → Secrets and variables → Actions → New repository secret**, crée :

| Secret | Contenu |
|---|---|
| `SPOND_USERNAME` | e-mail du compte Spond |
| `SPOND_PASSWORD` | mot de passe Spond |
| `GARMIN_EMAIL` | e-mail du compte Garmin Connect |
| `GARMIN_PASSWORD` | mot de passe Garmin Connect |
| `GARMIN_TOKENS` | *(facultatif, voir ci-dessous)* |

Avec la ligne de commande GitHub, chaque commande demande la valeur, qui ne s'affiche pas :

```bash
gh secret set SPOND_USERNAME -R cbt135/rccs
gh secret set SPOND_PASSWORD -R cbt135/rccs
gh secret set GARMIN_EMAIL -R cbt135/rccs
gh secret set GARMIN_PASSWORD -R cbt135/rccs
```

**Si la connexion Garmin échoue** (validation en deux étapes activée, ou connexion bloquée
depuis les serveurs GitHub), lance `python sync/garmin_tokens.py` sur ton ordinateur et colle le
résultat dans le secret `GARMIN_TOKENS`. Ces jetons restent valables environ un an.

**Tester tout de suite** : onglet **Actions → Synchro Spond → Garmin → Run workflow**.

> Le dépôt est public, ce qui permet à la montre de télécharger la trace sans identifiant. Les
> secrets restent privés, mais la trace et la date de la prochaine sortie sont visibles par
> tous.

## 2. Installer l'application sur la montre

L'application est compatible avec les montres sorties depuis fin 2021 : fēnix 7/8/9 et E,
epix 2 et Pro, Enduro 3/4, Forerunner 165/170/255/265/570/955/965/970, Instinct 2/3/E/Crossover,
Venu 2 Plus/3/4/X1, vívoactive 5/6, MARQ 2/3, Descent, D2, Approach S70/S72. La liste complète
se trouve dans `garmin-app/manifest.xml`. La montre doit être connectée à Garmin Connect sur le
téléphone, et le Bluetooth doit être actif.

1. Installe Visual Studio Code, l'extension **Monkey C** et le SDK Connect IQ (via le SDK
   Manager). Dans le SDK Manager, télécharge les appareils voulus, au minimum **fēnix 7**.
2. `Ctrl+Shift+P` → **Monkey C: Generate a Developer Key** (à faire une seule fois).
3. Ouvre le dossier `garmin-app`, puis `Ctrl+Shift+P` → **Monkey C: Build for Device** →
   **fenix7**. La commande produit un fichier `.prg`.
4. Branche la montre en USB et copie le `.prg` dans `GARMIN/APPS/`.
5. Sur la montre, lance **Trace RCCS** depuis la liste des applications.

Pour tester sans montre : **Monkey C: Run** ouvre le simulateur. Le téléchargement de parcours
y est simulé de façon partielle.

## Fichiers

```
.github/workflows/sync.yml   tâche planifiée
sync/sync_rccs.py            synchro Spond → Garmin + publication de la trace
sync/garmin_tokens.py        génération des jetons Garmin (à lancer en local)
trace/                       dernière trace uniquement (écrit par la tâche)
garmin-app/                  application Connect IQ « Trace RCCS »
```
