"""Hand-worked anchor cases. The arithmetic is written out so a human can re-check it.

All use age 30 unless stated. "taxable" is after the standard deduction and Sec 288A rounding.
Totals are after 4% cess and Sec 288B rounding.
"""
ANCHORS = [
    {"id": "anchor_new_at_87a_limit", "why":
     "gross 7,75,000 -> new taxable 7,00,000: slab tax 20,000, fully rebated -> 0. Old: taxable 7,25,000: "
     "12,500+20%x2,25,000=57,500, +4% cess = 59,800",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 775_000}, "old": 59_800, "new": 0},
    {"id": "anchor_new_marginal_relief", "why":
     "gross 7,85,000 -> new taxable 7,10,000: slab tax 21,000 but capped at income above 7L = 10,000; +4% = 10,400. "
     "Old: taxable 7,35,000: 12,500+20%x2,35,000=59,500, +4% = 61,880",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 785_000}, "old": 61_880, "new": 10_400},
    {"id": "anchor_new_15L", "why":
     "gross 15,00,000 -> new taxable 14,25,000: 20,000+30,000+30,000+20%x2,25,000=45,000 -> 1,25,000; +4% = 1,30,000",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 1_500_000}, "old": 257_400, "new": 130_000},
    {"id": "anchor_new_surcharge_10pct", "why":
     "gross 1,00,00,000 -> new taxable 99,25,000: tax 1,40,000+30%x84,25,000=26,67,500; surcharge 10% = 2,66,750; "
     "sum 29,34,250; cess 1,17,370 -> 30,51,620",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 10_000_000}, "old": 3_200_340, "new": 3_051_620},
    {"id": "anchor_new_surcharge_marginal_relief", "why":
     "gross 50,75,010 -> new taxable 50,00,010: tax 11,90,003; 10% surcharge would be 1,19,000 but tax+surcharge may "
     "exceed tax at 50L (11,90,000) by at most 10 -> 11,90,010; cess 47,600.4 -> 12,37,610",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 5_075_010}, "old": 1_391_010, "new": 1_237_610},
    {"id": "anchor_fy2526_new_at_12L", "why":
     "FY25-26 gross 12,75,000 -> new taxable 12,00,000: slab tax 60,000 fully rebated -> 0",
     "input": {"fy": "2025-26", "age": 30, "gross_salary": 1_275_000}, "old": 187_200, "new": 0},
    {"id": "anchor_fy2526_new_marginal_relief", "why":
     "FY25-26 gross 12,85,000 -> new taxable 12,10,000: slab tax 61,500 capped at income above 12L = 10,000; +4% = 10,400",
     "input": {"fy": "2025-26", "age": 30, "gross_salary": 1_285_000}, "old": 190_320, "new": 10_400},
    {"id": "anchor_old_rebate_cliff", "why":
     "old regime, gross 5,50,000 -> taxable 5,00,000: slab tax 12,500, rebate 12,500 -> 0 (old: no marginal relief)",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 550_000}, "old": 0, "new": 0},
    {"id": "anchor_old_just_over_rebate", "why":
     "old regime, gross 5,50,010 -> taxable 5,00,010 rounds to 5,00,010: 12,500+20%x10 = 12,502, no rebate, +4% = 13,002 -> 13,000",
     "input": {"fy": "2024-25", "age": 30, "gross_salary": 550_010}, "old": 13_000, "new": 0},
]
