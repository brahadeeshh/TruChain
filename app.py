import hashlib
import json
import time
from datetime import datetime, timezone

import pandas as pd
import requests
import streamlit as st

# --------------------------------------------------
# TRUCHAIN CONFIGURATION & PAGE SETUP
# --------------------------------------------------

st.set_page_config(
    page_title="TruChain | Financial Claim Verification & Audit",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

CATEGORIES = {
    "Monthly Income": {
        "slug": "monthly_income",
        "icon": "💼",
        "tag": "Payroll & Salary",
        "description": "Verify salary, employment income, and recurring payroll against trusted corporate records.",
        "default_ref": "PAYROLL-TEST-101",
        "default_amount": 30000.0,
        "fields": [
            ("Monthly salary", "number", 30000.0),
            ("Other monthly income", "number", 0.0),
            ("Employment type", "select", ["Salaried", "Self-employed", "Freelancer", "Other"]),
            ("Employer or income source", "text", "Acme Corp Ltd"),
        ],
    },
    "Bank Balance": {
        "slug": "bank_balance",
        "icon": "🏦",
        "tag": "Banking & Liquidity",
        "description": "Verify declared bank account balance against authenticated banking provider records.",
        "default_ref": "BANK-REF-201",
        "default_amount": 150000.0,
        "fields": [
            ("Declared account balance", "number", 150000.0),
            ("Account type", "select", ["Savings", "Current", "Fixed deposit", "Other"]),
            ("Bank name", "text", "State Bank of India"),
            ("Statement date", "date", None),
        ],
    },
    "Monthly Expenses": {
        "slug": "monthly_expenses",
        "icon": "📉",
        "tag": "Cash Outflow",
        "description": "Reconcile rent, utility bills, household expenditures, and recurring liabilities.",
        "default_ref": "EXPENSE-REF-301",
        "default_amount": 18000.0,
        "fields": [
            ("Rent or housing expenses", "number", 12000.0),
            ("Utilities and bills", "number", 6000.0),
            ("Food and household expenses", "number", 0.0),
            ("Other monthly expenses", "number", 0.0),
        ],
    },
    "Loans & Liabilities": {
        "slug": "loans_liabilities",
        "icon": "📜",
        "tag": "Debt Obligations",
        "description": "Verify declared outstanding debt, EMIs, lender contracts, and declared credit liabilities.",
        "default_ref": "LOAN-REF-401",
        "default_amount": 500000.0,
        "fields": [
            ("Outstanding loan amount", "number", 500000.0),
            ("Monthly EMI", "number", 15000.0),
            ("Loan type", "select", ["Education", "Home", "Personal", "Vehicle", "Business", "Other"]),
            ("Lender name", "text", "HDFC Bank Ltd"),
        ],
    },
    "Tax & Financial Documents": {
        "slug": "tax_financial_documents",
        "icon": "📑",
        "tag": "Tax & Filings",
        "description": "Submit tax returns, verified payslips, or official revenue authority assessments.",
        "default_ref": "TAX-REF-501",
        "default_amount": 450000.0,
        "fields": [
            ("Declared annual gross income", "number", 450000.0),
            ("Document type", "select", ["Income tax return", "Payslip", "Invoice", "Bank statement", "Other"]),
            ("Financial year", "text", "2025-2026"),
            ("Issuing organization", "text", "Income Tax Department"),
        ],
    },
    "General Financial Claim": {
        "slug": "general_financial_claim",
        "icon": "🛡️",
        "tag": "Grants & Subsidies",
        "description": "Submit general financial claims, reimbursement grants, or educational scholarships for audit.",
        "default_ref": "CLAIM-REF-601",
        "default_amount": 25000.0,
        "fields": [
            ("Claim type", "select", ["Scholarship", "Reimbursement", "Insurance", "Business claim", "Other"]),
            ("Claimed amount", "number", 25000.0),
            ("Claim reference", "text", "SCHOLAR-2026"),
            ("Claim description", "text", "Tuition reimbursement"),
        ],
    },
}

# --------------------------------------------------
# NAVIGATION CALLBACK HANDLERS
# --------------------------------------------------

def navigate_to(page_name, category_name=None):
    """Callback to switch navigation safely."""
    st.session_state["main_navigation"] = page_name
    if category_name:
        st.session_state["selected_category"] = category_name


def apply_preset(user_id, category, amount, reference_id):
    """Callback to fill demo presets safely."""
    st.session_state["form_user_id"] = user_id
    st.session_state["verification_category"] = category
    st.session_state["selected_category"] = category
    st.session_state["form_claimed_amount"] = float(amount)
    st.session_state["form_reference_id"] = reference_id


# --------------------------------------------------
# HIGH-END DESIGN SYSTEM & CUSTOM CSS
# --------------------------------------------------

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&display=swap');

    :root {
        --bg-main: #070b14;
        --bg-card: rgba(15, 23, 42, 0.75);
        --border-glass: rgba(255, 255, 255, 0.08);
        --accent-emerald: #10b981;
        --accent-amber: #f59e0b;
        --accent-blue: #3b82f6;
        --accent-cyan: #06b6d4;
        --accent-purple: #8b5cf6;
        --text-primary: #f8fafc;
        --text-muted: #94a3b8;
    }

    /* Overall App Background & Typography */
    .stApp {
        background-color: var(--bg-main);
        background-image: 
            radial-gradient(circle at 10% 15%, rgba(59, 130, 246, 0.08) 0%, transparent 40%),
            radial-gradient(circle at 90% 25%, rgba(16, 185, 129, 0.06) 0%, transparent 40%),
            radial-gradient(circle at 50% 80%, rgba(139, 92, 246, 0.05) 0%, transparent 50%);
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
        color: var(--text-primary);
    }

    /* Streamlit Main Container Spacing */
    .block-container {
        padding-top: 1.5rem !important;
        padding-bottom: 3rem !important;
        max-width: 1400px;
    }

    /* Sidebar Overhaul */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0b1120 0%, #080d19 100%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.07) !important;
        box-shadow: 4px 0 24px rgba(0, 0, 0, 0.4);
    }

    [data-testid="stSidebar"] hr {
        border-color: rgba(255, 255, 255, 0.08);
        margin: 1.2rem 0;
    }

    /* Sidebar Radio Navigation */
    [data-testid="stSidebar"] [data-testid="stRadio"] > div {
        gap: 6px;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label {
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        padding: 10px 14px;
        transition: all 0.2s ease-in-out;
        cursor: pointer;
        display: flex;
        align-items: center;
        color: #cbd5e1;
    }

    [data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
        background: rgba(30, 41, 59, 0.8);
        border-color: rgba(59, 130, 246, 0.4);
        color: #ffffff;
        transform: translateX(3px);
    }

    /* Top Brand Hero Banner */
    .hero-container {
        position: relative;
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.85) 0%, rgba(30, 41, 59, 0.6) 100%);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 20px;
        padding: 24px 30px;
        margin-bottom: 24px;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.35);
        overflow: hidden;
    }

    .hero-container::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #10b981 0%, #3b82f6 50%, #8b5cf6 100%);
    }

    .hero-title-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 12px;
    }

    .hero-title {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        background: linear-gradient(135deg, #ffffff 40%, #94a3b8 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
    }

    .hero-tag {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.78rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        padding: 5px 12px;
        border-radius: 9999px;
        background: rgba(16, 185, 129, 0.12);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }

    .hero-desc {
        color: #94a3b8;
        font-size: 0.98rem;
        margin-top: 8px;
        margin-bottom: 12px;
        max-width: 900px;
        line-height: 1.5;
    }

    .hero-pills {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 14px;
    }

    .hero-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 4px 12px;
        border-radius: 8px;
        font-size: 0.8rem;
        font-weight: 600;
        background: rgba(15, 23, 42, 0.6);
        border: 1px solid rgba(255, 255, 255, 0.08);
        color: #cbd5e1;
    }

    /* KPI Stat Cards */
    .stat-card {
        background: rgba(15, 23, 42, 0.65);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px 18px;
        text-align: left;
        backdrop-filter: blur(12px);
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        height: 100%;
    }

    .stat-card:hover {
        transform: translateY(-4px);
        border-color: rgba(255, 255, 255, 0.18);
        box-shadow: 0 12px 28px rgba(0, 0, 0, 0.45);
    }

    .stat-card-top {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
    }

    .stat-icon {
        width: 36px;
        height: 36px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
    }

    .stat-val {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        line-height: 1;
        margin-bottom: 4px;
        font-family: 'JetBrains Mono', monospace;
    }

    .stat-label {
        font-size: 0.82rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #64748b;
    }

    .stat-sub {
        font-size: 0.78rem;
        color: #94a3b8;
        margin-top: 6px;
    }

    /* Verification Status Banners */
    .status-banner {
        border-radius: 16px;
        padding: 20px 24px;
        margin-bottom: 20px;
        display: flex;
        align-items: flex-start;
        gap: 18px;
        position: relative;
        backdrop-filter: blur(16px);
        box-shadow: 0 10px 28px rgba(0, 0, 0, 0.35);
    }

    .status-banner-verified {
        background: linear-gradient(135deg, rgba(6, 78, 59, 0.45) 0%, rgba(15, 23, 42, 0.85) 100%);
        border: 1px solid rgba(16, 185, 129, 0.4);
        box-shadow: 0 0 30px rgba(16, 185, 129, 0.15);
    }

    .status-banner-mismatch {
        background: linear-gradient(135deg, rgba(120, 53, 15, 0.45) 0%, rgba(15, 23, 42, 0.85) 100%);
        border: 1px solid rgba(245, 158, 11, 0.4);
        box-shadow: 0 0 30px rgba(245, 158, 11, 0.15);
    }

    .status-banner-unverified {
        background: linear-gradient(135deg, rgba(51, 65, 85, 0.45) 0%, rgba(15, 23, 42, 0.85) 100%);
        border: 1px solid rgba(148, 163, 184, 0.3);
        box-shadow: 0 0 30px rgba(148, 163, 184, 0.1);
    }

    .status-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 6px 16px;
        border-radius: 9999px;
        font-size: 0.95rem;
        font-weight: 800;
        letter-spacing: 0.05em;
        text-transform: uppercase;
    }

    .status-pill-verified {
        background: #064e3b;
        color: #34d399;
        border: 1px solid #10b981;
    }

    .status-pill-mismatch {
        background: #78350f;
        color: #fde68a;
        border: 1px solid #f59e0b;
    }

    .status-pill-unverified {
        background: #1e293b;
        color: #cbd5e1;
        border: 1px solid #475569;
    }

    /* Web3 Blockchain Certificate Card */
    .web3-cert-card {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.9) 0%, rgba(10, 16, 30, 0.95) 100%);
        border: 1px solid rgba(59, 130, 246, 0.3);
        border-radius: 18px;
        padding: 24px;
        margin-top: 18px;
        position: relative;
        backdrop-filter: blur(16px);
        box-shadow: 0 12px 32px rgba(0, 0, 0, 0.4), 0 0 25px rgba(59, 130, 246, 0.12);
    }

    .web3-cert-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 24px;
        right: 24px;
        height: 2px;
        background: linear-gradient(90deg, #3b82f6 0%, #06b6d4 50%, #10b981 100%);
    }

    .hash-chip {
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.85rem;
        background: rgba(10, 15, 26, 0.8);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 8px;
        padding: 8px 12px;
        color: #38bdf8;
        word-break: break-all;
    }

    /* Category Cards in Dashboard */
    .cat-card {
        background: rgba(15, 23, 42, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 16px;
        padding: 20px;
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }

    .cat-card:hover {
        border-color: rgba(59, 130, 246, 0.4);
        transform: translateY(-3px);
        box-shadow: 0 10px 25px rgba(0, 0, 0, 0.3);
    }

    .cat-tag {
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        padding: 3px 8px;
        border-radius: 6px;
        background: rgba(59, 130, 246, 0.15);
        color: #60a5fa;
        border: 1px solid rgba(59, 130, 246, 0.3);
        display: inline-block;
        margin-bottom: 8px;
    }

    /* Streamlit Global Widget Polish */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.25s ease !important;
        padding: 0.5rem 1rem !important;
    }

    .stButton > button:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 6px 18px rgba(0, 0, 0, 0.3) !important;
    }

    /* Primary Submit Button Glow */
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #2563eb 0%, #1d4ed8 100%) !important;
        border: 1px solid #3b82f6 !important;
        box-shadow: 0 4px 16px rgba(37, 99, 235, 0.4) !important;
        color: #ffffff !important;
    }

    .stButton > button[kind="primary"]:hover {
        background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%) !important;
        box-shadow: 0 6px 24px rgba(37, 99, 235, 0.6) !important;
    }

    /* Container Borders */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(255, 255, 255, 0.08) !important;
        background: rgba(15, 23, 42, 0.45) !important;
        border-radius: 14px !important;
    }

    /* Input styling */
    div[data-baseweb="input"] {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
    }

    div[data-baseweb="input"]:focus-within {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.25) !important;
    }

    div[data-baseweb="select"] {
        background-color: rgba(15, 23, 42, 0.6) !important;
        border-color: rgba(255, 255, 255, 0.12) !important;
        border-radius: 10px !important;
    }

    /* Pulse beacon */
    .pulse-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px currentColor;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# SIDEBAR NAVIGATION & TELEMETRY
# --------------------------------------------------

with st.sidebar:
    st.markdown(
        """
        <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 8px; padding-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.08);">
            <div style="width: 40px; height: 40px; border-radius: 10px; background: linear-gradient(135deg, #10b981, #3b82f6); display: flex; align-items: center; justify-content: center; font-size: 1.3rem; box-shadow: 0 4px 12px rgba(16, 185, 129, 0.3);">
                ⚡
            </div>
            <div>
                <div style="font-size: 1.25rem; font-weight: 800; color: #ffffff; letter-spacing: -0.02em;">TruChain</div>
                <div style="font-size: 0.72rem; font-weight: 600; color: #94a3b8; text-transform: uppercase; letter-spacing: 0.06em;">Cryptographic Audit Hub</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    nav_options = ["Dashboard", "Verify Finances", "Audit History", "About TruChain"]
    if "main_navigation" not in st.session_state:
        st.session_state["main_navigation"] = "Dashboard"

    page = st.radio(
        "Navigation",
        nav_options,
        key="main_navigation",
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown(
        """
        <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em; color: #64748b; margin-bottom: 10px;">
            📡 System Telemetry
        </div>
        """,
        unsafe_allow_html=True,
    )

    backend_url = st.text_input(
        "FastAPI Base URL",
        value="http://127.0.0.1:8000",
        help="FastAPI backend host URL.",
    ).strip().rstrip("/")

    endpoint = st.text_input(
        "Verification Endpoint",
        value="/verify-finances",
        help="POST endpoint for financial claim verification.",
    ).strip()

    if endpoint and not endpoint.startswith("/"):
        endpoint = "/" + endpoint

    # Backend Connection Ping
    backend_online = False
    ping_ms = 0
    try:
        t0 = time.time()
        health_check = requests.get(f"{backend_url}/health", timeout=1.5)
        ping_ms = int((time.time() - t0) * 1000)
        if health_check.ok:
            backend_online = True
    except Exception:
        backend_online = False

    if backend_online:
        st.markdown(
            f"""
            <div style="background: rgba(16, 185, 129, 0.1); border: 1px solid rgba(16, 185, 129, 0.3); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px; display: flex; align-items: center; justify-content: space-between;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="pulse-dot" style="background-color: #10b981; color: #10b981;"></span>
                    <span style="font-size: 0.85rem; font-weight: 700; color: #34d399;">FastAPI Connected</span>
                </div>
                <span style="font-size: 0.75rem; color: #94a3b8; font-family: 'JetBrains Mono', monospace;">{ping_ms}ms</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style="background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); border-radius: 10px; padding: 10px 12px; margin-bottom: 10px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="pulse-dot" style="background-color: #ef4444; color: #ef4444;"></span>
                    <span style="font-size: 0.85rem; font-weight: 700; color: #f87171;">FastAPI Offline (Port 8000)</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Hardhat & Smart Contract Details Card
    st.markdown(
        """
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 12px; margin-top: 10px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                <span style="font-size: 0.75rem; font-weight: 700; color: #94a3b8; text-transform: uppercase;">Hardhat Node</span>
                <span style="font-size: 0.72rem; color: #38bdf8; font-family: 'JetBrains Mono', monospace;">:8545</span>
            </div>
            <div style="font-size: 0.78rem; color: #cbd5e1; margin-bottom: 10px;">
                ⛓️ Local EVM JSON-RPC
            </div>
            <div style="border-top: 1px solid rgba(255, 255, 255, 0.06); padding-top: 8px;">
                <div style="font-size: 0.72rem; font-weight: 700; color: #94a3b8; text-transform: uppercase; margin-bottom: 4px;">Contract Address</div>
                <div style="font-size: 0.72rem; font-family: 'JetBrains Mono', monospace; color: #a78bfa; word-break: break-all; background: rgba(0,0,0,0.3); padding: 4px 6px; border-radius: 6px;">
                    0x5FbDB2315678afecb367f032d93F642f64180aa3
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="margin-top: 18px; padding: 12px; background: rgba(59, 130, 246, 0.08); border: 1px solid rgba(59, 130, 246, 0.2); border-radius: 12px;">
            <div style="font-size: 0.78rem; font-weight: 700; color: #60a5fa; margin-bottom: 4px;">🔒 Zero-PII Guarantee</div>
            <div style="font-size: 0.73rem; color: #94a3b8; line-height: 1.4;">
                No names or raw financial figures touch the blockchain. Only cryptographic Keccak-256 commitments are recorded.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

# --------------------------------------------------
# TOP BRAND HERO BANNER
# --------------------------------------------------

st.markdown(
    """
    <div class="hero-container">
        <div class="hero-title-row">
            <div>
                <h1 class="hero-title">⚡ TruChain — Financial Claim Verification & Audit</h1>
                <p class="hero-desc">
                    Enterprise financial verification and cryptographic audit engine powered by salted Keccak-256 commitments and Ethereum smart contracts.
                </p>
            </div>
            <div>
                <span class="hero-tag">
                    <span class="pulse-dot" style="background-color: #10b981; color: #10b981;"></span>
                    Zero-PII On-Chain Audit
                </span>
            </div>
        </div>
        <div class="hero-pills">
            <span class="hero-pill">🛡️ Authoritative Source Matching</span>
            <span class="hero-pill">⛓️ Hardhat Local EVM</span>
            <span class="hero-pill">🔐 Salted Keccak-256 Hashes</span>
            <span class="hero-pill">📜 Smart Contract Tamper-Evidence</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# --------------------------------------------------
# HELPER RENDERING FUNCTIONS
# --------------------------------------------------

def render_verification_banner(status):
    """Render distinctive high-tech badge and description based on verification status."""
    if status == "VERIFIED":
        st.markdown(
            """
            <div class="status-banner status-banner-verified">
                <div style="font-size: 2.2rem; line-height: 1;">✅</div>
                <div>
                    <span class="status-pill status-pill-verified">VERIFIED — MATCH CONFIRMED</span>
                    <p style="margin-top: 8px; margin-bottom: 0; color: #d1fae5; font-size: 0.95rem; line-height: 1.5;">
                        <strong>Exact Match Reconciled:</strong> The submitted financial information strictly reconciles against the trusted authoritative reference source.
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif status == "MISMATCH":
        st.markdown(
            """
            <div class="status-banner status-banner-mismatch">
                <div style="font-size: 2.2rem; line-height: 1;">⚠️</div>
                <div>
                    <span class="status-pill status-pill-mismatch">MISMATCH — VARIANCE DETECTED</span>
                    <p style="margin-top: 8px; margin-bottom: 0; color: #fef3c7; font-size: 0.95rem; line-height: 1.5;">
                        <strong>Audit Review Flag:</strong> Submitted claim amount differs from the authoritative record.
                        <br><span style="color: #fcd34d; font-size: 0.85rem;"><em>Note: A mismatch is a signal for human investigation, not automatic proof of fraudulent activity.</em></span>
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="status-banner status-banner-unverified">
                <div style="font-size: 2.2rem; line-height: 1;">❓</div>
                <div>
                    <span class="status-pill status-pill-unverified">UNVERIFIED — NO REFERENCE MATCH</span>
                    <p style="margin-top: 8px; margin-bottom: 0; color: #cbd5e1; font-size: 0.95rem; line-height: 1.5;">
                        <strong>Unresolved Reference:</strong> The submitted claim could not be matched against existing reference records. Manual review or updated identifier is required.
                    </p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def show_backend_response(data):
    """Render full structured verification result and blockchain audit proof."""
    if not isinstance(data, dict):
        st.json(data)
        return

    status = str(
        data.get("status")
        or data.get("verification_status")
        or data.get("result")
        or "PENDING"
    ).upper()

    render_verification_banner(status)

    # Reconciliation Matrix Grid
    claimed_amt = data.get("claimed_amount")
    verified_amt = data.get("verified_amount")
    ref_source = data.get("reference_source") or "Synthetic Test Record"
    diff = None
    if claimed_amt is not None and verified_amt is not None:
        diff = claimed_amt - verified_amt

    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.markdown(
            f"""
            <div class="stat-card" style="border-left: 3px solid #3b82f6;">
                <div class="stat-card-top">
                    <span class="stat-label">Claimed Amount</span>
                    <span style="font-size: 1.2rem;">📝</span>
                </div>
                <div class="stat-val" style="color: #ffffff;">
                    {"₹{:,.2f}".format(claimed_amt) if claimed_amt is not None else "N/A"}
                </div>
                <div class="stat-sub">Declared in submitted application</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_b:
        verified_str = "₹{:,.2f}".format(verified_amt) if verified_amt is not None else "No Reference Match"
        st.markdown(
            f"""
            <div class="stat-card" style="border-left: 3px solid #10b981;">
                <div class="stat-card-top">
                    <span class="stat-label">Authoritative Source</span>
                    <span style="font-size: 1.2rem;">🏛️</span>
                </div>
                <div class="stat-val" style="color: #34d399; font-size: 1.8rem;">
                    {verified_str}
                </div>
                <div class="stat-sub">Source: {ref_source}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_c:
        if diff is not None:
            if abs(diff) < 0.01:
                diff_display = "₹0.00 (Exact Match)"
                diff_color = "#34d399"
                diff_icon = "🎯"
            elif diff > 0:
                diff_display = f"+₹{diff:,.2f} (Over-declared)"
                diff_color = "#f59e0b"
                diff_icon = "📈"
            else:
                diff_display = f"-₹{abs(diff):,.2f} (Under-declared)"
                diff_color = "#f59e0b"
                diff_icon = "📉"
        else:
            diff_display = "N/A"
            diff_color = "#94a3b8"
            diff_icon = "ℹ️"

        st.markdown(
            f"""
            <div class="stat-card" style="border-left: 3px solid {diff_color};">
                <div class="stat-card-top">
                    <span class="stat-label">Variance / Delta</span>
                    <span style="font-size: 1.2rem;">{diff_icon}</span>
                </div>
                <div class="stat-val" style="color: {diff_color}; font-size: 1.8rem;">
                    {diff_display}
                </div>
                <div class="stat-sub">Calculated audit variance</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    explanation = data.get("explanation")
    if explanation:
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.5); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px; margin: 16px 0; color: #cbd5e1; font-size: 0.95rem;">
                <strong style="color: #60a5fa;">📋 Reconciliation Findings:</strong> {explanation}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Blockchain Audit Section
    blockchain_info = data.get("blockchain") or data
    blockchain_status = str(blockchain_info.get("blockchain_status", "PENDING")).upper()
    tx_hash = blockchain_info.get("transaction_hash") or data.get("transaction_hash")
    commitment_hash = blockchain_info.get("commitment_hash") or data.get("commitment_hash")
    claim_id_hash = blockchain_info.get("claim_id_hash") or data.get("claim_id_hash")
    claim_id = data.get("claim_id")

    st.markdown(
        """
        <div style="margin-top: 24px; margin-bottom: 8px; display: flex; align-items: center; justify-content: space-between;">
            <h3 style="margin: 0; font-size: 1.25rem; font-weight: 700; color: #f8fafc;">
                ⛓️ Cryptographic Audit Certificate (Local Hardhat EVM)
            </h3>
            <span style="font-size: 0.75rem; font-family: 'JetBrains Mono', monospace; color: #38bdf8; background: rgba(56, 189, 248, 0.1); border: 1px solid rgba(56, 189, 248, 0.3); padding: 3px 10px; border-radius: 6px;">
                CONTRACT: TruChainAudit.sol
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if blockchain_status == "RECORDED" and tx_hash:
        st.markdown(
            f"""
            <div class="web3-cert-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; flex-wrap: wrap; gap: 8px;">
                    <div>
                        <span style="font-size: 1.15rem; font-weight: 700; color: #ffffff;">Tamper-Evident On-Chain Seal</span>
                        <div style="font-size: 0.8rem; color: #94a3b8; margin-top: 2px;">
                            This verification result is immutably anchored into the Ethereum virtual machine.
                        </div>
                    </div>
                    <span style="background: rgba(16, 185, 129, 0.15); color: #34d399; font-size: 0.8rem; font-weight: 700; padding: 4px 12px; border-radius: 9999px; border: 1px solid rgba(16, 185, 129, 0.4); text-transform: uppercase;">
                        STATUS: RECORDED ON-CHAIN
                    </span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        col_tx1, col_tx2 = st.columns([1, 1])

        with col_tx1:
            st.markdown(
                """
                <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-top: 8px; margin-bottom: 4px;">
                    🔗 Blockchain Transaction Hash
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.code(str(tx_hash), language="text")

        with col_tx2:
            st.markdown(
                """
                <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-top: 8px; margin-bottom: 4px;">
                    🔐 Salted Keccak-256 Commitment Hash
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.code(str(commitment_hash) if commitment_hash else "N/A", language="text")

        col_sub1, col_sub2 = st.columns([1, 1])
        with col_sub1:
            st.markdown(
                """
                <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px;">
                    🏷️ Claim ID Hash (bytes32)
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.code(str(claim_id_hash) if claim_id_hash else "N/A", language="text")

        with col_sub2:
            if claim_id:
                st.markdown(
                    f"""
                    <div style="font-size: 0.8rem; font-weight: 700; text-transform: uppercase; color: #94a3b8; margin-bottom: 4px;">
                        🗃️ Database Anchor
                    </div>
                    <div style="padding: 10px 14px; background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 8px; color: #cbd5e1; font-family: 'JetBrains Mono', monospace; font-size: 0.9rem;">
                        Claim Record ID: <strong>#{claim_id}</strong>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        if claim_id:
            # On-chain tamper-evidence verification button
            if st.button("🔍 Verify Tamper-Evidence Directly On-Chain", key=f"onchain_btn_{claim_id}", use_container_width=True):
                with st.spinner("Invoking smart contract method TruChainAudit.getAudit()..."):
                    try:
                        onchain_res = requests.get(f"{backend_url}/verify-onchain/{claim_id}", timeout=6)
                        if onchain_res.ok:
                            onchain_json = onchain_res.json()
                            if onchain_json.get("onchain_verified"):
                                st.markdown(
                                    f"""
                                    <div style="background: rgba(16, 185, 129, 0.15); border: 1px solid #10b981; border-radius: 12px; padding: 16px; margin-top: 14px;">
                                        <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 6px;">
                                            <span style="font-size: 1.5rem;">🛡️</span>
                                            <span style="font-size: 1.05rem; font-weight: 700; color: #34d399;">Smart Contract Cryptographic Seal Confirmed!</span>
                                        </div>
                                        <div style="color: #d1fae5; font-size: 0.9rem;">
                                            The commitment hash retrieved directly from the Hardhat EVM smart contract exactly matches this claim's cryptographic fingerprint. The record has never been tampered with.
                                        </div>
                                        <div style="margin-top: 10px; font-family: 'JetBrains Mono', monospace; font-size: 0.8rem; color: #6ee7b7; word-break: break-all;">
                                            On-Chain Hash: {onchain_json.get('onchain_commitment_hash')}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                st.error("❌ On-chain verification mismatch! Hashes do not match.")
                        else:
                            st.error(f"Failed to query smart contract: {onchain_res.text}")
                    except Exception as e:
                        st.error(f"Error querying on-chain audit: {e}")
    else:
        st.warning(f"Blockchain Status: {blockchain_status}. Message: {blockchain_info.get('message', 'Awaiting commit.')}")

    with st.expander("🔍 View Raw JSON Audit Payload"):
        st.json(data)


def send_verification(payload):
    """Submit the verification to FastAPI backend and display results."""
    url = backend_url + endpoint

    try:
        with st.spinner("Transmitting claim to FastAPI & anchoring cryptographic audit on local Hardhat blockchain..."):
            response = requests.post(url, json=payload, timeout=30)

        if not response.ok:
            st.error(f"Backend returned HTTP {response.status_code}.")
            try:
                st.json(response.json())
            except ValueError:
                st.code(response.text[:3000])
            return

        try:
            data = response.json()
        except ValueError:
            st.error("Backend responded, but did not return valid JSON.")
            st.code(response.text[:3000])
            return

        st.session_state["last_verification"] = data
        st.session_state["last_verification_category"] = payload.get("category", "General")
        show_backend_response(data)

    except requests.exceptions.ConnectionError:
        st.error("Could not connect to FastAPI. Ensure FastAPI is running on port 8000.")
    except requests.exceptions.Timeout:
        st.error("Backend request timed out. Check the API and Hardhat node.")
    except requests.exceptions.RequestException as exc:
        st.error(f"Request failed: {exc}")


# --------------------------------------------------
# PAGE 1: DASHBOARD
# --------------------------------------------------

if page == "Dashboard":
    # Fetch live stats from FastAPI
    total_claims = 0
    verified_cnt = 0
    mismatch_cnt = 0
    unverified_cnt = 0
    blockchain_cnt = 0

    try:
        stats_resp = requests.get(f"{backend_url}/stats", timeout=2)
        if stats_resp.ok:
            sdata = stats_resp.json()
            total_claims = sdata.get("total_claims", 0)
            verified_cnt = sdata.get("verified", 0)
            mismatch_cnt = sdata.get("mismatch", 0)
            unverified_cnt = sdata.get("unverified", 0)
            blockchain_cnt = sdata.get("blockchain_recorded", 0)
    except Exception:
        pass

    # 5 High-Tech KPI Metric Cards
    m1, m2, m3, m4, m5 = st.columns(5)

    with m1:
        st.markdown(
            f"""
            <div class="stat-card" style="border-top: 3px solid #3b82f6;">
                <div class="stat-card-top">
                    <span class="stat-label">Total Claims</span>
                    <span style="font-size: 1.3rem;">📊</span>
                </div>
                <div class="stat-val" style="color: #ffffff;">{total_claims}</div>
                <div class="stat-sub">Submitted to date</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m2:
        st.markdown(
            f"""
            <div class="stat-card" style="border-top: 3px solid #10b981;">
                <div class="stat-card-top">
                    <span class="stat-label">Verified</span>
                    <span style="font-size: 1.3rem;">✅</span>
                </div>
                <div class="stat-val" style="color: #34d399;">{verified_cnt}</div>
                <div class="stat-sub">Reconciled matches</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m3:
        st.markdown(
            f"""
            <div class="stat-card" style="border-top: 3px solid #f59e0b;">
                <div class="stat-card-top">
                    <span class="stat-label">Mismatches</span>
                    <span style="font-size: 1.3rem;">⚠️</span>
                </div>
                <div class="stat-val" style="color: #fbbf24;">{mismatch_cnt}</div>
                <div class="stat-sub">Audit review signals</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m4:
        st.markdown(
            f"""
            <div class="stat-card" style="border-top: 3px solid #64748b;">
                <div class="stat-card-top">
                    <span class="stat-label">Unverified</span>
                    <span style="font-size: 1.3rem;">❓</span>
                </div>
                <div class="stat-val" style="color: #94a3b8;">{unverified_cnt}</div>
                <div class="stat-sub">Unmatched references</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with m5:
        st.markdown(
            f"""
            <div class="stat-card" style="border-top: 3px solid #8b5cf6;">
                <div class="stat-card-top">
                    <span class="stat-label">On-Chain Audits</span>
                    <span style="font-size: 1.3rem;">⛓️</span>
                </div>
                <div class="stat-val" style="color: #a78bfa;">{blockchain_cnt}</div>
                <div class="stat-sub">Tamper-evident logs</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # Verification Lifecycle Architecture Cards
    st.markdown(
        """
        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 14px; display: flex; align-items: center; gap: 8px;">
            <span>🔄 Verification & Audit Protocol</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    w1, w2, w3, w4 = st.columns(4)
    with w1:
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 16px; height: 100%;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #3b82f6; text-transform: uppercase;">Step 01</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin: 4px 0 6px 0;">Claim Submission</div>
                <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">Applicant submits claimed amount anchored by trusted reference ID.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with w2:
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 16px; height: 100%;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #10b981; text-transform: uppercase;">Step 02</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin: 4px 0 6px 0;">Source Comparison</div>
                <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">Backend queries reference source; detects exact match or variance delta.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with w3:
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 16px; height: 100%;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #8b5cf6; text-transform: uppercase;">Step 03</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin: 4px 0 6px 0;">Salted Commitment</div>
                <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">Computes Keccak-256 hash containing outcome and amounts with zero raw PII.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with w4:
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 14px; padding: 16px; height: 100%;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #06b6d4; text-transform: uppercase;">Step 04</div>
                <div style="font-size: 0.95rem; font-weight: 700; color: #ffffff; margin: 4px 0 6px 0;">On-Chain Anchoring</div>
                <div style="font-size: 0.8rem; color: #94a3b8; line-height: 1.4;">TruChainAudit smart contract immutably commits proof to Ethereum EVM.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)

    # Category Selection Grid
    st.markdown(
        """
        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 14px;">
            📑 Select Category for Verification
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(3)
    for index, (category, config) in enumerate(CATEGORIES.items()):
        with cols[index % 3]:
            with st.container(border=True):
                st.markdown(
                    f"""
                    <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px;">
                        <span style="font-size: 1.6rem;">{config['icon']}</span>
                        <span class="cat-tag">{config['tag']}</span>
                    </div>
                    <div style="font-size: 1.05rem; font-weight: 700; color: #ffffff; margin-bottom: 4px;">{category}</div>
                    <div style="font-size: 0.8rem; color: #94a3b8; margin-bottom: 12px; min-height: 40px; line-height: 1.4;">
                        {config['description']}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
                st.button(
                    f"Verify {category} →",
                    key=f"dash_open_{index}",
                    use_container_width=True,
                    on_click=navigate_to,
                    args=("Verify Finances", category),
                )

    st.divider()

    # Session Activity Inspector
    st.markdown(
        """
        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 10px;">
            🕒 Latest Verification in this Session
        </div>
        """,
        unsafe_allow_html=True,
    )

    if "last_verification" in st.session_state:
        st.caption(f"Category: {st.session_state.get('last_verification_category', 'Monthly Income')}")
        show_backend_response(st.session_state["last_verification"])
    else:
        st.markdown(
            """
            <div style="background: rgba(15, 23, 42, 0.45); border: 1px dashed rgba(255, 255, 255, 0.15); border-radius: 14px; padding: 24px; text-align: center; color: #94a3b8;">
                <div style="font-size: 1.8rem; margin-bottom: 6px;">🔍</div>
                <div style="font-weight: 600; color: #cbd5e1; margin-bottom: 4px;">No claims verified yet in this active session</div>
                <div style="font-size: 0.85rem;">Head to <strong>Verify Finances</strong> or click any category above to run your first automated verification.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# --------------------------------------------------
# PAGE 2: VERIFY FINANCES
# --------------------------------------------------

elif page == "Verify Finances":
    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 4px;">
                🚀 Verify Financial Claim
            </h2>
            <div style="color: #94a3b8; font-size: 0.95rem;">
                Submit a financial declaration to reconcile against reference records and anchor an immutable audit into the smart contract.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1-Click Quick Demo Presets for Hackathon Judges & Evaluators
    st.markdown(
        """
        <div style="background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.8) 100%); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 16px; padding: 18px 20px; margin-bottom: 24px;">
            <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px; flex-wrap: wrap; gap: 6px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.2rem;">⚡</span>
                    <span style="font-size: 0.95rem; font-weight: 700; color: #ffffff;">Quick Demo Presets (1-Click Fill)</span>
                </div>
                <span style="font-size: 0.75rem; color: #38bdf8; font-family: 'JetBrains Mono', monospace;">Instant Evaluation Modes</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    p1, p2, p3 = st.columns(3)

    with p1:
        st.button(
            "🟢 Match Demo (₹30,000 → VERIFIED)",
            help="Pre-fills DEMO-USER-02, Monthly Income, ₹30,000, reference PAYROLL-TEST-101",
            use_container_width=True,
            on_click=apply_preset,
            args=("DEMO-USER-02", "Monthly Income", 30000.0, "PAYROLL-TEST-101"),
        )
    with p2:
        st.button(
            "🟡 Mismatch Demo (₹35,000 → MISMATCH)",
            help="Pre-fills DEMO-USER-02, Monthly Income, ₹35,000, reference PAYROLL-TEST-101 (reference is ₹30,000)",
            use_container_width=True,
            on_click=apply_preset,
            args=("DEMO-USER-02", "Monthly Income", 35000.0, "PAYROLL-TEST-101"),
        )
    with p3:
        st.button(
            "⚪ Unverified Demo (Unknown Ref)",
            help="Pre-fills DEMO-USER-02, Monthly Income, ₹30,000, reference UNKNOWN-REF-999",
            use_container_width=True,
            on_click=apply_preset,
            args=("DEMO-USER-02", "Monthly Income", 30000.0, "UNKNOWN-REF-999"),
        )

    st.markdown("<div style='height: 14px;'></div>", unsafe_allow_html=True)

    category_options = list(CATEGORIES.keys())
    default_category = st.session_state.get("selected_category", category_options[0])
    if default_category not in category_options:
        default_category = category_options[0]

    category = st.selectbox(
        "Select Verification Category",
        category_options,
        index=category_options.index(default_category),
        key="verification_category",
    )

    config = CATEGORIES[category]

    # Verification Submission Form
    with st.form("financial_verification_form", clear_on_submit=False):
        st.markdown(
            f"""
            <div style="background: rgba(15, 23, 42, 0.4); border: 1px solid rgba(255, 255, 255, 0.08); border-radius: 12px; padding: 14px 18px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="font-size: 1.4rem;">{config['icon']}</span>
                    <div>
                        <span style="font-size: 1rem; font-weight: 700; color: #ffffff;">{category} Verification</span>
                        <div style="font-size: 0.8rem; color: #94a3b8;">{config['description']}</div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown("#### 1. Applicant & Reference Anchor")
        c_id1, c_id2 = st.columns(2)

        with c_id1:
            claimant_name = st.text_input(
                "Claim / Applicant Identifier (user_id)",
                value=st.session_state.get("form_user_id", "DEMO-USER-02"),
                placeholder="e.g. DEMO-USER-02",
                help="Applicant identifier.",
            )
        with c_id2:
            reference_id = st.text_input(
                "Reference Identifier (reference_id)",
                value=st.session_state.get("form_reference_id", config.get("default_ref", "PAYROLL-TEST-101")),
                placeholder="e.g. PAYROLL-TEST-101",
                help="Identifier in the trusted reference database.",
            )

        st.markdown("#### 2. Claim Parameters & Category Details")
        col_amt, col_blank = st.columns([1, 1])
        with col_amt:
            claimed_amount = st.number_input(
                "Claimed Amount (₹)",
                min_value=0.0,
                value=st.session_state.get("form_claimed_amount", config.get("default_amount", 30000.0)),
                step=1000.0,
                format="%.2f",
                key="form_claimed_amount_input",
            )

        details = {}
        fields = config["fields"]
        cols_fields = st.columns(2)

        for index, field in enumerate(fields):
            label, field_type, default_val = field[0], field[1], field[2] if len(field) > 2 else None
            with cols_fields[index % 2]:
                if field_type == "number":
                    details[label] = st.number_input(
                        label,
                        min_value=0.0,
                        value=float(default_val) if default_val else 0.0,
                        step=500.0,
                        format="%.2f",
                        key=f"field_{category}_{label}",
                    )
                elif field_type == "select":
                    options = field[2] if isinstance(field[2], list) else ["Standard", "Other"]
                    details[label] = st.selectbox(
                        label,
                        options,
                        key=f"field_{category}_{label}",
                    )
                elif field_type == "date":
                    details[label] = st.date_input(
                        label,
                        key=f"field_{category}_{label}",
                    ).isoformat()
                elif field_type == "text":
                    details[label] = st.text_input(
                        label,
                        value=str(default_val) if default_val else "",
                        key=f"field_{category}_{label}",
                    )

        st.markdown("#### 3. Cryptographic Evidence & Declarations")
        uploaded_file = st.file_uploader(
            "Upload Supporting Document (Optional)",
            type=["pdf", "png", "jpg", "jpeg", "csv", "txt"],
            help="Computes client-side SHA-256 hash. The hash is committed to the blockchain, preserving document privacy.",
        )

        notes = st.text_area(
            "Audit Notes (Optional)",
            placeholder="Add context or notes for this verification.",
            height=70,
        )

        consent = st.checkbox(
            "I confirm that I am authorized to submit these details and that the information is accurate.",
            value=True,
        )

        submitted = st.form_submit_button(
            "🚀 Submit for Verification & Blockchain Audit",
            type="primary",
            use_container_width=True,
        )

    if submitted:
        if not claimant_name.strip():
            st.error("Please enter the applicant or claim identifier.")
        elif not reference_id.strip():
            st.error("Please enter the reference identifier.")
        elif not consent:
            st.error("Please confirm the declaration before submitting.")
        else:
            evidence_hash = None
            evidence_filename = None

            if uploaded_file is not None:
                file_bytes = uploaded_file.getvalue()
                evidence_hash = hashlib.sha256(file_bytes).hexdigest()
                evidence_filename = uploaded_file.name

            payload = {
                "user_id": claimant_name.strip(),
                "claimant_name": claimant_name.strip(),
                "category": category,
                "claimed_amount": float(claimed_amount),
                "reference_id": reference_id.strip(),
                "details": details,
                "notes": notes.strip() or None,
                "evidence_filename": evidence_filename,
                "evidence_sha256": evidence_hash,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }

            send_verification(payload)


# --------------------------------------------------
# PAGE 3: AUDIT HISTORY
# --------------------------------------------------

elif page == "Audit History":
    st.markdown(
        """
        <div style="margin-bottom: 20px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 4px;">
                📜 Audit History & Verification Records
            </h2>
            <div style="color: #94a3b8; font-size: 0.95rem;">
                Inspect historical financial claims, verification outcomes, and immutable on-chain transaction hashes.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    try:
        with st.spinner("Fetching claims and blockchain audit ledger..."):
            claims_resp = requests.get(f"{backend_url}/claims?limit=50", timeout=5)

        if claims_resp.ok:
            claims_data = claims_resp.json()
            if claims_data:
                # Status filter selector
                filter_status = st.radio(
                    "Filter by Result:",
                    ["All Records", "VERIFIED Only", "MISMATCH Only", "UNVERIFIED Only"],
                    horizontal=True,
                )

                filtered_data = claims_data
                if filter_status == "VERIFIED Only":
                    filtered_data = [c for c in claims_data if str(c.get("status")).upper() == "VERIFIED"]
                elif filter_status == "MISMATCH Only":
                    filtered_data = [c for c in claims_data if str(c.get("status")).upper() == "MISMATCH"]
                elif filter_status == "UNVERIFIED Only":
                    filtered_data = [c for c in claims_data if str(c.get("status")).upper() == "UNVERIFIED"]

                if filtered_data:
                    df = pd.DataFrame(filtered_data)
                    df_display = df[[
                        "claim_id", "user_id", "claim_type", "claimed_amount",
                        "verified_amount", "status", "blockchain_status", "created_at"
                    ]].copy()

                    df_display.rename(columns={
                        "claim_id": "Claim ID",
                        "user_id": "Applicant",
                        "claim_type": "Category",
                        "claimed_amount": "Claimed (₹)",
                        "verified_amount": "Reference (₹)",
                        "status": "Result",
                        "blockchain_status": "Blockchain",
                        "created_at": "Timestamp"
                    }, inplace=True)

                    st.dataframe(df_display, use_container_width=True, hide_index=True)
                else:
                    st.info(f"No claims found with status '{filter_status}'.")

                st.markdown("<div style='height: 18px;'></div>", unsafe_allow_html=True)

                st.markdown(
                    """
                    <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 10px;">
                        🔍 Detailed Record Inspector
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                selected_claim_id = st.selectbox(
                    "Select Claim ID to view cryptographic audit proof:",
                    options=[c["claim_id"] for c in claims_data],
                    format_func=lambda cid: f"Claim #{cid} — Status: {next((c['status'] for c in claims_data if c['claim_id'] == cid), '')}"
                )

                if selected_claim_id:
                    matched = next((c for c in claims_data if c["claim_id"] == selected_claim_id), None)
                    if matched:
                        show_backend_response(matched)
            else:
                st.info("No claims recorded yet in the database.")
        else:
            st.error(f"Failed to fetch audit history: HTTP {claims_resp.status_code}")
    except Exception as exc:
        st.error(f"Could not connect to FastAPI backend: {exc}")

    st.divider()

    st.markdown(
        """
        <div style="font-size: 1.15rem; font-weight: 700; color: #ffffff; margin-bottom: 8px;">
            🔎 Direct Record Lookup by ID or Transaction Hash
        </div>
        """,
        unsafe_allow_html=True,
    )

    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_val = st.text_input(
            "Enter Claim ID or Transaction Hash (0x...):",
            key="search_query",
            label_visibility="collapsed",
            placeholder="e.g. 1 or 0x4d38e...",
        )
    with search_col2:
        search_clicked = st.button("Search Audit Record", use_container_width=True)

    if search_clicked:
        if search_val.strip():
            try:
                res = requests.post(f"{backend_url}/verify-record", json={"record_id": search_val.strip()}, timeout=5)
                if res.ok:
                    show_backend_response(res.json())
                else:
                    st.warning("No record found matching that ID or transaction hash.")
            except Exception as e:
                st.error(f"Lookup failed: {e}")


# --------------------------------------------------
# PAGE 4: ABOUT TRUCHAIN
# --------------------------------------------------

elif page == "About TruChain":
    st.markdown(
        """
        <div style="margin-bottom: 24px;">
            <h2 style="font-size: 1.6rem; font-weight: 800; color: #ffffff; margin-bottom: 4px;">
                🏛️ Architecture & Cryptographic Proofs
            </h2>
            <div style="color: #94a3b8; font-size: 0.95rem;">
                TruChain solves trust, traceability, and applicant privacy in automated financial decisions.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_arch1, col_arch2 = st.columns([1, 1])

    with col_arch1:
        st.markdown(
            """
            <div class="stat-card" style="margin-bottom: 18px;">
                <h4 style="color: #38bdf8; margin-top: 0;">🏗️ Enterprise Architecture</h4>
                <ul style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.7; padding-left: 20px;">
                    <li><strong>Streamlit Interface (Port 8504):</strong> Glassmorphic Web3 dashboard for applicant submission and regulatory audit tracking.</li>
                    <li><strong>FastAPI Backend (Port 8000):</strong> Asynchronous API engine orchestrating reconciliation logic and commitment hashing.</li>
                    <li><strong>Hardhat Blockchain (Port 8545):</strong> Local Ethereum JSON-RPC EVM node.</li>
                    <li><strong>TruChainAudit Smart Contract:</strong> Solidity contract deployed at address <code>0x5FbDB2315678afecb367f032d93F642f64180aa3</code>.</li>
                    <li><strong>Web3.py Client:</strong> Cryptographic commitment signing and on-chain event receipt verification.</li>
                </ul>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_arch2:
        st.markdown(
            """
            <div class="stat-card" style="margin-bottom: 18px;">
                <h4 style="color: #34d399; margin-top: 0;">🔐 Privacy-First Commitment Scheme</h4>
                <div style="color: #cbd5e1; font-size: 0.9rem; line-height: 1.7;">
                    Financial documents and applicant identities contain sensitive Personally Identifiable Information (PII). TruChain enforces:
                    <ol style="padding-left: 20px; margin-top: 8px;">
                        <li><strong>Zero Raw PII On-Chain:</strong> Raw amounts, names, and bank statements are never stored on the public blockchain.</li>
                        <li><strong>Cryptographic Salting:</strong> Uses random salts to prevent rainbow table attacks.</li>
                        <li><strong>Tamper-Evident Immutability:</strong> Any change to amounts invalidates the on-chain hash.</li>
                        <li><strong>Independent Auditor Verification:</strong> Regulators verify claims without seeing unencrypted data.</li>
                    </ol>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown(
        """
        <div style="background: rgba(15, 23, 42, 0.7); border: 1px solid rgba(59, 130, 246, 0.3); border-radius: 16px; padding: 20px; margin-top: 10px;">
            <h4 style="color: #60a5fa; margin-top: 0; margin-bottom: 8px;">🧮 Mathematical Commitment Formula</h4>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 0.9rem; color: #38bdf8; background: rgba(0, 0, 0, 0.4); padding: 12px 16px; border-radius: 8px; overflow-x: auto;">
                CommitmentHash = Keccak-256("TruChain" || claimId || status || claimedAmount || verifiedAmount || salt)
            </div>
            <div style="color: #94a3b8; font-size: 0.85rem; margin-top: 10px; line-height: 1.5;">
                Every audit record produces an immutable 32-byte cryptographic digest that is permanently stored in the smart contract's state storage.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
