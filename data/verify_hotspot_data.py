"""Reproduces the numbers in E01-Official-Data-and-Field-Mapping.md.

Usage: python3 verify_hotspot_data.py wifi_hotspots_full.csv
"""
import csv
import sys
from collections import Counter

rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
n = len(rows)

BOROUGHS = {"1": "Manhattan", "2": "Bronx", "3": "Brooklyn", "4": "Queens", "5": "Staten Island"}


def blank(v):
    return v is None or v.strip() == ""


def normalize(r):
    """Cleaning rules from the mapping doc: sentinels become None."""
    out = dict(r)
    if out["activated"].startswith("9999-09-09"):
        out["activated"] = None
    if out["sourceid"] in ("", "0"):
        out["sourceid"] = None
    return out


rows = [normalize(r) for r in rows]
print("rows:", n, "columns:", len(rows[0]))
print("unique doitt_id:", len({r["doitt_id"] for r in rows}) == n)
print("unique objectid:", len({r["objectid"] for r in rows}) == n)
print("missing lat/long:", sum(1 for r in rows if blank(r["latitude"]) or blank(r["longitude"])))
print("borough code matches boroname:", all(BOROUGHS[r["borough"]] == r["boroname"] for r in rows))
print("providers:", len({r["provider"] for r in rows}))
print("type:", dict(Counter(r["type"] for r in rows)))
print("missing name:", sum(1 for r in rows if blank(r["name"])), "/", n)
print("missing remarks:", sum(1 for r in rows if blank(r["remarks"])), "/", n)
print("activated unknown (sentinel):", sum(1 for r in rows if r["activated"] is None))
print("sourceid null after cleaning:", sum(1 for r in rows if r["sourceid"] is None))
coords = Counter((r["latitude"], r["longitude"]) for r in rows)
print("coordinate groups shared by 2+ hotspots:", sum(1 for v in coords.values() if v > 1))
