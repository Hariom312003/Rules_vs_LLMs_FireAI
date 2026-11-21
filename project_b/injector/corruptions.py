"""Task 2: the 12 corruption types, injected at a controlled rate.

`inject(clean_batch, key, rate, seed)` returns `(corrupted_df, Truth)`.

rate semantics
  row-level problems   fraction of rows affected (duplicates: fraction added)
  a, b (schema)        fraction of columns affected (at least one)
  c  (date switch)     fraction of rows, taken from the END of the batch
                       (format switches "partway through")
  g  (null spike)      fraction of the chosen agency's rows nulled

`Truth.row_mask` is aligned to the returned frame's index (True = corrupted
row) so detection rate is exact. Schema-level problems have row_mask=None and
list the affected columns. Everything is seeded: same seed -> same output.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np
import pandas as pd

from ..schema import ALT_FMT, CORE_COLUMNS, FLOAT_COLS, ISO_FMT

BOROUGH_ZIPS = {
    "MANHATTAN": ["10001", "10011", "10027", "10033"],
    "BRONX": ["10451", "10458", "10467", "10472"],
    "BROOKLYN": ["11201", "11215", "11222", "11230"],
    "QUEENS": ["11101", "11354", "11373", "11432"],
    "STATEN ISLAND": ["10301", "10306", "10312", "10314"],
}


@dataclass
class Truth:
    key: str
    row_mask: pd.Series | None = None  # True where the row is corrupted
    columns: list[str] = field(default_factory=list)
    note: str = ""

    @property
    def n_bad_rows(self) -> int:
        return 0 if self.row_mask is None else int(self.row_mask.sum())


Result = tuple[pd.DataFrame, Truth]
ApplyFn = Callable[[pd.DataFrame, float, np.random.Generator], Result]


@dataclass(frozen=True)
class Corruption:
    key: str
    name: str
    level: str  # "schema" | "batch" | "row"
    apply: ApplyFn


def _pick_rows(df: pd.DataFrame, rate: float, rng: np.random.Generator,
               eligible: pd.Series | None = None) -> np.ndarray:
    idx = np.arange(len(df)) if eligible is None else np.flatnonzero(eligible.to_numpy())
    n = min(len(idx), max(1, int(round(rate * len(df))))) if rate > 0 else 0
    return rng.choice(idx, size=n, replace=False) if n else np.array([], dtype=int)


def _mask(df: pd.DataFrame, rows: np.ndarray) -> pd.Series:
    m = pd.Series(False, index=df.index)
    m.iloc[rows] = True
    return m


def _pick_cols(df: pd.DataFrame, rate: float, rng: np.random.Generator,
               pool: list[str]) -> list[str]:
    pool = [c for c in pool if c in df.columns]
    n = min(len(pool), max(1, int(round(rate * len(df.columns)))))
    return list(rng.choice(pool, size=n, replace=False))


# --- a. renamed or dropped column -------------------------------------------
def c_a(df, rate, rng) -> Result:
    cols = _pick_cols(df, rate, rng, [c for c in CORE_COLUMNS if c != "unique_key"])
    out = df.copy()
    renamed = []
    for i, c in enumerate(cols):
        if i % 2 == 0:  # drop
            out = out.drop(columns=c)
        else:  # rename (typical upstream drift: new casing / name)
            out = out.rename(columns={c: c.upper() if i % 4 == 1 else c + "_v2"})
            renamed.append(c)
    return out, Truth("a", None, cols, "dropped/renamed")


# --- b. column type change ---------------------------------------------------
def c_b(df, rate, rng) -> Result:
    cols = _pick_cols(df, rate, rng, FLOAT_COLS + ["unique_key", "incident_zip"])
    out = df.copy()
    for c in cols:
        if c in FLOAT_COLS:  # numbers arriving as strings
            out[c] = out[c].map(lambda v: None if pd.isna(v) else f"{v:.6f}")
        else:  # identifiers arriving as numbers
            out[c] = pd.to_numeric(out[c], errors="coerce")
    return out, Truth("b", None, cols, "type changed")


# --- c. date format switch partway through the batch ------------------------
def c_c(df, rate, rng) -> Result:
    out = df.copy()
    n = min(len(df), max(1, int(round(rate * len(df)))))
    rows = np.arange(len(df) - n, len(df))
    for c in ("created_date", "closed_date"):
        vals = pd.to_datetime(out[c].iloc[rows], format=ISO_FMT, errors="coerce")
        out.loc[out.index[rows], c] = vals.dt.strftime(ALT_FMT).where(vals.notna(), None)
    return out, Truth("c", _mask(out, rows), ["created_date", "closed_date"],
                      f"MM/DD/YYYY hh:mm:ss AM/PM from row {rows[0]}")


# --- d. latitude / longitude swapped ----------------------------------------
def c_d(df, rate, rng) -> Result:
    out = df.copy()
    rows = _pick_rows(df, rate, rng, df["latitude"].notna() & df["longitude"].notna())
    lat = out["latitude"].to_numpy(copy=True)
    lon = out["longitude"].to_numpy(copy=True)
    lat[rows], lon[rows] = df["longitude"].to_numpy()[rows], df["latitude"].to_numpy()[rows]
    out["latitude"], out["longitude"] = lat, lon
    return out, Truth("d", _mask(out, rows), ["latitude", "longitude"])


# --- e. exact duplicates -----------------------------------------------------
def c_e(df, rate, rng) -> Result:
    src = _pick_rows(df, rate, rng)
    copies = df.iloc[src].copy()
    out = pd.concat([df, copies], ignore_index=True)
    m = pd.Series(False, index=out.index)
    m.iloc[len(df):] = True
    return out, Truth("e", m, list(df.columns), "exact copies appended")


# --- f. near-duplicates ------------------------------------------------------
def _typo(s: str | None, rng: np.random.Generator) -> str | None:
    if not s or len(s) < 3:
        return s
    i = int(rng.integers(1, len(s) - 1))
    mode = int(rng.integers(0, 3))
    if mode == 0:
        return s[:i] + s[i + 1:]  # delete a char
    if mode == 1:
        return s[:i] + s[i] + s[i:]  # double a char
    return s.upper() if s != s.upper() else s.lower()  # case change


def c_f(df, rate, rng) -> Result:
    src = _pick_rows(df, rate, rng, df["created_date"].notna())
    copies = df.iloc[src].copy()
    ts = pd.to_datetime(copies["created_date"], format=ISO_FMT, errors="coerce")
    shift = pd.to_timedelta(rng.integers(1, 120, size=len(copies)), unit="s")
    copies["created_date"] = (ts + shift).dt.strftime(ISO_FMT.replace("%f", "000"))
    # half of them also get a slightly altered text field
    txt_rows = rng.random(len(copies)) < 0.5
    copies.loc[txt_rows, "descriptor"] = [
        _typo(v, rng) for v in copies.loc[txt_rows, "descriptor"]]
    start = int(pd.to_numeric(df["unique_key"], errors="coerce").max() or 0)
    copies["unique_key"] = [str(start + i + 1) for i in range(len(copies))]
    out = pd.concat([df, copies], ignore_index=True)
    m = pd.Series(False, index=out.index)
    m.iloc[len(df):] = True
    return out, Truth("f", m, ["created_date", "descriptor"],
                      "same request, timestamp +1..120s, new key")


# --- g. null spike in one agency's records ----------------------------------
def c_g(df, rate, rng) -> Result:
    out = df.copy()
    top = df["agency"].value_counts()
    agency = str(top.index[int(rng.integers(0, min(3, len(top))))])
    cols = [c for c in ("incident_zip", "borough", "latitude", "longitude", "descriptor")
            if c in out.columns]
    col_set = list(rng.choice(cols, size=min(2, len(cols)), replace=False))
    # rate is the share of that agency's rows hit (not of the whole batch)
    ag_rows = np.flatnonzero((df["agency"] == agency).to_numpy())
    n = max(1, int(round(rate * len(ag_rows)))) if rate > 0 else 0
    rows = (rng.choice(ag_rows, size=min(n, len(ag_rows)), replace=False)
            if n else np.array([], dtype=int))
    for c in col_set:
        out.iloc[rows, out.columns.get_loc(c)] = np.nan if c in FLOAT_COLS else None
    return out, Truth("g", _mask(out, rows), col_set, f"agency={agency}")


# --- h. closed date earlier than created date -------------------------------
def c_h(df, rate, rng) -> Result:
    out = df.copy()
    rows = _pick_rows(df, rate, rng, df["closed_date"].notna() & df["created_date"].notna())
    cr = pd.to_datetime(df["created_date"].iloc[rows], format=ISO_FMT)
    back = pd.to_timedelta(rng.integers(3600, 30 * 86400, size=len(rows)), unit="s")
    out.iloc[rows, out.columns.get_loc("closed_date")] = (
        (cr - back).dt.strftime(ISO_FMT.replace("%f", "000")).to_numpy())
    return out, Truth("h", _mask(out, rows), ["closed_date"])


# --- i. ZIP inconsistent with borough ---------------------------------------
def c_i(df, rate, rng) -> Result:
    out = df.copy()
    rows = _pick_rows(df, rate, rng, df["borough"].notna() & df["incident_zip"].notna())
    col = out.columns.get_loc("incident_zip")
    for r in rows:
        other = [b for b in BOROUGH_ZIPS if b != df["borough"].iloc[r]]
        b = other[int(rng.integers(0, len(other)))]
        zs = BOROUGH_ZIPS[b]
        out.iloc[r, col] = zs[int(rng.integers(0, len(zs)))]
    return out, Truth("i", _mask(out, rows), ["incident_zip"])


# --- j. complaint type inconsistent with descriptor -------------------------
def c_j(df, rate, rng) -> Result:
    out = df.copy()
    seen = set(zip(df["complaint_type"], df["descriptor"]))
    types = sorted(df["complaint_type"].dropna().unique())
    rows = _pick_rows(df, rate, rng, df["complaint_type"].notna() & df["descriptor"].notna())
    col = out.columns.get_loc("complaint_type")
    changed = []
    for r in rows:
        d = df["descriptor"].iloc[r]
        cands = [t for t in types if (t, d) not in seen]
        if cands:
            out.iloc[r, col] = cands[int(rng.integers(0, len(cands)))]
            changed.append(r)
    return out, Truth("j", _mask(out, np.array(changed, dtype=int)), ["complaint_type"])


# --- k. resolution description contradicts status ---------------------------
_CLOSED_TEXT = ["The Department of Housing Preservation and Development inspected and the "
                "violation was corrected. The complaint has been closed.",
                "The agency resolved this issue and closed the service request."]
_OPEN_TEXT = ["This request is still open and the agency has not yet responded to the "
              "complaint.",
              "The complaint is pending and no action has been taken. It remains unresolved."]


def c_k(df, rate, rng) -> Result:
    out = df.copy()
    rows = _pick_rows(df, rate, rng, df["status"].notna())
    col = out.columns.get_loc("resolution_description")
    for r in rows:
        pool = _OPEN_TEXT if df["status"].iloc[r] == "Closed" else _CLOSED_TEXT
        out.iloc[r, col] = pool[int(rng.integers(0, len(pool)))]
    return out, Truth("k", _mask(out, rows), ["resolution_description"])


# --- l. personal data in free text ------------------------------------------
_FIRST = ["James", "Maria", "Wei", "Aisha", "Carlos", "Priya", "John", "Elena"]
_LAST = ["Smith", "Garcia", "Chen", "Khan", "Lopez", "Patel", "Brown", "Rossi"]


def _pii(rng: np.random.Generator) -> str:
    n = f"{_FIRST[int(rng.integers(0, 8))]} {_LAST[int(rng.integers(0, 8))]}"
    kind = int(rng.integers(0, 3))
    if kind == 0:
        return f"Caller {n} at {int(rng.integers(200, 999))}-{int(rng.integers(200, 999))}-{int(rng.integers(1000, 9999))}"
    if kind == 1:
        return f"contact {n.lower().replace(' ', '.')}@example.com"
    return f"complainant name: {n}, phone ({int(rng.integers(200, 999))}) {int(rng.integers(200, 999))}-{int(rng.integers(1000, 9999))}"


def c_l(df, rate, rng) -> Result:
    out = df.copy()
    rows = _pick_rows(df, rate, rng)
    col = out.columns.get_loc("resolution_description")
    for r in rows:
        base = df["resolution_description"].iloc[r] or ""
        out.iloc[r, col] = f"{base} {_pii(rng)}".strip()
    return out, Truth("l", _mask(out, rows), ["resolution_description"])


CORRUPTIONS: list[Corruption] = [
    Corruption("a", "Renamed or dropped column", "schema", c_a),
    Corruption("b", "Column type change", "schema", c_b),
    Corruption("c", "Date format switch partway through batch", "batch", c_c),
    Corruption("d", "Latitude/longitude swapped", "row", c_d),
    Corruption("e", "Exact duplicates", "row", c_e),
    Corruption("f", "Near-duplicates", "row", c_f),
    Corruption("g", "Null spike in one agency's records", "batch", c_g),
    Corruption("h", "Closed date earlier than created date", "row", c_h),
    Corruption("i", "ZIP inconsistent with borough", "row", c_i),
    Corruption("j", "Complaint Type inconsistent with Descriptor", "row", c_j),
    Corruption("k", "Resolution Description contradicting Status", "row", c_k),
    Corruption("l", "Personal data in free-text fields", "row", c_l),
]

BY_KEY = {c.key: c for c in CORRUPTIONS}


def inject(df: pd.DataFrame, key: str, rate: float, seed: int = 0) -> Result:
    return BY_KEY[key].apply(df, rate, np.random.default_rng(seed))
