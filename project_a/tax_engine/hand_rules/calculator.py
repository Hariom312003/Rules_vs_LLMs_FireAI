"""Implementation (a): hand-coded rules (logic in code, every number in YAML).

Exact arithmetic (fractions) throughout; rounding happens only where the law
rounds: total income to the nearest Rs 10 (Sec 288A) and the final amount
payable to the nearest Rs 10 (Sec 288B). Every rupee in the answer is a
TraceLine with its clause.
"""
from __future__ import annotations

import math
from fractions import Fraction as F
from functools import lru_cache
from pathlib import Path

import yaml

from ..models import RegimeResult, TaxpayerInput, TaxResult, TraceLine

CONFIG_DIR = Path(__file__).parent / "config"


@lru_cache(maxsize=None)
def load_config(fy: str) -> dict:
    path = CONFIG_DIR / f"fy{fy.replace('-', '_')}.yaml"
    if not path.exists():
        raise ValueError(f"no rules configured for FY {fy}")  # loud failure, never a silent default
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def round_to_unit(x: F, unit: int) -> int:
    """Nearest multiple of `unit`; exactly half rounds UP (Sec 288A/288B: digit 5 rounds up)."""
    return int(math.floor(x / unit + F(1, 2))) * unit


def to_rupee(x: F) -> int:
    return int(math.floor(x + F(1, 2)))


def slab_tax(slabs: list, income: F) -> F:
    tax, prev = F(0), F(0)
    for upper, rate in slabs:
        top = F(upper) if upper is not None else None
        if income > prev:
            part = (min(income, top) if top is not None else income) - prev
            tax += part * rate / 100
        if top is None or income <= top:
            break
        prev = top
    return tax


def surcharge_with_relief(cfg_rows: list, slabs: list, income: F, tax_after: F) -> F:
    rate, prev_rate, thr = 0, 0, None
    for threshold, r in cfg_rows:
        if income > threshold:
            prev_rate, rate, thr = rate, r, F(threshold)
    if rate == 0:
        return F(0)
    sc = tax_after * rate / 100
    cap = slab_tax(slabs, thr) * (1 + F(prev_rate, 100)) + (income - thr)  # marginal relief
    return max(F(0), min(sc, cap - tax_after))


def age_band(age: int) -> str:
    return "super_senior_80_plus" if age >= 80 else "senior_60_79" if age >= 60 else "below_60"


class HandRulesCalculator:
    name = "hand_rules"

    def compute_regime(self, inp: TaxpayerInput, regime: str) -> RegimeResult:
        cfg = load_config(inp.fy)
        unit = cfg["rounding_unit"]
        gross = F(inp.gross_salary)
        inc: list[tuple[str, F, str]] = [("Gross salary", gross, "Sec 15 / 17(1)")]

        std = min(F(cfg["standard_deduction"][regime]["amount"]), gross)
        inc.append(("Standard deduction", -std, cfg["standard_deduction"][regime]["clause"]))
        salary_income = gross - std
        via = F(0)
        hp_loss = F(0)

        if regime == "old":
            d = cfg["deductions"]
            h = d["hra"]
            basic = F(inp.basic_salary)
            pct = h["metro_pct"] if inp.metro_city else h["non_metro_pct"]
            hra = max(F(0), min(F(inp.hra_received), basic * pct / 100,
                                F(inp.rent_paid) - basic * h["rent_minus_basic_pct"] / 100))
            if hra:
                inc.append(("HRA exemption", -hra, "Sec 10(13A) read with Rule 2A"))
            salary_income -= hra
            hp_loss = F(min(inp.home_loan_interest, d["home_loan_interest_cap"]))
            if hp_loss:
                inc.append(("Home-loan interest (self-occupied)", -hp_loss, "Sec 24(b)"))
            senior = inp.self_senior or inp.age >= 60
            psenior = inp.parents_senior
            ded = [
                ("Section 80C", min(inp.sec_80c, d["sec_80c_cap"]), "Sec 80C"),
                ("Section 80CCD(1B)", min(inp.sec_80ccd_1b, d["sec_80ccd_1b_cap"]), "Sec 80CCD(1B)"),
                ("Section 80D self/family",
                 min(inp.sec_80d_self, d["sec_80d"]["self_senior_cap" if senior else "self_cap"]), "Sec 80D"),
                ("Section 80D parents",
                 min(inp.sec_80d_parents, d["sec_80d"]["parents_senior_cap" if psenior else "parents_cap"]), "Sec 80D"),
            ]
            gti = max(F(0), salary_income - hp_loss)
            total_via = min(F(sum(a for _, a, _ in ded)), gti)  # VI-A cannot exceed GTI
            for label, amt, clause in ded:
                if amt:
                    inc.append((label, -F(amt), clause))
            via = total_via
        gti = max(F(0), salary_income - hp_loss)
        raw_total = gti - via
        taxable = round_to_unit(raw_total, unit)  # Sec 288A
        T = F(taxable)

        slabs = cfg["slabs"]["new"]["all"] if regime == "new" else cfg["slabs"]["old"][age_band(inp.age)]
        tax = slab_tax(slabs, T)
        rb = cfg["rebate_87a"][regime]
        tax_after, rebate = tax, F(0)
        if T <= rb["income_limit"]:
            rebate = min(tax, F(rb["max_rebate"]))
            tax_after = tax - rebate
        elif rb["marginal_relief"]:
            tax_after = min(tax, T - rb["income_limit"])
            rebate = tax - tax_after
        sc = surcharge_with_relief(cfg["surcharge"][regime], slabs, T, tax_after)
        cess = (tax_after + sc) * cfg["cess_percent"] / 100
        total = round_to_unit(tax_after + sc + cess, unit)  # Sec 288B

        # ---- trace: income group sums to taxable income, tax group sums to total tax
        trace: list[TraceLine] = []
        isum = 0
        for label, amt, clause in inc:
            a = to_rupee(amt)
            trace.append(TraceLine(label=label, amount=a, clause=clause, group="income"))
            isum += a
        if taxable - isum:
            trace.append(TraceLine(label="Rounding / floor at zero", amount=taxable - isum,
                                   clause="Sec 288A; total income not below zero", group="income"))
        tsum = 0
        sections = "Sec 115BAC(1A)" if regime == "new" else "Finance Act First Schedule (old regime rates)"
        parts = [("Tax on slabs", to_rupee(tax), sections)]
        if rebate:
            parts.append(("Rebate / marginal relief u/s 87A", -to_rupee(rebate), "Sec 87A"))
        if sc:
            parts.append(("Surcharge (after marginal relief)", to_rupee(sc), "Finance Act surcharge schedule"))
        parts.append(("Health and education cess", to_rupee(cess), "Finance Act: cess 4%"))
        for label, amt, clause in parts:
            trace.append(TraceLine(label=label, amount=amt, clause=clause, group="tax"))
            tsum += amt
        if total - tsum:
            trace.append(TraceLine(label="Rounding of amount payable", amount=total - tsum,
                                   clause="Sec 288B", group="tax"))
        return RegimeResult(regime=regime, taxable_income=taxable, tax_before_rebate=to_rupee(tax),
                            rebate_87a=to_rupee(rebate), surcharge=to_rupee(sc), cess=to_rupee(cess),
                            total_tax=total, trace=trace)

    def compute(self, inp: TaxpayerInput) -> TaxResult:
        old, new = self.compute_regime(inp, "old"), self.compute_regime(inp, "new")
        rec = "old" if old.total_tax < new.total_tax else "new"  # tie -> new ([R16])
        diff = abs(old.total_tax - new.total_tax)
        if diff == 0:
            why = (f"Both regimes give the same tax (Rs {new.total_tax:,}); the new regime is "
                   "recommended because it is the default and needs no investment proof.")
        else:
            lo, hi = (old, new) if rec == "old" else (new, old)
            ded = sum(-l.amount for l in old.trace if l.group == "income" and l.amount < 0
                      and not l.label.startswith("Standard"))
            why = (f"The {rec} regime is lower: Rs {lo.total_tax:,} versus Rs {hi.total_tax:,} "
                   f"(saves Rs {diff:,}). Old-regime deductions available to you total "
                   f"Rs {ded:,} (HRA, 80C, 80CCD(1B), 80D, home-loan interest) against the "
                   f"lower new-regime slab rates.")
        return TaxResult(old=old, new=new, recommended=rec, explanation=why)
