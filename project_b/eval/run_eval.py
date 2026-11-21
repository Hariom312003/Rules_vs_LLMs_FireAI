"""Task 4: every (problem a..l) x (detector family) on controlled corruptions.

    python -m project_b.eval.run_eval                 # rules + stats (free, fast)
    python -m project_b.eval.run_eval --llm           # + Gemini review (needs key)

Per row of the output table:
  detection_rate   row-level problems: recall over corrupted rows (LLM: over the
                   rows it actually reviewed); schema problems: share of batches caught
  batch_hit_rate   share of corrupted batches with >=1 alert of the right type
  fa_row_rate      share of CLEAN rows flagged with this problem type
  fa_batch_rate    share of CLEAN batches with >=1 alert of this type
  cost_per_m_rows  LLM: notional token cost; rules/stats: CPU time at an ASSUMED
                   $0.04 per vCPU-hour (laptop-class), so the two are comparable
  rows_per_s       throughput of that single check on this machine
  clarity          mean Alert.clarity() of this type's alerts (0..1)
"""
from __future__ import annotations

import argparse
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ..data.loader import load_clean, make_batches
from ..detectors.base import Alert
from ..detectors.llm import LLMDetector
from ..detectors.rules import RuleDetectors
from ..detectors.stats import StatDetectors
from ..injector.corruptions import CORRUPTIONS, inject

RESULTS = Path(__file__).resolve().parents[1] / "results"
ROOT = Path(__file__).resolve().parents[2]
CPU_USD_PER_HOUR = 0.04  # assumption, stated in RESULTS_B.md


def _alerts_for(alerts: list[Alert], key: str) -> list[Alert]:
    return [a for a in alerts if a.problem_key == key]


def _timed_key(det, key: str, batch: pd.DataFrame) -> tuple[list[Alert], float]:
    """Time one check in isolation (rules/stats expose _<key>; LLM runs whole)."""
    fn = getattr(det, f"_{key}", None)
    t0 = time.perf_counter()
    alerts = fn(batch) if fn else det.detect(batch)
    return alerts, time.perf_counter() - t0


def score(alerts: list[Alert], key: str, truth, n_rows: int, reviewed: set[int] | None):
    mine = _alerts_for(alerts, key)
    flagged = {a.row_index for a in mine if a.row_index is not None}
    hit = len(mine) > 0
    if truth is not None and truth.row_mask is not None:
        bad = set(np.flatnonzero(truth.row_mask.to_numpy()).tolist())
        if reviewed is not None:
            bad &= reviewed
        rec = len(bad & flagged) / len(bad) if bad else np.nan
        detect = rec
    else:
        detect = float(hit)
    return detect, float(hit), mine


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch-size", type=int, default=2000)
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--rate", type=float, default=0.05, help="row corruption rate")
    ap.add_argument("--schema-rate", type=float, default=0.1, help="share of columns for a,b")
    ap.add_argument("--spike-rate", type=float, default=0.5, help="share of one agency's rows nulled (g)")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--llm-batch-size", type=int, default=100)
    ap.add_argument("--llm-rate", type=float, default=0.10)
    ap.add_argument("--llm-reps", type=int, default=2)
    ap.add_argument("--max-clean", type=int, default=80_000)
    args = ap.parse_args(argv)

    clean = load_clean(max_rows=args.max_clean)
    cut = int(len(clean) * 0.5)
    base, pool = clean.iloc[:cut].reset_index(drop=True), clean.iloc[cut:].reset_index(drop=True)
    print(f"clean rows: {len(clean):,} (baseline {len(base):,}, test pool {len(pool):,})")

    dets = [RuleDetectors().fit(base), StatDetectors().fit(base)]
    llm_det = None
    if args.llm:
        llm_det = LLMDetector(max_rows=args.llm_batch_size).fit(base)

    batches = make_batches(pool, args.batch_size)[: args.reps]
    small = make_batches(pool, args.llm_batch_size, seed=1)[: args.llm_reps]
    rows = []

    def run_family(det, batch_list, rate_row, rate_schema, is_llm=False):
        # clean batches -> false alarms
        clean_alerts = []
        for b in batch_list:
            if is_llm:
                det.client.stats.calls.clear()
            clean_alerts.append(det.detect(b))
        n_clean = sum(len(b) for b in batch_list)
        for c in CORRUPTIONS:
            key, det_scores, hits, clar, secs = c.key, [], [], [], []
            tot_rows = 0
            for rep, b in enumerate(batch_list):
                rate = rate_schema if c.level == "schema" else (args.spike_rate if key == "g" else rate_row)
                cb, truth = inject(b, key, rate, seed=rep)
                tot_rows += len(cb)
                if is_llm:
                    det.client.stats.calls.clear()
                alerts, dt = _timed_key(det, key, cb)
                secs.append(dt)
                d, h, mine = score(alerts, key, truth, len(cb),
                                   det.last_reviewed if is_llm else None)
                det_scores.append(d); hits.append(h); clar += [a.clarity() for a in mine]
                if is_llm:
                    llm_cost = det.client.stats.summary()["total_cost_usd"]
            fa_rows = sum(len({a.row_index for a in _alerts_for(al, key) if a.row_index is not None})
                          for al in clean_alerts)
            fa_batch = np.mean([len(_alerts_for(al, key)) > 0 for al in clean_alerts])
            rps = tot_rows / max(sum(secs), 1e-9)
            if is_llm:
                cost_m = llm_cost / max(len(cb), 1) * 1e6
            else:
                cost_m = (1e6 / rps) * CPU_USD_PER_HOUR / 3600
            rows.append(dict(problem=key, name=c.name, detector=det.name,
                             detection_rate=float(np.nanmean(det_scores)) if det_scores else np.nan,
                             batch_hit_rate=float(np.mean(hits)),
                             fa_row_rate=fa_rows / n_clean, fa_batch_rate=float(fa_batch),
                             cost_per_m_rows_usd=cost_m, rows_per_s=rps,
                             clarity=float(np.mean(clar)) if clar else np.nan))
            print(f"  {det.name:6} {key} detect={rows[-1]['detection_rate']:.2f} "
                  f"fa_row={rows[-1]['fa_row_rate']:.4f}")

    for d in dets:
        print(f"[{d.name}]")
        run_family(d, batches, args.rate, args.schema_rate)
    if llm_det is not None:
        print("[llm]")
        run_family(llm_det, small, args.llm_rate, args.schema_rate, is_llm=True)

    RESULTS.mkdir(exist_ok=True)
    df = pd.DataFrame(rows)
    prev = RESULTS / "metrics_b.csv"
    if not args.llm and prev.exists():  # a run without --llm must not erase measured LLM rows
        old_rows = pd.read_csv(prev)
        keep = old_rows[old_rows["detector"] == "llm"]
        if len(keep):
            print(f"keeping {len(keep)} LLM rows from the earlier run")
            df = pd.concat([df, keep], ignore_index=True)
    df.to_csv(RESULTS / "metrics_b.csv", index=False)
    md = to_markdown(df)
    (RESULTS / "metrics_b.md").write_text(md, encoding="utf-8")
    _inject_into_results(md)
    print(f"wrote {RESULTS / 'metrics_b.csv'}")


def to_markdown(df: pd.DataFrame) -> str:
    lines = ["| Problem | Detector | Detection | Batch hit | FA rows (clean) | FA batches (clean) "
             "| $ / M rows | Rows/s | Clarity |", "|---|---|---|---|---|---|---|---|---|"]
    for _, r in df.iterrows():
        f = lambda v, p=2: "n/a" if pd.isna(v) else f"{v:.{p}f}"
        lines.append(f"| {r.problem} {r['name']} | {r.detector} | {f(r.detection_rate)} | "
                     f"{f(r.batch_hit_rate)} | {r.fa_row_rate:.4f} | {f(r.fa_batch_rate)} | "
                     f"{r.cost_per_m_rows_usd:.4f} | {r.rows_per_s:,.0f} | {f(r.clarity)} |")
    return "\n".join(lines)


def _inject_into_results(md: str) -> None:
    p = ROOT / "RESULTS_B.md"
    if not p.exists():
        return
    t = p.read_text(encoding="utf-8")
    new = f"<!-- METRICS:START -->\n{md}\n<!-- METRICS:END -->"
    if "<!-- METRICS:START -->" in t:
        t = re.sub(r"<!-- METRICS:START -->.*<!-- METRICS:END -->", lambda _: new, t, flags=re.S)
        p.write_text(t, encoding="utf-8")


if __name__ == "__main__":
    main()
