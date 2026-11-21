"""Common detector contract so rules / stats / LLM are measured identically.

A detector returns Alerts. `row_index=None` means a batch-level alert.
Alert clarity (Task 4) is scored from how many of column / observed / expected
an alert carries, so fill them in whenever they are known.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol

import pandas as pd

Family = Literal["rules", "stats", "llm"]


@dataclass
class Alert:
    problem_key: str  # a..l, matches injector.corruptions
    detector: str
    family: Family
    reason: str
    row_index: int | None = None
    column: str | None = None
    observed: str | None = None
    expected: str | None = None
    confidence: float | None = None

    def clarity(self) -> float:
        """0..1: reason present + column named + observed value + expected value."""
        parts = [bool(self.reason and len(self.reason) > 10), bool(self.column),
                 bool(self.observed), bool(self.expected)]
        return sum(parts) / 4


class Detector(Protocol):
    name: str
    family: Family
    problem_keys: list[str]  # which of a..l this detector targets

    def fit(self, clean: pd.DataFrame) -> "Detector": ...

    def detect(self, batch: pd.DataFrame) -> list[Alert]: ...
