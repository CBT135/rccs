#!/usr/bin/env python3
"""Synchronise les traces Garmin des événements Spond du club vers Garmin Connect
et publie la prochaine trace dans le dépôt (dossier trace/).

Étapes :
  1. Connexion à Spond, lecture des événements à venir (avec commentaires).
  2. Recherche des liens de parcours Garmin (connect.garmin.com/.../course/<id>)
     dans la description et les commentaires.
  3. Pour chaque événement trouvé : ajout au calendrier Garmin d'un événement
     AAAAMMJJ-<SIGLE> (ex. 20261104-RCCS) à la date et l'heure de l'événement
     Spond (sans copier le parcours dans le compte, rien n'est recréé s'il existe).
  4. La dernière trace postée sur Spond est téléchargée en GPX, renommée
     AAAAMMJJ-<SIGLE> et écrite dans trace/ (GPX + latest.json + latest.txt) ; les anciennes traces sont supprimées, il n'en
     reste qu'une seule. C'est ce que télécharge l'application de la montre.

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


def course_link_of(event: dict) -> tuple[int, dt.datetime] | None:
    """Dernier lien de parcours publié dans l'événement, avec sa date de publication."""
    best: tuple[int, dt.datetime] | None = None
    desc_ids = COURSE_RE.findall(event.get("description") or "")
    if desc_ids:
        best = (int(desc_ids[-1]), _ts(event.get("createdTime") or event.get("updated")))
    stack = list(event.get("comments") or [])
    while stack:
        c = stack.pop(0)
        stack.extend(c.get("children") or [])
        ids = COURSE_RE.findall(c.get("text") or "")
        if ids:
            when = _ts(c.get("timestamp"))
            if best is None or when >= best[1]:
                best = (int(ids[-1]), when)
    return best


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


def month_items(g, day: dt.date, cache: dict) -> list[dict]:
    key = (day.year, day.month)
    if key not in cache:
        data = g.connectapi(f"/calendar-service/year/{day.year}/month/{day.month - 1}")
        cache[key] = data.get("calendarItems") or []
    return cache[key]


def ensure_event(g, name: str, start: dt.datetime, course: dict, event: dict, cache: dict) -> None:
    day = start.date()
    for it in month_items(g, day, cache):
        if it.get("title") == name and it.get("date") == day.isoformat():
            log(f"  événement {name} déjà au calendrier")
            return
    loc = event.get("location") or {}
    city = loc.get("address") or loc.get("feature") or ""
    sp = json.loads(course["startPoint"]) if isinstance(course.get("startPoint"), str) else (course.get("startPoint") or {})
    body = {
        "eventName": name,
        "date": day.isoformat(),
        "completionTarget": {
            "value": round((course.get("distanceMeter") or 0) / 1000, 2),
            "unit": "kilometer",
            "unitType": "distance",
        },
        "eventTimeLocal": {"startTimeHhMm": start.strftime("%H:%M"), "timeZoneId": "Europe/Paris"},
        "note": f"Spond : {event.get('heading', '')}",
        "location": f"{city}, FR" if city else None,
        "locationStartPoint": {"lat": sp.get("latitude"), "lon": sp.get("longitude")} if sp else None,
        "eventType": "running",
        "eventPrivacy": {"label": "PRIVATE", "isShareable": False, "isDiscoverable": False},
        "eventCustomization": {"customGoal": None, "isPrimaryEvent": False, "isTrainingEvent": False},
        "race": False,
    }
    g.create_calendar_event(body)
    cache.pop((day.year, day.month), None)
    log(f"  événement {name} ajouté au calendrier le {day} à {start:%H:%M}")


def rename_gpx(raw: bytes, name: str) -> bytes:
    ns = "http://www.topografix.com/GPX/1/1"
    ET.register_namespace("", ns)
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


def publish(g, name: str, course_id: int, start: dt.datetime, event: dict, posted: dt.datetime) -> None:
    """Écrit la trace dans trace/ et supprime toutes les autres."""
    TRACE_DIR.mkdir(exist_ok=True)
    gpx = rename_gpx(g.download_course(course_id, fmt="gpx"), name)
    keep = {f"{name}.gpx", "latest.json", "latest.txt"}
    for f in TRACE_DIR.iterdir():
        if f.is_file() and f.name not in keep:
            f.unlink()
    (TRACE_DIR / f"{name}.gpx").write_bytes(gpx)
    meta = {
        "name": name,
        "gpx": f"trace/{name}.gpx",
        "date": start.date().isoformat(),
        "heure": start.strftime("%H:%M"),
        "titre": event.get("heading"),
        "garminCourseId": course_id,
        "publieeSurSpond": posted.astimezone(TZ).isoformat(timespec="minutes"),
    }
    (TRACE_DIR / "latest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n")
    # Lu par l'application de la montre (GitHub sert les fichiers bruts en text/plain).
    (TRACE_DIR / "latest.txt").write_text(name + "\n")
    log(f"Trace publiée dans le dépôt : {name}")


# ----------------------------------------------------------------- main --

def main() -> None:
    events = asyncio.run(spond_events())
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
        log("Aucun événement Spond à venir avec une trace Garmin. Dépôt inchangé.")
        return

    g = garmin_client()
    cache: dict = {}
    for start, name, cid, ev, posted in found:
        log(f"{start:%d/%m %H:%M} {ev.get('heading')} -> {name} (parcours {cid})")
        try:
            ensure_event(g, name, start, g.get_course(cid), ev, cache)
        except Exception as e:  # on continue avec les autres événements
            log(f"  ERREUR calendrier Garmin : {e}")

    # Dépôt : uniquement la dernière trace postée sur Spond.
    start, name, cid, ev, posted = max(found, key=lambda x: x[4])
    publish(g, name, cid, start, ev, posted)


if __name__ == "__main__":
    try:
        main()
    finally:
        out = os.environ.get("GITHUB_STEP_SUMMARY")
        if out and SUMMARY:
            with open(out, "a", encoding="utf-8") as fh:
                fh.write("### Synchro Spond → Garmin\n\n" + "\n".join(f"- {l}" for l in SUMMARY) + "\n")
