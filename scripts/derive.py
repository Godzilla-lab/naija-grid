#!/usr/bin/env python3
"""
Derived tables from data/nerc_caps_all.csv. Stdlib only.

  data/derived/band_counts_by_disco_month.csv  feeders per band, per DisCo, per month
  data/derived/band_changes.csv                feeders whose band changed between two
                                               consecutive published orders of the same DisCo
  data/derived/feeder_first_last_seen.csv      first and last order each feeder appears in

Feeders are matched on (disco, feeder_key). A key that appears more than once in a
single DisCo order is ambiguous and is left out of band_changes (counted in the log).
"""
from __future__ import annotations

import csv
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "derived"
BANDS = "ABCDE"


def load() -> list[dict]:
    with (DATA / "nerc_caps_all.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def write(path: Path, fields: list[str], rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"{path.relative_to(ROOT)}: {len(rows)} rows")


def band_counts(rows: list[dict]) -> None:
    c: dict[tuple, Counter] = defaultdict(Counter)
    for r in rows:
        c[(r["period"], r["disco"])][r["service_band"]] += 1
    out = []
    for (period, disco), cnt in sorted(c.items()):
        rec = {"period": period, "disco": disco}
        rec.update({f"band_{b}": cnt.get(b, 0) for b in BANDS})
        rec["total"] = sum(cnt.values())
        rec["band_a_share"] = round(cnt.get("A", 0) / rec["total"], 4) if rec["total"] else ""
        out.append(rec)
    write(OUT / "band_counts_by_disco_month.csv",
          ["period", "disco"] + [f"band_{b}" for b in BANDS] + ["total", "band_a_share"], out)


def index(rows: list[dict]):
    """(disco, period) -> {feeder_key: row}, plus the set of ambiguous keys."""
    by: dict[tuple, dict] = defaultdict(dict)
    dup: dict[tuple, set] = defaultdict(set)
    for r in rows:
        k = (r["disco"], r["period"])
        if r["feeder_key"] in by[k]:
            dup[k].add(r["feeder_key"])
        by[k][r["feeder_key"]] = r
    return by, dup


def band_changes(rows: list[dict]) -> None:
    by, dup = index(rows)
    periods: dict[str, list[str]] = defaultdict(list)
    for disco, period in by:
        periods[disco].append(period)
    out, ambiguous = [], 0
    for disco in sorted(periods):
        ps = sorted(periods[disco])
        for prev, cur in zip(ps, ps[1:]):
            a, b = by[(disco, prev)], by[(disco, cur)]
            bad = dup[(disco, prev)] | dup[(disco, cur)]
            for key in sorted(set(a) & set(b)):
                if key in bad:
                    ambiguous += 1
                    continue
                fb, tb = a[key]["service_band"], b[key]["service_band"]
                if fb == tb:
                    continue
                out.append({
                    "disco": disco, "feeder_key": key, "business_unit": b[key]["business_unit"],
                    "feeder_raw": b[key]["feeder_raw"], "from_period": prev, "to_period": cur,
                    "from_band": fb, "to_band": tb,
                    "direction": "up" if tb < fb else "down",
                    "from_cap_kwh": a[key]["cap_kwh"], "to_cap_kwh": b[key]["cap_kwh"],
                })
    write(OUT / "band_changes.csv",
          ["disco", "feeder_key", "business_unit", "feeder_raw", "from_period", "to_period",
           "from_band", "to_band", "direction", "from_cap_kwh", "to_cap_kwh"], out)
    if ambiguous:
        print(f"  {ambiguous} feeder comparisons skipped: key repeated within one order")


def first_last(rows: list[dict]) -> None:
    seen: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        seen[(r["disco"], r["feeder_key"])].append(r)
    out = []
    for (disco, key), rs in sorted(seen.items()):
        rs.sort(key=lambda r: r["period"])
        periods = sorted({r["period"] for r in rs})
        out.append({
            "disco": disco, "feeder_key": key, "business_unit": rs[-1]["business_unit"],
            "feeder_raw": rs[-1]["feeder_raw"], "first_seen": periods[0], "last_seen": periods[-1],
            "months_seen": len(periods), "first_band": rs[0]["service_band"],
            "last_band": rs[-1]["service_band"], "last_cap_kwh": rs[-1]["cap_kwh"],
        })
    write(OUT / "feeder_first_last_seen.csv",
          ["disco", "feeder_key", "business_unit", "feeder_raw", "first_seen", "last_seen",
           "months_seen", "first_band", "last_band", "last_cap_kwh"], out)


def main() -> None:
    rows = load()
    band_counts(rows)
    band_changes(rows)
    first_last(rows)


if __name__ == "__main__":
    main()
