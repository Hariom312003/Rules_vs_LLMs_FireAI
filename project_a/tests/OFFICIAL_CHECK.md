# Cross-checking against the Income Tax Department's official calculator

The brief requires **at least 30 cases checked against the official calculator**. That calculator is an interactive web form, so this step is manual and **has not been done**. All current `source` values in `cases*.jsonl` are therefore `oracle` or `hand_worked`, never `official_calc`.

## Steps (about 45 minutes)
1. Open https://www.incometax.gov.in -> Quick links / e-Calculators -> **Tax Calculator** (choose the assessment year matching the row's `fy`: FY 2024-25 = AY 2025-26).
2. For each row in `data/official_checklist.csv` enter: age category, salary income, then run **both** the old and the new regime. HRA, 80C, 80CCD(1B), 80D and home-loan interest go in the deduction fields (old regime only). Use "resident individual", "salary only", no other income.
3. Record the **total tax payable including surcharge and cess** into `official_old_total_tax` and `official_new_total_tax`, put your initials in `checked_by`, and use `notes` for anything the form did not allow (e.g. it rounded differently, or has no field for the input).
4. Run `python -m pytest project_a -q -k official`. Every filled row must match; a mismatch is a finding: decide whether our rule or the calculator is wrong and write it in `RESULTS_A.md`.
5. After at least 30 rows match, set `"source": "official_calc"` for those ids in `cases.jsonl` (or note the count in `RESULTS_A.md`).

Rows that fall exactly on rounding boundaries (the `+5`, `-5` offsets) are the most likely to expose a difference in the calculator's rounding of income (Sec 288A) and of tax (Sec 288B).
