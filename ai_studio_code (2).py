import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import plotly.graph_objects as go
from edgar import Company, set_identity

# Set page layout
st.set_page_config(page_title="SEC Edgar-Powered Interactive DCF", layout="wide")

st.title("SEC EDGAR-Powered Interactive DCF Model")
st.caption("Extract exact financial statements directly from the SEC EDGAR database, customize projections, and calculate valuation.")

# --- 1. SEC IDENTITY CONFIGURATION (Mandated by SEC Edgar API) ---
st.sidebar.header("1. SEC EDGAR Authentication")
sec_email = st.sidebar.text_input(
    "User-Agent Email (Required by SEC)",
    value="analyst@independentresearch.com",
    help="The SEC requires all programmatic requests to declare a valid contact email in the User-Agent header."
)

if sec_email:
    try:
        set_identity(sec_email)
    except Exception as e:
        st.sidebar.error(f"Could not set SEC identity: {e}")

# --- 2. VALUATION PARAMETERS ---
st.sidebar.header("2. Valuation Parameters")
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol", value="MSFT").upper().strip()
rf_rate = st.sidebar.number_input("Risk-Free Rate (%)", min_value=0.0, max_value=20.0, value=4.2, step=0.1) / 100
erp = st.sidebar.number_input("Equity Risk Premium (%)", min_value=0.0, max_value=20.0, value=5.5, step=0.1) / 100
perpetual_growth = st.sidebar.number_input("Perpetual Growth Rate (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1) / 100

# Helper function to remove internal metadata columns from EDGAR tables
def clean_sec_dataframe(df):
    if df is None or df.empty:
        return df
    cols_to_drop = ['level', 'abstract', 'parent_concept', 'parent_abstract_concept', 'concept']
    existing_drops = [c for c in cols_to_drop if c in df.columns]
    return df.drop(columns=existing_drops)

# Helper for standard financial data extraction
def safe_get(df, keys, default=0.0):
    if df is None or df.empty:
        return default
    df_normalized = df.copy()
    df_normalized.index = df_normalized.index.astype(str).str.lower().str.strip()
    for key in keys:
        key_norm = key.lower().strip()
        if key_norm in df_normalized.index:
            row = df_normalized.loc[key_norm]
            val = row.iloc[0] if isinstance(row, pd.Series) else row
            if pd.notna(val):
                return float(val)
    return default

# --- 3. FETCH DATA (Optimized to return only serializable objects) ---
@st.cache_data(show_spinner="Fetching exact statements from SEC EDGAR...", ttl=3600)
def load_sec_data(ticker_str, email_str):
    try:
        set_identity(email_str)
        company = Company(ticker_str)
        financials = company.get_financials()
        
        # Pull standard views inside the cached function and convert to native DataFrames
        return {
            "income_standard": financials.income_statement().to_dataframe(view="standard"),
            "income_summary": financials.income_statement().to_dataframe(view="summary"),
            "income_detailed": financials.income_statement().to_dataframe(view="detailed"),
            
            "balance_standard": financials.balance_sheet().to_dataframe(view="standard"),
            "balance_summary": financials.balance_sheet().to_dataframe(view="summary"),
            "balance_detailed": financials.balance_sheet().to_dataframe(view="detailed"),
            
            "cashflow_standard": financials.cashflow_statement().to_dataframe(view="standard"),
            "cashflow_summary": financials.cashflow_statement().to_dataframe(view="summary"),
            "cashflow_detailed": financials.cashflow_statement().to_dataframe(view="detailed"),
            
            "company_name": str(company.name),
            "cik": str(company.cik),
            "error": None
        }
    except Exception as e:
        return {"error": str(e)}

@st.cache_data(show_spinner="Loading market calculation variables...", ttl=3600)
def load_market_vars(ticker_str):
    try:
        ticker = yf.Ticker(ticker_str)
        # Convert objects to standard dict and copied dataframes to avoid serialization failures
        info = dict(ticker.info)
        financials = ticker.financials.copy()
        balance_sheet = ticker.balance_sheet.copy()
        cashflow = ticker.cashflow.copy()
        
        return info, financials, balance_sheet, cashflow, None
    except Exception as e:
        return None, None, None, None, str(e)

if ticker_symbol:
    # Load SEC Data
    sec_data = load_sec_data(ticker_symbol, sec_email)
    # Load Market Data (Now optimized to exclude the raw yf.Ticker object)
    yf_info, yf_financials, yf_balance, yf_cashflow, yf_error = load_market_vars(ticker_symbol)
    
    if sec_data.get("error") or yf_error:
        st.error(f"Error loading company data. Details: SEC Error: {sec_data.get('error')} | Market Error: {yf_error}")
        st.info("Ensure you have set a valid User-Agent email and the ticker is a standard US-listed SEC filer.")
    else:
        # --- DISPLAY METRICS HEADER ---
        company_name = sec_data["company_name"]
        cik = sec_data["cik"]
        current_price = yf_info.get('currentPrice', 0.0)
        shares_outstanding = yf_info.get('sharesOutstanding', 1.0)
        beta = yf_info.get('beta', 1.0)
        
        st.subheader(f"{company_name} (CIK: {cik})")
        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        col_m1.metric("Current Market Price", f"${current_price:,.2f}")
        col_m2.metric("Market Cap", f"${yf_info.get('marketCap', shares_outstanding * current_price):,.0f}")
        col_m3.metric("Beta", f"{beta:.2f}")
        
        # Safe balance sheet retrieval for WACC
        cash_and_equiv = safe_get(yf_balance, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash'])
        total_debt = safe_get(yf_balance, ['Total Debt', 'Long Term Debt', 'LongTermDebt'])
        if total_debt == 0.0:
            total_debt = safe_get(yf_balance, ['Long Term Debt']) + safe_get(yf_balance, ['Current Debt', 'Short Long Term Debt'])
        
        net_debt = max(0.0, total_debt - cash_and_equiv)
        col_m4.metric("Net Debt", f"${net_debt:,.0f}")

        # --- Display RAW SEC EDGAR Financial Statements ---
        st.subheader("Exact Financial Statements (As Filed to SEC)")
        st.markdown("These tables preserve the exact custom line items, headers, and segments written down by the company.")
        
        view_mode = st.selectbox("Select Display View (Standard matches SEC Viewer, Summary removes segment details)", ["standard", "summary", "detailed"])
        
        tab_is, tab_bs, tab_cf = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow Statement"])
        
        # Accessing correct pre-compiled serializable DataFrames
        income_key = f"income_{view_mode}"
        balance_key = f"balance_{view_mode}"
        cashflow_key = f"cashflow_{view_mode}"
        
        with tab_is:
            st.dataframe(clean_sec_dataframe(sec_data[income_key]), use_container_width=True)
            
        with tab_bs:
            st.dataframe(clean_sec_dataframe(sec_data[balance_key]), use_container_width=True)
            
        with tab_cf:
            st.dataframe(clean_sec_dataframe(sec_data[cashflow_key]), use_container_width=True)

        # --- STEP 4: INTERACTIVE PROJECTION METRICS ---
        st.subheader("Interactive 5-Year Projection Drivers")
        st.markdown("Use the editable spreadsheet below to manage the financial vectors modeled beneath the statements.")
        
        # Gather baseline metrics from normalized data
        latest_revenue = safe_get(yf_financials, ['Total Revenue', 'Revenue'])
        latest_ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'])
        latest_interest = safe_get(yf_financials, ['Interest Expense'])
        latest_tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'])
        latest_ebt = safe_get(yf_financials, ['Pretax Income', 'Income Before Tax'])
        latest_capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx']))
        latest_da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'])
        
        hist_revenue_growth = 0.08
        if yf_financials is not None and yf_financials.shape[1] > 1:
            try:
                rev_list = yf_financials.loc['Total Revenue'].values
                hist_revenue_growth = (rev_list[0] / rev_list[1]) - 1 if rev_list[1] != 0 else 0.08
            except:
                pass
                
        hist_ebit_margin = latest_ebit / latest_revenue if latest_revenue else 0.20
        hist_tax_rate = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
        hist_capex_pct = latest_capex / latest_revenue if latest_revenue else 0.04
        hist_da_pct = latest_da / latest_revenue if latest_revenue else 0.04
        hist_nwc_change_pct = 0.01

        projection_metrics = [
            "Revenue Growth Rate (%)",
            "Operating (EBIT) Margin (%)",
            "Effective Tax Rate (%)",
            "CapEx as % of Revenue (%)",
            "D&A as % of Revenue (%)",
            "Change in NWC as % of Revenue (%)"
        ]
        
        default_projections = {
            "Year 1": [hist_revenue_growth * 100, hist_ebit_margin * 100, hist_tax_rate * 100, hist_capex_pct * 100, hist_da_pct * 100, hist_nwc_change_pct * 100],
            "Year 2": [hist_revenue_growth * 100, hist_ebit_margin * 100, hist_tax_rate * 100, hist_capex_pct * 100, hist_da_pct * 100, hist_nwc_change_pct * 100],
            "Year 3": [hist_revenue_growth * 100, hist_ebit_margin * 100, hist_tax_rate * 100, hist_capex_pct * 100, hist_da_pct * 100, hist_nwc_change_pct * 100],
            "Year 4": [hist_revenue_growth * 100, hist_ebit_margin * 100, hist_tax_rate * 100, hist_capex_pct * 100, hist_da_pct * 100, hist_nwc_change_pct * 100],
            "Year 5": [hist_revenue_growth * 100, hist_ebit_margin * 100, hist_tax_rate * 100, hist_capex_pct * 100, hist_da_pct * 100, hist_nwc_change_pct * 100],
        }
        
        proj_df = pd.DataFrame(default_projections, index=projection_metrics)
        edited_proj_df = st.data_editor(proj_df, use_container_width=True)
        
        # Read edited data
        p_rev_growth = edited_proj_df.loc["Revenue Growth Rate (%)"].values / 100
        p_ebit_margin = edited_proj_df.loc["Operating (EBIT) Margin (%)"].values / 100
        p_tax_rate = edited_proj_df.loc["Effective Tax Rate (%)"].values / 100
        p_capex = edited_proj_df.loc["CapEx as % of Revenue (%)"].values / 100
        p_da = edited_proj_df.loc["D&A as % of Revenue (%)"].values / 100
        p_nwc = edited_proj_df.loc["Change in NWC as % of Revenue (%)"].values / 100

        # --- STEP 5: WACC ENGINE ---
        st.subheader("Weighted Average Cost of Capital (WACC)")
        cost_of_equity = rf_rate + (beta * erp)
        
        implied_interest_rate = 0.05
        if total_debt > 0 and latest_interest > 0:
            implied_interest_rate = min(latest_interest / total_debt, 0.15)
            
        market_cap = yf_info.get('marketCap', shares_outstanding * current_price)
        total_val = market_cap + total_debt
        
        weight_equity = market_cap / total_val if total_val > 0 else 1.0
        weight_debt = total_debt / total_val if total_val > 0 else 0.0
        
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            ui_cost_equity = st.number_input("Cost of Equity (%)", value=float(cost_of_equity * 100), step=0.1) / 100
        with col_w2:
            ui_cost_debt = st.number_input("Pre-Tax Cost of Debt (%)", value=float(implied_interest_rate * 100), step=0.1) / 100
        with col_w3:
            avg_tax = p_tax_rate[0]
            ui_wacc = (weight_equity * ui_cost_equity) + (weight_debt * ui_cost_debt * (1 - avg_tax))
            st.metric("Calculated WACC (%)", f"{ui_wacc * 100:.2f}%")

        # --- STEP 6: FCFF ENGINE AND PRESENT VALUE ---
        years = [f"Year {i}" for i in range(1, 6)]
        projected_rev = []
        projected_ebit = []
        projected_ebiat = []
        projected_da_val = []
        projected_capex_val = []
        projected_nwc_val = []
        projected_fcff = []
        discount_factors = []
        pv_fcff = []
        
        current_rev = latest_revenue
        for i in range(5):
            next_rev = current_rev * (1 + p_rev_growth[i])
            projected_rev.append(next_rev)
            current_rev = next_rev
            
            ebit = next_rev * p_ebit_margin[i]
            projected_ebit.append(ebit)
            
            ebiat = ebit * (1 - p_tax_rate[i])
            projected_ebiat.append(ebiat)
            
            da = next_rev * p_da[i]
            capex = next_rev * p_capex[i]
            nwc_change = next_rev * p_nwc[i]
            
            projected_da_val.append(da)
            projected_capex_val.append(capex)
            projected_nwc_val.append(nwc_change)
            
            fcff = ebiat + da - capex - nwc_change
            projected_fcff.append(fcff)
            
            df = 1 / ((1 + ui_wacc) ** (i + 1))
            discount_factors.append(df)
            pv_fcff.append(fcff * df)
            
        dcf_schedule_df = pd.DataFrame({
            "Projected Revenue": projected_rev,
            "Operating EBIT": projected_ebit,
            "EBIAT (Earnings Before Interest After Taxes)": projected_ebiat,
            "Add: Depreciation & Amortization": projected_da_val,
            "Less: Capital Expenditures": projected_capex_val,
            "Less: Change in Net Working Capital": projected_nwc_val,
            "Free Cash Flow to Firm (FCFF)": projected_fcff,
            "Discount Factor": discount_factors,
            "Present Value of FCFF": pv_fcff
        }, index=years).T
        
        st.subheader("Projected Free Cash Flows (FCFF) Table")
        st.dataframe(dcf_schedule_df.style.format("{:,.2f}"))

        # --- STEP 7: VALUATION & IMPLIED STOCK PRICE ---
        st.subheader("DCF Target Valuation Summary")
        
        sum_pv_fcff = sum(pv_fcff)
        terminal_value = (projected_fcff[-1] * (1 + perpetual_growth)) / (ui_wacc - perpetual_growth) if ui_wacc > perpetual_growth else 0.0
        pv_terminal_val = terminal_value * discount_factors[-1]
        
        enterprise_value = sum_pv_fcff + pv_terminal_val
        implied_equity_val = enterprise_value - total_debt + cash_and_equiv
        implied_stock_price = implied_equity_val / shares_outstanding if shares_outstanding > 0 else 0.0
        
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        col_v1.metric("PV of 5Yr Cash Flows", f"${sum_pv_fcff:,.0f}")
        col_v2.metric("PV of Terminal Value", f"${pv_terminal_val:,.0f}")
        col_v3.metric("Implied Enterprise Value", f"${enterprise_value:,.0f}")
        col_v4.metric("Implied Target Share Price", f"${implied_stock_price:,.2f}")
        
        if ui_wacc <= perpetual_growth:
            st.error("Mathematical Constraint Error: Your calculated WACC must be strictly higher than your Perpetual Growth Rate to perform a DCF valuation.")

        # --- Chart Comparison ---
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Price Comparison',
            x=['Current Market Price', 'Implied DCF Target Price'],
            y=[current_price, implied_stock_price],
            marker_color=['#1f77b4', '#2ca02c']
        ))
        fig.update_layout(
            title_text=f"Valuation Target vs. Market Price ({ticker_symbol})",
            yaxis_title="Stock Price ($)",
            width=600,
            height=400
        )
        st.plotly_chart(fig, use_container_width=False)