"""
Income Tax Calculator for Resident Salaried Individual (FY 2024-25)
Implements both Old and New Regime calculations per Finance Act 2024.
"""

from fractions import Fraction
import math

# =============================================================================
# MODULE-LEVEL CONSTANTS (with rule IDs as comments)
# =============================================================================

# [R1] STANDARD DEDUCTION
STANDARD_DEDUCTION_OLD = 50000
STANDARD_DEDUCTION_NEW = 75000

# [R2] HRA EXEMPTION LIMITS (percentages of basic salary)
HRA_PERCENT_Metro = 0.50
HRA_PERCENT_Other = 0.40
Metros = {"Delhi", "Mumbai", "Kolkata", "Chennai"}

# [R3] SECTION 80C LIMIT
LIMIT_80C = 150000

# [R4] SECTION 80CCD(1B) LIMIT
LIMIT_80CCD_1B = 50000

# [R5] SECTION 80D LIMITS
LIMIT_80D_SELF = 25000
LIMIT_80D_SELF_SENIOR = 50000
LIMIT_80D_PARENTS = 25000
LIMIT_80D_PARENTS_SENIOR = 50000

# [R6] SECTION 24(b) HOUSE LOAN INTEREST LIMIT
LIMIT_HOUSE_LOAN_INTEREST = 200000

# [R10] OLD REGIME SLABS
OLD_SLABS = [
    (0, 250000, 0),
    (250001, 500000, 0.05),
    (500001, 1000000, 0.20),
    (1000001, float('inf'), 0.30),
]

# [R11] NEW REGIME SLABS
NEW_SLABS = [
    (0, 300000, 0),
    (300001, 700000, 0.05),
    (700001, 1000000, 0.10),
    (1000001, 1200000, 0.15),
    (1200001, 1500000, 0.20),
    (1500001, float('inf'), 0.30),
]

# [R12] REBATE UNDER 87A
REBATE_87A_OLD_LIMIT = 500000
REBATE_87A_OLD_AMOUNT = 12500
REBATE_87A_NEW_LIMIT = 700000
REBATE_87A_NEW_AMOUNT = 25000

# [R13] SURCHARGE RATES
SURCHARGE_RATES = {
    5000000: 0.10,
    10000000: 0.15,
    20000000: 0.25,
    50000000: 0.37,  # Old regime only
}
SURCHARGE_MAX_NEW = 0.25  # New regime cap

# [R14] CESS RATE
CESS_RATE = 0.04

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def round_to_nearest_10(value: int) -> int:
    """
    [R9] Sec 288A: Round to nearest multiple of 10.
    If last digit is 5 or more, round up; otherwise round down.
    """
    if value < 0:
        return -round_to_nearest_10(-value)
    return (value + 5) // 10 * 10

def round_tax_amount(value: int) -> int:
    """
    [R15] Sec 288B: Round final tax payable to nearest multiple of 10.
    """
    return round_to_nearest_10(value)

def calculate_tax_on_slabs(income: int, slabs: list) -> int:
    """
    Calculate tax based on progressive slabs.
    Returns tax before any rebate.
    """
    tax = 0
    prev_limit = 0
    for limit, rate in slabs:
        if limit == float('inf'):
            taxable_in_this_slab = income - prev_limit
        else:
            taxable_in_this_slab = min(income, limit) - prev_limit
        
        if taxable_in_this_slab > 0:
            tax += int(taxable_in_this_slab * rate)
        
        prev_limit = limit
        if prev_limit >= income:
            break
    
    return tax

def calculate_surcharge(tax_after_rebate: int, total_income: int, is_new_regime: bool) -> int:
    """
    [R13] Calculate surcharge based on total income.
    """
    if tax_after_rebate <= 0:
        return 0
    
    surcharge_rate = 0.0
    threshold = 0
    
    # Determine applicable surcharge rate
    if is_new_regime:
        # New regime: max 25%
        if total_income > 5000000:
            surcharge_rate = SURCHARGE_MAX_NEW
        elif total_income > 2000000:
            surcharge_rate = 0.25
        elif total_income > 1000000:
            surcharge_rate = 0.15
        elif total_income > 500000:
            surcharge_rate = 0.10
    else:
        # Old regime
        if total_income > 50000000:
            surcharge_rate = 0.37
        elif total_income > 20000000:
            surcharge_rate = 0.25
        elif total_income > 10000000:
            surcharge_rate = 0.15
        elif total_income > 5000000:
            surcharge_rate = 0.10
    
    surcharge = int(tax_after_rebate * surcharge_rate)
    return surcharge

def calculate_cess(tax_plus_surcharge: int) -> int:
    """
    [R14] Health and Education Cess: 4% of (tax + surcharge)
    """
    return int(tax_plus_surcharge * CESS_RATE)

def calculate_87a_rebate(total_income: int, is_new_regime: bool) -> tuple:
    """
    [R12] Calculate rebate under 87A.
    Returns (rebate_amount, is_marginal_relief_applied)
    """
    if is_new_regime:
        if total_income <= REBATE_87A_NEW_LIMIT:
            return REBATE_87A_NEW_AMOUNT, False
        else:
            # Marginal relief: tax cannot exceed (income - threshold)
            excess_income = total_income - REBATE_87A_NEW_LIMIT
            return excess_income, True
    else:
        if total_income <= REBATE_87A_OLD_LIMIT:
            return REBATE_87A_OLD_AMOUNT, False
        else:
            # Old regime: no marginal relief mentioned, but rebate is capped at tax
            # If income > limit, rebate = 0
            return 0, False

def calculate_hra_exemption(basic_salary: int, hra_received: int, rent_paid: int, metro_city: bool) -> int:
    """
    [R2] HRA Exemption calculation
    """
    if hra_received <= 0 or rent_paid <= 0:
        return 0
    
    # (b) Percentage of salary
    if metro_city:
        percent = HRA_PERCENT_Metro
    else:
        percent = HRA_PERCENT_Other
    
    limit_b = int(basic_salary * percent)
    
    # (c) Rent paid minus 10% of salary
    limit_c = rent_paid - int(basic_salary * 0.10)
    
    # Exemption is the least of (a), (b), (c)
    exemption = min(hra_received, limit_b, limit_c)
    
    return max(0, exemption)

def calculate_old_regime_deductions(gross_salary: int, basic_salary: int, 
                                    sec_80c: int, sec_80ccd_1b: int,
                                    sec_80d_self: int, sec_80d_parents: int,
                                    parents_senior: bool, self_senior: bool,
                                    home_loan_interest: int) -> int:
    """
    Calculate total deductions under old regime.
    """
    deductions = 0
    
    # [R1] Standard deduction
    deductions += min(gross_salary, STANDARD_DEDUCTION_OLD)
    
    # [R2] HRA exemption
    hra_exemption = calculate_hra_exemption(basic_salary, 0, 0, False)  # metro_city not needed for deduction calc
    deductions += hra_exemption
    
    # [R3] Section 80C
    deductions += min(sec_80c, LIMIT_80C)
    
    # [R4] Section 80CCD(1B)
    deductions += min(sec_80ccd_1b, LIMIT_80CCD_1B)
    
    # [R5] Section 80D
    # Self, spouse, children
    if self_senior:
        deductions += min(sec_80d_self, LIMIT_80D_SELF_SENIOR)
    else:
        deductions += min(sec_80d_self, LIMIT_80D_SELF)
    
    # Parents
    if parents_senior:
        deductions += min(sec_80d_parents, LIMIT_80D_PARENTS_SENIOR)
    else:
        deductions += min(sec_80d_parents, LIMIT_80D_PARENTS)
    
    # [R6] House loan interest (set off against salary)
    deductions += min(home_loan_interest, LIMIT_HOUSE_LOAN_INTEREST)
    
    return deductions

def calculate_new_regime_deductions(gross_salary: int) -> int:
    """
    [R7] New regime: Only standard deduction applies.
    """
    return min(gross_salary, STANDARD_DEDUCTION_NEW)

def compute_regime(gross_salary: int, basic_salary: int, hra_received: int, 
                   rent_paid: int, metro_city: bool, sec_80c: int, 
                   sec_80ccd_1b: int, sec_80d_self: int, sec_80d_parents: int,
                   parents_senior: bool, self_senior: bool, home_loan_interest: int,
                   is_new_regime: bool) -> dict:
    """
    Compute tax for a single regime.
    """
    trace = []
    
    # Calculate deductions
    if is_new_regime:
        deductions = calculate_new_regime_deductions(gross_salary)
    else:
        deductions = calculate_old_regime_deductions(
            gross_salary, basic_salary, sec_80c, sec_80ccd_1b,
            sec_80d_self, sec_80d_parents, parents_senior, self_senior,
            home_loan_interest
        )
    
    # Total income before rounding
    total_income_before_rounding = gross_salary - deductions
    
    # [R9] Round to nearest 10
    taxable_income = round_to_nearest_10(total_income_before_rounding)
    
    # Build income trace
    income_trace = [
        {"label": "Gross salary", "amount": gross_salary, "clause": "Salary Income", "group": "income"},
        {"label": "Deductions", "amount": -deductions, "clause": "Sec 16(ia)/80C/80D/80CCD/24(b)", "group": "income"}
    ]
    
    # Add rounding line if needed
    if total_income_before_rounding != taxable_income:
        income_trace.append({
            "label": "Rounding / floor at zero", 
            "amount": taxable_income - total_income_before_rounding, 
            "clause": "Sec 288A", 
            "group": "income"
        })
    
    # Ensure taxable_income is not negative
    if taxable_income < 0:
        taxable_income = 0
    
    # Calculate tax based on regime
    if is_new_regime:
        slabs = NEW_SLABS
    else:
        slabs = OLD_SLABS
    
    tax_before_rebate = calculate_tax_on_slabs(taxable_income, slabs)
    
    # [R12] Rebate under 87A
    rebate_amount, marginal_relief_applied = calculate_87a_rebate(taxable_income, is_new_regime)
    
    tax_after_rebate = tax_before_rebate - rebate_amount
    if tax_after_rebate < 0:
        tax_after_rebate = 0
    
    # [R13] Surcharge
    surcharge = calculate_surcharge(tax_after_rebate, taxable_income, is_new_regime)
    
    # Marginal relief for new regime if applicable
    if is_new_regime and marginal_relief_applied:
        excess_income = taxable_income - REBATE_87A_NEW_LIMIT
        max_tax = excess_income
        if tax_after_rebate + surcharge > max_tax:
            tax_after_rebate = max_tax - surcharge
            if tax_after_rebate < 0:
                tax_after_rebate = 0
    
    # [R14] Cess
    tax_plus_surcharge = tax_after_rebate + surcharge
    cess = calculate_cess(tax_plus_surcharge)
    
    # Total tax before rounding
    total_tax_before_rounding = tax_after_rebate + surcharge + cess
    
    # [R15] Round final tax
    total_tax = round_tax_amount(total_tax_before_rounding)
    
    # Build tax trace
    tax_trace = [
        {"label": "Tax on slabs", "amount": tax_before_rebate, "clause": "Sec 10(1)/115BAC", "group": "tax"},
        {"label": "Rebate 87A", "amount": -rebate_amount, "clause": "Sec 87A", "group": "tax"}
    ]
    
    if tax_before_rebate != tax_after_rebate + surcharge + cess:
        # Add intermediate lines for clarity
        pass
    
    tax_trace.append({
        "label": "Surcharge", 
        "amount": surcharge, 
        "clause": "Sec 2(37)", 
        "group": "tax"
    })
    
    tax_trace.append({
        "label": "Cess", 
        "amount": cess, 
        "clause": "Sec 115B", 
        "group": "tax"
    })
    
    # Add rounding line if needed
    if total_tax_before_rounding != total_tax:
        tax_trace.append({
            "label": "Rounding of amount payable", 
            "amount": total_tax - total_tax_before_rounding, 
            "clause": "Sec 288B", 
            "group": "tax"
        })
    
    return {
        "regime": "new" if is_new_regime else "old",
        "taxable_income": taxable_income,
        "tax_before_rebate": tax_before_rebate,
        "rebate_87a": rebate_amount,
        "surcharge": surcharge,
        "cess": cess,
        "total_tax": total_tax,
        "trace": income_trace + tax_trace
    }

def calculate(inp: dict) -> dict:
    """
    Main entry point for income tax calculation.
    """
    # Extract inputs
    fy = inp.get("fy", "2024-25")
    age = inp.get("age", 0)
    gross_salary = inp.get("gross_salary", 0)
    basic_salary = inp.get("basic_salary", 0)
    hra_received = inp.get("hra_received", 0)
    rent_paid = inp.get("rent_paid", 0)
    metro_city = inp.get("metro_city", False)
    sec_80c = inp.get("sec_80c", 0)
    sec_80ccd_1b = inp.get("sec_80ccd_1b", 0)
    sec_80d_self = inp.get("sec_80d_self", 0)
    sec_80d_parents = inp.get("sec_80d_parents", 0)
    parents_senior = inp.get("parents_senior", False)
    self_senior = inp.get("self_senior", False)
    home_loan_interest = inp.get("home_loan_interest", 0)
    
    # Determine senior citizen status
    is_senior = age >= 60
    
    # Compute both regimes
    old_result = compute_regime(
        gross_salary, basic_salary, hra_received, rent_paid, metro_city,
        sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
        parents_senior, self_senior, home_loan_interest,
        is_new_regime=False
    )
    
    new_result = compute_regime(
        gross_salary, basic_salary, hra_received, rent_paid, metro_city,
        sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
        parents_senior, self_senior, home_loan_interest,
        is_new_regime=True
    )
    
    # Determine recommended regime
    old_total = old_result["total_tax"]
    new_total = new_result["total_tax"]
    
    if new_total <= old_total:
        recommended = "new"
        explanation = f"New regime is better by Rs {new_total - old_total}."
    else:
        recommended = "old"
        explanation = f"Old regime is better by Rs {old_total - new_total}."
    
    return {
        "old": old_result,
        "new": new_result,
        "recommended": recommended,
        "explanation": explanation
    }
