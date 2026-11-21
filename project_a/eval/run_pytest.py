"""Stage wrapper so run_all.py can run the pytest suite for Project A."""
import subprocess
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    rc = subprocess.call([sys.executable, "-m", "pytest", "project_a", "-q"], cwd=root)
    if rc not in (0, 5):  # 5 = no tests collected
        raise RuntimeError(f"pytest exited with {rc}")
