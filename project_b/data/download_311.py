"""Download NYC 311 requests created in calendar year 2023 (Socrata API).

    python -m project_b.data.download_311                 # full year, ~3M rows
    python -m project_b.data.download_311 --months 1 --limit 20000   # quick sample

Writes one parquet per month to project_b/data/raw/311_2023_MM.parquet.
Everything is stored as strings on purpose: the raw data's type/format
problems are exactly what Task 1 must find, so do not coerce here.
Dataset: "311 Service Requests from 2010 to Present" (id erm2-nwe9).
"""
from __future__ import annotations

import argparse
import calendar
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

URL = "https://data.cityofnewyork.us/resource/erm2-nwe9.json"
RAW_DIR = Path(__file__).parent / "raw"
PAGE = 50_000


def fetch_month(year: int, month: int, limit: int | None, session: requests.Session) -> pd.DataFrame:
    last = calendar.monthrange(year, month)[1]
    where = (
        f"created_date >= '{year}-{month:02d}-01T00:00:00' "
        f"AND created_date <= '{year}-{month:02d}-{last}T23:59:59.999'"
    )
    headers = {}
    if os.getenv("SOCRATA_APP_TOKEN"):
        headers["X-App-Token"] = os.environ["SOCRATA_APP_TOKEN"]

    rows: list[dict] = []
    offset = 0
    while True:
        n = PAGE if limit is None else min(PAGE, limit - len(rows))
        if n <= 0:
            break
        params = {"$where": where, "$order": ":id", "$limit": n, "$offset": offset}
        for attempt in range(6):
            try:
                r = session.get(URL, params=params, headers=headers, timeout=300)
                if r.status_code == 200:
                    break
            except requests.exceptions.RequestException as e:  # timeouts, resets
                print(f"  retry {attempt + 1} after {type(e).__name__}")
            time.sleep(2 ** attempt)
        else:
            raise RuntimeError(f"giving up on {year}-{month:02d} offset {offset}")
        page = r.json()
        rows.extend(page)
        if len(page) < n:
            break
        offset += n
    return pd.DataFrame(rows).astype("string")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2023)
    ap.add_argument("--months", type=int, default=12, help="first N months only")
    ap.add_argument("--limit", type=int, default=None, help="max rows per month (sampling)")
    args = ap.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    with requests.Session() as s:
        for m in range(1, args.months + 1):
            out = RAW_DIR / f"311_{args.year}_{m:02d}.parquet"
            if out.exists():
                print(f"skip {out.name} (exists)")
                continue
            df = fetch_month(args.year, m, args.limit, s)
            df.to_parquet(out, index=False)
            print(f"{out.name}: {len(df):,} rows, {len(df.columns)} cols")


if __name__ == "__main__":
    main()
