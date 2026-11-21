"""Family (c): LLM review. Two modes, both cost-aware:
  * row review   - rows are packed `rows_per_call` to a prompt; the model returns
                   JSON verdicts naming the problem type and a reason.
  * batch review - ONE call over a schema/profile summary (columns, dtypes,
                   null rates per agency, date shapes) for batch-level problems.
`max_rows` caps how many rows one detect() call may send (free-tier budget).
"""
from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from common.llm import LLMClient

from ..schema import CORE_COLUMNS
from .base import Alert

PROBLEMS = {
    "a": "a column is missing/renamed",
    "b": "a column has the wrong data type (numbers as strings or vice versa)",
    "c": "date is not in ISO 'YYYY-MM-DDTHH:MM:SS.fff' format",
    "d": "latitude/longitude look swapped or outside New York City",
    "e": "row is an exact duplicate of another row in the list",
    "f": "row is a near-duplicate of another row (same request, slightly different time/text)",
    "g": "unusual number of nulls for an agency",
    "h": "closed_date is earlier than created_date",
    "i": "incident_zip does not belong to the stated borough",
    "j": "complaint_type does not make sense with the descriptor",
    "k": "resolution_description contradicts status",
    "l": "free text contains personal data (phone, email, person name)",
}

ROW_SYSTEM = (
    "You are a data-quality reviewer for NYC 311 service-request rows. "
    "Find rows with real problems from this list:\n"
    + "\n".join(f"{k}: {v}" for k, v in PROBLEMS.items())
    + "\nReturn ONLY JSON: {\"issues\":[{\"row\":<int>,\"problem\":\"a-l\","
      "\"column\":\"...\",\"observed\":\"...\",\"reason\":\"short, specific\"}]}. "
      "Return {\"issues\":[]} if all rows are fine. Do not flag rows without clear evidence."
)

BATCH_SYSTEM = (
    "You review a PROFILE of a batch of NYC 311 data against its expected schema. "
    "Report batch-level problems only, from keys a (missing/renamed column), "
    "b (wrong data type), c (mixed date formats), g (null spike for one agency). "
    "Return ONLY JSON: {\"issues\":[{\"problem\":\"a|b|c|g\",\"column\":\"...\","
    "\"observed\":\"...\",\"reason\":\"short, specific\"}]}."
)


def _row_text(df: pd.DataFrame, i: int, cols: list[str]) -> str:
    r = df.iloc[i]
    return json.dumps({"row": i, **{c: (None if pd.isna(r[c]) else r[c]) for c in cols}},
                      default=str, ensure_ascii=False)


def _parse(text: str) -> list[dict]:
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)).get("issues", []) if m else []
    except json.JSONDecodeError:
        return []


class LLMDetector:
    name = "llm"
    family = "llm"
    problem_keys = list("abcdefghijkl")

    def __init__(self, client: LLMClient | None = None, rows_per_call: int = 25,
                 max_rows: int = 200, seed: int = 0):
        self.client = client or LLMClient()
        self.rows_per_call, self.max_rows, self.seed = rows_per_call, max_rows, seed
        self.last_reviewed: set[int] = set()

    def fit(self, clean: pd.DataFrame) -> "LLMDetector":
        return self  # nothing to learn: that is the point of using an LLM

    def profile(self, df: pd.DataFrame) -> str:
        info = {"expected_columns": CORE_COLUMNS, "n_rows": len(df),
                "columns": {c: {"dtype": str(df[c].dtype),
                                "null_rate": round(float(df[c].isna().mean()), 3),
                                "examples": [str(v) for v in df[c].dropna().head(3)]}
                            for c in df.columns}}
        if "agency" in df.columns:
            info["null_rate_by_agency_top"] = {
                str(a): {c: round(float(g[c].isna().mean()), 2) for c in df.columns
                         if g[c].isna().mean() > 0.05}
                for a, g in list(df.groupby("agency"))[:12] if len(g) >= 20}
        for c in ("created_date", "closed_date"):
            if c in df.columns:
                shapes = df[c].dropna().astype(str).str.replace(r"\d", "9", regex=True)
                info[f"{c}_shapes"] = shapes.value_counts().head(5).to_dict()
        return json.dumps(info, default=str)

    def detect(self, batch: pd.DataFrame) -> list[Alert]:
        out: list[Alert] = []
        # batch review (1 call)
        for it in _parse(self.client.generate(self.profile(batch), system=BATCH_SYSTEM,
                                              json_mode=True)):
            if it.get("problem") in PROBLEMS:
                out.append(Alert(it["problem"], self.name, "llm", str(it.get("reason", "")),
                                 None, it.get("column"), str(it.get("observed") or "") or None,
                                 None))
        # row review (sampled to max_rows)
        n = len(batch)
        idx = np.arange(n) if n <= self.max_rows else np.sort(
            np.random.default_rng(self.seed).choice(n, self.max_rows, replace=False))
        self.last_reviewed = set(int(i) for i in idx)  # eval scores recall on these only
        return out + self.review_rows(batch, idx)

    def review_rows(self, batch: pd.DataFrame, idx) -> list[Alert]:
        """LLM-review exactly these row positions (used directly by the hybrid pipeline)."""
        out: list[Alert] = []
        idx = np.asarray(idx, dtype=int)
        cols = list(batch.columns)
        for s in range(0, len(idx), self.rows_per_call):
            chunk = idx[s:s + self.rows_per_call]
            prompt = "Rows:\n" + "\n".join(_row_text(batch, int(i), cols) for i in chunk)
            for it in _parse(self.client.generate(prompt, system=ROW_SYSTEM, json_mode=True)):
                try:
                    r = int(it["row"])
                except (KeyError, TypeError, ValueError):
                    continue
                if r in set(map(int, chunk)) and it.get("problem") in PROBLEMS:
                    out.append(Alert(it["problem"], self.name, "llm", str(it.get("reason", "")),
                                     r, it.get("column"), str(it.get("observed") or "") or None,
                                     None))
        return out
