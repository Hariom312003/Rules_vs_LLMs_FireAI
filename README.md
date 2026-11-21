# Rules vs LLMs Take-Home Assignment — Fire AI

**Candidate Submission** | **Evaluator:** Kaustubh Keshav, Fire AI  
**Assignment Thesis:** Deciding when a deterministic rule is the right tool, when an LLM earns its cost, and when the answer is a combination of both.

---

## 1. Quickstart & Installation Instructions

### Prerequisites
- Python 3.10+ (tested on Python 3.10, 3.11, and 3.12).
- Google Gemini API key (optional for core reproduction, required for live LLM extraction; free tier from [Google AI Studio](https://aistudio.google.com/apikey)).

### Setup from Scratch
```bash
# 1. Create and activate a clean virtual environment
python3 -m venv .venv
source .venv/bin/activate       # On Windows: .venv\Scripts\activate

# 2. Install all dependencies (includes tax engine, data quality, FastAPI & Streamlit)
pip install --upgrade pip
pip install -r requirements.txt

# 3. Configure environment variables (optional, defaults to offline determinism)
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY if testing live LLM features

# 4. Run all unit & integration tests (773 passed in ~2 seconds)
python -m pytest project_a project_b -q

# 5. Master single-command reproduction (reproduces every number in RESULTS_A/B in ~24s)
python run_all.py --skip-llm

# 6. Run web application integration tests (FastAPI + Streamlit headless test suite)
python test_web_full.py

# 7. Launch interactive Web Application (FastAPI backend + Streamlit frontend)
uvicorn app_api:app --host 127.0.0.1 --port 8000 &
streamlit run app_ui.py --server.port 8501
```

---

## 2. Deliverables & Repository Structure

In accordance with Page 4 of the Fire AI Assignment Brief:

```
rules-vs-llms-assignment/
├── project_a/                  # Project A: Income-tax engine
│   ├── tax_engine/             # Three implementations: hand_rules, llm_query, llm_compiled
│   ├── parser/                 # Plain-language extractor (Gemini/Regex) + evidence validation
│   ├── rules_source/           # Statutory texts with clause IDs (FY 2024-25 & FY 2025-26)
│   └── tests/                  # 494 test cases, independent oracle, official 36-case checklist
├── project_b/                  # Project B: Data-quality layer (NYC 311 2023)
│   ├── data/                   # Raw parquet data loader & clean baseline generator
│   ├── profiling/              # Profiler detecting 19 real-world issue types in 2023 data
│   ├── injector/               # Controlled 12-problem corruption injector (seeded ground truth)
│   ├── detectors/              # Three detector families: rules, statistics/ML, and LLM review
│   └── pipeline/               # Multi-tier hybrid pipeline & LLM veto negative result
├── common/                     # Shared Gemini / local LLM client with token & cost logging
├── RESULTS_A.md                # Project A evaluation table, Task 5 change log, and final architecture
├── RESULTS_B.md                # Project B evaluation table, profile stats, and 50M rows/day scale design
├── DECISION_MATRIX.md          # Unified decision matrix: every choice justified by a measurement
├── AI_USAGE.md                 # AI usage note: tools used, where AI failed, and how it was caught
├── requirements.txt            # Unified dependencies (Python 3.10+)
├── README.md                   # This master documentation
├── run_all.py                  # Single command that reproduces every reported number
├── app_api.py                  # FastAPI REST endpoints
└── app_ui.py                   # Streamlit web UI for interactive testing
```

---

## 3. Executive Summary of Results

### Project A: Indian Salaried Income-Tax Engine
- **Hand-Coded Rules**: **100.0% rupee-exact (494/494 cases)** across both FY 2024-25 and FY 2025-26, 100% deterministic, **0.1 ms latency**, **$0 cost**, and 100% statutory clause traceability.
- **LLM at Query Time**: Exact on only **25% (3 of 12)** cases, failing silently on 9 cases (zero errors, plausible hallucinated numbers), **20.0s latency**, and **$0.54 / 1,000 requests**.
- **LLM-Compiled Rules**: Raw compile failed (0% exact, crashed); after fixing crash was **silently wrong on 194 of 256 cases (24% exact)** with 17 critical defects (e.g. 10% surcharge on >5L, inverted 87A rebate). Recompiling for FY 2025-26 generated a completely different buggy program.
- **Plain-Language Parser**: Hybrid architecture: LLM extracts facts (**89% exact** vs 25% for regex) while deterministic rules enforce evidence guards (stopping the LLM from inventing taxpayer age or assuming monthly salary) and decide when to ask clarifying questions instead of guessing.
- **Budget Change (Task 5)**: Hand-coded rules absorbed Finance Act 2025 in **26 YAML lines and 0 code lines**, passing 238/238 cases.

### Project B: Data-Quality Engine (NYC 311 2023)
- **Real Issues Profiled**: 240,000 raw 2023 rows analyzed: 5.14% near-duplicates, 2.97% phone numbers in free text, 2.38% status contradiction ("Closed" but text open/pending), 331 records with `closed_date` earlier than `created_date`.
- **Detector Winners**:
  - Declarative Rules won 9 of 12 categories (schema, column types, dates, coordinates bounding box, exact duplicates, invariants). Throughput: **5M–25M rows/s**, 0 false alarms.
  - Statistical Detectors won 3 categories (per-agency null spikes via learned baselines, Complaint Type vs Descriptor co-occurrence at **0.99 detection with 0.18% FA**).
  - LLM Review was slow (2–6 rows/s) and noisy alone.
- **Negative Result (LLM Veto)**: Giving the LLM veto power to drop rule/stat alerts caused semantic detection to collapse (**0.99 $\to$ 0.08**) because the model hallucinated false agreements. Veto is disabled by default.
- **Hybrid Pipeline**: Stage 1 (Rules on all rows) $\to$ Stage 2 (Stats per batch) $\to$ Stage 3 (LLM review only on 1–2% audit samples or high-ambiguity semantic flags). Runs at **~6,800 rows/s** without LLM veto, costing ~$0.002 per million rows.
- **50M Rows/Day Scalability**: Rules & stats process 50M rows in **~2.3 core-hours/day (~$0.10/day compute)**. LLM review is budgeted via sampling to ~500k rows/day.

---

## 4. Technical Defense Interview Guide

Be prepared to answer these core architectural questions during the 60-minute interview:
1. **Why not use an LLM for tax calculations?**  
   *Because tax requires rupee-exactness, determinism, and statutory auditability. Non-linear step functions (rebates, surcharges, marginal relief) cause LLMs to fail silently without errors (25% accuracy measured).*
2. **Why was the LLM veto removed from Project B?**  
   *Empirically measured: letting the LLM overrule rule/stat alerts dropped detection from 0.99 to 0.08 on Complaint vs Descriptor (dropping 146/150 true alerts) and slowed throughput from 6,800 to 44 rows/s.*
3. **How do you keep the system correct through the next Budget?**  
   *Derive thresholds into YAML, independently update `oracle.py`, generate boundary tests (+/-10 around every slab edge/rebate limit), and enforce a gate against the official Income Tax Dept calculator.*
