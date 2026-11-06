#!/usr/bin/env python3
"""Publie dans le dépôt (dossier trace/) la dernière trace Garmin postée sur Spond.

Étapes :
  1. Connexion à Spond, lecture des événements à venir (avec commentaires).
  2. Recherche des liens de parcours Garmin (connect.garmin.com/.../course/<id>)
     dans la description et les commentaires ; on retient le plus récent.
  3. Téléchargement du parcours en GPX (lecture seule : rien n'est écrit dans le
     compte Garmin, la connexion sert uniquement à lire le parcours), renommé
     AAAAMMJJ-<SIGLE> d'après la date de l'événement (ex. 20261104-RCCS).
  4. Écriture dans trace/ (FIT pour la montre + GPX + latest.json + latest.txt). L'ancienne trace n'est
     supprimée qu'une fois la nouvelle téléchargée ; sans nouvelle trace, le
     dossier reste inchangé. C'est ce que télécharge l'application de la montre.

Variables d'environnement (secrets GitHub) :
  SPOND_USERNAME, SPOND_PASSWORD     identifiants Spond
  GARMIN_EMAIL, GARMIN_PASSWORD      identifiants Garmin Connect
  GARMIN_TOKENS                      (facultatif) jetons Garmin, voir README
  CLUB_SIGLE                         (facultatif) force le sigle, sinon initiales du club
"""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Europe/Paris")
ROOT = Path(__file__).resolve().parent.parent
TRACE_DIR = ROOT / "trace"
SPOND_API = "https://api.spond.com/core/v1/"
COURSE_RE = re.compile(r"connect\.garmin\.com/(?:modern|app)/course/(\d+)", re.I)
# Export GPX d'un itinéraire Suunto / Sports Tracker (lien public, sans connexion).
SPORTSTRACKER_RE = re.compile(r"https://api\.sports-tracker\.com/apiserver/v\d+/routes/export/[^\s\"'<>]+", re.I)
SUMMARY: list[str] = []


def log(msg: str) -> None:
    print(msg, flush=True)
    SUMMARY.append(msg)


# ---------------------------------------------------------------- Spond --

async def spond_events() -> list[dict]:
    from spond import spond as spond_mod

    user, pwd = os.environ.get("SPOND_USERNAME"), os.environ.get("SPOND_PASSWORD")
    if not user or not pwd:
        sys.exit("Secrets SPOND_USERNAME / SPOND_PASSWORD manquants.")
    s = spond_mod.Spond(username=user, password=pwd)
    try:
        await s.login()
        params = {
            "includeComments": "true",
            "addProfileInfo": "false",
            "scheduled": "true",
            "order": "asc",
            "max": "100",
            "minEndTimestamp": dt.datetime.now(dt.timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%S.000Z"
            ),
        }
        async with s.clientsession.get(
            SPOND_API + "sponds", headers=s.auth_headers, params=params
        ) as r:
            if not r.ok:
                raise RuntimeError(f"Spond : erreur {r.status} {await r.text()}")
            return await r.json()
    finally:
        await s.clientsession.close()


def texts_of(event: dict) -> list[str]:
    out = [event.get("description") or ""]
    stack = list(event.get("comments") or [])
    while stack:
        c = stack.pop(0)
        out.append(c.get("text") or "")
        stack.extend(c.get("children") or [])
    return out


def _ts(v) -> dt.datetime:
    """Horodatage Spond (ISO ou millisecondes) -> datetime UTC."""
    if isinstance(v, (int, float)):
        return dt.datetime.fromtimestamp(v / 1000, dt.timezone.utc)
    if isinstance(v, str) and v:
        return dt.datetime.fromisoformat(v.replace("Z", "+00:00"))
    return dt.datetime.min.replace(tzinfo=dt.timezone.utc)


def sources_in(text: str) -> list:
    """Traces prises en charge dans un texte, dans l'ordre : numéro de parcours Garmin (int)
    ou lien d'export Sports Tracker (str)."""
    found = [(m.start(), int(m.group(1))) for m in COURSE_RE.finditer(text)]
    found += [(m.start(), m.group(0)) for m in SPORTSTRACKER_RE.finditer(text)]
    return [src for _, src in sorted(found)]


def course_link_of(event: dict) -> tuple[int | str, dt.datetime] | None:
    """Première trace postée dans l'événement (description puis commentaires, par date),
    avec sa date de publication. Garmin Connect ou Sports Tracker."""
    posts = [(_ts(event.get("createdTime") or event.get("updated")), event.get("description") or "")]
    stack = list(event.get("comments") or [])
    while stack:
        c = stack.pop(0)
        stack.extend(c.get("children") or [])
        posts.append((_ts(c.get("timestamp")), c.get("text") or ""))
    for when, text in sorted(posts, key=lambda x: x[0]):
        srcs = sources_in(text)
        if srcs:
            return srcs[0], when
    return None


def describe(src) -> str:
    return f"parcours Garmin {src}" if isinstance(src, int) else "itinéraire Sports Tracker"


def club_sigle(event: dict) -> str:
    forced = os.environ.get("CLUB_SIGLE", "").strip()
    if forced:
        return forced
    name = ((event.get("recipients") or {}).get("group") or {}).get("name") or ""
    words = [w for w in re.split(r"[\s\-'’]+", name) if w and w[0].isalpha()]
    sigle = "".join(w[0].upper() for w in words if w[0].isupper() or len(w) > 3)
    return sigle or "RCCS"


# --------------------------------------------------------------- Garmin --

def garmin_client():
    from garminconnect import Garmin

    email, pwd = os.environ.get("GARMIN_EMAIL"), os.environ.get("GARMIN_PASSWORD")
    tokens = os.environ.get("GARMIN_TOKENS", "").strip() or None
    if not tokens and not (email and pwd):
        sys.exit("Secrets GARMIN_EMAIL / GARMIN_PASSWORD (ou GARMIN_TOKENS) manquants.")
    g = Garmin(email=email, password=pwd)
    g.login(tokenstore=tokens) if tokens else g.login()
    return g


def rename_gpx(raw: bytes, name: str) -> bytes:
    m = re.search(rb'<gpx[^>]*\sxmlns="([^"]+)"', raw)
    ns = m.group(1).decode() if m else "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", ns)
    # Conserve les préfixes d'origine de Garmin (sinon ET écrit ns0, ns1…).
    for prefix, uri in re.findall(rb'xmlns:(\w+)="([^"]+)"', raw):
        try:
            ET.register_namespace(prefix.decode(), uri.decode())
        except ValueError:  # préfixes « nsN » réservés par ElementTree, renommés automatiquement
            pass
    root = ET.fromstring(raw)
    found = False
    for tag in ("metadata", "trk", "rte"):
        for el in root.iter(f"{{{ns}}}{tag}"):
            n = el.find(f"{{{ns}}}name")
            if n is None:
                n = ET.Element(f"{{{ns}}}name")
                el.insert(0, n)
            n.text = name
            found = True
    if not found:
        raise ValueError("GPX sans trace")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def download_url(url: str) -> bytes:
    import urllib.request

    req = urllib.request.Request(url, headers={"User-Agent": "rccs-trace/1.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        data = r.read()
    if b"<gpx" not in data[:2000]:
        raise ValueError(f"le lien ne renvoie pas de GPX ({data[:80]!r})")
    return data


def get_gpx(g, src) -> bytes:
    return g.download_course(src, fmt="gpx") if isinstance(src, int) else download_url(src)


def publish(g, name: str, src, start: dt.datetime, event: dict, posted: dt.datetime) -> None:
    """Écrit la trace dans trace/ et supprime toutes les autres."""
    TRACE_DIR.mkdir(exist_ok=True)
    from gpx2fit import gpx_to_fit, rename_fit_course, stats

    gpx = rename_gpx(get_gpx(g, src), name)
    fit = None
    if isinstance(src, int):
        # FIT préparé par Garmin Connect pour la montre principale : il contient les points de virage
        # (selon le réglage « Notifications de changements de direction » du parcours). On ne change
        # que son nom. À défaut, conversion maison du GPX avec détection des virages.
        try:
            device = os.environ.get("GARMIN_DEVICE_ID", "").strip() or \
                g.get_primary_training_device()["PrimaryTrainingDevice"]["deviceId"]
            raw = g.download(f"/course-service/course/fit/{src}/{device}", params={"elevation": "true"})
            fit = rename_fit_course(raw, name)
            log(f"FIT Garmin pour l'appareil {device}, renommé {name}")
        except Exception as e:
            log(f"FIT Garmin indisponible ({e}) : conversion du GPX avec détection des virages")
    if fit is None:
        fit = gpx_to_fit(gpx, name, src if isinstance(src, int) else 0)
        st = stats(gpx)
        log(f"FIT créé depuis le GPX : {st['km']} km, {st['points']} points, {st['virages']} virages, "
            f"altitude {'oui' if st['altitude'] else 'non'}")
    keep = {f"{name}.fit", f"{name}.gpx", "latest.json", "latest.txt"}
    for f in TRACE_DIR.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
    (TRACE_DIR / f"{name}.gpx").write_bytes(gpx)
    (TRACE_DIR / f"{name}.fit").write_bytes(fit)
    meta = {
        "name": name,
        "fit": f"trace/{name}.fit",
        "gpx": f"trace/{name}.gpx",
        "date": start.date().isoformat(),
        "heure": start.strftime("%H:%M"),
        "titre": event.get("heading"),
        "source": f"https://connect.garmin.com/modern/course/{src}" if isinstance(src, int) else src,
        "publieeSurSpond": posted.astimezone(TZ).isoformat(timespec="seconds"),
    }
    (TRACE_DIR / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    # Lu par l'application de la montre (GitHub sert les fichiers bruts en text/plain).
    (TRACE_DIR / "latest.txt").write_text(name + "\n")
    log(f"Trace publiée dans le dépôt : {name}")


# ----------------------------------------------------------------- main --

def forced() -> bool:
    """Lancement manuel avec un parcours imposé (champs du formulaire « Run workflow »)."""
    cid = os.environ.get("FORCE_COURSE_ID", "").strip()
    if not cid:
        return False
    srcs = sources_in(cid)
    cid = srcs[0] if srcs else int(cid)
    day = os.environ.get("FORCE_DATE", "").strip()
    hhmm = os.environ.get("FORCE_TIME", "").strip() or "18:30"
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
        sys.exit("Date attendue au format AAAA-MM-JJ.")
    start = dt.datetime.fromisoformat(f"{day}T{hhmm}").replace(tzinfo=TZ)
    sigle = os.environ.get("CLUB_SIGLE", "").strip() or "RCCS"
    name = f"{start:%Y%m%d}-{sigle}"
    log(f"Publication manuelle : {describe(cid)} -> {name}")
    # Datée du début de la sortie : toute trace postée ensuite sur Spond la remplacera.
    publish(garmin_client() if isinstance(cid, int) else None, name, cid, start,
            {"heading": "Publication manuelle"}, start)
    return True


URL_RE = re.compile(r"https?://\S+")


def list_links(events: list[dict]) -> None:
    """Mode relevé : affiche les liens postés dans les événements à venir, sans rien publier."""
    for ev in events:
        start = dt.datetime.fromisoformat(ev["startTimestamp"].replace("Z", "+00:00")).astimezone(TZ)
        items = [("description", ev.get("createdTime"), ev.get("description") or "")]
        stack = list(ev.get("comments") or [])
        while stack:
            c = stack.pop(0)
            stack.extend(c.get("children") or [])
            items.append(("commentaire", c.get("timestamp"), c.get("text") or ""))
        for kind, when, text in items:
            for url in URL_RE.findall(text):
                log(f"{start:%d/%m %H:%M} {ev.get('heading')} | {kind} {_ts(when).astimezone(TZ):%d/%m %H:%M} | {url}")
        for a in ev.get("attachments") or []:
            log(f"{start:%d/%m %H:%M} {ev.get('heading')} | pièce jointe | {json.dumps(a, ensure_ascii=False)[:300]}")
        link = course_link_of(ev)
        if link:
            from gpx2fit import gpx_to_fit, stats

            src, posted = link
            try:
                g = garmin_client() if isinstance(src, int) else None
                name = f"{start:%Y%m%d}-{club_sigle(ev)}"
                gpx = rename_gpx(get_gpx(g, src), name)
                fit = gpx_to_fit(gpx, name)
                st = stats(gpx)
                log(f"  -> retenue : {describe(src)} (postée le {posted.astimezone(TZ):%d/%m %H:%M}) : GPX lu, "
                    f"{st['km']} km, {st['points']} points, {st['virages']} virages, altitude "
                    f"{'oui' if st['altitude'] else 'non'}, FIT {len(fit)} octets")
            except Exception as e:
                log(f"  -> ERREUR lecture {describe(src)} : {e}")


def main() -> None:
    if forced():
        return
    events = asyncio.run(spond_events())
    if os.environ.get("LIST_LINKS") == "true":
        list_links(events)
        return
    found = []
    per_day: dict[str, int] = {}
    for ev in sorted(events, key=lambda e: e["startTimestamp"]):
        link = course_link_of(ev)
        if not link:
            continue
        cid, posted = link
        start = dt.datetime.fromisoformat(ev["startTimestamp"].replace("Z", "+00:00")).astimezone(TZ)
        base = f"{start:%Y%m%d}-{club_sigle(ev)}"
        per_day[base] = per_day.get(base, 0) + 1
        name = base if per_day[base] == 1 else f"{base}-{per_day[base]}"
        found.append((start, name, cid, ev, posted))

    if not found:
        log("Aucun événement Spond à venir avec une trace : trace précédente conservée.")
        # Vérifie quand même la connexion Garmin (lecture) pour détecter un problème avant la prochaine trace.
        try:
            garmin_client()
            log("Connexion Garmin OK.")
        except SystemExit:
            raise
        except Exception as e:
            log(f"ERREUR connexion Garmin : {e}")
            raise
        return

    # Dépôt : uniquement la dernière trace postée sur Spond.
    start, name, cid, ev, posted = max(found, key=lambda x: x[4])

    # On ne remplace la trace du dépôt que par une trace postée plus récemment.
    current = TRACE_DIR / "latest.json"
    if current.exists():
        try:
            meta = json.loads(current.read_text())
            prev = dt.datetime.fromisoformat(meta["publieeSurSpond"])
            if posted.replace(microsecond=0) <= prev:   # date enregistrée à la seconde près
                log(f"Pas de nouvelle trace (dernière publiée : {meta['name']}) : dépôt inchangé.")
                return
        except (KeyError, ValueError):
            pass
    log(f"Dernière trace postée : {ev.get('heading')} du {start:%d/%m %H:%M} -> {name} ({describe(cid)})")
    publish(garmin_client() if isinstance(cid, int) else None, name, cid, start, ev, posted)


if __name__ == "__main__":
    try:
        main()
    finally:
        out = os.environ.get("GITHUB_STEP_SUMMARY")
        if out and SUMMARY:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write("### Trace Spond RCCS\n\n" + "\n".join(f"- {l}" for l in SUMMARY) + "\n")
