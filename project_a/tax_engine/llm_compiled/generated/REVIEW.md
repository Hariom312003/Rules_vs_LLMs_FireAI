# Review of the LLM-compiled rules

Model: Qwen3.5-9B (Q4_K_M, local, thinking off). Compile time 104.9 s, 2,527 tokens in / 4,280 out, one call.
Raw output: `raw/rules_2024_25.raw.py` (425 lines, never edited). Reviewed file: `rules_2024_25.py` (changes marked `# REVIEW: Dn`).
Reviewer: Claude Code (AI assistant), 2026-11-20. **A human must re-read this file against `rules_source/fy2024_25.txt` before submission.** The raw output was read once top to bottom, then the suite (258 cases) was run to find what reading missed.

## What the raw output did on the suite
All 258 cases raised `ValueError: too many values to unpack` (a loud failure, D1). After applying ONLY the mechanical fix for D1, the module stopped crashing but was **silently wrong on 194 of 256 cases (case-exact 24%, per-regime exact 44%)**: the crash hid the other defects, and fixing it exposed them without any error. Measured by `eval/run_change.py` (`raw_after_crash_fix_only`).

## Defects found
| # | Defect in the LLM's code | Kind | How found |
|---|---|---|---|
| D1 | `OLD_SLABS` / `NEW_SLABS` are 3-tuples (low, high, rate) but `calculate_tax_on_slabs` unpacks `(limit, rate)` | crash (loud) | running the suite |
| D2 | Slab tax and cess computed with float rates and `int()` truncation | silent (off by rupees) | reading |
| D3 | Slab ranges written as 250001..500000 (off-by-one style) | cosmetic once D1 fixed | reading |
| D4 | 87A: returns the full cap (25,000 / 12,500) not `min(tax, cap)`; marginal relief returns the *excess income* as the rebate, so tax becomes `tax - excess` instead of `min(tax, excess)` | silent wrong | reading + suite |
| D5 | New-regime surcharge ladder wrong: income > 5,000,000 gets 25%, > 1,000,000 gets 15%, > 500,000 gets 10% (so a Rs 8L earner is charged surcharge) | silent wrong, large | reading |
| D6 | No marginal relief on surcharge at all | silent wrong near 50L/1Cr/2Cr/5Cr | reading |
| D7 | HRA exemption is called with `hra_received=0, rent_paid=0, metro=False` ("metro_city not needed"), so HRA never applies | silent wrong | reading |
| D8 | `self_senior` ignored; computed `is_senior = age >= 60` is never used | silent wrong for seniors (80D) | reading |
| D9 | Chapter VI-A deductions not capped at gross total income; income not floored at zero before rounding | silent wrong on low incomes | suite |
| D10 | Old-regime slabs ignore age bands (senior 3L, super-senior 5L exemption) | silent wrong for age 60+ | reading |
| D11 | `Metros` set defined but unused (input already a bool) | dead code | reading |
| D12 | Float arithmetic for percentages | silent risk | reading |
| D13 | **Invented clause citations**: tax on slabs "Sec 10(1)/115BAC", surcharge "Sec 2(37)", cess "Sec 115B"; all deductions lumped into one "Deductions" line with a generic clause | traceability failure | reading |
| D14 | Rounding trace line is built before the zero-floor clamp, so income trace lines would not sum to taxable income | silent trace error | reading |
| D15 | New-regime marginal-relief block subtracts surcharge from the tax (`max_tax - surcharge`) | silent wrong | reading |
| D16 | Standard deduction and Chapter VI-A mixed in one `deductions` number, so HRA/home-loan interest are not separately traced | traceability | reading |
| D17 | Explanation prints `new_total - old_total` (negative number) | cosmetic | reading |

## What the LLM got right
Constants for R1, R3-R6, R11 slabs, R12 limits, cess; rule-id comments next to every constant (this made review fast); tie -> new; output shape accepted by `TaxResult` once D1 was fixed.

## Review effort (honest)
Reading 425 lines, writing the corrected module and re-testing took the assistant about 1.5 minutes by the machine clock (compile finished 19:46:10, suite green 19:47:24, 2026-11-20); for a human reviewer who must also check each number against the rule text, budget 30-60 minutes per FY. The reviewed file is about 170 lines; **most of the raw file had to be rewritten**, so "review" here was nearer to "rewrite with the draft as a guide". A weaker or sloppier review would have shipped D4, D5 and D8 as silent errors.

## Sign-off checklist for the human owner
- [ ] Constants block matches `rules_source/fy2024_25.txt` clause by clause
- [ ] Full suite passes: `python -m project_a.eval.run_eval` (compiled column)
- [ ] Header changed to `# REVIEWED: YES by <name> on <date>`

---
# FY 2025-26 (Task 5): second compile, reviewed differently

Model: Qwen3.5-9B again, same prompt, same settings. Compile time 142.1 s, 2,467 tokens in / 5,699 out, 450 lines (the FY 2024-25 draft was 425 lines). Raw output: `raw/rules_2025_26.raw.py`.

**The new draft is not the old draft with new numbers.** Temperature 0 does not make a regenerated module similar to the previous one: different structure, different function names, different bugs.
- Raw result on the 238-case FY 2025-26 suite: **225 loud failures** (`UnboundLocalError: actual_80d_self` in the old-regime function: a variable used before it is assigned), 12 silent wrong answers, 1 correct.
- The constants it did get right: new-regime slabs (4/8/12/16/20/24 lakh, 5-30%), 87A limit 12,00,000 and cap 60,000.
- The draft was **not patched**. Reviewing a fresh 450-line draft with new defects would repeat the FY 2024-25 effort. Instead the reviewed `rules_2025_26.py` was **derived from the already-reviewed FY 2024-25 module** by changing 11 lines (new slabs, new 87A constants, headings). It is green on all 238 cases, case-exact 1.0.

Process lesson recorded for RESULTS_A: after the first review, the reviewed code (not the LLM) must be the source of truth. A Budget change is then a small diff to reviewed constants, and the LLM is useful only for proposing that diff, not for regenerating the module.
