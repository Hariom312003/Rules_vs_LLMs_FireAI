# Project B — Data-quality checks: results

_All numbers produced by `python run_all.py --project b`. Nothing here is filled yet._

## 1. Real issues found in raw 2023 data
<!-- PROFILE:START -->
Profiled **240,000** raw 2023 rows, 44 columns.

| Issue | Count | % of rows | Example (unique_key: values) |
|---|---|---|---|
| complaint_type: case/whitespace variants of the same value | 52,786 | 21.994 | `{"unique_key": "56421814", "complaint_type": "FLOORING/STAIRS"}` |
| descriptor: case/whitespace variants of the same value | 48,409 | 20.17 | `{"unique_key": "56421814", "descriptor": "FLOOR"}` |
| near-duplicates: same agency/type/address within 5 min | 12,339 | 5.141 | `{"unique_key": "56414137", "agency": "NYPD", "complaint_type": "Noise - Residential", "incident_address": "147` |
| resolution_description: phone number in free text | 7,132 | 2.972 | `{"unique_key": "56414878", "resolution_description": "The Department of Environmental Protection (DEP) didn't ` |
| status Closed but text says open/pending | 5,702 | 2.376 | `{"unique_key": "56460390", "status": "Closed", "resolution_description": "The complaint you filed is a duplica` |
| closed within 1 minute of created (suspicious) | 5,040 | 2.1 | `{"unique_key": "56421344", "created_date": "2023-01-02T08:05:36.000", "closed_date": "2023-01-02T08:05:36.000"` |
| latitude/longitude missing | 4,967 | 2.07 | `{"unique_key": "56441136", "latitude": null, "longitude": null, "agency": "DEP"}` |
| incident_zip missing | 3,578 | 1.491 | `{"unique_key": "56437309", "incident_zip": null, "borough": "MANHATTAN"}` |
| resolution_description missing on Closed | 2,974 | 1.239 | `{"unique_key": "56412534", "status": "Closed", "agency": "DSNY"}` |
| descriptor missing | 2,625 | 1.094 | `{"unique_key": "56414524", "complaint_type": "Homeless Person Assistance", "descriptor": null, "agency": "DHS"` |
| status Closed but closed_date missing | 1,390 | 0.579 | `{"unique_key": "56686328", "status": "Closed", "closed_date": null}` |
| borough 'Unspecified' or missing | 589 | 0.245 | `{"unique_key": "56414169", "borough": "Unspecified", "agency": "DOT"}` |
| status not Closed but closed_date present | 504 | 0.21 | `{"unique_key": "56434568", "status": "Pending", "closed_date": "2022-12-30T09:37:00.000"}` |
| closed_date earlier than created_date | 331 | 0.138 | `{"unique_key": "56434568", "created_date": "2023-01-03T09:37:00.000", "closed_date": "2022-12-30T09:37:00.000"` |
| resolution_description: email in free text | 271 | 0.113 | `{"unique_key": "56414270", "resolution_description": "The NYC Health Department has responded to your service ` |
| exact duplicate rows | 150 | 0.062 | `{"unique_key": "56409451", "agency": "DOT", "complaint_type": "Traffic Signal Condition", "created_date": "202` |
| incident_zip not in NYC ranges | 127 | 0.053 | `{"unique_key": "56413807", "incident_zip": "11040", "borough": "QUEENS"}` |
| incident_zip inconsistent with borough | 82 | 0.034 | `{"unique_key": "56413505", "incident_zip": "10463", "borough": "MANHATTAN"}` |
| status open but text says closed/resolved | 41 | 0.017 | `{"unique_key": "56428291", "status": "Started", "resolution_description": "The Department of Environmental Pro` |

Checked but clean (0 hits): created_date not ISO format, created_date outside calendar 2023, closed_date in the future / after data pull, open > 365 days after created, lat/lon exactly 0, lat/lon outside NYC bounding box, lat/lon look swapped, incident_zip malformed (not 5 digits), agency: case/whitespace variants of the same value, borough: case/whitespace variants of the same value, status: case/whitespace variants of the same value, complaint_type missing, descriptor: phone number in free text, descriptor: email in free text, duplicate unique_key.
<!-- PROFILE:END -->

## 2. Per-problem detection, false alarms, cost

Auto-filled by `python -m project_b.eval.run_eval`. Cost for rules/stats = CPU time at an assumed $0.04 per vCPU-hour; LLM = notional Gemini token price.

<!-- METRICS:START -->
| Problem | Detector | Detection | Batch hit | FA rows (clean) | FA batches (clean) | $ / M rows | Rows/s | Clarity |
|---|---|---|---|---|---|---|---|---|
| a Renamed or dropped column | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 25,444,214 | 1.00 |
| b Column type change | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4,981,630 | 1.00 |
| c Date format switch partway through batch | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 400,760 | 1.00 |
| d Latitude/longitude swapped | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 974,936 | 1.00 |
| e Exact duplicates | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 524,122 | 0.50 |
| f Near-duplicates | rules | 1.00 | 1.00 | 0.0005 | 1.00 | 0.0001 | 179,442 | 1.00 |
| g Null spike in one agency's records | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0001 | 174,119 | 0.50 |
| h Closed date earlier than created date | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 600,580 | 1.00 |
| i ZIP inconsistent with borough | rules | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 575,324 | 1.00 |
| j Complaint Type inconsistent with Descriptor | rules | 1.00 | 1.00 | 0.0045 | 1.00 | 0.0000 | 411,441 | 1.00 |
| k Resolution Description contradicting Status | rules | 1.00 | 1.00 | 0.0245 | 1.00 | 0.0001 | 129,573 | 1.00 |
| l Personal data in free-text fields | rules | 1.00 | 1.00 | 0.0045 | 1.00 | 0.0002 | 67,940 | 1.00 |
| a Renamed or dropped column | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 18,493,575 | 1.00 |
| b Column type change | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 576,544 | 1.00 |
| c Date format switch partway through batch | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0001 | 166,441 | 0.75 |
| d Latitude/longitude swapped | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 304,231 | 0.75 |
| e Exact duplicates | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 511,422 | 0.25 |
| f Near-duplicates | stats | 0.87 | 1.00 | 0.0010 | 1.00 | 0.0005 | 21,617 | 0.75 |
| g Null spike in one agency's records | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0003 | 42,450 | 0.50 |
| h Closed date earlier than created date | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 569,392 | 0.75 |
| i ZIP inconsistent with borough | stats | 1.00 | 1.00 | 0.0000 | 0.00 | 0.0000 | 406,485 | 0.75 |
| j Complaint Type inconsistent with Descriptor | stats | 0.99 | 1.00 | 0.0018 | 1.00 | 0.0000 | 377,355 | 0.75 |
| k Resolution Description contradicting Status | stats | 0.02 | 1.00 | 0.0007 | 0.67 | 0.0002 | 58,158 | 0.75 |
| l Personal data in free-text fields | stats | 0.00 | 0.00 | 0.0000 | 0.00 | 0.0001 | 77,869 | n/a |
| a Renamed or dropped column | llm | 0.50 | 0.50 | 0.0000 | 0.00 | 0.0000 | 3 | 0.75 |
| b Column type change | llm | 0.50 | 0.50 | 0.0000 | 0.00 | 0.0000 | 2 | 0.75 |
| c Date format switch partway through batch | llm | 0.00 | 1.00 | 0.0000 | 1.00 | 0.0000 | 2 | 0.75 |
| d Latitude/longitude swapped | llm | 0.70 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4 | 0.75 |
| e Exact duplicates | llm | 0.06 | 0.50 | 0.0000 | 0.00 | 0.0000 | 2 | 0.75 |
| f Near-duplicates | llm | 0.00 | 0.00 | 0.0000 | 0.00 | 0.0000 | 3 | n/a |
| g Null spike in one agency's records | llm | 0.33 | 1.00 | 0.0200 | 0.50 | 0.0000 | 3 | 0.75 |
| h Closed date earlier than created date | llm | 0.65 | 1.00 | 0.0100 | 1.00 | 0.0000 | 3 | 0.75 |
| i ZIP inconsistent with borough | llm | 0.10 | 1.00 | 0.0000 | 0.00 | 0.0000 | 3 | 0.75 |
| j Complaint Type inconsistent with Descriptor | llm | 0.10 | 1.00 | 0.0050 | 0.50 | 0.0000 | 2 | 0.75 |
| k Resolution Description contradicting Status | llm | 0.35 | 1.00 | 0.0000 | 0.00 | 0.0000 | 4 | 0.75 |
| l Personal data in free-text fields | llm | 0.30 | 1.00 | 0.0000 | 0.00 | 0.0000 | 6 | 0.75 |
<!-- METRICS:END -->

## 3. Hybrid pipeline (end to end)
What it catches, what it costs. Auto-filled by `python -m project_b.pipeline.run`.

<!-- HYBRID:START -->
Hybrid (rules + stats + LLM): **44 rows/s**, compute $0.2523 / M rows, LLM $0.00 / M rows.

| Problem | Owner | Detection | FA rows (clean) | LLM rows | Suppressed by LLM |
|---|---|---|---|---|---|
| a Renamed or dropped column | rules | 1.00 | 0.0000 | 45 | 0 |
| b Column type change | rules | 1.00 | 0.0000 | 88 | 0 |
| c Date format switch partway through batch | rules | 1.00 | 0.0000 | 97 | 0 |
| d Latitude/longitude swapped | rules | 1.00 | 0.0000 | 115 | 0 |
| e Exact duplicates | rules | 1.00 | 0.0000 | 94 | 0 |
| f Near-duplicates | stats | 0.81 | 0.0005 | 83 | 0 |
| g Null spike in one agency's records | stats | 1.00 | 0.0000 | 100 | 0 |
| h Closed date earlier than created date | rules | 1.00 | 0.0000 | 98 | 0 |
| i ZIP inconsistent with borough | rules | 1.00 | 0.0000 | 100 | 0 |
| j Complaint Type inconsistent with Descriptor | stats | 1.00 | 0.0015 | 150 | 0 |
| k Resolution Description contradicting Status | rules | 1.00 | 0.0285 | 150 | 0 |
| l Personal data in free-text fields | rules | 1.00 | 0.0050 | 90 | 0 |
<!-- HYBRID:END -->

**Cost of the LLM stage (Qwen3.5-4B, local, annotate-only):** the same pipeline runs at ~44 rows/s with the LLM stage versus ~6,800 rows/s with rules + stats only, because ~100-150 rows per 2,000-row batch go to the model at ~4 s per 25 rows. Detection with the LLM stage equals the rules + stats detection (the sampled LLM review added no extra true finds in this run). API cost is $0 for a local model; the compute figure in the table charges that wall time at CPU rates and is therefore not comparable to a Gemini bill.

## 3a. Negative result: LLM veto in the hybrid
With Qwen3.5-4B (local) allowed to DROP rule/stat alerts it disagreed with, detection collapsed for the semantic checks (j 0.99 -> 0.08, k 1.00 -> 0.09; 146 of 150 true j alerts suppressed) and throughput fell from ~6,800 to 44 rows/s. Raw output: `project_b/results/hybrid_b_llm_veto.json`. The default pipeline therefore uses the LLM only to annotate flagged rows and to review a 2% sample (`HybridPipeline(veto=False)`).

## 4. Scale design (max 2 pages)
50M rows/day, 120 customers, different schemas: projected cost and latency; what changes at scale and why.

_Draft projection from measured rules + stats throughput (~6,000 rows/s on one laptop core, ~$0.002 / M rows compute). LLM cost is NOT yet measured; fill it in after `pipeline.run --llm`._

- **Compute:** 50M rows/day / 6,000 rows/s ≈ 2.3 core-hours/day, about $0.1/day at $0.04 per vCPU-hour. Across 120 customers (~420k rows each) every customer's day fits in about 70 s of one core.
- **LLM:** the budget lever is rows reviewed. At the hybrid's sampling (2% of rows plus flagged semantic rows) the LLM sees about 1M rows/day; price that with the measured tokens per row.
- **What changes at scale:** (1) schemas differ per customer, so the hard-coded NYC bounds / ZIP map become per-customer config or learned baselines (stats wins on portability); (2) baselines must be versioned and refit per customer; (3) near-duplicate matching needs blocking/MinHash instead of pairwise comparisons; (4) alert volume, not detection, becomes the constraint, so false-alarm rate per customer matters more than recall.
