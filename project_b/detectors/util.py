"""Helpers shared by detectors. Batches may be corrupted (missing/renamed/
retyped columns), so every access goes through these defensive helpers."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..schema import ISO_FMT
from .base import Alert, Family


def text_col(df: pd.DataFrame, name: str) -> pd.Series | None:
    """Column as object strings with nulls preserved; None if column missing."""
    if name not in df.columns:
        return None
    return df[name].astype(object).map(lambda v: None if pd.isna(v) else str(v))


def num_col(df: pd.DataFrame, name: str) -> pd.Series | None:
    if name not in df.columns:
        return None
    return pd.to_numeric(df[name], errors="coerce")


def parse_iso(df: pd.DataFrame, name: str) -> pd.Series | None:
    s = text_col(df, name)
    return None if s is None else pd.to_datetime(s, format=ISO_FMT, errors="coerce")


def row_alerts(mask: pd.Series, key: str, detector: str, family: Family, *,
               column: str | None = None, df: pd.DataFrame | None = None,
               reason: str, expected: str | None = None,
               confidence: float | None = None) -> list[Alert]:
    """One alert per True row; `reason` may use {value} for the observed value."""
    out: list[Alert] = []
    for i in np.flatnonzero(mask.to_numpy()):
        obs = None
        if column is not None and df is not None and column in df.columns:
            v = df[column].iloc[i]
            obs = None if pd.isna(v) else str(v)
        out.append(Alert(key, detector, family, reason.format(value=obs, col=column),
                         int(i), column, obs, expected, confidence))
    return out
