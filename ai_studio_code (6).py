import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
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
        padding: 20px; 
        border-radius: 8px; 
        text-align: center;
        margin-bottom: 15px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
    ">
        <span style="color: #9CA3AF; font-size: 0.8rem; letter-spacing: 0.08em; text-transform: uppercase; font-weight: 600;">{label}</span>
        <h2 style="color: {text_color}; font-size: 1.65rem; margin: 8px 0 0 0; font-family: 'Playfair Display', Georgia, serif; font-weight: 500;">{value}</h2>
    </div>
    """

# Helper: Exquisite custom HTML financial statement renderer
def generate_luxury_table(df):
    html = "<div class='table-wrapper' style='overflow-x: auto; margin: 25px 0; border-radius: 8px; border: 1px solid #1F2937;'>"
    html += "<table style='width: 100%; border-collapse: collapse; background-color: #0B0F19; color: #E5E7EB;'>"
    
    # Header Row
    html += "<tr style='border-bottom: 2px solid #C5A880;'>"
    html += "<th style='padding: 12px 16px; text-align: left; background-color: #111827; color: #C5A880; font-family: \"Segoe UI\", sans-serif; font-weight: 600; min-width: 250px;'>Financial Driver</th>"
    for col in df.columns:
        html += f"<th style='padding: 12px 16px; text-align: right; background-color: #111827; color: #F3F4F6; font-family: \"Segoe UI\", sans-serif; font-weight: 500;'>{col}</th>"
    html += "</tr>"
    
    # Body Rows
    for row_idx, row_name in enumerate(df.index):
        is_key_row = "Revenue ($M)" in row_name or "EBIAT ($M)" in row_name or "Unlevered" in row_name
        is_total_row = "Present Value of FCF ($M)" in row_name
        
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
        label_style = "padding: 10px 16px; text-align: left; border-right: 1px solid #1F2937;"
        if is_total_row:
            label_style += " color: #C5A880;"
        html += f"<td style='{label_style}'>{row_name}</td>"
        
        # Value Cells
        for col in df.columns:
            val = df.at[row_name, col]
            cell_style = "padding: 10px 16px; text-align: right; font-family: 'Courier New', monospace;"
            html += f"<td style='{cell_style}'>{val}</td>"
        html += "</tr>"
        
    html += "</table></div>"
    return html

# Helper: Robust SEC DataFrame cleaner to prevent unexpected extraction failure crashes
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

ticker_symbol = st.sidebar.text_input("Ticker Symbol", value="MSFT").upper().strip()
forecast_years = st.sidebar.slider("Forecast Horizon (Years)", min_value=1, max_value=15, value=5)

st.sidebar.markdown("<h3 style='color: #C5A880; font-size: 1.15rem;'>Global Assumptions</h3>", unsafe_allow_html=True)
rf_rate = st.sidebar.number_input("Risk-Free Rate (%)", min_value=0.0, max_value=20.0, value=4.2, step=0.1) / 100
erp = st.sidebar.number_input("Equity Risk Premium (%)", min_value=0.0, max_value=20.0, value=5.5, step=0.1) / 100
perpetual_growth = st.sidebar.number_input("Perpetual Growth Rate (%)", min_value=0.0, max_value=10.0, value=2.0, step=0.1) / 100

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
        financials = ticker.financials.reindex(sorted(ticker.financials.columns), axis=1)
        balance_sheet = ticker.balance_sheet.reindex(sorted(ticker.balance_sheet.columns), axis=1)
        cashflow = ticker.cashflow.reindex(sorted(ticker.cashflow.columns), axis=1)
        return info, financials, balance_sheet, cashflow, None
    except Exception as e:
        return None, None, None, None, str(e)

if ticker_symbol:
    sec_data = load_sec_data(ticker_symbol, sec_email)
    yf_info, yf_financials, yf_balance, yf_cashflow, yf_error = load_market_vars(ticker_symbol)
    
    if yf_error:
        st.error(f"Could not initialize model inputs for ticker {ticker_symbol}.")
    else:
        # Fallback evaluation
        if not sec_data:
            sec_failed = True
        else:
            sec_failed = "error" in sec_data and sec_data["error"] is not None
            
        if sec_failed:
            st.sidebar.warning("SEC lookup offline; using secondary database.")
            company_name = yf_info.get('longName', ticker_symbol)
            cik = "N/A"
        else:
            company_name = sec_data["company_name"]
            cik = sec_data["cik"]
            
        current_price = yf_info.get('currentPrice', 0.0)
        shares_outstanding = yf_info.get('sharesOutstanding', 1.0)
        beta = yf_info.get('beta', 1.0)
        
        # Balance sheet evaluation
        cash_and_equiv = safe_get(yf_balance, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments', 'Cash'], col_idx=-1)
        total_debt = safe_get(yf_balance, ['Total Debt', 'Long Term Debt', 'LongTermDebt'], col_idx=-1)
        if total_debt == 0.0:
            total_debt = safe_get(yf_balance, ['Long Term Debt'], col_idx=-1) + safe_get(yf_balance, ['Current Debt', 'Short Long Term Debt'], col_idx=-1)
        net_debt = max(0.0, total_debt - cash_and_equiv)
        
        # Base driver calculations
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
                rev_vals = yf_financials.loc['Total Revenue'].values
                hist_rev_growth = (rev_vals[-1] / rev_vals[-2]) - 1
            except:
                pass
                
        hist_ebit_margin = latest_ebit / latest_revenue if latest_revenue else 0.20
        hist_tax_rate = latest_tax / latest_ebt if latest_ebt and latest_ebt > 0 else 0.21
        hist_capex_pct = latest_capex / latest_revenue if latest_revenue else 0.04
        hist_da_pct = latest_da / latest_revenue if latest_revenue else 0.04
        hist_nwc_change_pct = 0.01

        # WACC Input parameters
        cost_of_equity = rf_rate + (beta * erp)
        implied_interest_rate = 0.05
        if total_debt > 0 and latest_interest > 0:
            implied_interest_rate = min(latest_interest / total_debt, 0.15)
            
        market_cap = yf_info.get('marketCap', shares_outstanding * current_price)
        total_val = market_cap + total_debt
        weight_equity = market_cap / total_val if total_val > 0 else 1.0
        weight_debt = total_debt / total_val if total_val > 0 else 0.0
        
        st.sidebar.markdown("<h3 style='color: #C5A880; font-size: 1.15rem;'>WACC Matrix</h3>", unsafe_allow_html=True)
        ui_cost_equity = st.sidebar.number_input("Target Cost of Equity (%)", value=float(cost_of_equity*100), step=0.1) / 100
        ui_cost_debt = st.sidebar.number_input("Target Pre-Tax Cost of Debt (%)", value=float(implied_interest_rate*100), step=0.1) / 100
        ui_wacc = (weight_equity * ui_cost_equity) + (weight_debt * ui_cost_debt * (1 - hist_tax_rate))
        st.sidebar.metric("Target WACC", f"{ui_wacc * 100:.2f}%")

        # --- MAIN WORKSPACE ---
        st.markdown(f"<h1 style='font-size: 2.1rem; margin-bottom: 2px;'>{company_name}</h1>", unsafe_allow_html=True)
        st.markdown(f"<span style='color: #9CA3AF; font-size: 0.9rem; letter-spacing: 0.05em; text-transform: uppercase;'>CIK: {cik} | Dynamic Timeline Model</span>", unsafe_allow_html=True)
        st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

        # Build dynamic default dataframe for the drivers (Interactive grid on Main Page)
        proj_cols = [f"Year {i} (P)" for i in range(1, forecast_years + 1)]
        driver_rows = [
            "Revenue Growth Rate (%)",
            "Operating (EBIT) Margin (%)",
            "Effective Tax Rate (%)",
            "CapEx as % of Revenue (%)",
            "D&A as % of Revenue (%)",
            "Change in NWC as % of Revenue (%)"
        ]
        
        default_drivers = {}
        for col_idx, col_lbl in enumerate(proj_cols):
            default_drivers[col_lbl] = [
                hist_rev_growth * 100,
                hist_ebit_margin * 100,
                hist_tax_rate * 100,
                hist_capex_pct * 100,
                hist_da_pct * 100,
                hist_nwc_change_pct * 100
            ]
            
        default_drivers_df = pd.DataFrame(default_drivers, index=driver_rows)
        
        # DISPLAY INTERACTIVE MAIN PAGE INPUT BLOCK
        st.subheader("Model Projections Input Matrix")
        st.markdown("Directly edit driver assumptions below to project performance. Press Enter after editing any cell.")
        
        edited_drivers_df = st.data_editor(
            default_drivers_df,
            use_container_width=True,
            num_rows="fixed",
            key="main_drivers_editor"
        )
        
        # Read edited metrics safely with type-safety checks
        def get_driver_row(df, row_name):
            try:
                return np.array([float(x) for x in df.loc[row_name].values]) / 100.0
            except Exception:
                return np.zeros(forecast_years)

        p_rev_growth = get_driver_row(edited_drivers_df, "Revenue Growth Rate (%)")
        p_ebit_margin = get_driver_row(edited_drivers_df, "Operating (EBIT) Margin (%)")
        p_tax_rate = get_driver_row(edited_drivers_df, "Effective Tax Rate (%)")
        p_capex = get_driver_row(edited_drivers_df, "CapEx as % of Revenue (%)")
        p_da = get_driver_row(edited_drivers_df, "D&A as % of Revenue (%)")
        p_nwc = get_driver_row(edited_drivers_df, "Change in NWC as % of Revenue (%)")

        # --- MODEL GENERATION PIPELINE ---
        hist_columns = [str(col.year) if hasattr(col, 'year') else str(col) for col in yf_financials.columns]
        proj_columns = [f"{int(hist_columns[-1]) + i} (P)" for i in range(1, forecast_years + 1)]
        all_timeline_columns = hist_columns + proj_columns
        
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

        # 1. Populate historical metrics
        num_hist_periods = len(hist_columns)
        for i in range(num_hist_periods):
            col_lbl = hist_columns[i]
            rev = safe_get(yf_financials, ['Total Revenue', 'Revenue'], col_idx=i) / 1e6
            ebit = safe_get(yf_financials, ['Operating Income', 'EBIT'], col_idx=i) / 1e6
            tax = safe_get(yf_financials, ['Tax Provision', 'Income Tax Expense'], col_idx=i) / 1e6
            ebiat = ebit - tax
            da = safe_get(yf_cashflow, ['Depreciation And Amortization', 'Depreciation'], col_idx=i) / 1e6
            capex = abs(safe_get(yf_cashflow, ['Capital Expenditure', 'CapEx'], col_idx=i)) / 1e6
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

        # 2. Populate projected metrics
        current_rev = model_df.at["Revenue ($M)", hist_columns[-1]]
        projected_fcf_list = []
        discount_factors_list = []
        pv_fcf_list = []
        
        for i in range(forecast_years):
            col_lbl = proj_columns[i]
            growth = p_rev_growth[i]
            margin = p_ebit_margin[i]
            tax_rate = p_tax_rate[i]
            capex_pct = p_capex[i]
            da_pct = p_da[i]
            nwc_pct = p_nwc[i]
            
            rev = current_rev * (1 + growth)
            current_rev = rev
            ebit = rev * margin
            tax = ebit * tax_rate
            ebiat = ebit - tax
            da = rev * da_pct
            capex = rev * capex_pct
            nwc_change = rev * nwc_pct
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

        # Format DataFrame values
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
                    formatted_df.at[row, col] = f"${float(val):,.1f}"

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

        # --- EXECUTIVE KPIS ---
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        with col_c1:
            st.markdown(render_luxury_card("Implied Target Price", f"${implied_stock_price:,.2f}", is_accent=True), unsafe_allow_html=True)
        with col_c2:
            st.markdown(render_luxury_card("Current Price", f"${current_price:,.2f}"), unsafe_allow_html=True)
        with col_c3:
            st.markdown(render_luxury_card("Enterprise Value", f"${enterprise_value:,.1f}M"), unsafe_allow_html=True)
        with col_c4:
            st.markdown(render_luxury_card("Assumed WACC", f"{ui_wacc*100:.2f}%"), unsafe_allow_html=True)

        # --- TIMELINE VIEW ---
        st.subheader("Integrated 3-Statement Forecast Timeline")
        st.markdown(generate_luxury_table(formatted_df), unsafe_allow_html=True)

        # Plotly Valuation Comparison Chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            name='Price Comparison',
            x=['Current Market Price', 'Implied DCF Value'],
            y=[current_price, implied_stock_price],
            marker_color=['#4B5563', '#C5A880'],
            width=[0.4, 0.4]
        ))
        fig.update_layout(
            paper_bgcolor='#090D16',
            plot_bgcolor='#0B0F19',
            font_color='#E5E7EB',
            xaxis=dict(showgrid=False, linecolor='#374151'),
            yaxis=dict(showgrid=True, gridcolor='#1F2937', linecolor='#374151'),
            margin=dict(l=40, r=40, t=40, b=40),
            height=350,
            width=650
        )
        st.plotly_chart(fig, use_container_width=False)

        # --- REFERENCE SHEETS ---
        st.subheader("Filing Verification Worksheets")
        st.markdown("Raw source statements loaded dynamically for verification.")
        
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