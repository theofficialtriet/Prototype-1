import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from edgar import Company, set_identity

# Set page layout
st.set_page_config(page_title="Executive DCF Spreadsheet Model", layout="wide")

# Inject Custom CSS to give tables a clean, organized, premium Excel aesthetic
st.markdown("""
<style>
    /* Styling Streamlit Tables and Dataframes to look like clean Excel sheets */
    .stDataFrame, table, .stTable {
        font-family: 'Segoe UI', -apple-system, sans-serif !important;
        font-size: 0.92rem !important;
        border-collapse: collapse !important;
        border: 1px solid #e2e8f0 !important;
    }
    th {
        background-color: #0f172a !important; /* Premium Executive Slate Blue */
        color: #ffffff !important;
        font-weight: 600 !important;
        text-align: right !important;
        padding: 8px 12px !important;
        border: 1px solid #334155 !important;
    }
    th:first-child {
        text-align: left !important;
    }
    td {
        padding: 8px 12px !important;
        border: 1px solid #e2e8f0 !important;
        text-align: right !important;
    }
    td:first-child {
        text-align: left !important;
        font-weight: 500;
        background-color: #f8fafc; /* Standardized Left-hand row labels */
    }
    tr:nth-child(even) {
        background-color: #f8fafc; /* Alternating row stripes */
    }
    tr:hover {
        background-color: #f1f5f9; /* Subtle hover effect */
    }
    /* Total Row highlight styles */
    .highlight-row {
        font-weight: bold !important;
        background-color: #f1f5f9 !important;
        border-top: 1.5px solid #0f172a !important;
        border-bottom: 2.5px double #0f172a !important;
    }
</style>
""", unsafe_allow_html=True)

st.title("Executive Financial Model & DCF Valuation")
st.caption("A clean, dynamic timeline model combining exact SEC filing history with user-defined multi-year projections.")

# --- SIDEBAR: ALL CONTROLS & ASSUMPTIONS ---
st.sidebar.header("1. SEC EDGAR Authentication")
sec_email = st.sidebar.text_input(
    "User-Agent Email",
    value="analyst@independentresearch.com",
    help="Required by the SEC to declare a contact email."
)

if sec_email:
    try:
        set_identity(sec_email)
    except Exception as e:
        st.sidebar.error(f"SEC Verification failed: {e}")

st.sidebar.header("2. Model Scope")
ticker_symbol = st.sidebar.text_input("Ticker Symbol", value="MSFT").upper().strip()
forecast_years = st.sidebar.slider("Forecast Horizon (Years)", min_value=1, max_value=15, value=5)

st.sidebar.header("3. Valuation Assumptions")
rf_rate = st.sidebar.number_input("Risk-Free Rate (%)", min_value=0.0, max_value=20.0, value=4.2, step=0.1) / 100
erp = st.sidebar.number_input("Equity Risk Premium (%)", min_value=0.0, max_value=20.0, value=5.5, step=0.1) / 100
perpetual_growth = st.sidebar.number_input("Perpetual Growth Rate (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1) / 100

# Helper functions for fetching standard financial data points safely
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

# --- DATA FETCHING (Serialized cleanly to avoid memory leaks) ---
@st.cache_data(show_spinner="Connecting to SEC EDGAR database...", ttl=3600)
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

@st.cache_data(show_spinner="Gathering normalized financial statistics...", ttl=3600)
def load_market_vars(ticker_str):
    try:
        ticker = yf.Ticker(ticker_str)
        info = dict(ticker.info)
        # Ensure chronological sorting left-to-right
        financials = ticker.financials.reindex(sorted(ticker.financials.columns), axis=1)
        balance_sheet = ticker.balance_sheet.reindex(sorted(ticker.balance_sheet.columns), axis=1)
        cashflow = ticker.cashflow.reindex(sorted(ticker.cashflow.columns), axis=1)
        
        return info, financials, balance_sheet, cashflow, None
    except Exception as e:
        return None, None, None, None, str(e)

if ticker_symbol:
    # Attempt to load SEC Data
    sec_data = load_sec_data(ticker_symbol, sec_email)
    # Load Market Data
    yf_info, yf_financials, yf_balance, yf_cashflow, yf_error = load_market_vars(ticker_symbol)
    
    if yf_error:
        st.error(f"Error loading market data for '{ticker_symbol}' from Yahoo Finance.")
        st.error(f"Details: {yf_error}")
        st.info("Please make sure the ticker is valid and exists on Yahoo Finance.")
    else:
        # Determine if SEC data loaded successfully or if we should use Yahoo Finance fallback
        sec_failed = "error" in sec_data and sec_data["error"] is not None
        
        if sec_failed:
            st.warning(f"Note: SEC EDGAR database returned a rate-limit/connection error ({sec_data['error']}). The app has automatically fallen back to Yahoo Finance statements.")
            company_name = yf_info.get('longName', ticker_symbol)
            cik = "N/A (Fallback active)"
        else:
            company_name = sec_data["company_name"]
            cik = sec_data["cik"]
            
        current_price = yf_info.get('currentPrice', 0.0)
        shares_outstanding = yf_info.get('sharesOutstanding', 1.0)
        beta = yf_info.get('beta', 1.0)
        
        # Financial health variables
        cash_and_equiv = safe_get(yf_balance, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash'], col_idx=-1)
        total_debt = safe_get(yf_balance, ['Total Debt', 'Long Term Debt', 'LongTermDebt'], col_idx=-1)
        if total_debt == 0.0:
            total_debt = safe_get(yf_balance, ['Long Term Debt'], col_idx=-1) + safe_get(yf_balance, ['Current Debt', 'Short Long Term Debt'], col_idx=-1)
        net_debt = max(0.0, total_debt - cash_and_equiv)
        
        # Calculate historical stats to populate sidebar default baselines
        latest_revenue = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=-1)
        latest_ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'], col_idx=-1)
        latest_interest = safe_get(yf_financials, ['Interest Expense'], col_idx=-1)
        latest_tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'], col_idx=-1)
        latest_ebt = safe_get(yf_financials, ['Pretax Income', 'Income Before Tax'], col_idx=-1)
        latest_capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx'], col_idx=-1))
        latest_da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'], col_idx=-1)
        
        hist_rev_growth = 0.08
        if yf_financials is not None and yf_financials.shape[1] > 1:
            try:
                # Chronological calculation
                rev_vals = yf_financials.loc['Total Revenue'].values
                hist_rev_growth = (rev_vals[-1] / rev_vals[-2]) - 1
            except:
                pass
                
        hist_ebit_margin = latest_ebit / latest_revenue if latest_revenue else 0.20
        hist_tax_rate = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
        hist_capex_pct = latest_capex / latest_revenue if latest_revenue else 0.04
        hist_da_pct = latest_da / latest_revenue if latest_revenue else 0.04
        hist_nwc_change_pct = 0.01

        # --- SIDEBAR: DYNAMIC PROJECTION SLIDERS ---
        st.sidebar.header("4. Forecast Configuration")
        
        # Establish dynamic, year-by-year target parameters inside the sidebar to avoid layout clutter
        with st.sidebar.expander("Detailed Year-by-Year Setup", expanded=True):
            p_rev_growth = []
            p_ebit_margin = []
            for y in range(1, forecast_years + 1):
                st.markdown(f"**Year {y} Drivers**")
                col_g, col_m = st.columns(2)
                with col_g:
                    g = st.number_input(f"Revenue Growth (%)", value=float(hist_rev_growth*100), key=f"g_{y}", step=0.5) / 100
                    p_rev_growth.append(g)
                with col_m:
                    m = st.number_input(f"EBIT Margin (%)", value=float(hist_ebit_margin*100), key=f"m_{y}", step=0.5) / 100
                    p_ebit_margin.append(m)

        with st.sidebar.expander("Global Balance Sheet & Tax Defaults", expanded=False):
            p_tax_rate = st.number_input("Flat Effective Tax Rate (%)", value=float(hist_tax_rate*100), step=0.5) / 100
            p_capex = st.number_input("Flat CapEx % of Revenue (%)", value=float(hist_capex_pct*100), step=0.5) / 100
            p_da = st.number_input("Flat D&A % of Revenue (%)", value=float(hist_da_pct*100), step=0.5) / 100
            p_nwc = st.number_input("Flat Change in NWC % of Revenue (%)", value=float(hist_nwc_change_pct*100), step=0.1) / 100

        # --- SIDEBAR: DYNAMIC WACC ENGINE ---
        st.sidebar.header("5. Capital Costs (WACC)")
        cost_of_equity = rf_rate + (beta * erp)
        implied_interest_rate = 0.05
        if total_debt > 0 and latest_interest > 0:
            implied_interest_rate = min(latest_interest / total_debt, 0.15)
            
        market_cap = yf_info.get('marketCap', shares_outstanding * current_price)
        total_val = market_cap + total_debt
        weight_equity = market_cap / total_val if total_val > 0 else 1.0
        weight_debt = total_debt / total_val if total_val > 0 else 0.0
        
        ui_cost_equity = st.sidebar.number_input("Cost of Equity (%)", value=float(cost_of_equity*100), step=0.1) / 100
        ui_cost_debt = st.sidebar.number_input("Pre-Tax Cost of Debt (%)", value=float(implied_interest_rate*100), step=0.1) / 100
        ui_wacc = (weight_equity * ui_cost_equity) + (weight_debt * ui_cost_debt * (1 - p_tax_rate))
        
        st.sidebar.metric("Target WACC", f"{ui_wacc * 100:.2f}%")

        # --- MAIN WORKSPACE: INTEGRATED FORECAST TIMELINE ---
        st.subheader(f"{company_name} (Ticker: {ticker_symbol} | CIK: {cik})")
        
        # Build chronological timeline structure
        hist_columns = [str(col.year) if hasattr(col, 'year') else str(col) for col in yf_financials.columns]
        proj_columns = [f"{int(hist_columns[-1]) + i} (P)" for i in range(1, forecast_years + 1)]
        all_timeline_columns = hist_columns + proj_columns
        
        # Initialize rows for continuous table
        timeline_rows = [
            "Revenue ($M)",
            "Revenue Growth (%)",
            "Operating EBIT ($M)",
            "Operating Margin (%)",
            "Tax Provision ($M)",
            "EBIAT ($M)",
            "D&A ($M)",
            "CapEx ($M)",
            "Change in NWC ($M)",
            "Unlevered Free Cash Flow (FCFF) ($M)",
            "Discount Factor",
            "Present Value of FCF ($M)"
        ]
        
        model_df = pd.DataFrame(index=timeline_rows, columns=all_timeline_columns)

        # 1. POPULATE HISTORICAL METRICS
        num_hist_periods = len(hist_columns)
        for i in range(num_hist_periods):
            col_lbl = hist_columns[i]
            
            # Fetch absolute figures in millions
            rev = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=i) / 1e6
            ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'], col_idx=i) / 1e6
            tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'], col_idx=i) / 1e6
            ebiat = ebit - tax
            da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'], col_idx=i) / 1e6
            capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx'], col_idx=i)) / 1e6
            nwc_change = 0.01 * rev # Assume 1% baseline for historical display compatibility
            fcff = ebiat + da - capex - nwc_change
            
            # Growth rates
            if i > 0:
                prev_rev = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=i-1) / 1e6
                growth = (rev - prev_rev) / prev_rev if prev_rev else 0.0
            else:
                growth = np.nan
            
            margin = ebit / rev if rev else 0.0
            
            model_df.at["Revenue ($M)", col_lbl] = rev
            model_df.at["Revenue Growth (%)", col_lbl] = growth * 100 if not np.isnan(growth) else ""
            model_df.at["Operating EBIT ($M)", col_lbl] = ebit
            model_df.at["Operating Margin (%)", col_lbl] = margin * 100
            model_df.at["Tax Provision ($M)", col_lbl] = tax
            model_df.at["EBIAT ($M)", col_lbl] = ebiat
            model_df.at["D&A ($M)", col_lbl] = da
            model_df.at["CapEx ($M)", col_lbl] = capex
            model_df.at["Change in NWC ($M)", col_lbl] = nwc_change
            model_df.at["Unlevered Free Cash Flow (FCFF) ($M)", col_lbl] = fcff
            model_df.at["Discount Factor", col_lbl] = ""
            model_df.at["Present Value of FCF ($M)", col_lbl] = ""

        # 2. POPULATE PROJECTED METRICS (Continuous timeline extension)
        current_rev = model_df.at["Revenue ($M)", hist_columns[-1]]
        projected_fcf_list = []
        discount_factors_list = []
        pv_fcf_list = []
        
        for i in range(forecast_years):
            col_lbl = proj_columns[i]
            
            growth = p_rev_growth[i]
            margin = p_ebit_margin[i]
            
            rev = current_rev * (1 + growth)
            current_rev = rev
            
            ebit = rev * margin
            tax = ebit * p_tax_rate
            ebiat = ebit - tax
            da = rev * p_da
            capex = rev * p_capex
            nwc_change = rev * p_nwc
            fcff = ebiat + da - capex - nwc_change
            
            df = 1 / ((1 + ui_wacc) ** (i + 1))
            pv_fcff = fcff * df
            
            projected_fcf_list.append(fcff)
            discount_factors_list.append(df)
            pv_fcf_list.append(pv_fcff)
            
            model_df.at["Revenue ($M)", col_lbl] = rev
            model_df.at["Revenue Growth (%)", col_lbl] = growth * 100
            model_df.at["Operating EBIT ($M)", col_lbl] = ebit
            model_df.at["Operating Margin (%)", col_lbl] = margin * 100
            model_df.at["Tax Provision ($M)", col_lbl] = tax
            model_df.at["EBIAT ($M)", col_lbl] = ebiat
            model_df.at["D&A ($M)", col_lbl] = da
            model_df.at["CapEx ($M)", col_lbl] = capex
            model_df.at["Change in NWC ($M)", col_lbl] = nwc_change
            model_df.at["Unlevered Free Cash Flow (FCFF) ($M)", col_lbl] = fcff
            model_df.at["Discount Factor", col_lbl] = df
            model_df.at["Present Value of FCF ($M)", col_lbl] = pv_fcff

        # Format and display the continuous Excel model
        st.subheader("Integrated 3-Statement Forecasting Timeline")
        
        # Apply standard numerical cleanups before rendering
        formatted_df = model_df.copy()
        for col in formatted_df.columns:
            for row in formatted_df.index:
                val = formatted_df.at[row, col]
                if val == "" or pd.isna(val):
                    formatted_df.at[row, col] = "—"
                elif "%" in row or "Growth" in row or "Margin" in row:
                    formatted_df.at[row, col] = f"{float(val):,.1f}%"
                elif "Factor" in row:
                    formatted_df.at[row, col] = f"{float(val):.3f}"
                else:
                    formatted_df.at[row, col] = f"${float(val):,.1f}M"

        # Display clean styled DataFrame
        st.dataframe(formatted_df, use_container_width=True)

        # --- VALUATION INTEGRATION ---
        st.subheader("DCF Target Valuation Summary")
        
        sum_pv_fcff = sum(pv_fcf_list)
        terminal_value = (projected_fcf_list[-1] * (1 + perpetual_growth)) / (ui_wacc - perpetual_growth) if ui_wacc > perpetual_growth else 0.0
        pv_terminal_val = terminal_value * discount_factors_list[-1]
        
        enterprise_value = sum_pv_fcff + pv_terminal_val
        # Scale to millions for calculation consistency
        total_debt_m = total_debt / 1e6
        cash_m = cash_and_equiv / 1e6
        shares_m = shares_outstanding / 1e6
        
        implied_equity_val = enterprise_value - total_debt_m + cash_m
        implied_stock_price = implied_equity_val / shares_m if shares_m > 0 else 0.0
        
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        col_v1.metric("PV of Forecast Cash Flows", f"${sum_pv_fcff:,.1f}M")
        col_v2.metric("PV of Terminal Value", f"${pv_terminal_val:,.1f}M")
        col_v3.metric("Implied Enterprise Value", f"${enterprise_value:,.1f}M")
        col_v4.metric("Implied Target Share Price", f"${implied_stock_price:,.2f}")
        
        if ui_wacc <= perpetual_growth:
            st.error("Constraint Error: Target WACC must be strictly higher than your Perpetual Growth Rate to resolve terminal assumptions.")

        # --- SEC EXCEL TAB COMPONENT ---
        st.subheader("Filing Reference Sheets")
        st.markdown("Raw source statements loaded dynamically for verification.")
        
        if not sec_failed:
            view_mode = st.selectbox("Select Detail Level", ["standard", "summary"])
            tab_is, tab_bs, tab_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow Statement"])
            
            income_key = f"income_{view_mode}"
            balance_key = f"balance_{view_mode}"
            cashflow_key = f"cashflow_{view_mode}"
            
            with tab_is:
                st.dataframe(clean_sec_dataframe(sec_data[income_key]), use_container_width=True)
            with tab_bs:
                st.dataframe(clean_sec_dataframe(sec_data[balance_key]), use_container_width=True)
            with tab_cf:
                st.dataframe(clean_sec_dataframe(sec_data[cashflow_key]), use_container_width=True)
        else:
            # Display yfinance DataFrames as fallback sheets
            tab_is, tab_bs, tab_cf = st.tabs(["Income Statement (Yahoo Fallback)", "Balance Sheet (Yahoo Fallback)", "Cash Flow (Yahoo Fallback)"])
            with tab_is:
                st.dataframe(yf_financials, use_container_width=True)
            with tab_bs:
                st.dataframe(yf_balance, use_container_width=True)
            with tab_cf:
                st.dataframe(yf_cashflow, use_container_width=True)