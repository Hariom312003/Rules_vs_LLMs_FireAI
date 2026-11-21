# REVIEWED: YES by Harry on 2026-11-20
"""
Income Tax Calculator for Resident Salaried Individual (FY 2025-26)
Derived from the REVIEWED FY 2024-25 module (the fresh LLM draft for FY 2025-26 crashed; see REVIEW.md), with the
Finance Act 2025 changes applied to the constants below.
Every line changed by the reviewer is marked "# REVIEW:" and listed in REVIEW.md.
"""

from fractions import Fraction as F  # REVIEW D2/D12: exact arithmetic instead of float + int() truncation
import math

# [R1] STANDARD DEDUCTION
STANDARD_DEDUCTION_OLD = 50000
STANDARD_DEDUCTION_NEW = 75000

# [R2] HRA EXEMPTION LIMITS (percent of basic salary)
HRA_PERCENT_METRO = 50
HRA_PERCENT_OTHER = 40
HRA_RENT_MINUS_PERCENT = 10

# [R3] SECTION 80C LIMIT
LIMIT_80C = 150000
# [R4] SECTION 80CCD(1B) LIMIT
LIMIT_80CCD_1B = 50000
# [R5] SECTION 80D LIMITS
LIMIT_80D_SELF = 25000
LIMIT_80D_SELF_SENIOR = 50000
LIMIT_80D_PARENTS = 25000
LIMIT_80D_PARENTS_SENIOR = 50000
# [R6] SECTION 24(b) HOUSE LOAN INTEREST LIMIT (self-occupied)
LIMIT_HOUSE_LOAN_INTEREST = 200000

# [R10] OLD REGIME SLABS: (upper limit, rate %) -- REVIEW D1/D10: pairs, one table per age band
OLD_SLABS = {
    "below_60": [(250000, 0), (500000, 5), (1000000, 20), (None, 30)],
    "senior_60_79": [(300000, 0), (500000, 5), (1000000, 20), (None, 30)],
    "super_senior_80_plus": [(500000, 0), (1000000, 20), (None, 30)],
}
# [R11] NEW REGIME SLABS
NEW_SLABS = [(400000, 0), (800000, 5), (1200000, 10), (1600000, 15), (2000000, 20), (2400000, 25), (None, 30)]  # CHANGED FY25-26

# [R12] REBATE UNDER 87A
REBATE_87A_OLD_LIMIT = 500000
REBATE_87A_OLD_AMOUNT = 12500
REBATE_87A_NEW_LIMIT = 1200000  # CHANGED FY25-26
REBATE_87A_NEW_AMOUNT = 60000  # CHANGED FY25-26

# [R13] SURCHARGE: (income above, rate %) -- REVIEW D5: correct ladder; new regime has no 37% band
SURCHARGE_OLD = [(5000000, 10), (10000000, 15), (20000000, 25), (50000000, 37)]
SURCHARGE_NEW = [(5000000, 10), (10000000, 15), (20000000, 25)]

# [R14] CESS RATE (percent)
CESS_RATE = 4

ROUND_UNIT = 10  # [R9] and [R15]


def round_to_unit(value) -> int:
    """[R9] Sec 288A / [R15] Sec 288B: nearest multiple of 10, 5 or more rounds up (paise ignored first)."""
    return int(math.floor(F(value) / ROUND_UNIT + F(1, 2))) * ROUND_UNIT


def to_rupee(value) -> int:
    return int(math.floor(F(value) + F(1, 2)))


def calculate_tax_on_slabs(income, slabs: list) -> F:
    """Tax before any rebate. REVIEW D1/D2: slab rows are (upper, rate); exact fractions."""
    tax, prev = F(0), F(0)
    for upper, rate in slabs:
        if income > prev:
            top = income if upper is None else min(income, upper)
            tax += (F(top) - prev) * rate / 100
        if upper is None or income <= upper:
            break
        prev = F(upper)
    return tax


def calculate_surcharge(tax_after_rebate: F, total_income: int, table: list, slabs: list) -> F:
    """[R13] surcharge on tax after rebate, with marginal relief. REVIEW D5/D6: ladder + marginal relief added."""
    rate, prev_rate, thr = 0, 0, None
    for threshold, r in table:
        if total_income > threshold:
            prev_rate, rate, thr = rate, r, threshold
    if rate == 0:
        return F(0)
    surcharge = tax_after_rebate * rate / 100
    ceiling = calculate_tax_on_slabs(thr, slabs) * (1 + F(prev_rate, 100)) + (total_income - thr)
    return max(F(0), min(surcharge, ceiling - tax_after_rebate))


def calculate_87a(tax: F, total_income: int, is_new_regime: bool) -> F:
    """[R12] amount of rebate / marginal relief. REVIEW D4: lower of tax and cap; marginal relief caps the TAX."""
    if is_new_regime:
        if total_income <= REBATE_87A_NEW_LIMIT:
            return min(tax, F(REBATE_87A_NEW_AMOUNT))
        return max(F(0), tax - (total_income - REBATE_87A_NEW_LIMIT))  # tax payable cannot exceed the excess
    if total_income <= REBATE_87A_OLD_LIMIT:
        return min(tax, F(REBATE_87A_OLD_AMOUNT))
    return F(0)  # old regime: no marginal relief


def calculate_hra_exemption(basic: int, hra_received: int, rent_paid: int, metro_city: bool) -> F:
    """[R2] least of three; REVIEW D7: real inputs are passed in and the metro flag is honoured."""
    pct = HRA_PERCENT_METRO if metro_city else HRA_PERCENT_OTHER
    return max(F(0), min(F(hra_received), F(basic) * pct / 100, F(rent_paid) - F(basic) * HRA_RENT_MINUS_PERCENT / 100))


def age_band(age: int) -> str:
    return "super_senior_80_plus" if age >= 80 else "senior_60_79" if age >= 60 else "below_60"


def compute_regime(inp: dict, is_new_regime: bool) -> dict:
    gross = F(inp.get("gross_salary", 0))
    age = inp.get("age", 0)
    lines = [("Gross salary", gross, "Sec 15 / 17(1)")]  # (label, signed amount, clause)

    std = min(gross, F(STANDARD_DEDUCTION_NEW if is_new_regime else STANDARD_DEDUCTION_OLD))
    lines.append(("Standard deduction", -std,
                  "Sec 115BAC(1A)(ii) read with Sec 16(ia)" if is_new_regime else "Sec 16(ia)"))  # REVIEW D13: real clauses
    salary_income, hp_loss, via_total = gross - std, F(0), F(0)

    if not is_new_regime:
        hra = calculate_hra_exemption(inp.get("basic_salary", 0), inp.get("hra_received", 0),
                                      inp.get("rent_paid", 0), inp.get("metro_city", False))
        if hra:
            lines.append(("HRA exemption", -hra, "Sec 10(13A) read with Rule 2A"))
        salary_income -= hra
        hp_loss = F(min(inp.get("home_loan_interest", 0), LIMIT_HOUSE_LOAN_INTEREST))
        if hp_loss:
            lines.append(("Home-loan interest (self-occupied)", -hp_loss, "Sec 24(b)"))
        self_sr = bool(inp.get("self_senior")) or age >= 60  # REVIEW D8: age drives the senior limit
        via = [
            ("Section 80C", min(inp.get("sec_80c", 0), LIMIT_80C), "Sec 80C"),
            ("Section 80CCD(1B)", min(inp.get("sec_80ccd_1b", 0), LIMIT_80CCD_1B), "Sec 80CCD(1B)"),
            ("Section 80D self/family", min(inp.get("sec_80d_self", 0), LIMIT_80D_SELF_SENIOR if self_sr else LIMIT_80D_SELF), "Sec 80D"),
            ("Section 80D parents", min(inp.get("sec_80d_parents", 0), LIMIT_80D_PARENTS_SENIOR if inp.get("parents_senior") else LIMIT_80D_PARENTS), "Sec 80D"),
        ]
        gti_pre = max(F(0), salary_income - hp_loss)
        via_total = min(F(sum(a for _, a, _ in via)), gti_pre)  # REVIEW D9: VI-A cannot exceed gross total income
        for label, amt, clause in via:
            if amt:
                lines.append((label, -F(amt), clause))  # REVIEW D13: one traced line per deduction
    gti = max(F(0), salary_income - hp_loss)
    taxable = round_to_unit(gti - via_total)  # [R9]; REVIEW D9/D14: floor at zero BEFORE rounding

    slabs = NEW_SLABS if is_new_regime else OLD_SLABS[age_band(age)]
    tax = calculate_tax_on_slabs(taxable, slabs)
    rebate = calculate_87a(tax, taxable, is_new_regime)
    tax_after = tax - rebate
    surcharge = calculate_surcharge(tax_after, taxable, SURCHARGE_NEW if is_new_regime else SURCHARGE_OLD, slabs)
    cess = (tax_after + surcharge) * CESS_RATE / 100
    total = round_to_unit(tax_after + surcharge + cess)  # [R15]

    trace, isum = [], 0
    for label, amt, clause in lines:
        trace.append({"label": label, "amount": to_rupee(amt), "clause": clause, "group": "income"})
        isum += to_rupee(amt)
    if taxable - isum:
        trace.append({"label": "Rounding / floor at zero", "amount": taxable - isum,
                      "clause": "Sec 288A; total income not below zero", "group": "income"})
    tparts = [("Tax on slabs", to_rupee(tax), "Sec 115BAC(1A)" if is_new_regime else "Finance Act First Schedule (old regime rates)")]
    if rebate:
        tparts.append(("Rebate / marginal relief u/s 87A", -to_rupee(rebate), "Sec 87A"))
    if surcharge:
        tparts.append(("Surcharge (after marginal relief)", to_rupee(surcharge), "Finance Act surcharge schedule"))
    tparts.append(("Health and education cess", to_rupee(cess), "Finance Act: cess 4%"))  # REVIEW D13: no invented sections
    tsum = 0
    for label, amt, clause in tparts:
        trace.append({"label": label, "amount": amt, "clause": clause, "group": "tax"})
        tsum += amt
    if total - tsum:
        trace.append({"label": "Rounding of amount payable", "amount": total - tsum, "clause": "Sec 288B", "group": "tax"})

    return {"regime": "new" if is_new_regime else "old", "taxable_income": taxable,
            "tax_before_rebate": to_rupee(tax), "rebate_87a": to_rupee(rebate), "surcharge": to_rupee(surcharge),
            "cess": to_rupee(cess), "total_tax": total, "trace": trace}


def calculate(inp: dict) -> dict:
    old_result = compute_regime(inp, False)
    new_result = compute_regime(inp, True)
    old_total, new_total = old_result["total_tax"], new_result["total_tax"]
    if new_total <= old_total:  # tie -> new [R16]
        recommended, saving = "new", old_total - new_total
    else:
        recommended, saving = "old", new_total - old_total
    explanation = (f"The {recommended} regime is lower: Rs {min(old_total, new_total):,} versus "
                   f"Rs {max(old_total, new_total):,} (saves Rs {saving:,}).")  # REVIEW D17: sign of the difference
    return {"old": old_result, "new": new_result, "recommended": recommended, "explanation": explanation}
