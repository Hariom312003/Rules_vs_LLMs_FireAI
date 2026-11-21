"""Family (b): statistical / ML detectors. Baselines are LEARNED from clean
data in fit(); no thresholds on domain knowledge such as the NYC bounding box.
"""
from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict

import numpy as np
import pandas as pd
from scipy import stats as sps
from sklearn.ensemble import IsolationForest
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from ..schema import CORE_COLUMNS, EXPECTED_KIND, STATUSES_CLOSED
from .base import Alert
from .util import num_col, parse_iso, row_alerts, text_col


def _pattern(v: str) -> str:
    """Shape signature: digits->9, letters->a (collapsed), e.g. 2023-01-05T.. -> 9-9-9a9:9:9.9"""
    s = re.sub(r"\d+", "9", v)
    return re.sub(r"[A-Za-z]+", "a", s)


def _text_feats(s: pd.Series) -> np.ndarray:
    s = s.fillna("").astype(str)
    n = s.str.len().clip(lower=1)
    return np.column_stack([
        s.str.len(),
        s.str.count(r"\d") / n,
        s.str.count("@"),
        s.str.count(r"[A-Z]") / n,
        s.str.count(r"[-().]") / n,
    ])


class StatDetectors:
    name = "stats"
    family = "stats"
    problem_keys = list("abcdefghijkl")

    def __init__(self, seed: int = 0):
        self.seed = seed

    def fit(self, clean: pd.DataFrame) -> "StatDetectors":
        self.cols = list(clean.columns)
        self.fill = clean.notna().mean()
        # c: shape-pattern frequencies of the date columns
        self.pat = {c: Counter(clean[c].dropna().astype(str).map(_pattern))
                    for c in ("created_date", "closed_date")}
        self.pat_n = {c: sum(v.values()) for c, v in self.pat.items()}
        # d: per-borough mean/cov of coordinates (Mahalanobis)
        self.geo = {}
        for b, g in clean.groupby("borough"):
            xy = g[["latitude", "longitude"]].dropna().to_numpy()
            if len(xy) > 30:
                cov = np.cov(xy.T) + np.eye(2) * 1e-9
                self.geo[b] = (xy.mean(0), np.linalg.inv(cov))
        allxy = clean[["latitude", "longitude"]].dropna().to_numpy()
        self.geo_all = (allxy.mean(0), np.linalg.inv(np.cov(allxy.T) + np.eye(2) * 1e-9))
        d = self._maha(clean)
        self.geo_thr = float(np.nanquantile(d, 0.9995)) * 1.5
        # g: baseline null-rate per column
        self.null_base = clean.isna().mean()
        self.null_base_ag = clean.groupby('agency').apply(lambda g: g.isna().mean(), include_groups=False)
        # h: duration distribution
        dur = (parse_iso(clean, "closed_date") - parse_iso(clean, "created_date")).dt.total_seconds()
        self.dur_min = float(dur.min()) if dur.notna().any() else 0.0
        # i: P(borough | zip); j: P(type | descriptor)
        self.zb = self._cond(clean, "incident_zip", "borough")
        self.dt = self._cond(clean, "descriptor", "complaint_type")
        # k: text classifier  resolution text -> closed?
        r = clean["resolution_description"].fillna("")
        y = clean["status"].isin(STATUSES_CLOSED).astype(int)
        self.k_model = None
        if y.nunique() == 2 and len(clean) > 50:
            self.k_vec = TfidfVectorizer(ngram_range=(1, 2), min_df=2, max_features=20000)
            self.k_model = LogisticRegression(max_iter=300).fit(self.k_vec.fit_transform(r), y)
        # l: isolation forest on text-shape features
        txt = pd.concat([clean["descriptor"], clean["resolution_description"]])
        self.l_model = IsolationForest(n_estimators=100, random_state=self.seed,
                                       contamination=0.001).fit(_text_feats(txt))
        self.l_thr = float(np.quantile(self.l_model.score_samples(_text_feats(txt)), 0.001))
        # e: baseline duplicate rate
        self.dup_base = float(clean.duplicated().mean())
        return self

    @staticmethod
    def _cond(df, given, target):
        d = defaultdict(Counter)
        for g, t in zip(df[given], df[target]):
            if pd.notna(g) and pd.notna(t):
                d[g][t] += 1
        return d

    def _maha(self, df) -> np.ndarray:
        lat, lon = num_col(df, "latitude"), num_col(df, "longitude")
        xy = np.column_stack([lat, lon]) if lat is not None and lon is not None else np.empty((0, 2))
        out = np.full(len(xy), np.nan)
        bor = df["borough"].to_numpy() if "borough" in df.columns else np.array([None] * len(xy))
        for i, (p, b) in enumerate(zip(xy, bor)):
            if np.isnan(p).any():
                continue
            m, inv = self.geo.get(b, self.geo_all)
            diff = p - m
            out[i] = float(np.sqrt(diff @ inv @ diff))
        return out

    # a: column fill-rate vector vs baseline -------------------------------
    def _a(self, df):
        missing = [c for c in self.cols if c not in df.columns]
        extra = [c for c in df.columns if c not in self.cols]
        jac = len(set(df.columns) & set(self.cols)) / max(1, len(set(df.columns) | set(self.cols)))
        if jac < 1.0:
            return [Alert("a", self.name, "stats",
                          f"Column-set similarity {jac:.2f} vs baseline; missing {missing}, new {extra}",
                          None, ",".join(missing or extra), f"jaccard={jac:.2f}", "jaccard=1.00")]
        return []

    # b: dominant value type per column vs baseline -------------------------
    def _b(self, df):
        out = []
        for c in self.cols:
            if c not in df.columns:
                continue
            kind = EXPECTED_KIND.get(c)
            sample = df[c].dropna().head(200)
            if sample.empty:
                continue
            is_num = float(np.mean([isinstance(v, (int, float, np.number)) for v in sample]))
            want_num = 1.0 if kind == "float" else 0.0
            if abs(is_num - want_num) > 0.5:
                out.append(Alert("b", self.name, "stats",
                                 f"Value type of '{c}': {is_num:.0%} numeric vs baseline {want_num:.0%}",
                                 None, c, f"{is_num:.0%} numeric", f"{want_num:.0%} numeric"))
        return out

    # c: date shape pattern rarer than baseline ----------------------------
    def _c(self, df):
        out = []
        for c in ("created_date", "closed_date"):
            s = text_col(df, c)
            if s is None:
                continue
            pats = s.map(lambda v: _pattern(v) if isinstance(v, str) else None)
            freq = pats.map(lambda p: self.pat[c].get(p, 0) / self.pat_n[c] if isinstance(p, str) else np.nan)
            bad = freq.notna() & (freq < 0.001)
            out += row_alerts(bad, "c", self.name, "stats", column=c, df=df,
                              reason="{col} value '{value}' has a shape seen in <0.1% of baseline")
        return out

    # d: Mahalanobis distance from the borough's coordinate cloud ---------
    def _d(self, df):
        d = self._maha(df)
        bad = pd.Series(np.nan_to_num(d, nan=0) > self.geo_thr, index=df.index)
        return row_alerts(bad, "d", self.name, "stats", column="latitude", df=df,
                          reason="Coordinates far from borough's usual cluster (lat={value})")

    # e: batch duplicate rate (binomial) then flag repeated rows ----------
    def _e(self, df):
        dup = df.duplicated(keep="first")
        n, k = len(df), int(dup.sum())
        if n == 0 or sps.binomtest(k, n, max(self.dup_base, 1e-4), alternative="greater").pvalue > 1e-3:
            return []
        return row_alerts(dup, "e", self.name, "stats", df=df,
                          reason=f"Duplicate rate {k / n:.1%} far above baseline {self.dup_base:.2%}")

    # f: fuzzy match (time + text similarity) inside blocks ---------------
    def _f(self, df):
        ts = parse_iso(df, "created_date")
        need = ["agency", "complaint_type", "incident_address", "descriptor"]
        if ts is None or any(c not in df.columns for c in need):
            return []
        exact = df.duplicated(keep="first")
        work = df.assign(_t=ts)[~exact & ts.notna()]
        mask = pd.Series(False, index=df.index)
        for _, g in work.groupby(["agency", "complaint_type", "incident_address"], dropna=False):
            if len(g) < 2:
                continue
            g = g.sort_values("_t")
            idx, tt, dd = g.index.to_list(), g["_t"].to_list(), g["descriptor"].fillna("").to_list()
            for i in range(1, len(g)):
                for j in range(i):
                    if (tt[i] - tt[j]).total_seconds() <= 600 and \
                            difflib.SequenceMatcher(None, dd[i], dd[j]).ratio() >= 0.8:
                        mask.loc[idx[i]] = True
                        break
        return row_alerts(mask, "f", self.name, "stats", column="created_date", df=df,
                          reason="Near-identical request (same place/type, text similarity>=0.8) within 10 min")

    # g: per-agency null rate vs baseline, binomial test -------------------
    def _g(self, df):
        if "agency" not in df.columns:
            return []
        out = []
        for c in self.cols:
            if c not in df.columns or c == "closed_date":
                continue
            for ag, g in df.groupby("agency"):
                if len(g) < 20:
                    continue
                per_ag = (self.null_base_ag.loc[ag, c] if ag in self.null_base_ag.index and c in self.null_base_ag.columns
                          else self.null_base.get(c, 0))
                base = max(float(per_ag), 0.005)
                k = int(g[c].isna().sum())
                if sps.binomtest(k, len(g), base, alternative="greater").pvalue < 1e-6 and k / len(g) - base > 0.05:
                    out.append(Alert("g", self.name, "stats",
                                     f"Agency {ag}: '{c}' null rate {k / len(g):.0%} vs baseline {base:.1%}",
                                     None, c, f"{k / len(g):.0%}", f"{base:.1%}"))
                    out += row_alerts((df["agency"] == ag) & df[c].isna(), "g", self.name, "stats",
                                      column=c, df=df, reason=f"Null '{c}' in agency {ag} (null-rate anomaly)")
        return out

    # h: duration below anything seen in baseline ---------------------------
    def _h(self, df):
        cr, cl = parse_iso(df, "created_date"), parse_iso(df, "closed_date")
        if cr is None or cl is None:
            return []
        dur = (cl - cr).dt.total_seconds()
        return row_alerts(dur < min(self.dur_min, 0) - 0.0 if self.dur_min >= 0 else dur < self.dur_min,
                          "h", self.name, "stats", column="closed_date", df=df,
                          reason="Resolution time is below the minimum seen in baseline (negative)")

    # i: P(borough | zip) from baseline -----------------------------------
    def _i(self, df):
        z, b = text_col(df, "incident_zip"), text_col(df, "borough")
        if z is None or b is None:
            return []
        def p(zz, bb):
            c = self.zb.get(zz)
            return None if not c else c[bb] / sum(c.values())
        probs = pd.Series([p(zz, bb) if zz and bb else None for zz, bb in zip(z, b)], index=df.index)
        return row_alerts(probs.notna() & (probs < 0.01), "i", self.name, "stats",
                          column="incident_zip", df=df,
                          reason="P(borough | ZIP {value}) < 1% in baseline")

    # j: P(complaint type | descriptor) from baseline -----------------------
    def _j(self, df):
        t, d = text_col(df, "complaint_type"), text_col(df, "descriptor")
        if t is None or d is None:
            return []
        def p(tt, dd):
            c = self.dt.get(dd)
            return None if not c else c[tt] / sum(c.values())
        probs = pd.Series([p(tt, dd) if tt and dd else None for tt, dd in zip(t, d)], index=df.index)
        return row_alerts(probs.notna() & (probs < 0.01), "j", self.name, "stats",
                          column="complaint_type", df=df,
                          reason="P(Complaint Type '{value}' | Descriptor) < 1% in baseline")

    # k: text classifier disagrees with status -----------------------------
    def _k(self, df):
        r, s = text_col(df, "resolution_description"), text_col(df, "status")
        if r is None or s is None or self.k_model is None:
            return []
        p_closed = self.k_model.predict_proba(self.k_vec.transform(r.fillna("")))[:, 1]
        is_closed = s.isin(STATUSES_CLOSED).to_numpy()
        p_actual = np.where(is_closed, p_closed, 1 - p_closed)
        bad = pd.Series(p_actual < 0.1, index=df.index)
        return row_alerts(bad, "k", self.name, "stats", column="resolution_description", df=df,
                          reason="Resolution text unlikely (<10%) for this status per classifier")

    # l: isolation forest on text-shape features ----------------------------
    def _l(self, df):
        out = []
        for c in ("descriptor", "resolution_description"):
            s = text_col(df, c)
            if s is None:
                continue
            sc = self.l_model.score_samples(_text_feats(s))
            out += row_alerts(pd.Series(sc < self.l_thr, index=df.index), "l", self.name, "stats",
                              column=c, df=df, reason=f"Text in '{c}' is a statistical outlier (digits/@/caps profile)")
        return out

    def detect(self, batch: pd.DataFrame) -> list[Alert]:
        out: list[Alert] = []
        for k in self.problem_keys:
            out += getattr(self, f"_{k}")(batch)
        return out
