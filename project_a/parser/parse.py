"""Task 3: free text (incl. Hinglish) -> TaxpayerInput, or a clarifying question.

Hybrid design
  extract   LLM (or a regex baseline when no model is reachable) turns text into a
            loose dict of facts + flags (what is mentioned, what looks contradictory).
  validate  deterministic rules decide whether we can proceed. NEVER guess: age and
            gross salary must be present and unambiguous; salary basis/period must be
            clear; if rent / home loan / parents' insurance / NPS is mentioned, the
            amounts the tax needs must be given; contradictions are asked about.
  Unmentioned deductions default to 0 and are reported back as `assumptions`.
City -> metro is a rule (Delhi, Mumbai, Kolkata, Chennai), not an LLM decision.
"""
from __future__ import annotations

import json
import re

from pydantic import BaseModel

from common.llm import LLMClient

from ..tax_engine.models import TaxpayerInput

METRO = {"delhi", "new delhi", "mumbai", "bombay", "kolkata", "calcutta", "chennai", "madras"}

QUESTIONS = {
    "age": "What is your age (in years)? It decides the old-regime slab and the senior-citizen limits.",
    "gross_salary": "What is your total annual gross salary in rupees?",
    "gross_salary_basis": "Is that figure your gross salary, your CTC or your take-home pay? I need the annual gross salary.",
    "gross_salary_period": "Is that amount per month or per year?",
    "basic_salary": "For HRA I need your annual basic salary (including DA). What is it?",
    "hra_received": "How much HRA does your employer pay you per year?",
    "rent_paid": "How much rent do you pay per year?",
    "metro_city": "Which city do you live in? (HRA depends on whether it is Delhi, Mumbai, Kolkata or Chennai.)",
    "home_loan_interest": "How much home-loan interest did you pay this year (self-occupied house)?",
    "sec_80d_self": "How much health-insurance premium did you pay for yourself/family this year?",
    "sec_80d_parents": "How much health-insurance premium did you pay for your parents this year?",
    "parents_senior": "Is either parent 60 or older?",
    "sec_80ccd_1b": "How much did you invest in NPS (additional, 80CCD(1B)) this year?",
}


class ParseOutcome(BaseModel):
    status: str  # "ok" | "needs_clarification"
    input: TaxpayerInput | None = None
    question: str | None = None
    missing: list[str] = []         # keys from QUESTIONS the question is about
    assumptions: list[str] = []     # what we defaulted to zero
    extractor: str = ""


# ----------------------------------------------------------------------------------------
# extraction
# ----------------------------------------------------------------------------------------
EXTRACT_SYSTEM = """You extract facts about an Indian salaried taxpayer from a short message (English, Hinglish or Hindi).
Return ONLY JSON with exactly these keys. Use null when the message does not say. NEVER guess or invent a number.
Amounts are rupees; convert lakh (1,00,000), crore (1,00,00,000), k/hazaar (1,000) and monthly->annual (x12) yourself, but ONLY multiply by 12 when the text says per month/monthly/mahina. Report amounts exactly as stated: do not apply legal limits or caps, and for 80C-type items give the SUM of everything stated.
{
 "ages_mentioned": [int, ...],            // the TAXPAYER's own age(s) stated as a number or number word; NEVER infer an age from words like "senior citizen" or "young"; ages of parents or other people do NOT go here (use parents_senior instead)
 "salary_amounts_annual": [int, ...],     // every distinct GROSS salary figure stated, converted to annual rupees; if both a CTC and a gross figure are given return only the gross one; do not add bonuses unless stated as part of salary
 "salary_basis": "gross"|"ctc"|"take_home"|null,   // "ctc"/"take_home" ONLY if the message says CTC/package/in-hand/take-home; plain "salary" or "income" or "pay" -> "gross"; null if no salary figure
 "salary_period": "annual"|"monthly"|"unclear"|null,        // unclear if the message gives a bare number with no period
 "basic_salary_annual": int|null, "hra_received_annual": int|null, "rent_paid_annual": int|null,
 "city": string|null,
 "sec_80c_annual": int|null,              // total 80C-type investments (PPF, ELSS, LIC, EPF, tuition...)
 "nps_80ccd_1b": int|null, "health_premium_self": int|null, "health_premium_parents": int|null,
 "parents_senior": true|false|null, "home_loan_interest_annual": int|null,
 "mentions": {"rent": bool, "home_loan": bool, "parents_insurance": bool, "nps": bool, "health_insurance_self": bool},
 "vague_or_range": bool                   // true if figures are approximate ranges like "8-10 lakh" or "about 25ish"
}"""

_NUM = r"(\d[\d,]*(?:\.\d+)?)"
_UNIT = {"crore": 1e7, "cr": 1e7, "lakh": 1e5, "lakhs": 1e5, "lac": 1e5, "lacs": 1e5, "l": 1e5, "lpa": 1e5,
         "k": 1e3, "hazaar": 1e3, "hazar": 1e3, "thousand": 1e3}


def _amounts(text: str) -> list[tuple[int, int, bool]]:
    """(value, position, monthly?) for every money-like number in text."""
    out = []
    pat = re.compile(_NUM + r"\s*(crore|cr|lakhs?|lacs?|lpa|hazaa?r|thousand|k|l)?\b(?:\s*(?:/|per|a|ka|pm|p\.m\.)?\s*(month|mahina|mahine|mo|pm|monthly|year|annum|pa|saal|saalana|yr)?)?",
                     re.I)
    for m in pat.finditer(text.replace("\u20b9", " ")):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        unit = (m.group(2) or "").lower()
        v *= _UNIT.get(unit, 1)
        per = (m.group(3) or "").lower()
        out.append((int(round(v)), m.start(), per in ("month", "mahina", "mahine", "mo", "pm", "monthly")))
    return out


def extract_regex(text: str) -> dict:
    """Baseline extractor: no model, English/Hinglish keywords only. Weak on contradictions and Hindi script."""
    t = text.lower()
    ages = [int(a) for a in re.findall(r"(?:age[d:\s]*|aged\s*|umar\s*|umr\s*)(\d{2})\b", t)]
    ages += [int(a) for a in re.findall(r"\b(\d{2})\s*(?:years|yrs|yr|saal|sal|y/o|m\b|f\b)", t)]
    ages += [int(a) for a in re.findall(r"\bi'?m\s+(\d{2})\b", t)]
    ages = sorted(set(a for a in ages if 15 <= a <= 100))
    sal = []
    monthly = False
    for v, pos, mth in _amounts(text):
        before, after_ = t[max(0, pos - 30):pos], t[pos:pos + 40]
        has_unit = bool(re.match(r"\s*\d[\d,.]*\s*(?:crore|cr|lakhs?|lacs?|lpa|hazaa?r|thousand|k|l)\b", after_))
        if re.match(r"\s*\d[\d,.]*\s*(?:years?|yrs?|saal|sal|y/o|year old|m\b|f\b)", after_) or                 (not has_unit and re.search(r"(?:age|aged|umar|umr|i'?m|im)\s*:?\s*$", before)):
            continue  # that number is an age
        if not re.search(r"salary|earn|income|pay|make|ctc|gross|take-home|take home|in-hand|vetan|fixed|\blpa\b",
                         t[max(0, pos - 45):pos + 15]):
            continue
        if re.search(r"rent|kiraya|premium|invest|80c|nps|hra|basic|interest|byaaj|loan|ppf|elss|bonus", before):
            continue
        is_m = bool(re.match(r"\s*\d[\d,.]*\s*(?:k|hazaar|lakhs?)?\s*(?:/|per|a|ka)?\s*(?:month|mahina|mahine|mo|pm|monthly)\b", after_)) or mth
        sal.append(v * (12 if is_m else 1))
        monthly = monthly or is_m
    basis = "ctc" if re.search(r"\bctc\b", t) and not re.search(r"gross", t) else \
        "take_home" if re.search(r"take[- ]?home|in[- ]?hand", t) else "gross" if sal else None
    bare = bool(sal) and not re.search(r"lakh|lac|crore|\blpa\b|\bk\b|per (?:annum|year|month)|a year|pa\b|monthly|mahina|saal|/yr|/month|annual", t)
    men = {"rent": bool(re.search(r"\brent|kiraya|kiraye", t)), "home_loan": bool(re.search(r"home loan|housing loan|ghar ka loan", t)),
           "parents_insurance": bool(re.search(r"parents?.*(?:insurance|mediclaim|premium)|(?:insurance|mediclaim|premium).*parents?", t)),
           "nps": bool(re.search(r"\bnps\b", t)), "health_insurance_self": bool(re.search(r"mediclaim|health insurance|80d", t)) and not re.search(r"parents?", t)}
    out = {"ages_mentioned": ages, "salary_amounts_annual": sorted(set(sal)), "salary_basis": basis,
           "salary_period": "unclear" if bare else ("monthly" if monthly else "annual" if sal else None),
           "basic_salary_annual": None, "hra_received_annual": None, "rent_paid_annual": None, "city": None,
           "sec_80c_annual": None, "nps_80ccd_1b": None, "health_premium_self": None, "health_premium_parents": None,
           "parents_senior": None, "home_loan_interest_annual": None, "mentions": men,
           "vague_or_range": bool(re.search(r"\d\s*-\s*\d|ish\b|maybe|about|approx", t))}
    for city in ("delhi", "mumbai", "kolkata", "chennai", "bengaluru", "bangalore", "pune", "hyderabad"):
        if city in t:
            out["city"] = city
    def after(label_re: str):
        m = re.search(r"(?:" + label_re + r")[^0-9]{0,25}" + _NUM + r"\s*(crore|lakhs?|lacs?|k|l|hazaar)?", t)
        return int(float(m.group(1).replace(",", "")) * _UNIT.get((m.group(2) or ""), 1)) if m else None
    out["basic_salary_annual"] = after(r"basic")
    out["hra_received_annual"] = after(r"hra")
    out["home_loan_interest_annual"] = after(r"(?:interest|byaaj)") if men["home_loan"] or "interest" in t else None
    out["nps_80ccd_1b"] = after(r"nps") if men["nps"] else None
    out["sec_80c_annual"] = after(r"80c|ppf|elss")
    return out


def extract_llm(text: str, client: LLMClient) -> dict:
    raw = client.generate(f"Message:\n{text}", system=EXTRACT_SYSTEM, json_mode=True, temperature=0.0)
    m = re.search(r"\{.*\}", raw, re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


# ----------------------------------------------------------------------------------------
# validation (shared by both extractors; deterministic and auditable)
# ----------------------------------------------------------------------------------------
_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TENS = {2: "twenty", 3: "thirty", 4: "forty", 5: "fifty", 6: "sixty", 7: "seventy", 8: "eighty", 9: "ninety"}
_MONTH_CUE = re.compile(r"per\s*month|/\s*month|a month|monthly|mahina|mahine|\bpm\b|p\.m\.|every month|each month", re.I)


def age_supported(age: int, text: str) -> bool:
    """The age the extractor claims must actually be written in the text (digits or English number words)."""
    if re.search(rf"(?<!\d){age}(?!\d)", text):
        return True
    t, o = divmod(age, 10)
    if t in _TENS:
        words = {_TENS[t]} if o == 0 else {f"{_TENS[t]}-{_ONES[o]}", f"{_TENS[t]} {_ONES[o]}"}
        return any(w in text.lower() for w in words)
    return False


def _i(v):
    return int(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def validate(facts: dict, fy: str = "2024-25", extractor: str = "", text: str | None = None) -> ParseOutcome:
    miss: list[str] = []
    ages = [a for a in (facts.get("ages_mentioned") or []) if _i(a) is not None]
    if text is not None:  # evidence guard: an age that is not written in the text is a guess
        ages = [a for a in ages if age_supported(int(a), text)]
        if facts.get("salary_period") == "monthly" and not _MONTH_CUE.search(text):
            facts = {**facts, "salary_period": "unclear"}  # "monthly" without any month cue is a guess
    sal = [s for s in (facts.get("salary_amounts_annual") or []) if _i(s) is not None]
    men = facts.get("mentions") or {}

    if len(set(ages)) > 1 or not ages:
        miss.append("age")
    if facts.get("vague_or_range"):
        miss.append("gross_salary")  # approximate figures are not good enough for a rupee-exact answer
    if len(set(sal)) > 1 or not sal:
        if "gross_salary" not in miss:
            miss.append("gross_salary")
    elif facts.get("salary_basis") in ("ctc", "take_home"):  # plain "salary" is read as gross; only an explicit CTC / take-home is ambiguous
        miss.append("gross_salary_basis")
    elif facts.get("salary_period") == "unclear":
        miss.append("gross_salary_period")

    basic, hra, rent = (_i(facts.get(k)) for k in ("basic_salary_annual", "hra_received_annual", "rent_paid_annual"))
    city = (facts.get("city") or "").strip().lower() or None
    if men.get("rent") and rent != 0:
        for k, v in (("basic_salary", basic), ("hra_received", hra), ("rent_paid", rent)):
            if v is None:
                miss.append(k)
        if not city:
            miss.append("metro_city")
    if men.get("home_loan") and _i(facts.get("home_loan_interest_annual")) is None:
        miss.append("home_loan_interest")
    if men.get("parents_insurance"):
        if _i(facts.get("health_premium_parents")) is None:
            miss.append("sec_80d_parents")
        if facts.get("parents_senior") is None:
            miss.append("parents_senior")
    if men.get("nps") and _i(facts.get("nps_80ccd_1b")) is None:
        miss.append("sec_80ccd_1b")
    if men.get("health_insurance_self") and _i(facts.get("health_premium_self")) is None:
        miss.append("sec_80d_self")

    miss = list(dict.fromkeys(miss))
    if miss:
        q = " ".join(QUESTIONS[k] for k in miss)
        return ParseOutcome(status="needs_clarification", question=q, missing=miss, extractor=extractor)

    z = lambda k: _i(facts.get(k)) or 0
    inp = TaxpayerInput(
        fy=fy, age=int(ages[0]), gross_salary=int(sal[0]), basic_salary=z("basic_salary_annual"),
        hra_received=z("hra_received_annual"), rent_paid=z("rent_paid_annual"),
        metro_city=bool(city and city in METRO), sec_80c=z("sec_80c_annual"), sec_80ccd_1b=z("nps_80ccd_1b"),
        sec_80d_self=z("health_premium_self"), sec_80d_parents=z("health_premium_parents"),
        parents_senior=bool(facts.get("parents_senior")), home_loan_interest=z("home_loan_interest_annual"))
    assumed = []
    if not inp.sec_80c: assumed.append("no 80C investments")
    if not inp.sec_80ccd_1b: assumed.append("no NPS 80CCD(1B)")
    if not (inp.sec_80d_self or inp.sec_80d_parents): assumed.append("no 80D health premium")
    if not inp.home_loan_interest: assumed.append("no home-loan interest")
    if not inp.rent_paid: assumed.append("no rent / HRA claim")
    return ParseOutcome(status="ok", input=inp, assumptions=assumed, extractor=extractor)


def parse(text: str, mode: str = "llm", client: LLMClient | None = None, fy: str = "2024-25") -> ParseOutcome:
    """mode: "llm" (LLM extractor + rule validation) or "regex" (baseline extractor + same validation)."""
    if mode == "regex":
        return validate(extract_regex(text), fy, "regex", text)
    return validate(extract_llm(text, client or LLMClient()), fy, "llm", text)
