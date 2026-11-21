"""LLM-compiled rules: the reviewed modules are exact, unreviewed ones are refused, raw drafts stay broken (evidence)."""
import shutil
from pathlib import Path

import pytest

from project_a.tax_engine.llm_compiled.calculator import GENERATED_DIR, LLMCompiledCalculator
from project_a.tax_engine.models import TaxpayerInput
from project_a.tests.build_suite import load_cases

CALC = LLMCompiledCalculator()
CASES = load_cases("2024-25")[::3] + load_cases("2025-26")[::3]


@pytest.mark.parametrize("case", CASES, ids=[f"{c['fy']}-{c['id']}" for c in CASES])
def test_reviewed_compiled_rules_are_exact(case):
    r = CALC.compute(TaxpayerInput(**case["input"]))
    assert (r.old.total_tax, r.new.total_tax) == (case["expected_old"], case["expected_new"])


def test_unreviewed_file_is_refused(tmp_path: Path):
    raw = GENERATED_DIR / "raw" / "rules_2024_25.raw.py"
    shutil.copy(raw, tmp_path / "rules_2024_25.py")
    (tmp_path / "rules_2024_25.py").write_text("# REVIEWED: NO\n" + raw.read_text(encoding="utf-8"), encoding="utf-8")
    with pytest.raises(PermissionError):
        LLMCompiledCalculator(directory=tmp_path).compute(TaxpayerInput(age=30, gross_salary=1_000_000))


def test_raw_fy2024_draft_is_broken_as_documented():
    """REVIEW.md D1: the raw FY 2024-25 draft crashes on slab unpacking."""
    raw = GENERATED_DIR / "raw" / "rules_2024_25.raw.py"
    import importlib.util
    spec = importlib.util.spec_from_file_location("raw24", str(raw))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    with pytest.raises(ValueError):
        mod.calculate(TaxpayerInput(age=30, gross_salary=1_500_000).model_dump())


def test_unknown_fy_is_loud():
    with pytest.raises(ValueError):
        CALC.compute(TaxpayerInput.model_construct(fy="2030-31", age=30, gross_salary=1))
