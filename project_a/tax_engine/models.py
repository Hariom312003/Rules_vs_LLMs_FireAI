"""Shared input/output contract for all three implementations.

Money is integer rupees everywhere (no floats) so "rupee-exact" is a plain
equality check. Every rupee in a result must appear as a TraceLine carrying
the clause it came from -- that is how traceability is measured in Task 4.
"""
from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel, Field

Regime = Literal["old", "new"]


class TaxpayerInput(BaseModel):
    """Structured salaried-person profile. Amounts are annual, in rupees."""

    fy: Literal["2024-25", "2025-26"] = "2024-25"
    age: int = Field(ge=0, le=120)  # drives slab / senior-citizen limits
    gross_salary: int = Field(ge=0)
    basic_salary: int = Field(default=0, ge=0)  # HRA needs basic (+DA)
    hra_received: int = Field(default=0, ge=0)
    rent_paid: int = Field(default=0, ge=0)
    metro_city: bool = False  # 50% vs 40% HRA limit (Delhi/Mumbai/Kolkata/Chennai)
    sec_80c: int = Field(default=0, ge=0)
    sec_80ccd_1b: int = Field(default=0, ge=0)  # NPS additional
    sec_80d_self: int = Field(default=0, ge=0)
    sec_80d_parents: int = Field(default=0, ge=0)
    parents_senior: bool = False
    self_senior: bool = False
    home_loan_interest: int = Field(default=0, ge=0)  # self-occupied house


class TraceLine(BaseModel):
    """One rupee-amount in the answer and the clause it comes from.

    group "income": signed lines that sum to taxable_income
        (gross salary +, each deduction -, final rounding/floor adjustment).
    group "tax": signed lines that sum to total_tax
        (slab tax +, 87A rebate -, surcharge +, cess +, final rounding adjustment).
    """

    label: str  # e.g. "Standard deduction"
    amount: int  # signed rupees
    clause: str  # e.g. "Sec 16(ia)" -- required, never empty
    group: Literal["income", "tax"] = "tax"


class RegimeResult(BaseModel):
    regime: Regime
    taxable_income: int
    tax_before_rebate: int
    rebate_87a: int
    surcharge: int
    cess: int
    total_tax: int
    trace: list[TraceLine] = Field(default_factory=list)


class TaxResult(BaseModel):
    old: RegimeResult
    new: RegimeResult
    recommended: Regime
    explanation: str  # why this regime wins, in words


class Calculator(Protocol):
    """Every implementation (hand / llm_query / llm_compiled) satisfies this."""

    name: str

    def compute(self, inp: TaxpayerInput) -> TaxResult: ...
