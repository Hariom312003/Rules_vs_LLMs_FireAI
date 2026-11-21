"""Load raw 311 parquet files and derive a CLEAN reference set.

`load_raw()`   -> exactly what the API gave us (all strings) -- used by profiling.
`load_clean()` -> typed rows that pass every basic validity check; the
                  injector corrupts these and the detectors are scored on them.
Note: the clean filter reuses simple rules (ZIP<->borough, bbox, dates), so
"false alarms on clean batches" is measured against this definition of clean.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from ..schema import (CORE_COLUMNS, ISO_FMT, LAT_RANGE, LON_RANGE, STATUSES_CLOSED,
                      zip_borough)

RAW_DIR = Path(__file__).parent / "raw"

_PII = re.compile(r"(?:\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b)|(?:[\w.+-]+@[\w-]+\.[\w.-]+)")


def load_raw(files: int | None = None) -> pd.DataFrame:
    paths = sorted(RAW_DIR.glob("311_*.parquet"))
    if not paths:
        raise FileNotFoundError(
            "No raw data. Run: python -m project_b.data.download_311 --months 12 --limit 20000")
    if files:
        paths = paths[:files]
    return pd.concat([pd.read_parquet(p) for p in paths], ignore_index=True)


def _typed(raw: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in CORE_COLUMNS if c not in raw.columns]
    df = raw.reindex(columns=CORE_COLUMNS).copy()
    for c in missing:
        df[c] = pd.NA
    for c in ("latitude", "longitude"):
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
    for c in df.columns:
        if c not in ("latitude", "longitude"):
            df[c] = df[c].astype("object").where(df[c].notna(), None)
    return df


def clean_mask(df: pd.DataFrame) -> pd.Series:
    """Rows with no detectable basic problem (strict on purpose)."""
    ok = pd.Series(True, index=df.index)
    cd = pd.to_datetime(df["created_date"], format=ISO_FMT, errors="coerce")
    cl = pd.to_datetime(df["closed_date"], format=ISO_FMT, errors="coerce")
    ok &= cd.notna()
    ok &= ~(cl.notna() & (cl < cd))
    ok &= df["closed_date"].isna() | cl.notna()
    ok &= df["latitude"].between(*LAT_RANGE) & df["longitude"].between(*LON_RANGE)
    zb = df["incident_zip"].map(zip_borough)
    ok &= zb.notna() & (zb == df["borough"])
    ok &= df["agency"].notna() & df["complaint_type"].notna() & df["descriptor"].notna()
    ok &= df["status"].notna()
    for c in ("descriptor", "resolution_description"):
        ok &= ~df[c].fillna("").astype(str).str.contains(_PII)
    ok &= ~df.duplicated(subset=["unique_key"], keep="first")
    return ok


def load_clean(raw: pd.DataFrame | None = None, max_rows: int | None = None,
               seed: int = 0) -> pd.DataFrame:
    raw = load_raw() if raw is None else raw
    df = _typed(raw)
    df = df[clean_mask(df)].reset_index(drop=True)
    if max_rows and len(df) > max_rows:
        df = df.sample(max_rows, random_state=seed).reset_index(drop=True)
    return df


def make_batches(df: pd.DataFrame, batch_size: int, seed: int = 0) -> list[pd.DataFrame]:
    """Shuffle then split into equal batches (index reset per batch)."""
    df = df.sample(frac=1.0, random_state=seed).reset_index(drop=True)
    return [df.iloc[i:i + batch_size].reset_index(drop=True)
            for i in range(0, len(df) - batch_size + 1, batch_size)]
