"""Setup sanity checks: contracts import and the schema validates."""
from project_a.tax_engine.models import TaxpayerInput


def test_input_schema_defaults():
    inp = TaxpayerInput(age=30, gross_salary=1_000_000)
    assert inp.fy == "2024-25"
    assert inp.sec_80c == 0


def test_calculators_expose_name():
    from project_a.tax_engine.hand_rules.calculator import HandRulesCalculator
    from project_a.tax_engine.llm_compiled.calculator import LLMCompiledCalculator

    assert HandRulesCalculator.name == "hand_rules"
    assert LLMCompiledCalculator.name == "llm_compiled"
