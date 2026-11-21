"""Independent reference calculator used ONLY to produce expected values.

Deliberately NOT sharing code or data layout with tax_engine/hand_rules:
  * slabs are encoded the way the official page prints them: (start, base_tax, rate)
    i.e. "Rs 12,500 + 20% of income above Rs 5,00,000";
  * money is held in paise (integers) until the final rounding;
  * HRA / deduction caps are separate literals here, not read from YAML.
If this file and hand_rules disagree, one of them has a bug (or a rule was typed wrong).
"""
from __future__ import annotations

PAISE = 100

# (income_above, base_tax_in_rupees, rate_percent) -- last row open-ended
OLD = {
    "below_60": [(0, 0, 0), (250_000, 0, 5), (500_000, 12_500, 20), (1_000_000, 112_500, 30)],
    "senior": [(0, 0, 0), (300_000, 0, 5), (500_000, 10_000, 20), (1_000_000, 110_000, 30)],
    "super": [(0, 0, 0), (500_000, 0, 20), (1_000_000, 100_000, 30)],
}
NEW = {
    "2024-25": [(0, 0, 0), (300_000, 0, 5), (700_000, 20_000, 10), (1_000_000, 50_000, 15),
                (1_200_000, 80_000, 20), (1_500_000, 140_000, 30)],
    "2025-26": [(0, 0, 0), (400_000, 0, 5), (800_000, 20_000, 10), (1_200_000, 60_000, 15),
                (1_600_000, 120_000, 20), (2_000_000, 200_000, 25), (2_400_000, 300_000, 30)],
}
REBATE_NEW = {"2024-25": (700_000, 25_000), "2025-26": (1_200_000, 60_000)}
REBATE_OLD = (500_000, 12_500)
SURCHARGE_LADDER = [(5_000_000, 10), (10_000_000, 15), (20_000_000, 25), (50_000_000, 37)]


def _tax_p(table, income: int) -> int:
    """Tax in paise for an integer-rupee income from a base+rate table."""
    row = max(r for r in table if income > r[0]) if income > 0 else table[0]
    start, base, rate = row
    return base * PAISE + rate * (income - start)  # rate% of rupees == rate paise per rupee


def _round10(rupees_times_100: int) -> int:
    """Nearest Rs 10, half up, from an amount in paise."""
    unit = 10 * PAISE
    return ((rupees_times_100 + unit // 2) // unit) * 10


def _ceil_div(a: int, b: int) -> int:
    return -(-a // b)


def _surcharge_p(tax_p: int, income: int, table, regime: str) -> int:
    ladder = [r for r in SURCHARGE_LADDER if not (regime == "new" and r[1] == 37)]
    band = [r for r in ladder if income > r[0]]
    if not band:
        return 0
    thr, rate = band[-1]
    below = [r for r in ladder if r[0] < thr]
    prev_rate = below[-1][1] if below else 0
    full = tax_p * rate  # in paise*percent; divide by 100 at the end
    tax_at_thr = _tax_p(table, thr)
    ceiling = tax_at_thr * (100 + prev_rate) + (income - thr) * PAISE * 100 - tax_p * 100
    return max(0, min(full, ceiling))  # paise * 100


def _regime_total(income: int, table, regime: str, fy: str) -> int:
    t = _tax_p(table, income)
    if regime == "new":
        lim, cap = REBATE_NEW[fy]
        if income <= lim:
            t -= min(t, cap * PAISE)
        else:
            t = min(t, (income - lim) * PAISE)
    else:
        lim, cap = REBATE_OLD
        if income <= lim:
            t -= min(t, cap * PAISE)
    sc100 = _surcharge_p(t, income, table, regime)  # surcharge in paise*100
    pre_cess_100 = t * 100 + sc100                  # (tax+surcharge) in paise*100
    # exact: amount_p = pre_cess_100 * 104 / (100*100)  -> round half-up to Rs 10 via integers
    num, den = pre_cess_100 * 104, 100 * 100 * 100  # rupees = num/den
    unit = 10
    return ((2 * num + unit * den) // (2 * unit * den)) * unit


def _round_income(x: int) -> int:
    return ((x + 5) // 10) * 10


def expected(inp: dict) -> dict:
    """inp uses TaxpayerInput field names. Returns total tax under both regimes."""
    fy = inp.get("fy", "2024-25")
    g = inp["gross_salary"]
    age = inp["age"]
    # ---- new regime: only the standard deduction
    new_inc = _round_income(max(0, g - min(75_000, g)))
    new_total = _regime_total(new_inc, NEW[fy], "new", fy)
    # ---- old regime
    basic = inp.get("basic_salary", 0)
    hra_recv, rent = inp.get("hra_received", 0), inp.get("rent_paid", 0)
    share = 50 if inp.get("metro_city") else 40
    # least of three, done in paise*100 to avoid fractions: share% of basic, rent-10% basic
    cand = [hra_recv * 100, basic * share, rent * 100 - basic * 10]
    hra_ex_100 = max(0, min(cand))  # in rupees*100
    s_cap = 50_000 if (inp.get("self_senior") or age >= 60) else 25_000
    p_cap = 50_000 if inp.get("parents_senior") else 25_000
    via = (min(inp.get("sec_80c", 0), 150_000) + min(inp.get("sec_80ccd_1b", 0), 50_000)
           + min(inp.get("sec_80d_self", 0), s_cap) + min(inp.get("sec_80d_parents", 0), p_cap))
    hp = min(inp.get("home_loan_interest", 0), 200_000)
    std = min(50_000, g)
    gti_100 = max(0, (g - std - hp) * 100 - hra_ex_100)  # rupees*100
    via_100 = min(via * 100, gti_100)
    total_100 = gti_100 - via_100
    old_inc = _round_income(total_100 // 100)  # Sec 288A: ignore the paise first, then nearest Rs 10
    band = "super" if age >= 80 else "senior" if age >= 60 else "below_60"
    old_total = _regime_total(old_inc, OLD[band], "old", fy)
    return {"old": old_total, "new": new_total,
            "recommended": "old" if old_total < new_total else "new",
            "taxable_old": old_inc, "taxable_new": new_inc}
