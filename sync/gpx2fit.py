"""Conversion GPX -> fichier FIT « course » (parcours) lisible par les montres Garmin.

Le nom du parcours (Course.name) est celui affiché dans le menu Parcours de la montre.
"""

from __future__ import annotations

import datetime as dt
import math
import xml.etree.ElementTree as ET

from fit_tool.fit_file_builder import FitFileBuilder
from fit_tool.profile.messages.course_message import CourseMessage
from fit_tool.profile.messages.event_message import EventMessage
from fit_tool.profile.messages.file_id_message import FileIdMessage
from fit_tool.profile.messages.lap_message import LapMessage
from fit_tool.profile.messages.record_message import RecordMessage
from fit_tool.profile.profile_type import Event, EventType, FileType, Manufacturer, Sport

NS = "{http://www.topografix.com/GPX/1/1}"
SPEED = 10 / 3.6  # allure fictive de 10 km/h pour les horodatages du parcours


def _points(gpx: bytes) -> list[tuple[float, float, float | None]]:
    root = ET.fromstring(gpx)
    pts = []
    for tag in ("trkpt", "rtept"):
        for p in root.iter(NS + tag):
            ele = p.find(NS + "ele")
            pts.append((float(p.get("lat")), float(p.get("lon")),
                        float(ele.text) if ele is not None and ele.text else None))
        if pts:
            break
    if len(pts) < 2:
        raise ValueError("GPX sans points de trace")
    return pts


def _dist(a, b) -> float:
    r = 6371008.8
    la1, la2 = math.radians(a[0]), math.radians(b[0])
    dla, dlo = la2 - la1, math.radians(b[1] - a[1])
    h = math.sin(dla / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin(dlo / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def gpx_to_fit(gpx: bytes, name: str) -> bytes:
    pts = _points(gpx)
    t0 = round(dt.datetime.now(dt.timezone.utc).timestamp()) * 1000

    records, dist, ts = [], 0.0, t0
    for i, p in enumerate(pts):
        if i:
            step = _dist(pts[i - 1], p)
            dist += step
            ts += max(1000, round(step / SPEED * 1000))
        r = RecordMessage()
        r.timestamp = ts
        r.position_lat = p[0]
        r.position_long = p[1]
        r.distance = dist
        if p[2] is not None:
            r.altitude = p[2]
        records.append(r)
    t_end = ts
    ascent = sum(max(0.0, (b[2] or 0) - (a[2] or 0)) for a, b in zip(pts, pts[1:]) if a[2] is not None and b[2] is not None)
    descent = sum(max(0.0, (a[2] or 0) - (b[2] or 0)) for a, b in zip(pts, pts[1:]) if a[2] is not None and b[2] is not None)

    b = FitFileBuilder(auto_define=True, min_string_size=50)

    m = FileIdMessage()
    m.type = FileType.COURSE
    m.manufacturer = Manufacturer.DEVELOPMENT.value
    m.product = 0
    m.time_created = t0
    m.serial_number = 0x52434353  # "RCCS"
    b.add(m)

    m = CourseMessage()
    m.course_name = name
    m.sport = Sport.RUNNING
    b.add(m)

    m = LapMessage()
    m.timestamp = t_end
    m.start_time = t0
    m.start_position_lat, m.start_position_long = pts[0][0], pts[0][1]
    m.end_position_lat, m.end_position_long = pts[-1][0], pts[-1][1]
    m.total_elapsed_time = (t_end - t0) / 1000
    m.total_timer_time = (t_end - t0) / 1000
    m.total_distance = dist
    m.total_ascent = round(ascent)
    m.total_descent = round(descent)
    b.add(m)

    m = EventMessage()
    m.timestamp = t0
    m.event = Event.TIMER
    m.event_type = EventType.START
    b.add(m)

    b.add_all(records)

    m = EventMessage()
    m.timestamp = t_end
    m.event = Event.TIMER
    m.event_type = EventType.STOP_ALL
    b.add(m)

    return b.build().to_bytes()
