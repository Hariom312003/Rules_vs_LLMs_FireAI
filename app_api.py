"""FastAPI backend for Rules vs LLMs project.

Exposes endpoints for:
- Health check (/api/health)
- Plain-language tax query parsing & calculation (LLM + Rules) (/api/tax/query)
- Direct structured tax calculation (Hand-coded Rules) (/api/tax/calculate)
- Data quality checking for free text (/api/dq/check_text)
- Full record data quality inspection across all 12 corruptions (/api/dq/inspect_record)
"""
import os
import sys
from pathlib import Path
from typing import Any, Literal

import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Ensure project directories are in sys.path
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Project_A"))
sys.path.insert(0, str(ROOT / "Project_B"))

from project_a.service import answer
from project_a.tax_engine.hand_rules.calculator import HandRulesCalculator
from project_a.tax_engine.models import TaxpayerInput
from project_b.detectors.rules import RuleDetectors
from project_b.detectors.stats import StatDetectors

app = FastAPI(
    title="Rules vs LLMs API",
    description="Backend API powering Indian Income Tax computation & Data Quality detection",
    version="1.0.0",
)

ALLOWED_ORIGINS = [
    orig.strip()
    for orig in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if orig.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

calc = HandRulesCalculator()
dq_rules = RuleDetectors()
dq_stats = StatDetectors()


class TaxQueryRequest(BaseModel):
    query: str = Field(..., description="Natural language description of taxpayer finances", min_length=2)
    mode: Literal["llm", "regex"] = Field("llm", description="Extractor to use")
    fy: Literal["2024-25", "2025-26"] = Field("2024-25", description="Assessment/financial year")


class TextDQRequest(BaseModel):
    resolution_description: str = Field(..., description="Free text resolution note")
    status: str = Field("Closed", description="Ticket status (e.g. Closed, Open, Pending)")


class RecordDQRequest(BaseModel):
    record: dict[str, Any] = Field(..., description="NYC 311 record dictionary")


@app.get("/")
def read_root():
    return {
        "service": "Rules vs LLMs API",
        "status": "online",
        "endpoints": [
            "/api/health",
            "/api/tax/query",
            "/api/tax/calculate",
            "/api/dq/check_text",
            "/api/dq/inspect_record",
        ],
    }


@app.get("/api/health")
def health_check():
    gemini_key_set = bool(os.getenv("GEMINI_API_KEY"))
    model = os.getenv("GEMINI_MODEL", "gemini-3.5-flash")
    return {
        "status": "healthy",
        "version": "1.0.0",
        "gemini_configured": gemini_key_set,
        "active_model": model,
        "tax_engine": "HandRulesCalculator (fractions.Fraction)",
        "supported_fys": ["2024-25", "2025-26"],
    }


@app.post("/api/tax/query")
def tax_query(req: TaxQueryRequest):
    """Processes a natural language query with Gemini extractor and hand-coded tax rules."""
    try:
        result = answer(req.query, mode=req.mode, fy=req.fy, calculator=calc)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/tax/calculate")
def tax_calculate(inp: TaxpayerInput):
    """Computes exact tax under both regimes using hand-coded deterministic rules."""
    try:
        res = calc.compute(inp)
        return {
            "status": "ok",
            "recommended": res.recommended,
            "explanation": res.explanation,
            "savings": abs(res.old.total_tax - res.new.total_tax),
            "old_regime": {
                "taxable_income": res.old.taxable_income,
                "tax_before_rebate": res.old.tax_before_rebate,
                "rebate_87a": res.old.rebate_87a,
                "surcharge": res.old.surcharge,
                "cess": res.old.cess,
                "total_tax": res.old.total_tax,
                "trace": [t.model_dump() for t in res.old.trace],
            },
            "new_regime": {
                "taxable_income": res.new.taxable_income,
                "tax_before_rebate": res.new.tax_before_rebate,
                "rebate_87a": res.new.rebate_87a,
                "surcharge": res.new.surcharge,
                "cess": res.new.cess,
                "total_tax": res.new.total_tax,
                "trace": [t.model_dump() for t in res.new.trace],
            },
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/dq/check_text")
def check_text_dq(req: TextDQRequest):
    """Checks free text for PII leaks (phone/email) and resolution-vs-status contradiction."""
    df = pd.DataFrame([{
        "unique_key": "sample_1",
        "status": req.status,
        "resolution_description": req.resolution_description,
        "descriptor": "",
        "complaint_type": "",
    }])
    alerts = []
    # Check k: Resolution contradicts status
    for alert in dq_rules._k(df):
        alerts.append({
            "problem": alert.problem_key,
            "type": "status_contradiction",
            "reason": alert.reason,
            "observed": alert.observed,
        })
    # Check l: PII in free text
    for alert in dq_rules._l(df):
        alerts.append({
            "problem": alert.problem_key,
            "type": "pii_leak",
            "reason": alert.reason,
            "observed": alert.observed,
        })
    return {"alerts": alerts, "clean": len(alerts) == 0}


@app.post("/api/dq/inspect_record")
def inspect_record(req: RecordDQRequest):
    """Full data quality inspection for an NYC 311 record across all rule detectors."""
    df = pd.DataFrame([req.record])
    alerts = []
    for a in dq_rules.detect(df):
        alerts.append({
            "problem": a.problem_key,
            "detector": a.detector,
            "family": a.family,
            "reason": a.reason,
            "column": a.column,
            "observed": a.observed,
            "expected": a.expected,
            "clarity": a.clarity(),
        })
    return {"alerts": alerts, "clean": len(alerts) == 0, "total_alerts": len(alerts)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app_api:app", host="127.0.0.1", port=8000, reload=True)
