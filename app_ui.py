"""Streamlit Frontend for Rules vs LLMs.

Interactive UI for:
1. Natural Language Tax Advisor (Gemini extractor + Deterministic Rules via FastAPI)
2. Direct What-If Tax Calculator (0.1ms hand-coded rules)
3. Data Quality Inspector (Full Project B rules detector)
"""
import os
import sys
import time
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

# Expose Streamlit secrets to os.environ so all submodules (common.llm, etc.) have access
try:
    if hasattr(st, "secrets"):
        for k, v in st.secrets.items():
            if isinstance(v, (str, int, float, bool)) and k not in os.environ:
                os.environ[k] = str(v)
except Exception:
    pass

# Setup paths
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "Project_A"))
sys.path.insert(0, str(ROOT / "Project_B"))

from project_a.service import answer
from project_a.tax_engine.hand_rules.calculator import HandRulesCalculator
from project_a.tax_engine.models import TaxpayerInput
from project_b.detectors.rules import RuleDetectors

def get_default_api_base() -> str:
    """Retrieve API base URL from Streamlit secrets, environment variables, or local default."""
    try:
        if hasattr(st, "secrets") and "API_BASE_URL" in st.secrets:
            return str(st.secrets["API_BASE_URL"]).rstrip("/")
    except Exception:
        pass
    env_val = os.getenv("API_BASE_URL")
    if env_val:
        return env_val.rstrip("/")
    return "http://127.0.0.1:8000"

st.set_page_config(
    page_title="Rules vs LLMs | Fire AI",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for styling
st.markdown("""
<style>
    .metric-card {
        background-color: #f8f9fa;
        border-radius: 8px;
        padding: 16px;
        border-left: 5px solid #1a73e8;
        box-shadow: 0 1px 3px rgba(0,0,0,0.1);
    }
    .winner-badge {
        background-color: #e6f4ea;
        color: #137333;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 700;
        font-size: 1.1rem;
        display: inline-block;
        margin-bottom: 15px;
    }
    .warning-badge {
        background-color: #fef7e0;
        color: #b06000;
        padding: 8px 16px;
        border-radius: 20px;
        font-weight: 600;
        font-size: 1rem;
        display: inline-block;
        margin-bottom: 12px;
    }
</style>
""", unsafe_allow_html=True)

# Sidebar: Environment & Backend Configuration
with st.sidebar:
    st.markdown("### 🔌 System Architecture")
    default_base = get_default_api_base()
    
    with st.expander("⚙️ Backend API Endpoint", expanded=False):
        api_input = st.text_input("FastAPI Base URL:", value=default_base, key="api_base_override")
        st.caption("Change this to your hosted Render URL (e.g. `https://your-service.onrender.com`)")

    API_BASE = st.session_state.get("api_base_override", default_base).rstrip("/")

    # Check backend health
    backend_online = False
    backend_info = {}
    try:
        h_resp = requests.get(f"{API_BASE}/api/health", timeout=3.0)
        if h_resp.status_code == 200:
            backend_online = True
            backend_info = h_resp.json()
    except Exception:
        backend_online = False

    if backend_online:
        st.success(f"🟢 **FastAPI Connected**\n`{API_BASE}`")
        st.caption(f"**Model:** `{backend_info.get('active_model', 'gemini-3.5-flash')}`")
    else:
        st.warning(f"🟡 **Direct Engine Mode**\nBackend unreachable at `{API_BASE}`. Using in-process rules engine.")
        if "onrender.com" in API_BASE:
            st.info("ℹ️ **Render Free Tier Cold-Start:** Render web services spin down after 15m. Please allow 30–50s for the first request to wake the server.")
    
    st.markdown("---")
    st.markdown("### 📚 Evaluation Scope")
    st.markdown("- **Project A:** Rupee-exact Indian Income Tax Engine (FY 2024-25 & FY 2025-26).")
    st.markdown("- **Project B:** NYC 311 Data Quality Firewall (Rules, Stats, & LLM review).")
    st.markdown("- **Core Principle:** LLMs for unstructured language; deterministic rules for exact arithmetic.")

calc = HandRulesCalculator()
dq_rules = RuleDetectors()

st.title("⚖️ Rules vs LLMs — Intelligent Advisor")
st.caption("Combining **Google Gemini** for messy natural-language parsing with **Deterministic Rules** for rupee-exact calculation.")

tabs = st.tabs([
    "💬 Plain-Language Tax Advisor",
    "🧮 Direct Tax Calculator",
    "🛡️ Data Quality Inspector (Project B)",
])

# -----------------------------------------------------------------------------
# TAB 1: PLAIN-LANGUAGE TAX ADVISOR
# -----------------------------------------------------------------------------
with tabs[0]:
    st.subheader("Salaried Individual Income Tax Engine")
    st.markdown("Describe your annual income, age, city, and investments in plain English, Hinglish, or Hindi.")

    col_ex1, col_ex2, col_ex3, col_ex4 = st.columns(4)
    with col_ex1:
        if st.button("💼 18L Salary + 1.5L PPF"):
            st.session_state["query_input"] = "I'm 32, earn 18 lakh a year, 1.5 lakh in PPF"
    with col_ex2:
        if st.button("🇮🇳 Hinglish + Rent + 80C"):
            st.session_state["query_input"] = "Meri annual salary 14 lakh hai, Mumbai me rehta hu, rent 30000 per month, 80C 1.5 lakh"
    with col_ex3:
        if st.button("🩺 Parents 80D + 9.5L"):
            st.session_state["query_input"] = "Age 45, salary 9.5 lakh, health insurance 25k for self and 50k for senior citizen parents"
    with col_ex4:
        if st.button("❓ Incomplete (Needs Age)"):
            st.session_state["query_input"] = "I earn 12 lakh a year"

    default_text = st.session_state.get("query_input", "I'm 32, earn 18 lakh a year, 1.5 lakh in PPF")
    user_query = st.text_area("Your Financial Profile:", value=default_text, height=90)

    col_opt1, col_opt2 = st.columns(2)
    with col_opt1:
        fy_choice = st.selectbox("Financial Year:", ["2024-25", "2025-26"], index=0,
                                 help="FY 2024-25 (AY 2025-26) or FY 2025-26 (Finance Act 2025)")
    with col_opt2:
        mode_choice = st.radio("Extractor Model:", ["llm", "regex"], index=0,
                               format_func=lambda x: "Google Gemini 3.5 Flash (Recommended)" if x == "llm" else "Regex Baseline (No LLM)",
                               horizontal=True)

    if st.button("Calculate My Tax", type="primary"):
        with st.spinner("Analyzing with Gemini & calculating tax to the rupee..."):
            t0 = time.perf_counter()
            res = None
            if backend_online:
                try:
                    payload = {"query": user_query, "mode": mode_choice, "fy": fy_choice}
                    resp = requests.post(f"{API_BASE}/api/tax/query", json=payload, timeout=45)
                    if resp.status_code == 200:
                        res = resp.json()
                    else:
                        st.error(f"Backend API error ({resp.status_code}): {resp.text}")
                except Exception as e:
                    st.warning(f"Backend call failed: {e}. Falling back to direct engine.")
            if res is None:
                try:
                    res = answer(user_query, mode=mode_choice, fy=fy_choice, calculator=calc)
                except Exception as exc:
                    err_str = str(exc)
                    st.session_state.pop("last_res", None)
                    if "GEMINI_API_KEY" in err_str:
                        st.error(
                            "🔑 **Google Gemini API Key is not set in Streamlit Cloud Secrets!**\n\n"
                            "Since the Render backend is offline/unreachable, this app is running in **Direct In-Process Engine Mode**.\n\n"
                            "### Quick Fix 1 (Add Key in 30 seconds):\n"
                            "1. Click **'Manage app'** at the bottom-right corner of this screen.\n"
                            "2. Click the three dots **⋮** ➔ **Settings** ➔ **Secrets**.\n"
                            "3. Paste your Gemini API key:\n"
                            "```toml\n"
                            'GEMINI_API_KEY = "your_actual_gemini_api_key_here"\n'
                            "```\n"
                            "4. Click **Save**.\n\n"
                            "---\n"
                            "⚡ **Quick Fix 2 (No Key Needed):**\n"
                            "Select **'Regex Baseline (No LLM)'** under **Extractor Model** above, then click **Calculate My Tax**! "
                            "It runs 100% locally with zero external APIs and tests the exact deterministic rules engine."
                        )
                    else:
                        st.error(f"⚠️ Calculation error: {err_str}")
                    res = None

            if res is not None:
                elapsed = time.perf_counter() - t0
                st.session_state["last_res"] = res
                st.session_state["last_latency"] = elapsed

    if "last_res" in st.session_state:
        res = st.session_state["last_res"]
        lat = st.session_state.get("last_latency", 0.0)

        if res.get("status") == "needs_clarification":
            st.warning("⚠️ **Clarification Needed**")
            st.markdown(f"**Question from Tax Engine:** {res['question']}")
            st.info("The engine refused to guess ambiguous or missing data. Please update your profile description above with the answer and re-calculate.")
        elif res.get("status") == "ok":
            rec = res["recommended"].upper()
            old_tax = res["old_regime"]["total_tax"]
            new_tax = res["new_regime"]["total_tax"]
            savings = abs(old_tax - new_tax)

            st.markdown(f"<div class='winner-badge'>🏆 Recommended: {rec} REGIME (Saves ₹{savings:,})</div>", unsafe_allow_html=True)
            st.caption(f"⚡ Processing latency: {lat:.2f}s | Routed via: {'FastAPI Backend' if backend_online else 'Direct Python Engine'}")

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Old Regime Tax", f"₹{old_tax:,}")
            m2.metric("New Regime Tax", f"₹{new_tax:,}")
            m3.metric("Selected Winner", f"{rec} Regime")
            m4.metric("Annual Tax Savings", f"₹{savings:,}", delta=f"₹{savings:,}")

            st.info(f"💡 **Explanation**: {res['explanation']}")

            with st.expander("🔍 Extracted Structured Data & Assumptions"):
                c_a, c_b = st.columns(2)
                with c_a:
                    st.write("**Extracted Taxpayer Profile:**")
                    st.json(res["input"])
                with c_b:
                    st.write("**Assumptions Made (defaulted to 0):**")
                    for a in res.get("assumptions", []):
                        st.markdown(f"- *{a}*")

            with st.expander("📜 Clause-by-Clause Statutory Audit Trace"):
                st.markdown("Every rupee accounted for and mapped to an official section clause:")
                trace_col1, trace_col2 = st.columns(2)
                with trace_col1:
                    st.write("### Old Regime Trace")
                    if "trace" in res and "old" in res["trace"]:
                        st.dataframe(pd.DataFrame(res["trace"]["old"]))
                with trace_col2:
                    st.write("### New Regime Trace")
                    if "trace" in res and "new" in res["trace"]:
                        st.dataframe(pd.DataFrame(res["trace"]["new"]))

# -----------------------------------------------------------------------------
# TAB 2: DIRECT TAX CALCULATOR (WHAT-IF ANALYSIS)
# -----------------------------------------------------------------------------
with tabs[1]:
    st.subheader("Direct Interactive Tax Calculator")
    st.caption("Instantaneous 0.1ms calculation using deterministic rules. Explore scenarios live.")

    col_d1, col_d2, col_d3 = st.columns(3)
    with col_d1:
        d_fy = st.selectbox("FY:", ["2024-25", "2025-26"], key="direct_fy")
        d_age = st.number_input("Age:", min_value=18, max_value=100, value=30, step=1)
        d_gross = st.number_input("Gross Annual Salary (₹):", min_value=0, value=1500000, step=50000)
        d_basic = st.number_input("Basic Salary + DA (₹):", min_value=0, value=600000, step=25000)

    with col_d2:
        d_hra_rec = st.number_input("HRA Received (₹):", min_value=0, value=250000, step=10000)
        d_rent = st.number_input("Annual Rent Paid (₹):", min_value=0, value=300000, step=10000)
        d_metro = st.checkbox("Living in Metro (Delhi, Mumbai, Kolkata, Chennai)?", value=True)
        d_80c = st.number_input("Section 80C (PPF, ELSS, EPF) (₹):", min_value=0, value=150000, step=10000)

    with col_d3:
        d_80ccd = st.number_input("NPS Additional 80CCD(1B) (₹):", min_value=0, value=50000, step=5000)
        d_80d_self = st.number_input("80D Health Premium (Self/Family) (₹):", min_value=0, value=25000, step=5000)
        d_80d_par = st.number_input("80D Health Premium (Parents) (₹):", min_value=0, value=35000, step=5000)
        d_par_sr = st.checkbox("Parents are Senior Citizens (60+)?", value=True)
        d_home_loan = st.number_input("Home Loan Interest (Self-occupied) (₹):", min_value=0, value=0, step=10000)

    inp_dict = {
        "fy": d_fy,
        "age": d_age,
        "gross_salary": d_gross,
        "basic_salary": d_basic,
        "hra_received": d_hra_rec,
        "rent_paid": d_rent,
        "metro_city": d_metro,
        "sec_80c": d_80c,
        "sec_80ccd_1b": d_80ccd,
        "sec_80d_self": d_80d_self,
        "sec_80d_parents": d_80d_par,
        "parents_senior": d_par_sr,
        "self_senior": d_age >= 60,
        "home_loan_interest": d_home_loan,
    }

    t_calc0 = time.perf_counter()
    d_res = None
    if backend_online:
        try:
            c_resp = requests.post(f"{API_BASE}/api/tax/calculate", json=inp_dict, timeout=5)
            if c_resp.status_code == 200:
                d_res = c_resp.json()
        except Exception:
            d_res = None
    
    if d_res is None:
        raw_res = calc.compute(TaxpayerInput(**inp_dict))
        d_res = {
            "recommended": raw_res.recommended,
            "explanation": raw_res.explanation,
            "savings": abs(raw_res.old.total_tax - raw_res.new.total_tax),
            "old_regime": {"total_tax": raw_res.old.total_tax, "trace": [t.model_dump() for t in raw_res.old.trace]},
            "new_regime": {"total_tax": raw_res.new.total_tax, "trace": [t.model_dump() for t in raw_res.new.trace]},
        }
    calc_ms = (time.perf_counter() - t_calc0) * 1000

    d_winner = d_res["recommended"].upper()
    d_sav = d_res["savings"]

    st.markdown("---")
    res_c1, res_c2, res_c3 = st.columns(3)
    res_c1.metric("Old Regime Tax", f"₹{d_res['old_regime']['total_tax']:,}")
    res_c2.metric("New Regime Tax", f"₹{d_res['new_regime']['total_tax']:,}")
    res_c3.metric(f"Winner: {d_winner} REGIME", f"Saves ₹{d_sav:,}")
    st.info(d_res["explanation"])
    st.caption(f"⚡ Calculation Latency: {calc_ms:.2f} ms")

# -----------------------------------------------------------------------------
# TAB 3: DATA QUALITY INSPECTOR (PROJECT B)
# -----------------------------------------------------------------------------
with tabs[2]:
    st.subheader("Data-Quality Guardrail Tester (Project B)")
    st.caption("Inspect raw free text for PII leaks / status contradictions, or run the complete 12-problem rules suite on a sample record.")

    dq_mode = st.radio("Inspection Mode:", ["Free-Text Inspector (PII & Status Contradiction)", "Full NYC 311 Record Inspector (12 Corruptions)"], horizontal=True)

    if dq_mode == "Free-Text Inspector (PII & Status Contradiction)":
        dq_col1, dq_col2 = st.columns([3, 1])
        with dq_col1:
            dq_text = st.text_area(
                "Resolution Description / Free Text:",
                value="The complaint is still in progress and pending inspection. Please call the officer at 212-555-0199 or email john.doe@nyc.gov.",
                height=100,
            )
        with dq_col2:
            dq_status = st.selectbox("Ticket Status:", ["Closed", "Open", "Pending", "Started"])

        if st.button("Run Text DQ Check", type="secondary"):
            alerts = []
            if backend_online:
                try:
                    resp = requests.post(f"{API_BASE}/api/dq/check_text", json={"resolution_description": dq_text, "status": dq_status}, timeout=5)
                    if resp.status_code == 200:
                        alerts = [(a["type"], a["reason"], "error" if a["type"] == "status_contradiction" else "warning") for a in resp.json().get("alerts", [])]
                except Exception:
                    alerts = []
            if not alerts and not backend_online:
                df_sample = pd.DataFrame([{
                    "unique_key": "sample_101",
                    "status": dq_status,
                    "resolution_description": dq_text,
                    "descriptor": "",
                    "complaint_type": "",
                }])
                for a in dq_rules._k(df_sample):
                    alerts.append(("status_contradiction", a.reason, "error"))
                for a in dq_rules._l(df_sample):
                    alerts.append(("pii_leak", a.reason, "warning"))

            if not alerts:
                st.success("✅ Clean Record! No PII leaks or status contradictions detected.")
            else:
                for typ, reason, severity in alerts:
                    if severity == "error":
                        st.error(f"🚨 **{typ.upper()}**: {reason}")
                    else:
                        st.warning(f"⚠️ **{typ.upper()}**: {reason}")

    else:
        st.markdown("#### Test a Complete NYC 311 Record Against All Rule Detectors")
        st.caption("Checks: schema, types, date format, lat/lon swapped, duplicates, closed < created, ZIP vs borough, PII.")
        
        c_r1, c_r2 = st.columns(2)
        with c_r1:
            rec_unique_key = st.text_input("unique_key:", value="56414137")
            rec_agency = st.text_input("agency:", value="NYPD")
            rec_complaint = st.text_input("complaint_type:", value="Noise - Residential")
            rec_descriptor = st.text_input("descriptor:", value="Loud Music/Party")
            rec_status = st.selectbox("status:", ["Closed", "Open", "Pending", "Started"], key="rec_status")
        with c_r2:
            rec_created = st.text_input("created_date:", value="2023-01-05T14:30:00.000")
            rec_closed = st.text_input("closed_date:", value="2023-01-05T12:00:00.000", help="Notice closed earlier than created!")
            rec_zip = st.text_input("incident_zip:", value="10001")
            rec_borough = st.text_input("borough:", value="MANHATTAN")
            rec_lat = st.number_input("latitude:", value=-73.99, help="Notice: longitude in latitude field!")
            rec_lon = st.number_input("longitude:", value=40.75)
            rec_res_desc = st.text_input("resolution_description:", value="Case was closed. Officer contact 212-555-9876.")

        if st.button("Inspect Complete Record Against All Rules"):
            rec_dict = {
                "unique_key": rec_unique_key,
                "agency": rec_agency,
                "complaint_type": rec_complaint,
                "descriptor": rec_descriptor,
                "status": rec_status,
                "created_date": rec_created,
                "closed_date": rec_closed,
                "incident_zip": rec_zip,
                "borough": rec_borough,
                "latitude": rec_lat,
                "longitude": rec_lon,
                "resolution_description": rec_res_desc,
            }
            rec_alerts = []
            if backend_online:
                try:
                    resp = requests.post(f"{API_BASE}/api/dq/inspect_record", json={"record": rec_dict}, timeout=5)
                    if resp.status_code == 200:
                        rec_alerts = resp.json().get("alerts", [])
                except Exception:
                    rec_alerts = []
            if not rec_alerts and not backend_online:
                df_rec = pd.DataFrame([rec_dict])
                for a in dq_rules.detect(df_rec):
                    rec_alerts.append({
                        "problem": a.problem_key,
                        "reason": a.reason,
                        "column": a.column,
                        "observed": a.observed,
                        "expected": a.expected,
                    })
            
            if not rec_alerts:
                st.success("✅ Record passed all declarative rule checks!")
            else:
                st.warning(f"Found {len(rec_alerts)} violations:")
                st.dataframe(pd.DataFrame(rec_alerts))
