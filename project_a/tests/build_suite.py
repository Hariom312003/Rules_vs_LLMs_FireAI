"""Task 1: build the test suite (deterministic, seeded).

    python -m project_a.tests.build_suite

Writes (all committed so results are reproducible):
  tests/data/cases.jsonl             FY 2024-25 cases      {id, fy, input, expected_old, expected_new, expected_recommended, source, note}
  tests/data/cases_fy2025_26.jsonl   FY 2025-26 cases (used for the Task 5 law change)
  tests/data/descriptions.jsonl      50 plain-language descriptions (from descriptions.py)
  tests/data/official_checklist.csv  >=30 inputs to run through the Income Tax Dept calculator by hand

Expected values come from tests/oracle.py (an independent encoding of the rules) and from
tests/anchors.py (hand-worked). They never come from any of the three implementations.
`source` is "oracle" or "hand_worked"; it only becomes "official_calc" after a human fills
official_checklist.csv (see tests/OFFICIAL_CHECK.md).
"""
from __future__ import annotations

import csv
import json
import random
from pathlib import Path

from .anchors import ANCHORS
from .descriptions import DESCRIPTIONS
from .oracle import expected

DATA = Path(__file__).parent / "data"
OFF = [-10, -5, -1, 0, 1, 5, 10]  # around every threshold (5 matters because of Rs 10 rounding)

NEW_THR = {"2024-25": [300_000, 700_000, 1_000_000, 1_200_000, 1_500_000],
           "2025-26": [400_000, 800_000, 1_200_000, 1_600_000, 2_000_000, 2_400_000]}
OLD_THR = [(35, [250_000, 500_000, 1_000_000]), (62, [300_000, 500_000, 1_000_000]),
           (83, [500_000, 1_000_000])]
SURCH = [5_000_000, 10_000_000, 20_000_000, 50_000_000]


def _case(fy: str, cid: str, note: str, **inp) -> dict:
    inp = {"age": 30, **inp, "fy": fy}
    e = expected(inp)
    return {"id": cid, "fy": fy, "input": inp, "expected_old": e["old"], "expected_new": e["new"],
            "expected_recommended": e["recommended"], "source": "oracle", "note": note}


def generate(fy: str, n_random: int, old_extra: bool = True) -> list[dict]:
    out: list[dict] = []
    add = lambda cid, note, **kw: out.append(_case(fy, cid, note, **kw))

    for t in NEW_THR[fy]:                       # new-regime slab edges and the 87A limit
        for o in OFF:
            add(f"new_edge_{t}_{o:+d}", f"new regime taxable {t}{o:+d}", gross_salary=t + o + 75_000)
    for age, ths in OLD_THR:                    # old-regime slab edges per age band
        for t in ths:
            for o in OFF:
                add(f"old_edge_a{age}_{t}_{o:+d}", f"old regime age {age} taxable {t}{o:+d}",
                    age=age, gross_salary=t + o + 50_000)
    for t in SURCH:                             # surcharge thresholds, both regimes
        for o in (-10, -1, 0, 1, 10, 1_000, 100_000):
            add(f"surch_new_{t}_{o:+d}", f"new regime taxable {t}{o:+d}", gross_salary=t + o + 75_000)
            add(f"surch_old_{t}_{o:+d}", f"old regime taxable {t}{o:+d}", gross_salary=t + o + 50_000)

    base = dict(gross_salary=1_200_000, age=30)  # deduction caps
    for v in (0, 149_999, 150_000, 150_001, 300_000):
        add(f"c80_{v}", "80C cap", **base, sec_80c=v)
    for v in (49_999, 50_000, 50_001):
        add(f"c80ccd_{v}", "80CCD(1B) cap", **base, sec_80ccd_1b=v)
    for v in (24_999, 25_000, 26_000):
        add(f"d80_self_{v}", "80D self non-senior", **base, sec_80d_self=v)
    for v in (49_999, 50_000, 51_000):
        add(f"d80_self_sr_{v}", "80D self senior", gross_salary=1_200_000, age=62, sec_80d_self=v)
    for v, sr in ((25_000, False), (30_000, False), (50_000, True), (60_000, True)):
        add(f"d80_par_{v}_{int(sr)}", "80D parents", **base, sec_80d_parents=v, parents_senior=sr)
    for v in (199_999, 200_000, 250_000):
        add(f"hl_{v}", "home-loan interest cap", **base, home_loan_interest=v)
    add("all_ded_max", "every deduction at its cap", gross_salary=2_500_000, sec_80c=150_000,
        sec_80ccd_1b=50_000, sec_80d_self=25_000, sec_80d_parents=50_000, parents_senior=True,
        home_loan_interest=200_000)
    add("all_ded_over_gross", "deductions larger than income", gross_salary=300_000, sec_80c=150_000,
        sec_80ccd_1b=50_000, sec_80d_self=25_000, home_loan_interest=200_000)

    hra = dict(gross_salary=1_500_000, basic_salary=600_000, age=30)  # HRA three-way minimum
    add("hra_recv_min_metro", "HRA received is smallest (metro)", **hra, hra_received=100_000, rent_paid=400_000, metro_city=True)
    add("hra_pct_min_metro", "50% of basic smallest (metro)", **hra, hra_received=400_000, rent_paid=500_000, metro_city=True)
    add("hra_pct_min_nonmetro", "40% of basic smallest (non-metro)", **hra, hra_received=400_000, rent_paid=500_000, metro_city=False)
    add("hra_rent_min", "rent minus 10% of basic smallest", **hra, hra_received=400_000, rent_paid=120_000, metro_city=True)
    add("hra_rent_below_10pct", "rent below 10% of basic -> 0", **hra, hra_received=300_000, rent_paid=50_000, metro_city=True)
    add("hra_no_rent", "HRA received but no rent", **hra, hra_received=300_000, rent_paid=0, metro_city=False)
    add("hra_no_hra", "rent paid but no HRA", **hra, hra_received=0, rent_paid=300_000, metro_city=True)
    add("hra_no_basic", "basic unknown (0)", gross_salary=1_500_000, hra_received=300_000, rent_paid=300_000)

    for g in (0, 1, 30_000, 50_000, 50_001, 75_000, 75_001, 60_000_000, 100_000_000):  # extremes
        add(f"extreme_{g}", f"gross salary {g}", gross_salary=g)
    for g in (60_000_000, 100_000_000):
        add(f"extreme_old_dedn_{g}", "37% band with deductions", gross_salary=g, sec_80c=150_000, age=70)

    rnd = random.Random(2024 if fy == "2024-25" else 2025)  # seeded mixed profiles
    for i in range(n_random):
        g = rnd.choice([rnd.randint(2, 40) * 50_000, rnd.randint(4, 60) * 100_000, rnd.randint(1, 30) * 1_000_000])
        basic = int(g * rnd.uniform(0.3, 0.5)) // 100 * 100
        add(f"rand_{i:03d}", "random mixed profile", age=rnd.choice([24, 29, 35, 44, 52, 59, 60, 67, 82]),
            gross_salary=g, basic_salary=basic,
            hra_received=rnd.choice([0, 0, int(basic * 0.4) // 100 * 100, int(basic * 0.5) // 100 * 100]),
            rent_paid=rnd.choice([0, 0, int(g * 0.15) // 1000 * 1000, int(g * 0.25) // 1000 * 1000]),
            metro_city=rnd.random() < 0.5, sec_80c=rnd.choice([0, 50_000, 100_000, 150_000, 200_000]),
            sec_80ccd_1b=rnd.choice([0, 0, 25_000, 50_000]), sec_80d_self=rnd.choice([0, 12_000, 25_000, 40_000]),
            sec_80d_parents=rnd.choice([0, 0, 20_000, 35_000, 60_000]), parents_senior=rnd.random() < 0.4,
            home_loan_interest=rnd.choice([0, 0, 90_000, 200_000, 300_000]))
    return out


def anchors() -> list[dict]:
    out = []
    for a in ANCHORS:
        e = expected(a["input"])
        assert (e["old"], e["new"]) == (a["old"], a["new"]), (a["id"], e, a)  # oracle must agree with the hand work
        out.append({"id": a["id"], "fy": a["input"]["fy"], "input": a["input"], "expected_old": a["old"],
                    "expected_new": a["new"], "expected_recommended": "old" if a["old"] < a["new"] else "new",
                    "source": "hand_worked", "note": a["why"]})
    return out


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n", encoding="utf-8")


def load_cases(fy: str = "2024-25") -> list[dict]:
    name = "cases.jsonl" if fy == "2024-25" else "cases_fy2025_26.jsonl"
    return [json.loads(l) for l in (DATA / name).read_text(encoding="utf-8").splitlines() if l.strip()]


def main() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    anc = anchors()
    c24 = [a for a in anc if a["fy"] == "2024-25"] + generate("2024-25", n_random=60)
    c25 = [a for a in anc if a["fy"] == "2025-26"] + generate("2025-26", n_random=40)
    write_jsonl(DATA / "cases.jsonl", c24)
    write_jsonl(DATA / "cases_fy2025_26.jsonl", c25)
    write_jsonl(DATA / "descriptions.jsonl", DESCRIPTIONS)

    pick = c24[::max(1, len(c24) // 36)][:36]  # evenly spread across categories
    cols = ["age", "gross_salary", "basic_salary", "hra_received", "rent_paid", "metro_city", "sec_80c",
            "sec_80ccd_1b", "sec_80d_self", "sec_80d_parents", "parents_senior", "self_senior", "home_loan_interest"]
    
    existing = {}
    csv_path = DATA / "official_checklist.csv"
    if csv_path.exists():
        with csv_path.open(encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("official_old_total_tax", "").strip():
                    existing[r["id"]] = (r["official_old_total_tax"], r.get("official_new_total_tax", ""),
                                         r.get("checked_by", ""), r.get("notes", ""))

    with (DATA / "official_checklist.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "fy"] + cols + ["official_old_total_tax", "official_new_total_tax", "checked_by", "notes"])
        for c in pick:
            filled = existing.get(c["id"], ("", "", "", ""))
            w.writerow([c["id"], c["fy"]] + [c["input"].get(k, 0) for k in cols] + list(filled))
    print(f"FY24-25 cases: {len(c24)} | FY25-26 cases: {len(c25)} | descriptions: {len(DESCRIPTIONS)} "
          f"| official checklist rows: {len(pick)}")


if __name__ == "__main__":
    main()
