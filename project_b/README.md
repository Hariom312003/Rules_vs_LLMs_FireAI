# Project B — NYC 311 data-quality layer

Handoff status: **code complete for rules + stats + hybrid; LLM family written but not yet measured** (needs a free Gemini key).

## Run (from the repo root)

```bash
python run_all.py --setup                 # once: .venv + libraries
cp .env.example .env                      # add GEMINI_API_KEY to enable the LLM parts
python -m project_b.data.download_311 --months 12 --limit 20000   # sample (NOT included in the emailed package; see ../README_FIRST.md)
python -m project_b.profiling.profile     # Task 1  -> RESULTS_B.md "real issues"
python -m project_b.eval.run_eval         # Tasks 3-4 -> RESULTS_B.md metrics table (add --llm for Gemini)
python -m project_b.pipeline.run          # Task 5  -> RESULTS_B.md hybrid table (add --llm)
python -m pytest project_b -q             # unit tests (synthetic data, no download needed)
```

## Map
| Path | Task |
|---|---|
| `data/download_311.py`, `data/loader.py` | download sample; load raw / derive a CLEAN reference set |
| `schema.py` | expected columns, NYC bounding box, ZIP->borough rule |
| `profiling/profile.py` | 1. profile raw data |
| `injector/corruptions.py` | 2. the 12 corruption types (seeded, ground truth in `Truth`) |
| `detectors/{rules,stats,llm}.py` | 3. three detector families, common `Alert` contract |
| `eval/run_eval.py` | 4. detection / false alarms / cost / throughput / clarity |
| `pipeline/{hybrid,run}.py` | 5. hybrid pipeline (`ROUTING` = who owns which problem) |

## Still to do
1. Add a Gemini key and run `run_eval --llm` and `pipeline.run --llm` (LLM columns are empty until then).
2. Optionally download the full 2023 year (drop `--limit`) for final numbers; the sample is the first 20k rows of each month by id.
3. Review `ROUTING` in `pipeline/hybrid.py` against the LLM results, then finish `RESULTS_B.md` section 4 (scale) and the Project B rows of `DECISION_MATRIX.md`.
4. Fill `AI_USAGE.md` honestly.

## Local LLM option (no Gemini key needed)
`common/llm.py` has a local backend. Start `llama-server` on port 8090 with a GGUF model, then:
```bash
set LLM_BACKEND=local           # PowerShell: $env:LLM_BACKEND="local"
python -m project_b.eval.run_eval --llm
```
Measured so far: **LFM2.5-1.2B-Instruct is too small for this task** — it echoes the problem list from the prompt and emits malformed JSON (detection ~0 on 10 of 12 problem types). Report model name next to every LLM number, and note the assignment names the Gemini free tier.

## Known caveats (worth stating in the write-up)
- The "clean" set is raw rows passing basic validity checks, so the false-alarm rate is measured against that definition.
- Injected text for problems k and l uses fixed templates, so keyword/regex rules score optimistically on them; the real-data false-alarm rate (rules k ~2.5% of clean rows) is the more honest number.
- Phone numbers found in real resolution text are mostly agency contact numbers, not personal data; the profile counts them as hits.
