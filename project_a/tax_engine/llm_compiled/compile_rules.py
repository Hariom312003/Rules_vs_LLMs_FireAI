"""Implementation (c), step 1: an LLM converts the rule text into executable rules ONCE.

    python -m project_a.tax_engine.llm_compiled.compile_rules 2024-25
    python -m project_a.tax_engine.llm_compiled.compile_rules 2025-26

Output:
  generated/raw/rules_<fy>.raw.py   exactly what the model wrote (never edited)
  generated/rules_<fy>.py           the file that actually runs; starts as a copy of the raw output
                                    with header "REVIEWED: NO". A human must read it, fix it, record
                                    the changes in generated/REVIEW.md and flip the header to
                                    "REVIEWED: YES by <who> on <date>". The runner refuses unreviewed files.
Compiling costs one LLM call per FY; running the rules afterwards costs nothing.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

from common.llm import LLMClient

from ..llm_query.calculator import SYSTEM as OUTPUT_SPEC

GENERATED_DIR = Path(__file__).parent / "generated"
RULES_DIR = Path(__file__).resolve().parents[2] / "rules_source"

COMPILE_SYSTEM = """You are a careful Python engineer. Convert the tax RULES you are given into ONE Python module.
Requirements:
 - define exactly one entry point:  def calculate(inp: dict) -> dict
 - `inp` has the keys: fy, age, gross_salary, basic_salary, hra_received, rent_paid, metro_city (bool),
   sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents, parents_senior (bool), self_senior (bool),
   home_loan_interest. All amounts are integer rupees.
 - it must return a dict with EXACTLY the JSON shape described in OUTPUT SHAPE below (keys old, new,
   recommended, explanation; each regime has taxable_income, tax_before_rebate, rebate_87a, surcharge, cess,
   total_tax, trace).
 - put every number (slabs, limits, caps, rates) in module-level constants at the top, each with a comment
   naming the rule id ([R1], [R10] ...) it comes from, so a reviewer can check them against the rules.
 - use only the standard library (fractions.Fraction and math are allowed). No network, no file access, no I/O.
 - implement rounding exactly as the rules say (Sec 288A for income, Sec 288B for the final amount).
 - keep the code straightforward: small helper functions, no cleverness.
Return ONLY the Python code in one ```python block.

OUTPUT SHAPE
"""


def _rules_path(fy: str) -> Path:
    return RULES_DIR / f"fy{fy.replace('-', '_')}.txt"


def compile_fy(fy: str, client: LLMClient | None = None) -> dict:
    client = client or LLMClient()
    rules = _rules_path(fy).read_text(encoding="utf-8")
    t0 = time.perf_counter()
    raw = client.generate(f"RULES\n{rules}\n\nWrite the module now.",
                          system=COMPILE_SYSTEM + OUTPUT_SPEC, temperature=0.0, use_cache=False, max_tokens=6000)
    seconds = time.perf_counter() - t0
    m = re.search(r"```(?:python)?\n(.*?)```", raw, re.S)
    code = (m.group(1) if m else raw).strip() + "\n"
    stem = f"rules_{fy.replace('-', '_')}"
    (GENERATED_DIR / "raw").mkdir(parents=True, exist_ok=True)
    raw_path = GENERATED_DIR / "raw" / f"{stem}.raw.py"
    raw_path.write_text(code, encoding="utf-8")
    run_path = GENERATED_DIR / f"{stem}.py"
    if not run_path.exists():
        run_path.write_text(f"# REVIEWED: NO\n# Generated from rules_source/fy{fy.replace('-', '_')}.txt by an LLM; do not trust until reviewed.\n{code}",
                            encoding="utf-8")
    stats = client.stats.summary()
    info = {"fy": fy, "seconds": round(seconds, 1), "raw_path": str(raw_path), "run_path": str(run_path),
            "tokens_in": stats["in_tokens"], "tokens_out": stats["out_tokens"], "model": client.model}
    import json
    (GENERATED_DIR / "raw" / f"{stem}.info.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return info


if __name__ == "__main__":
    print(compile_fy(sys.argv[1] if len(sys.argv) > 1 else "2024-25"))
