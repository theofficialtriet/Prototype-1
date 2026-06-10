import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import re
import plotly.graph_objects as go
from edgar import Company, set_identity

# ── Page config ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Executive DCF Model", layout="wide")

# ── Global fallback guards ───────────────────────────────────────────────────
exact_inc_items: list = []
exact_bal_items: list = []
exact_cf_items:  list = []
fallback_active  = False
sec_failed       = True

# ── Session state ─────────────────────────────────────────────────────────────
if "projection_notes" not in st.session_state:
    st.session_state["projection_notes"] = []

# ── Row-index constants ───────────────────────────────────────────────────────
FULL_INC_ROWS = [
    "Revenue ($M)", "Revenue Growth (%)",
    "Cost of Revenue ($M)", "Cost of Operations ($M)", "Other Costs ($M)",
    "Operating EBIT ($M)", "Operating Margin (%)",
    "Tax Provision ($M)", "EBIAT ($M)",
]
FULL_BAL_ROWS = [
    "Cash ($M)", "Debt ($M)",
    "Receivables ($M)", "Inventory ($M)", "Payables ($M)",
    "Net Working Capital ($M)",
]
FULL_CF_ROWS = [
    "EBIAT ($M)", "D&A ($M)", "CapEx ($M)",
    "Change in NWC ($M)", "Unlevered Free Cash Flow (FCFF) ($M)",
    "Discount Factor", "Present Value of FCF ($M)",
]

# ── Global CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp {
        background-color: #000000 !important;
        color: #E7E9EA !important;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif !important;
    }
    section[data-testid="stSidebar"] {
        background-color: #16181C !important;
        border-right: 1px solid #2F3336 !important;
    }
    input, select, textarea, div[role="button"], div[data-baseweb="input"] {
        background-color: #000000 !important;
        color: #E7E9EA !important;
        border: 1px solid #2F3336 !important;
        border-radius: 9999px !important;
    }
    button[data-baseweb="tab"] {
        color: #71767B !important;
        font-weight: 500 !important;
        background: transparent !important;
        border: none !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #1D9BF0 !important;
        border-bottom: 2px solid #1D9BF0 !important;
        font-weight: 700 !important;
    }
    div.stButton > button:first-child {
        background-color: #1D9BF0 !important;
        color: #FFFFFF !important;
        border: 1px solid #1D9BF0 !important;
        border-radius: 9999px !important;
        font-weight: 700 !important;
        padding: 0.5rem 1.5rem !important;
        transition: all 0.15s cubic-bezier(0.4, 0, 0.2, 1) !important;
    }
    div.stButton > button:first-child:hover {
        background-color: #1A8CD8 !important;
        box-shadow: 0 0 10px rgba(29, 155, 240, 0.3) !important;
        transform: translateY(-1px);
    }
    h1, h2, h3 { font-weight: 800 !important; color: #F7F9F9 !important; }
    div[data-testid="stExpander"] {
        background-color: #16181C !important;
        border: 1px solid #2F3336 !important;
        border-radius: 12px !important;
    }
    [data-testid="stDataEditor"] {
        border: 1px solid #2F3336 !important;
        border-radius: 8px !important;
        overflow: hidden !important;
    }
    [data-testid="stDataEditor"]:focus-within {
        border-color: #1D9BF0 !important;
        box-shadow: 0 0 0 3px rgba(29, 155, 240, 0.25) !important;
    }
    div[data-testid="stToggle"] div[role="switch"][aria-checked="true"] {
        background-color: #00BA7C !important;
    }
    div[data-testid="stToggle"] div[role="switch"][aria-checked="true"] > div {
        background-color: #FFFFFF !important;
    }
    .ticker-wrap {
        overflow: hidden; width: 100%;
        background-color: #16181C; border: 1px solid #2F3336;
        border-radius: 12px; padding: 8px 0;
        box-shadow: 0 4px 6px rgba(0,0,0,0.2); margin-bottom: 20px;
    }
    .ticker-content { display: flex; width: 200%; animation: ticker 35s linear infinite; }
    .ticker-item { flex-shrink:0; width:50%; display:flex; justify-content:space-around; white-space:nowrap; font-size:0.85rem; }
    @keyframes ticker {
        0%   { transform: translate3d(0,0,0); }
        100% { transform: translate3d(-50%,0,0); }
    }
    .section-label {
        color: #71767B; font-size: 0.72rem; letter-spacing: 0.07em;
        text-transform: uppercase; font-weight: 700;
        border-bottom: 1px solid #2F3336; padding-bottom: 4px; margin: 16px 0 8px 0;
    }
    .adv-info-box {
        background: #0B1A2A; border: 1px solid #1D9BF0;
        border-radius: 8px; padding: 10px 14px; margin-bottom: 10px;
        font-size: 0.82rem; color: #93C5FD;
    }
</style>
""", unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  HELPERS                                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

def render_luxury_card(label: str, value: str, is_accent: bool = False) -> str:
    border = "#1D9BF0" if is_accent else "#2F3336"
    bg     = "#16181C" if is_accent else "#000000"
    color  = "#1D9BF0" if is_accent else "#F7F9F9"
    return f"""
    <div style="background:{bg};border:1px solid {border};border-top:3px solid {border};
        padding:15px;border-radius:12px;text-align:center;margin-bottom:12px;
        box-shadow:0 4px 6px -1px rgba(0,0,0,0.2);">
        <span style="color:#71767B;font-size:0.75rem;letter-spacing:0.05em;
            text-transform:uppercase;font-weight:700;">{label}</span>
        <h2 style="color:{color};font-size:1.55rem;margin:5px 0 0 0;font-weight:800;">{value}</h2>
    </div>"""


def generate_luxury_table(df: pd.DataFrame) -> str:
    html = ("<div style='overflow-x:auto;margin:15px 0;border-radius:12px;"
            "border:1px solid #2F3336;'>")
    html += ("<table style='width:100%;border-collapse:collapse;"
             "background:#000000;color:#E7E9EA;"
             "font-family:-apple-system,BlinkMacSystemFont,\"Segoe UI\",Roboto,sans-serif;'>")
    html += "<tr style='border-bottom:2px solid #2F3336;'>"
    html += ("<th style='padding:10px 14px;text-align:left;background:#16181C;"
             "color:#1D9BF0;font-weight:700;min-width:200px;'>Financial Item</th>")
    for col in df.columns:
        html += (f"<th style='padding:10px 14px;text-align:right;background:#16181C;"
                 f"color:#F7F9F9;font-weight:600;'>{col}</th>")
    html += "</tr>"

    KEY_WORDS   = ["Sales", "Revenue", "Profit", "EBIT", "Earnings", "FCF", "Cash ($M)", "Debt ($M)"]
    TOTAL_WORDS = ["Present Value of FCF", "Value of Future Cash"]

    for idx, row_name in enumerate(df.index):
        is_total = any(w in row_name for w in TOTAL_WORDS)
        is_key   = any(w in row_name for w in KEY_WORDS)
        is_proj  = False
        if is_total:
            row_style = ("style='background:#16181C;font-weight:bold;"
                         "border-top:1px solid #1D9BF0;border-bottom:3px double #1D9BF0;'")
        elif is_key:
            row_style = "style='font-weight:700;color:#FFFFFF;background:#16181C;'"
        elif idx % 2 == 0:
            row_style = "style='background:#0B0C0E;'"
        else:
            row_style = "style='background:#000000;'"

        html += f"<tr {row_style}>"
        lbl_style = "padding:8px 14px;text-align:left;border-right:1px solid #2F3336;"
        if is_total:
            lbl_style += "color:#1D9BF0;"
        html += f"<td style='{lbl_style}'>{row_name}</td>"
        for col in df.columns:
            is_proj_col = "(P)" in str(col)
            cell_color  = "#E7E9EA" if not is_proj_col else "#93C5FD"
            cell_style  = (f"padding:8px 14px;text-align:right;"
                           f"font-family:'Courier New',monospace;color:{cell_color};")
            html += f"<td style='{cell_style}'>{df.at[row_name, col]}</td>"
        html += "</tr>"

    html += "</table></div>"
    return html


def clean_sec_dataframe(df) -> pd.DataFrame:
    if df is None or not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    drops = [c for c in ['level', 'abstract', 'parent_concept',
                          'parent_abstract_concept', 'concept'] if c in df.columns]
    try:
        return df.drop(columns=drops)
    except Exception:
        return df


def map_columns_to_years(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    new_cols = {}
    for col in df.columns:
        m = re.search(r'\b(19|20)\d{2}\b', str(col))
        new_cols[col] = m.group(0) if m else str(col)
    return df.rename(columns=new_cols)


def extract_year_string(col) -> str:
    m = re.search(r'\b(19|20)\d{2}\b', str(col))
    return m.group(0) if m else str(col)


def safe_get(df: pd.DataFrame, keys: list, col_idx: int = 0,
             default: float = 0.0) -> float:
    if df is None or df.empty:
        return default
    norm = df.copy()
    norm.index = norm.index.astype(str).str.lower().str.strip()
    for key in keys:
        kn = key.lower().strip()
        if kn in norm.index:
            row = norm.loc[kn]
            val = row.iloc[col_idx] if isinstance(row, pd.Series) else row
            if pd.notna(val):
                return float(val)
    return default


def extract_numeric_rows_for_advanced(df: pd.DataFrame) -> list:
    if df is None or df.empty:
        return []
    seen, result = set(), []
    for idx, row in df.iterrows():
        if not str(idx).strip():
            continue
        try:
            if pd.to_numeric(row, errors='coerce').notna().any():
                key = str(idx)
                if key not in seen:
                    seen.add(key)
                    result.append(key)
        except Exception:
            pass
    return result


def find_projected_row_values(df: pd.DataFrame, keywords: list,
                               default_values, proj_periods: list):
    if df is None or df.empty:
        return default_values
    norm = df.copy()
    norm.index = norm.index.astype(str).str.lower().str.strip()
    for kw in keywords:
        kw_l = kw.lower().strip()
        for idx in norm.index:
            if kw_l in idx:
                try:
                    return np.array([float(norm.at[idx, c]) for c in proj_periods])
                except Exception:
                    pass
    return default_values


def get_driver_row(df: pd.DataFrame, row_name: str, num_years: int) -> np.ndarray:
    try:
        return np.array([float(x) for x in df.loc[row_name].values]) / 100.0
    except Exception:
        return np.zeros(num_years)


def format_statement_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    """Format a raw calc DataFrame for display (dollars, pct, etc.)."""
    out = raw_df.astype(object)
    for col in out.columns:
        for row in out.index:
            val = out.at[row, col]
            if val == "" or (not isinstance(val, str) and pd.isna(val)):
                out.at[row, col] = "—"
            elif isinstance(row, str) and ("%" in row or "Growth" in row or "Margin" in row):
                try:
                    out.at[row, col] = f"{float(val):,.1f}%"
                except Exception:
                    out.at[row, col] = str(val)
            elif isinstance(row, str) and ("Multiplier" in row or "Factor" in row):
                try:
                    out.at[row, col] = f"{float(val):.3f}"
                except Exception:
                    out.at[row, col] = str(val)
            else:
                try:
                    out.at[row, col] = f"${float(val):,.1f}"
                except Exception:
                    out.at[row, col] = str(val)
    return out


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  LIVE DATA FETCHERS                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

@st.cache_data(ttl=1800)
def fetch_live_us10y_trend():
    url    = "https://quote.cnbc.com/quote-html-webservice/quote.htm"
    params = dict(noform="1", partnerId="2", fund="1", exthrs="0",
                  output="json", symbolType="issue", symbols="US10Y",
                  requestMethod="extended")
    try:
        res   = requests.get(url, params=params, timeout=5)
        quote = res.json()["ExtendedQuoteResult"]["ExtendedQuote"][0]["QuickQuote"]
        live  = float(quote["last"]) / 100.0
        hist  = yf.Ticker("^TNX").history(period="1mo")
        if hist.empty:
            raise ValueError()
        rates = (hist["Close"].values / 10.0) / 100.0
        dates = hist.index.strftime("%Y-%m-%d").tolist()
        return live, rates.tolist(), dates
    except Exception:
        np.random.seed(42)
        base = 0.0425
        path = base + np.cumsum(np.random.normal(0, 0.0005, 30))
        return base, path.tolist(), [f"2026-05-{i:02d}" for i in range(1, 31)]


@st.cache_data(ttl=900)
def fetch_ticker_tape():
    symbols = {"S&P 500": "^GSPC", "NASDAQ": "^IXIC", "Apple": "AAPL",
               "Microsoft": "MSFT", "NVIDIA": "NVDA", "Google": "GOOGL"}
    items = []
    for name, sym in symbols.items():
        try:
            hist = yf.Ticker(sym).history(period="2d")
            if not hist.empty and len(hist) >= 2:
                c0, c1 = hist["Close"].iloc[-2], hist["Close"].iloc[-1]
                chg    = c1 - c0
                pct    = (chg / c0) * 100
                sign   = "+" if chg >= 0 else ""
                color  = "#39FF14" if chg >= 0 else "#FF3B30"
                items.append(
                    f"<span style='color:#FFFFFF;font-weight:700;'>{name}</span> "
                    f"<span style='color:{color};'>{c1:,.2f} ({sign}{pct:.2f}%)</span>"
                )
        except Exception:
            pass
    return (" &nbsp;&nbsp;•&nbsp;&nbsp; ".join(items)
            or "S&P 500 5,420.15 (+0.45%) &nbsp;&nbsp;•&nbsp;&nbsp; NASDAQ 18,540.22 (+0.65%)")


@st.cache_data(show_spinner="Accessing SEC EDGAR…", ttl=3600)
def load_sec_data(ticker_str: str, email_str: str) -> dict:
    try:
        set_identity(email_str)
        company = Company(ticker_str)
        fin     = company.get_financials()
        return {
            "income_standard":   fin.income_statement().to_dataframe(view="standard"),
            "income_summary":    fin.income_statement().to_dataframe(view="summary"),
            "balance_standard":  fin.balance_sheet().to_dataframe(view="standard"),
            "balance_summary":   fin.balance_sheet().to_dataframe(view="summary"),
            "cashflow_standard": fin.cashflow_statement().to_dataframe(view="standard"),
            "cashflow_summary":  fin.cashflow_statement().to_dataframe(view="summary"),
            "company_name": str(company.name),
            "cik": str(company.cik),
            "error": None,
        }
    except Exception as e:
        return {"error": str(e)}


def get_mock_market_vars(ticker_str: str):
    t = ticker_str.upper()
    cols = [pd.Timestamp("2023-12-31"), pd.Timestamp("2024-12-31"), pd.Timestamp("2025-12-31")]
    MOCKS = {
        "AAPL": {
            "info": {"currentPrice": 185.00, "sharesOutstanding": 15_400_000_000,
                     "beta": 1.2, "marketCap": 2_849_000_000_000,
                     "longName": "Apple Inc. (Reference Database)"},
            "fin":  pd.DataFrame({cols[0]: [383_285e6, 114_301e6, 16_741e6, 114_301e6],
                                  cols[1]: [385_600e6, 115_000e6, 15_000e6, 115_000e6],
                                  cols[2]: [410_000e6, 125_000e6, 16_000e6, 125_000e6]},
                                 index=["Total Revenue","Operating Income","Tax Provision","Pretax Income"]),
            "bal":  pd.DataFrame({cols[0]: [135e9, 105e9], cols[1]: [140e9, 100e9], cols[2]: [150e9, 95e9]},
                                 index=["Cash And Cash Equivalents","Total Debt"]),
            "cf":   pd.DataFrame({cols[0]: [10e9, 11.5e9], cols[1]: [9.5e9, 11e9], cols[2]: [10.5e9, 12e9]},
                                 index=["Capital Expenditure","Depreciation And Amortization"]),
        },
        "MSFT": {
            "info": {"currentPrice": 415.00, "sharesOutstanding": 7_430_000_000,
                     "beta": 1.15, "marketCap": 3_083_000_000_000,
                     "longName": "Microsoft Corporation (Reference Database)"},
            "fin":  pd.DataFrame({cols[0]: [211_915e6, 88_523e6, 16_950e6, 88_523e6],
                                  cols[1]: [245_120e6, 100_000e6, 18_500e6, 100_000e6],
                                  cols[2]: [280_000e6, 118_000e6, 21_000e6, 118_000e6]},
                                 index=["Total Revenue","Operating Income","Tax Provision","Pretax Income"]),
            "bal":  pd.DataFrame({cols[0]: [80e9, 75e9], cols[1]: [85e9, 70e9], cols[2]: [90e9, 68e9]},
                                 index=["Cash And Cash Equivalents","Total Debt"]),
            "cf":   pd.DataFrame({cols[0]: [28.1e9, 13.6e9], cols[1]: [30.5e9, 14.2e9], cols[2]: [32e9, 15e9]},
                                 index=["Capital Expenditure","Depreciation And Amortization"]),
        },
    }
    m = MOCKS.get(t)
    if m:
        return m["info"], m["fin"], m["bal"], m["cf"]
    info = {"currentPrice": 150.00, "sharesOutstanding": 1_000_000_000,
            "beta": 1.1, "marketCap": 150_000_000_000,
            "longName": f"{t} Corp (Reference Database)"}
    fin  = pd.DataFrame({cols[0]: [10e9, 2e9, 315e6, 2e9],
                         cols[1]: [11e9, 2.2e9, 350e6, 2.2e9],
                         cols[2]: [12.1e9, 2.42e9, 385e6, 2.42e9]},
                        index=["Total Revenue","Operating Income","Tax Provision","Pretax Income"])
    bal  = pd.DataFrame({cols[0]: [2e9, 1.5e9], cols[1]: [2.2e9, 1.4e9], cols[2]: [2.4e9, 1.3e9]},
                        index=["Cash And Cash Equivalents","Total Debt"])
    cf   = pd.DataFrame({cols[0]: [400e6, 400e6], cols[1]: [440e6, 440e6], cols[2]: [484e6, 484e6]},
                        index=["Capital Expenditure","Depreciation And Amortization"])
    return info, fin, bal, cf


@st.cache_data(show_spinner="Loading market data…", ttl=3600)
def load_market_vars(ticker_str: str):
    try:
        ticker = yf.Ticker(ticker_str)
        info   = dict(ticker.info)
        if not info or "currentPrice" not in info:
            raise ValueError("Incomplete info.")
        fin = ticker.financials.copy()
        if fin.empty:
            raise ValueError("Empty financials.")
        bal = ticker.balance_sheet.copy()
        cf  = ticker.cashflow.copy()
        for df in (fin, bal, cf):
            df.sort_index(axis=1, inplace=True)
        return info, fin, bal, cf, False
    except Exception:
        info, fin, bal, cf = get_mock_market_vars(ticker_str)
        return info, fin, bal, cf, True


# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  SIDEBAR                                                                     ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

st.sidebar.markdown(
    "<h2 style='color:#1D9BF0;font-size:1.4rem;border-bottom:1px solid #2F3336;"
    "padding-bottom:8px;margin-bottom:15px;'>Executive Control</h2>",
    unsafe_allow_html=True,
)

sec_email = st.sidebar.text_input("SEC User-Agent Email",
                                   value="analyst@independentresearch.com")
if sec_email:
    try:
        set_identity(sec_email)
    except Exception as e:
        st.sidebar.error(f"SEC identity error: {e}")

ticker_symbol  = st.sidebar.text_input("Ticker Symbol", value="AAPL").upper().strip()
forecast_years = st.sidebar.slider("Forecast Horizon (Years)", 1, 15, 5)

projection_init = st.sidebar.radio(
    "Model Initialization",
    ["Historical Roll-Forward (Preload Averages)", "Start Fresh (All Zeros)"],
    index=0,
    help="'Roll-Forward' seeds each driver from the company's historical average. "
         "'Start Fresh' clears all inputs to zero so you build from scratch.",
)
start_fresh = "Start Fresh" in projection_init

st.sidebar.markdown(
    "<h3 style='color:#1D9BF0;font-size:1.15rem;'>Global Assumptions</h3>",
    unsafe_allow_html=True,
)

live_rf, rf_history, rf_dates = fetch_live_us10y_trend()

st.sidebar.markdown(f"""
<div style="background:#000000;border:1px solid #2F3336;border-top:3px solid #1D9BF0;
    padding:16px;border-radius:12px;text-align:center;margin-bottom:20px;
    box-shadow:0 4px 6px rgba(0,0,0,0.4);">
    <span style="color:#71767B;font-size:0.75rem;letter-spacing:0.05em;
        text-transform:uppercase;font-weight:700;display:block;">US 10-Yr Yield (CNBC Live)</span>
    <h2 style="color:#1D9BF0;font-size:1.85rem;margin:8px 0;font-weight:800;">{live_rf*100:.3f}%</h2>
    <p style="color:#71767B;font-size:0.72rem;margin:0;">Risk-free baseline for WACC</p>
</div>
""", unsafe_allow_html=True)

fig_yield = go.Figure()
fig_yield.add_trace(go.Scatter(
    x=rf_dates, y=[x * 100 for x in rf_history],
    mode="lines+markers",
    line=dict(color="#1D9BF0", width=2),
    marker=dict(size=4, color="#39FF14"),
))
fig_yield.update_layout(
    paper_bgcolor="#000000", plot_bgcolor="#000000",
    font_color="#71767B",
    xaxis=dict(showgrid=True, gridcolor="#2F3336", showticklabels=False),
    yaxis=dict(showgrid=True, gridcolor="#2F3336", ticksuffix="%"),
    margin=dict(l=10, r=10, t=10, b=10), height=120,
)
st.sidebar.plotly_chart(fig_yield, use_container_width=True,
                         config={"displayModeBar": False})

erp              = st.sidebar.number_input("Equity Risk Premium (%)", 0.0, 20.0, 5.5, 0.1) / 100
perpetual_growth = st.sidebar.number_input("Terminal Growth Rate (%)", 0.0, 10.0, 2.0, 0.1) / 100

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  DATA LOADING                                                                ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

if not ticker_symbol:
    st.info("Enter a ticker symbol in the sidebar to begin.")
    st.stop()

sec_data = load_sec_data(ticker_symbol, sec_email)
yf_info, yf_financials, yf_balance, yf_cashflow, fallback_active = load_market_vars(ticker_symbol)

sec_failed   = not sec_data or ("error" in sec_data and sec_data["error"] is not None)
company_name = sec_data.get("company_name", yf_info.get("longName", ticker_symbol)) if not sec_failed else yf_info.get("longName", ticker_symbol)
cik          = sec_data.get("cik", "N/A") if not sec_failed else "N/A"

current_price      = yf_info.get("currentPrice", 0.0)
shares_outstanding = yf_info.get("sharesOutstanding", 1.0)
beta               = yf_info.get("beta", 1.0)

# Balance sheet baseline
cash_and_equiv = safe_get(yf_balance, ["Cash And Cash Equivalents",
                                        "Cash Cash Equivalents And Short Term Investments",
                                        "Cash"], col_idx=-1)
total_debt     = safe_get(yf_balance, ["Total Debt", "Long Term Debt"], col_idx=-1)
if total_debt == 0.0:
    total_debt = (safe_get(yf_balance, ["Long Term Debt"], col_idx=-1) +
                  safe_get(yf_balance, ["Current Debt", "Short Long Term Debt"], col_idx=-1))
net_debt = max(0.0, total_debt - cash_and_equiv)

# Income statement baseline
latest_revenue  = safe_get(yf_financials, ["Total Revenue", "Revenue"], col_idx=-1)
latest_ebit     = safe_get(yf_financials, ["Operating Income", "EBIT"], col_idx=-1)
latest_interest = safe_get(yf_financials, ["Interest Expense"], col_idx=-1)
latest_tax      = safe_get(yf_financials, ["Tax Provision", "Income Tax Expense"], col_idx=-1)
latest_ebt      = safe_get(yf_financials, ["Pretax Income", "Income Before Tax"], col_idx=-1)
latest_capex    = abs(safe_get(yf_cashflow, ["Capital Expenditure", "CapEx"], col_idx=-1))
latest_da       = safe_get(yf_cashflow, ["Depreciation And Amortization", "Depreciation"], col_idx=-1)

# Derived percentages in $M
hist_rev_last  = latest_revenue / 1e6
hist_cogs_last = (safe_get(yf_financials, ["Cost Of Revenue", "CostOfRevenue"], col_idx=-1) / 1e6) or (0.60 * hist_rev_last)
hist_opex_last = (safe_get(yf_financials, ["Selling General Administrative", "Operating Expense"], col_idx=-1) / 1e6) or (0.15 * hist_rev_last)
hist_other_last = 0.02 * hist_rev_last
hist_ar_last   = (safe_get(yf_balance, ["Accounts Receivable", "Receivables"], col_idx=-1) / 1e6) or (0.12 * hist_rev_last)
hist_inv_last  = (safe_get(yf_balance, ["Inventory", "Inventories"], col_idx=-1) / 1e6) or (0.10 * hist_rev_last)
hist_ap_last   = (safe_get(yf_balance, ["Accounts Payable", "Payables"], col_idx=-1) / 1e6) or (0.08 * hist_rev_last)
hist_cash_last = cash_and_equiv / 1e6
hist_debt_last = total_debt / 1e6

hist_tax_rate     = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
hist_capex_pct    = latest_capex / latest_revenue if latest_revenue else 0.04
hist_da_pct       = latest_da / latest_revenue if latest_revenue else 0.04
hist_nwc_chg_pct  = 0.01
hist_dso = (hist_ar_last * 365) / hist_rev_last  if hist_rev_last  > 0 else 45
hist_dio = (hist_inv_last * 365) / hist_cogs_last if hist_cogs_last > 0 else 45
hist_dpo = (hist_ap_last  * 365) / hist_cogs_last if hist_cogs_last > 0 else 45
hist_cash_pct = hist_cash_last / hist_rev_last if hist_rev_last > 0 else 0.10
hist_debt_pct = hist_debt_last / hist_rev_last if hist_rev_last > 0 else 0.15

hist_rev_growth = 0.08
if yf_financials is not None and yf_financials.shape[1] > 1:
    try:
        rv = yf_financials.loc["Total Revenue"].values
        hist_rev_growth = (rv[-1] / rv[-2]) - 1
    except Exception:
        pass

# WACC
cost_of_equity    = live_rf + beta * erp
implied_int_rate  = 0.05
if total_debt > 0 and latest_interest > 0:
    implied_int_rate = min(latest_interest / total_debt, 0.15)
market_cap   = yf_info.get("marketCap", shares_outstanding * current_price)
total_val    = market_cap + total_debt
w_eq         = market_cap / total_val if total_val > 0 else 1.0
w_de         = total_debt / total_val if total_val > 0 else 0.0

st.sidebar.markdown(
    "<h3 style='color:#1D9BF0;font-size:1.15rem;'>WACC Matrix</h3>",
    unsafe_allow_html=True,
)
ui_cost_eq   = st.sidebar.number_input("Required Return on Equity (%)", value=float(cost_of_equity * 100), step=0.1) / 100
ui_cost_debt = st.sidebar.number_input("Pre-Tax Cost of Debt (%)", value=float(implied_int_rate * 100), step=0.1) / 100
ui_wacc      = (w_eq * ui_cost_eq) + (w_de * ui_cost_debt * (1 - hist_tax_rate))
st.sidebar.metric("Blended WACC", f"{ui_wacc * 100:.2f}%")

# ── Column layout ─────────────────────────────────────────────────────────────
hist_columns   = [extract_year_string(c) for c in yf_financials.columns]
num_hist       = len(hist_columns)
proj_columns   = [f"{int(hist_columns[-1]) + i} (P)" for i in range(1, forecast_years + 1)]
# alias used everywhere below
proj_cols      = proj_columns

# ── Ticker tape ───────────────────────────────────────────────────────────────
tape = fetch_ticker_tape()
st.markdown(f"""
<div class="ticker-wrap">
  <div class="ticker-content">
    <div class="ticker-item">{tape}</div>
    <div class="ticker-item">{tape}</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f"<h2 style='margin-bottom:2px;'>{company_name}</h2>"
    f"<span style='color:#71767B;font-size:0.85rem;'>CIK: {cik} &nbsp;|&nbsp; "
    f"{'⚠️ Yahoo Finance fallback active — SEC unavailable' if fallback_active or sec_failed else '✅ SEC EDGAR live'}</span>",
    unsafe_allow_html=True,
)

# ── Two-column workspace ──────────────────────────────────────────────────────
col_left, col_right = st.columns([1, 1.2], gap="large")

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  LEFT COLUMN — Controls & Projections Editor                                 ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
with col_left:
    st.markdown(
        "<h4 style='color:#E7E9EA;margin-top:0;margin-bottom:10px;font-weight:700;'>"
        "Model Configuration</h4>",
        unsafe_allow_html=True,
    )

    advanced_mode = st.toggle("Advanced Mode", value=True)
    jargon_free   = st.toggle(
        "Translate Jargon to Plain English" if advanced_mode
        else "✨ Translate Jargon to Plain English",
        value=True,
    )

    if advanced_mode:
        lbl_comment = "Comment"
        lbl_tab_inc = "Income Statement"
        lbl_tab_bal = "Balance Sheet"
        lbl_tab_cf  = "Cash Flow"
        lbl_timeline = "Integrated Forecast Timeline"
    else:
        lbl_comment = "💬 Comment"
        lbl_tab_inc = "📊 Income Statement"
        lbl_tab_bal = "🏛️ Balance Sheet"
        lbl_tab_cf  = "💸 Cash Flow"
        lbl_timeline = "📊 Integrated Forecast Timeline"

    st.markdown("<hr style='border-color:#2F3336;margin:12px 0;' />",
                unsafe_allow_html=True)

    # ── Resolve exact SEC line items for Advanced Mode ─────────────────────────
    raw_sec_inc = pd.DataFrame()
    raw_sec_bal = pd.DataFrame()
    raw_sec_cf  = pd.DataFrame()

    if advanced_mode and not sec_failed:
        def _prep_sec_df(key: str) -> pd.DataFrame:
            df = clean_sec_dataframe(sec_data.get(key)).copy()
            if not df.empty and "label" in df.columns:
                df = df.set_index("label")
                df = df[~df.index.duplicated(keep="first")]
            return df

        raw_sec_inc = _prep_sec_df("income_standard")
        raw_sec_bal = _prep_sec_df("balance_standard")
        raw_sec_cf  = _prep_sec_df("cashflow_standard")

        exact_inc_items = extract_numeric_rows_for_advanced(raw_sec_inc)
        exact_bal_items = extract_numeric_rows_for_advanced(raw_sec_bal)
        exact_cf_items  = extract_numeric_rows_for_advanced(raw_sec_cf)

    # ── Annotation dialog ──────────────────────────────────────────────────────
    @st.dialog("Model Annotations & Citations" if advanced_mode
               else "📝 Model Annotations & Citations")
    def show_comment_dialog(periods):
        st.markdown("Add analytical notes or source citations for any cell — "
                    "similar to comments in Google Docs or Excel.")
        c1, c2 = st.columns(2)
        with c1:
            stmt = st.selectbox("Statement", ["Income Statement",
                                              "Balance Sheet",
                                              "Cash Flow Statement"])
        with c2:
            if stmt == "Income Statement":
                items = (exact_inc_items if advanced_mode and not sec_failed
                         and len(exact_inc_items) > 0
                         else ["Revenue Growth Rate (%)", "Cost of Revenue as % of Rev (%)",
                               "Operating Costs as % of Rev (%)", "Effective Tax Rate (%)"])
            elif stmt == "Balance Sheet":
                items = (exact_bal_items if advanced_mode and not sec_failed
                         and len(exact_bal_items) > 0
                         else ["Receivables % of Revenue (%)", "Inventory % of Revenue (%)",
                               "Payables % of Revenue (%)", "Cash Reserves % of Revenue (%)",
                               "Debt % of Revenue (%)"])
            else:
                items = (exact_cf_items if advanced_mode and not sec_failed
                         and len(exact_cf_items) > 0
                         else ["CapEx as % of Revenue (%)", "D&A as % of Revenue (%)"])
            note_item = st.selectbox("Line Item", items)

        note_year     = st.selectbox("Period", periods)
        note_text     = st.text_area("Analytical Rationale / Comment")
        note_citation = st.text_input("Source (URL, report, earnings call)")

        if st.button("Publish Annotation"):
            if note_text:
                st.session_state["projection_notes"].append({
                    "statement": stmt, "item": note_item,
                    "period": note_year, "note": note_text,
                    "citation": note_citation or "Independent Analyst Forecast",
                })
                st.rerun()

    # ── Jargon tip ────────────────────────────────────────────────────────────
    if jargon_free:
        st.info("💡 **How this works**: We estimate how much cash the company will generate, "
                "apply a safety discount (money today > money tomorrow), and sum it up to find "
                "what one share is truly worth.")

    # ── Section header + comment button ───────────────────────────────────────
    hdr_l, hdr_r = st.columns([4, 1.5], gap="small")
    with hdr_l:
        st.markdown("<h3 style='color:#1D9BF0;margin-top:0;'>Projections Modeler</h3>",
                    unsafe_allow_html=True)
    with hdr_r:
        if st.button(lbl_comment, use_container_width=True):
            show_comment_dialog(proj_cols)

    # ── Percentage column config ───────────────────────────────────────────────
    pct_col_cfg = {
        col: st.column_config.NumberColumn(
            label=col, format="%.1f%%",
            min_value=-100.0, max_value=500.0, step=0.1
        ) for col in proj_cols
    }

    # ── PROJECTION TABS ────────────────────────────────────────────────────────
    tab_inc, tab_bal, tab_cf = st.tabs([lbl_tab_inc, lbl_tab_bal, lbl_tab_cf])

    # Seed values (0 = Start Fresh, else historical averages)
    def _seed(val): return 0.0 if start_fresh else val

    # ── INCOME STATEMENT TAB ──────────────────────────────────────────────────
    with tab_inc:
        adv_inc_ok = advanced_mode and not sec_failed and len(exact_inc_items) > 0

        if adv_inc_ok:
            st.markdown(
                "<div class='adv-info-box'>🔬 <b>Advanced Mode</b> — Every SEC-reported Income "
                "Statement line is available. Enter a YoY growth rate (%) per year. "
                "Leave at 0% to hold flat.</div>",
                unsafe_allow_html=True,
            )
            init = 0.0 if start_fresh else 5.0
            df0  = pd.DataFrame(
                {c: [init] * len(exact_inc_items) for c in proj_cols},
                index=exact_inc_items,
            )
            edited_inc_df = st.data_editor(
                df0, use_container_width=True,
                column_config=pct_col_cfg, key="inc_adv_v1",
            )
        else:
            if advanced_mode and sec_failed:
                st.warning("SEC unavailable — showing simplified drivers.")
            rows = ["Revenue Growth Rate (%)",
                    "Cost of Revenue as % of Rev (%)",
                    "Operating Costs as % of Rev (%)",
                    "Other Costs as % of Rev (%)",
                    "Effective Tax Rate (%)"]
            vals = [_seed(hist_rev_growth * 100),
                    _seed((hist_cogs_last / hist_rev_last) * 100 if hist_rev_last else 60.0),
                    _seed((hist_opex_last / hist_rev_last) * 100 if hist_rev_last else 15.0),
                    _seed((hist_other_last / hist_rev_last) * 100 if hist_rev_last else 2.0),
                    _seed(hist_tax_rate * 100)]
            df0  = pd.DataFrame({c: vals for c in proj_cols}, index=rows)
            edited_inc_df = st.data_editor(
                df0, use_container_width=True,
                column_config=pct_col_cfg, key="inc_std_v1",
            )

    # ── BALANCE SHEET TAB ─────────────────────────────────────────────────────
    with tab_bal:
        adv_bal_ok = advanced_mode and not sec_failed and len(exact_bal_items) > 0

        if adv_bal_ok:
            st.markdown(
                "<div class='adv-info-box'>🔬 <b>Advanced Mode</b> — Every SEC-reported Balance "
                "Sheet line is editable. Enter a YoY growth rate (%) per projected year.</div>",
                unsafe_allow_html=True,
            )

        autopilot = st.toggle(
            "Enable Autopilot (Wall Street working-capital rules)" if advanced_mode
            else "🤖 Enable Autopilot (Wall Street working-capital rules)",
            value=not adv_bal_ok,   # default OFF in advanced mode so user can drive all rows
        )

        if autopilot:
            st.markdown(
                f"<span style='color:#1D9BF0;font-size:0.85rem;font-weight:600;'>"
                f"{'Autopilot' if advanced_mode else '🤖 Autopilot'} Active</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"- **Receivables (DSO):** {hist_dso:.1f} days\n"
                f"- **Inventory (DIO):** {hist_dio:.1f} days\n"
                f"- **Payables (DPO):** {hist_dpo:.1f} days\n"
                f"- **Cash:** {hist_cash_pct*100:.1f}% of Revenue\n"
                f"- **Debt:** Flat at ${hist_debt_last:,.1f}M"
            )
            p_ar_pct = p_inv_pct = p_ap_pct = p_cash_pct = p_debt_pct = np.zeros(forecast_years)
            edited_bal_df = pd.DataFrame()
        else:
            st.markdown(
                "<span style='color:#F87171;font-size:0.85rem;'>"
                "Autopilot Off — enter your assumptions below.</span>",
                unsafe_allow_html=True,
            )
            if adv_bal_ok:
                init = 0.0 if start_fresh else 5.0
                df0  = pd.DataFrame(
                    {c: [init] * len(exact_bal_items) for c in proj_cols},
                    index=exact_bal_items,
                )
                edited_bal_df = st.data_editor(
                    df0, use_container_width=True,
                    column_config=pct_col_cfg, key="bal_adv_v1",
                )
                # simple % drivers still needed for FCFF math
                p_ar_pct   = np.full(forecast_years, hist_ar_last   / hist_rev_last if hist_rev_last else 0.12)
                p_inv_pct  = np.full(forecast_years, hist_inv_last  / hist_rev_last if hist_rev_last else 0.10)
                p_ap_pct   = np.full(forecast_years, hist_ap_last   / hist_rev_last if hist_rev_last else 0.08)
                p_cash_pct = np.full(forecast_years, hist_cash_pct)
                p_debt_pct = np.full(forecast_years, hist_debt_pct)
            else:
                rows = ["Receivables % of Revenue (%)",
                        "Inventory % of Revenue (%)",
                        "Payables % of Revenue (%)",
                        "Cash Reserves % of Revenue (%)",
                        "Debt % of Revenue (%)"]
                vals = [_seed((hist_ar_last  / hist_rev_last) * 100 if hist_rev_last else 12.0),
                        _seed((hist_inv_last / hist_rev_last) * 100 if hist_rev_last else 10.0),
                        _seed((hist_ap_last  / hist_rev_last) * 100 if hist_rev_last else  8.0),
                        _seed(hist_cash_pct * 100),
                        _seed(hist_debt_pct * 100)]
                df0  = pd.DataFrame({c: vals for c in proj_cols}, index=rows)
                edited_bal_df = st.data_editor(
                    df0, use_container_width=True,
                    column_config=pct_col_cfg, key="bal_std_v1",
                )
                p_ar_pct   = get_driver_row(edited_bal_df, "Receivables % of Revenue (%)", forecast_years)
                p_inv_pct  = get_driver_row(edited_bal_df, "Inventory % of Revenue (%)",   forecast_years)
                p_ap_pct   = get_driver_row(edited_bal_df, "Payables % of Revenue (%)",    forecast_years)
                p_cash_pct = get_driver_row(edited_bal_df, "Cash Reserves % of Revenue (%).", forecast_years)
                p_debt_pct = get_driver_row(edited_bal_df, "Debt % of Revenue (%)",         forecast_years)
                # retry without trailing dot
                if np.all(p_cash_pct == 0):
                    p_cash_pct = get_driver_row(edited_bal_df, "Cash Reserves % of Revenue (%)", forecast_years)

    # ── CASH FLOW TAB ─────────────────────────────────────────────────────────
    with tab_cf:
        adv_cf_ok = advanced_mode and not sec_failed and len(exact_cf_items) > 0

        if adv_cf_ok:
            st.markdown(
                "<div class='adv-info-box'>🔬 <b>Advanced Mode</b> — Every SEC-reported Cash "
                "Flow Statement line is editable. Enter a YoY growth rate (%) per projected year. "
                "CapEx and D&A are automatically synced to the DCF engine.</div>",
                unsafe_allow_html=True,
            )
            init = 0.0 if start_fresh else 5.0
            df0  = pd.DataFrame(
                {c: [init] * len(exact_cf_items) for c in proj_cols},
                index=exact_cf_items,
            )
            edited_cf_df = st.data_editor(
                df0, use_container_width=True,
                column_config=pct_col_cfg, key="cf_adv_v1",
            )
        else:
            if advanced_mode and sec_failed:
                st.warning("SEC unavailable — showing simplified drivers.")
            rows = ["CapEx as % of Revenue (%)",
                    "D&A as % of Revenue (%)"]
            vals = [_seed(hist_capex_pct * 100), _seed(hist_da_pct * 100)]
            df0  = pd.DataFrame({c: vals for c in proj_cols}, index=rows)
            edited_cf_df = st.data_editor(
                df0, use_container_width=True,
                column_config=pct_col_cfg, key="cf_std_v1",
            )

    # ── Extract driver arrays from editors ─────────────────────────────────────
    adv_inc_ok = advanced_mode and not sec_failed and len(exact_inc_items) > 0
    adv_cf_ok  = advanced_mode and not sec_failed and len(exact_cf_items) > 0

    if not adv_inc_ok:
        p_rev_growth = get_driver_row(edited_inc_df, "Revenue Growth Rate (%)",            forecast_years)
        p_cogs_pct   = get_driver_row(edited_inc_df, "Cost of Revenue as % of Rev (%)",    forecast_years)
        p_opex_pct   = get_driver_row(edited_inc_df, "Operating Costs as % of Rev (%)",    forecast_years)
        p_other_pct  = get_driver_row(edited_inc_df, "Other Costs as % of Rev (%)",        forecast_years)
        p_tax_rate   = get_driver_row(edited_inc_df, "Effective Tax Rate (%)",              forecast_years)
    else:
        # Advanced: use first revenue-like row for growth; others remain as-is
        p_rev_growth = np.zeros(forecast_years)
        p_cogs_pct   = np.full(forecast_years, hist_cogs_last / hist_rev_last if hist_rev_last else 0.6)
        p_opex_pct   = np.full(forecast_years, hist_opex_last / hist_rev_last if hist_rev_last else 0.15)
        p_other_pct  = np.full(forecast_years, 0.02)
        p_tax_rate   = np.full(forecast_years, hist_tax_rate)

    if not adv_cf_ok:
        p_capex = get_driver_row(edited_cf_df, "CapEx as % of Revenue (%)", forecast_years)
        p_da    = get_driver_row(edited_cf_df, "D&A as % of Revenue (%)",   forecast_years)
    else:
        p_capex = np.full(forecast_years, hist_capex_pct)
        p_da    = np.full(forecast_years, hist_da_pct)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  CALCULATION ENGINE                                                          ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

full_timeline = hist_columns + proj_columns

inc_df_calc = pd.DataFrame(index=FULL_INC_ROWS, columns=full_timeline, dtype=object)
bal_df_calc = pd.DataFrame(index=FULL_BAL_ROWS, columns=full_timeline, dtype=object)
cf_df_calc  = pd.DataFrame(index=FULL_CF_ROWS,  columns=full_timeline, dtype=object)

# ── Populate historical periods ───────────────────────────────────────────────
for i in range(num_hist):
    c    = hist_columns[i]
    rev  = safe_get(yf_financials, ["Total Revenue", "Revenue"],          col_idx=i) / 1e6
    cogs = safe_get(yf_financials, ["Cost Of Revenue", "CostOfRevenue"],  col_idx=i) / 1e6
    opex = safe_get(yf_financials, ["Selling General Administrative",
                                    "Operating Expense"],                  col_idx=i) / 1e6
    other = 0.02 * rev
    ebit  = safe_get(yf_financials, ["Operating Income", "EBIT"],         col_idx=i) / 1e6
    tax   = safe_get(yf_financials, ["Tax Provision", "Income Tax Expense"], col_idx=i) / 1e6
    ebiat = ebit - tax
    da    = safe_get(yf_cashflow,   ["Depreciation And Amortization",
                                     "Depreciation"],                      col_idx=i) / 1e6
    capex = abs(safe_get(yf_cashflow, ["Capital Expenditure", "CapEx"],   col_idx=i)) / 1e6
    cash  = safe_get(yf_balance, ["Cash And Cash Equivalents", "Cash"],   col_idx=i) / 1e6
    debt  = safe_get(yf_balance, ["Total Debt", "Long Term Debt"],        col_idx=i) / 1e6
    if debt == 0.0:
        debt = (safe_get(yf_balance, ["Long Term Debt"],    col_idx=i) +
                safe_get(yf_balance, ["Current Debt"],       col_idx=i)) / 1e6
    ar  = safe_get(yf_balance, ["Accounts Receivable", "Receivables"],    col_idx=i) / 1e6
    inv = safe_get(yf_balance, ["Inventory", "Inventories"],              col_idx=i) / 1e6
    ap  = safe_get(yf_balance, ["Accounts Payable", "Payables"],          col_idx=i) / 1e6
    nwc = (ar + inv) - ap
    nwc_chg = 0.01 * rev
    fcff    = ebiat + da - capex - nwc_chg
    growth  = ((rev - safe_get(yf_financials, ["Total Revenue", "Revenue"],
                                col_idx=i-1) / 1e6) /
               (safe_get(yf_financials, ["Total Revenue", "Revenue"],
                          col_idx=i-1) / 1e6)) if i > 0 else np.nan
    margin = ebit / rev if rev else 0.0

    inc_df_calc.at["Revenue ($M)",          c] = rev
    inc_df_calc.at["Revenue Growth (%)",    c] = (growth * 100) if not np.isnan(growth) else ""
    inc_df_calc.at["Cost of Revenue ($M)",  c] = cogs
    inc_df_calc.at["Cost of Operations ($M)", c] = opex
    inc_df_calc.at["Other Costs ($M)",      c] = other
    inc_df_calc.at["Operating EBIT ($M)",   c] = ebit
    inc_df_calc.at["Operating Margin (%)",  c] = margin * 100
    inc_df_calc.at["Tax Provision ($M)",    c] = tax
    inc_df_calc.at["EBIAT ($M)",            c] = ebiat

    bal_df_calc.at["Cash ($M)",             c] = cash
    bal_df_calc.at["Debt ($M)",             c] = debt
    bal_df_calc.at["Receivables ($M)",      c] = ar
    bal_df_calc.at["Inventory ($M)",        c] = inv
    bal_df_calc.at["Payables ($M)",         c] = ap
    bal_df_calc.at["Net Working Capital ($M)", c] = nwc

    cf_df_calc.at["EBIAT ($M)",             c] = ebiat
    cf_df_calc.at["D&A ($M)",              c] = da
    cf_df_calc.at["CapEx ($M)",            c] = capex
    cf_df_calc.at["Change in NWC ($M)",    c] = nwc_chg
    cf_df_calc.at["Unlevered Free Cash Flow (FCFF) ($M)", c] = fcff
    cf_df_calc.at["Discount Factor",       c] = ""
    cf_df_calc.at["Present Value of FCF ($M)", c] = ""

# ── Advanced mode: raw SEC projection tables ───────────────────────────────────
raw_inc_calc = pd.DataFrame()
raw_bal_calc = pd.DataFrame()
raw_cf_calc  = pd.DataFrame()

adv_inc_ok = advanced_mode and not sec_failed and len(exact_inc_items) > 0
adv_bal_ok = advanced_mode and not sec_failed and len(exact_bal_items) > 0
adv_cf_ok  = advanced_mode and not sec_failed and len(exact_cf_items)  > 0

if adv_inc_ok or adv_bal_ok or adv_cf_ok:
    def _build_raw(key: str) -> pd.DataFrame:
        df = clean_sec_dataframe(sec_data.get(key)).copy()
        if not df.empty and "label" in df.columns:
            df = df.set_index("label")
            df = df[~df.index.duplicated(keep="first")]
        df = map_columns_to_years(df)
        for col in proj_cols:
            df[col] = np.nan
        return df

    if adv_inc_ok:
        raw_inc_calc = _build_raw("income_standard")
        for row in exact_inc_items:
            try:
                last = pd.to_numeric(raw_inc_calc.loc[row].iloc[num_hist - 1], errors="coerce")
                last = last if pd.notna(last) else 100.0
                g    = get_driver_row(edited_inc_df, row, forecast_years)
                for j, c in enumerate(proj_cols):
                    last = last * (1 + g[j])
                    raw_inc_calc.at[row, c] = last
            except Exception:
                pass

    if adv_bal_ok and not autopilot:
        raw_bal_calc = _build_raw("balance_standard")
        for row in exact_bal_items:
            try:
                last = pd.to_numeric(raw_bal_calc.loc[row].iloc[num_hist - 1], errors="coerce")
                last = last if pd.notna(last) else 100.0
                g    = get_driver_row(edited_bal_df, row, forecast_years)
                for j, c in enumerate(proj_cols):
                    last = last * (1 + g[j])
                    raw_bal_calc.at[row, c] = last
            except Exception:
                pass

    if adv_cf_ok:
        raw_cf_calc = _build_raw("cashflow_standard")
        for row in exact_cf_items:
            try:
                last = pd.to_numeric(raw_cf_calc.loc[row].iloc[num_hist - 1], errors="coerce")
                last = last if pd.notna(last) else 100.0
                g    = get_driver_row(edited_cf_df, row, forecast_years)
                for j, c in enumerate(proj_cols):
                    last = last * (1 + g[j])
                    raw_cf_calc.at[row, c] = last
            except Exception:
                pass

    # Sync key driver arrays from raw advanced tables
    current_rev_adv = inc_df_calc.at["Revenue ($M)", hist_columns[-1]]
    if adv_inc_ok and not raw_inc_calc.empty:
        p_adv_rev   = find_projected_row_values(
            raw_inc_calc, ["revenue", "net sales", "total revenue", "sales"],
            np.full(forecast_years, current_rev_adv), proj_cols,
        )
        if p_adv_rev is not None and len(p_adv_rev) == forecast_years:
            p_rev_growth[0] = (p_adv_rev[0] - current_rev_adv) / current_rev_adv if current_rev_adv else 0.0
            for j in range(1, forecast_years):
                p_rev_growth[j] = ((p_adv_rev[j] - p_adv_rev[j-1]) / p_adv_rev[j-1]
                                   if p_adv_rev[j-1] else 0.0)
            adv_cogs = find_projected_row_values(
                raw_inc_calc, ["cost of revenue", "cost of sales", "cost of goods"],
                p_adv_rev * (hist_cogs_last / hist_rev_last if hist_rev_last else 0.6), proj_cols)
            adv_opex = find_projected_row_values(
                raw_inc_calc, ["selling general", "operating expenses", "sg&a"],
                p_adv_rev * (hist_opex_last / hist_rev_last if hist_rev_last else 0.15), proj_cols)
            p_cogs_pct = adv_cogs / np.where(p_adv_rev != 0, p_adv_rev, 1)
            p_opex_pct = adv_opex / np.where(p_adv_rev != 0, p_adv_rev, 1)

    if adv_cf_ok and not raw_cf_calc.empty:
        adv_rev_ref = np.array([
            inc_df_calc.at["Revenue ($M)", hist_columns[-1]] *
            np.prod([1 + p_rev_growth[k] for k in range(j + 1)])
            for j in range(forecast_years)
        ])
        adv_capex = find_projected_row_values(
            raw_cf_calc, ["capital expenditure", "capex", "additions to property"],
            adv_rev_ref * hist_capex_pct, proj_cols)
        adv_da    = find_projected_row_values(
            raw_cf_calc, ["depreciation", "amortization", "depreciation and amortization"],
            adv_rev_ref * hist_da_pct, proj_cols)
        p_capex = adv_capex / np.where(adv_rev_ref != 0, adv_rev_ref, 1)
        p_da    = adv_da    / np.where(adv_rev_ref != 0, adv_rev_ref, 1)

# ── Populate projected periods ────────────────────────────────────────────────
current_rev = float(inc_df_calc.at["Revenue ($M)", hist_columns[-1]] or hist_rev_last)
prev_nwc    = float(bal_df_calc.at["Net Working Capital ($M)", hist_columns[-1]] or 0.0)
proj_fcf_list, disc_list, pv_list = [], [], []

for i in range(forecast_years):
    c        = proj_columns[i]
    growth   = float(p_rev_growth[i])
    cogs_pct = float(p_cogs_pct[i])
    opex_pct = float(p_opex_pct[i])
    oth_pct  = float(p_other_pct[i])
    t_rate   = float(p_tax_rate[i])
    cap_pct  = float(p_capex[i])
    da_pct   = float(p_da[i])

    rev   = current_rev * (1 + growth)
    current_rev = rev
    cogs  = rev * cogs_pct
    opex  = rev * opex_pct
    other = rev * oth_pct
    ebit  = rev - cogs - opex - other
    tax   = ebit * t_rate
    ebiat = ebit - tax
    da    = rev * da_pct
    capex = rev * cap_pct

    if autopilot:
        ar   = (hist_dso * rev) / 365
        inv  = (hist_dio * cogs) / 365
        ap   = (hist_dpo * cogs) / 365
        cash = hist_cash_pct * rev
        debt = hist_debt_last
    else:
        ar   = rev * float(p_ar_pct[i])
        inv  = rev * float(p_inv_pct[i])
        ap   = rev * float(p_ap_pct[i])
        cash = rev * float(p_cash_pct[i])
        debt = rev * float(p_debt_pct[i])

    nwc     = (ar + inv) - ap
    nwc_chg = nwc - prev_nwc
    prev_nwc = nwc
    fcff    = ebiat + da - capex - nwc_chg
    df_     = 1 / ((1 + ui_wacc) ** (i + 1))
    pv_fcff = fcff * df_

    proj_fcf_list.append(fcff)
    disc_list.append(df_)
    pv_list.append(pv_fcff)

    inc_df_calc.at["Revenue ($M)",           c] = rev
    inc_df_calc.at["Revenue Growth (%)",     c] = growth * 100
    inc_df_calc.at["Cost of Revenue ($M)",   c] = cogs
    inc_df_calc.at["Cost of Operations ($M)", c] = opex
    inc_df_calc.at["Other Costs ($M)",       c] = other
    inc_df_calc.at["Operating EBIT ($M)",    c] = ebit
    inc_df_calc.at["Operating Margin (%)",   c] = (ebit / rev * 100) if rev else 0.0
    inc_df_calc.at["Tax Provision ($M)",     c] = tax
    inc_df_calc.at["EBIAT ($M)",             c] = ebiat

    bal_df_calc.at["Cash ($M)",              c] = cash
    bal_df_calc.at["Debt ($M)",              c] = debt
    bal_df_calc.at["Receivables ($M)",       c] = ar
    bal_df_calc.at["Inventory ($M)",         c] = inv
    bal_df_calc.at["Payables ($M)",          c] = ap
    bal_df_calc.at["Net Working Capital ($M)", c] = nwc

    cf_df_calc.at["EBIAT ($M)",              c] = ebiat
    cf_df_calc.at["D&A ($M)",               c] = da
    cf_df_calc.at["CapEx ($M)",             c] = capex
    cf_df_calc.at["Change in NWC ($M)",     c] = nwc_chg
    cf_df_calc.at["Unlevered Free Cash Flow (FCFF) ($M)", c] = fcff
    cf_df_calc.at["Discount Factor",        c] = df_
    cf_df_calc.at["Present Value of FCF ($M)", c] = pv_fcff

# ── DCF valuation ─────────────────────────────────────────────────────────────
sum_pv      = sum(pv_list)
tv          = ((proj_fcf_list[-1] * (1 + perpetual_growth)) /
               (ui_wacc - perpetual_growth)) if ui_wacc > perpetual_growth else 0.0
pv_tv       = tv * disc_list[-1]
ev          = sum_pv + pv_tv
total_debt_m = total_debt / 1e6
cash_m       = cash_and_equiv / 1e6
shares_m     = shares_outstanding / 1e6
eq_val       = ev - total_debt_m + cash_m
impl_price   = eq_val / shares_m if shares_m > 0 else 0.0

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  RIGHT COLUMN — Live Statement Output                                        ║
# ╚══════════════════════════════════════════════════════════════════════════════╝

JARGON_INC = {
    "Revenue ($M)":             "Total Sales ($M)",
    "Revenue Growth (%)":       "Sales Growth Rate (%)",
    "Cost of Revenue ($M)":     "Cost of Production ($M)",
    "Cost of Operations ($M)":  "Operating Expenses ($M)",
    "Other Costs ($M)":         "Other Costs ($M)",
    "Operating EBIT ($M)":      "Core Operating Profit ($M)",
    "Operating Margin (%)":     "Profit Margin on Sales (%)",
    "Tax Provision ($M)":       "Taxes Paid ($M)",
    "EBIAT ($M)":               "Net Earnings After Tax ($M)",
}
JARGON_BAL = {
    "Cash ($M)":                "Bank Cash ($M)",
    "Debt ($M)":                "Total Loans ($M)",
    "Receivables ($M)":         "Unpaid Customer Invoices ($M)",
    "Inventory ($M)":           "Unsold Goods ($M)",
    "Payables ($M)":            "Unpaid Supplier Bills ($M)",
    "Net Working Capital ($M)": "Operational Capital ($M)",
}
JARGON_CF = {
    "EBIAT ($M)":               "Net Earnings ($M)",
    "D&A ($M)":                 "Depreciation Recovery ($M)",
    "CapEx ($M)":               "Equipment Investment ($M)",
    "Change in NWC ($M)":       "Change in Working Capital ($M)",
    "Unlevered Free Cash Flow (FCFF) ($M)": "Free Cash Flow for Investors ($M)",
    "Discount Factor":          "Safety Discount Multiplier",
    "Present Value of FCF ($M)": "Present Value of Cash ($M)",
}

with col_right:
    st.markdown("<h3 style='color:#1D9BF0;margin-top:0;'>Live Statement Output</h3>",
                unsafe_allow_html=True)
    st.markdown(
        "Projected years shown in <span style='color:#93C5FD;'>blue</span>. "
        "Scroll right for historical context.",
        unsafe_allow_html=True,
    )

    stmt_sel = st.radio("Select Statement:", ["Income Statement",
                                              "Balance Sheet",
                                              "Cash Flow Statement"],
                         horizontal=True)

    adv_all_ok = advanced_mode and not sec_failed

    if adv_all_ok and stmt_sel == "Income Statement" and not raw_inc_calc.empty:
        stmt_raw = raw_inc_calc.copy()
    elif adv_all_ok and stmt_sel == "Balance Sheet" and not raw_bal_calc.empty:
        stmt_raw = raw_bal_calc.copy()
    elif adv_all_ok and stmt_sel == "Cash Flow Statement" and not raw_cf_calc.empty:
        stmt_raw = raw_cf_calc.copy()
    else:
        if stmt_sel == "Income Statement":
            stmt_raw = inc_df_calc.copy()
            if jargon_free:
                stmt_raw.index = [JARGON_INC.get(r, r) for r in stmt_raw.index]
        elif stmt_sel == "Balance Sheet":
            stmt_raw = bal_df_calc.copy()
            if jargon_free:
                stmt_raw.index = [JARGON_BAL.get(r, r) for r in stmt_raw.index]
        else:
            stmt_raw = cf_df_calc.copy()
            if jargon_free:
                stmt_raw.index = [JARGON_CF.get(r, r) for r in stmt_raw.index]

    valid_cols   = [c for c in (hist_columns + proj_columns) if c in stmt_raw.columns]
    stmt_display = stmt_raw[valid_cols]
    stmt_fmt     = format_statement_df(stmt_display)
    st.markdown(generate_luxury_table(stmt_fmt), unsafe_allow_html=True)

# ── Annotations ledger ─────────────────────────────────────────────────────────
if st.session_state["projection_notes"]:
    st.markdown("<hr style='border-color:#2F3336;margin:30px 0;' />",
                unsafe_allow_html=True)
    st.markdown("<h4 style='color:#1D9BF0;'>Active Annotations Ledger</h4>",
                unsafe_allow_html=True)
    for entry in st.session_state["projection_notes"]:
        st.markdown(f"""
        <div style="background:#16181C;border:1px solid #2F3336;border-left:4px solid #1D9BF0;
            padding:15px;border-radius:8px;margin-bottom:12px;">
            <span style="color:#1D9BF0;font-weight:700;font-size:0.85rem;">
                {entry['statement']} — {entry['item']} ({entry['period']})</span><br/>
            <p style="color:#E7E9EA;margin:6px 0;font-size:0.95rem;">"{entry['note']}"</p>
            <span style="color:#71767B;font-size:0.75rem;font-style:italic;">
                Source: {entry['citation']}</span>
        </div>
        """, unsafe_allow_html=True)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  LOWER SECTION — Forecast Timeline + Valuation                               ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
st.markdown("<hr style='border-color:#2F3336;margin:30px 0;' />",
            unsafe_allow_html=True)
st.subheader(lbl_timeline)

col_ll, col_lr = st.columns([1, 1.2], gap="large")

with col_ll:
    combined = pd.concat([inc_df_calc, bal_df_calc, cf_df_calc])
    combined = combined[~combined.index.duplicated(keep="first")]
    combined = combined[[c for c in full_timeline if c in combined.columns]]

    if jargon_free:
        jargon_all = {**JARGON_INC, **JARGON_BAL, **JARGON_CF}
        combined.index = [jargon_all.get(r, r) for r in combined.index]

    st.markdown("**Complete 3-Statement Forecast Timeline**")
    st.markdown(generate_luxury_table(format_statement_df(combined)),
                unsafe_allow_html=True)

with col_lr:
    st.markdown("**Valuation Summary**")
    r1, r2 = st.columns(2)
    with r1:
        lbl = "Calculated Fair Price" if jargon_free else "Implied Target Price"
        st.markdown(render_luxury_card(lbl, f"${impl_price:,.2f}", is_accent=True),
                    unsafe_allow_html=True)
    with r2:
        lbl = "Market Price" if jargon_free else "Current Price"
        st.markdown(render_luxury_card(lbl, f"${current_price:,.2f}"),
                    unsafe_allow_html=True)
    r3, r4 = st.columns(2)
    with r3:
        lbl = "Business Worth" if jargon_free else "Enterprise Value"
        st.markdown(render_luxury_card(lbl, f"${ev:,.1f}M"), unsafe_allow_html=True)
    with r4:
        lbl = "Discount Rate" if jargon_free else "WACC"
        st.markdown(render_luxury_card(lbl, f"{ui_wacc*100:.2f}%"), unsafe_allow_html=True)

    lbl_mkt = "Market Price" if jargon_free else "Current Market Price"
    lbl_dcf = "Fair Value"   if jargon_free else "Implied DCF Value"
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=[lbl_mkt, lbl_dcf],
        y=[current_price, impl_price],
        marker_color=["#4B5563", "#1D9BF0"],
        width=[0.35, 0.35],
    ))
    fig.update_layout(
        paper_bgcolor="#000000", plot_bgcolor="#0B0C0E",
        font_color="#E7E9EA",
        xaxis=dict(showgrid=False, linecolor="#2F3336"),
        yaxis=dict(showgrid=True, gridcolor="#2F3336", linecolor="#2F3336"),
        margin=dict(l=20, r=20, t=20, b=20), height=300,
    )
    st.plotly_chart(fig, use_container_width=True)

# ╔══════════════════════════════════════════════════════════════════════════════╗
# ║  VERIFICATION WORKSHEETS (Raw SEC / Yahoo Finance data)                      ║
# ╚══════════════════════════════════════════════════════════════════════════════╝
st.markdown("<hr style='border-color:#2F3336;margin:30px 0;' />",
            unsafe_allow_html=True)
st.subheader("Verification Worksheets")

if jargon_free:
    st.markdown(
        "These show the raw source data from SEC or Yahoo Finance used for historical figures:\n"
        "- **Income Statement** — the scorecard showing revenue minus costs\n"
        "- **Balance Sheet** — what the company owns vs. what it owes\n"
        "- **Cash Flow Statement** — actual cash in and out of the business"
    )

if not sec_failed:
    view_mode = st.selectbox("SEC Report Detail Level", ["standard", "summary"])
    t_is, t_bs, t_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow Statement"])
    with t_is:
        st.dataframe(clean_sec_dataframe(sec_data.get(f"income_{view_mode}")),
                     use_container_width=True)
    with t_bs:
        st.dataframe(clean_sec_dataframe(sec_data.get(f"balance_{view_mode}")),
                     use_container_width=True)
    with t_cf:
        st.dataframe(clean_sec_dataframe(sec_data.get(f"cashflow_{view_mode}")),
                     use_container_width=True)
else:
    t_is, t_bs, t_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
    with t_is:
        st.dataframe(yf_financials, use_container_width=True)
    with t_bs:
        st.dataframe(yf_balance, use_container_width=True)
    with t_cf:
        st.dataframe(yf_cashflow, use_container_width=True)
