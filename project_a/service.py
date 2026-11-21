"""End-to-end service: plain-language description -> clarifying question OR tax answer.

    python -m project_a.service "I'm 32, earn 18 lakh a year, 1.5 lakh in PPF"            # LLM extractor (needs a backend)
    python -m project_a.service --regex "I'm 32, earn 18 lakh a year, 1.5 lakh in PPF"    # no LLM at all
    python -m project_a.service --fy 2025-26 --regex "29M, 9.6L pa, nothing else"

Architecture (see RESULTS_A.md section 4): LLM only for understanding the text; deterministic hand-coded
rules for every rupee; the answer carries the clause for each figure.
"""
from __future__ import annotations

import argparse
import json

from .parser.parse import parse
from .tax_engine.hand_rules.calculator import HandRulesCalculator
from .tax_engine.models import TaxResult


def answer(text: str, mode: str = "llm", fy: str = "2024-25", calculator=None) -> dict:
    out = parse(text, mode=mode, fy=fy)
    if out.status != "ok":
        return {"status": "needs_clarification", "question": out.question, "missing": out.missing}
    res: TaxResult = (calculator or HandRulesCalculator()).compute(out.input)
    return {"status": "ok", "assumptions": out.assumptions, "input": out.input.model_dump(),
            "recommended": res.recommended, "explanation": res.explanation,
            "old_regime": {"taxable_income": res.old.taxable_income, "total_tax": res.old.total_tax},
            "new_regime": {"taxable_income": res.new.taxable_income, "total_tax": res.new.total_tax},
            "trace": {"old": [t.model_dump() for t in res.old.trace], "new": [t.model_dump() for t in res.new.trace]}}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("text")
    ap.add_argument("--regex", action="store_true", help="use the regex baseline extractor (no LLM)")
    ap.add_argument("--fy", default="2024-25", choices=["2024-25", "2025-26"])
    ap.add_argument("--trace", action="store_true", help="print the clause-by-clause trace")
    a = ap.parse_args()
    r = answer(a.text, "regex" if a.regex else "llm", a.fy)
    if not a.trace:
        r.pop("trace", None)
    print(json.dumps(r, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
