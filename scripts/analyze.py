#!/usr/bin/env python3
"""
naija-grid analysis: turn the raw NERC cap rows into clean tables, rankings, charts and findings.

Input : output/grid/nerc_caps_all.csv  (one row per feeder per order month, from nerc_caps.py)
Output: output/grid/analysis/
          clean/feeders.csv               one row per feeder (dimension table)
          clean/caps_long.csv             one row per feeder per month (fact table)
          clean/band_history_wide.csv     feeders x months, band letters (opens well in Excel)
          summary/coverage_by_month.csv   PDFs, DisCos, states, feeders per month
          summary/disco_month.csv         band counts and shares, median caps, per DisCo per month
          summary/state_month.csv         same per state
          summary/state_jurisdiction.csv  first and last month each state appears in NERC caps
          summary/band_transitions.csv    every month-to-month band change, with direction
          rankings/*.csv                  latest-month rankings, highest to lowest
          charts/*.png
          findings.json                   every number the report quotes, computed here
Run   : python scripts/analyze.py
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "parsed" / "nerc_caps_all.csv"
OUT = ROOT / "data"

BANDS = ["A", "B", "C", "D", "E"]
BAND_RANK = {b: i for i, b in enumerate(BANDS)}  # A=0 best supply promise, E=4 worst
BAND_COLORS = {"A": "#1b7837", "B": "#7fbf7b", "C": "#d9d9d9", "D": "#f1a340", "E": "#b35806"}
DISCO_NAMES = {
    "AEDC": "Abuja", "BEDC": "Benin", "EEDC": "Enugu", "EKEDC": "Eko", "IBEDC": "Ibadan",
    "IKEDC": "Ikeja", "JEDC": "Jos", "KAEDC": "Kaduna", "KEDCO": "Kano", "PHED": "Port Harcourt",
    "YEDC": "Yola", "APLE": "Aba Power",
}


def norm_key(s: str) -> str:
    s = str(s or "").upper()
    s = re.sub(r"[^A-Z0-9/]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def ym(y: int, m: int) -> str:
    return f"{int(y):04d}-{int(m):02d}"


def prev_month(s: str) -> str:
    y, m = map(int, s.split("-"))
    m -= 1
    if m == 0:
        y, m = y - 1, 12
    return ym(y, m)


MANUAL_BU_STATE = ROOT / "data" / "reference" / "bu_state_manual.csv"


NG_STATES = ["ABIA", "ADAMAWA", "AKWA IBOM", "ANAMBRA", "BAUCHI", "BAYELSA", "BENUE", "BORNO", "CROSS RIVER",
             "DELTA", "EBONYI", "EDO", "EKITI", "ENUGU", "FCT", "GOMBE", "IMO", "JIGAWA", "KADUNA", "KANO", "KATSINA",
             "KEBBI", "KOGI", "KWARA", "LAGOS", "NASARAWA", "NIGER", "OGUN", "ONDO", "OSUN", "OYO", "PLATEAU",
             "RIVERS", "SOKOTO", "TARABA", "YOBE", "ZAMFARA"]


def clean_state(v: str) -> str:
    """Map a printed or OCR'd state to one of the 37; anything else becomes blank.

    OCR reads table borders as I, L, [ or | ('ILAGOS', 'LEBONYI', '[SOKOTO') and sometimes adds
    a trailing R ('ADAMAWAR'). Exact match first, then those repairs, then a strict fuzzy match.
    """
    import difflib
    s = re.sub(r"[^A-Z ]", " ", str(v or "").upper())
    s = re.sub(r"\s+", " ", s).strip()
    if s in ("ABUJA", "FCT ABUJA", "F C T"):
        return "FCT"
    if s in NG_STATES:
        return s
    for cand in (s[1:], s[:-1], s[1:-1], s.split(" ")[0]):
        if cand in NG_STATES:
            return cand
    m = difflib.get_close_matches(s, NG_STATES, n=1, cutoff=0.86)
    return m[0] if m else ""


def feeder_core(raw: str) -> str:
    """Stable feeder name: drop voltage tags, the word FEEDER, punctuation and case."""
    s = str(raw or "").upper()
    s = re.sub(r"\b\d{1,2}\s*KV\b", " ", s)
    s = re.sub(r"^\d{1,2}\s*-\s*", " ", s)            # Ikeja '11-...'
    s = re.sub(r"\bFEEDERS?\b|\bFDR\b", " ", s)
    s = s.replace("_", " ")
    s = re.sub(r"[^A-Z0-9/]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def bu_core(bu: str) -> str:
    s = norm_key(bu)
    s = re.sub(r"\b(BU|BUSINESS UNIT|AREA OFFICE|DISTRICT|REGION|REGIONAL OFFICE|SERVICE CENTRE|SC)\b", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def load() -> pd.DataFrame:
    df = pd.read_csv(SRC, dtype=str).fillna("")
    df = df[df["service_band"].isin(BANDS)].copy()
    df["cap_kwh"] = pd.to_numeric(df["cap_kwh"], errors="coerce")
    df = df[df["cap_kwh"].notna() & (df["cap_kwh"] > 0)]
    df["order_month"] = [ym(y, m) for y, m in zip(df["year"], df["month"])]
    df["consumption_month"] = df["order_month"].map(prev_month)
    df["disco_name"] = df["disco"].map(DISCO_NAMES).fillna(df["disco"])
    df["bu_core"] = df["business_unit"].map(bu_core)
    df["state_printed_raw"] = df["state"]
    # two-word states split across two columns by the layout: 'AKWA' | 'IBOM', 'CROSS' | 'RIVER'
    joined = (df["state"].str.upper().str.strip() + " " + df["business_unit"].str.upper().str.strip())
    two = joined.isin(["AKWA IBOM", "CROSS RIVER"])
    df.loc[two, "state"] = joined[two]
    df.loc[two, "business_unit"] = df.loc[two, "feeder_raw"].str.split().str[0]
    df.loc[two, "feeder_raw"] = df.loc[two, "feeder_raw"].str.split(n=1).str[1].fillna("")
    df["bu_core"] = df["business_unit"].map(bu_core)
    df["state"] = df["state"].map(clean_state)

    # State: printed > learned from newer orders (same DisCo + business unit) > manual map > unknown
    df["state_source"] = df["state"].map(lambda v: "printed" if v else "")
    learned = (df[df["state"] != ""].groupby(["disco", "bu_core"])["state"]
               .agg(lambda s: s.value_counts().index[0]).to_dict())
    manual = {}
    if MANUAL_BU_STATE.exists():
        m = pd.read_csv(MANUAL_BU_STATE, dtype=str).fillna("")
        manual = {(r.disco, r.bu_core): r.state for r in m.itertuples()}
    fill_l = [(learned.get((d, b), "")) for d, b in zip(df["disco"], df["bu_core"])]
    fill_m = [(manual.get((d, b), "")) for d, b in zip(df["disco"], df["bu_core"])]
    blank = df["state"] == ""
    df.loc[blank, "state"] = pd.Series(fill_l, index=df.index)[blank]
    df.loc[blank & (df["state"] != ""), "state_source"] = "learned"
    blank = df["state"] == ""
    df.loc[blank, "state"] = pd.Series(fill_m, index=df.index)[blank]
    df.loc[blank & (df["state"] != ""), "state_source"] = "manual"
    df.loc[df["state"] == "", ["state", "state_source"]] = ["UNKNOWN", "unknown"]

    # Exact repeats inside one order (same DisCo, month, business unit, feeder, band, cap) are printing
    # duplicates in NERC's PDF: drop them and count them.
    before = len(df)
    df = df.drop_duplicates(["disco", "order_month", "bu_core", "feeder_raw", "service_band", "cap_kwh"]).copy()
    df.attrs["exact_duplicates_dropped"] = before - len(df)

    # Feeder identity. Default: DisCo + stable feeder name (kV tags, FEEDER, case removed), which links
    # renamed feeders across years. Where that name collides with a different row in the same month,
    # the feeder is keyed on its full printed name + business unit + its position among same-named
    # rows in the order (NERC lists some codes twice with different caps every month, e.g. AT5_FDR 8_M2_3A).
    df["feeder_core"] = df["feeder_raw"].map(feeder_core)
    df["raw_key"] = df["feeder_raw"].map(norm_key)
    clash = df.groupby(["disco", "order_month", "feeder_core"])["feeder_core"].transform("size") > 1
    clash_keys = set(zip(df.loc[clash, "disco"], df.loc[clash, "feeder_core"]))
    df["occ"] = df.groupby(["disco", "order_month", "bu_core", "raw_key"]).cumcount()
    df["feeder_key"] = [
        (f"{r}|{b}|{o}" if (d, c) in clash_keys else c)
        for d, c, r, b, o in zip(df["disco"], df["feeder_core"], df["raw_key"], df["bu_core"], df["occ"])
    ]
    df["feeder_id"] = [hashlib.sha1(f"{d}|{k}".encode()).hexdigest()[:12]
                       for d, k in zip(df["disco"], df["feeder_key"])]
    df = reconcile_ocr(df)
    df = df.rename(columns={"service_band": "band"})
    df["band_rank"] = df["band"].map(BAND_RANK)
    return df


def reconcile_ocr(df: pd.DataFrame) -> pd.DataFrame:
    """Link OCR rows whose name has a small misread to the same feeder in the text-extracted months.

    For each OCR row with a feeder_id never seen in text months, look for the closest text-month feeder
    in the same DisCo (and same state when known) by name similarity; adopt its id when similarity is at
    least 0.88 and the match is unique. Every adopted link is marked id_link='fuzzy_ocr'.
    """
    import difflib
    df["id_link"] = "exact"
    if "extraction_method" not in df.columns:
        return df
    text = df[df["extraction_method"] != "ocr"]
    canon = text.drop_duplicates("feeder_id")[["disco", "state", "raw_key", "feeder_id"]]
    known = set(canon["feeder_id"])
    pools = {d: g for d, g in canon.groupby("disco")}
    ocr_new = df[(df["extraction_method"] == "ocr") & ~df["feeder_id"].isin(known)]
    remap: dict[tuple, str] = {}
    for (d, st, rk), _ in ocr_new.groupby(["disco", "state", "raw_key"]):
        pool = pools.get(d)
        if pool is None:
            continue
        cand = pool[pool["state"] == st] if st not in ("", "UNKNOWN") else pool
        if cand.empty:
            cand = pool
        names = cand["raw_key"].tolist()
        best = difflib.get_close_matches(rk, names, n=2, cutoff=0.88)
        if not best:
            continue
        if len(best) == 2 and difflib.SequenceMatcher(None, rk, best[1]).ratio() == difflib.SequenceMatcher(None, rk, best[0]).ratio():
            continue  # ambiguous
        remap[(d, st, rk)] = cand.loc[cand["raw_key"] == best[0], "feeder_id"].iloc[0]
    if remap:
        keys = list(zip(df["disco"], df["state"], df["raw_key"]))
        mask = (df["extraction_method"] == "ocr") & ~df["feeder_id"].isin(known)
        new_ids = [remap.get(k) if m else None for k, m in zip(keys, mask)]
        hit = pd.Series([x is not None for x in new_ids], index=df.index)
        df.loc[hit, "feeder_id"] = [x for x in new_ids if x is not None]
        df.loc[hit, "id_link"] = "fuzzy_ocr"
        # two OCR rows can now point to one feeder in the same month; keep the first, flag the rest
        dup = df.duplicated(["feeder_id", "order_month"], keep="first") & hit
        if dup.any():
            df.loc[dup, "feeder_id"] = df.loc[dup, "feeder_id"] + "_ocr"
            df.loc[dup, "id_link"] = "fuzzy_ocr_conflict"
    df.attrs["id_link_counts"] = df["id_link"].value_counts().to_dict()
    return df


def write(df: pd.DataFrame, rel: str) -> None:
    p = OUT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(p, index=False)


def band_shares(g: pd.DataFrame) -> pd.Series:
    n = len(g)
    out = {"feeders": n}
    for b in BANDS:
        c = int((g["band"] == b).sum())
        out[f"band_{b}"] = c
        out[f"share_{b}_pct"] = round(100 * c / n, 1) if n else 0.0
    out["median_cap_kwh"] = float(g["cap_kwh"].median())
    for b in BANDS:
        s = g.loc[g["band"] == b, "cap_kwh"]
        out[f"median_cap_{b}"] = float(s.median()) if len(s) else None
    return pd.Series(out)


def main() -> None:
    df = load()
    F: dict = {}  # findings
    months = sorted(df["order_month"].unique())
    latest = months[-1]
    F["months_covered"] = len(months)
    F["first_month"], F["latest_month"] = months[0], latest
    F["rows"] = int(len(df))
    F["pdf_files"] = int(df["source_file"].nunique())
    F["distinct_feeders"] = int(df["feeder_id"].nunique())
    F["exact_duplicates_dropped"] = int(df.attrs.get("exact_duplicates_dropped", 0))
    F["id_link_counts"] = {k: int(v) for k, v in df["id_link"].value_counts().items()}
    F["state_source_rows"] = df["state_source"].value_counts().to_dict()
    unk = (df[df["state_source"] == "unknown"].groupby(["disco", "bu_core"]).size()
           .sort_values(ascending=False).reset_index(name="rows"))
    write(unk, "qa/unmapped_business_units.csv")

    # ---------- duplicates within a month (same feeder listed twice) ----------
    dup = df.duplicated(["feeder_id", "order_month"], keep=False)
    F["duplicate_feeder_month_rows"] = int(dup.sum())
    dfu = df.sort_values("cap_kwh", ascending=False).drop_duplicates(["feeder_id", "order_month"])

    # ---------- clean tables ----------
    caps_long = dfu[["feeder_id", "disco", "disco_name", "state", "order_month", "consumption_month",
                     "band", "cap_kwh", "state_source", "extraction_method", "id_link",
                     "source_file", "source_page"]].sort_values(["feeder_id", "order_month"])
    write(caps_long, "clean/caps_long.csv")
    try:
        caps_long.to_parquet(OUT / "clean" / "caps_long.parquet", index=False)
    except Exception as e:  # noqa: BLE001  pyarrow optional
        print("parquet skipped:", e)

    g = dfu.sort_values("order_month").groupby("feeder_id")
    feeders = g.agg(
        disco=("disco", "last"), disco_name=("disco_name", "last"), state=("state", "last"),
        business_unit=("business_unit", "last"), voltage_kv=("voltage_kv", "last"),
        injection_substation=("injection_substation", "last"), feeder_name=("feeder_name", "last"),
        feeder_raw=("feeder_raw", "last"), first_seen=("order_month", "first"), last_seen=("order_month", "last"),
        months_listed=("order_month", "nunique"), latest_band=("band", "last"), latest_cap_kwh=("cap_kwh", "last"),
        best_band_ever=("band_rank", "min"), worst_band_ever=("band_rank", "max"),
        band_changes=("band", lambda s: int((s != s.shift()).sum() - 1)),
    ).reset_index()
    feeders["best_band_ever"] = feeders["best_band_ever"].map(lambda r: BANDS[int(r)])
    feeders["worst_band_ever"] = feeders["worst_band_ever"].map(lambda r: BANDS[int(r)])
    write(feeders.sort_values(["disco", "state", "feeder_raw"]), "clean/feeders.csv")

    wide = dfu.pivot_table(index="feeder_id", columns="order_month", values="band", aggfunc="first")
    wide = feeders.set_index("feeder_id")[["disco", "state", "feeder_raw"]].join(wide).reset_index()
    write(wide.sort_values(["disco", "state", "feeder_raw"]), "clean/band_history_wide.csv")

    # ---------- coverage ----------
    cov = dfu.groupby("order_month").agg(pdfs=("source_file", "nunique"), discos=("disco", "nunique"),
                                         states=("state", "nunique"), feeders=("feeder_id", "nunique")).reset_index()
    write(cov, "summary/coverage_by_month.csv")
    F["months_with_data"] = cov["order_month"].tolist()

    # ---------- jurisdiction: when each state leaves NERC's caps ----------
    st = dfu.groupby("state").agg(first_month=("order_month", "min"), last_month=("order_month", "max"),
                                  months_present=("order_month", "nunique"), discos=("disco", lambda s: ",".join(sorted(set(s)))),
                                  feeders_peak=("feeder_id", "nunique")).reset_index()
    st["still_in_nerc_caps"] = st["last_month"] == latest
    regp = ROOT / "data" / "reference" / "state_regulators.csv"
    if regp.exists():
        reg = pd.read_csv(regp, dtype=str).fillna("")
        reg["state"] = reg["state"].str.upper()
        reg = reg[["state", "regulator_acronym", "nerc_order_no", "order_date", "effective_date", "status"]].rename(
            columns={"status": "transfer_status", "effective_date": "transfer_deadline"})
        st = st.merge(reg, on="state", how="left").fillna("")
        st["transferred"] = st["transfer_status"].isin(["completed", "in transition"])
        st["published_after_transfer_deadline"] = st.apply(
            lambda r: bool(r["transferred"] and r["transfer_deadline"][:7] and r["last_month"] > r["transfer_deadline"][:7]), axis=1)
        F["transferred_but_still_published"] = st.loc[st["transferred"] & st["still_in_nerc_caps"],
                                                      ["state", "regulator_acronym", "transfer_deadline"]].to_dict("records")
        F["transferred_and_dropped"] = st.loc[st["transferred"] & ~st["still_in_nerc_caps"],
                                              ["state", "regulator_acronym", "transfer_deadline", "last_month"]].to_dict("records")
    st = st.sort_values(["still_in_nerc_caps", "last_month"])
    write(st, "summary/state_jurisdiction.csv")
    gone = st[~st["still_in_nerc_caps"] & (st["state"] != "UNKNOWN")].copy()
    F["states_left"] = gone[["state", "last_month", "discos"]].to_dict("records")
    F["states_remaining"] = sorted(st.loc[st["still_in_nerc_caps"], "state"].tolist())
    stayers = set(F["states_remaining"])

    # ---------- per DisCo / state per month ----------
    dm = dfu.groupby(["disco", "disco_name", "order_month"]).apply(band_shares, include_groups=False).reset_index()
    write(dm, "summary/disco_month.csv")
    sm = dfu.groupby(["state", "order_month"]).apply(band_shares, include_groups=False).reset_index()
    write(sm, "summary/state_month.csv")

    # ---------- transitions ----------
    t = dfu.sort_values(["feeder_id", "order_month"]).copy()
    t["prev_band"] = t.groupby("feeder_id")["band"].shift()
    t["prev_month"] = t.groupby("feeder_id")["order_month"].shift()
    t = t[t["prev_band"].notna() & (t["prev_band"] != t["band"])].copy()
    t["direction"] = (t["band"].map(BAND_RANK) < t["prev_band"].map(BAND_RANK)).map({True: "upgrade", False: "downgrade"})
    t["steps"] = (t["prev_band"].map(BAND_RANK) - t["band"].map(BAND_RANK)).abs()
    trans = t[["feeder_id", "disco", "disco_name", "state", "feeder_raw", "prev_month", "order_month",
               "prev_band", "band", "direction", "steps"]].rename(columns={"band": "new_band", "order_month": "month"})
    write(trans, "summary/band_transitions.csv")
    F["transitions_total"] = int(len(trans))
    F["upgrades"] = int((trans["direction"] == "upgrade").sum())
    F["downgrades"] = int((trans["direction"] == "downgrade").sum())
    by_m = trans.groupby(["month", "direction"]).size().unstack(fill_value=0)
    write(by_m.reset_index(), "summary/transitions_by_month.csv")
    F["top_transition_months"] = by_m.sum(axis=1).sort_values(ascending=False).head(5).to_dict()
    a_moves = trans[(trans["prev_band"] == "A") | (trans["new_band"] == "A")]
    F["into_A"] = int((a_moves["new_band"] == "A").sum())
    F["out_of_A"] = int((a_moves["prev_band"] == "A").sum())

    # ---------- latest snapshot rankings ----------
    L = dfu[dfu["order_month"] == latest]
    r_disco = L.groupby(["disco", "disco_name"]).apply(band_shares, include_groups=False).reset_index()
    r_disco = r_disco.sort_values("share_A_pct", ascending=False)
    write(r_disco, "rankings/discos_by_band_A_share_latest.csv")
    r_state = L.groupby("state").apply(band_shares, include_groups=False).reset_index()
    r_state = r_state.sort_values(["share_A_pct", "feeders"], ascending=False)
    write(r_state, "rankings/states_by_band_A_share_latest.csv")
    F["latest_feeders"] = int(L["feeder_id"].nunique())
    F["latest_band_counts"] = L["band"].value_counts().reindex(BANDS, fill_value=0).to_dict()
    F["latest_discos"] = r_disco[["disco_name", "feeders", "share_A_pct", "share_E_pct", "median_cap_kwh"]].to_dict("records")
    F["latest_states_top"] = r_state.head(10)[["state", "feeders", "share_A_pct"]].to_dict("records")
    F["latest_states_bottom"] = r_state[r_state["feeders"] >= 10].tail(10)[["state", "feeders", "share_A_pct"]].to_dict("records")

    cols = ["disco_name", "state", "business_unit", "feeder_raw", "band", "cap_kwh"]
    write(L.sort_values("cap_kwh", ascending=False).head(50)[cols], "rankings/highest_caps_latest.csv")
    write(L.sort_values("cap_kwh").head(50)[cols], "rankings/lowest_caps_latest.csv")

    cap_band = L.groupby("band")["cap_kwh"].describe(percentiles=[.1, .5, .9])[["count", "10%", "50%", "90%", "max"]]
    write(cap_band.reset_index(), "rankings/cap_distribution_by_band_latest.csv")
    F["latest_cap_by_band"] = cap_band.round(0).to_dict("index")

    # anomaly: lower band with cap above the Band A median in the same DisCo
    a_med = L[L["band"] == "A"].groupby("disco")["cap_kwh"].median()
    an = L[(L["band"].isin(["D", "E"])) & (L["cap_kwh"] > L["disco"].map(a_med))].copy()
    an["disco_band_A_median"] = an["disco"].map(a_med)
    write(an.sort_values("cap_kwh", ascending=False)[cols + ["disco_band_A_median"]], "rankings/anomaly_low_band_high_cap_latest.csv")
    F["anomaly_low_band_high_cap"] = int(len(an))

    vol = feeders[feeders["months_listed"] >= 6].sort_values(["band_changes", "months_listed"], ascending=False)
    write(vol.head(100)[["disco_name", "state", "feeder_raw", "months_listed", "band_changes", "best_band_ever",
                         "worst_band_ever", "latest_band"]], "rankings/most_volatile_feeders.csv")

    dg = trans.groupby("disco_name")["direction"].value_counts().unstack(fill_value=0)
    dg["net_upgrades"] = dg.get("upgrade", 0) - dg.get("downgrade", 0)
    write(dg.sort_values("downgrade", ascending=False).reset_index(), "rankings/discos_by_downgrades.csv")
    F["discos_by_downgrades"] = dg.sort_values("downgrade", ascending=False).reset_index().to_dict("records")

    # ---------- like-for-like trend (states still in NERC caps, months with full coverage) ----------
    full_months = cov[cov["discos"] >= 10]["order_month"].tolist()
    LL = dfu[dfu["state"].isin(stayers) & dfu["order_month"].isin(full_months)]
    trend = LL.groupby("order_month").apply(band_shares, include_groups=False).reset_index()
    write(trend, "summary/like_for_like_trend.csv")
    if len(trend):
        F["like_for_like"] = {
            "states": sorted(stayers), "first": trend.iloc[0][["order_month", "feeders", "share_A_pct", "median_cap_kwh"]].to_dict(),
            "latest": trend.iloc[-1][["order_month", "feeders", "share_A_pct", "median_cap_kwh"]].to_dict(),
        }

    # ---------- charts ----------
    ch = ROOT / "docs" / "charts"
    ch.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"figure.dpi": 130, "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

    # 1 coverage
    fig, ax = plt.subplots(figsize=(9, 3.2))
    ax.bar(cov["order_month"], cov["feeders"], color="#4c72b0")
    ax.set_title("Feeders listed in NERC monthly cap orders")
    ax.set_ylabel("feeders")
    ax.tick_params(axis="x", rotation=90, labelsize=6)
    fig.tight_layout(); fig.savefig(ch / "01_coverage.png"); plt.close(fig)

    # 2 band mix over time, like for like
    if len(trend):
        fig, ax = plt.subplots(figsize=(9, 3.6))
        bottom = None
        for b in BANDS:
            vals = trend[f"share_{b}_pct"].values
            ax.bar(trend["order_month"], vals, bottom=bottom, color=BAND_COLORS[b], label=f"Band {b}")
            bottom = vals if bottom is None else bottom + vals
        ax.set_title("Band mix over time, states still in NERC's cap orders in the latest month (like for like)")
        ax.set_ylabel("% of feeders"); ax.legend(ncol=5, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.32))
        ax.tick_params(axis="x", rotation=90, labelsize=6)
        fig.tight_layout(); fig.savefig(ch / "02_band_mix_like_for_like.png"); plt.close(fig)

    # 3 latest DisCo ranking by Band A share
    rd = r_disco.sort_values("share_A_pct")
    fig, ax = plt.subplots(figsize=(7, 4))
    left = None
    for b in BANDS:
        vals = rd[f"share_{b}_pct"].values
        ax.barh(rd["disco_name"], vals, left=left, color=BAND_COLORS[b], label=b)
        left = vals if left is None else left + vals
    ax.set_title(f"Service band mix by DisCo, {latest} order")
    ax.set_xlabel("% of feeders"); ax.legend(ncol=5, fontsize=7, title="band", loc="upper center", bbox_to_anchor=(0.5, -0.14))
    fig.tight_layout(); fig.savefig(ch / "03_discos_band_mix_latest.png"); plt.close(fig)

    # 4 cap by band
    fig, ax = plt.subplots(figsize=(6, 3.6))
    data = [L.loc[L["band"] == b, "cap_kwh"].values for b in BANDS]
    ax.boxplot(data, tick_labels=BANDS, showfliers=False, patch_artist=True,
               boxprops=dict(facecolor="#dddddd"))
    ax.set_title(f"Monthly cap per unmetered customer by band, {latest}")
    ax.set_xlabel("service band"); ax.set_ylabel("kWh per month")
    fig.tight_layout(); fig.savefig(ch / "04_cap_by_band_latest.png"); plt.close(fig)

    # 5 transitions per month
    if len(by_m):
        fig, ax = plt.subplots(figsize=(9, 3.2))
        ax.bar(by_m.index, by_m.get("upgrade", 0), color="#1b7837", label="upgrade")
        ax.bar(by_m.index, -by_m.get("downgrade", 0), color="#b35806", label="downgrade")
        ax.axhline(0, color="black", lw=0.6)
        ax.set_title("Feeder band changes per month (up = upgrade, down = downgrade)")
        ax.legend(fontsize=7); ax.tick_params(axis="x", rotation=90, labelsize=6)
        fig.tight_layout(); fig.savefig(ch / "05_band_changes_by_month.png"); plt.close(fig)

    # 6 state presence timeline
    pres = dfu.groupby(["state", "order_month"]).size().unstack(fill_value=0) > 0
    pres = pres.loc[st.sort_values("last_month")["state"]]
    fig, ax = plt.subplots(figsize=(9, max(3, 0.18 * len(pres))))
    ax.imshow(pres.values, aspect="auto", cmap="Greens", interpolation="nearest")
    ax.set_yticks(range(len(pres))); ax.set_yticklabels(pres.index, fontsize=6)
    ax.set_xticks(range(len(pres.columns))); ax.set_xticklabels(pres.columns, rotation=90, fontsize=5)
    ax.set_title("Which states appear in NERC cap orders each month (green = present)")
    fig.tight_layout(); fig.savefig(ch / "06_state_presence.png"); plt.close(fig)

    # 7 states ranked by Band A share, latest month (states with at least 10 feeders)
    rs = r_state[(r_state["feeders"] >= 10) & (r_state["state"] != "UNKNOWN")].sort_values("share_A_pct")
    fig, ax = plt.subplots(figsize=(7, max(3, 0.24 * len(rs))))
    ax.barh(rs["state"], rs["share_A_pct"], color=BAND_COLORS["A"])
    for y, (v, n) in enumerate(zip(rs["share_A_pct"], rs["feeders"])):
        ax.text(v + 0.8, y, f"{v:.0f}%  ({int(n)} feeders)", va="center", fontsize=7)
    ax.set_xlim(0, max(100, rs["share_A_pct"].max() + 25))
    ax.set_title(f"Share of feeders in Band A by state, {latest} order (highest at top)")
    ax.set_xlabel("% of the state's listed feeders in Band A")
    fig.tight_layout(); fig.savefig(ch / "07_states_band_A_ranking.png"); plt.close(fig)

    # 8 median cap per band over time (like for like)
    if len(trend):
        fig, ax = plt.subplots(figsize=(9, 3.4))
        for b in BANDS:
            ax.plot(trend["order_month"], trend[f"median_cap_{b}"], marker="o", ms=2, lw=1.4, color=BAND_COLORS[b], label=f"Band {b}")
        ax.set_title("Median monthly cap per unmetered customer, by band (kWh)")
        ax.set_ylabel("kWh per month"); ax.legend(ncol=5, fontsize=7)
        ax.tick_params(axis="x", rotation=90, labelsize=6)
        fig.tight_layout(); fig.savefig(ch / "08_median_cap_by_band_over_time.png"); plt.close(fig)

    (OUT / "findings.json").write_text(json.dumps(F, indent=1, default=str))
    print(json.dumps({k: F[k] for k in ("months_covered", "first_month", "latest_month", "rows", "pdf_files",
                                         "distinct_feeders", "latest_feeders", "transitions_total", "upgrades",
                                         "downgrades")}, indent=1))


if __name__ == "__main__":
    main()
