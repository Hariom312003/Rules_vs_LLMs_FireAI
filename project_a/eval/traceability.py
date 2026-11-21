"""Task 4 traceability metric: does every rupee in the answer trace to a clause?

For one RegimeResult we check four things:
  1. every TraceLine has a non-empty clause;
  2. income-group lines sum exactly to taxable_income;
  3. tax-group lines sum exactly to total_tax;
  4. the headline figures (tax_before_rebate, rebate_87a, surcharge, cess) each appear as a trace line.
traced_share = checks passed / checks total (0..1). Lines/regimes missing => 0.
"""
from __future__ import annotations

from ..tax_engine.models import RegimeResult, TaxResult


def check_regime(r: RegimeResult) -> tuple[int, int]:
    passed = total = 0
    total += 1
    passed += all(l.clause and l.clause.strip() for l in r.trace) and bool(r.trace)
    total += 1
    passed += sum(l.amount for l in r.trace if l.group == "income") == r.taxable_income
    total += 1
    passed += sum(l.amount for l in r.trace if l.group == "tax") == r.total_tax
    tax_amounts = [l.amount for l in r.trace if l.group == "tax"]
    for headline in (r.tax_before_rebate, -r.rebate_87a if r.rebate_87a else None,
                     r.surcharge if r.surcharge else None, r.cess):
        if headline is None:
            continue
        total += 1
        passed += headline in tax_amounts
    return passed, total


def traced_share(res: TaxResult) -> float:
    p = t = 0
    for r in (res.old, res.new):
        a, b = check_regime(r)
        p, t = p + a, t + b
    return p / t if t else 0.0
