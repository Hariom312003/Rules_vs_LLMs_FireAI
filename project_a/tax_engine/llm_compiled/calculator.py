"""Implementation (c), step 2: run the reviewed, LLM-compiled rules. No LLM at run time.

The runner loads generated/rules_<fy>.py and refuses to execute it unless its first line
says "# REVIEWED: YES" (set by a human after reading and testing it). Pass
allow_unreviewed=True ONLY to measure the raw model output (see eval/run_change.py).
"""
from __future__ import annotations

import importlib.util
from functools import lru_cache
from pathlib import Path

from ..models import TaxpayerInput, TaxResult

GENERATED_DIR = Path(__file__).parent / "generated"


@lru_cache(maxsize=None)
def _load(path: str):
    spec = importlib.util.spec_from_file_location(Path(path).stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class LLMCompiledCalculator:
    name = "llm_compiled"

    def __init__(self, allow_unreviewed: bool = False, directory: Path | None = None):
        self.allow_unreviewed = allow_unreviewed
        self.directory = directory or GENERATED_DIR

    def _module(self, fy: str):
        path = self.directory / f"rules_{fy.replace('-', '_')}.py"
        if not path.exists():
            raise ValueError(f"no compiled rules for FY {fy}; run compile_rules.py")
        head = path.read_text(encoding="utf-8").splitlines()[0]
        if not head.startswith("# REVIEWED: YES") and not self.allow_unreviewed:
            raise PermissionError(f"{path.name} has not been reviewed ('{head}')")
        return _load(str(path))

    def compute(self, inp: TaxpayerInput) -> TaxResult:
        return TaxResult.model_validate(self._module(inp.fy).calculate(inp.model_dump()))
