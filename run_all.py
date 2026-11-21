"""Single entry point that reproduces every reported number across both Project A and Project B.

    python run_all.py              # runs all stages (skips expensive LLM calls if no key is set)
    python run_all.py --project a  # only Project A (tax engine)
    python run_all.py --project b  # only Project B (data quality)
    python run_all.py --skip-llm   # skip stages that call LLMs
    python run_all.py --setup      # create venv + install deps, then exit

Each stage is a module with a main(); stages that are missing are reported as TODO.
"""
from __future__ import annotations

import argparse
import importlib
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Project_A"))
sys.path.insert(0, str(ROOT / "Project_B"))

# (project, label, module, llm) -- llm: False | True (required) | "optional" (adds --llm if a key is set)
STAGES = [
    ("a", "A1 build test suite", "project_a.tests.build_suite", False),
    ("a", "A2 pytest (hand-coded rules)", "project_a.eval.run_pytest", False),
    ("a", "A4 measure 3 implementations + parser", "project_a.eval.run_eval", "optional"),
    ("a", "A5 FY2025-26 change experiments", "project_a.eval.run_change", "optional"),
    ("b", "B1 profile raw 2023 data", "project_b.profiling.profile", False),
    ("b", "B3/B4 detectors x corruptions", "project_b.eval.run_eval", "optional"),
    ("b", "B5 hybrid pipeline end-to-end", "project_b.pipeline.run", "optional"),
]


def setup() -> None:
    venv = ROOT / ".venv"
    if not venv.exists():
        subprocess.check_call([sys.executable, "-m", "venv", str(venv)])
    py = venv / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")
    subprocess.check_call([str(py), "-m", "pip", "install", "-U", "pip"])
    subprocess.check_call([str(py), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])
    print(f"\nSetup done. Activate with: {venv}\\Scripts\\activate" if sys.platform == "win32"
          else f"\nSetup done. Activate with: source {venv}/bin/activate")


def main() -> int:
    ap = argparse.ArgumentParser(description="Reproduce all numbers for Rules vs LLMs assignment.")
    ap.add_argument("--project", choices=["a", "b"], help="Run only Project A or Project B")
    ap.add_argument("--skip-llm", action="store_true", help="Skip stages requiring LLM API calls")
    ap.add_argument("--setup", action="store_true", help="Set up virtualenv and install dependencies")
    args = ap.parse_args()

    if args.setup:
        setup()
        return 0

    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")

    has_llm = bool(os.getenv("GEMINI_API_KEY")) or os.getenv("LLM_BACKEND") == "local"

    print("=" * 70)
    print(" FIRE AI — RULES VS LLMS TAKE-HOME REPRODUCIBILITY HARNESS")
    print("=" * 70)
    print(f" LLM Backend Enabled : {has_llm and not args.skip_llm}")
    print(f" Python Executable   : {sys.executable}")
    print(f" Working Directory   : {ROOT}")
    print("=" * 70)

    failed = 0
    for proj, label, mod, needs_llm in STAGES:
        if args.project and proj != args.project:
            continue
        if needs_llm is True and (args.skip_llm or not has_llm):
            print(f"[SKIP] {label} (requires LLM API key)")
            continue
        try:
            m = importlib.import_module(mod)
        except ModuleNotFoundError as e:
            if e.name and mod.startswith(e.name):
                print(f"[TODO] {label}: {mod} not found")
                continue
            raise

        t0 = time.perf_counter()
        print(f"[RUN ] {label}...")
        use_llm = needs_llm == "optional" and not args.skip_llm and has_llm
        sys.argv = [mod] + (["--llm"] if use_llm else [])
        try:
            m.main()
        except NotImplementedError:
            print(f"[TODO] {label}: not implemented yet")
            continue
        except Exception as e:
            failed += 1
            print(f"[FAIL] {label}: {e!r}")
            continue
        print(f"[ OK ] {label} ({time.perf_counter() - t0:.2f}s)")

    print("=" * 70)
    if failed:
        print(f"❌ {failed} stage(s) failed.")
        return 1
    else:
        print("✅ All requested stages completed successfully.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
