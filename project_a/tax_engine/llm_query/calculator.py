"""Implementation (b): LLM at query time.

For every request the LLM receives the rule text for the requested FY plus the
structured input and returns the complete TaxResult as JSON (both regimes, trace,
recommendation, explanation). No Python arithmetic is allowed to fix its answer:
that would turn it into a hybrid and spoil the comparison. A response that is not
valid TaxResult JSON raises (a LOUD failure); a wrong-but-valid answer is a SILENT one.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from common.llm import LLMClient

from ..models import TaxpayerInput, TaxResult

RULES_DIR = Path(__file__).resolve().parents[2] / "rules_source"

SYSTEM = """You are an income-tax calculator for a resident salaried individual in India.
Apply ONLY the rules in the RULES section. Work in integer rupees. Follow every rounding rule exactly.
Compute BOTH regimes ("old" and "new"), then recommend the one with the lower total_tax (tie -> "new").

Return ONLY a JSON object, no prose, with this shape:
{
 "old": REGIME, "new": REGIME,
 "recommended": "old" | "new",
 "explanation": "one or two sentences saying why that regime is better, with the rupee difference"
}
where REGIME is
{
 "regime": "old" | "new",
 "taxable_income": int,          // total income after deductions and Sec 288A rounding
 "tax_before_rebate": int,       // tax on slabs
 "rebate_87a": int,              // rebate or marginal relief under 87A (0 if none)
 "surcharge": int,               // after marginal relief
 "cess": int,
 "total_tax": int,               // after Sec 288B rounding
 "trace": [ {"label": str, "amount": int, "clause": str, "group": "income" | "tax"} ]
}
trace rules: every rupee must appear.
 group "income" lines: "Gross salary" (+), each deduction/exemption (negative), plus one line
   "Rounding / floor at zero" if needed, so that the income lines SUM to taxable_income.
 group "tax" lines: "Tax on slabs" (+), 87A rebate (negative), "Surcharge" (+), cess (+), plus one line
   "Rounding of amount payable" if needed, so that the tax lines SUM to total_tax.
 every line needs a clause such as "Sec 16(ia)", "Sec 87A", "Sec 288A".
"""


class LLMQueryCalculator:
    name = "llm_query"

    def __init__(self, client: LLMClient | None = None, use_cache: bool = False):
        self.client = client or LLMClient()
        self.use_cache = use_cache  # False for measurement runs (determinism needs fresh calls)
        self._rules: dict[str, str] = {}

    def rules_text(self, fy: str) -> str:
        if fy not in self._rules:
            path = RULES_DIR / f"fy{fy.replace('-', '_')}.txt"
            if not path.exists():
                raise ValueError(f"no rule text for FY {fy}")
            self._rules[fy] = path.read_text(encoding="utf-8")
        return self._rules[fy]

    def compute(self, inp: TaxpayerInput) -> TaxResult:
        prompt = (f"RULES\n{self.rules_text(inp.fy)}\n\nTAXPAYER (annual rupees)\n"
                  f"{json.dumps(inp.model_dump(), indent=1)}\n\nReturn the JSON result.")
        raw = self.client.generate(prompt, system=SYSTEM, json_mode=True, temperature=0.0,
                                   use_cache=self.use_cache, max_tokens=4096)
        m = re.search(r"\{.*\}", raw, re.S)
        if not m:
            raise ValueError("LLM returned no JSON")
        return TaxResult.model_validate_json(m.group(0))
