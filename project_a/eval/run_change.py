"""Task 5: the law changes (FY 2025-26). Apply it to all three implementations and see what breaks.

    python -m project_a.eval.run_change              # hand rules + compiled rules (no LLM calls beyond the files on disk)
    python -m project_a.eval.run_change --llm        # + LLM query-time (small) and re-compiling FY 2025-26 with the LLM

For each implementation it records
  * what happens if the change is NOT applied (loud error or silently wrong answers?)
  * what happens on a PARTIAL update (a classic Budget-day mistake)
  * accuracy after the change is applied
  * automated timings (compile seconds, diff size). Human/assistant effort is logged by hand in
    results/build_log.md because it cannot be measured by a script.
SILENT = a valid answer that is wrong, with no error raised.
"""
from __future__ import annotations

import argparse
import difflib
import importlib.util
import json
import re
import time
from pathlib import Path

from common.llm import LLMClient

from ..tax_engine.hand_rules import calculator as hand_mod
from ..tax_engine.hand_rules.calculator import CONFIG_DIR, HandRulesCalculator, load_config
from ..tax_engine.llm_compiled.calculator import GENERATED_DIR, LLMCompiledCalculator
from ..tax_engine.llm_compiled.compile_rules import compile_fy
from ..tax_engine.llm_query.calculator import LLMQueryCalculator
from ..tax_engine.models import TaxResult, TaxpayerInput
from ..tests.build_suite import load_cases
from ..tests.oracle import expected
from .run_eval import evaluate, spread

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[1] / "results"


def brief(r: dict) -> dict:
    return {k: r[k] for k in ("n_cases", "regime_exact", "case_exact", "loud_errors", "silent_wrong") if k in r}


class FixedFile(LLMCompiledCalculator):
    """Run one specific generated file (used to test the raw LLM output and the stale FY2024-25 rules)."""

    def __init__(self, path: Path):
        super().__init__(allow_unreviewed=True)
        self.path = path

    def _module(self, fy: str):
        spec = importlib.util.spec_from_file_location(self.path.stem, str(self.path))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


def crash_fix_only(raw: Path, cases: list[dict]) -> dict | str:
    """Apply ONLY the mechanical fix for a slab-unpacking crash and measure what is still wrong (silent errors)."""
    import tempfile
    code = raw.read_text(encoding="utf-8")
    triples = re.search(r"\(\s*\d+\s*,\s*[\w.()']+\s*,\s*[\d.]+\s*\)", code)  # slab rows written as (low, high, rate)
    fixed = code.replace("for limit, rate in slabs:", "for _lo, limit, rate in slabs:")
    if fixed == code or not triples:
        return "n/a: this draft's crash is not the slab-unpacking one (not a one-line fix)"
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "crashfix.py"
        p.write_text(fixed, encoding="utf-8")
        return brief(evaluate(FixedFile(p), cases))


def sensitive(cases: list[dict]) -> list[dict]:
    """FY2025-26 cases whose new-regime answer differs from what FY2024-25 rules would give."""
    out = []
    for c in cases:
        old_fy = expected({**c["input"], "fy": "2024-25"})
        if old_fy["new"] != c["expected_new"]:
            out.append(c)
    return out


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--llm-cases", type=int, default=12)
    ap.add_argument("--reuse-compiled", action="store_true", help="do not re-run the compile call; use generated/raw/*.info.json")
    args = ap.parse_args(argv)

    cases = load_cases("2025-26")
    sens = sensitive(cases)
    res: dict = {"n_cases": len(cases), "n_cases_affected_by_change": len(sens)}

    # ---------------- hand-coded rules ----------------
    h: dict = {}
    try:  # change not applied at all -> must be a LOUD failure
        HandRulesCalculator().compute(TaxpayerInput.model_construct(fy="2026-27", age=30, gross_salary=1_000_000))
        h["no_config_for_new_fy"] = "SILENT (no error)"
    except Exception as e:
        h["no_config_for_new_fy"] = f"loud: {type(e).__name__}"
    a = "".join(open(CONFIG_DIR / "fy2024_25.yaml", encoding="utf-8").readlines())
    b = "".join(open(CONFIG_DIR / "fy2025_26.yaml", encoding="utf-8").readlines())
    diff = [l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
    h["config_lines_changed"] = len(diff)
    h["code_lines_changed"] = 0
    real = load_config("2025-26")
    old = load_config("2024-25")
    orig = hand_mod.load_config
    for label, patch in (("partial_update_slabs_only", {"rebate_87a": old["rebate_87a"]}),
                         ("partial_update_rebate_only", {"slabs": old["slabs"]})):
        hand_mod.load_config = lambda fy, p=patch: {**real, **p}
        try:
            h[label] = brief(evaluate(HandRulesCalculator(), cases))
        finally:
            hand_mod.load_config = orig
    h["after_update"] = brief(evaluate(HandRulesCalculator(), cases))
    res["hand_rules"] = h

    # ---------------- LLM-compiled rules ----------------
    c: dict = {}
    stale = GENERATED_DIR / "rules_2024_25.py"
    if stale.exists():
        c["stale_fy2024_rules_used_for_fy2025"] = brief(evaluate(FixedFile(stale), cases))
    info_path = GENERATED_DIR / "raw" / "rules_2025_26.info.json"
    if args.llm or info_path.exists():
        if (args.reuse_compiled or not args.llm) and info_path.exists():
            info = json.loads(info_path.read_text(encoding="utf-8"))
        else:
            info = compile_fy("2025-26", LLMClient())  # writes raw + (if absent) an unreviewed runnable copy
        c["recompile"] = {"seconds": info["seconds"], "model": info["model"],
                          "tokens_in": info["tokens_in"], "tokens_out": info["tokens_out"]}
    raw = GENERATED_DIR / "raw" / "rules_2025_26.raw.py"
    if raw.exists():
        c["raw_llm_output"] = brief(evaluate(FixedFile(raw), cases))
        c["raw_after_crash_fix_only"] = crash_fix_only(raw, cases)
    run = GENERATED_DIR / "rules_2025_26.py"
    if run.exists():
        reviewed = run.read_text(encoding="utf-8").startswith("# REVIEWED: YES")
        c["reviewed_file_present"] = reviewed
        c["after_review"] = brief(evaluate(LLMCompiledCalculator(allow_unreviewed=True), cases)) if reviewed else "not reviewed yet"
    res["llm_compiled"] = c

    # ---------------- LLM at query time ----------------
    if args.llm:
        client = LLMClient()
        q = LLMQueryCalculator(client)
        k = args.llm_cases
        q_res = {"model": client.model, "after_update": brief(evaluate(q, spread(cases, k), client))}
        sub = spread(sens, min(8, len(sens)))
        stale_q = LLMQueryCalculator(LLMClient())
        stale_q.rules_text = lambda fy: LLMQueryCalculator.rules_text(stale_q, "2024-25")  # prompt NOT updated
        q_res["stale_prompt_fy2024_rules"] = brief(evaluate(stale_q, sub))
        res["llm_query"] = q_res

    RESULTS.mkdir(exist_ok=True)
    prev_path = RESULTS / "change_a.json"
    if prev_path.exists() and "llm_query" not in res:  # keep earlier LLM measurements when run without --llm
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        if "llm_query" in prev:
            res["llm_query"] = {**prev["llm_query"], "carried_over_from_earlier_run": True}
    prev_path.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    md = to_markdown(res)
    p = ROOT / "RESULTS_A.md"
    t = p.read_text(encoding="utf-8")
    if "<!-- CHANGE_A:START -->" in t:
        p.write_text(re.sub(r"<!-- CHANGE_A:START -->.*<!-- CHANGE_A:END -->",
                            lambda _: f"<!-- CHANGE_A:START -->\n{md}\n<!-- CHANGE_A:END -->", t, flags=re.S), encoding="utf-8")
    print(md)


def to_markdown(res: dict) -> str:
    def f(x):
        if not isinstance(x, dict):
            return str(x)
        return (f"{x['case_exact']:.2f} exact, {x['loud_errors']} loud, {x['silent_wrong']} silent of {x['n_cases']}")
    h, c, q = res["hand_rules"], res.get("llm_compiled", {}), res.get("llm_query", {})
    n, aff = res["n_cases"], res["n_cases_affected_by_change"]
    rows = [
        f"FY 2025-26 suite: {n} cases, of which {aff} have a new-regime answer that differs from FY 2024-25 rules.", "",
        "| Scenario | Hand-coded rules | LLM at query time | LLM-compiled rules |", "|---|---|---|---|",
        f"| Change not applied | {h['no_config_for_new_fy']} | stale prompt (FY24 rules): {f(q.get('stale_prompt_fy2024_rules', 'not run'))} | stale compiled FY24 rules: {f(c.get('stale_fy2024_rules_used_for_fy2025', 'not run'))} |",
        f"| Partial update | slabs only: {f(h['partial_update_slabs_only'])}; rebate only: {f(h['partial_update_rebate_only'])} | n/a (rule text is replaced whole) | n/a (module is regenerated whole) |",
        f"| Change applied | {f(h['after_update'])} | {f(q.get('after_update', 'not run'))} | raw LLM output: {f(c.get('raw_llm_output', 'not run'))}; raw + crash fix only: {f(c.get('raw_after_crash_fix_only', 'n/a'))}; after human review: {f(c.get('after_review', 'not run'))} |",
        f"| Size of the change | {h['config_lines_changed']} YAML lines, {h['code_lines_changed']} code lines | rule-text file replaced | recompile: {c.get('recompile', {}).get('seconds', 'n/a')} s ({c.get('recompile', {}).get('model', '')}) + review |",
    ]
    return "\n".join(rows)


if __name__ == "__main__":
    main()
