"""Task 4: measure all three implementations (+ the parser).

    python -m project_a.eval.run_eval                       # hand rules + compiled rules + regex parser (seconds, free)
    python -m project_a.eval.run_eval --llm                 # + LLM query-time + LLM parser (small, see defaults)
    python -m project_a.eval.run_eval --llm --llm-cases 40 --det-inputs 5   # bigger run

Per implementation:
  accuracy      rupee-exact share of (case, regime) totals; also whole-case (both regimes + recommendation)
  determinism   same input repeated N times: how many distinct outputs (1 = deterministic)
  latency       p50 / p95 per request
  cost / 1,000  LLM: tokens x Gemini list price (notional for a local model); others: CPU time at an
                ASSUMED $0.04 per vCPU-hour
  traceability  share of trace checks passed (see traceability.py)
  errors        calls that raised (loud) vs wrong-but-valid answers (silent)
Writes project_a/results/metrics_a.json and fills the table between the METRICS_A markers in RESULTS_A.md.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import time
from collections import Counter, defaultdict
from pathlib import Path

from common.llm import LLMClient

from ..parser.parse import parse
from ..tax_engine.hand_rules.calculator import HandRulesCalculator
from ..tax_engine.llm_compiled.calculator import LLMCompiledCalculator
from ..tax_engine.llm_query.calculator import LLMQueryCalculator
from ..tax_engine.models import TaxpayerInput
from ..tests.build_suite import DATA, load_cases
from .traceability import traced_share

ROOT = Path(__file__).resolve().parents[2]
RESULTS = Path(__file__).resolve().parents[1] / "results"
CPU_USD_PER_HOUR = 0.04


def pct(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else float("nan")


def spread(cases: list[dict], n: int) -> list[dict]:
    """n cases spread evenly over the whole list (keeps every category represented)."""
    if n >= len(cases):
        return cases
    step = len(cases) / n
    return [cases[int(i * step)] for i in range(n)]


_CATS = ["new_edge", "old_edge", "surch_new", "surch_old", "c80ccd", "c80", "d80_self_sr", "d80_self", "d80_par",
         "hl", "all_ded", "hra", "extreme", "anchor", "rand"]


def category(cid: str) -> str:
    return next((c for c in _CATS if cid.startswith(c)), cid)


def evaluate(calc, cases: list[dict], llm_client: LLMClient | None = None) -> dict:
    ok_reg = tot_reg = ok_case = 0
    lat, errors, trace, silent, by_cat = [], Counter(), [], 0, defaultdict(lambda: [0, 0])
    wrong_ids: list[str] = []
    for c in cases:
        inp = TaxpayerInput(**c["input"])
        t0 = time.perf_counter()
        try:
            r = calc.compute(inp)
        except Exception as e:  # LOUD failure: the caller knows something went wrong
            errors[type(e).__name__] += 1
            lat.append(time.perf_counter() - t0)
            by_cat[category(c["id"])][1] += 1
            continue
        lat.append(time.perf_counter() - t0)
        got = (r.old.total_tax, r.new.total_tax)
        want = (c["expected_old"], c["expected_new"])
        ok_reg += (got[0] == want[0]) + (got[1] == want[1])
        tot_reg += 2
        good = got == want and r.recommended == c["expected_recommended"]
        ok_case += good
        by_cat[category(c["id"])][0] += good
        by_cat[category(c["id"])][1] += 1
        if not good:
            silent += 1  # valid answer, wrong, no error raised
            wrong_ids.append(c["id"])
        trace.append(traced_share(r))
    n = len(cases)
    out = {"n_cases": n, "regime_exact": ok_reg / tot_reg if tot_reg else 0.0, "case_exact": ok_case / n,
           "loud_errors": sum(errors.values()), "error_types": dict(errors), "silent_wrong": silent,
           "latency_p50_s": pct(lat, 0.5), "latency_p95_s": pct(lat, 0.95),
           "traceability": statistics.mean(trace) if trace else 0.0,
           "by_category": {k: f"{v[0]}/{v[1]}" for k, v in sorted(by_cat.items())}, "wrong_ids": wrong_ids[:25]}
    if llm_client is not None:
        s = llm_client.stats.summary()
        out["cost_per_1000_usd"] = s["notional_gemini_usd"] / max(1, s["live_calls"]) * 1000
        out["tokens_per_request"] = (s["in_tokens"] + s["out_tokens"]) / max(1, s["live_calls"])
    else:
        out["cost_per_1000_usd"] = statistics.mean(lat) * 1000 * CPU_USD_PER_HOUR / 3600
    return out


def determinism(calc, cases: list[dict], repeats: int) -> dict:
    distinct_totals, distinct_json = [], []
    for c in cases:
        inp = TaxpayerInput(**c["input"])
        totals, blobs = set(), set()
        for _ in range(repeats):
            try:
                r = calc.compute(inp)
                totals.add((r.old.total_tax, r.new.total_tax, r.recommended))
                blobs.add(r.model_dump_json())
            except Exception as e:
                totals.add(("error", type(e).__name__))
                blobs.add(type(e).__name__)
        distinct_totals.append(len(totals))
        distinct_json.append(len(blobs))
    return {"inputs": len(cases), "repeats": repeats, "max_distinct_totals": max(distinct_totals),
            "max_distinct_full_outputs": max(distinct_json), "deterministic": max(distinct_json) == 1}


def parser_eval(descs: list[dict], mode: str, client: LLMClient | None) -> dict:
    ok_fields = asked_right = asked_when_ok = missed_ask = relevant = n_ok = n_ask = errs = 0
    hallu = 0
    lat = []
    guessed_ids, unneeded_ids, wrong_extract_ids = [], [], []
    for d in descs:
        t0 = time.perf_counter()
        try:
            o = parse(d["text"], mode=mode, client=client)
        except Exception:
            errs += 1
            o = None
        lat.append(time.perf_counter() - t0)
        if d["expected"] is not None:
            n_ok += 1
            if o is None:
                continue
            if o.status == "needs_clarification":
                asked_when_ok += 1
                unneeded_ids.append(f"{d['id']}:{','.join(o.missing)}")
            elif all(getattr(o.input, k) == v for k, v in d["expected"].items()):
                dump = o.input.model_dump()
                extra = [k for k, v in dump.items() if k not in d["expected"] and k != "fy" and v not in (0, False)]
                hallu += bool(extra)
                ok_fields += not extra
            else:
                wrong_extract_ids.append(d["id"])
        else:
            n_ask += 1
            if o is None:
                continue
            if o.status == "needs_clarification":
                asked_right += 1
                relevant += bool(set(o.missing) & set(d["clarify"]))
            else:
                missed_ask += 1  # guessed when it should have asked: the failure the brief cares about most
                guessed_ids.append(f"{d['id']}->{json.dumps({k: v for k, v in o.input.model_dump().items() if v not in (0, False, None) and k != 'fy'})}")
    out = {"n": len(descs), "extraction_exact": ok_fields / n_ok, "n_should_extract": n_ok,
           "asked_when_not_needed": asked_when_ok, "n_should_ask": n_ask, "asked_correctly": asked_right,
           "guessed_instead_of_asking": missed_ask, "question_on_right_topic": relevant,
           "invented_fields": hallu, "guessed_ids": guessed_ids, "asked_unnecessarily_ids": unneeded_ids,
           "wrong_extraction_ids": wrong_extract_ids, "exceptions": errs, "latency_p50_s": pct(lat, 0.5), "latency_p95_s": pct(lat, 0.95)}
    if client is not None:
        s = client.stats.summary()
        out["cost_per_1000_usd"] = s["notional_gemini_usd"] / max(1, s["live_calls"]) * 1000
    return out


def fmt(x, p=3):
    return "n/a" if x is None or (isinstance(x, float) and x != x) else f"{x:.{p}f}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--parser-only", action="store_true", help="re-run only the parser comparison and merge into the existing metrics_a.json")
    ap.add_argument("--llm-cases", type=int, default=16)
    ap.add_argument("--det-inputs", type=int, default=2)
    ap.add_argument("--repeats", type=int, default=10)
    args = ap.parse_args(argv)

    cases = load_cases("2024-25")
    det_cases = spread(cases, 30)
    descs = [json.loads(l) for l in (DATA / "descriptions.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    res: dict = {"fy": "2024-25"}
    if args.parser_only:
        res = json.loads((RESULTS / "metrics_a.json").read_text(encoding="utf-8"))

    for name, calc in (() if args.parser_only else (("hand_rules", HandRulesCalculator()), ("llm_compiled", LLMCompiledCalculator()))):
        print(f"[{name}] {len(cases)} cases")
        try:
            res[name] = evaluate(calc, cases)
            res[name]["determinism"] = determinism(calc, det_cases, args.repeats)
        except Exception as e:  # e.g. compiled rules not reviewed yet
            res[name] = {"error": repr(e)}
        print("  ", {k: v for k, v in res[name].items() if k in ("regime_exact", "case_exact", "error")})

    client = None
    if args.llm and not args.parser_only:
        client = LLMClient()
        q = LLMQueryCalculator(client)
        sub = spread(cases, args.llm_cases)
        print(f"[llm_query] model={client.model}: accuracy on {len(sub)} cases")
        res["llm_query"] = evaluate(q, sub, client)
        res["llm_query"]["model"] = client.model
        client2 = LLMClient()  # fresh stats for the determinism runs
        q2 = LLMQueryCalculator(client2)
        print(f"[llm_query] determinism {args.det_inputs} inputs x {args.repeats} repeats")
        res["llm_query"]["determinism"] = determinism(q2, spread(cases, args.det_inputs), args.repeats)
        print("  ", {k: v for k, v in res["llm_query"].items() if k in ("regime_exact", "case_exact", "loud_errors", "silent_wrong")})

    print("[parser] regex baseline")
    res["parser_regex"] = parser_eval(descs, "regex", None)
    if args.llm:
        pc = LLMClient()
        print("[parser] LLM extractor + rule validation")
        res["parser_llm"] = parser_eval(descs, "llm", pc)
        res["parser_llm"]["model"] = pc.model

    RESULTS.mkdir(exist_ok=True)
    prev_path = RESULTS / "metrics_a.json"
    if prev_path.exists() and not args.parser_only:  # a run without --llm must not erase measured LLM results
        prev = json.loads(prev_path.read_text(encoding="utf-8"))
        for k in ("llm_query", "parser_llm"):
            if k not in res and k in prev:
                res[k] = {**prev[k], "carried_over_from_earlier_run": True}
    prev_path.write_text(json.dumps(res, indent=2, default=str), encoding="utf-8")
    md = to_markdown(res)
    p = ROOT / "RESULTS_A.md"
    if p.exists() and "<!-- METRICS_A:START -->" in p.read_text(encoding="utf-8"):
        t = p.read_text(encoding="utf-8")
        p.write_text(re.sub(r"<!-- METRICS_A:START -->.*<!-- METRICS_A:END -->",
                            lambda _: f"<!-- METRICS_A:START -->\n{md}\n<!-- METRICS_A:END -->", t, flags=re.S), encoding="utf-8")
    print(md)


def to_markdown(res: dict) -> str:
    names = [n for n in ("hand_rules", "llm_query", "llm_compiled") if n in res]
    head = "| Metric | " + " | ".join(names) + " |\n|---|" + "---|" * len(names)
    rows = []
    def row(label, f):
        rows.append(f"| {label} | " + " | ".join(f(res[n]) if "error" not in res[n] else "n/a" for n in names) + " |")
    row("Cases evaluated", lambda r: str(r["n_cases"]))
    row("Rupee-exact accuracy (per regime)", lambda r: fmt(r["regime_exact"]))
    row("Whole-case exact (both regimes + recommendation)", lambda r: fmt(r["case_exact"]))
    row("Loud errors / silent wrong answers", lambda r: f"{r['loud_errors']} / {r['silent_wrong']}")
    row("Determinism (distinct outputs over repeats)", lambda r: f"{r['determinism']['max_distinct_full_outputs']} distinct over {r['determinism']['repeats']} runs x {r['determinism']['inputs']} inputs")
    row("Latency p50 / p95 (s)", lambda r: f"{fmt(r['latency_p50_s'], 4)} / {fmt(r['latency_p95_s'], 4)}")
    row("Cost per 1,000 requests (USD)", lambda r: fmt(r["cost_per_1000_usd"], 4))
    row("Every rupee traces to a clause (share of checks)", lambda r: fmt(r["traceability"]))
    out = head + "\n" + "\n".join(rows)
    if "parser_regex" in res:
        out += "\n\n| Parser (50 descriptions) | extraction exact | guessed instead of asking | asked when not needed | invented fields | p50 latency (s) | cost / 1,000 (USD) |\n|---|---|---|---|---|---|---|\n"
        for k in ("parser_regex", "parser_llm"):
            if k in res:
                r = res[k]
                out += (f"| {k.replace('parser_', '')} | {r['extraction_exact']:.2f} ({r['n_should_extract']} cases) | "
                        f"{r['guessed_instead_of_asking']}/{r['n_should_ask']} | {r['asked_when_not_needed']}/{r['n_should_extract']} | "
                        f"{r['invented_fields']} | {fmt(r.get('latency_p50_s_uncached', r['latency_p50_s']), 2)} | "
                        f"{fmt(r.get('cost_per_1000_usd_uncached', r.get('cost_per_1000_usd', 0.0)), 3)} |\n")
    return out


if __name__ == "__main__":
    main()
