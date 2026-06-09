import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import requests
import plotly.graph_objects as go
from edgar import Company, set_identity

# Set page layout
st.set_page_config(page_title="Executive DCF Spreadsheet Model", layout="wide")

# --- QUIET LUXURY DARK THEMING (Global CSS Injections) ---
st.markdown("""
<style>
    /* Main Background and Text Defaults */
    .stApp {
        background-color: #090D16 !important;
        color: #E5E7EB !important;
    }
    
    /* Left-hand Sidebar Navigation Panel styling */
    section[data-testid="stSidebar"] {
        background-color: #0B0F19 !important;
        border-right: 1px solid #1F2937 !important;
    }
    
    /* Input field borders and background fills */
    input, select, textarea, div[role="button"], div[data-baseweb="input"] {
        background-color: #111827 !important;
        color: #F3F4F6 !important;
        border: 1px solid #374151 !important;
        border-radius: 6px !important;
    }
    
    /* Elegant Tab styling with Champagne Gold Accents */
    button[data-baseweb="tab"] {
        color: #9CA3AF !important;
        font-weight: 500 !important;
        background: transparent !important;
        border: none !important;
    }
    button[data-baseweb="tab"][aria-selected="true"] {
        color: #C5A880 !important;
        border-bottom: 2px solid #C5A880 !important;
        font-weight: 600 !important;
    }
    
    /* Custom Styling for interactive buttons (Action state) */
    div.stButton > button:first-child {
        background-color: #C5A880 !important;
        color: #090D16 !important;
        border: 1px solid #C5A880 !important;
        border-radius: 6px !important;
        font-weight: 600 !important;
        padding: 0.5rem 1.5rem !important;
        letter-spacing: 0.05em !important;
        transition: all 0.3s ease-in-out !important;
    }
    div.stButton > button:first-child:hover {
        background-color: #E2D1B9 !important;
        border-color: #E2D1B9 !important;
        box-shadow: 0 0 15px rgba(197, 168, 128, 0.4) !important;
        transform: translateY(-1px);
    }
    
    /* Headers & Typography */
    h1, h2, h3 {
        font-family: 'Playfair Display', Georgia, serif !important;
        font-weight: 500 !important;
        color: #F3F4F6 !important;
    }
    
    /* Collapsible Expander customization */
    div[data-testid="stExpander"] {
        background-color: #0B0F19 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 8px !important;
    }
</style>
""", unsafe_allow_html=True)

# Helper: Build premium luxury card metrics
def render_luxury_card(label, value, is_accent=False):
    border_color = "#C5A880" if is_accent else "#1F2937"
    bg_color = "#111827" if is_accent else "#0B0F19"
    text_color = "#C5A880" if is_accent else "#F3F4F6"
    return f"""
    <div style="
        background-color: {bg_color}; 
        border: 1px solid {border_color}; 
        border-top: 3px solid {border_color}; 
        padding: 15px; 
        border-radius: 8px; 
        text-align: center;
        margin-bottom: 12px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    ">
        <span style="color: #9CA3AF; font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600;">{label}</span>
        <h2 style="color: {text_color}; font-size: 1.5rem; margin: 5px 0 0 0; font-family: 'Playfair Display', Georgia, serif; font-weight: 500;">{value}</h2>
    </div>
    """

# Helper: Exquisite custom HTML financial statement renderer
def generate_luxury_table(df):
    html = "<div class='table-wrapper' style='overflow-x: auto; margin: 15px 0; border-radius: 8px; border: 1px solid #1F2937;'>"
    html += "<table style='width: 100%; border-collapse: collapse; background-color: #0B0F19; color: #E5E7EB;'>"
    
    # Header Row
    html += "<tr style='border-bottom: 2px solid #C5A880;'>"
    html += "<th style='padding: 10px 14px; text-align: left; background-color: #111827; color: #C5A880; font-family: \"Segoe UI\", sans-serif; font-weight: 600; min-width: 200px;'>Financial Item</th>"
    for col in df.columns:
        html += f"<th style='padding: 10px 14px; text-align: right; background-color: #111827; color: #F3F4F6; font-family: \"Segoe UI\", sans-serif; font-weight: 500;'>{col}</th>"
    html += "</tr>"
    
    # Body Rows
    for row_idx, row_name in enumerate(df.index):
        is_key_row = any(x in row_name for x in ["Sales", "Revenue", "Profit", "EBIT", "Earnings", "FCF", "Cash for Investors", "Cash ($M)", "Debt ($M)"])
        is_total_row = "Value of Future Cash ($M)" in row_name or "Present Value of FCF" in row_name
        
        row_style = ""
        if is_total_row:
            row_style = "style='background-color: #1F2937; font-weight: bold; border-top: 1px solid #C5A880; border-bottom: 3px double #C5A880;'"
        elif is_key_row:
            row_style = "style='font-weight: 600; color: #FFFFFF; background-color: #111827;'"
        elif row_idx % 2 == 0:
            row_style = "style='background-color: #0E1321;'"
        else:
            row_style = "style='background-color: #090D16;'"
            
        html += f"<tr {row_style}>"
        # Label Cell
        label_style = "padding: 8px 14px; text-align: left; border-right: 1px solid #1F2937;"
        if is_total_row:
            label_style += " color: #C5A880;"
        html += f"<td style='{label_style}'>{row_name}</td>"
        
        # Value Cells
        for col in df.columns:
            val = df.at[row_name, col]
            cell_style = "padding: 8px 14px; text-align: right; font-family: 'Courier New', monospace;"
            html += f"<td style='{cell_style}'>{val}</td>"
        html += "</tr>"
        
    html += "</table></div>"
    return html

# Helper: Robust SEC DataFrame cleaner
def clean_sec_dataframe(df):
    if df is None:
        return pd.DataFrame()
    if not isinstance(df, pd.DataFrame):
        return pd.DataFrame()
    if df.empty:
        return df
    cols_to_drop = ['level', 'abstract', 'parent_concept', 'parent_abstract_concept', 'concept']
    existing_drops = [c for c in cols_to_drop if c in df.columns]
    try:
        return df.drop(columns=existing_drops)
    except Exception:
        return df

# Helper for standard financial data extraction
def safe_get(df, keys, col_idx=0, default=0.0):
    if df is None or df.empty:
        return default
    df_normalized = df.copy()
    df_normalized.index = df_normalized.index.astype(str).str.lower().str.strip()
    for key in keys:
        key_norm = key.lower().strip()
        if key_norm in df_normalized.index:
            row = df_normalized.loc[key_norm]
            if isinstance(row, pd.Series):
                if col_idx < len(row):
                    val = row.iloc[col_idx]
                else:
                    val = row.iloc[-1]
            else:
                val = row
            if pd.notna(val):
                return float(val)
    return default

# --- LIVE CNBC TREASURY RATE INGESTION ---
@st.cache_data(ttl=1800)
def fetch_live_us10y():
    url = "https://quote.cnbc.com/quote-html-webservice/quote.htm"
    params = {
        "noform": "1",
        "partnerId": "2",
        "fund": "1",
        "exthrs": "0",
        "output": "json",
        "symbolType": "issue",
        "symbols": "US10Y",
        "requestMethod": "extended",
    }
    try:
        res = requests.get(url, params=params, timeout=5)
        data = res.json()
        quote = data["ExtendedQuoteResult"]["ExtendedQuote"][0]["QuickQuote"]
        return float(quote["last"]) / 100.0  # e.g., 0.0425 for 4.25%
    except Exception:
        return 0.0425 # Resilient high-end fallback rate

# --- CONTROLS SECTION ---
st.sidebar.markdown("<h2 style='color: #C5A880; font-size: 1.4rem; border-bottom: 1px solid #374151; padding-bottom: 8px; margin-bottom: 15px;'>Executive Control</h2>", unsafe_allow_html=True)
sec_email = st.sidebar.text_input(
    "SEC User-Agent Email",
    value="analyst@independentresearch.com"
)

if sec_email:
    try:
        set_identity(sec_email)
    except Exception as e:
        st.sidebar.error(f"SEC identity configuration failed: {e}")

ticker_symbol = st.sidebar.text_input("Ticker Symbol", value="AAPL").upper().strip()
forecast_years = st.sidebar.slider("Forecast Horizon (Years)", min_value=1, max_value=15, value=5)

st.sidebar.markdown("<h3 style='color: #C5A880; font-size: 1.15rem;'>Global Assumptions</h3>", unsafe_allow_html=True)

# Fetch live CNBC Risk-free rate
live_rf = fetch_live_us10y()
st.sidebar.metric("Live US 10Y Yield (Risk-Free Rate) [CNBC]", f"{live_rf * 100:.3f}%")

erp = st.sidebar.number_input("Equity Risk Premium (%)", min_value=0.0, max_value=20.0, value=5.5, step=0.1) / 100
perpetual_growth = st.sidebar.number_input("Perpetual Growth Rate Forever (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1) / 100

# Cache configurations
@st.cache_data(show_spinner="Accessing SEC EDGAR database...", ttl=3600)
def load_sec_data(ticker_str, email_str):
    try:
        set_identity(email_str)
        company = Company(ticker_str)
        financials = company.get_financials()
        return {
            "income_standard": financials.income_statement().to_dataframe(view="standard"),
            "income_summary": financials.income_statement().to_dataframe(view="summary"),
            "balance_standard": financials.balance_sheet().to_dataframe(view="standard"),
            "balance_summary": financials.balance_sheet().to_dataframe(view="summary"),
            "cashflow_standard": financials.cashflow_statement().to_dataframe(view="standard"),
            "cashflow_summary": financials.cashflow_statement().to_dataframe(view="summary"),
            "company_name": str(company.name),
            "cik": str(company.cik),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(show_spinner="Evaluating normalized market metrics...", ttl=3600)
def load_market_vars(ticker_str):
    try:
        ticker = yf.Ticker(ticker_str)
        info = dict(ticker.info)
        
        if not info or 'currentPrice' not in info:
            raise ValueError("Yahoo Finance returned an incomplete info object.")
            
        financials = ticker.financials.copy()
        if financials.empty:
            raise ValueError("Financials data array empty.")
            
        balance_sheet = ticker.balance_sheet.copy()
        cashflow = ticker.cashflow.copy()
        
        financials = financials.reindex(sorted(financials.columns), axis=1)
        balance_sheet = balance_sheet.reindex(sorted(balance_sheet.columns), axis=1)
        cashflow = cashflow.reindex(sorted(cashflow.columns), axis=1)
        
        return info, financials, balance_sheet, cashflow, False
    except Exception as e:
        info, financials, balance, cashflow = get_mock_market_vars(ticker_str)
        return info, financials, balance, cashflow, True

if ticker_symbol:
    sec_data = load_sec_data(ticker_symbol, sec_email)
    yf_info, yf_financials, yf_balance, yf_cashflow, fallback_active = load_market_vars(ticker_symbol)
    
    if not sec_data:
        sec_failed = True
    else:
        sec_failed = "error" in sec_data and sec_data["error"] is not None
        
    if sec_failed:
        company_name = yf_info.get('longName', ticker_symbol)
        cik = "N/A"
    else:
        company_name = sec_data["company_name"]
        cik = sec_data["cik"]
        
    current_price = yf_info.get('currentPrice', 0.0)
    shares_outstanding = yf_info.get('sharesOutstanding', 1.0)
    beta = yf_info.get('beta', 1.0)
    
    # Absolute values fetch from last year
    cash_and_equiv = safe_get(yf_balance, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash'], col_idx=-1)
    total_debt = safe_get(yf_balance, ['Total Debt', 'Long Term Debt', 'LongTermDebt'], col_idx=-1)
    if total_debt == 0.0:
        total_debt = safe_get(yf_balance, ['Long Term Debt'], col_idx=-1) + safe_get(yf_balance, ['Current Debt', 'Short Long Term Debt'], col_idx=-1)
    net_debt = max(0.0, total_debt - cash_and_equiv)
    
    latest_revenue = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=-1)
    latest_ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'], col_idx=-1)
    latest_interest = safe_get(yf_financials, ['Interest Expense'], col_idx=-1)
    latest_tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'], col_idx=-1)
    latest_ebt = safe_get(yf_financials, ['Pretax Income', 'Income Before Tax'], col_idx=-1)
    latest_capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx'], col_idx=-1))
    latest_da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'], col_idx=-1)
    
    # Standard baseline values in Millions
    hist_rev_last = latest_revenue / 1e6
    hist_cogs_last = (safe_get(yf_financials, ['Cost of Revenue', 'CostOfRevenue'], col_idx=-1) / 1e6) or (0.60 * hist_rev_last)
    hist_opex_last = (safe_get(yf_financials, ['Selling General Administrative', 'Operating Expense'], col_idx=-1) / 1e6) or (0.15 * hist_rev_last)
    hist_other_last = 0.02 * hist_rev_last
    
    hist_ar_last = (safe_get(yf_balance, ['Accounts Receivable', 'Receivables'], col_idx=-1) / 1e6) or (0.12 * hist_rev_last)
    hist_inv_last = (safe_get(yf_balance, ['Inventory', 'Inventories'], col_idx=-1) / 1e6) or (0.10 * hist_rev_last)
    hist_ap_last = (safe_get(yf_balance, ['Accounts Payable', 'Payables'], col_idx=-1) / 1e6) or (0.08 * hist_rev_last)
    hist_cash_last = cash_and_equiv / 1e6
    hist_debt_last = total_debt / 1e6

    # Calculate Days Sales Outstanding (DSO), Days Inventory Outstanding (DIO), Days Payable Outstanding (DPO) (Wall Street Prep Rules)
    hist_dso = (hist_ar_last * 365) / hist_rev_last if hist_rev_last > 0 else 45
    hist_dio = (hist_inv_last * 365) / hist_cogs_last if hist_cogs_last > 0 else 45
    hist_dpo = (hist_ap_last * 365) / hist_cogs_last if hist_cogs_last > 0 else 45
    hist_cash_pct = hist_cash_last / hist_rev_last if hist_rev_last > 0 else 0.10
    hist_debt_pct = hist_debt_last / hist_rev_last if hist_rev_last > 0 else 0.15
    
    hist_rev_growth = 0.08
    if yf_financials is not None and yf_financials.shape[1] > 1:
        try:
            rev_vals = yf_financials.loc['Total Revenue'].values
            hist_rev_growth = (rev_vals[-1] / rev_vals[-2]) - 1
        except:
            pass
            
    hist_tax_rate = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
    hist_capex_pct = latest_capex / latest_revenue if latest_revenue else 0.04
    hist_da_pct = latest_da / latest_revenue if latest_revenue else 0.04

    # WACC calculations
    cost_of_equity = live_rf + (beta * erp)
    implied_interest_rate = 0.05
    if total_debt > 0 and latest_interest > 0:
        implied_interest_rate = min(latest_interest / total_debt, 0.15)
        
    market_cap = yf_info.get('marketCap', shares_outstanding * current_price)
    total_val = market_cap + total_debt
    weight_equity = market_cap / total_val if total_val > 0 else 1.0
    weight_debt = total_debt / total_val if total_val > 0 else 0.0
    
    st.sidebar.markdown("<h3 style='color: #C5A880; font-size: 1.15rem;'>WACC Matrix</h3>", unsafe_allow_html=True)
    ui_cost_equity = st.sidebar.number_input("Required Return on Equity (%)", value=float(cost_of_equity*100), step=0.1) / 100
    ui_cost_debt = st.sidebar.number_input("Pre-Tax Cost of Loans (%)", value=float(implied_interest_rate*100), step=0.1) / 100
    ui_wacc = (weight_equity * ui_cost_equity) + (weight_debt * ui_cost_debt * (1 - hist_tax_rate))
    st.sidebar.metric("WACC Discount Rate", f"{ui_wacc * 100:.2f}%")

    # --- MAIN WORKSPACE ---
    st.markdown(f"<h1 style='font-size: 2.1rem; margin-bottom: 2px;'>{company_name}</h1>", unsafe_allow_html=True)
    st.markdown(f"<span style='color: #9CA3AF; font-size: 0.9rem; letter-spacing: 0.05em; text-transform: uppercase;'>CIK: {cik} | Executive Investment Suite</span>", unsafe_allow_html=True)
    
    if fallback_active:
        st.warning("Yahoo Finance is currently rate-limiting host cloud requests. The system has automatically loaded baseline parameters.")
        
    st.markdown("<div style='margin-top: 15px;'></div>", unsafe_allow_html=True)

    # --- PLAIN ENGLISH TRANSLATION MODE TRIGGER ---
    jargon_free = st.toggle("✨ Translate Complex Jargon to Plain English", value=True)
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

    # --- TWO-COLUMN WORKSPACE (Left: Projections Setup | Right: Real-time Output & Valuation) ---
    col_left, col_right = st.columns([1, 1.2], gap="large")

    # --- LEFT COLUMN: MODEL PROJECTIONS BUILDER ---
    with col_left:
        st.markdown("<h3 style='color: #C5A880; margin-top:0;'>Projections Control Center</h3>", unsafe_allow_html=True)
        st.markdown("Modify the projected variables below. The financial timeline and target price on the right will react instantly.")
        
        proj_cols = [f"Year {i} (P)" for i in range(1, forecast_years + 1)]
        
        tab_inc, tab_bal, tab_cf = st.tabs(["📊 Income Statement", "🏛️ Balance Sheet", "💸 Cash Flow Statement"])
        
        with tab_inc:
            st.markdown("**Income Statement Metric Drivers**")
            default_inc_dict = {
                col_lbl: [
                    hist_rev_growth * 100, 
                    (hist_cogs_last / hist_rev_last) * 100, 
                    (hist_opex_last / hist_rev_last) * 100, 
                    (hist_other_last / hist_rev_last) * 100, 
                    hist_tax_rate * 100
                ]
                for col_lbl in proj_cols
            }
            inc_driver_rows = [
                "Revenue Growth Rate (%)",
                "Cost of Revenue as % of Rev (%)",
                "Operating Costs as % of Rev (%)",
                "Other Costs as % of Rev (%)",
                "Effective Tax Rate (%)"
            ]
            inc_drivers_df = pd.DataFrame(default_inc_dict, index=inc_driver_rows)
            edited_inc_df = st.data_editor(inc_drivers_df, use_container_width=True, key="inc_editor_v2")
            
        with tab_bal:
            st.markdown("**Balance Sheet Metric Drivers**")
            
            # Autopilot feature trigger
            autopilot_on = st.toggle("🤖 Enable Balance Sheet Autopilot (Wall Street Prep Rules)", value=True, 
                                     help="Automatically projects Cash, Receivables, Payables, and Inventory using historical Days Sales Outstanding (DSO), Days Inventory Outstanding (DIO), and Days Payable Outstanding (DPO).")
            
            if autopilot_on:
                st.markdown("<span style='color: #C5A880; font-size: 0.85rem; font-weight:600;'>Autopilot Active (Wall Street Prep Rules In Effect)</span>", unsafe_allow_html=True)
                st.markdown(f"""
                *   **Receivables (DSO)**: {hist_dso:.1f} days (Accounts Receivable is projected based on Revenue) [2]
                *   **Inventory (DIO)**: {hist_dio:.1f} days (Inventory is projected based on Cost of Goods Sold) [2]
                *   **Payables (DPO)**: {hist_dpo:.1f} days (Accounts Payable is projected based on Cost of Goods Sold) [2]
                *   **Cash Reserves**: {hist_cash_pct*100:.1f}% of Sales
                *   **Debt Reserve**: Projected flat at ${hist_debt_last:.1f}M
                """)
                # Return dummy/inactive editors
                p_ar_pct = np.zeros(forecast_years)
                p_inv_pct = np.zeros(forecast_years)
                p_ap_pct = np.zeros(forecast_years)
                p_cash_pct = np.zeros(forecast_years)
                p_debt_pct = np.zeros(forecast_years)
            else:
                st.markdown("<span style='color: #F87171; font-size: 0.85rem;'>Autopilot Offline. Modify balance sheet ratios below:</span>", unsafe_allow_html=True)
                default_bal_dict = {
                    col_lbl: [
                        (hist_ar_last / hist_rev_last) * 100,
                        (hist_inv_last / hist_rev_last) * 100,
                        (hist_ap_last / hist_rev_last) * 100,
                        hist_cash_pct * 100,
                        hist_debt_pct * 100
                    ]
                    for col_lbl in proj_cols
                }
                bal_driver_rows = [
                    "Receivables % of Revenue (%)",
                    "Inventory % of Revenue (%)",
                    "Payables % of Revenue (%)",
                    "Cash Reserves % of Revenue (%)",
                    "Debt % of Revenue (%)"
                ]
                bal_drivers_df = pd.DataFrame(default_bal_dict, index=bal_driver_rows)
                edited_bal_df = st.data_editor(bal_drivers_df, use_container_width=True, key="bal_editor_v2")
                
                # Extract user input manual percentages
                def get_driver_row(df, row_name, num_years):
                    try:
                        return np.array([float(x) for x in df.loc[row_name].values]) / 100.0
                    except Exception:
                        return np.zeros(num_years)
                
                p_ar_pct = get_driver_row(edited_bal_df, "Receivables % of Revenue (%)", forecast_years)
                p_inv_pct = get_driver_row(edited_bal_df, "Inventory % of Revenue (%)", forecast_years)
                p_ap_pct = get_driver_row(edited_bal_df, "Payables % of Revenue (%)", forecast_years)
                p_cash_pct = get_driver_row(edited_bal_df, "Cash Reserves % of Revenue (%)", forecast_years)
                p_debt_pct = get_driver_row(edited_bal_df, "Debt % of Revenue (%)", forecast_years)
            
        with tab_cf:
            st.markdown("**Cash Flow Statement Metric Drivers**")
            default_cf_dict = {
                col_lbl: [hist_capex_pct * 100, hist_da_pct * 100]
                for col_lbl in proj_cols
            }
            cf_driver_rows = [
                "CapEx as % of Revenue (%)",
                "D&A as % of Revenue (%)"
            ]
            cf_drivers_df = pd.DataFrame(default_cf_dict, index=cf_driver_rows)
            edited_cf_df = st.data_editor(cf_drivers_df, use_container_width=True, key="cf_editor_v2")

        # Read edited metrics safely with type-safety checks
        def get_driver_row(df, row_name, num_years):
            try:
                return np.array([float(x) for x in df.loc[row_name].values]) / 100.0
            except Exception:
                return np.zeros(num_years)

        p_rev_growth = get_driver_row(edited_inc_df, "Revenue Growth Rate (%)", forecast_years)
        p_cogs_pct = get_driver_row(edited_inc_df, "Cost of Revenue as % of Rev (%)", forecast_years)
        p_opex_pct = get_driver_row(edited_inc_df, "Operating Costs as % of Rev (%)", forecast_years)
        p_other_pct = get_driver_row(edited_inc_df, "Other Costs as % of Rev (%)", forecast_years)
        p_tax_rate = get_driver_row(edited_inc_df, "Effective Tax Rate (%)", forecast_years)
        
        p_capex = get_driver_row(edited_cf_df, "CapEx as % of Revenue (%)", forecast_years)
        p_da = get_driver_row(edited_cf_df, "D&A as % of Revenue (%)", forecast_years)

    # --- RIGHT COLUMN: FORECAST TIMELINE & VALUATION ---
    with col_right:
        # --- MODEL GENERATION PIPELINE ---
        hist_columns = [str(col.year) if hasattr(col, 'year') else str(col) for col in yf_financials.columns]
        proj_columns = [f"{int(hist_columns[-1]) + i} (P)" for i in range(1, forecast_years + 1)]
        all_timeline_columns = hist_columns + proj_columns
        
        timeline_rows = [
            "Revenue ($M)",
            "Revenue Growth (%)",
            "Cost of Revenue ($M)",
            "Cost of Operations ($M)",
            "Other Costs ($M)",
            "Operating EBIT ($M)",
            "Operating Margin (%)",
            "Tax Provision ($M)",
            "EBIAT ($M)",
            "D&A ($M)",
            "CapEx ($M)",
            "Cash ($M)",
            "Debt ($M)",
            "Receivables ($M)",
            "Inventory ($M)",
            "Payables ($M)",
            "Net Working Capital ($M)",
            "Change in NWC ($M)",
            "Unlevered Free Cash Flow (FCFF) ($M)",
            "Discount Factor",
            "Present Value of FCF ($M)"
        ]
        
        model_df = pd.DataFrame(index=timeline_rows, columns=all_timeline_columns)

        # 1. Populate historical metrics
        num_hist_periods = len(hist_columns)
        for i in range(num_hist_periods):
            col_lbl = hist_columns[i]
            rev = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=i) / 1e6
            cogs = safe_get(yf_financials, ['Cost Of Revenue', 'CostOfRevenue'], col_idx=i) / 1e6
            opex = safe_get(yf_financials, ['Selling General Administrative', 'Operating Expense'], col_idx=i) / 1e6
            other = 0.02 * rev
            ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'], col_idx=i) / 1e6
            tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'], col_idx=i) / 1e6
            ebiat = ebit - tax
            da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'], col_idx=i) / 1e6
            capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx'], col_idx=i)) / 1e6
            
            # Balance sheet metrics
            cash = safe_get(yf_balance, ['Cash And Cash Equivalents', 'Cash'], col_idx=i) / 1e6
            debt = safe_get(yf_balance, ['Total Debt', 'Long Term Debt'], col_idx=i) / 1e6
            if debt == 0.0:
                debt = (safe_get(yf_balance, ['Long Term Debt'], col_idx=i) + safe_get(yf_balance, ['Current Debt'], col_idx=i)) / 1e6
                
            ar = safe_get(yf_balance, ['Accounts Receivable', 'Receivables'], col_idx=i) / 1e6
            inv = safe_get(yf_balance, ['Inventory', 'Inventories'], col_idx=i) / 1e6
            ap = safe_get(yf_balance, ['Accounts Payable', 'Payables'], col_idx=i) / 1e6
            nwc = (ar + inv) - ap
            nwc_change = 0.01 * rev
            fcff = ebiat + da - capex - nwc_change
            
            if i > 0:
                prev_rev = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=i-1) / 1e6
                growth = (rev - prev_rev) / prev_rev if prev_rev else 0.0
            else:
                growth = np.nan
            
            margin = ebit / rev if rev else 0.0
            
            model_df.at["Revenue ($M)", col_lbl] = rev
            model_df.at["Revenue Growth (%)", col_lbl] = growth * 100 if not np.isnan(growth) else ""
            model_df.at["Cost of Revenue ($M)", col_lbl] = cogs
            model_df.at["Cost of Operations ($M)", col_lbl] = opex
            model_df.at["Other Costs ($M)", col_lbl] = other
            model_df.at["Operating EBIT ($M)", col_lbl] = ebit
            model_df.at["Operating Margin (%)", col_lbl] = margin * 100
            model_df.at["Tax Provision ($M)", col_lbl] = tax
            model_df.at["EBIAT ($M)", col_lbl] = ebiat
            model_df.at["D&A ($M)", col_lbl] = da
            model_df.at["CapEx ($M)", col_lbl] = capex
            model_df.at["Cash ($M)", col_lbl] = cash
            model_df.at["Debt ($M)", col_lbl] = debt
            model_df.at["Receivables ($M)", col_lbl] = ar
            model_df.at["Inventory ($M)", col_lbl] = inv
            model_df.at["Payables ($M)", col_lbl] = ap
            model_df.at["Net Working Capital ($M)", col_lbl] = nwc
            model_df.at["Change in NWC ($M)", col_lbl] = nwc_change
            model_df.at["Unlevered Free Cash Flow (FCFF) ($M)", col_lbl] = fcff
            model_df.at["Discount Factor", col_lbl] = ""
            model_df.at["Present Value of FCF ($M)", col_lbl] = ""

        # 2. Populate projected metrics
        current_rev = model_df.at["Revenue ($M)", hist_columns[-1]]
        prev_nwc = model_df.at["Net Working Capital ($M)", hist_columns[-1]]
        
        projected_fcf_list = []
        discount_factors_list = []
        pv_fcf_list = []
        
        for i in range(forecast_years):
            col_lbl = proj_columns[i]
            growth = p_rev_growth[i]
            cogs_pct = p_cogs_pct[i]
            opex_pct = p_opex_pct[i]
            other_pct = p_other_pct[i]
            tax_rate = p_tax_rate[i]
            capex_pct = p_capex[i]
            da_pct = p_da[i]
            
            # Calculations
            rev = current_rev * (1 + growth)
            current_rev = rev
            
            cogs = rev * cogs_pct
            opex = rev * opex_pct
            other = rev * other_pct
            ebit = rev - cogs - opex - other
            tax = ebit * tax_rate
            ebiat = ebit - tax
            da = rev * da_pct
            capex = rev * capex_pct
            
            # Balance sheet logic
            if autopilot_on:
                # Receivables (DSO), Inventory (DIO), Payables (DPO) (Wall Street Prep compliant)
                ar = (hist_dso * rev) / 365
                inv = (hist_dio * cogs) / 365
                ap = (hist_dpo * cogs) / 365
                cash = hist_cash_pct * rev
                debt = hist_debt_last
            else:
                ar = rev * p_ar_pct[i]
                inv = rev * p_inv_pct[i]
                ap = rev * p_ap_pct[i]
                cash = rev * p_cash_pct[i]
                debt = rev * p_debt_pct[i]
                
            nwc = (ar + inv) - ap
            nwc_change = nwc - prev_nwc
            prev_nwc = nwc
            
            fcff = ebiat + da - capex - nwc_change
            
            df = 1 / ((1 + ui_wacc) ** (i + 1))
            pv_fcff = fcff * df
            
            projected_fcf_list.append(fcff)
            discount_factors_list.append(df)
            pv_fcf_list.append(pv_fcff)
            
            model_df.at["Revenue ($M)", col_lbl] = rev
            model_df.at["Revenue Growth (%)", col_lbl] = growth * 100
            model_df.at["Cost of Revenue ($M)", col_lbl] = cogs
            model_df.at["Cost of Operations ($M)", col_lbl] = opex
            model_df.at["Other Costs ($M)", col_lbl] = other
            model_df.at["Operating EBIT ($M)", col_lbl] = ebit
            model_df.at["Operating Margin (%)", col_lbl] = (ebit / rev) * 100
            model_df.at["Tax Provision ($M)", col_lbl] = tax
            model_df.at["EBIAT ($M)", col_lbl] = ebiat
            model_df.at["D&A ($M)", col_lbl] = da
            model_df.at["CapEx ($M)", col_lbl] = capex
            model_df.at["Cash ($M)", col_lbl] = cash
            model_df.at["Debt ($M)", col_lbl] = debt
            model_df.at["Receivables ($M)", col_lbl] = ar
            model_df.at["Inventory ($M)", col_lbl] = inv
            model_df.at["Payables ($M)", col_lbl] = ap
            model_df.at["Net Working Capital ($M)", col_lbl] = nwc
            model_df.at["Change in NWC ($M)", col_lbl] = nwc_change
            model_df.at["Unlevered Free Cash Flow (FCFF) ($M)", col_lbl] = fcff
            model_df.at["Discount Factor", col_lbl] = df
            model_df.at["Present Value of FCF ($M)", col_lbl] = pv_fcff

        # Dynamic Calculations
        sum_pv_fcff = sum(pv_fcf_list)
        terminal_value = (projected_fcf_list[-1] * (1 + perpetual_growth)) / (ui_wacc - perpetual_growth) if ui_wacc > perpetual_growth else 0.0
        pv_terminal_val = terminal_value * discount_factors_list[-1]
        enterprise_value = sum_pv_fcff + pv_terminal_val
        
        total_debt_m = total_debt / 1e6
        cash_m = cash_and_equiv / 1e6
        shares_m = shares_outstanding / 1e6
        
        implied_equity_val = enterprise_value - total_debt_m + cash_m
        implied_stock_price = implied_equity_val / shares_m if shares_m > 0 else 0.0

        # Apply Jargon Translation mapping if Jargon Free is triggered
        translated_df = model_df.copy()
        if jargon_free:
            jargon_translation_map = {
                "Revenue ($M)": "Total Sales (Money In) ($M)",
                "Revenue Growth (%)": "Sales Growth Rate (%)",
                "Cost of Revenue ($M)": "Cost of Production ($M)",
                "Cost of Operations ($M)": "Operating Expenses (OpEx) ($M)",
                "Other Costs ($M)": "Other Miscellaneous Costs ($M)",
                "Operating EBIT ($M)": "Core Operating Profit ($M)",
                "Operating Margin (%)": "Profit Margin on Sales (%)",
                "Tax Provision ($M)": "Taxes Paid ($M)",
                "EBIAT ($M)": "Net Business Earnings (After Taxes) ($M)",
                "D&A ($M)": "Wear & Tear Non-Cash Recovery ($M)",
                "CapEx ($M)": "Facilities & Equipment Reinvestments ($M)",
                "Cash ($M)": "Bank Cash Reserves ($M)",
                "Debt ($M)": "Total Unpaid Loans ($M)",
                "Receivables ($M)": "Unpaid Customer Invoices (Receivables) ($M)",
                "Inventory ($M)": "Unsold Goods in Warehouse ($M)",
                "Payables ($M)": "Unpaid Supplier Bills (Payables) ($M)",
                "Net Working Capital ($M)": "Daily Capital Locked in Operations ($M)",
                "Change in NWC ($M)": "Change in Operational Capital ($M)",
                "Unlevered Free Cash Flow (FCFF) ($M)": "Leftover Cash for Investors ($M)",
                "Discount Factor": "Safety Discount Multiplier",
                "Present Value of FCF ($M)": "Present Value of Future Cash ($M)"
            }
            translated_df.index = [jargon_translation_map.get(row, row) for row in translated_df.index]

        # Format DataFrame values
        formatted_df = translated_df.copy()
        for col in formatted_df.columns:
            for row in formatted_df.index:
                val = formatted_df.at[row, col]
                if val == "" or pd.isna(val):
                    formatted_df.at[row, col] = "—"
                elif "%" in row or "Growth" in row or "Margin" in row:
                    formatted_df.at[row, col] = f"{float(val):,.1f}%"
                elif "Multiplier" in row or "Factor" in row:
                    formatted_df.at[row, col] = f"{float(val):.3f}"
                else:
                    formatted_df.at[row, col] = f"${float(val):,.1f}"

        # --- EXECUTIVE KPIS ---
        st.markdown("<h3 style='color: #C5A880; margin-top:0;'>Live Valuation Output</h3>", unsafe_allow_html=True)
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            lbl = "Calculated Fair Price" if jargon_free else "Implied Target Price"
            st.markdown(render_luxury_card(lbl, f"${implied_stock_price:,.2f}", is_accent=True), unsafe_allow_html=True)
        with col_c2:
            lbl = "Stock Market Price" if jargon_free else "Current Price"
            st.markdown(render_luxury_card(lbl, f"${current_price:,.2f}"), unsafe_allow_html=True)
            
        col_c3, col_c4 = st.columns(2)
        with col_c3:
            lbl = "Business Fair Worth" if jargon_free else "Enterprise Value"
            st.markdown(render_luxury_card(lbl, f"${enterprise_value:,.1f}M"), unsafe_allow_html=True)
        with col_c4:
            lbl = "Cost of Capital" if jargon_free else "Assumed WACC"
            st.markdown(render_luxury_card(lbl, f"{ui_wacc*100:.2f}%"), unsafe_allow_html=True)

        # --- TIMELINE VIEW ---
        st.markdown(generate_luxury_table(formatted_df), unsafe_allow_html=True)

        # Plotly Valuation Comparison Chart
        lbl_market = "Market Stock Price" if jargon_free else "Current Market Price"
        lbl_dcf = "Calculated Fair Price" if jargon_free else "Implied DCF Value"
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Price Comparison',
            x=[lbl_market, lbl_dcf],
            y=[current_price, implied_stock_price],
            marker_color=['#4B5563', '#C5A880'],
            width=[0.3, 0.3]
        ))
        fig.update_layout(
            paper_bgcolor='#090D16',
            plot_bgcolor='#0B0F19',
            font_color='#E5E7EB',
            xaxis=dict(showgrid=False, linecolor='#374151'),
            yaxis=dict(showgrid=True, gridcolor='#1F2937', linecolor='#374151'),
            margin=dict(l=20, r=20, t=20, b=20),
            height=280
        )
        st.plotly_chart(fig, use_container_width=True)

    # --- REFERENCE SHEETS (Non-Finance friendly explainers) ---
    st.markdown("<hr style='border-color: #1F2937;' />", unsafe_allow_html=True)
    st.subheader("Verification Worksheets")
    
    if jargon_free:
        st.markdown("""
        These spreadsheets display the raw data used as reference for historical figures:
        *   **Income Statement**: "The scorecard" showing Sales minus operating costs.
        *   **Balance Sheet**: "The Inventory Ledger" showing what the company owns vs what it owes.
        *   **Cash Flow Statement**: "The Cash Register" tracking exact money movement.
        """)
        
    if not sec_failed:
        view_mode = st.selectbox("SEC Report Resolution", ["standard", "summary"])
        tab_is, tab_bs, tab_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow Statement"])
        
        income_key = f"income_{view_mode}"
        balance_key = f"balance_{view_mode}"
        cashflow_key = f"cashflow_{view_mode}"
        
        with tab_is:
            df_to_show = clean_sec_dataframe(sec_data.get(income_key, None))
            st.dataframe(df_to_show, use_container_width=True)
        with tab_bs:
            df_to_show = clean_sec_dataframe(sec_data.get(balance_key, None))
            st.dataframe(df_to_show, use_container_width=True)
        with tab_cf:
            df_to_show = clean_sec_dataframe(sec_data.get(cashflow_key, None))
            st.dataframe(df_to_show, use_container_width=True)
    else:
        tab_is, tab_bs, tab_cf = st.tabs(["Income Statement (Historical Reference)", "Balance Sheet (Historical Reference)", "Cash Flow (Historical Reference)"])
        with tab_is:
            st.dataframe(yf_financials, use_container_width=True)
        with tab_bs:
            st.dataframe(yf_balance, use_container_width=True)
        with tab_cf:
            st.dataframe(yf_cashflow, use_container_width=True)