"""Deterministic part of the parser: given extracted facts, does it ask instead of guess?"""
from project_a.parser.parse import QUESTIONS, parse, validate

BASE = {"ages_mentioned": [30], "salary_amounts_annual": [1_200_000], "salary_basis": "gross",
        "salary_period": "annual", "mentions": {}}


def test_complete_facts_proceed_with_assumptions():
    o = validate(BASE)
    assert o.status == "ok" and o.input.age == 30 and o.input.gross_salary == 1_200_000
    assert "no 80C investments" in o.assumptions


def test_missing_age_or_salary_asks():
    assert validate({**BASE, "ages_mentioned": []}).missing == ["age"]
    assert validate({**BASE, "salary_amounts_annual": []}).missing == ["gross_salary"]


def test_contradictions_ask():
    assert "age" in validate({**BASE, "ages_mentioned": [34, 52]}).missing
    assert "gross_salary" in validate({**BASE, "salary_amounts_annual": [1_200_000, 1_500_000]}).missing


def test_ctc_takehome_and_bare_numbers_are_ambiguous():
    assert validate({**BASE, "salary_basis": "ctc"}).missing == ["gross_salary_basis"]
    assert validate({**BASE, "salary_basis": "take_home"}).missing == ["gross_salary_basis"]
    assert validate({**BASE, "salary_period": "unclear"}).missing == ["gross_salary_period"]


def test_rent_without_details_asks_for_each_missing_piece():
    o = validate({**BASE, "mentions": {"rent": True}})
    assert set(o.missing) == {"basic_salary", "hra_received", "rent_paid", "metro_city"}


def test_metro_is_a_rule_not_an_llm_guess():
    facts = {**BASE, "mentions": {"rent": True}, "basic_salary_annual": 500_000, "hra_received_annual": 200_000,
             "rent_paid_annual": 240_000}
    assert validate({**facts, "city": "Mumbai"}).input.metro_city is True
    assert validate({**facts, "city": "Bengaluru"}).input.metro_city is False


def test_mentions_without_amounts_ask():
    assert validate({**BASE, "mentions": {"home_loan": True}}).missing == ["home_loan_interest"]
    assert set(validate({**BASE, "mentions": {"parents_insurance": True}}).missing) == {"sec_80d_parents", "parents_senior"}
    assert validate({**BASE, "mentions": {"nps": True}}).missing == ["sec_80ccd_1b"]


def test_every_question_key_has_text():
    for k in ("age", "gross_salary", "gross_salary_basis", "gross_salary_period", "metro_city"):
        assert "?" in QUESTIONS[k]


def test_regex_mode_runs_without_an_llm():
    o = parse("I'm 32 and earn 18 lakh a year. No investments.", mode="regex")
    assert o.status == "ok" and o.input.gross_salary == 1_800_000 and o.input.age == 32


def test_service_end_to_end_without_llm():
    from project_a.service import answer
    r = answer("I'm 32 and earn 18 lakh a year. No investments.", mode="regex")
    assert r["status"] == "ok" and r["new_regime"]["total_tax"] > 0 and r["recommended"] == "new"
    q = answer("I earn 15 lakh.", mode="regex")
    assert q["status"] == "needs_clarification" and q["missing"] == ["age"]
