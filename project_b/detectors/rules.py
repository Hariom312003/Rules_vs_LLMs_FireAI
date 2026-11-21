"""Family (a): declarative rules / schema checks. Cheap, deterministic,
per-row, and every alert says exactly which rule fired."""
from __future__ import annotations

import re

import numpy as np
import pandas as pd

from ..schema import (CORE_COLUMNS, EXPECTED_KIND, FLOAT_COLS, ISO_REGEX, LAT_RANGE,
                      LON_RANGE, STATUSES_CLOSED, zip_borough)
from .base import Alert
from .util import num_col, parse_iso, row_alerts, text_col

PHONE = re.compile(r"(?<!\d)(?:\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4})(?!\d)")
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
NAME_HINT = re.compile(r"\b(?:caller|complainant|name:?|mr\.?|mrs\.?|ms\.?|dr\.?)\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+)?")
OPEN_WORDS = re.compile(r"\b(?:still open|pending|not yet|unresolved|no action|has not)\b", re.I)
CLOSED_WORDS = re.compile(r"\b(?:has been closed|was closed|closed (?:this|the)|resolved|corrected)\b", re.I)
CLOSED_STATUS = STATUSES_CLOSED

NULL_RATE_LIMIT = 0.30  # static threshold: >30% nulls in a monitored column per agency
NEAR_DUP_SECONDS = 300


class RuleDetectors:
    name = "rules"
    family = "rules"
    problem_keys = list("abcdefghijkl")

    def __init__(self):
        self.valid_pairs: set[tuple[str, str]] = set()

    def fit(self, clean: pd.DataFrame) -> "RuleDetectors":
        """Rules are hand-written; fit only loads the reference (complaint, descriptor) table."""
        self.valid_pairs = set(zip(clean["complaint_type"], clean["descriptor"]))
        return self

    # -- one method per problem key; each returns alerts -------------------
    def _a(self, df) -> list[Alert]:
        miss = [c for c in CORE_COLUMNS if c not in df.columns]
        extra = [c for c in df.columns if c not in CORE_COLUMNS]
        if not miss and not extra:
            return []
        return [Alert("a", self.name, "rules",
                      f"Schema mismatch: missing {miss}, unexpected {extra} (possible rename)",
                      None, ",".join(miss or extra), str(extra) or None, "core columns")]

    def _b(self, df) -> list[Alert]:
        out = []
        for c, kind in EXPECTED_KIND.items():
            if c not in df.columns:
                continue
            numeric = pd.api.types.is_numeric_dtype(df[c])
            if kind == "float" and not numeric:
                out.append(Alert("b", self.name, "rules",
                                 f"Column '{c}' expected numeric but arrived as {df[c].dtype}",
                                 None, c, str(df[c].dtype), "float64"))
            elif kind != "float" and numeric and df[c].notna().any():
                out.append(Alert("b", self.name, "rules",
                                 f"Column '{c}' expected text but arrived as {df[c].dtype}",
                                 None, c, str(df[c].dtype), "string"))
        return out

    def _c(self, df) -> list[Alert]:
        out = []
        for c in ("created_date", "closed_date"):
            s = text_col(df, c)
            if s is None:
                continue
            bad = s.notna() & ~s.fillna("").str.match(ISO_REGEX)
            out += row_alerts(bad, "c", self.name, "rules", column=c, df=df,
                              reason="{col} value '{value}' does not match ISO format",
                              expected="YYYY-MM-DDTHH:MM:SS[.fff]")
        return out

    def _d(self, df) -> list[Alert]:
        lat, lon = num_col(df, "latitude"), num_col(df, "longitude")
        if lat is None or lon is None:
            return []
        bad = (lat.notna() & ~lat.between(*LAT_RANGE)) | (lon.notna() & ~lon.between(*LON_RANGE))
        swapped = lat.between(*LON_RANGE) & lon.between(*LAT_RANGE)
        out = row_alerts(bad, "d", self.name, "rules", column="latitude", df=df,
                         reason="Coordinates outside NYC box (lat={value})",
                         expected=f"lat {LAT_RANGE}, lon {LON_RANGE}")
        for a in out:
            if swapped.iloc[a.row_index]:
                a.reason += "; values look swapped (lat holds a longitude)"
        return out

    def _e(self, df) -> list[Alert]:
        return row_alerts(df.duplicated(keep="first"), "e", self.name, "rules", df=df,
                          reason="Row is an exact duplicate of an earlier row",
                          expected="unique rows")

    def _f(self, df) -> list[Alert]:
        keys = ["agency", "complaint_type", "incident_address", "incident_zip", "borough"]
        ts = parse_iso(df, "created_date")
        if ts is None or any(k not in df.columns for k in keys):
            return []
        exact = df.duplicated(keep="first")
        work = df.assign(_t=ts)[~exact & ts.notna()].sort_values("_t")
        gap = work.groupby(keys, dropna=False)["_t"].diff().dt.total_seconds()
        near = gap.notna() & (gap <= NEAR_DUP_SECONDS)
        mask = pd.Series(False, index=df.index)
        mask.loc[near[near].index] = True
        return row_alerts(mask, "f", self.name, "rules", column="created_date", df=df,
                          reason=f"Same agency/type/address as another request within {NEAR_DUP_SECONDS}s",
                          expected="distinct requests")

    def _g(self, df) -> list[Alert]:
        if "agency" not in df.columns:
            return []
        out = []
        for c in ("incident_zip", "borough", "latitude", "longitude", "descriptor"):
            if c not in df.columns:
                continue
            g = df.groupby("agency")[c].apply(lambda s: s.isna().mean())
            n = df.groupby("agency").size()
            for ag in g[(g > NULL_RATE_LIMIT) & (n >= 20)].index:
                mask = (df["agency"] == ag) & df[c].isna()
                out.append(Alert("g", self.name, "rules",
                                 f"Agency {ag}: {g[ag]:.0%} of '{c}' is null", None, c,
                                 f"{g[ag]:.0%} null", f"<= {NULL_RATE_LIMIT:.0%}"))
                out += row_alerts(mask, "g", self.name, "rules", column=c, df=df,
                                  reason=f"Null '{c}' in agency {ag} during a null spike")
        return out

    def _h(self, df) -> list[Alert]:
        cr, cl = parse_iso(df, "created_date"), parse_iso(df, "closed_date")
        if cr is None or cl is None:
            return []
        return row_alerts(cl.notna() & cr.notna() & (cl < cr), "h", self.name, "rules",
                          column="closed_date", df=df,
                          reason="closed_date {value} is earlier than created_date",
                          expected=">= created_date")

    def _i(self, df) -> list[Alert]:
        z, b = text_col(df, "incident_zip"), text_col(df, "borough")
        if z is None or b is None:
            return []
        implied = z.map(zip_borough)
        bad = implied.notna() & b.notna() & (implied != b)
        out = row_alerts(bad, "i", self.name, "rules", column="incident_zip", df=df,
                         reason="ZIP {value} does not belong to the stated borough")
        for a in out:
            a.expected = f"borough {implied.iloc[a.row_index]}"
        return out

    def _j(self, df) -> list[Alert]:
        t, d = text_col(df, "complaint_type"), text_col(df, "descriptor")
        if t is None or d is None or not self.valid_pairs:
            return []
        bad = pd.Series([(a, b) not in self.valid_pairs if a and b else False
                         for a, b in zip(t, d)], index=df.index)
        return row_alerts(bad, "j", self.name, "rules", column="complaint_type", df=df,
                          reason="Complaint Type '{value}' never appears with this Descriptor",
                          expected="known (type, descriptor) pair")

    def _k(self, df) -> list[Alert]:
        r, s = text_col(df, "resolution_description"), text_col(df, "status")
        if r is None or s is None:
            return []
        r = r.fillna("")
        closed = s.isin(CLOSED_STATUS)
        bad = (closed & r.str.contains(OPEN_WORDS)) | (~closed & r.str.contains(CLOSED_WORDS))
        return row_alerts(bad, "k", self.name, "rules", column="resolution_description",
                          df=df, reason="Resolution text contradicts status (keyword rule)",
                          expected="text consistent with status")

    def _l(self, df) -> list[Alert]:
        out = []
        for c in ("descriptor", "resolution_description"):
            s = text_col(df, c)
            if s is None:
                continue
            s = s.fillna("")
            for kind, rx in (("phone number", PHONE), ("email address", EMAIL),
                             ("person name", NAME_HINT)):
                out += row_alerts(s.str.contains(rx), "l", self.name, "rules", column=c,
                                  df=df, reason=f"Possible {kind} in free text field '{c}'",
                                  expected="no personal data")
        return out

    def detect(self, batch: pd.DataFrame) -> list[Alert]:
        out: list[Alert] = []
        for k in self.problem_keys:
            out += getattr(self, f"_{k}")(batch)
        return out
