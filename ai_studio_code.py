import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go

# Set page configuration
st.set_page_config(page_title="Interactive DCF Valuation Model", layout="wide")

st.title("Interactive Discounted Cash Flow (DCF) Model")
st.caption("Retrieve financial data from Yahoo Finance, customize 5-year projections, adjust WACC, and calculate the implied stock price.")

# Helper function to safely retrieve financial metrics from yfinance DataFrames
def safe_get(df, keys, default=0.0):
    if df is None or df.empty:
        return default
    # Normalize index to lowercase and stripped string to prevent key mismatches
    df_normalized = df.copy()
    df_normalized.index = df_normalized.index.astype(str).str.lower().str.strip()
    
    for key in keys:
        key_norm = key.lower().strip()
        if key_norm in df_normalized.index:
            row = df_normalized.loc[key_norm]
            # Handle cases where multiple rows match or return pandas Series
            val = row.iloc[0] if isinstance(row, pd.Series) else row
            if pd.notna(val):
                return float(val)
    return default

# 1. Sidebar - Input Ticker and Global Assumptions
st.sidebar.header("1. Input Ticker")
ticker_symbol = st.sidebar.text_input("Enter Ticker Symbol", value="MSFT").upper().strip()
load_button = st.sidebar.button("Fetch Financial Data")

st.sidebar.header("2. Valuation Parameters")
rf_rate = st.sidebar.number_input("Risk-Free Rate (%)", min_value=0.0, max_value=20.0, value=4.2, step=0.1) / 100
erp = st.sidebar.number_input("Equity Risk Premium (%)", min_value=0.0, max_value=20.0, value=5.5, step=0.1) / 100
perpetual_growth = st.sidebar.number_input("Perpetual Growth Rate (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1) / 100

# Cache data loading to avoid redundant API calls
@st.cache_data(ttl=3600)
def load_company_data(ticker_str):
    try:
        ticker = yf.Ticker(ticker_str)
        info = ticker.info
        
        # Pull financial sheets
        financials = ticker.financials
        balance_sheet = ticker.balance_sheet
        cashflow = ticker.cashflow
        
        return ticker, info, financials, balance_sheet, cashflow, None
    except Exception as e:
        return None, None, None, None, None, str(e)

# Fetch Data
if ticker_symbol:
    ticker_obj, info, financials, balance, cashflow, error = load_company_data(ticker_symbol)
    
    if error or not info or 'currentPrice' not in info:
        st.error(f"Error fetching data for '{ticker_symbol}'. Please verify the ticker symbol.")
    else:
        st.success(f"Data successfully loaded for {info.get('longName', ticker_symbol)}")
        
        # --- PREPARE DATA ---
        # Current stock details
        current_price = info.get('currentPrice', 0.0)
        shares_outstanding = info.get('sharesOutstanding', 1.0)
        beta = info.get('beta', 1.0)
        
        # Safely extract historical balance sheet items (Latest Period)
        cash_and_equiv = safe_get(balance, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash'])
        total_debt = safe_get(balance, ['Total Debt', 'Long Term Debt', 'LongTermDebt'])
        
        # Fallback if Total Debt is 0 or not found
        if total_debt == 0.0:
            lt_debt = safe_get(balance, ['Long Term Debt'])
            st_debt = safe_get(balance, ['Current Debt', 'Short Long Term Debt'])
            total_debt = lt_debt + st_debt

        net_debt = max(0.0, total_debt - cash_and_equiv)
        
        # Safely extract latest income statement items
        latest_revenue = safe_get(financials, ['Total Revenue', 'Revenue'])
        latest_ebit = safe_get(financials, ['Operating Income', 'EBIT'])
        latest_interest = safe_get(financials, ['Interest Expense'])
        latest_tax = safe_get(financials, ['Tax Provision', 'Income Tax Expense'])
        latest_ebt = safe_get(financials, ['Pretax Income', 'Income Before Tax'])
        
        # Historical metrics for default projection baseline
        hist_revenue_growth = 0.08  # Default baseline fallback
        if financials is not None and financials.shape[1] > 1:
            try:
                rev_list = financials.loc['Total Revenue'].values
                hist_revenue_growth = (rev_list[0] / rev_list[1]) - 1 if rev_list[1] != 0 else 0.08
            except Exception:
                pass
                
        hist_ebit_margin = latest_ebit / latest_revenue if latest_revenue else 0.20
        hist_tax_rate = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
        
        latest_capex = abs(safe_get(cashflow, ['Capital Expenditure', 'CapEx']))
        latest_da = safe_get(cashflow, ['Depreciation And Amortization', 'Depreciation'])
        
        hist_capex_pct = latest_capex / latest_revenue if latest_revenue else 0.04
        hist_da_pct = latest_da / latest_revenue if latest_revenue else 0.04
        hist_nwc_change_pct = 0.01  # Default benchmark assumption for change in Net Working Capital
        
        # --- VISUAL DISPLAY: Company Overview ---
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Current Price", f"${current_price:,.2f}")
        col2.metric("Market Cap", f"${info.get('marketCap', shares_outstanding * current_price):,.0f}")
        col3.metric("Beta", f"{beta:.2f}")
        col4.metric("Net Debt", f"${net_debt:,.0f}")
        
        # --- TABULAR PRESENTATION OF FINANCIALS ---
        st.subheader("Historical Financial Data Reference")
        tab1, tab2, tab3 = st.tabs(["Income Statement", "Balance Sheet", "Cash Flow"])
        
        with tab1:
            if financials is not None:
                st.dataframe(financials.head(15))
            else:
                st.write("Income statement data not available.")
        with tab2:
            if balance is not None:
                st.dataframe(balance.head(15))
            else:
                st.write("Balance sheet data not available.")
        with tab3:
            if cashflow is not None:
                st.dataframe(cashflow.head(15))
            else:
                st.write("Cash flow data not available.")

        # --- STEP 2: PROJECTIONS ---
        st.subheader("Interactive 5-Year Projections")
        st.write("Modify the baseline assumptions below to project future performance.")
        
        # Setup input dataframe structure for Streamlit Data Editor
        projection_metrics = [
            "Revenue Growth (%)",
            "EBIT Margin (%)",
            "Tax Rate (%)",
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
        
        # Data editor for manual override
        edited_proj_df = st.data_editor(proj_df, use_container_width=True)
        
        # Extract projection vectors from user input
        p_rev_growth = edited_proj_df.loc["Revenue Growth (%)"].values / 100
        p_ebit_margin = edited_proj_df.loc["EBIT Margin (%)"].values / 100
        p_tax_rate = edited_proj_df.loc["Tax Rate (%)"].values / 100
        p_capex = edited_proj_df.loc["CapEx as % of Revenue (%)"].values / 100
        p_da = edited_proj_df.loc["D&A as % of Revenue (%)"].values / 100
        p_nwc = edited_proj_df.loc["Change in NWC as % of Revenue (%)"].values / 100
        
        # --- STEP 3: WACC CALCULATION ---
        st.subheader("WACC Parameter Optimization")
        
        # Calculate Default Cost of Equity
        cost_of_equity = rf_rate + (beta * erp)
        
        # Calculate Default Cost of Debt
        implied_interest_rate = 0.05
        if total_debt > 0 and latest_interest > 0:
            implied_interest_rate = min(latest_interest / total_debt, 0.15) # Cap at 15% as standard sanity boundary
            
        market_cap = info.get('marketCap', shares_outstanding * current_price)
        total_value = market_cap + total_debt
        
        weight_equity = market_cap / total_value if total_value > 0 else 1.0
        weight_debt = total_debt / total_value if total_value > 0 else 0.0
        
        col_w1, col_w2, col_w3 = st.columns(3)
        with col_w1:
            ui_cost_equity = st.number_input("Cost of Equity (%)", value=float(cost_of_equity * 100), step=0.1) / 100
        with col_w2:
            ui_cost_debt = st.number_input("Pre-Tax Cost of Debt (%)", value=float(implied_interest_rate * 100), step=0.1) / 100
        with col_w3:
            avg_tax_rate = p_tax_rate[0] # Using Year 1 projected tax rate for calculation
            ui_wacc = (weight_equity * ui_cost_equity) + (weight_debt * ui_cost_debt * (1 - avg_tax_rate))
            st.metric("Calculated WACC (%)", f"{ui_wacc * 100:.2f}%", help="Weighted average of your inputs and dynamic balance sheet configurations.")
            
        # --- STEP 4: GENERATE DCF SCHEDULE ---
        st.subheader("Projected Free Cash Flows (FCFF)")
        
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
            # Revenue
            next_rev = current_rev * (1 + p_rev_growth[i])
            projected_rev.append(next_rev)
            current_rev = next_rev
            
            # EBIT
            ebit = next_rev * p_ebit_margin[i]
            projected_ebit.append(ebit)
            
            # EBIAT
            ebiat = ebit * (1 - p_tax_rate[i])
            projected_ebiat.append(ebiat)
            
            # Add-backs / Deductions
            da = next_rev * p_da[i]
            capex = next_rev * p_capex[i]
            nwc_change = next_rev * p_nwc[i]
            
            projected_da_val.append(da)
            projected_capex_val.append(capex)
            projected_nwc_val.append(nwc_change)
            
            # FCFF = EBIAT + D&A - CapEx - Change in NWC
            fcff = ebiat + da - capex - nwc_change
            projected_fcff.append(fcff)
            
            # Discounting
            df = 1 / ((1 + ui_wacc) ** (i + 1))
            discount_factors.append(df)
            pv_fcff.append(fcff * df)
            
        dcf_schedule_df = pd.DataFrame({
            "Revenue": projected_rev,
            "EBIT": projected_ebit,
            "EBIAT": projected_ebiat,
            "D&A (+)": projected_da_val,
            "CapEx (-)": projected_capex_val,
            "NWC Change (-)": projected_nwc_val,
            "Unlevered FCF (FCFF)": projected_fcff,
            "Discount Factor": discount_factors,
            "Present Value of FCFF": pv_fcff
        }, index=years).T
        
        st.dataframe(dcf_schedule_df.style.format("{:,.2f}"))
        
        # --- STEP 5: VALUATION OUTPUTS ---
        st.subheader("DCF Valuation Summary")
        
        sum_pv_fcff = sum(pv_fcff)
        
        # Terminal Value calculation (Gordon Growth Model)
        terminal_value = (projected_fcff[-1] * (1 + perpetual_growth)) / (ui_wacc - perpetual_growth) if ui_wacc > perpetual_growth else 0.0
        pv_terminal_value = terminal_value * discount_factors[-1]
        
        enterprise_value = sum_pv_fcff + pv_terminal_value
        implied_equity_value = enterprise_value - total_debt + cash_and_equiv
        implied_stock_price = implied_equity_value / shares_outstanding if shares_outstanding > 0 else 0.0
        
        # Outputs layout
        col_v1, col_v2, col_v3, col_v4 = st.columns(4)
        col_v1.metric("PV of 5Yr Cash Flows", f"${sum_pv_fcff:,.0f}")
        col_v2.metric("PV of Terminal Value", f"${pv_terminal_value:,.0f}")
        col_v3.metric("Implied Enterprise Value", f"${enterprise_value:,.0f}")
        col_v4.metric("Implied Share Price", f"${implied_stock_price:,.2f}")
        
        # Safety Check / Logic Alert
        if ui_wacc <= perpetual_growth:
            st.error("Warning: The WACC must be strictly greater than the Perpetual Growth Rate to generate a mathematically sound terminal value valuation.")
            
        # Graphical representation
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Price Comparison',
            x=['Current Market Price', 'Implied DCF Target Price'],
            y=[current_price, implied_stock_price],
            marker_color=['#1f77b4', '#2ca02c']
        ))
        
        fig.update_layout(
            title_text=f"Valuation Comparison for {ticker_symbol}",
            yaxis_title="Stock Price ($)",
            width=600,
            height=400
        )
        
        st.plotly_chart(fig, use_container_width=False)