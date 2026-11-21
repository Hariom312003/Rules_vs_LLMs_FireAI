"""Stage: hybrid pipeline end to end -> results/hybrid_b.json + RESULTS_B.md section.

    python -m project_b.pipeline.run            # rules + stats only
    python -m project_b.pipeline.run --llm      # + LLM verification/sampling (needs key)

Runs the pipeline on clean batches (false alarms) and on one batch per problem
type (detection), then reports what it catches, what it costs and how fast.
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np

from ..data.loader import load_clean, make_batches
from ..detectors.llm import LLMDetector
from ..eval.run_eval import CPU_USD_PER_HOUR, score
from ..injector.corruptions import CORRUPTIONS, inject
from .hybrid import HybridPipeline

RESULTS = Path(__file__).resolve().parents[1] / "results"
ROOT = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spike-rate", type=float, default=0.5)
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--batch-size", type=int, default=2000)
    ap.add_argument("--rate", type=float, default=0.05)
    ap.add_argument("--max-clean", type=int, default=80_000)
    args = ap.parse_args(argv)

    clean = load_clean(max_rows=args.max_clean)
    cut = len(clean) // 2
    base, pool = clean.iloc[:cut].reset_index(drop=True), clean.iloc[cut:].reset_index(drop=True)
    batches = make_batches(pool, args.batch_size)
    llm = LLMDetector() if args.llm else None
    pipe = HybridPipeline(llm=llm).fit(base)

    rows, tot_rows, tot_secs, tot_cost = [], 0, 0.0, 0.0
    # clean batch -> false alarms
    cres = pipe.run(batches[0])
    tot_rows += len(batches[0]); tot_secs += sum(cres.seconds.values()); tot_cost += cres.llm_cost_usd
    fa_by_key = {c.key: len({a.row_index for a in cres.alerts if a.problem_key == c.key
                             and a.row_index is not None}) / len(batches[0]) for c in CORRUPTIONS}

    for i, c in enumerate(CORRUPTIONS):
        b = batches[(i + 1) % len(batches)]
        rate = 0.1 if c.level == "schema" else (args.spike_rate if c.key == "g" else args.rate)
        cb, truth = inject(b, c.key, rate, seed=i)
        r = pipe.run(cb)
        tot_rows += len(cb); tot_secs += sum(r.seconds.values()); tot_cost += r.llm_cost_usd
        det, hit, _ = score(r.alerts, c.key, truth, len(cb), None)
        rows.append({"problem": c.key, "name": c.name, "owner": pipe.routing[c.key],
                     "detection": None if np.isnan(det) else round(det, 3),
                     "fa_row_rate_clean": round(fa_by_key[c.key], 5),
                     "llm_rows": r.llm_rows_reviewed, "suppressed_by_llm": r.suppressed_by_llm})

    rps = tot_rows / max(tot_secs, 1e-9)
    cpu_per_m = (1e6 / rps) * CPU_USD_PER_HOUR / 3600
    llm_per_m = tot_cost / tot_rows * 1e6
    out = {"rows_processed": tot_rows, "rows_per_s": round(rps), "compute_usd_per_m_rows": round(cpu_per_m, 4),
           "llm_usd_per_m_rows": round(llm_per_m, 2), "llm_enabled": args.llm, "per_problem": rows}
    RESULTS.mkdir(exist_ok=True)
    prev = RESULTS / "hybrid_b.json"
    if not args.llm and prev.exists() and json.loads(prev.read_text(encoding="utf-8")).get("llm_enabled"):
        (RESULTS / "hybrid_b_no_llm.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        print("kept the earlier LLM-enabled hybrid_b.json and RESULTS_B.md; this rules+stats run is in hybrid_b_no_llm.json")
        return
    prev.write_text(json.dumps(out, indent=2), encoding="utf-8")

    md = [f"Hybrid ({'rules + stats + LLM' if args.llm else 'rules + stats, LLM off'}): "
          f"**{rps:,.0f} rows/s**, compute ${cpu_per_m:.4f} / M rows, LLM ${llm_per_m:.2f} / M rows.", "",
          "| Problem | Owner | Detection | FA rows (clean) | LLM rows | Suppressed by LLM |", "|---|---|---|---|---|---|"]
    for r in rows:
        d = "n/a" if r["detection"] is None else f"{r['detection']:.2f}"
        md.append(f"| {r['problem']} {r['name']} | {r['owner']} | {d} | {r['fa_row_rate_clean']:.4f} "
                  f"| {r['llm_rows']} | {r['suppressed_by_llm']} |")
    p = ROOT / "RESULTS_B.md"
    t = p.read_text(encoding="utf-8")
    new = "<!-- HYBRID:START -->\n" + "\n".join(md) + "\n<!-- HYBRID:END -->"
    if "<!-- HYBRID:START -->" in t:
        p.write_text(re.sub(r"<!-- HYBRID:START -->.*<!-- HYBRID:END -->", lambda _: new, t, flags=re.S),
                     encoding="utf-8")
    print("\n".join(md))


if __name__ == "__main__":
    main()
