"""Task 5: hybrid pipeline.

  stage 1  rules on EVERY row         (cheap, deterministic, explainable)
  stage 2  statistics per batch       (learned baselines; catches what rules can't state)
  stage 3  LLM only where it pays:
             - VERIFY rows that stage 1/2 flagged for the semantic problems
               (j, k) -- drop the alert if the LLM disagrees (false-alarm filter)
             - SAMPLE a small share of unflagged rows for semantic issues (j, k, l)
               that nothing else caught
Which family owns which problem is `ROUTING` below -- change it from the
measured winners in DECISION_MATRIX.md, not from intuition.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from common.llm import LLMClient

from ..detectors.base import Alert
from ..detectors.llm import LLMDetector
from ..detectors.rules import RuleDetectors
from ..detectors.stats import StatDetectors

# Default ownership; update after reading RESULTS_B.md.
ROUTING: dict[str, str] = {
    "a": "rules", "b": "rules", "c": "rules", "d": "rules", "e": "rules", "h": "rules",
    "i": "rules", "k": "rules", "l": "rules",
    "f": "stats", "g": "stats", "j": "stats",
}
LLM_VERIFY = {"j", "k"}      # semantic: rows flagged here get an LLM second opinion
LLM_SAMPLE_KEYS = {"j", "k", "l"}


@dataclass
class PipelineResult:
    alerts: list[Alert]
    seconds: dict[str, float] = field(default_factory=dict)
    llm_rows_reviewed: int = 0
    llm_cost_usd: float = 0.0
    suppressed_by_llm: int = 0


class HybridPipeline:
    def __init__(self, llm: LLMDetector | None = None, routing: dict[str, str] | None = None,
                 sample_rate: float = 0.02, max_llm_rows: int = 150, seed: int = 0,
                 veto: bool = False):
        self.rules, self.stats, self.llm = RuleDetectors(), StatDetectors(seed), llm
        self.routing = routing or ROUTING
        self.sample_rate, self.max_llm_rows, self.seed = sample_rate, max_llm_rows, seed
        # veto=True lets the LLM DROP rule/stat alerts it disagrees with. Measured with Qwen3.5-4B
        # this removed 146/150 true j alerts (detection 0.99 -> 0.08): keep False unless the LLM is strong.
        self.veto = veto

    def fit(self, clean: pd.DataFrame) -> "HybridPipeline":
        self.rules.fit(clean)
        self.stats.fit(clean)
        return self

    def run(self, batch: pd.DataFrame) -> PipelineResult:
        res = PipelineResult([])
        t = time.perf_counter()
        a1 = [a for a in self.rules.detect(batch) if self.routing.get(a.problem_key) == "rules"]
        res.seconds["rules"] = time.perf_counter() - t
        t = time.perf_counter()
        a2 = [a for a in self.stats.detect(batch) if self.routing.get(a.problem_key) == "stats"]
        res.seconds["stats"] = time.perf_counter() - t
        alerts = a1 + a2

        if self.llm is not None:
            t = time.perf_counter()
            self.llm.client.stats.calls.clear()
            alerts = self._llm_stage(batch, alerts, res)
            res.seconds["llm"] = time.perf_counter() - t
            res.llm_cost_usd = self.llm.client.stats.summary()["total_cost_usd"]
        res.alerts = alerts
        return res

    def _llm_stage(self, batch: pd.DataFrame, alerts: list[Alert], res: PipelineResult) -> list[Alert]:
        rng = np.random.default_rng(self.seed)
        verify_rows = sorted({a.row_index for a in alerts
                              if a.problem_key in LLM_VERIFY and a.row_index is not None})
        verify_rows = verify_rows[: self.max_llm_rows]
        flagged = {a.row_index for a in alerts if a.row_index is not None}
        pool = np.array([i for i in range(len(batch)) if i not in flagged])
        n_s = min(len(pool), max(0, int(self.sample_rate * len(batch))),
                  max(0, self.max_llm_rows - len(verify_rows)))
        sample = rng.choice(pool, n_s, replace=False) if n_s else np.array([], dtype=int)
        review = sorted(set(verify_rows) | set(map(int, sample)))
        if not review:
            return alerts
        res.llm_rows_reviewed = len(review)
        llm_alerts = self.llm.review_rows(batch, review)
        confirmed = {(a.row_index, a.problem_key) for a in llm_alerts}
        confirmed_rows = {a.row_index for a in llm_alerts}

        kept: list[Alert] = []
        for a in alerts:
            if a.problem_key in LLM_VERIFY and a.row_index in set(verify_rows):
                if a.row_index in confirmed_rows:  # LLM agrees something is wrong
                    a.reason += " [LLM-confirmed]"
                    a.confidence = 0.9
                    kept.append(a)
                elif self.veto:
                    res.suppressed_by_llm += 1
                else:
                    a.confidence = 0.5  # LLM did not confirm; keep, flagged as unconfirmed
                    kept.append(a)
            else:
                kept.append(a)
        have = {(a.row_index, a.problem_key) for a in kept}
        kept += [a for a in llm_alerts
                 if a.problem_key in LLM_SAMPLE_KEYS and (a.row_index, a.problem_key) not in have
                 and a.row_index in set(map(int, sample))]
        return kept
