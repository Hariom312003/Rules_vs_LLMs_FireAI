"""Task 1: profile the RAW 2023 data and document REAL quality problems.

    python -m project_b.profiling.profile

Works on the untouched string data (no coercion) and records, per issue:
count, share of rows, and up to 3 example rows. Output:
  project_b/results/profile.json
  the section between <!-- PROFILE:START --> / <!-- PROFILE:END --> in RESULTS_B.md
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.loader import load_raw
from ..schema import ISO_REGEX, LAT_RANGE, LON_RANGE, STATUSES_CLOSED, zip_borough

RESULTS = Path(__file__).resolve().parents[1] / "results"
ROOT = Path(__file__).resolve().parents[2]
PHONE = re.compile(r"(?<!\d)(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
OPEN_WORDS = re.compile(r"\b(?:still open|pending|not yet|unresolved|no action)\b", re.I)
CLOSED_WORDS = re.compile(r"\b(?:has been closed|was closed|closed (?:this|the)|resolved|corrected)\b", re.I)


def _examples(df: pd.DataFrame, mask: pd.Series, cols: list[str], n: int = 3) -> list[dict]:
    cols = [c for c in dict.fromkeys(["unique_key"] + cols) if c in df.columns]
    return df.loc[mask, cols].head(n).where(lambda x: x.notna(), None).to_dict("records")


def main() -> None:
    df = load_raw()
    n = len(df)
    num = lambda c: pd.to_numeric(df.get(c), errors="coerce")
    issues: list[dict] = []

    def add(name: str, mask: pd.Series, cols: list[str], note: str = "") -> None:
        mask = mask.fillna(False)
        issues.append({"issue": name, "count": int(mask.sum()), "pct": round(100 * mask.mean(), 3),
                       "note": note, "examples": _examples(df, mask, cols)})

    cd = pd.to_datetime(df["created_date"], errors="coerce")
    cl = pd.to_datetime(df["closed_date"], errors="coerce") if "closed_date" in df else pd.Series(pd.NaT, index=df.index)

    # --- dates -------------------------------------------------------------
    add("created_date not ISO format", df["created_date"].notna() & ~df["created_date"].fillna("").str.match(ISO_REGEX),
        ["created_date"])
    add("created_date outside calendar 2023", cd.notna() & (cd.dt.year != 2023), ["created_date"])
    add("closed_date earlier than created_date", cl.notna() & cd.notna() & (cl < cd), ["created_date", "closed_date"])
    add("closed_date in the future / after data pull", cl.notna() & (cl > pd.Timestamp.now()), ["closed_date"])
    add("status Closed but closed_date missing", df["status"].isin(STATUSES_CLOSED) & df["closed_date"].isna(),
        ["status", "closed_date"])
    add("status not Closed but closed_date present", ~df["status"].isin(STATUSES_CLOSED) & df["closed_date"].notna(),
        ["status", "closed_date"])
    dur = (cl - cd).dt.total_seconds()
    add("closed within 1 minute of created (suspicious)", dur.between(0, 60), ["created_date", "closed_date", "agency"])
    add("open > 365 days after created", cd.notna() & df["closed_date"].isna() & (cd < pd.Timestamp("2023-01-01")),
        ["created_date"], "created before 2023-01-01")

    # --- geography ---------------------------------------------------------
    lat, lon = num("latitude"), num("longitude")
    add("latitude/longitude missing", lat.isna() | lon.isna(), ["latitude", "longitude", "agency"])
    add("lat/lon exactly 0", (lat == 0) | (lon == 0), ["latitude", "longitude"])
    out_box = lat.notna() & lon.notna() & ~((lat.between(*LAT_RANGE)) & lon.between(*LON_RANGE))
    add("lat/lon outside NYC bounding box", out_box, ["latitude", "longitude", "borough"])
    add("lat/lon look swapped", lat.between(*LON_RANGE) & lon.between(*LAT_RANGE), ["latitude", "longitude"])
    z = df["incident_zip"]
    add("incident_zip missing", z.isna(), ["incident_zip", "borough"])
    add("incident_zip malformed (not 5 digits)", z.notna() & ~z.fillna("").str.fullmatch(r"\d{5}"), ["incident_zip"])
    implied = z.map(zip_borough)
    add("incident_zip not in NYC ranges", z.notna() & z.fillna("").str.fullmatch(r"\d{5}") & implied.isna(),
        ["incident_zip", "borough"])
    add("incident_zip inconsistent with borough", implied.notna() & df["borough"].notna() & (implied != df["borough"]),
        ["incident_zip", "borough"])
    add("borough 'Unspecified' or missing", df["borough"].isna() | (df["borough"] == "Unspecified"), ["borough", "agency"])

    # --- categories & text ------------------------------------------------
    for c in ("complaint_type", "agency", "borough", "status", "descriptor"):
        if c not in df:
            continue
        v = df[c].dropna()
        norm = v.str.strip().str.lower()
        variants = v.groupby(norm).nunique()
        bad = norm.map(variants.to_dict()) > 1
        add(f"{c}: case/whitespace variants of the same value", bad.reindex(df.index, fill_value=False), [c],
            f"{int((variants > 1).sum())} values affected")
    add("complaint_type missing", df["complaint_type"].isna(), ["complaint_type"])
    add("descriptor missing", df["descriptor"].isna(), ["complaint_type", "descriptor", "agency"])
    add("resolution_description missing on Closed", df["status"].isin(STATUSES_CLOSED) & df["resolution_description"].isna(),
        ["status", "agency"])
    rd = df["resolution_description"].fillna("")
    add("status Closed but text says open/pending", df["status"].isin(STATUSES_CLOSED) & rd.str.contains(OPEN_WORDS),
        ["status", "resolution_description"])
    add("status open but text says closed/resolved", ~df["status"].isin(STATUSES_CLOSED) & rd.str.contains(CLOSED_WORDS),
        ["status", "resolution_description"])
    for c in ("descriptor", "resolution_description"):
        s = df[c].fillna("")
        add(f"{c}: phone number in free text", s.str.contains(PHONE), [c])
        add(f"{c}: email in free text", s.str.contains(EMAIL), [c])

    # --- duplicates --------------------------------------------------------
    add("duplicate unique_key", df.duplicated("unique_key", keep="first"), ["unique_key"])
    add("exact duplicate rows", df.drop(columns=["unique_key"], errors="ignore").duplicated(keep="first"),
        ["agency", "complaint_type", "created_date"], "ignoring unique_key")
    key = ["agency", "complaint_type", "incident_address", "incident_zip"]
    if all(k in df for k in key):
        w = df.assign(_t=cd).dropna(subset=["_t", "incident_address"]).sort_values("_t")
        gap = w.groupby(key)["_t"].diff().dt.total_seconds()
        near = pd.Series(False, index=df.index)
        near.loc[gap[(gap >= 0) & (gap <= 300)].index] = True
        add("near-duplicates: same agency/type/address within 5 min", near,
            ["agency", "complaint_type", "incident_address", "created_date"])

    nulls = (df.isna().mean() * 100).round(2).sort_values(ascending=False)
    by_agency = {}
    if "agency" in df:
        top = df["agency"].value_counts().head(8).index
        by_agency = {a: (df[df["agency"] == a].isna().mean() * 100).round(1)
                     .sort_values(ascending=False).head(4).to_dict() for a in top}
    out = {"rows": n, "columns": list(df.columns), "null_pct": nulls.to_dict(),
           "top_null_cols_by_agency": by_agency, "issues": issues,
           "note": "Data is a per-month capped sample unless the full download was run."}

    RESULTS.mkdir(exist_ok=True)
    (RESULTS / "profile.json").write_text(json.dumps(out, indent=2, default=str), encoding="utf-8")

    found = [i for i in issues if i["count"] > 0]
    md = [f"Profiled **{n:,}** raw 2023 rows, {len(df.columns)} columns.", "",
          "| Issue | Count | % of rows | Example (unique_key: values) |", "|---|---|---|---|"]
    for i in sorted(found, key=lambda i: -i["count"]):
        ex = (json.dumps(i["examples"][0], default=str, ensure_ascii=False)[:110]
              if i["examples"] else "")
        md.append(f"| {i['issue']} | {i['count']:,} | {i['pct']} | `{ex}` |")
    md += ["", f"Checked but clean (0 hits): {', '.join(i['issue'] for i in issues if i['count'] == 0) or 'none'}."]
    _inject("PROFILE", "\n".join(md))
    print(f"profiled {n:,} rows; {len(found)} issue types with hits -> {RESULTS / 'profile.json'}")


def _inject(tag: str, body: str) -> None:
    p = ROOT / "RESULTS_B.md"
    t = p.read_text(encoding="utf-8")
    new = f"<!-- {tag}:START -->\n{body}\n<!-- {tag}:END -->"
    if f"<!-- {tag}:START -->" in t:
        t = re.sub(rf"<!-- {tag}:START -->.*<!-- {tag}:END -->", lambda _: new, t, flags=re.S)
        p.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main()
