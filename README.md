# RCCS : dernière trace Spond sur la montre

Ce dépôt publie la dernière trace Garmin postée dans les événements Spond du Running Club
Colombier-Saugnieu, sous le nom **AAAAMMJJ-RCCS**. L'application **Trace RCCS** la charge ensuite
sur la montre.

## Fonctionnement

1. **Tâche planifiée GitHub** (`.github/workflows/sync.yml`). Elle s'exécute le mercredi et le
   vendredi à 15h55, 16h55 et 17h55, le samedi à 18h et le dimanche à 8h55, heure de Paris
   (heure d'été et d'hiver gérées).
   - Elle lit les événements Spond à venir et repère les traces postées en description ou en
     commentaire : parcours Garmin Connect (`connect.garmin.com/.../course/<id>`) ou export
     d'itinéraire Sports Tracker / Suunto (`api.sports-tracker.com/.../routes/export/...`).
     Pour un même événement, elle prend la **première** trace postée. Entre les événements, elle
     retient la plus récente. Les liens OpenRunner ne sont pas pris en charge (export réservé aux
     comptes connectés).
   - Elle télécharge ce parcours en GPX et le renomme `AAAAMMJJ-RCCS` d'après la date de
     l'événement (suffixe `-2` si deux sorties ont lieu le même jour). Elle l'écrit ensuite dans
     `trace/`, avec `latest.txt` et `latest.json`.
   - Le fichier `.fit` chargé par la montre est celui que Garmin Connect prépare pour ta montre
     principale, renommé `AAAAMMJJ-RCCS`. Il contient les annonces de changement de direction
     si le réglage « Notifications de changements de direction » est activé sur le parcours.
     S'il n'est pas disponible, le workflow le recrée à partir du GPX et détecte lui-même les
     virages (seuil 45°).
   - **Rien n'est écrit dans le compte Garmin.** La connexion Garmin sert uniquement à lire le
     parcours, que Garmin refuse de fournir sans connexion.
   - L'ancienne trace reste dans `trace/` tant qu'aucune trace plus récente n'a été postée. Elle
     n'est supprimée qu'une fois la nouvelle téléchargée.
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

**Tester tout de suite** : onglet **Actions → Trace Spond RCCS → Run workflow**.

**Publier un parcours précis** (test, ou trace partagée ailleurs que sur Spond) : dans
**Run workflow**, renseigne le lien ou le numéro du parcours Garmin, la date (AAAA-MM-JJ) et
l'heure. Spond n'est pas lu. La trace est publiée sous le nom AAAAMMJJ-RCCS et sera remplacée par
la prochaine trace postée sur Spond.

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

**Si l'application disparaît après une mise à jour** : supprime l'ancienne version et vide le
cache avec Garmin Express, puis recopie le nouveau `.prg`. Ne garde qu'un seul `.prg` de
l'application dans `GARMIN/APPS`.

## Fichiers

```
.github/workflows/sync.yml   tâche planifiée
sync/sync_rccs.py            publication de la dernière trace (lecture Spond + Garmin)
sync/garmin_tokens.py        génération des jetons Garmin (à lancer en local)
trace/                       dernière trace uniquement (écrit par la tâche)
garmin-app/                  application Connect IQ « Trace RCCS »
```
