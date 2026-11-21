# Project A — Income-tax engine: rules, LLM or both?

Brief: `task harry.pdf` (Project A). A service that tells a salaried person in India what tax they owe under the old and new regime, which to pick and why — computed three ways, then measured, then defended.

**Status: code, tests, rule texts, measurements and write-up are complete. Two things need a human** (see "Before you submit"): the 30-case check against the official calculator, and sign-off on the AI-reviewed compiled rules.

## Setup

```bash
python run_all.py --setup            # creates .venv, installs requirements.txt
cp .env.example .env                 # only needed for the LLM parts (see "LLM backends")
.venv\Scripts\activate               # Windows  (source .venv/bin/activate elsewhere)
python -m pytest project_a -q        # ~590 tests, a few seconds, no LLM
```
Python 3.10+ (developed on 3.11).

## Run

```bash
python run_all.py --project a --skip-llm     # suite + tests + free parts of the evaluation (seconds)
python run_all.py --project a                # + LLM parts if GEMINI_API_KEY or LLM_BACKEND=local is set (about 20-40 min on a laptop GPU)
python -m project_a.eval.run_eval --llm --llm-cases 40 --det-inputs 5      # bigger measurement
python -m project_a.eval.run_change --llm --reuse-compiled                 # Task 5 experiments
python -m project_a.tests.build_suite        # regenerate cases / descriptions / official checklist
```
Results land in `project_a/results/*.json` and are written into the marked blocks of `RESULTS_A.md`.

### LLM backends
- **Gemini free tier** (what the brief names): put `GEMINI_API_KEY` in `.env`.
- **Local model**: start `llama-server` (llama.cpp) with a GGUF model, e.g. `llama-server -m Qwen3.5-9B-Q4_K_M.gguf --host 127.0.0.1 --port 8090 -c 12288 -ngl 99 --reasoning-budget 0`, then set `LLM_BACKEND=local` and `LOCAL_LLM_MODEL=Qwen3.5-9B`. The numbers in `RESULTS_A.md` were produced this way; **no Gemini run was made**. Cost columns use tokens x Gemini 2.0 Flash list price (check `PRICES_PER_M` in `common/llm.py`).

## What is where

| Brief task | Files |
|---|---|
| Rule text, official sources only | `rules_source/fy2024_25.txt`, `fy2025_26.txt` (clause ids R1..R16), `SOURCES.md` (what was verified where, what was not) |
| 1. Test suite | `tests/oracle.py` (independent reference), `tests/anchors.py` (hand-worked), `tests/build_suite.py` -> `tests/data/cases.jsonl` (256 FY24-25), `cases_fy2025_26.jsonl` (238), `descriptions.jsonl` (50), `official_checklist.csv` (36 rows to check by hand), `tests/OFFICIAL_CHECK.md` |
| 2a. Hand-coded rules | `tax_engine/hand_rules/calculator.py` (logic) + `config/fy2024_25.yaml`, `fy2025_26.yaml` (every number) |
| 2b. LLM at query time | `tax_engine/llm_query/calculator.py` |
| 2c. LLM-compiled rules | `tax_engine/llm_compiled/compile_rules.py` (compile once), `generated/raw/*.raw.py` (untouched model output), `generated/rules_*.py` (reviewed, executed), `generated/REVIEW.md` (defects found), `calculator.py` (runs it; refuses unreviewed files) |
| 3. Plain-language input | `parser/parse.py` (extractor: LLM or regex baseline; deterministic validation that asks instead of guessing) |
| 4. Measure everything | `eval/run_eval.py`, `eval/traceability.py` |
| 5. The law changes | `eval/run_change.py`, `results/build_log.md` |
| 6. Final design | `RESULTS_A.md` section 4 |

Shared contract: `tax_engine/models.py` (integer rupees; every result carries `TraceLine`s with a clause; "income" lines sum to taxable income, "tax" lines sum to total tax).

## Assumptions baked into the rules (state them in the interview)
Resident individual; salary income only; age is as of the end of the FY (60+ senior, 80+ super-senior); `basic_salary` includes DA for HRA; `gross_salary` is annual gross (not CTC, not take-home); 80D amounts are premiums paid; employer NPS 80CCD(2), professional tax, leave encashment and perquisites are out of scope; paise are ignored and total income and payable tax are rounded to the nearest Rs 10 (Sec 288A/288B).

## Before you submit (manual steps that cannot be automated)
1. **Official-calculator cross-check (brief: at least 30 cases).** Follow `tests/OFFICIAL_CHECK.md`; fill `tests/data/official_checklist.csv`; run `python -m pytest project_a -q -k official`. Not done yet — currently every case is `oracle` or `hand_worked`.
2. **Confirm the clauses marked S in `rules_source/SOURCES.md`** (HRA / Rule 2A, 87A marginal relief for FY25-26, surcharge marginal-relief wording) against the Finance Act text; several government hosts refused automated access.
3. **Re-read `generated/rules_2024_25.py` and `rules_2025_26.py` and `REVIEW.md`**, then change the header to `# REVIEWED: YES by <your name> on <date>`. The AI assistant that wrote the review is not a substitute for you.
4. Fill `AI_USAGE.md` (a draft is included) and read `RESULTS_A.md` end to end; you must be able to explain and change every line live.
5. Optional: run the larger measurement (`--llm-cases 40 --det-inputs 5`) or with Gemini, and update the numbers.
