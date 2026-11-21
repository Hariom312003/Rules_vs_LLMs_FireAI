"""Comprehensive End-to-End Functional Test Suite for Web Application.

Tests:
1. FastAPI backend endpoints live (/api/health, /api/tax/query, /api/tax/calculate, /api/dq/check_text, /api/dq/inspect_record)
2. English, Hinglish, LLM parser, regex baseline, clarification questions
3. Direct tax calculation across FY 2024-25 and FY 2025-26
4. Concurrency & 422 validation
5. Streamlit frontend using streamlit.testing.v1.AppTest across all 3 tabs:
   - Tab 1: Natural Language Tax Advisor
   - Tab 2: Direct Tax Calculator & live what-if updates
   - Tab 3: Data Quality Inspector & full record analysis
"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Project_A"))
sys.path.insert(0, str(ROOT / "Project_B"))

API_BASE = "http://127.0.0.1:8000"


def test_fastapi_endpoints():
    print("\n==========================================")
    print("PHASE 2: FASTAPI BACKEND VERIFICATION")
    print("==========================================")

    # 1. Health
    r = requests.get(f"{API_BASE}/api/health", timeout=5)
    assert r.status_code == 200, f"Health check failed: {r.text}"
    health_data = r.json()
    print(f"[*] /api/health: OK (model: {health_data.get('active_model')})")

    # 2. Direct Calculate FY 2024-25
    payload_calc_24 = {
        "fy": "2024-25",
        "age": 30,
        "gross_salary": 1500000,
        "basic_salary": 600000,
        "hra_received": 250000,
        "rent_paid": 300000,
        "metro_city": True,
        "sec_80c": 150000,
        "sec_80ccd_1b": 50000,
        "sec_80d_self": 25000,
        "sec_80d_parents": 35000,
        "parents_senior": True,
        "self_senior": False,
        "home_loan_interest": 0,
    }
    r = requests.post(f"{API_BASE}/api/tax/calculate", json=payload_calc_24, timeout=5)
    assert r.status_code == 200, f"Calculate failed: {r.text}"
    d24 = r.json()
    print(f"[*] /api/tax/calculate (2024-25): Old=Rs {d24['old_regime']['total_tax']} New=Rs {d24['new_regime']['total_tax']} Winner={d24['recommended']} Savings=Rs {d24['savings']}")
    assert d24["old_regime"]["total_tax"] == 106600
    assert d24["new_regime"]["total_tax"] == 130000
    assert d24["recommended"] == "old"
    assert d24["savings"] == 23400

    # 3. Direct Calculate FY 2025-26 (Finance Act 2025 changes)
    payload_calc_25 = dict(payload_calc_24, fy="2025-26")
    r = requests.post(f"{API_BASE}/api/tax/calculate", json=payload_calc_25, timeout=5)
    assert r.status_code == 200, f"Calculate 2025 failed: {r.text}"
    d25 = r.json()
    print(f"[*] /api/tax/calculate (2025-26): Old=Rs {d25['old_regime']['total_tax']} New=Rs {d25['new_regime']['total_tax']} Winner={d25['recommended']} Savings=Rs {d25['savings']}")
    assert d25["new_regime"]["total_tax"] == 97500
    assert d25["recommended"] == "new"
    assert d25["savings"] == 9100

    # 4. Natural Language Query (English - Regex baseline)
    nl_payload_en = {
        "query": "I'm 32 and earn 18 lakh a year. No investments.",
        "fy": "2024-25",
        "mode": "regex",
    }
    r = requests.post(f"{API_BASE}/api/tax/query", json=nl_payload_en, timeout=10)
    assert r.status_code == 200
    q_en = r.json()
    print(f"[*] /api/tax/query (English, regex): status={q_en['status']} recommended={q_en.get('recommended')} old={q_en.get('old_regime', {}).get('total_tax')}")
    assert q_en["status"] == "ok"
    assert q_en["input"]["gross_salary"] == 1800000
    assert q_en["recommended"] == "new"

    # 5. Natural Language Query (Hinglish - Gemini LLM)
    nl_payload_hinglish = {
        "query": "Meri age 35 saal hai, salary 25 lakh per year hai. 80C mein 1.5 lakh invest kiya hai aur NPS mein 50 hazaar.",
        "fy": "2024-25",
        "mode": "llm",
    }
    r = requests.post(f"{API_BASE}/api/tax/query", json=nl_payload_hinglish, timeout=45)
    assert r.status_code == 200
    q_hi = r.json()
    print(f"[*] /api/tax/query (Hinglish, Gemini LLM): status={q_hi['status']} recommended={q_hi.get('recommended')} savings=Rs {abs(q_hi['old_regime']['total_tax'] - q_hi['new_regime']['total_tax'])}")
    assert q_hi["status"] == "ok"
    assert q_hi["input"]["gross_salary"] == 2500000
    assert q_hi["input"]["sec_80c"] == 150000
    assert q_hi["input"]["sec_80ccd_1b"] == 50000

    # 6. Clarification Request on Ambiguous Input
    nl_payload_ambig = {
        "query": "I earn 12 lakh a year",
        "fy": "2024-25",
        "mode": "regex",
    }
    r = requests.post(f"{API_BASE}/api/tax/query", json=nl_payload_ambig, timeout=10)
    assert r.status_code == 200
    q_ambig = r.json()
    print(f"[*] /api/tax/query (Ambiguous input refused to guess): status={q_ambig['status']} question={q_ambig.get('question')}")
    assert q_ambig["status"] == "needs_clarification"
    assert "age" in q_ambig["question"].lower() or "how old" in q_ambig["question"].lower()

    # 7. Data Quality Check Text (PII + Contradiction)
    dq_text_payload = {
        "resolution_description": "The ticket is still open and pending inspection. Call officer at 212-555-0199 or email test@example.com",
        "status": "Closed",
    }
    r = requests.post(f"{API_BASE}/api/dq/check_text", json=dq_text_payload, timeout=5)
    assert r.status_code == 200
    dq_res = r.json()
    alert_types = [a["type"] for a in dq_res["alerts"]]
    print(f"[*] /api/dq/check_text alerts detected: {alert_types}")
    assert "status_contradiction" in alert_types
    assert "pii_leak" in alert_types

    # 8. Data Quality Full Record Inspection (12 problem types)
    rec_payload = {
        "record": {
            "unique_key": "12345678",
            "agency": "NYPD",
            "complaint_type": "Noise",
            "descriptor": "Loud Music",
            "status": "Closed",
            "created_date": "2023-05-10T15:00:00.000",
            "closed_date": "2023-05-10T12:00:00.000",  # closed < created
            "incident_zip": "10001",
            "borough": "BROOKLYN",  # 10001 is Manhattan
            "latitude": -73.98,      # swapped lat/lon
            "longitude": 40.75,
            "resolution_description": "Contact john.doe@nyc.gov for info.",
        }
    }
    r = requests.post(f"{API_BASE}/api/dq/inspect_record", json=rec_payload, timeout=5)
    assert r.status_code == 200
    rec_res = r.json()
    rec_problems = [a["problem"] for a in rec_res["alerts"]]
    print(f"[*] /api/dq/inspect_record problems detected: {rec_problems}")
    assert "d" in rec_problems or any("lat" in a["reason"].lower() for a in rec_res["alerts"])
    assert "h" in rec_problems or any("earlier" in a["reason"].lower() for a in rec_res["alerts"])
    assert "i" in rec_problems or any("borough" in a["reason"].lower() for a in rec_res["alerts"])
    assert "l" in rec_problems or any("pii" in a["reason"].lower() or "email" in a["reason"].lower() for a in rec_res["alerts"])

    # 9. Request Validation & 422 Errors
    r = requests.post(f"{API_BASE}/api/tax/calculate", json={"invalid": "payload"}, timeout=5)
    assert r.status_code == 422, f"Expected 422, got {r.status_code}"
    print("[*] /api/tax/calculate schema validation (422): PASS")

    # 10. Concurrency & Throughput
    def worker(_):
        return requests.post(f"{API_BASE}/api/tax/calculate", json=payload_calc_24, timeout=5).status_code

    with ThreadPoolExecutor(max_workers=10) as ex:
        statuses = list(ex.map(worker, range(50)))
    assert all(s == 200 for s in statuses)
    print(f"[*] Concurrency test: 50 requests across 10 threads: 100% SUCCESS")


def test_streamlit_app():
    print("\n==========================================")
    print("PHASE 3: STREAMLIT APPTEST (UI INTEGRATION)")
    print("==========================================")

    at = AppTest.from_file("app_ui.py", default_timeout=30)
    at.run()
    assert not at.exception, f"App crashed on startup: {at.exception}"
    print(f"[*] Streamlit app initial load: SUCCESS (Title: {at.title[0].value if at.title else 'Loaded'})")

    # Verify all tabs exist
    assert len(at.tabs) == 3, f"Expected 3 tabs, found {len(at.tabs)}"
    print("[*] All 3 tabs verified: Tax Advisor, Direct Calculator, Data Quality Inspector")

    # TAB 1: Natural Language Advisor with default input
    calc_button = None
    for b in at.button:
        if b.label == "Calculate My Tax":
            calc_button = b
            break
    assert calc_button is not None, "Calculate My Tax button not found"
    calc_button.click()
    at.run()
    assert not at.exception, f"Exception after clicking Calculate My Tax: {at.exception}"
    print(f"[*] Tab 1 Tax Advisor ran successfully. Metric count: {len(at.metric)}")
    metric_labels = [m.label for m in at.metric]
    print(f"[*] Tab 1 Metric labels: {metric_labels}")
    assert any("Old Regime" in lbl for lbl in metric_labels)
    assert any("New Regime" in lbl for lbl in metric_labels)

    # TAB 1: Incomplete Query testing clarification refusal
    at.text_area[0].input("I earn 12 lakh a year")
    for b in at.button:
        if b.label == "Calculate My Tax":
            b.click()
            break
    at.run()
    assert not at.exception, f"Exception on ambiguous query: {at.exception}"
    warning_texts = [w.value for w in at.warning]
    print(f"[*] Tab 1 Ambiguous query warnings: {warning_texts}")
    assert any("Clarification" in w for w in warning_texts) or any("needs_clarification" in w for w in warning_texts)

    # TAB 2: Direct Tax Calculator
    # Modify inputs: change gross salary to 20 LPA
    for num in at.number_input:
        if "Gross Annual Salary" in num.label:
            num.set_value(2000000)
            break
    at.run()
    assert not at.exception, f"Exception after updating gross salary: {at.exception}"
    print(f"[*] Direct Calculator update to 20L: SUCCESS")

    # TAB 3: Data Quality Inspector
    # Select Full NYC 311 Record Inspector radio option
    for r in at.radio:
        if "Inspection Mode" in r.label:
            r.set_value("Full NYC 311 Record Inspector (12 Corruptions)")
            break
    at.run()
    assert not at.exception, f"Exception after switching DQ mode: {at.exception}"
    
    # Click inspect record button
    for b in at.button:
        if "Inspect Complete Record" in b.label:
            b.click()
            break
    at.run()
    assert not at.exception, f"Exception after inspecting complete record: {at.exception}"
    print(f"[*] Tab 3 DQ Inspector ran successfully. DataFrames displayed: {len(at.dataframe)}")
    assert len(at.dataframe) > 0, "Expected alert dataframe to be displayed in Tab 3"
    print("[*] Tab 3 Full Record Violations DataFrame populated and verified!")


if __name__ == "__main__":
    test_fastapi_endpoints()
    test_streamlit_app()
    print("\n==========================================")
    print("ALL INTEGRATION AND UI TESTS PASSED 100%!")
    print("==========================================")
