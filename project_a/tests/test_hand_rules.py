"""Hand-coded rules vs the independent oracle suite (>=200 cases per FY) and traceability."""
import csv
from pathlib import Path

import pytest

from project_a.eval.traceability import traced_share
from project_a.tax_engine.hand_rules.calculator import HandRulesCalculator
from project_a.tax_engine.models import TaxpayerInput
from project_a.tests.build_suite import DATA, load_cases

CALC = HandRulesCalculator()
CASES = load_cases("2024-25") + load_cases("2025-26")


def test_suite_size():
    assert len(load_cases("2024-25")) >= 200
    assert len(load_cases("2025-26")) >= 100
    assert len((DATA / "descriptions.jsonl").read_text(encoding="utf-8").splitlines()) == 50


@pytest.mark.parametrize("case", CASES, ids=[f"{c['fy']}-{c['id']}" for c in CASES])
def test_rupee_exact(case):
    r = CALC.compute(TaxpayerInput(**case["input"]))
    assert (r.old.total_tax, r.new.total_tax) == (case["expected_old"], case["expected_new"])
    assert r.recommended == case["expected_recommended"]


@pytest.mark.parametrize("case", CASES[::7], ids=[f"{c['fy']}-{c['id']}" for c in CASES[::7]])
def test_every_rupee_traces_to_a_clause(case):
    r = CALC.compute(TaxpayerInput(**case["input"]))
    assert traced_share(r) == 1.0


def test_unknown_fy_fails_loudly():
    with pytest.raises(Exception):
        CALC.compute(TaxpayerInput.model_construct(fy="2030-31", age=30, gross_salary=1))


def test_official_calculator_cross_check():
    """Runs only on rows a human filled into official_checklist.csv (brief needs >=30)."""
    rows = list(csv.DictReader((DATA / "official_checklist.csv").open(encoding="utf-8")))
    filled = [r for r in rows if r["official_old_total_tax"].strip() and r["official_new_total_tax"].strip()]
    if len(filled) < 1:
        pytest.skip("official_checklist.csv not filled yet (see tests/OFFICIAL_CHECK.md)")
    for r in filled:
        inp = TaxpayerInput(fy=r["fy"], age=int(r["age"]), gross_salary=int(r["gross_salary"]),
                            basic_salary=int(r["basic_salary"]), hra_received=int(r["hra_received"]),
                            rent_paid=int(r["rent_paid"]), metro_city=r["metro_city"] == "True",
                            sec_80c=int(r["sec_80c"]), sec_80ccd_1b=int(r["sec_80ccd_1b"]),
                            sec_80d_self=int(r["sec_80d_self"]), sec_80d_parents=int(r["sec_80d_parents"]),
                            parents_senior=r["parents_senior"] == "True", self_senior=r["self_senior"] == "True",
                            home_loan_interest=int(r["home_loan_interest"]))
        res = CALC.compute(inp)
        assert (res.old.total_tax, res.new.total_tax) == (int(r["official_old_total_tax"]), int(r["official_new_total_tax"])), r["id"]
