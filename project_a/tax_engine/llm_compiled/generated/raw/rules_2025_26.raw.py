"""
Income Tax Calculator for Resident Salaried Individual (FY 2025-26)
Implements both Old and New Regime calculations per the provided rules.
"""

from fractions import Fraction
from math import floor, ceil

# =============================================================================
# MODULE-LEVEL CONSTANTS (with rule IDs as comments)
# =============================================================================

# [R1] STANDARD DEDUCTION
STANDARD_DEDUCTION_OLD = 50000
STANDARD_DEDUCTION_NEW = 75000

# [R2] HRA EXEMPTION LIMITS (percent of basic)
HRA_PERCENT_Metro = 50
HRA_PERCENT_Other = 40

# [R3] SECTION 80C
LIMIT_80C = 150000

# [R4] SECTION 80CCD(1B)
LIMIT_80CCD1B = 50000

# [R5] SECTION 80D
LIMIT_80D_SELF = 25000
LIMIT_80D_SELF_SENIOR = 50000
LIMIT_80D_PARENTS = 25000
LIMIT_80D_PARENTS_SENIOR = 50000

# [R6] SECTION 24(b) HOME LOAN INTEREST
LIMIT_24B = 200000

# [R9] ROUNDING OF INCOME (Sec 288A)
def round_income(amount: int) -> int:
    """Round to nearest multiple of 10 (5 or more rounds up)."""
    return (amount + 5) // 10 * 10

# [R10] OLD REGIME RATES
OLD_SLABS = [
    (250000, 0),
    (500000, 5),
    (1000000, 20),
    (float('inf'), 30)
]

# Age-based nil slab for old regime
OLD_NIL_SLAB = {
    'below_60': 250000,
    'senior_60_79': 300000,
    'senior_80_plus': 500000
}

# [R11] NEW REGIME RATES (FY 2025-26)
NEW_SLABS = [
    (400000, 0),
    (800000, 5),
    (1200000, 10),
    (1600000, 15),
    (2000000, 20),
    (2400000, 25),
    (float('inf'), 30)
]

# [R12] REBATE UNDER 87A
REBATE_87A_OLD_LIMIT = 500000
REBATE_87A_OLD_AMOUNT = 12500

REBATE_87A_NEW_LIMIT = 1200000
REBATE_87A_NEW_AMOUNT = 60000

# [R13] SURCHARGE
SURCHARGE_RATES = {
    5000000: 0.10,
    10000000: 0.15,
    20000000: 0.25,
    50000000: 0.37  # Old regime only
}
SURCHARGE_NEW_MAX = 0.25  # New regime cap

# [R14] CESS
CESS_RATE = 0.04

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def calculate_tax_on_slabs(income: int, slabs: list, nil_slab: int = 0) -> int:
    """
    Calculate tax on income using given slabs.
    slabs: list of (limit, rate) tuples.
    nil_slab: income up to this amount is tax-free.
    Returns tax as integer (rounded to nearest rupee).
    """
    tax = 0
    prev_limit = nil_slab
    
    for limit, rate in slabs:
        if limit == float('inf'):
            limit = income + 1  # Ensure we cover all remaining income
            break
        
        taxable_in_this_slab = min(income, limit) - prev_limit
        if taxable_in_this_slab > 0:
            tax += int(taxable_in_this_slab * rate / 100)
        
        prev_limit = limit
    
    return tax

def calculate_surcharge(tax_after_rebate: int, total_income: int, is_new_regime: bool) -> int:
    """
    Calculate surcharge based on total income.
    Applies marginal relief if applicable.
    """
    if tax_after_rebate <= 0:
        return 0
    
    # Determine applicable surcharge rates
    if is_new_regime:
        # New regime: max 25%
        if total_income > 20000000:
            rate = 0.25
        elif total_income > 10000000:
            rate = 0.15
        elif total_income > 5000000:
            rate = 0.10
        else:
            rate = 0
    else:
        # Old regime
        if total_income > 50000000:
            rate = 0.37
        elif total_income > 20000000:
            rate = 0.25
        elif total_income > 10000000:
            rate = 0.15
        elif total_income > 5000000:
            rate = 0.10
        else:
            rate = 0
    
    surcharge = int(tax_after_rebate * rate / 100)
    
    # Marginal relief check (applies to both regimes per rules)
    # Tax + surcharge cannot exceed (tax + surcharge at threshold) + (income - threshold)
    # For simplicity, we check if surcharge exceeds the marginal relief limit
    
    if total_income > 50000000:  # Old regime highest threshold
        threshold = 50000000
        rate_below = 0.25
        tax_at_threshold = calculate_tax_on_slabs(50000000, OLD_SLABS, OLD_NIL_SLAB['senior_80_plus'])
        surcharge_at_threshold = int(tax_at_threshold * rate_below / 100)
        max_payable = tax_at_threshold + surcharge_at_threshold + (total_income - threshold)
        if tax_after_rebate + surcharge > max_payable:
            surcharge = max_payable - tax_after_rebate
    
    elif total_income > 20000000:
        threshold = 20000000
        rate_below = 0.15
        tax_at_threshold = calculate_tax_on_slabs(20000000, OLD_SLABS, OLD_NIL_SLAB['senior_80_plus'])
        surcharge_at_threshold = int(tax_at_threshold * rate_below / 100)
        max_payable = tax_at_threshold + surcharge_at_threshold + (total_income - threshold)
        if tax_after_rebate + surcharge > max_payable:
            surcharge = max_payable - tax_after_rebate
    
    elif total_income > 10000000:
        threshold = 10000000
        rate_below = 0.10
        tax_at_threshold = calculate_tax_on_slabs(10000000, OLD_SLABS, OLD_NIL_SLAB['senior_80_plus'])
        surcharge_at_threshold = int(tax_at_threshold * rate_below / 100)
        max_payable = tax_at_threshold + surcharge_at_threshold + (total_income - threshold)
        if tax_after_rebate + surcharge > max_payable:
            surcharge = max_payable - tax_after_rebate
    
    elif total_income > 5000000:
        threshold = 5000000
        rate_below = 0
        tax_at_threshold = calculate_tax_on_slabs(5000000, OLD_SLABS, OLD_NIL_SLAB['senior_80_plus'])
        surcharge_at_threshold = 0
        max_payable = tax_at_threshold + surcharge_at_threshold + (total_income - threshold)
        if tax_after_rebate + surcharge > max_payable:
            surcharge = max_payable - tax_after_rebate
    
    return surcharge

def calculate_87a_rebate(tax_before_surcharge: int, total_income: int, is_new_regime: bool) -> int:
    """
    Calculate rebate under Section 87A.
    Returns the rebate amount (negative value for tax calculation).
    """
    if is_new_regime:
        if total_income <= REBATE_87A_NEW_LIMIT:
            rebate = min(tax_before_surcharge, REBATE_87A_NEW_AMOUNT)
        else:
            # Marginal relief: tax cannot exceed (income - 1200000)
            max_tax = total_income - REBATE_87A_NEW_LIMIT
            if tax_before_surcharge > max_tax:
                rebate = tax_before_surcharge - max_tax
            else:
                rebate = min(tax_before_surcharge, REBATE_87A_NEW_AMOUNT)
    else:
        if total_income <= REBATE_87A_OLD_LIMIT:
            rebate = min(tax_before_surcharge, REBATE_87A_OLD_AMOUNT)
        else:
            rebate = 0
    
    return rebate

def calculate_cess(tax_after_surcharge: int) -> int:
    """Calculate 4% health and education cess."""
    return int(tax_after_surcharge * CESS_RATE / 100)

def round_final_amount(amount: int) -> int:
    """Round to nearest multiple of 10 (5 or more rounds up)."""
    return (amount + 5) // 10 * 10

def get_age_category(age: int) -> str:
    """Return age category for old regime."""
    if age >= 80:
        return 'senior_80_plus'
    elif age >= 60:
        return 'senior_60_79'
    else:
        return 'below_60'

# =============================================================================
# MAIN CALCULATION FUNCTION
# =============================================================================

def calculate(inp: dict) -> dict:
    """
    Calculate income tax under both old and new regimes.
    Returns a dict with results for both regimes and recommendation.
    """
    fy = inp['fy']
    age = inp['age']
    gross_salary = inp['gross_salary']
    basic_salary = inp['basic_salary']
    hra_received = inp['hra_received']
    rent_paid = inp['rent_paid']
    metro_city = inp['metro_city']
    sec_80c = inp['sec_80c']
    sec_80ccd_1b = inp['sec_80ccd_1b']
    sec_80d_self = inp['sec_80d_self']
    sec_80d_parents = inp['sec_80d_parents']
    parents_senior = inp['parents_senior']
    self_senior = inp['self_senior']
    home_loan_interest = inp['home_loan_interest']
    
    # Ensure non-negative inputs
    gross_salary = max(0, gross_salary)
    basic_salary = max(0, basic_salary)
    hra_received = max(0, hra_received)
    rent_paid = max(0, rent_paid)
    sec_80c = max(0, sec_80c)
    sec_80ccd_1b = max(0, sec_80ccd_1b)
    sec_80d_self = max(0, sec_80d_self)
    sec_80d_parents = max(0, sec_80d_parents)
    home_loan_interest = max(0, home_loan_interest)
    
    # Calculate Old Regime
    old_result = calculate_old_regime(
        age, gross_salary, basic_salary, hra_received, rent_paid,
        metro_city, sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
        parents_senior, self_senior, home_loan_interest
    )
    
    # Calculate New Regime
    new_result = calculate_new_regime(
        age, gross_salary, basic_salary, hra_received, rent_paid,
        metro_city, sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
        parents_senior, self_senior, home_loan_interest
    )
    
    # Determine recommendation
    if new_result['total_tax'] <= old_result['total_tax']:
        recommended = 'new'
        explanation = f"New regime is better by Rs {new_result['total_tax'] - old_result['total_tax']}"
    else:
        recommended = 'old'
        explanation = f"Old regime is better by Rs {old_result['total_tax'] - new_result['total_tax']}"
    
    return {
        'old': old_result,
        'new': new_result,
        'recommended': recommended,
        'explanation': explanation
    }

def calculate_old_regime(age, gross_salary, basic_salary, hra_received, rent_paid,
                         metro_city, sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
                         parents_senior, self_senior, home_loan_interest):
    """Calculate tax under old regime."""
    trace = []
    
    # Gross salary
    trace.append({'label': 'Gross salary', 'amount': gross_salary, 'clause': 'Sec 17', 'group': 'income'})
    
    # Standard deduction [R1]
    std_ded = min(STANDARD_DEDUCTION_OLD, gross_salary)
    trace.append({'label': f'Standard deduction', 'amount': -std_ded, 'clause': 'Sec 16(ia)', 'group': 'income'})
    
    # HRA exemption [R2]
    hra_exemption = 0
    if hra_received > 0 and rent_paid > 0:
        # (a) HRA received
        hra_a = hra_received
        
        # (b) 50% or 40% of basic salary
        if metro_city:
            hra_b = int(basic_salary * HRA_PERCENT_Metro / 100)
        else:
            hra_b = int(basic_salary * HRA_PERCENT_Other / 100)
        
        # (c) Rent paid - 10% of salary
        hra_c = rent_paid - int(basic_salary * 10 / 100)
        if hra_c < 0:
            hra_c = 0
        
        hra_exemption = min(hra_a, hra_b, hra_c)
    
    if hra_exemption > 0:
        trace.append({'label': 'HRA exemption', 'amount': -hra_exemption, 'clause': 'Sec 10(13A)', 'group': 'income'})
    
    # Section 80C [R3]
    if sec_80c > 0:
        trace.append({'label': 'Section 80C', 'amount': -sec_80c, 'clause': 'Sec 80C', 'group': 'income'})
    
    # Section 80CCD(1B) [R4]
    if sec_80ccd_1b > 0:
        trace.append({'label': 'Section 80CCD(1B)', 'amount': -sec_80ccd_1b, 'clause': 'Sec 80CCD(1B)', 'group': 'income'})
    
    # Section 80D [R5]
    # Self
    if sec_80d_self > 0:
        limit_80d_self = LIMIT_80D_SELF_SENIOR if self_senior else LIMIT_80D_SELF
        actual_80d_self = min(sec_80d_self, limit_80d_self)
        trace.append({'label': 'Section 80D (self)', 'amount': -actual_80d_self, 'clause': 'Sec 80D', 'group': 'income'})
    
    # Parents
    if sec_80d_parents > 0:
        limit_80d_parents = LIMIT_80D_PARENTS_SENIOR if parents_senior else LIMIT_80D_PARENTS
        actual_80d_parents = min(sec_80d_parents, limit_80d_parents)
        trace.append({'label': 'Section 80D (parents)', 'amount': -actual_80d_parents, 'clause': 'Sec 80D', 'group': 'income'})
    
    # Section 24(b) Home loan interest [R6]
    if home_loan_interest > 0:
        actual_24b = min(home_loan_interest, LIMIT_24B)
        trace.append({'label': 'Home loan interest', 'amount': -actual_24b, 'clause': 'Sec 24(b)', 'group': 'income'})
    
    # Calculate total income before rounding
    total_income_before_rounding = gross_salary - std_ded - hra_exemption - sec_80c - sec_80ccd_1b - actual_80d_self - actual_80d_parents - actual_24b
    
    # Ensure non-negative
    if total_income_before_rounding < 0:
        total_income_before_rounding = 0
    
    # Round income [R9]
    taxable_income = round_income(total_income_before_rounding)
    
    # Add rounding line if needed
    if total_income_before_rounding != taxable_income:
        trace.append({'label': 'Rounding / floor at zero', 'amount': taxable_income - total_income_before_rounding, 'clause': 'Sec 288A', 'group': 'income'})
    
    # Calculate tax on slabs [R10]
    age_category = get_age_category(age)
    nil_slab = OLD_NIL_SLAB[age_category]
    tax_before_rebate = calculate_tax_on_slabs(taxable_income, OLD_SLABS, nil_slab)
    
    # Apply 87A rebate [R12]
    rebate_87a = calculate_87a_rebate(tax_before_rebate, taxable_income, False)
    tax_after_rebate = tax_before_rebate - rebate_87a
    
    # Calculate surcharge [R13]
    surcharge = calculate_surcharge(tax_after_rebate, taxable_income, False)
    tax_after_surcharge = tax_after_rebate + surcharge
    
    # Calculate cess [R14]
    cess = calculate_cess(tax_after_surcharge)
    total_tax_before_rounding = tax_after_surcharge + cess
    
    # Round final amount [R15]
    total_tax = round_final_amount(total_tax_before_rounding)
    
    # Add tax trace lines
    trace.append({'label': 'Tax on slabs', 'amount': tax_before_rebate, 'clause': 'Sec 115BAC(1A)', 'group': 'tax'})
    if rebate_87a > 0:
        trace.append({'label': 'Rebate 87A', 'amount': -rebate_87a, 'clause': 'Sec 87A', 'group': 'tax'})
    if surcharge > 0:
        trace.append({'label': 'Surcharge', 'amount': surcharge, 'clause': 'Sec 2(37)', 'group': 'tax'})
    if cess > 0:
        trace.append({'label': 'Cess', 'amount': cess, 'clause': 'Sec 1(45)', 'group': 'tax'})
    if total_tax_before_rounding != total_tax:
        trace.append({'label': 'Rounding of amount payable', 'amount': total_tax - total_tax_before_rounding, 'clause': 'Sec 288B', 'group': 'tax'})
    
    return {
        'regime': 'old',
        'taxable_income': taxable_income,
        'tax_before_rebate': tax_before_rebate,
        'rebate_87a': rebate_87a,
        'surcharge': surcharge,
        'cess': cess,
        'total_tax': total_tax,
        'trace': trace
    }

def calculate_new_regime(age, gross_salary, basic_salary, hra_received, rent_paid,
                         metro_city, sec_80c, sec_80ccd_1b, sec_80d_self, sec_80d_parents,
                         parents_senior, self_senior, home_loan_interest):
    """Calculate tax under new regime."""
    trace = []
    
    # Gross salary
    trace.append({'label': 'Gross salary', 'amount': gross_salary, 'clause': 'Sec 17', 'group': 'income'})
    
    # Standard deduction [R1]
    std_ded = min(STANDARD_DEDUCTION_NEW, gross_salary)
    trace.append({'label': f'Standard deduction', 'amount': -std_ded, 'clause': 'Sec 115BAC(1A)(ii)', 'group': 'income'})
    
    # Note: No HRA, 80C, 80CCD(1B), 80D, or 24(b) deductions in new regime [R7]
    
    # Calculate total income before rounding
    total_income_before_rounding = gross_salary - std_ded
    
    # Ensure non-negative
    if total_income_before_rounding < 0:
        total_income_before_rounding = 0
    
    # Round income [R9]
    taxable_income = round_income(total_income_before_rounding)
    
    # Add rounding line if needed
    if total_income_before_rounding != taxable_income:
        trace.append({'label': 'Rounding / floor at zero', 'amount': taxable_income - total_income_before_rounding, 'clause': 'Sec 288A', 'group': 'income'})
    
    # Calculate tax on slabs [R11]
    tax_before_rebate = calculate_tax_on_slabs(taxable_income, NEW_SLABS, 0)
    
    # Apply 87A rebate [R12]
    rebate_87a = calculate_87a_rebate(tax_before_rebate, taxable_income, True)
    tax_after_rebate = tax_before_rebate - rebate_87a
    
    # Calculate surcharge [R13]
    surcharge = calculate_surcharge(tax_after_rebate, taxable_income, True)
    tax_after_surcharge = tax_after_rebate + surcharge
    
    # Calculate cess [R14]
    cess = calculate_cess(tax_after_surcharge)
    total_tax_before_rounding = tax_after_surcharge + cess
    
    # Round final amount [R15]
    total_tax = round_final_amount(total_tax_before_rounding)
    
    # Add tax trace lines
    trace.append({'label': 'Tax on slabs', 'amount': tax_before_rebate, 'clause': 'Sec 115BAC(1A)', 'group': 'tax'})
    if rebate_87a > 0:
        trace.append({'label': 'Rebate 87A', 'amount': -rebate_87a, 'clause': 'Sec 87A', 'group': 'tax'})
    if surcharge > 0:
        trace.append({'label': 'Surcharge', 'amount': surcharge, 'clause': 'Sec 2(37)', 'group': 'tax'})
    if cess > 0:
        trace.append({'label': 'Cess', 'amount': cess, 'clause': 'Sec 1(45)', 'group': 'tax'})
    if total_tax_before_rounding != total_tax:
        trace.append({'label': 'Rounding of amount payable', 'amount': total_tax - total_tax_before_rounding, 'clause': 'Sec 288B', 'group': 'tax'})
    
    return {
        'regime': 'new',
        'taxable_income': taxable_income,
        'tax_before_rebate': tax_before_rebate,
        'rebate_87a': rebate_87a,
        'surcharge': surcharge,
        'cess': cess,
        'total_tax': total_tax,
        'trace': trace
    }
