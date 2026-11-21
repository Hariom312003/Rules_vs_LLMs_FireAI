# Sources and verification status

Retrieved 2026-11-20. The brief requires **official sources only**. Several government hosts (indiabudget.gov.in, incometaxindia.gov.in legacy paths, indiacode.nic.in, pib.gov.in) refused the automated fetch tool (HTTP 403). What was actually read:

| Source (official) | Used for |
|---|---|
| https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-1 ("Salaried Individuals for AY 2026-27", reviewed 09-Jul-2026), read directly | FY 2025-26 new-regime slabs, 87A limits (Rs 12,500 / 5L old; Rs 60,000 / 12L new), old-regime slabs by age, surcharge bands and the 25% new-regime cap, cess 4%, 80C Rs 1.5L, 80CCD(1B) Rs 50k, 80D limits, 24(b) Rs 2L, deductions barred in the new regime |
| https://www.incometax.gov.in/iec/foportal/help/individual/return-applicable-2 (senior / super-senior page, AY 2026-27) | senior-citizen old-regime slabs |
| Search-result excerpts of Income Tax Dept / PIB pages (the pages themselves returned 403 to the fetch tool): PIB "Summary of the Union Budget" 2024-07-23 (https://static.pib.gov.in/WriteReadData/specificdocs/documents/2024/jul/doc2024723352501.pdf), incometax.gov.in "New vs Old Tax Regime FAQs", incometaxindia.gov.in "Section 87A" (https://wm.incometaxindia.gov.in/web/guest/w/section-87a-24) | FY 2024-25 new-regime slabs (3/7/10/12/15 lakh), standard deduction Rs 50,000 old / Rs 75,000 new, 87A Rs 25,000 up to Rs 7L and its marginal relief |
| https://www.incometaxindia.gov.in/w/section-288a-53 and https://www.incometaxindia.gov.in/w/section-288b-59 (excerpts) | Rounding of income and tax to the nearest Rs 10, digit 5 rounds up |

## Verification table

| Clause | Status | Note |
|---|---|---|
| R1 standard deduction, R11/R12 FY24-25 and FY25-26 slabs and rebates, R13 surcharge, R14 cess, R15 rounding | V | official page or official excerpt read |
| R3-R7 deduction limits | V | incometax.gov.in salaried page (AY 2026-27 table; limits not separately shown for AY 2025-26) |
| R10 old-regime slabs FY 2024-25 | V* | shown on the AY 2026-27 page; Finance Act 2024 did not change them (stated in the Budget 2024 summary, no change to old regime) |
| R2 HRA (Sec 10(13A), Rule 2A) | **S** | well-established statutory rule, **not fetched from an official page in this session** |
| R12 87A marginal relief for FY 2025-26 (above Rs 12L) | **S** | Finance Act 2025 text not fetched; modelled like the FY 2024-25 provision |
| R13 surcharge marginal relief formula | **S** | wording of the Finance Act schedule not fetched; page describes the principle |

## What a human must still do (before submitting)
1. Open the Income Tax Department's official calculator (https://www.incometax.gov.in -> e-Calculators -> Tax calculator) and fill `project_a/tests/data/official_checklist.csv` (instructions inside). The brief requires at least 30 cases checked against it; **this has not been done** because the calculator is an interactive form.
2. Confirm the rows marked S against the Finance Act 2024 / Finance Act 2025 text (egazette.gov.in or indiacode.nic.in) and the Income-tax Rules (Rule 2A).
3. Replace "V*" with a direct citation if a stricter source is required.
