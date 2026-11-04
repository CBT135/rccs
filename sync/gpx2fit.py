"""Conversion GPX -> fichier FIT « course » (parcours) pour les montres Garmin.

Le fichier reproduit exactement la structure des parcours FIT exportés par
Garmin Connect (mêmes messages, mêmes champs, mêmes types, même ordre, big-endian) :

    file_id, course, lap, event (start), record x N, event (stop), file_creator

Le nom du parcours (course.name) est celui affiché dans le menu Parcours de la montre.
"""

from __future__ import annotations

import datetime as dt
import math
import struct
import xml.etree.ElementTree as ET

NS = "{http://www.topografix.com/GPX/1/1}"
SPEED = 3.334            # m/s, allure de référence utilisée par Garmin Connect (12 km/h)
FIT_EPOCH = 631065600    # 1989-12-31T00:00:00Z
PROFILE_VERSION = 21219
CREATOR = "rccs-gpx2fit"

# Types de base FIT : (code, format struct big-endian)
ENUM, UINT8, UINT16, UINT32, SINT32, STRING = (0x00, "B"), (0x02, "B"), (0x84, "H"), (0x86, "I"), (0x85, "i"), (0x07, None)

# Définitions identiques à celles d'un parcours Garmin Connect : (global, [(champ, taille, type)])
DEFS = {
    "file_id": (0, [(0, 1, ENUM), (1, 2, UINT16), (2, 2, UINT16), (4, 4, UINT32), (3, 4, 0x8C), (5, 2, UINT16)]),
    "course": (31, [(254, 2, UINT16), (5, 53, STRING), (4, 1, ENUM), (7, 1, ENUM)]),
    "lap": (19, [(2, 4, UINT32), (253, 4, UINT32), (3, 4, SINT32), (4, 4, SINT32), (5, 4, SINT32), (6, 4, SINT32),
                 (21, 2, UINT16), (22, 2, UINT16), (29, 4, SINT32), (30, 4, SINT32), (27, 4, SINT32), (28, 4, SINT32),
                 (13, 2, UINT16), (7, 4, UINT32), (8, 4, UINT32), (9, 4, UINT32), (254, 2, UINT16)]),
    "event": (21, [(253, 4, UINT32), (0, 1, ENUM), (4, 1, UINT8), (1, 1, ENUM)]),
    "record": (20, [(0, 4, SINT32), (1, 4, SINT32), (253, 4, UINT32), (6, 2, UINT16), (5, 4, UINT32),
                    (2, 2, UINT16), (121, 2, UINT16), (122, 2, UINT16)]),
    "file_creator": (49, [(1, 1, UINT8), (2, 21, STRING)]),
}


def _crc(data: bytes, crc: int = 0) -> int:
    table = (0x0000, 0xCC01, 0xD801, 0x1400, 0xF001, 0x3C00, 0x2800, 0xE401,
             0xA001, 0x6C00, 0x7800, 0xB401, 0x5000, 0x9C01, 0x8801, 0x4400)
    for byte in data:
        tmp = table[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ table[byte & 0xF]
        tmp = table[crc & 0xF]
        crc = (crc >> 4) & 0x0FFF
        crc = crc ^ tmp ^ table[(byte >> 4) & 0xF]
    return crc


class _Writer:
    def __init__(self):
        self.buf = bytearray()

    def define(self, local: int, name: str) -> None:
        g, fields = DEFS[name]
        self.buf += struct.pack(">BBBHB", 0x40 | local, 0, 1, g, len(fields))
        for num, size, bt in fields:
            code = bt if isinstance(bt, int) else bt[0]
            self.buf += struct.pack(">BBB", num, size, code)

    def data(self, local: int, name: str, values: dict) -> None:
        _, fields = DEFS[name]
        self.buf.append(local)
        for num, size, bt in fields:
            v = values[num]
            if bt is STRING:
                raw = v.encode("utf-8")[: size - 1]
                self.buf += raw + b"\0" * (size - len(raw))
            elif isinstance(bt, int):  # uint32z (numéro de série)
                self.buf += struct.pack(">I", v)
            else:
                self.buf += struct.pack(">" + bt[1], v)

    def file(self) -> bytes:
        header = struct.pack(">BB", 14, 0x10) + struct.pack("<HI", PROFILE_VERSION, len(self.buf)) + b".FIT"
        header += struct.pack("<H", _crc(header))
        body = header + bytes(self.buf)
        return body + struct.pack("<H", _crc(body))


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


def _semi(deg: float) -> int:
    return int(round(deg * 2**31 / 180))


def gpx_to_fit(gpx: bytes, name: str, course_id: int = 0) -> bytes:
    pts = _points(gpx)
    t0 = int(dt.datetime.now(dt.timezone.utc).timestamp()) - FIT_EPOCH

    # Points : distance cumulée, dénivelés cumulés, horodatage à allure constante.
    recs, dist, up, down, prev_ele = [], 0.0, 0.0, 0.0, None
    for i, (lat, lon, ele) in enumerate(pts):
        if i:
            dist += _dist(pts[i - 1], (lat, lon))
        if ele is not None and prev_ele is not None:
            d = ele - prev_ele
            up += max(d, 0.0)
            down += max(-d, 0.0)
        if ele is not None:
            prev_ele = ele
        alt = ele if ele is not None else (prev_ele if prev_ele is not None else 0.0)
        recs.append({
            0: _semi(lat), 1: _semi(lon),
            253: t0 + int(round(dist / SPEED)),
            6: 0 if i == 0 else int(round(SPEED * 1000)),
            5: int(round(dist * 100)),
            2: max(0, min(0xFFFE, int(round((alt + 500) * 5)))),
            121: int(round(up)), 122: int(round(down)),
        })
    t_end = recs[-1][253]
    elapsed_ms = int(round(dist / SPEED * 1000))
    lats = [r[0] for r in recs]
    lons = [r[1] for r in recs]

    w = _Writer()
    w.define(0, "file_id")
    w.data(0, "file_id", {0: 6, 1: 1, 2: 65534, 4: t0, 3: course_id & 0xFFFFFFFF, 5: 1})
    w.define(1, "course")
    w.data(1, "course", {254: 0, 5: name, 4: 1, 7: 0})          # sport 1 = course à pied
    w.define(2, "lap")
    w.data(2, "lap", {
        2: t0, 253: t0,
        3: recs[0][0], 4: recs[0][1], 5: recs[-1][0], 6: recs[-1][1],
        21: int(round(up)), 22: int(round(down)),
        29: min(lats), 30: min(lons), 27: max(lats), 28: max(lons),
        13: 0, 7: elapsed_ms, 8: elapsed_ms, 9: int(round(dist * 100)), 254: 0,
    })
    w.define(3, "event")
    w.data(3, "event", {253: t0, 0: 0, 4: 0, 1: 0})           # timer, start
    w.define(4, "record")
    for r in recs:
        w.data(4, "record", r)
    w.data(3, "event", {253: t_end, 0: 0, 4: 0, 1: 9})        # timer, stop_disable_all
    w.define(0, "file_creator")
    w.data(0, "file_creator", {1: 0, 2: CREATOR})
    return w.file()
