# AI Usage Note

_Written in compliance with the Fire AI assignment guidelines: "which tools you used, for what, and one place where the AI was wrong and how you caught it."_

## 1. Tools Used and For What

| Tool | Project | Purpose / Component |
| :--- | :---: | :--- |
| **Google Gemini API (gemini-3.5-flash / gemini-2.0-flash)** | **A & B** | - Natural language parser (extracting taxpayer facts from English, Hinglish, and Hindi free text).<br>- LLM query-time tax calculation experiments (Task 2b).<br>- LLM-compiled rule generation experiment (Task 2c).<br>- LLM data-quality review of NYC 311 batches (Task 3c, Task 5). |
| **Antigravity IDE / Claude (Sonnet 3.5 / 3.7)** | **A & B** | - Project scaffolding, boilerplate, and dependency management.<br>- Implementing deterministic tax math in `HandRulesCalculator` and the independent `oracle.py`.<br>- Building the 494-case boundary test suite and 50 plain-language test descriptions.<br>- Implementing the 12 corruption injectors and statistical detectors (Isolation Forest, TF-IDF + Logistic Regression, Mahalanobis distance).<br>- FastAPI backend and Streamlit UI. |
| **Qwen3.5-9B & Qwen3.5-4B (local llama.cpp)** | **A & B** | - Local offline benchmarking for determinism repeats and latency baseline comparison. |

---

## 2. Where the AI Was Wrong, and How It Was Caught

### A. Project A: LLM-Compiled Rules Hallucinations & Critical Math Errors
- **The Failure**: When prompted to compile the statutory tax text (`rules_source/fy2024_25.txt`) into a single executable Python module:
  1. The raw compiled output crashed immediately on all test cases due to an unhandled tuple unpacking error in the slab ladder loop.
  2. After fixing the crash, the compiled script executed but was **silently wrong on 194 out of 256 cases (only 24% accuracy)**.
  3. Critical defects caught during audit:
     - **Catastrophic Surcharge Ladder**: The LLM charged a 10% surcharge on taxable income exceeding Rs 5 lakh (the law states Rs 50 lakh!).
     - **Inverted Section 87A Marginal Relief**: It subtracted `(income - 7,00,000)` from total tax instead of capping tax payable at the excess income.
     - **Hallucinated Statutory Clauses**: Invented fictional legal sections in the audit trace, citing *"Section 115B"* and *"Section 2(37)"*.
     - **Omitted Senior Citizen Slabs**: Defaulted to the below-60 slab ladder for all ages.
- **How It Was Caught**: Caught by running the comprehensive boundary test suite (`python -m pytest project_a -q`) against the independent reference oracle (`tests/oracle.py`), which asserted rupee-exact equivalence. Every single defect was recorded in `project_a/tax_engine/llm_compiled/generated/REVIEW.md`. Recompiling for FY 2025-26 produced an entirely new set of silent bugs, proving that LLM code generation is non-reproducible and dangerous for financial engines.

### B. Project A: Rounding Truncation Flaw in Early Oracle Implementation
- **The Failure**: An early version of `tests/oracle.py` rounded fractional rupees to the nearest rupee *before* applying the statutory Section 288A/288B nearest-Rs 10 rounding.
- **How It Was Caught**: Re-reading CBDT guidelines and the official CBDT circular example (e.g. Rs 2,52,844.99 $\to$ ignore paise first $\to$ Rs 2,52,840). Caught by manual hand-working of anchor cases in `tests/anchors.py`.

### C. Project B: The "LLM Veto" Catastrophe in the Hybrid Pipeline
- **The Failure**: In the first design of the hybrid pipeline, the LLM was given "veto power" to dismiss alerts raised by rules or statistical detectors if the model disagreed.
- **How It Was Caught**: When evaluating Problem (j) (*Complaint Type inconsistent with Descriptor*), detection rate collapsed from **0.99 to 0.08**: the LLM incorrectly dismissed 146 out of 150 true anomalies, believing that *"Noise - Commercial"* was consistent with *"Loud Music/Party"* in a residential zoning context. Furthermore, pipeline throughput dropped from **~6,800 rows/s to 44 rows/s**. The veto was immediately disabled; the final design restricts the LLM to annotating flagged rows or auditing a 1–2% sample.

### D. Project B: Global Null-Rate False Alarms in Statistical Detector
- **The Failure**: The initial statistical detector for null spikes (Problem g) computed a global null baseline across all agencies. Because certain agencies (like DEP or DHS) naturally omit fields like `incident_address` or `landmark` for park/waterway complaints, the detector generated a **9% false alarm rate on clean production data**.
- **How It Was Caught**: Caught by the false-alarm column in `run_eval.py`. Fixed by implementing a **per-agency baseline** `clean.groupby('agency').apply(lambda g: g.isna().mean())`, eliminating all false alarms on clean batches.
