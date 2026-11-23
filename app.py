"""
app.py
Streamlit Dashboard for Analyzing Network Monitoring Device (NMD) Readings of Transformers.
Features:
- Excel file upload (Sheets: DB, Names, Poles, Solar Customers)
- Comprehensive CT Polarity Analysis (> 90% threshold rule, Case 1 & Case 2 curve analysis)
- Transformer & Feeder Profiles (Currents, Voltages, Feeder Voltage Drop)
- Feeder Topology & Pole Hierarchy
- Solar Customer Analysis (min(Inverter, Installed))
- Interactive Plotly Visualizations & Export Options
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, time
import io
import os
import re
import importlib

import excel_parser
import ct_polarity_analyzer
import sample_data_generator
import load_profile_analyzer
import feeder_topology_analyzer
import voltage_profile_analyzer
import report_generator
import mitigation_solutions_engine

# Force reload helper modules so hot-reloading always uses fresh code
importlib.reload(excel_parser)
importlib.reload(ct_polarity_analyzer)
importlib.reload(sample_data_generator)
importlib.reload(load_profile_analyzer)
importlib.reload(feeder_topology_analyzer)
importlib.reload(voltage_profile_analyzer)
importlib.reload(report_generator)
importlib.reload(mitigation_solutions_engine)

from excel_parser import parse_nmd_excel
from ct_polarity_analyzer import analyze_transformer_ct_polarities
from sample_data_generator import generate_nmd_excel
from load_profile_analyzer import compute_daily_load_profiles
from feeder_topology_analyzer import (
    build_network_topology,
    create_network_schematic_figure,
    get_network_summary_dataframe,
    get_feeder_display_name,
    get_feeder_name_lookup,
    clean_feeder_name
)
from voltage_profile_analyzer import (
    analyze_all_network_voltages,
    compute_diurnal_voltage_profile,
    create_diurnal_voltage_chart,
    create_network_voltage_comparison_chart,
    create_voltage_drop_delta_chart
)
from report_generator import generate_word_report
from mitigation_solutions_engine import analyze_mitigation_solutions

# Page configuration
logo_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leco_logo.png")
if not os.path.exists(logo_file):
    logo_file = "leco_logo.png" if os.path.exists("leco_logo.png") else None

st.set_page_config(
    page_title="LECO NMD Transformer Analysis Dashboard",
    page_icon=logo_file or "⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sidebar: Brand, Dark Mode Toggle & Navigation
with st.sidebar:
    if logo_file:
        st.image(logo_file, width=110)
    else:
        st.image("https://img.icons8.com/fluency/96/electricity.png", width=64)
    st.markdown("### TF Analyzer")
    st.markdown("**LECO Network Monitoring System**")
    
    # 🌙 Dark Mode Toggle Switch
    dark_mode = st.toggle(
        "🌙 Dark Mode",
        value=st.session_state.get("dark_mode", False),
        key="dark_mode",
        help="Switch between Light and Dark visual themes across all tabs and charts"
    )
    st.markdown("---")

# Themed Plotly Chart Wrapper (Dynamically adapts all charts to Light / Dark Mode)
orig_plotly_chart = st.plotly_chart

def themed_plotly_chart(fig, *args, **kwargs):
    if fig is not None and hasattr(fig, "update_layout"):
        if dark_mode:
            # 1. Base dark layout & canvas
            fig.update_layout(
                template="plotly_dark",
                paper_bgcolor="#0F172A",
                plot_bgcolor="#1E293B",
                font=dict(color="#E2E8F0", family="sans-serif")
            )
            # 2. X and Y axes styling (crisp text, visible grid lines)
            fig.update_xaxes(
                color="#E2E8F0",
                tickfont=dict(color="#CBD5E1", size=11),
                title_font=dict(color="#F8FAFC", size=12),
                gridcolor="#334155",
                zerolinecolor="#475569"
            )
            fig.update_yaxes(
                color="#E2E8F0",
                tickfont=dict(color="#CBD5E1", size=11),
                title_font=dict(color="#F8FAFC", size=12),
                gridcolor="#334155",
                zerolinecolor="#475569"
            )
            # 3. Legend
            if hasattr(fig.layout, "legend") and fig.layout.legend:
                fig.update_layout(legend=dict(font=dict(color="#E2E8F0"), bgcolor="rgba(15, 23, 42, 0.75)"))

            # 4. Shapes (e.g., daytime solar window, thresholds)
            if hasattr(fig.layout, "shapes") and fig.layout.shapes:
                for s in fig.layout.shapes:
                    fc = str(getattr(s, "fillcolor", "") or "").lower()
                    if "254, 240, 138" in fc or "254, 243, 199" in fc or "yellow" in fc:
                        s.fillcolor = "rgba(245, 158, 11, 0.14)"
                    elif "37, 99, 235" in fc or "59, 130, 246" in fc or "blue" in fc:
                        s.fillcolor = "rgba(59, 130, 246, 0.15)"
                    elif "16, 185, 129" in fc or "green" in fc:
                        s.fillcolor = "rgba(16, 185, 129, 0.12)"

            # 5. Annotations (peak badges, rating lines, solar window text)
            if hasattr(fig.layout, "annotations") and fig.layout.annotations:
                for a in fig.layout.annotations:
                    bg = str(getattr(a, "bgcolor", "") or "").lower()
                    if "eff6ff" in bg or "dbeafe" in bg:
                        a.bgcolor = "#0F2042"
                        a.bordercolor = "#3B82F6"
                        if hasattr(a, "font") and a.font:
                            a.font.color = "#93C5FD"
                    elif "fef2f2" in bg or "fee2e2" in bg:
                        a.bgcolor = "#2A0E0E"
                        a.bordercolor = "#EF4444"
                        if hasattr(a, "font") and a.font:
                            a.font.color = "#FCA5A5"
                    elif "ecfdf5" in bg or "d1fae5" in bg:
                        a.bgcolor = "#062B1D"
                        a.bordercolor = "#10B981"
                        if hasattr(a, "font") and a.font:
                            a.font.color = "#6EE7B7"
                    elif "fffbeb" in bg or "fef3c7" in bg:
                        a.bgcolor = "#271C0C"
                        a.bordercolor = "#F59E0B"
                        if hasattr(a, "font") and a.font:
                            a.font.color = "#FCD34D"
                    else:
                        if hasattr(a, "font") and a.font:
                            col = getattr(a.font, "color", None)
                            col_str = str(col).lower() if col else ""
                            if any(c in col_str for c in ["#059669", "#065f46", "#047857"]):
                                a.font.color = "#34D399"
                            elif any(c in col_str for c in ["#ef4444", "#dc2626", "#b91c1c", "#991b1b"]):
                                a.font.color = "#F87171"
                            elif any(c in col_str for c in ["#d97706", "#b45309", "#92400e", "#f59e0b"]):
                                a.font.color = "#FBBF24"
                            elif any(c in col_str for c in ["#2563eb", "#1d4ed8", "#1e40af", "#1e3a8a"]):
                                a.font.color = "#60A5FA"
                            elif not col or col_str in ["#1e293b", "#334155", "#0f172a", "#4b5563", "#64748b", "black", "#000000", "none", ""]:
                                a.font.color = "#E2E8F0"
                        elif not hasattr(a, "font") or not a.font:
                            a.font = dict(color="#E2E8F0")

            # 6. Indicators (Gauges)
            for t in fig.data:
                if t.type == "indicator":
                    if hasattr(t, "number") and t.number and hasattr(t.number, "font"):
                        t.number.font.color = "#F8FAFC"
                    if hasattr(t, "title") and t.title and hasattr(t.title, "font"):
                        t.title.font.color = "#E2E8F0"
                    if hasattr(t, "gauge") and t.gauge:
                        if hasattr(t.gauge, "axis") and t.gauge.axis:
                            t.gauge.axis.tickcolor = "#94A3B8"
        else:
            fig.update_layout(
                template="plotly_white",
                paper_bgcolor="rgba(255, 255, 255, 0.0)",
                plot_bgcolor="rgba(248, 250, 252, 0.5)",
                font=dict(color="#0F172A", family="sans-serif")
            )
            fig.update_xaxes(
                color="#0F172A",
                tickfont=dict(color="#334155"),
                title_font=dict(color="#0F172A"),
                gridcolor="#E2E8F0"
            )
            fig.update_yaxes(
                color="#0F172A",
                tickfont=dict(color="#334155"),
                title_font=dict(color="#0F172A"),
                gridcolor="#E2E8F0"
            )
    return orig_plotly_chart(fig, *args, **kwargs)

st.plotly_chart = themed_plotly_chart

# Custom CSS for modern styling (Light Mode Baseline)
base_css = """
<style>
    .main-header {
        font-size: 2.1rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.2rem;
    }
    .kpi-card {
        background-color: #F8FAFC;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 5px solid #2563EB;
        box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        margin-bottom: 10px;
    }
    .kpi-title {
        font-size: 0.85rem;
        font-weight: 600;
        color: #64748B;
        text-transform: uppercase;
    }
    .kpi-value {
        font-size: 1.8rem;
        font-weight: 700;
        color: #0F172A;
    }
    .alert-banner-green {
        background-color: #ECFDF5;
        border: 1px solid #10B981;
        border-left: 8px solid #059669;
        padding: 16px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    .alert-banner-red {
        background-color: #FEF2F2;
        border: 1px solid #EF4444;
        border-left: 8px solid #DC2626;
        padding: 16px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    /* High contrast selectbox text in Light Mode baseline */
    div[data-testid="stSelectbox"] input,
    div.stSelectbox input {
        caret-color: transparent !important;
        cursor: pointer !important;
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
        font-weight: 500 !important;
    }
    div[data-testid="stSelectboxVirtualDropdown"] li,
    div[data-testid="stSelectboxVirtualDropdown"] [data-item-hl] {
        color: #0F172A !important;
        -webkit-text-fill-color: #0F172A !important;
    }
    .alert-banner-orange {
        background-color: #FFFBEB;
        border: 1px solid #F59E0B;
        border-left: 8px solid #D97706;
        padding: 16px 20px;
        border-radius: 8px;
        margin-bottom: 20px;
    }
    /* Non-editable selectbox dropdowns: pointer cursor, no text editing cursor, no text selection */
    div[data-baseweb="select"] input {
        caret-color: transparent !important;
        cursor: pointer !important;
        user-select: none !important;
    }
</style>
"""
st.markdown(base_css, unsafe_allow_html=True)

# Dark Mode CSS Overrides (Injected when Dark Mode toggle is active)
if dark_mode:
    dark_css = """
    <style>
        /* 1. Global App Typography & Background in Dark Mode */
        .stApp {
            background-color: #0B1120 !important;
            color: #E2E8F0 !important;
        }
        .stApp p,
        .stApp span,
        .stApp label,
        .stApp li,
        .stApp div[data-testid="stMarkdownContainer"] p,
        .stApp div[data-testid="stMarkdownContainer"] span,
        .stApp div[data-testid="stMarkdownContainer"] li {
            color: #E2E8F0 !important;
        }

        /* 2. Global Headings */
        .stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6,
        .stApp [data-testid="stHeadingWithActionElements"] h1,
        .stApp [data-testid="stHeadingWithActionElements"] h2,
        .stApp [data-testid="stHeadingWithActionElements"] h3,
        .stApp [data-testid="stHeadingWithActionElements"] h4 {
            color: #F8FAFC !important;
        }

        /* 3. Header & Sub-header */
        .main-header {
            color: #93C5FD !important;
        }
        .sub-header {
            color: #CBD5E1 !important;
        }

        /* 4. Captions & Secondary Text */
        .stApp small,
        .stApp [data-testid="stCaptionContainer"],
        .stApp [data-testid="stCaptionContainer"] p,
        .stApp .stCaption {
            color: #94A3B8 !important;
        }

        /* 5. SIDEBAR: Complete high-contrast styling for all text & widgets */
        [data-testid="stSidebar"] {
            background-color: #0F172A !important;
            border-right: 1px solid #1E293B !important;
            color: #E2E8F0 !important;
        }
        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] h4 {
            color: #60A5FA !important;
            font-weight: 700 !important;
        }
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] span,
        [data-testid="stSidebar"] label,
        [data-testid="stSidebar"] small,
        [data-testid="stSidebar"] div[data-testid="stMarkdownContainer"] p {
            color: #CBD5E1 !important;
        }
        [data-testid="stSidebar"] [data-testid="stRadio"] label p,
        [data-testid="stSidebar"] [data-testid="stRadio"] label span {
            color: #F1F5F9 !important;
            font-weight: 500 !important;
        }
        [data-testid="stSidebar"] [data-testid="stSelectbox"] label p {
            color: #F1F5F9 !important;
            font-weight: 500 !important;
        }
        [data-testid="stHeader"] {
            background-color: rgba(11, 17, 32, 0.8) !important;
        }

        /* 6. TABS: Crisp, legible tab headers in Dark Mode */
        [data-baseweb="tab-list"] {
            background-color: transparent !important;
            border-bottom: 1px solid #334155 !important;
        }
        button[data-baseweb="tab"],
        button[data-baseweb="tab"] *,
        button[data-baseweb="tab"] p,
        button[data-baseweb="tab"] div {
            color: #94A3B8 !important;
            font-size: 0.95rem !important;
        }
        button[data-baseweb="tab"]:hover,
        button[data-baseweb="tab"]:hover * {
            color: #F8FAFC !important;
        }
        button[data-baseweb="tab"][aria-selected="true"],
        button[data-baseweb="tab"][aria-selected="true"] *,
        button[data-baseweb="tab"][aria-selected="true"] p {
            color: #60A5FA !important;
            font-weight: 700 !important;
            border-bottom-color: #3B82F6 !important;
        }

        /* 7. KPI Cards in Dark Mode */
        .kpi-card {
            background-color: #1E293B !important;
            border-left: 5px solid #3B82F6 !important;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.5) !important;
        }
        .kpi-card div, .kpi-card strong, .kpi-card p {
            color: #E2E8F0 !important;
        }
        .kpi-title {
            color: #94A3B8 !important;
        }
        .kpi-value {
            color: #F8FAFC !important;
        }

        /* 8. ALERT BANNERS */
        .alert-banner-green {
            background-color: #062B1D !important;
            border: 1px solid #059669 !important;
            border-left: 8px solid #10B981 !important;
        }
        .alert-banner-green h4, .alert-banner-green h4 * {
            color: #6EE7B7 !important;
        }
        .alert-banner-green p, .alert-banner-green span, .alert-banner-green b {
            color: #D1FAE5 !important;
        }

        .alert-banner-red {
            background-color: #2A0E0E !important;
            border: 1px solid #B91C1C !important;
            border-left: 8px solid #EF4444 !important;
        }
        .alert-banner-red h4, .alert-banner-red h4 * {
            color: #FCA5A5 !important;
        }
        .alert-banner-red p, .alert-banner-red span, .alert-banner-red b {
            color: #FEE2E2 !important;
        }

        .alert-banner-orange {
            background-color: #271C0C !important;
            border: 1px solid #B45309 !important;
            border-left: 8px solid #F59E0B !important;
        }
        .alert-banner-orange h4, .alert-banner-orange h4 * {
            color: #FCD34D !important;
        }
        .alert-banner-orange p, .alert-banner-orange span, .alert-banner-orange b {
            color: #FEF3C7 !important;
        }

        /* 9. NOTICE / CAPACITY NOTIFICATION BANNERS */
        div[style*="background-color: #FFFBEB"] {
            background-color: #271C0C !important;
            border: 1px solid #B45309 !important;
            border-left: 6px solid #F59E0B !important;
        }
        div[style*="background-color: #FFFBEB"] * {
            color: #FEF3C7 !important;
        }
        div[style*="background-color: #FFFBEB"] span[style*="color: #92400E"] {
            color: #FCD34D !important;
            font-weight: 700 !important;
        }

        div[style*="background-color: #ECFDF5"] {
            background-color: #062B1D !important;
            border: 1px solid #059669 !important;
            border-left: 6px solid #10B981 !important;
        }
        div[style*="background-color: #ECFDF5"] * {
            color: #D1FAE5 !important;
        }
        div[style*="background-color: #ECFDF5"] span[style*="color: #065F46"] {
            color: #34D399 !important;
            font-weight: 700 !important;
        }

        /* 10. INLINE DIRECT SOLUTIONS & CALLOUTS */
        div[style*="background: #EFF6FF"], div[style*="background-color: #EFF6FF"] {
            background-color: #0F2042 !important;
            border: 1px solid #1E3A8A !important;
            border-left: 5px solid #3B82F6 !important;
        }
        div[style*="background: #EFF6FF"] *, div[style*="background-color: #EFF6FF"] * {
            color: #DBEAFE !important;
        }
        div[style*="background: #EFF6FF"] span[style*="color: #1E40AF"] {
            color: #60A5FA !important;
        }
        div[style*="background: #EFF6FF"] span[style*="color: #0F172A"],
        div[style*="background: #EFF6FF"] span[style*="color: #1E293B"] {
            color: #F8FAFC !important;
        }

        div[style*="background-color: #FEF2F2"] {
            background-color: #2A0E0E !important;
            border-color: #EF4444 !important;
        }
        div[style*="background-color: #FEF2F2"] * {
            color: #FECACA !important;
        }

        div[style*="background: #F8FAFC"], div[style*="background-color: #F8FAFC"] {
            background-color: #1E293B !important;
            border-color: #334155 !important;
        }
        div[style*="background: #F8FAFC"] *, div[style*="background-color: #F8FAFC"] * {
            color: #E2E8F0 !important;
        }
        div[style*="background: #F8FAFC"] h4 {
            color: #F8FAFC !important;
        }

        /* 11. EXPANDERS */
        div[data-testid="stExpander"] {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
        }
        div[data-testid="stExpander"] summary,
        div[data-testid="stExpander"] summary * {
            color: #F8FAFC !important;
            font-weight: 600 !important;
        }
        div[data-testid="stExpander"] svg {
            fill: #94A3B8 !important;
        }

        /* 12. METRICS */
        div[data-testid="stMetricValue"], div[data-testid="stMetricValue"] * {
            color: #F8FAFC !important;
        }
        div[data-testid="stMetricLabel"], div[data-testid="stMetricLabel"] * {
            color: #94A3B8 !important;
        }

        /* 13. CODE TAGS & MARKDOWN HIGHLIGHTS */
        code,
        .stMarkdown code,
        div[data-testid="stMarkdownContainer"] code {
            background-color: #1E293B !important;
            color: #60A5FA !important;
            border: 1px solid #334155 !important;
            padding: 2px 7px !important;
            border-radius: 4px !important;
            font-weight: 600 !important;
        }

        /* 14. FORM WIDGETS, SELECTBOXES & DROPDOWN LISTS */
        /* Selectbox Main Container: works with React-Aria, BaseWeb & Emotion classes */
        div[data-testid="stSelectbox"],
        div.stSelectbox {
            color: #F8FAFC !important;
        }

        div[data-testid="stSelectbox"] > div,
        div[data-testid="stSelectbox"] [class*="e1oobldh0"],
        div[data-testid="stSelectbox"] div[data-baseweb="select"],
        div[data-testid="stSelectbox"] div[data-baseweb="select"] > div,
        div[data-testid="stSelectbox"] div[data-baseweb="select"] div,
        div.stSelectbox > div,
        div.stSelectbox [class*="e1oobldh0"],
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] > div,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] [class*="e1oobldh0"] {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            color: #F8FAFC !important;
        }

        div[data-testid="stSelectbox"] > div:hover,
        div[data-testid="stSelectbox"] [class*="e1oobldh0"]:hover,
        div.stSelectbox > div:hover,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] > div:hover {
            border-color: #3B82F6 !important;
        }

        /* Selectbox Input & Selected Value Display: Pure crisp white text */
        div[data-testid="stSelectbox"] input,
        div[data-testid="stSelectbox"] [class*="e1oobldh1"],
        div[data-testid="stSelectbox"] div[data-baseweb="select"] input,
        div.stSelectbox input,
        div.stSelectbox [class*="e1oobldh1"],
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] input,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] [class*="e1oobldh1"],
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] span,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] div {
            color: #F8FAFC !important;
            -webkit-text-fill-color: #F8FAFC !important;
            background-color: transparent !important;
            font-weight: 500 !important;
        }

        div[data-testid="stSelectbox"] input::placeholder,
        div[data-testid="stSelectbox"] [class*="e1oobldh1"]::placeholder,
        div.stSelectbox input::placeholder,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] input::placeholder {
            color: #CBD5E1 !important;
            -webkit-text-fill-color: #CBD5E1 !important;
        }

        /* Selectbox Chevron & Clear Icons */
        div[data-testid="stSelectbox"] svg,
        div[data-testid="stSelectbox"] [class*="e1oobldh3"] svg,
        div.stSelectbox svg,
        [data-testid="stSidebar"] div[data-testid="stSelectbox"] svg {
            fill: #CBD5E1 !important;
            color: #CBD5E1 !important;
        }

        /* Dropdown Virtual Popup Menu (When Opened) */
        div[data-testid="stSelectboxVirtualDropdown"],
        div[data-testid="stSelectboxVirtualDropdown"] [class*="e1oobldh4"],
        div[data-testid="stSelectboxVirtualDropdown"] [class*="e1oobldh5"],
        div[data-testid="stSelectboxVirtualDropdown"] ul,
        div[data-baseweb="popover"],
        div[data-baseweb="popover"] > div,
        div[data-baseweb="menu"],
        ul[role="listbox"],
        ul[aria-label="Selectbox options"] {
            background-color: #0F172A !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.7) !important;
        }

        /* Dropdown Menu Items / Option Rows */
        div[data-testid="stSelectboxVirtualDropdown"] li,
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"],
        div[data-testid="stSelectboxVirtualDropdown"] [class*="e1oobldh7"],
        li[role="option"] {
            background-color: #0F172A !important;
            color: #F8FAFC !important;
            font-weight: 500 !important;
        }

        div[data-testid="stSelectboxVirtualDropdown"] [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] [class*="e1oobldh8"],
        li[role="option"] * {
            color: #F8FAFC !important;
            -webkit-text-fill-color: #F8FAFC !important;
        }

        /* Dropdown Menu Item Hover / Focus / Active State */
        div[data-testid="stSelectboxVirtualDropdown"] li:hover,
        div[data-testid="stSelectboxVirtualDropdown"] li[data-hovered],
        div[data-testid="stSelectboxVirtualDropdown"] li[data-focused],
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover,
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"],
        li[role="option"]:hover,
        li[role="option"][aria-selected="true"] {
            background-color: #1E293B !important;
            color: #60A5FA !important;
        }

        div[data-testid="stSelectboxVirtualDropdown"] li:hover [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] li[data-hovered] [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] li[data-focused] [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"]:hover [data-item-hl],
        div[data-testid="stSelectboxVirtualDropdown"] [role="option"][aria-selected="true"] [data-item-hl],
        li[role="option"]:hover *,
        li[role="option"][aria-selected="true"] * {
            background-color: #1E293B !important;
            color: #60A5FA !important;
            -webkit-text-fill-color: #60A5FA !important;
            font-weight: 600 !important;
        }

        /* Number Inputs & Text Inputs */
        div[data-testid="stNumberInput"] div[data-baseweb="input"],
        div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
        div[data-testid="stNumberInput"] div[data-baseweb="input"] div,
        div[data-testid="stNumberInput"] input,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="input"],
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="input"] > div,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] div[data-baseweb="input"] div,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] input {
            background-color: #1E293B !important;
            color: #F8FAFC !important;
            border-color: #334155 !important;
            -webkit-text-fill-color: #F8FAFC !important;
        }
        div[data-testid="stNumberInput"] button,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] button {
            background-color: #1E293B !important;
            border-color: #334155 !important;
            color: #CBD5E1 !important;
        }
        div[data-testid="stNumberInput"] button:hover,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] button:hover {
            background-color: #334155 !important;
        }
        div[data-testid="stNumberInput"] button svg,
        [data-testid="stSidebar"] div[data-testid="stNumberInput"] button svg {
            fill: #CBD5E1 !important;
        }
        div[data-testid="stTextInput"] div[data-baseweb="input"],
        div[data-testid="stTextInput"] div[data-baseweb="input"] > div,
        div[data-testid="stTextInput"] div[data-baseweb="input"] div,
        div[data-testid="stTextInput"] input {
            background-color: #1E293B !important;
            color: #F8FAFC !important;
            border-color: #334155 !important;
            -webkit-text-fill-color: #F8FAFC !important;
        }
        div[data-testid="stSlider"] * {
            color: #CBD5E1 !important;
        }
        div[data-testid="stRadio"] label,
        div[data-testid="stRadio"] label p,
        div[data-testid="stRadio"] label span,
        div[data-testid="stRadio"] div[role="radiogroup"] * {
            color: #F1F5F9 !important;
        }

        /* 15. FILE UPLOADER IN DARK MODE */
        div[data-testid="stFileUploader"] {
            color: #F8FAFC !important;
        }
        div[data-testid="stFileUploader"] label,
        div[data-testid="stFileUploader"] label p {
            color: #F1F5F9 !important;
            font-weight: 600 !important;
        }
        div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"],
        div[data-testid="stFileUploader"] section,
        div[data-testid="stFileUploader"] [class*="e12r9z2m0"],
        .stFileUploader section,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] section {
            background-color: #1E293B !important;
            border: 1.5px dashed #3B82F6 !important;
            border-radius: 10px !important;
            color: #F8FAFC !important;
            padding: 14px !important;
        }
        div[data-testid="stFileUploader"] section[data-testid="stFileUploaderDropzone"]:hover,
        div[data-testid="stFileUploader"] section:hover,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] section:hover {
            border-color: #60A5FA !important;
            background-color: #24344D !important;
        }
        div[data-testid="stFileUploader"] button,
        div[data-testid="stFileUploader"] section button,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] button {
            background-color: #0F172A !important;
            border: 1px solid #3B82F6 !important;
            color: #60A5FA !important;
            border-radius: 6px !important;
            font-weight: 600 !important;
        }
        div[data-testid="stFileUploader"] button:hover,
        div[data-testid="stFileUploader"] section button:hover,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] button:hover {
            background-color: #1E3A8A !important;
            color: #FFFFFF !important;
            border-color: #60A5FA !important;
        }
        div[data-testid="stFileUploader"] button svg,
        div[data-testid="stFileUploader"] section button svg,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] button svg {
            fill: #60A5FA !important;
            color: #60A5FA !important;
        }
        div[data-testid="stFileUploader"] button:hover svg,
        div[data-testid="stFileUploader"] section button:hover svg,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] button:hover svg {
            fill: #FFFFFF !important;
            color: #FFFFFF !important;
        }
        div[data-testid="stFileUploader"] small,
        div[data-testid="stFileUploader"] span,
        div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzoneInstructions"],
        div[data-testid="stFileUploader"] div[data-testid="stFileUploaderDropzoneInstructions"] *,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] small,
        [data-testid="stSidebar"] div[data-testid="stFileUploader"] span {
            color: #CBD5E1 !important;
        }
        div[data-testid="stFileUploaderFile"],
        div[data-testid="stFileUploaderUploadedFiles"],
        [data-testid="stSidebar"] div[data-testid="stFileUploaderFile"] {
            background-color: #1E293B !important;
            border: 1px solid #334155 !important;
            color: #F8FAFC !important;
            border-radius: 6px !important;
        }
        div[data-testid="stFileUploaderFile"] * {
            color: #F8FAFC !important;
        }
        div[data-testid="stFileUploaderFile"] button svg {
            fill: #EF4444 !important;
        }

        /* 16. BUTTONS & DOWNLOAD BUTTONS */
        .stButton > button, div[data-testid="stDownloadButton"] > button {
            background-color: #1E3A8A !important;
            color: #FFFFFF !important;
            border: 1px solid #3B82F6 !important;
        }
        .stButton > button:hover, div[data-testid="stDownloadButton"] > button:hover {
            background-color: #2563EB !important;
            border-color: #60A5FA !important;
        }
        .stButton > button p, div[data-testid="stDownloadButton"] > button p {
            color: #FFFFFF !important;
        }

        /* 15. DIVIDERS & MISC */
        hr {
            border-color: #334155 !important;
        }
    </style>
    """
    st.markdown(dark_css, unsafe_allow_html=True)

# Enforce read-only attribute on selectbox inputs so text cannot be edited
st.html("""
<script>
function enforceReadonlySelects() {
    const inputs = document.querySelectorAll('div[data-testid="stSelectbox"] input, div.stSelectbox input, div[data-baseweb="select"] input');
    inputs.forEach(input => {
        if (!input.hasAttribute('readonly')) {
            input.setAttribute('readonly', 'true');
        }
    });
}
enforceReadonlySelects();
if (!window._readonlySelectObserver) {
    window._readonlySelectObserver = new MutationObserver(enforceReadonlySelects);
    window._readonlySelectObserver.observe(document.body, { childList: true, subtree: true });
}
</script>
""", unsafe_allow_javascript=True)


# Sidebar: Data Source & Settings
with st.sidebar:
    st.markdown("#### 📂 1. Select Data Source")
    data_mode = st.radio(
        "Choose Data Input Mode:",
        ["Upload Excel File", "Load Built-in Demo Dataset"],
        index=1
    )
    
    parsed_data = None
    
    if data_mode == "Upload Excel File":
        uploaded_file = st.file_uploader(
            "Upload NMD Excel File (.xlsx, .xls):",
            type=["xlsx", "xls"],
            help="Excel workbook with DB, Names, Poles, and Solar Customers sheets."
        )
        if uploaded_file is not None:
            with st.spinner("Parsing Excel file sheets..."):
                parsed_data = parse_nmd_excel(uploaded_file)
                if parsed_data["status"] == "error":
                    st.error(parsed_data["error_message"])
                    parsed_data = None
                else:
                    st.success("File uploaded and parsed successfully!")
    else:
        demo_scenario = st.selectbox(
            "Select Demo / Sample Dataset:",
            [
                "Scenario 1: Normal (All CTs Correct)",
                "Scenario 2: Phase A CT Reversed",
                "Scenario 3: All 3 CTs Reversed",
                "Scenario 4: Phase B & C CTs Reversed"
            ]
        )
        scenario_map = {
            "Scenario 1: Normal (All CTs Correct)": "Sample_NMD_Normal_30Days.xlsx",
            "Scenario 2: Phase A CT Reversed": "Sample_NMD_PhaseA_Reversed_30Days.xlsx",
            "Scenario 3: All 3 CTs Reversed": "Sample_NMD_All_Reversed_30Days.xlsx",
            "Scenario 4: Phase B & C CTs Reversed": "Sample_NMD_PhaseBC_Reversed_30Days.xlsx"
        }
        target_file = scenario_map[demo_scenario]
        if os.path.exists(target_file):
            parsed_data = parse_nmd_excel(target_file)
        else:
            with st.spinner("Generating sample data..."):
                sc_key = "normal"
                if "Phase A" in demo_scenario:
                    sc_key = "phase_a_reversed"
                elif "All 3" in demo_scenario:
                    sc_key = "all_reversed"
                elif "Phase B & C" in demo_scenario:
                    sc_key = "phase_bc_reversed"
                raw_bytes = generate_nmd_excel(sc_key, num_days=30)
                parsed_data = parse_nmd_excel(raw_bytes)

    st.markdown("---")
    st.markdown("#### ⚙️ 2. Polarity Analysis Settings")
    threshold_val = st.slider(
        "Statistical Dominance Threshold (%)",
        min_value=30.0,
        max_value=95.0,
        value=50.0,
        step=5.0,
        help="Percentage of nighttime intervals required to trigger a systemic Failure Mode (Default: 50%)."
    )
    
    col_n1, col_n2 = st.columns(2)
    with col_n1:
        night_start = st.number_input("Night Start (24h)", min_value=18, max_value=23, value=21, step=1)
    with col_n2:
        night_end = st.number_input("Night End (24h)", min_value=3, max_value=8, value=5, step=1)

    col_t1, col_t2 = st.columns(2)
    with col_t1:
        day_start = st.text_input("Day Start", value="06:00")
    with col_t2:
        day_end = st.text_input("Day End", value="18:00")

    st.markdown("---")
    st.markdown("#### ⚡ 3. Transformer Rating")
    rating_options = [
        "50 kVA",
        "100 kVA",
        "160 kVA",
        "250 kVA",
        "400 kVA",
        "630 kVA",
        "Custom"
    ]

    has_excel_cap = False
    excel_cap_val = None
    excel_raw_val = ""

    if parsed_data is not None:
        has_excel_cap = parsed_data.get("capacity_from_excel", False)
        excel_cap_val = parsed_data.get("transformer_capacity_kva")
        excel_raw_val = parsed_data.get("transformer_capacity_raw", "")

    # Detect dataset source change to auto-set selection once per dataset
    if data_mode == "Upload Excel File":
        curr_data_src = f"up_{uploaded_file.name}" if ('uploaded_file' in locals() and uploaded_file is not None) else "upload_none"
    else:
        curr_data_src = f"demo_{demo_scenario}" if 'demo_scenario' in locals() else "demo_none"
    if st.session_state.get("last_data_source") != curr_data_src:
        st.session_state["last_data_source"] = curr_data_src
        st.session_state[f"cap_confirmed_{curr_data_src}"] = False
        if has_excel_cap and excel_cap_val:
            std_opt = f"{int(excel_cap_val)} kVA"
            if std_opt in rating_options:
                st.session_state["tf_rating_dropdown"] = std_opt
            else:
                st.session_state["tf_rating_dropdown"] = "Custom"
                st.session_state["custom_kva_str"] = f"{excel_cap_val:g}"
        else:
            st.session_state["tf_rating_dropdown"] = "160 kVA"

    def on_cap_change():
        st.session_state[f"cap_confirmed_{curr_data_src}"] = True

    curr_choice = st.session_state.get("tf_rating_dropdown", "160 kVA")
    default_idx = rating_options.index(curr_choice) if curr_choice in rating_options else 2

    selected_rating_str = st.selectbox(
        "Transformer Rating (kVA)",
        rating_options,
        index=default_idx,
        filter_mode=None,
        key="tf_rating_dropdown",
        on_change=on_cap_change,
        help="Select nominal rated capacity of the distribution transformer. Choose 'Custom' to type a custom value."
    )
    if selected_rating_str == "Custom":
        custom_input = st.text_input(
            "Type Custom Rating (kVA):",
            value=st.session_state.get("custom_kva_str", ""),
            placeholder="Type kVA (e.g. 500)",
            help="Type your custom transformer rating in kVA and press Enter."
        )
        if custom_input.strip():
            st.session_state["custom_kva_str"] = custom_input.strip()
            num_match = re.search(r'(\d+(?:\.\d+)?)', custom_input)
            if num_match and float(num_match.group(1)) > 0:
                rated_cap = float(num_match.group(1))
                st.session_state[f"cap_confirmed_{curr_data_src}"] = True
                st.caption(f"✓ Active Transformer Rating: **{rated_cap:.0f} kVA**")
            else:
                st.warning("⚠️ Please type a valid numeric rating (e.g. 500). Using 160 kVA.")
                rated_cap = 160.0
        else:
            st.info("⌨️ Type your custom transformer rating in kVA above (e.g. 500).")
            rated_cap = 160.0
    else:
        rated_cap = float(selected_rating_str.split()[0])
        if selected_rating_str != "160 kVA":
            st.session_state[f"cap_confirmed_{curr_data_src}"] = True

    user_has_selected = bool(st.session_state.get(f"cap_confirmed_{curr_data_src}", False) or (not has_excel_cap and selected_rating_str != "160 kVA"))

    # Display status / prompt message in sidebar
    if parsed_data is not None:
        if has_excel_cap and excel_cap_val:
            if rated_cap == excel_cap_val:
                st.success(f"✅ **Auto-Detected from Excel:** **{excel_cap_val:.0f} kVA** (`{excel_raw_val}`).")
            else:
                st.info(f"🔄 **Overriding Excel Rating:** **{rated_cap:.0f} kVA** (Excel was {excel_cap_val:.0f} kVA).")
        else:
            if user_has_selected:
                st.success(f"✅ **Transformer Capacity Set:** **{rated_cap:.0f} kVA** (Website Selection).")
            else:
                st.warning("⚠️ **Give the Transformer Capacity:** No capacity was found in the Excel 'Names' sheet (in front of Transformer Pole ID). Please verify or select the rating above.")
                if st.button(f"✓ Confirm {rated_cap:.0f} kVA", key=f"btn_conf_{curr_data_src}"):
                    st.session_state[f"cap_confirmed_{curr_data_src}"] = True
                    st.rerun()
    else:
        st.info("ℹ️ Select or enter the transformer capacity above.")
        
    st.markdown("---")
    st.markdown("#### 📘 File Specification")
    st.caption("""
    **4 Required Sheets:**
    1. **DB**: 15-min interval readings (Ia, Ib, Ic, Va, Vb, Vc, Import/Export kVA).
    2. **Names**: Nickname (T/F, F1, F1M, F2), DB Name, Pole ID, and optional Capacity (e.g. 160kVA in cell next to Transformer Pole ID).
    3. **Poles**: Pole sequence by feeder (AB1, AB2, spurs).
    4. **Solar Customers**: Pole ID, Inverter kW, Installed kWp.
    """)


# Main App Layout
st.markdown('<div class="main-header">⚡ Distribution Transformer NMD Analytics</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">Automated Current Transformer (CT) Polarity Verification, Feeder Voltage Profiling & Solar Integration Analysis</div>', unsafe_allow_html=True)

if parsed_data is None:
    st.info("👈 Please upload an Excel file or select a Demo Dataset in the sidebar to begin analysis.")
    st.stop()

# Extract key elements from parsed data
names_df = parsed_data["names_df"]
poles_dict = parsed_data["poles_dict"]
solar_df = parsed_data["solar_df"]
device_readings = parsed_data["device_readings"]
tf_nick = parsed_data["transformer_nick"]
tf_db_name = parsed_data["transformer_db_name"]
summary = parsed_data["summary"]

# Find Transformer Readings
if tf_nick not in device_readings or len(device_readings[tf_nick]) == 0:
    st.error(f"No readings found for Transformer '{tf_nick}' ({tf_db_name}) in DB sheet.")
    st.stop()

df_tf = device_readings[tf_nick]

# Perform CT Polarity Analysis via Global Statistical Voting Engine (Nighttime Priority)
ct_result = analyze_transformer_ct_polarities(
    df_tf,
    anomaly_threshold_percent=threshold_val,
    night_start_hour=int(night_start),
    night_end_hour=int(night_end),
    daytime_start=day_start,
    daytime_end=day_end
)

# Perform Transformer Daily Load Profile Analysis (Net Load = Import kVA - Export kVA)
load_result = compute_daily_load_profiles(
    df_tf,
    rated_capacity_kva=float(rated_cap)
)

# Perform Transformer & Feeder Voltage Profile & Statutory Violation Analysis (230V +/- 6%)
network_voltage_result = analyze_all_network_voltages(
    device_readings,
    names_df=names_df,
    nominal_v=230.0,
    tolerance_pct=6.0
)

# Build Feeder Network Topology
network_topo = build_network_topology(poles_dict, names_df, solar_df) if poles_dict else None

# Compute Comprehensive Engineering Mitigation Solutions
parsed_data["rated_capacity"] = float(rated_cap)
mitigation_solutions = analyze_mitigation_solutions(
    ct_result,
    load_result,
    network_voltage_result,
    network_topo or {},
    parsed_data
)

# Determine prominent bold transformer number
tf_number_display = tf_db_name if (tf_db_name and str(tf_db_name).strip()) else tf_nick
tf_clean_id = re.sub(r'[^a-zA-Z0-9_\-]', '_', str(tf_number_display))
tf_sub_label = f"Nickname: {tf_nick}" if (tf_nick and tf_nick != tf_number_display) else "Role: Substation Transformer"
tf_val_style = ' style="font-size: 1.5rem;"' if len(str(tf_number_display)) > 8 else ''

# Extract clean transformer code (e.g. BZ5504 from 042/BZ5504 or BZ6004 from 041/BZ6004) for report naming
report_tf_code = "BZ0000"
for _s in [str(tf_db_name), str(tf_nick), str(tf_number_display)]:
    if not _s or _s.lower() == "nan":
        continue
    _m = re.search(r'([A-Za-z]{1,5}\d+)', _s)
    if _m:
        report_tf_code = _m.group(1).upper()
        break
else:
    for _s in [str(tf_db_name), str(tf_nick)]:
        _clean = re.sub(r'[^a-zA-Z0-9]', '', _s)
        if _clean and _clean.upper() not in ["TF", "T/F"]:
            report_tf_code = _clean.upper()
            break

# Header Stats Bar
col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Distribution Transformer</div>
        <div class="kpi-value"{tf_val_style}>{tf_number_display}</div>
        <small style="color: #6B7280;">{tf_sub_label}</small>
    </div>
    """, unsafe_allow_html=True)

with col_h2:
    pole_id = names_df[names_df["Nickname"] == tf_nick]["Pole_ID"].iloc[0] if len(names_df[names_df["Nickname"] == tf_nick]) > 0 else "N/A"
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Distribution Transformer Pole</div>
        <div class="kpi-value">{pole_id if pole_id else 'ST13/9'}</div>
        <small style="color: #6B7280;">Central 11kV/400V Pole • {rated_cap:.0f} kVA</small>
    </div>
    """, unsafe_allow_html=True)

with col_h3:
    time_span = f"{df_tf['Timestamp'].min().strftime('%b %d')} - {df_tf['Timestamp'].max().strftime('%b %d, %Y')}"
    valid_count = ct_result.get('valid_days_count', 0)
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Monitoring Period</div>
        <div class="kpi-value" style="font-size: 1.3rem; margin-top: 5px;">{time_span}</div>
        <small style="color: #6B7280;">{valid_count} Days (15-min Intervals)</small>
    </div>
    """, unsafe_allow_html=True)

with col_h4:
    tot_solar = summary["total_solar_kw"]
    cust_count = summary["solar_customers_count"]
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Solar Penetration</div>
        <div class="kpi-value">{tot_solar:.1f} <span style="font-size: 1rem;">kW</span></div>
        <small style="color: #6B7280;">{cust_count} Solar Customers</small>
    </div>
    """, unsafe_allow_html=True)

# Capacity Notice Banner
if has_excel_cap:
    override_note = f" (Manual override: <b>{rated_cap:.0f} kVA</b> selected in sidebar)" if rated_cap != excel_cap_val else ""
    cap_bg = "#062B1D" if dark_mode else "#ECFDF5"
    cap_border = "#059669" if dark_mode else "#10B981"
    cap_title = "#34D399" if dark_mode else "#065F46"
    cap_text = "#D1FAE5" if dark_mode else "#047857"
    st.markdown(f"""
    <div style="background-color: {cap_bg}; border: 1px solid {cap_border}; border-left: 6px solid #10B981; padding: 10px 18px; border-radius: 8px; margin-top: 10px; margin-bottom: 18px;">
        <span style="font-size: 1rem; color: {cap_title}; font-weight: 700;">✅ Transformer Capacity: {rated_cap:.0f} kVA</span>
        <span style="color: {cap_text}; font-size: 0.95rem; margin-left: 8px;">
            Auto-detected directly from Excel 'Names' sheet (Cell value: <code>{excel_raw_val}</code>){override_note}. You can change this anytime from the left sidebar.
        </span>
    </div>
    """, unsafe_allow_html=True)
elif user_has_selected:
    cap_bg = "#062B1D" if dark_mode else "#ECFDF5"
    cap_border = "#059669" if dark_mode else "#10B981"
    cap_title = "#34D399" if dark_mode else "#065F46"
    cap_text = "#D1FAE5" if dark_mode else "#047857"
    st.markdown(f"""
    <div style="background-color: {cap_bg}; border: 1px solid {cap_border}; border-left: 6px solid #10B981; padding: 10px 18px; border-radius: 8px; margin-top: 10px; margin-bottom: 18px;">
        <span style="font-size: 1rem; color: {cap_title}; font-weight: 700;">✅ Transformer Capacity Set: {rated_cap:.0f} kVA</span>
        <span style="color: {cap_text}; font-size: 0.95rem; margin-left: 8px;">
            Specified via website selection (Not provided in Excel). You can change this rating anytime from the left sidebar.
        </span>
    </div>
    """, unsafe_allow_html=True)
else:
    cap_bg = "#271C0C" if dark_mode else "#FFFBEB"
    cap_border = "#B45309" if dark_mode else "#F59E0B"
    cap_title = "#FCD34D" if dark_mode else "#92400E"
    cap_text = "#FEF3C7" if dark_mode else "#B45309"
    st.markdown(f"""
    <div style="background-color: {cap_bg}; border: 1px solid {cap_border}; border-left: 6px solid #F59E0B; padding: 12px 18px; border-radius: 8px; margin-top: 10px; margin-bottom: 18px;">
        <span style="font-size: 1.05rem; color: {cap_title}; font-weight: 700;">⚡ Give the Transformer Capacity:</span>
        <span style="color: {cap_text}; font-size: 0.95rem; margin-left: 6px;">
            Transformer capacity was not found in the uploaded Excel 'Names' sheet (in front of Transformer Pole ID). The analysis is currently using default <b>{rated_cap:.0f} kVA</b>. Please select or confirm the capacity in the left sidebar under <b>3. Transformer Rating</b>.
        </span>
    </div>
    """, unsafe_allow_html=True)

st.write("")

# Executive Report Download Action Bar
col_rep1, col_rep2 = st.columns([3, 1])
with col_rep1:
    st.markdown("""
    <div style="background: linear-gradient(90deg, #1E3A8A 0%, #0891B2 100%); padding: 12px 18px; border-radius: 8px; color: white;">
        <strong>📄 Official Proposal Justification Report (.docx) Ready:</strong> Styled to the LECO standard proposal format including Project Identification, Background Information, Analysis and Justification, per-feeder diurnal voltage profiles & time intervals, Solar distribution map, and Scope of Proposed Works.
    </div>
    """, unsafe_allow_html=True)
with col_rep2:
    report_metadata = {
        "branch": st.session_state.get("rep_branch", "Galle"),
        "csc": st.session_state.get("rep_csc", "Hikkaduwa"),
        "job_no": st.session_state.get("rep_job_no", ""),
        "last_rehab_year": st.session_state.get("rep_rehab_year", ""),
        "year": datetime.now().year
    }
    report_docx_data = generate_word_report(
        parsed_data,
        ct_result,
        load_result,
        network_topo or {},
        network_voltage_result,
        report_metadata=report_metadata
    )
    st.download_button(
        label="📥 Download Proposal Justification Report (.docx)",
        data=report_docx_data,
        file_name=f"{report_tf_code} Proposal Justification Report.docx",
        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        use_container_width=True
    )

with st.expander("⚙️ Customize Proposal Report Metadata (Branch, CSC, Job No)", expanded=False):
    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    with col_meta1:
        st.text_input("Branch:", value="Galle", key="rep_branch", help="Branch name for Project Identification table")
    with col_meta2:
        st.text_input("CSC (Customer Service Center):", value="Hikkaduwa", key="rep_csc", help="CSC for Project Identification table")
    with col_meta3:
        st.text_input("Job No:", value="", key="rep_job_no", placeholder="e.g. JB-2026-041", help="Optional Job Reference No")
    with col_meta4:
        st.text_input("Rehabilitated / Constructed Year:", value="", key="rep_rehab_year", placeholder="e.g. 2018", help="Constructed or last rehabilitated year")

st.write("")

# Main Tabs
tab_ct, tab_load, tab_voltage, tab_poles, tab_solar, tab_solutions, tab_raw = st.tabs([
    "🔍 CT Polarity Analysis",
    "📈 Transformer Daily Load Profile",
    "⚡ Voltage Profile & Violations",
    "🗺️ Feeder Topology & Poles",
    "☀️ Solar Customers",
    "💡 Solutions & Mitigation Advisory",
    "📋 Names & Raw Data"
])


# ==========================================
# TAB: TRANSFORMER DAILY LOAD PROFILE
# ==========================================
with tab_load:
    st.markdown("### 📈 Transformer Daily Load Profile Analysis")
    tf_caption_str = f"**{tf_number_display}**" + (f" (Device: {tf_nick})" if tf_nick != tf_number_display else "")
    st.caption(f"Evaluates the daily 24-hour load profile for {tf_caption_str} calculated as **Net Load (kVA) = Import kVA - Export kVA** from DB sheet.")

    lm = load_result.get("metrics", {})
    landmarks = load_result.get("landmarks", {})
    avg_24h = load_result.get("avg_24h_profile", pd.DataFrame())
    daily_stats_df = load_result.get("daily_stats_df", pd.DataFrame())
    raw_load_df = load_result.get("raw_df", df_tf)

    # Top KPI Metrics Cards
    col_l1, col_l2, col_l3, col_l4 = st.columns(4)
    with col_l1:
        st.metric(
            label="Monthly Peak Net Load",
            value=f"{lm.get('monthly_peak_kva', 0.0)} kVA",
            delta=f"Occurred: {lm.get('monthly_peak_timestamp', 'N/A')}",
            delta_color="off"
        )
    with col_l2:
        st.metric(
            label="Monthly Average Net Load",
            value=f"{lm.get('monthly_avg_load_kva', 0.0)} kVA",
            delta=f"Load Factor: {lm.get('monthly_load_factor_pct', 0.0)}%",
            delta_color="normal"
        )
    with col_l3:
        peak_load_pct = lm.get("monthly_peak_loading_pct", 0.0)
        avg_load_pct = lm.get("avg_demand_loading_pct", peak_load_pct)
        avg_peak_kva = lm.get("avg_peak_demand_kva", lm.get("monthly_peak_kva", 0.0))
        is_avg_overloaded = lm.get("is_overloaded_from_avg", avg_load_pct > 100.0)
        st.metric(
            label="Average Demand Loading",
            value=f"{avg_load_pct:.1f}%",
            delta=f"Peak: {avg_peak_kva:.1f} kVA of {rated_cap:.0f} kVA ({'OVERLOADED' if is_avg_overloaded else 'Normal'})",
            delta_color="inverse" if is_avg_overloaded or avg_load_pct > 80.0 else "normal"
        )
    with col_l4:
        tot_imp = lm.get("total_import_mvah", 0.0)
        st.metric(
            label="Monthly Energy Throughput",
            value=f"{tot_imp} MVAh",
            delta=f"{lm.get('total_days', 0)} Days Evaluated",
            delta_color="off"
        )

    # Solar Midday Duck Curve Callout Banner
    callout_bg = "#0F2042" if dark_mode else "#EFF6FF"
    callout_border = "#1E3A8A" if dark_mode else "#3B82F6"
    callout_title = "#93C5FD" if dark_mode else "#1E3A8A"
    callout_text = "#E2E8F0" if dark_mode else "#1E293B"
    st.markdown(f"""
    <div style="background-color: {callout_bg}; border: 1px solid {callout_border}; border-left: 6px solid #3B82F6; border-radius: 8px; padding: 12px 18px; margin: 15px 0; color: {callout_text};">
        <span style="font-weight: 700; color: {callout_title};">☀️ 24-Hour Average Profile Diurnal Landmarks:</span><br/>
        • <strong>Morning Peak:</strong> <code>{landmarks.get('morning_peak', {}).get('load_kva', 0.0)} kVA</code> at <code>{landmarks.get('morning_peak', {}).get('time', 'N/A')}</code><br/>
        • <strong>Midday Solar Trough:</strong> <code>{landmarks.get('midday_solar_trough', {}).get('load_kva', 0.0)} kVA</code> at <code>{landmarks.get('midday_solar_trough', {}).get('time', 'N/A')}</code> (Solar offset reduces transformer loading by <strong>{landmarks.get('midday_solar_trough', {}).get('solar_dip_reduction_kva', 0.0)} kVA</strong>)<br/>
        • <strong>Evening Peak:</strong> <code>{landmarks.get('evening_peak', {}).get('load_kva', 0.0)} kVA</code> at <code>{landmarks.get('evening_peak', {}).get('time', 'N/A')}</code>
    </div>
    """, unsafe_allow_html=True)

    # Chart 1: 24-Hour Average Diurnal Load Profile with Confidence Envelope
    st.write("")
    st.markdown("#### 📊 24-Hour Representative Daily Load Profile (15-Min Intervals)")
    st.caption("Shows the monthly average Net Load (Import kVA - Export kVA), Import kVA, Export kVA, and the 10th - 90th percentile daily envelope.")

    if not avg_24h.empty:
        fig_avg_load = go.Figure()

        # Daytime solar window shading
        fig_avg_load.add_vrect(
            x0=day_start, x1=day_end,
            fillcolor="rgba(254, 240, 138, 0.25)",
            layer="below", line_width=0,
            annotation_text="☀️ Daytime Solar Window",
            annotation_position="top left"
        )

        # Envelope: P10 to P90
        fig_avg_load.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Net_Load_P90"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip"
        ))
        fig_avg_load.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Net_Load_P10"],
            mode="lines", fill="tonexty", fillcolor="rgba(37, 99, 235, 0.12)",
            line=dict(width=0), name="10th - 90th Percentile Band", hoverinfo="skip"
        ))

        # Net Load Mean line
        fig_avg_load.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Net_Load_Mean"],
            mode="lines+markers", name="Average Net Load (Import - Export)",
            line=dict(color="#1D4ED8", width=3.0),
            marker=dict(size=4)
        ))

        # Import kVA Mean line
        fig_avg_load.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Import_kVA_Mean"],
            mode="lines", name="Import kVA",
            line=dict(color="#059669", width=2.0, dash="dot")
        ))

        # Export kVA Mean line (if export exists)
        if (avg_24h["Export_kVA_Mean"] > 0.05).any():
            fig_avg_load.add_trace(go.Scatter(
                x=avg_24h["Time"], y=avg_24h["Export_kVA_Mean"],
                mode="lines", name="Export kVA",
                line=dict(color="#DC2626", width=2.0, dash="dash")
            ))

        # Rated capacity line
        rated_val = float(lm.get("rated_capacity_kva", 160.0))
        avg_peak_kva = lm.get("avg_peak_demand_kva", avg_24h["Net_Load_Mean"].max() if not avg_24h.empty else 0.0)
        avg_peak_time = lm.get("avg_peak_time", str(avg_24h.loc[avg_24h["Net_Load_Mean"].idxmax(), "Time"]) if not avg_24h.empty else "N/A")
        avg_loading_pct = lm.get("avg_demand_loading_pct", round(avg_peak_kva / rated_val * 100.0, 1) if rated_val > 0 else 0.0)
        is_avg_overloaded = bool(avg_peak_kva > rated_val)
        avg_headroom = max(0.0, rated_val - avg_peak_kva)
        avg_overload_hrs = lm.get("avg_overload_hours", 0.0)
        avg_overload_range = lm.get("avg_overload_time_range", "None")

        fig_avg_load.add_hline(
            y=rated_val, line_dash="dash", line_color="#EF4444",
            annotation_text=f"Transformer Rating ({rated_val:.0f} kVA)",
            annotation_position="bottom right"
        )

        # Highlight peak on average demand curve with annotation
        peak_marker_color = "#DC2626" if is_avg_overloaded else "#1D4ED8"
        peak_badge_text = f"🚨 Average Peak: {avg_peak_kva:.1f} kVA ({avg_loading_pct:.1f}%) OVERLOAD" if is_avg_overloaded else f"✓ Average Peak: {avg_peak_kva:.1f} kVA ({avg_loading_pct:.1f}%)"
        fig_avg_load.add_annotation(
            x=avg_peak_time,
            y=avg_peak_kva,
            text=peak_badge_text,
            showarrow=True,
            arrowhead=2,
            arrowsize=1,
            arrowwidth=2,
            arrowcolor=peak_marker_color,
            ax=0,
            ay=-38,
            bgcolor="#FEF2F2" if is_avg_overloaded else "#EFF6FF",
            bordercolor=peak_marker_color,
            borderwidth=1.5,
            font=dict(color=peak_marker_color, size=11, family="Arial")
        )

        fig_avg_load.update_layout(
            xaxis_title="Time of Day (15-Minute Intervals)",
            yaxis_title="Load (kVA)",
            hovermode="x unified",
            margin=dict(l=40, r=40, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_avg_load, use_container_width=True, key="fig_avg_load")

        # Dedicated Average Demand Overload Finding & Engineering Conclusion Banner
        if is_avg_overloaded:
            banner_bg = "#2A0E0E" if dark_mode else "#FEF2F2"
            banner_border = "#B91C1C" if dark_mode else "#EF4444"
            banner_h4 = "#FCA5A5" if dark_mode else "#991B1B"
            badge_bg = "#450A0A" if dark_mode else "#FEE2E2"
            badge_txt = "#FCA5A5" if dark_mode else "#991B1B"
            badge_border = "#EF4444" if dark_mode else "#FCA5A5"
            p_color = "#FECACA" if dark_mode else "#7F1D1D"
            st.markdown(f"""
            <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-left: 6px solid #DC2626; border-radius: 8px; padding: 14px 20px; margin-top: 10px; margin-bottom: 22px;">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <h4 style="margin: 0; color: {banner_h4}; font-size: 1.1rem;">🚨 Transformer Overloaded from Average Demand Curve</h4>
                    <span style="background: {badge_bg}; color: {badge_txt}; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; border: 1px solid {badge_border};">
                        OVERLOADED ({avg_loading_pct:.1f}% OF RATING)
                    </span>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 0.95rem; color: {p_color}; line-height: 1.6;">
                    The 24-hour representative average demand curve <b>exceeds the transformer rating {rated_val:.0f} kVA</b>, reaching a peak average demand of <b>{avg_peak_kva:.1f} kVA ({avg_loading_pct:.1f}% loading)</b> at <b>{avg_peak_time}</b>.<br/>
                    • <b>Overload Magnitude:</b> Exceeds nameplate thermal rating by <b>{avg_peak_kva - rated_val:.1f} kVA</b> ({avg_loading_pct - 100.0:.1f}% overload above {rated_val:.0f} kVA).<br/>
                    • <b>Diurnal Duration:</b> Sustained daily overload occurs for <b>{avg_overload_hrs:.2f} hours</b> ({avg_overload_range}).<br/>
                    • <b>Engineering Finding:</b> This shows that the existing transformer is in an <b>overload condition</b>. Substation augmentation (capacity upgrade) or load deloading via feeder transfer is recommended.
                </p>
            </div>
            """, unsafe_allow_html=True)
        else:
            banner_bg = "#062B1D" if dark_mode else "#ECFDF5"
            banner_border = "#059669" if dark_mode else "#10B981"
            banner_h4 = "#34D399" if dark_mode else "#065F46"
            badge_bg = "#064E3B" if dark_mode else "#D1FAE5"
            badge_txt = "#6EE7B7" if dark_mode else "#065F46"
            badge_border = "#059669" if dark_mode else "#6EE7B7"
            p_color = "#D1FAE5" if dark_mode else "#047857"
            st.markdown(f"""
            <div style="background-color: {banner_bg}; border: 1px solid {banner_border}; border-left: 6px solid #10B981; border-radius: 8px; padding: 14px 20px; margin-top: 10px; margin-bottom: 22px;">
                <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
                    <h4 style="margin: 0; color: {banner_h4}; font-size: 1.1rem;">✅ Transformer Not Overloaded (Average Demand within Rating)</h4>
                    <span style="background: {badge_bg}; color: {badge_txt}; padding: 4px 14px; border-radius: 20px; font-weight: 700; font-size: 0.85rem; border: 1px solid {badge_border};">
                        NORMAL LOADING ({avg_loading_pct:.1f}%)
                    </span>
                </div>
                <p style="margin: 10px 0 0 0; font-size: 0.95rem; color: {p_color}; line-height: 1.6;">
                    The transformer maximum import and export kVA and maximum demand on the 24-hour average demand curve is in the acceptable range. Peak average demand reaches <b>{avg_peak_kva:.1f} kVA ({avg_loading_pct:.1f}% of rating)</b> at <b>{avg_peak_time}</b> against the rated capacity of <b>{rated_val:.0f} kVA</b>.<br/>
                    • <b>Available Headroom:</b> <b>{avg_headroom:.1f} kVA</b> operational thermal headroom remains available ({100.0 - avg_loading_pct:.1f}% spare margin).<br/>
                    • <b>Engineering Finding:</b> Maximum demand does not exceed the transformer rating {rated_val:.0f} kVA. This shows that the existing transformer is <b>not in overload condition</b>.
                </p>
            </div>
            """, unsafe_allow_html=True)

    # Chart 2: Weekday vs Weekend Comparison & Loading Gauge
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        st.markdown("#### 📅 Weekday vs Weekend Daily Load Profile")
        st.caption("Compares Monday–Friday consumer loading against Saturday–Sunday loading.")
        fig_wk = go.Figure()
        fig_wk.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Weekday_Net_Load"],
            mode="lines", name="Weekday Profile (Mon - Fri)",
            line=dict(color="#2563EB", width=2.5)
        ))
        fig_wk.add_trace(go.Scatter(
            x=avg_24h["Time"], y=avg_24h["Weekend_Net_Load"],
            mode="lines", name="Weekend Profile (Sat - Sun)",
            line=dict(color="#D97706", width=2.5, dash="dash")
        ))
        fig_wk.update_layout(
            xaxis_title="Time of Day",
            yaxis_title="Net Load (kVA)",
            hovermode="x unified",
            margin=dict(l=40, r=40, t=30, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_wk, use_container_width=True, key="fig_wk_load")

    with col_w2:
        st.markdown("#### 📊 Loading Profile Summary")
        w_mean = avg_24h["Weekday_Net_Load"].mean() if not avg_24h.empty else 0.0
        we_mean = avg_24h["Weekend_Net_Load"].mean() if not avg_24h.empty else 0.0
        w_peak = avg_24h["Weekday_Net_Load"].max() if not avg_24h.empty else 0.0
        we_peak = avg_24h["Weekend_Net_Load"].max() if not avg_24h.empty else 0.0

        st.markdown(f"""
        **Average Curve Peak:** `{avg_peak_kva:.2f} kVA` ({avg_loading_pct:.1f}%)  
        **Monthly Absolute Peak:** `{lm.get('monthly_peak_kva', 0.0):.2f} kVA` ({peak_load_pct:.1f}%)  
        **Weekday Peak Load:** `{w_peak:.2f} kVA`  
        **Weekend Peak Load:** `{we_peak:.2f} kVA`  
        **Transformer Status:** `{'OVERLOADED' if is_avg_overloaded else lm.get('loading_status', 'Normal')}`
        """)

        gauge_num_col = "#F8FAFC" if dark_mode else "#1E293B"
        gauge_title_col = "#E2E8F0" if dark_mode else "#334155"
        gauge_tick_col = "#94A3B8" if dark_mode else "#64748B"
        step_colors = (
            ["#1E3A8A", "#064E3B", "#78350F", "#7F1D1D"] if dark_mode
            else ["#DBEAFE", "#D1FAE5", "#FEF3C7", "#FEE2E2"]
        )
        fig_gauge = go.Figure(go.Indicator(
            mode="gauge+number",
            value=avg_loading_pct,
            number={'suffix': "%", 'font': {'size': 36, 'color': gauge_num_col}},
            title={'text': "<b>Average Demand Loading (%)</b>", 'font': {'size': 14, 'color': gauge_title_col}},
            gauge={
                'axis': {'range': [0, 140], 'tickwidth': 1, 'tickcolor': gauge_tick_col},
                'bar': {'color': "#DC2626" if is_avg_overloaded else "#3B82F6"},
                'steps': [
                    {'range': [0, 50], 'color': step_colors[0]},
                    {'range': [50, 80], 'color': step_colors[1]},
                    {'range': [80, 100], 'color': step_colors[2]},
                    {'range': [100, 140], 'color': step_colors[3]}
                ],
                'threshold': {
                    'line': {'color': "#DC2626", 'width': 4},
                    'thickness': 0.75,
                    'value': 100
                }
            }
        ))
        fig_gauge.update_layout(height=230, margin=dict(l=25, r=25, t=55, b=20))
        st.plotly_chart(fig_gauge, use_container_width=True, key="fig_load_gauge")

    # Chart 3: Single-Day 24-Hour Profile Explorer
    st.markdown("---")
    st.markdown("#### 🔬 Single-Day Load Profile Deep Dive")
    avail_dates = sorted(raw_load_df["Date"].unique())
    col_s1, col_s2 = st.columns([1, 2])
    with col_s1:
        sel_load_date = st.selectbox("Select Date to View 24-Hour Profile:", avail_dates, index=0)
        show_monthly_avg = st.checkbox("Overlay Monthly Average Profile as Benchmark", value=True)

    day_data = raw_load_df[raw_load_df["Date"] == sel_load_date].sort_values("Timestamp")
    day_peak = day_data["Net_Load_kVA"].max()
    day_peak_idx = day_data["Net_Load_kVA"].idxmax()
    day_peak_time = day_data.loc[day_peak_idx, "Time"] if day_peak_idx is not None else "N/A"
    day_min = day_data["Net_Load_kVA"].min()
    day_avg = day_data["Net_Load_kVA"].mean()
    day_lf = (day_avg / day_peak * 100.0) if day_peak > 0 else 0.0

    with col_s2:
        st.markdown(f"""
        **Date:** `{sel_load_date}` ({day_data['DayOfWeek'].iloc[0]})  
        **Daily Peak Load:** `{day_peak:.2f} kVA` at `{day_peak_time}` | **Daily Min Load:** `{day_min:.2f} kVA`  
        **Daily Average Load:** `{day_avg:.2f} kVA` | **Daily Load Factor:** `{day_lf:.1f}%`
        """)

    fig_single_day = go.Figure()
    fig_single_day.add_vrect(
        x0=f"{sel_load_date} {day_start}:00", x1=f"{sel_load_date} {day_end}:00",
        fillcolor="rgba(254, 240, 138, 0.25)",
        layer="below", line_width=0,
        annotation_text="☀️ Daytime Solar Window", annotation_position="top left"
    )

    fig_single_day.add_trace(go.Scatter(
        x=day_data["Timestamp"], y=day_data["Net_Load_kVA"],
        mode="lines+markers", name=f"Net Load ({sel_load_date})",
        line=dict(color="#2563EB", width=2.5),
        marker=dict(size=4)
    ))
    fig_single_day.add_trace(go.Scatter(
        x=day_data["Timestamp"], y=day_data["Import_kVA"],
        mode="lines", name="Import kVA",
        line=dict(color="#059669", width=1.5, dash="dot")
    ))
    if (day_data["Export_kVA"] > 0.05).any():
        fig_single_day.add_trace(go.Scatter(
            x=day_data["Timestamp"], y=day_data["Export_kVA"],
            mode="lines", name="Export kVA",
            line=dict(color="#DC2626", width=1.5, dash="dash")
        ))

    if show_monthly_avg and not avg_24h.empty:
        avg_map = avg_24h.set_index("Time")["Net_Load_Mean"].to_dict()
        benchmark_y = [avg_map.get(t, np.nan) for t in day_data["Time"]]
        fig_single_day.add_trace(go.Scatter(
            x=day_data["Timestamp"], y=benchmark_y,
            mode="lines", name="Monthly Average Benchmark",
            line=dict(color="#9CA3AF", width=2.0, dash="dash")
        ))

    fig_single_day.update_layout(
        title=f"24-Hour Net Load Profile for {sel_load_date} (15-Minute Intervals)",
        xaxis_title="Time",
        yaxis_title="Load (kVA)",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=40, b=40)
    )
    st.plotly_chart(fig_single_day, use_container_width=True, key="fig_single_day")

    # Chart 4: Daily Peak Load Trend Across the Entire Month
    st.markdown("---")
    st.markdown("#### 📈 Daily Peak Net Load Trend (30 Days)")
    if not daily_stats_df.empty:
        fig_peak_trend = px.bar(
            daily_stats_df, x="Date", y="Peak_Net_Load_kVA",
            color="Peak_Loading_Pct",
            color_continuous_scale="Viridis",
            labels={"Peak_Net_Load_kVA": "Peak Net Load (kVA)", "Peak_Loading_Pct": "Loading (%)"},
            title="Maximum Daily Peak Net Load per Calendar Day (kVA)"
        )
        fig_peak_trend.add_hline(
            y=rated_val, line_dash="dash", line_color="#EF4444",
            annotation_text=f"Transformer Rating ({rated_val} kVA)"
        )
        fig_peak_trend.update_layout(margin=dict(l=40, r=40, t=40, b=40))
        st.plotly_chart(fig_peak_trend, use_container_width=True, key="fig_peak_trend")

        # Daily Load Summary Table
        st.markdown("#### 📋 Daily Transformer Load Statistics Table")
        st.dataframe(daily_stats_df, use_container_width=True, height=320)

        csv_load = daily_stats_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Daily Load Statistics (CSV)",
            data=csv_load,
            file_name=f"Transformer_Daily_Load_Profiles_{tf_clean_id}.csv",
            mime="text/csv"
        )


# ==========================================
# TAB 1: CT POLARITY ANALYSIS (Global Statistical Voting Engine)
# ==========================================
with tab_ct:
    st.markdown("### 🔍 Global Statistical Voting Engine (Nighttime Priority)")
    st.caption("Evaluates nighttime intervals (zero solar generation) in strict priority order to detect physical CT reversals, reference channel swaps, and solar export signatures.")
    
    # Alert Banner
    badge_color = ct_result.get("badge_color", "green")
    if badge_color == "green":
        banner_class = "alert-banner-green"
    elif badge_color == "orange":
        banner_class = "alert-banner-orange"
    else:
        banner_class = "alert-banner-red"

    status_label = ct_result.get("status_label", "")
    action_rec = ct_result.get("action_recommendation", "")

    st.markdown(f"""
    <div class="{banner_class}">
        <h3 style="margin: 0 0 8px 0; color: #111827;">{status_label}</h3>
        <p style="margin: 0; font-size: 1rem; color: #374151;"><strong>Diagnostic Action:</strong> {action_rec}</p>
    </div>
    """, unsafe_allow_html=True)

    # Statistical Voting KPI Row
    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    conf = ct_result.get("confidence_percent", 0.0)
    dom_mode = ct_result.get("dominant_mode", "UNKNOWN")
    tot_night = ct_result.get("total_night_intervals", 0)
    day_eval = ct_result.get("daytime_solar_eval", {})
    
    with col_k1:
        st.metric(
            label="Dominant Polarity Profile",
            value=f"{dom_mode}",
            delta="Normal State" if dom_mode == "NORMAL_IMPORT" else "Failure Detected",
            delta_color="normal" if dom_mode == "NORMAL_IMPORT" else "inverse"
        )
    with col_k2:
        st.metric(
            label="Statistical Confidence Level",
            value=f"{conf}%",
            delta=f"Of {tot_night} Night Intervals",
            delta_color="normal" if conf >= threshold_val else "off"
        )
    with col_k3:
        anom_cts = ct_result.get("anomaly_cts", [])
        anom_str = ", ".join(anom_cts) if anom_cts else "None"
        st.metric(
            label="Affected CTs",
            value=f"{len(anom_cts)} Flagged",
            delta=f"{anom_str}",
            delta_color="normal" if len(anom_cts) == 0 else "inverse"
        )
    with col_k4:
        day_match = day_eval.get("matches_solar", True)
        st.metric(
            label="Daytime Solar Verification",
            value="Clean Solar Dip" if day_match else "Irregular Profile",
            delta="Verified Safe State" if day_match else "Check Daytime Load",
            delta_color="normal" if day_match else "off"
        )

    # Voting Breakdown Bar Chart & Table
    st.write("")
    st.markdown("#### 🗳️ Nighttime Interval Statistical Voting Distribution")
    st.caption(f"Evaluates all 15-minute intervals between {night_start}:00 and {night_end}:00 across the month ({tot_night} intervals) against the 8 failure modes in strict priority order.")

    vote_data = []
    vb = ct_result.get("vote_breakdown", {})
    for code, item in vb.items():
        if item["count"] > 0:
            vote_data.append({
                "Mode": code,
                "Description": item["name"],
                "Interval Count": item["count"],
                "Vote Share (%)": item["percentage"]
            })
    df_votes = pd.DataFrame(vote_data).sort_values("Interval Count", ascending=False) if vote_data else pd.DataFrame()

    if not df_votes.empty:
        fig_votes = px.bar(
            df_votes, x="Vote Share (%)", y="Description",
            orientation="h",
            color="Vote Share (%)",
            color_continuous_scale="Blues",
            text="Vote Share (%)",
            title="Dominant Polarity Vote Share Across Nighttime Monitored Intervals"
        )
        fig_votes.update_layout(yaxis=dict(autorange="reversed"), margin=dict(l=40, r=40, t=40, b=40), height=260)
        st.plotly_chart(fig_votes, use_container_width=True, key="fig_ct_votes")
        
        st.dataframe(df_votes, use_container_width=True, hide_index=True)

    # Logic Explanation Expander
    with st.expander("ℹ️ Failure Modes & Strict Priority Order (Click to Expand)", expanded=False):
        st.markdown("""
        | Priority | Failure Mode | Nighttime Condition | System Diagnostic Verdict |
        | :---: | :--- | :--- | :--- |
        | **1** | **Failure Mode 1: All Negative & Nighttime Export** | All 3 currents (A, B, C) < 0 AND `AVG._EXPORT_KVA > 0` | ❌ **CRITICAL SYSTEM ALERT:** All three CTs (Phases A, B, and C) are physically reversed. Nighttime power is incorrectly registering as Export. |
        | **2** | **Failure Mode 2: All Positive & Nighttime Export (Channel Swap)** | All 3 currents (A, B, C) > 0 AND `AVG._EXPORT_KVA > 0` | ❌ **CRITICAL SYSTEM ALERT:** Meter reference channel error. Import and Export data streams are globally inverted. |
        | **3** | **Failure Mode 3: Phase A Outlier & Nighttime Export** | Phase A > 0, Phase B & C < 0 AND `AVG._EXPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase B and Phase C CTs are physically reversed. |
        | **4** | **Failure Mode 4: Phase A Negative & Nighttime Import** | Phase A < 0, Phase B & C > 0 AND `AVG._IMPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase A CT is physically reversed. |
        | **5** | **Failure Mode 5: Phase C Outlier & Nighttime Export** | Phase C > 0, Phase A & B < 0 AND `AVG._EXPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase A and Phase B CTs are physically reversed. |
        | **6** | **Failure Mode 6: Phase C Negative & Nighttime Import** | Phase C < 0, Phase A & B > 0 AND `AVG._IMPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase C CT is physically reversed. |
        | **7** | **Failure Mode 7: Phase B Outlier & Nighttime Export** | Phase B > 0, Phase A & C < 0 AND `AVG._EXPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase A and Phase C CTs are physically reversed. |
        | **8** | **Failure Mode 8: Phase B Negative & Nighttime Import** | Phase B < 0, Phase A & C > 0 AND `AVG._IMPORT_KVA > 0` | ❌ **CRITICAL ALERT:** Phase B CT is physically reversed. |
        | **Safe State** | **Safe State: Normal Import & Solar Export Verification** | No nighttime discrepancies exist AND daytime profile matches solar export cleanly | ✅ **SYSTEM NORMAL:** All CT polarities match perfectly across all monitored periods. |
        """)

    st.write("")
    st.markdown("#### 📈 Average Current Profile")
    st.caption("Average 24-hour current curve across the month. Look for the daytime dip (Normal) vs daytime peak (Reversed).")

    # Calculate average 24-hour diurnal profile
    df_tf["Time_OfDay"] = df_tf["Timestamp"].dt.strftime("%H:%M")
    diurnal_df = df_tf.groupby("Time_OfDay")[["Ia", "Ib", "Ic"]].mean().reset_index()

    fig_diurnal = go.Figure()
    # Shading for daytime
    fig_diurnal.add_vrect(
        x0=day_start, x1=day_end,
        fillcolor="rgba(254, 240, 138, 0.25)",
        layer="below", line_width=0,
        annotation_text="☀️ Daytime Solar Window (06:00 - 18:00)",
        annotation_position="top left"
    )
    
    fig_diurnal.add_trace(go.Scatter(
        x=diurnal_df["Time_OfDay"], y=diurnal_df["Ia"],
        mode="lines+markers", name="Phase A (R)",
        line=dict(color="#DC2626", width=2.5),
        marker=dict(size=4)
    ))
    fig_diurnal.add_trace(go.Scatter(
        x=diurnal_df["Time_OfDay"], y=diurnal_df["Ib"],
        mode="lines+markers", name="Phase B (Y)",
        line=dict(color="#EAB308", width=2.5),
        marker=dict(size=4)
    ))
    fig_diurnal.add_trace(go.Scatter(
        x=diurnal_df["Time_OfDay"], y=diurnal_df["Ic"],
        mode="lines+markers", name="Phase C (B)",
        line=dict(color="#2563EB", width=2.5),
        marker=dict(size=4)
    ))

    fig_diurnal.update_layout(
        xaxis_title="Time of Day (15-Minute Intervals)",
        yaxis_title="Phase Current (Amperes)",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=30, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_diurnal, use_container_width=True, key="fig_ct_diurnal")

    # Full Time Series Chart
    st.markdown("#### 📊 Full Monitoring Period (15-Minute Readings)")
    fig_ts = px.line(
        df_tf, x="Timestamp", y=["Ia", "Ib", "Ic"],
        labels={"value": "Current (A)", "variable": "Phase", "Timestamp": "Date & Time"},
        color_discrete_map={"Ia": "#DC2626", "Ib": "#EAB308", "Ic": "#2563EB"},
        title="Continuous Phase Currents (Ia, Ib, Ic)"
    )
    fig_ts.update_layout(
        hovermode="x unified",
        margin=dict(l=40, r=40, t=40, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig_ts, use_container_width=True, key="fig_ct_ts")

    # Single-Day Deep Dive
    st.markdown("---")
    st.markdown("#### 🔬 Single-Day Deep Dive & Curve Inspection")
    if "daily_df" in ct_result and not ct_result["daily_df"].empty and "Date" in ct_result["daily_df"].columns:
        unique_dates = sorted(ct_result["daily_df"]["Date"].unique())
        if len(unique_dates) > 0:
            col_d1, col_d2 = st.columns([1, 2])
            with col_d1:
                selected_date = st.selectbox("Select Date to Inspect:", unique_dates, index=0)
            
            # Filter selected day
            day_readings = df_tf[df_tf["Timestamp"].dt.date == selected_date].copy()
            matched_audit = ct_result["daily_df"][ct_result["daily_df"]["Date"] == selected_date]
            day_audit = matched_audit.iloc[0] if len(matched_audit) > 0 else {}

            with col_d2:
                st.markdown(f"""
                **Daily Verdict:** `{day_audit.get('Verdict', 'N/A')}`  
                **Reversed CTs Flagged:** `{day_audit.get('Reversed_CTs', 'N/A')}`  
                **Signs:** A (`{day_audit.get('Sign_A', 'N/A')}`), B (`{day_audit.get('Sign_B', 'N/A')}`), C (`{day_audit.get('Sign_C', 'N/A')}`)  
                **Daytime Trends:** A (`{day_audit.get('Trend_A', 'N/A')}`), B (`{day_audit.get('Trend_B', 'N/A')}`), C (`{day_audit.get('Trend_C', 'N/A')}`)  
                <small><strong>Rule Applied:</strong> {day_audit.get('Rule', 'N/A')}</small><br/>
                <small><strong>Explanation:</strong> {day_audit.get('Explanation', 'N/A')}</small>
                """, unsafe_allow_html=True)

            fig_day = go.Figure()
            fig_day.add_vrect(
                x0=f"{selected_date} {day_start}:00", x1=f"{selected_date} {day_end}:00",
                fillcolor="rgba(254, 240, 138, 0.25)",
                layer="below", line_width=0,
                annotation_text="☀️ Daytime Window", annotation_position="top left"
            )
            fig_day.add_trace(go.Scatter(x=day_readings["Timestamp"], y=day_readings["Ia"], mode="lines+markers", name="Phase A", line=dict(color="#DC2626", width=2)))
            fig_day.add_trace(go.Scatter(x=day_readings["Timestamp"], y=day_readings["Ib"], mode="lines+markers", name="Phase B", line=dict(color="#EAB308", width=2)))
            fig_day.add_trace(go.Scatter(x=day_readings["Timestamp"], y=day_readings["Ic"], mode="lines+markers", name="Phase C", line=dict(color="#2563EB", width=2)))
            fig_day.update_layout(
                title=f"15-Minute Current Profile for {selected_date}",
                xaxis_title="Time",
                yaxis_title="Current (A)",
                hovermode="x unified",
                margin=dict(l=40, r=40, t=40, b=40)
            )
            st.plotly_chart(fig_day, use_container_width=True, key="fig_ct_day")
    else:
        st.info("No daily records available for deep dive inspection.")

    # Daily Audit Table
    st.markdown("---")
    st.markdown("#### 📋 Daily Evaluation Audit Log")
    if "daily_df" in ct_result and not ct_result["daily_df"].empty:
        avail_cols = [
            c for c in [
                "Date", "Dominant_Mode", "Nighttime_Confidence", "Reversed_CTs", "Verdict", "Night_Intervals"
            ] if c in ct_result["daily_df"].columns
        ]
        st.dataframe(
            ct_result["daily_df"][avail_cols],
            use_container_width=True,
            height=320
        )
        
        # Download daily table
        csv_daily = ct_result["daily_df"].to_csv(index=False).encode('utf-8')
        st.download_button(
            "📥 Download Daily Audit Log (CSV)",
            data=csv_daily,
            file_name=f"CT_Polarity_Daily_Audit_{tf_clean_id}.csv",
            mime="text/csv"
        )
    else:
        st.info("No audit log available for this dataset.")


# ==========================================
# TAB 2: VOLTAGE PROFILE & STATUTORY VIOLATIONS
# ==========================================
with tab_voltage:
    st.markdown("### ⚡ Transformer & Feeder Voltage Profiles & Statutory Violations")
    st.caption("Comprehensive analysis of High Voltage (HV > 243.8V) and Low Voltage (LV < 216.2V) violations against the 230V ± 6% statutory standard, NMD sensor health diagnostics, and 24-hour diurnal voltage profiles.")

    # 1. Hardware Diagnostic Alert Box (if any)
    if network_voltage_result.get("all_hardware_alerts"):
        for alert in network_voltage_result["all_hardware_alerts"]:
            st.error(f"**{alert['message']}**")

    # 3. Two Separate Tables for High Voltage Violations & Low Voltage Violations (Per-Phase Reporting)
    hv_summary_df = network_voltage_result.get("hv_summary_df", pd.DataFrame())
    lv_summary_df = network_voltage_result.get("lv_summary_df", pd.DataFrame())

    if not hv_summary_df.empty:
        st.markdown("#### 📈 Table 1: High Voltage (HV > 243.8 V) Violations Summary")
        st.caption("Statutory +6% limit violations evaluated per phase. Displays all violating phases exceeding the 1.0% considerable threshold, and identifies the worst phase.")
        display_hv_cols = [
            "Device", "Role", "DB Name", "Va HV Viol (%)", "Vb HV Viol (%)", "Vc HV Viol (%)",
            "Violating Phase(s)", "Worst Phase", "Max Voltage (V)", "HV Status"
        ]
        cols_hv = [c for c in display_hv_cols if c in hv_summary_df.columns]
        st.dataframe(
            hv_summary_df[cols_hv].style.format({
                "Va HV Viol (%)": "{:.2f}%",
                "Vb HV Viol (%)": "{:.2f}%",
                "Vc HV Viol (%)": "{:.2f}%",
                "Max Voltage (V)": "{:.1f} V"
            }),
            use_container_width=True
        )

    if not lv_summary_df.empty:
        st.markdown("#### 📉 Table 2: Low Voltage (LV < 216.2 V) Violations & Outages Summary")
        st.caption("Statutory -6% limit violations evaluated per phase. Displays all violating phases exceeding the 1.0% considerable threshold, grid outages, and sensor defect diagnostics.")
        display_lv_cols = [
            "Device", "Role", "DB Name", "Outages (Hrs)", "Va LV Viol (%)", "Vb LV Viol (%)", "Vc LV Viol (%)",
            "Violating Phase(s)", "Worst Phase", "Min Energized V", "LV Status"
        ]
        cols_lv = [c for c in display_lv_cols if c in lv_summary_df.columns]
        st.dataframe(
            lv_summary_df[cols_lv].style.format({
                "Outages (Hrs)": "{:.2f}",
                "Va LV Viol (%)": "{:.2f}%",
                "Vb LV Viol (%)": "{:.2f}%",
                "Vc LV Viol (%)": "{:.2f}%",
                "Min Energized V": "{:.1f} V"
            }),
            use_container_width=True
        )

    st.markdown("---")

    # 4. Deep-Dive Device 24-Hour Diurnal Voltage Profile
    st.markdown("#### 📈 Device 24-Hour Diurnal Voltage Profile & Analysis")
    st.caption("Diurnal 15-minute average voltage curves. Single-phase zero readings are neglected; system blackouts can be included/excluded.")

    available_devices = list(device_readings.keys())
    
    def format_device_label(dev_name):
        if dev_name == tf_nick or "T/F" in dev_name.upper():
            return f"⚡ {dev_name} (Transformer)"
        m_row = names_df[names_df["Nickname"] == dev_name]
        if not m_row.empty:
            db_n = str(m_row["DB_Name"].iloc[0]).strip()
            clean_n = clean_feeder_name(db_n)
            if clean_n and clean_n != dev_name:
                role = str(m_row["Role"].iloc[0]).strip()
                return f"{dev_name} - {clean_n} ({role})"
        return dev_name

    col_sel1, col_sel2 = st.columns([2, 1])
    with col_sel1:
        default_idx = available_devices.index(tf_nick) if tf_nick in available_devices else 0
        selected_device = st.selectbox(
            "Select Transformer / Feeder NMD:",
            available_devices,
            index=default_idx,
            format_func=format_device_label
        )
    with col_sel2:
        include_outages = st.checkbox("Include System Blackouts (All Phases = 0V)", value=True, help="When checked, periods where all three phases dropped to 0V are included in the average as requested.")

    dev_res = network_voltage_result["devices"].get(selected_device, {})
    if dev_res:
        pm = dev_res.get("phase_metrics", {})
        
        # Dedicated Per-Phase KPI Breakdown Cards (Phase A, Phase B, Phase C, Overall Verdict)
        col_pa, col_pb, col_pc, col_ov = st.columns(4)
        
        with col_pa:
            pa = pm.get("Phase A", {})
            st.markdown(f"""
            <div class="kpi-card" style="border-left: 5px solid #DC2626;">
                <div class="kpi-title" style="color: #DC2626;">Phase A (Va)</div>
                <div style="margin-top: 6px; font-size: 14px; line-height: 1.6;">
                    <strong>HV Viol (>243.8V):</strong> <span style="color: {'#DC2626' if pa.get('hv_pct', 0) > 5 else ('#D97706' if pa.get('hv_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pa.get('hv_pct', 0.0):.2f}%</span><br/>
                    <strong>LV Viol (<216.2V):</strong> <span style="color: {'#DC2626' if pa.get('lv_clean_pct', 0) > 5 else ('#D97706' if pa.get('lv_clean_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pa.get('lv_clean_pct', 0.0):.2f}%</span><br/>
                    <strong>Range:</strong> {pa.get('min_energized_v', 0.0):.1f}V – {pa.get('max_v', 0.0):.1f}V<br/>
                    <strong>Status:</strong> {pa.get('status', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)
            
        with col_pb:
            pb = pm.get("Phase B", {})
            st.markdown(f"""
            <div class="kpi-card" style="border-left: 5px solid #D97706;">
                <div class="kpi-title" style="color: #D97706;">Phase B (Vb)</div>
                <div style="margin-top: 6px; font-size: 14px; line-height: 1.6;">
                    <strong>HV Viol (>243.8V):</strong> <span style="color: {'#DC2626' if pb.get('hv_pct', 0) > 5 else ('#D97706' if pb.get('hv_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pb.get('hv_pct', 0.0):.2f}%</span><br/>
                    <strong>LV Viol (<216.2V):</strong> <span style="color: {'#DC2626' if pb.get('lv_clean_pct', 0) > 5 else ('#D97706' if pb.get('lv_clean_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pb.get('lv_clean_pct', 0.0):.2f}%</span><br/>
                    <strong>Range:</strong> {pb.get('min_energized_v', 0.0):.1f}V – {pb.get('max_v', 0.0):.1f}V<br/>
                    <strong>Status:</strong> {pb.get('status', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_pc:
            pc = pm.get("Phase C", {})
            st.markdown(f"""
            <div class="kpi-card" style="border-left: 5px solid #2563EB;">
                <div class="kpi-title" style="color: #2563EB;">Phase C (Vc)</div>
                <div style="margin-top: 6px; font-size: 14px; line-height: 1.6;">
                    <strong>HV Viol (>243.8V):</strong> <span style="color: {'#DC2626' if pc.get('hv_pct', 0) > 5 else ('#D97706' if pc.get('hv_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pc.get('hv_pct', 0.0):.2f}%</span><br/>
                    <strong>LV Viol (<216.2V):</strong> <span style="color: {'#DC2626' if pc.get('lv_clean_pct', 0) > 5 else ('#D97706' if pc.get('lv_clean_pct', 0) > 1 else '#059669')}; font-weight: 700;">{pc.get('lv_clean_pct', 0.0):.2f}%</span><br/>
                    <strong>Range:</strong> {pc.get('min_energized_v', 0.0):.1f}V – {pc.get('max_v', 0.0):.1f}V<br/>
                    <strong>Status:</strong> {pc.get('status', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        with col_ov:
            out_hrs = dev_res.get("interruption_hours", 0.0)
            out_cnt = dev_res.get("interruption_count", 0)
            st.markdown(f"""
            <div class="kpi-card" style="border-left: 5px solid #7C3AED;">
                <div class="kpi-title" style="color: #7C3AED;">Device Compliance Verdict</div>
                <div style="margin-top: 6px; font-size: 14px; line-height: 1.6;">
                    <strong>Worst HV:</strong> {dev_res.get('worst_hv_display', '—')}<br/>
                    <strong>Worst LV:</strong> {dev_res.get('worst_lv_display', '—')}<br/>
                    <strong>Blackouts:</strong> {out_hrs:.1f} hrs ({out_cnt} intervals)<br/>
                    <strong>Overall:</strong> {dev_res.get('overall_status', 'N/A')}
                </div>
            </div>
            """, unsafe_allow_html=True)

        # Diurnal Chart
        df_clean = dev_res.get("df_clean")
        if df_clean is not None and not df_clean.empty:
            diurnal_df = compute_diurnal_voltage_profile(df_clean, include_interruptions=include_outages)
            fig_diurnal = create_diurnal_voltage_chart(
                diurnal_df,
                selected_device,
                nominal_v=230.0,
                tolerance_pct=6.0,
                hardware_alerts=dev_res.get("hardware_alerts")
            )
            st.plotly_chart(fig_diurnal, use_container_width=True, key="fig_voltage_device_diurnal")

        # Raw 15-Minute Waveforms (Expandable)
        with st.expander(f"🔍 Inspect Raw 15-Minute Voltage & Current Waveforms for {selected_device}"):
            col_raw_v, col_raw_i = st.columns(2)
            with col_raw_v:
                fig_raw_v = px.line(
                    df_clean, x="Timestamp", y=["Va", "Vb", "Vc"],
                    labels={"value": "Voltage (V)", "variable": "Phase", "Timestamp": "Date & Time"},
                    color_discrete_map={"Va": "#DC2626", "Vb": "#D97706", "Vc": "#2563EB"},
                    title=f"Raw Phase Voltages ({selected_device})"
                )
                fig_raw_v.add_hline(y=243.8, line_dash="dash", line_color="#EF4444", annotation_text="+6% (243.8V)")
                fig_raw_v.add_hline(y=216.2, line_dash="dash", line_color="#EF4444", annotation_text="-6% (216.2V)")
                fig_raw_v.add_hline(y=230.0, line_dash="dot", line_color="#64748B", annotation_text="Nominal (230V)")
                fig_raw_v.update_layout(hovermode="x unified", margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fig_raw_v, use_container_width=True, key="fig_raw_v")

            with col_raw_i:
                fig_raw_i = px.line(
                    df_clean, x="Timestamp", y=["Ia", "Ib", "Ic"],
                    labels={"value": "Current (A)", "variable": "Phase", "Timestamp": "Date & Time"},
                    color_discrete_map={"Ia": "#DC2626", "Ib": "#D97706", "Ic": "#2563EB"},
                    title=f"Raw Phase Currents ({selected_device})"
                )
                fig_raw_i.update_layout(hovermode="x unified", margin=dict(l=40, r=40, t=40, b=40))
                st.plotly_chart(fig_raw_i, use_container_width=True, key="fig_raw_i")

    # 5. Network Voltage Comparison (Transformer vs Feeder Ends)
    if len(device_readings) > 1:
        st.markdown("---")
        st.markdown("#### 📈 Network Voltage Comparison (Transformer vs Feeder Ends)")
        st.caption("24-hour diurnal 3-phase clean voltage profiles comparing the Transformer and all Feeder Ends, highlighting evening voltage sag and solar midday rise.")

        fig_net_comp = create_network_voltage_comparison_chart(
            network_voltage_result["devices"],
            names_df=names_df,
            nominal_v=230.0,
            tolerance_pct=6.0
        )
        st.plotly_chart(fig_net_comp, use_container_width=True, key="fig_net_comp_full")






# ==========================================
# TAB: FEEDER TOPOLOGY & POLES
# ==========================================
with tab_poles:
    st.markdown("### 🗺️ Feeder Network Schematic & Solar Customer Spread")
    st.caption("Interactive Single-Line Diagram (SLD) depicting distribution transformer, feeder branches, NMD device locations, and solar generation distribution.")

    if not poles_dict:
        st.info("No feeder pole columns found in 'Poles' sheet.")
    else:
        # Build comprehensive network topology
        network_topo = build_network_topology(poles_dict, names_df, solar_df)
        net_summary_df = get_network_summary_dataframe(network_topo)

        # Top Network KPI Summary Cards
        tf_info = network_topo["transformer"]
        total_feeder_line_poles = sum(len(f["unique_poles"]) for f in network_topo["feeders"].values())
        total_net_poles = total_feeder_line_poles + 1  # 1 central Distribution Transformer pole
        total_nmds_count = len(network_topo["nmd_poles"])
        total_solar_poles = len(network_topo["solar_poles"])
        total_solar_kw = sum(s["effective_kw"] for s in network_topo["solar_poles"].values())

        col_nt1, col_nt2, col_nt3, col_nt4 = st.columns(4)
        with col_nt1:
            tf_topo_no = tf_info.get('db_name') if (tf_info.get('db_name') and str(tf_info.get('db_name')).strip() and tf_info.get('nickname', '').upper() in ["T/F", "TF", "TRANS", "TRANSFORMER"]) else (tf_info.get('db_name') or tf_info.get('nickname'))
            st.metric("Distribution Transformer", f"{tf_topo_no}", f"Pole: {tf_info['pole_id']}")
        with col_nt2:
            st.metric("Total Network Poles", f"{total_net_poles} Poles", f"{len(network_topo['feeders'])} Feeders + 1 Dist T/F")
        with col_nt3:
            st.metric("NMD Monitoring Nodes", f"{total_nmds_count} NMDs", "Middle & Feeder Ends")
        with col_nt4:
            st.metric("Solar Penetration", f"{total_solar_kw:.1f} kW", f"{total_solar_poles} Solar-Enabled Poles")

        # Interactive Controls
        st.write("")
        feeder_lookup = network_topo.get("feeder_name_lookup", {})
        def format_feeder_choice(fk):
            if fk == "All Feeders":
                return "🌐 All Feeders"
            name = feeder_lookup.get(fk, "")
            return f"{fk} - {name}" if name else fk

        feeder_options = ["All Feeders"] + list(network_topo["feeders"].keys())
        
        col_ctrl1, col_ctrl2, col_ctrl3 = st.columns([2, 2, 2])
        with col_ctrl1:
            sel_feeder_view = st.radio("Feeder Selection:", feeder_options, horizontal=True, format_func=format_feeder_choice)
        with col_ctrl2:
            pole_view_mode = st.radio(
                "Poles Visibility:",
                ["⭐ Special Poles Only", "⚫ Show All Distribution Poles"],
                horizontal=True,
                help="By default, shows only special nodes (Distribution Transformer, Solar, NMDs, Junctions). Toggle to show all intermediate line poles."
            )
            show_all_poles = (pole_view_mode == "⚫ Show All Distribution Poles")
        with col_ctrl3:
            label_mode = st.selectbox(
                "Label Display Density:",
                ["Standard", "Detailed", "All Poles", "Minimal"],
                format_func=lambda x: {
                    "Standard": "⚡ Standard (Clean Badges - Recommended)",
                    "Detailed": "🏷️ Detailed (Pole ID + Capacity)",
                    "All Poles": "🔢 All Poles (Every Pole Number)",
                    "Minimal": "📐 Clean SLD (Hover for Details)"
                }[x],
                index=0
            )

        st.caption("💡 **Tip**: Showing special poles only keeps the schematic uncluttered (matching standard single-line diagrams). Click any feeder to isolate it.")

        # 1. Plotly Single-Line Schematic Figure
        fig_schematic = create_network_schematic_figure(
            network_topo,
            selected_feeder=sel_feeder_view,
            show_all_poles=show_all_poles,
            label_mode=label_mode
        )
        st.plotly_chart(
            fig_schematic,
            use_container_width=True,
            key="fig_schematic",
            config={"scrollZoom": True, "displayModeBar": True, "responsive": True}
        )

        # Electrical SLD Legend Banner
        guide_bg = "#1E293B" if dark_mode else "#F8FAFC"
        guide_border = "#334155" if dark_mode else "#E2E8F0"
        guide_title = "#93C5FD" if dark_mode else "#1E3A8A"
        guide_text = "#CBD5E1" if dark_mode else "#334155"
        st.markdown(f"""
        <div style="background-color: {guide_bg}; border: 1px solid {guide_border}; border-radius: 8px; padding: 12px 18px; margin-bottom: 20px; color: {guide_text};">
            <span style="font-weight: 700; color: {guide_title};">📌 11kV / 400V Distribution Network Schematic Guide:</span><br/>
            • <strong>⚡ 11kV / 400V Distribution Transformer:</strong> Located at the central pole (<code>ST13/9</code>) with incoming 11kV medium-voltage supply line and standard interlocking primary/secondary winding circles (IEC 60617 / IEEE 315).<br/>
            • <strong>━ Main Feeder Conductors:</strong> Solid prominent lines representing continuous main feeder lines to ends.<br/>
            • <strong>━ Spur Feeder Conductors:</strong> Solid branch lines with 45° takeoff ramps and non-intersecting parallel runs.<br/>
            • <strong>🔗 Junction Poles:</strong> Dark open rings highlighting exact physical tap-off poles where spurs branch from the main feeder.<br/>
            • <strong>📌 NMD Monitoring Points:</strong> Cyan diamond markers at Middle and Feeder End monitoring locations.<br/>
            • <strong>🟡 Solar Generation Poles:</strong> Amber circular markers scaled proportionally to effective solar capacity (kW = min(Inverter, Installed)).
        </div>
        """, unsafe_allow_html=True)

        # 2. Comprehensive Feeder Summary Table
        st.markdown("---")
        st.markdown("#### 📋 Feeder Network Summary Table")
        st.dataframe(net_summary_df, use_container_width=True, hide_index=True)

        # 3. Detailed Feeder Pole Hierarchy & Branch Breakdown
        st.markdown("---")
        st.markdown("#### 🌳 Feeder Branch Breakdown & Pole Hierarchy")
        
        avail_feeders = list(network_topo["feeders"].keys())
        detail_feeder = st.selectbox("Select Feeder for Detailed Pole Inspection:", avail_feeders, index=0, format_func=format_feeder_choice)
        # Exclude distribution transformer pole so it is used only once and not repeated in every feeder
        raw_poles_list = poles_dict[detail_feeder]
        poles_list = [p for p in raw_poles_list if str(p).strip() != tf_info['pole_id']]
        st.caption(f"Feeder **{format_feeder_choice(detail_feeder)}** originates from central **Distribution Transformer** at Pole <code>{tf_info['pole_id']}</code>. Displaying {len(poles_list)} feeder distribution poles.")

        def parse_pole_hierarchy(poles: list) -> pd.DataFrame:
            records = []
            for p in poles:
                p_clean = str(p).strip()
                if not p_clean:
                    continue
                
                # Check for spurs
                if "/" in p_clean:
                    parent = p_clean.split("/")[0]
                    spur_level = "Sub-Spur" if any(c.isalpha() for c in p_clean.split("/")[-1]) else "Spur Branch"
                    category = f"Spur from {parent}"
                elif "-" in p_clean:
                    parent = p_clean.split("-")[0]
                    category = f"Spur from {parent}"
                elif any(c.isalpha() for c in p_clean[2:]) if len(p_clean) > 2 else False:
                    base = "".join([c for c in p_clean if not (c.isalpha() and p_clean.index(c) > 1)])
                    category = f"Spur from {base}"
                else:
                    category = "Main Feeder"

                # Check if NMD is at this pole
                matching_nmd = names_df[names_df["Pole_ID"] == p_clean]
                nmd_tag = f"📌 {matching_nmd['Nickname'].iloc[0]} ({matching_nmd['Role'].iloc[0]})" if len(matching_nmd) > 0 else "None"

                # Check solar customers at this pole
                matching_solar = solar_df[solar_df["Pole_ID"] == p_clean] if len(solar_df) > 0 else pd.DataFrame()
                solar_kw = matching_solar["Effective_Capacity_kW"].sum() if len(matching_solar) > 0 else 0.0
                solar_tag = f"{solar_kw:.1f} kW ({len(matching_solar)} cust)" if solar_kw > 0 else "None"

                records.append({
                    "Pole_ID": p_clean,
                    "Branch_Type": category,
                    "NMD_Device": nmd_tag,
                    "Solar_Generation": solar_tag,
                    "Solar_kW": solar_kw
                })
            return pd.DataFrame(records)

        df_hierarchy = parse_pole_hierarchy(poles_list)

        col_p1, col_p2 = st.columns([1, 2])
        with col_p1:
            branch_counts = df_hierarchy["Branch_Type"].value_counts().reset_index()
            branch_counts.columns = ["Branch", "Pole Count"]
            st.dataframe(branch_counts, use_container_width=True, hide_index=True)
            tot_f_solar = df_hierarchy["Solar_kW"].sum()
            st.metric("Total Solar Capacity on this Feeder", f"{tot_f_solar:.1f} kW")

        with col_p2:
            st.dataframe(df_hierarchy, use_container_width=True, height=360)


# ==========================================
# TAB 4: SOLAR CUSTOMERS
# ==========================================
with tab_solar:
    st.markdown("### ☀️ Solar Customer Details & Capacity Calculation")
    
    if len(solar_df) == 0:
        st.info("No records found in 'Solar Customers' sheet.")
    else:
        st.markdown("""
        > [!NOTE]
        > **Solar Capacity Rule:** As specified, effective solar capacity is evaluated as **`min(Inverter_Capacity, Installed_Capacity)`**.
        """)

        # KPI metrics
        col_s1, col_s2, col_s3, col_s4 = st.columns(4)
        with col_s1:
            st.metric("Total Solar Customers", f"{len(solar_df)}")
        with col_s2:
            st.metric("Total Effective Capacity", f"{solar_df['Effective_Capacity_kW'].sum():.1f} kW")
        with col_s3:
            st.metric("Total Inverter Capacity", f"{solar_df['Inverter_Capacity_kW'].sum():.1f} kW")
        with col_s4:
            st.metric("Total Installed Capacity", f"{solar_df['Installed_Capacity_kW'].sum():.1f} kWp")

        # Capacity per pole chart
        pole_solar = solar_df.groupby("Pole_ID")["Effective_Capacity_kW"].sum().reset_index().sort_values("Effective_Capacity_kW", ascending=False)
        fig_pole_sol = px.bar(
            pole_solar, x="Pole_ID", y="Effective_Capacity_kW",
            title="Effective Solar Capacity by Connected Pole (kW)",
            labels={"Effective_Capacity_kW": "Capacity (kW)", "Pole_ID": "Pole ID"},
            color="Effective_Capacity_kW",
            color_continuous_scale="Viridis"
        )
        fig_pole_sol.update_layout(margin=dict(l=40, r=40, t=40, b=40))
        st.plotly_chart(fig_pole_sol, use_container_width=True, key="fig_pole_sol")

        st.markdown("#### 📋 Solar Customer Directory")
        st.dataframe(solar_df, use_container_width=True, height=280)


# ==========================================
# TAB 6: SOLUTIONS & MITIGATION ADVISORY
# ==========================================
with tab_solutions:
    st.markdown("### 💡 Comprehensive Engineering Solutions & Mitigation Advisory")
    st.caption("Automated decision tree and prioritized intervention matrix based on empirical NMD field measurements and utility engineering practices.")

    # Executive Advisory Alert Banner
    sol_ct = mitigation_solutions["ct_solution"]
    sol_tf = mitigation_solutions["transformer_solution"]
    sol_lv = mitigation_solutions["lv_mitigation"]
    sol_hv = mitigation_solutions["hv_mitigation"]
    sol_sections = mitigation_solutions["sectional_localizations"]
    df_actions = mitigation_solutions["action_matrix_df"]

    if not sol_ct["is_normal"]:
        st.markdown(f"""
        <div class="alert-banner-red">
            <h4 style="margin: 0; color: #991B1B;">🚨 Priority 1: Current Transformer (CT) Wiring Polarity Inverted</h4>
            <p style="margin-top: 6px; margin-bottom: 4px; font-size: 0.95rem;">
                <b>Identified Mode:</b> {sol_ct['mode']} ({', '.join(sol_ct['affected_phases'])} reversed).<br>
                <b>Corrective Action:</b> {sol_ct['solution_title']}. Swap physical secondary CT leads at NMD terminal block.<br>
                <b>⚠️ Overload Assessment Indeterminate:</b> Because CT polarities are inverted, active/reactive power readings and directional flows are corrupted. Transformer loading cannot be accurately determined until CT connections are corrected.
            </p>
        </div>
        """, unsafe_allow_html=True)
    elif sol_tf["is_overloaded"]:
        st.markdown(f"""
        <div class="alert-banner-red">
            <h4 style="margin: 0; color: #991B1B;">⚡ Priority 2: Distribution Transformer Overloaded ({sol_tf['peak_loading_pct']:.1f}%)</h4>
            <p style="margin-top: 6px; margin-bottom: 4px; font-size: 0.95rem;">
                Peak average demand reached <b>{sol_tf['peak_kva']:.1f} kVA</b> at <b>{sol_tf.get('avg_peak_time', 'peak period')}</b> against rated capacity of <b>{sol_tf['rated_cap']:.0f} kVA</b> on the representative 24-hour diurnal demand curve. Substation augmentation or new transformer installation is required.
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div class="alert-banner-green">
            <h4 style="margin: 0; color: #065F46;">✅ Substation Operating Within Rated Limits (Average Demand Baseline)</h4>
            <p style="margin-top: 6px; margin-bottom: 4px; font-size: 0.95rem;">
                CT secondary polarity is verified normal (100% confidence). Representative 24-hour average peak demand is <b>{sol_tf['peak_loading_pct']:.1f}%</b> ({sol_tf['peak_kva']:.1f} kVA of {sol_tf['rated_cap']:.0f} kVA at {sol_tf.get('avg_peak_time', 'peak period')}), leaving <b>{sol_tf['headroom_kva']:.1f} kVA</b> operational thermal headroom. Transformer is not overloaded.
            </p>
        </div>
        """, unsafe_allow_html=True)

    # --------------------------------------------------------------------------
    # DIRECT SOLUTIONS & ACTION DIRECTIVES (EXECUTIVE ACTION SUMMARY)
    # --------------------------------------------------------------------------
    direct_solutions = mitigation_solutions.get("direct_solutions", [])
    st.markdown("#### 🎯 Direct Engineering Solutions (Field Action Directives)")
    st.caption("Direct, concise engineering interventions required in the field, listed in priority order with specific feeders and phase transfers.")

    if not direct_solutions:
        st.success("✅ **All Feeders Compliant**: No immediate physical line interventions or phase transfers required.")
    else:
        for sol in direct_solutions:
            prio = sol.get("priority", "P2")
            icon = sol.get("icon", "⚡")
            act_text = sol.get("direct_solution", "")
            details = sol.get("details", "")
            cat_name = sol.get("action_type", "Field Action")
            
            if "P1" in prio or "Critical" in prio:
                bg = "#2A0E0E" if dark_mode else "#FEF2F2"
                border = "#EF4444" if dark_mode else "#DC2626"
                badge_bg = "#450A0A" if dark_mode else "#FEE2E2"
                badge_txt = "#FCA5A5" if dark_mode else "#991B1B"
            elif "P2" in prio or "High" in prio:
                bg = "#271C0C" if dark_mode else "#FFFBEB"
                border = "#F59E0B" if dark_mode else "#D97706"
                badge_bg = "#451A03" if dark_mode else "#FEF3C7"
                badge_txt = "#FCD34D" if dark_mode else "#B45309"
            else:
                bg = "#062B1D" if dark_mode else "#F0FDF4"
                border = "#10B981" if dark_mode else "#16A34A"
                badge_bg = "#064E3B" if dark_mode else "#DCFCE7"
                badge_txt = "#6EE7B7" if dark_mode else "#15803D"
                
            title_col = "#F8FAFC" if dark_mode else "#0F172A"
            details_col = "#CBD5E1" if dark_mode else "#475569"
            st.markdown(f"""
            <div style="background-color: {bg}; border: 1px solid {border}60; border-left: 6px solid {border}; border-radius: 8px; padding: 12px 18px; margin-bottom: 10px;">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <span style="font-size: 1.05rem; font-weight: 700; color: {title_col};">
                        {icon} {act_text}
                    </span>
                    <span style="background-color: {badge_bg}; color: {badge_txt}; padding: 3px 10px; border-radius: 12px; font-size: 0.78rem; font-weight: 600;">
                        {prio} • {cat_name}
                    </span>
                </div>
                <div style="color: {details_col}; font-size: 0.88rem; margin-top: 4px;">
                    {details}
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.write("")
    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 1: CT POLARITY RESOLUTION & TRANSFORMER OVERLOAD GATE
    # --------------------------------------------------------------------------
    st.markdown("#### 1. Current Transformer (CT) Polarity Verification & Load Assessment Prerequisite")
    col_c1, col_c2 = st.columns([1, 2])
    with col_c1:
        st.metric("CT Polarity Status", "Normal" if sol_ct["is_normal"] else "Reversed", delta=f"{sol_ct['confidence']:.1f}% Conf", delta_color="normal" if sol_ct["is_normal"] else "inverse")
        st.metric("Dominant Operating Mode", sol_ct["mode"])
    with col_c2:
        if sol_ct["is_normal"]:
            st.success("✅ **CT Wiring Verified**: All CT secondary circuits match normal power import polarity across nighttime baseline and daytime solar periods. Directional power flow and transformer capacity metrics are physically valid.")
        else:
            st.error(f"🚨 **Action Required**: {sol_ct['solution_title']}\n\n{sol_ct['solution_desc']}")
            st.warning(f"⚠️ **Engineering Rule**: {sol_ct['overload_blocked_reason']}")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 2: TRANSFORMER LOADING CAPACITY PLAN
    # --------------------------------------------------------------------------
    st.markdown("#### 2. Substation Loading & Transformer Overload Capacity Plan (Average Demand Baseline)")
    col_t1, col_t2, col_t3, col_t4 = st.columns(4)
    with col_t1:
        st.metric("Peak Average Demand", f"{sol_tf['peak_kva']:.1f} kVA", help="Maximum net demand on the 24-hour representative diurnal curve")
    with col_t2:
        st.metric("Rated Capacity", f"{sol_tf['rated_cap']:.0f} kVA")
    with col_t3:
        st.metric("Average Loading %", f"{sol_tf['peak_loading_pct']:.1f}%", delta=f"{sol_tf['status']}", delta_color="inverse" if sol_tf["is_overloaded"] else "normal")
    with col_t4:
        st.metric("Available Headroom", f"{sol_tf['headroom_kva']:.1f} kVA")

    if not sol_tf["evaluation_valid"]:
        st.info("ℹ️ **Loading Assessment Deferred**: Accurate transformer capacity utilization cannot be evaluated until CT wiring is corrected.")
    elif sol_tf["is_overloaded"]:
        st.error(f"⚠️ **Transformer Overload on Average Demand Curve ({sol_tf['peak_loading_pct']:.1f}%)**: The 24-hour average demand profile exceeds thermal nameplate capacity ({sol_tf['peak_kva']:.1f} kVA > {sol_tf['rated_cap']:.0f} kVA at {sol_tf.get('avg_peak_time', 'peak period')}).")
        col_ov1, col_ov2 = st.columns(2)
        with col_ov1:
            st.markdown("""
            **Option A: Substation Augmentation (Capacity Upgrade)**
            - Replace existing transformer with the next standard IEC rating (e.g. 160 kVA → 250 kVA, or 250 kVA → 400 kVA).
            - Restores operating loading to < 80% with ample reserve capacity for load growth.
            """)
        with col_ov2:
            st.markdown("""
            **Option B: New Transformer Installation & Load Deloading**
            - Construct an adjacent 11kV/400V distribution substation closer to downstream load pockets.
            - Bifurcate existing feeders and transfer one or two heavily loaded radial branches to deload the existing unit.
            """)
    else:
        st.success(f"✅ **Capacity Adequate (Average Demand Baseline)**: Transformer operates safely within rated nameplate capacity with {sol_tf['headroom_kva']:.1f} kVA reserve headroom on the 24-hour representative average demand curve (Peak: {sol_tf['peak_kva']:.1f} kVA at {sol_tf.get('avg_peak_time', 'N/A')}).")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 3: LOW VOLTAGE (LV < 216.2V) MITIGATION ACTION PLAN
    # --------------------------------------------------------------------------
    st.markdown("#### 3. Low Voltage (LV < 216.2 V) Statutory Mitigation Action Plan")
    if sol_lv.get("system_wide_lv_issue", False):
        st.error("""
        🚨 **Concurrent System-Wide Low Voltage Detected (Substation Bus + Feeder Ends):**
        - **1. Cross-Check Upstream 11 kV Substation**: Check nearby distribution transformers fed from the same 11 kV line. If nearby transformers display identical undervoltage, the root cause is upstream 11 kV line drop or primary grid substation AVR tap setting.
        - **2. Distribution Transformer Tap Changer Adjustment**: If upstream 11 kV is normal, raise the transformer Off-Circuit Tap Changer (OCTC) to a higher position (**Tap 3 or Tap 4**, +2.5% to +5.0% boost) to elevate the entire secondary 400V/230V busbar voltage baseline by ~5.7V to 11.5V.
        """)

    feeder_lookup = network_topo.get("feeder_name_lookup", {}) if network_topo else {}
    st.markdown("**Per-Feeder Low Voltage Findings & Engineering Interventions:**")
    lv_feeders = sol_lv.get("feeder_analysis", [])
    if not lv_feeders:
        st.info("No feeder monitoring devices available for per-feeder low voltage analysis.")
    else:
        for fa in lv_feeders:
            f_disp = fa.get("feeder_display") or get_feeder_display_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            if fa.get("violation_category", "None") == "None":
                st.success(f"✅ **Feeder {f_disp} ({fa.get('end_device', '')})**: Fully Compliant (All phases LV violations ≤ 1.0%).")
            else:
                with st.expander(f"📉 Feeder {f_disp} ({fa.get('end_device', '')}) — {fa.get('violation_category', '')} Undervoltage ({fa.get('worst_phase', '—')} worst: {fa.get('worst_phase_pct', 0.0):.2f}%)", expanded=(fa.get("worst_phase_pct", 0.0) > 1.0)):
                    direct_sol_line = fa.get("direct_solution", "")
                    if direct_sol_line:
                        ds_bg = "#0F2042" if dark_mode else "#EFF6FF"
                        ds_border = "#1E3A8A" if dark_mode else "#BFDBFE"
                        ds_title = "#60A5FA" if dark_mode else "#1E40AF"
                        ds_txt = "#F8FAFC" if dark_mode else "#0F172A"
                        st.markdown(f"""
                        <div style="background: {ds_bg}; border: 1px solid {ds_border}; border-left: 5px solid #2563EB; padding: 10px 16px; border-radius: 6px; margin-bottom: 12px;">
                            <span style="font-weight: 700; color: {ds_title}; font-size: 0.95rem;">🎯 Direct Solution:</span>
                            <span style="color: {ds_txt}; font-weight: 600; font-size: 0.95rem; margin-left: 6px;">{direct_sol_line}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    st.markdown(f"**Violating Phase(s):** `{', '.join(fa.get('violating_phases', []))}` | **Worst-Affected Phase:** `{fa.get('worst_phase', '—')}` ({fa.get('worst_phase_pct', 0.0):.2f}%)")
                    for rec in fa.get("recommendations", []):
                        st.markdown(f"• **{rec['title']}** ({rec['type']}):\n  {rec['description']}")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 4: HIGH VOLTAGE (HV > 243.8V) MITIGATION ACTION PLAN
    # --------------------------------------------------------------------------
    st.markdown("#### 4. High Voltage (HV > 243.8 V) Statutory Mitigation Action Plan")
    if sol_hv.get("system_wide_hv_issue", False):
        st.warning("""
        ⚠️ **Concurrent System-Wide High Voltage Detected (Substation Bus + Feeder Ends):**
        - **1. Cross-Check Upstream 11 kV Grid (Nighttime Swell Check)**: Check nearby distribution transformers. If overvoltage persists at night across non-solar substations, the primary 11 kV distribution grid voltage is elevated (light loading, MV cable capacitance, or grid AVR setpoint).
        - **2. Distribution Transformer Tap Changer Adjustment**: Lower the transformer Off-Circuit Tap Changer (OCTC) to a lower position (**Tap 1 or Tap 2**, -2.5% to -5.0% buck) to step down secondary voltage across all feeders into statutory tolerance.
        """)

    st.markdown("**Per-Feeder High Voltage Findings & Solar Integration Interventions:**")
    hv_feeders = sol_hv.get("feeder_analysis", [])
    if not hv_feeders:
        st.info("No feeder monitoring devices available for per-feeder high voltage analysis.")
    else:
        for fa in hv_feeders:
            f_disp = fa.get("feeder_display") or get_feeder_display_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            if fa.get("violation_category", "None") == "None":
                st.success(f"✅ **Feeder {f_disp} ({fa.get('end_device', '')})**: Fully Compliant (All phases HV violations ≤ 1.0%).")
            else:
                solar_badge = f"☀️ Solar: {fa.get('feeder_solar_kw', 0.0):.1f} kW" if fa.get("has_solar", False) else "No Solar Customers"
                with st.expander(f"📈 Feeder {f_disp} ({fa.get('end_device', '')}) — {fa.get('violation_category', '')} Overvoltage [{solar_badge}]", expanded=True):
                    direct_sol_line = fa.get("direct_solution", "")
                    if direct_sol_line:
                        ds_bg = "#0F2042" if dark_mode else "#EFF6FF"
                        ds_border = "#1E3A8A" if dark_mode else "#BFDBFE"
                        ds_title = "#60A5FA" if dark_mode else "#1E40AF"
                        ds_txt = "#F8FAFC" if dark_mode else "#0F172A"
                        st.markdown(f"""
                        <div style="background: {ds_bg}; border: 1px solid {ds_border}; border-left: 5px solid #2563EB; padding: 10px 16px; border-radius: 6px; margin-bottom: 12px;">
                            <span style="font-weight: 700; color: {ds_title}; font-size: 0.95rem;">🎯 Direct Solution:</span>
                            <span style="color: {ds_txt}; font-weight: 600; font-size: 0.95rem; margin-left: 6px;">{direct_sol_line}</span>
                        </div>
                        """, unsafe_allow_html=True)
                    st.markdown(f"**Violating Phase(s):** `{', '.join(fa.get('violating_phases', []))}` | **Worst Phase:** `{fa.get('worst_phase', '—')}` ({fa.get('worst_phase_pct', 0.0):.2f}%)")
                    for rec in fa.get("recommendations", []):
                        st.markdown(f"• **{rec['title']}** ({rec['type']}):\n  {rec['description']}")

    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 5: SECTIONAL PROBLEM LOCALIZATION (MIDDLE NMD vs. END NMD)
    # --------------------------------------------------------------------------
    st.markdown("#### 5. Sectional Problem Localization (Middle NMD vs. Feeder End NMD)")
    st.caption("Compares voltage drops between the Middle NMD and Feeder End NMD to isolate the exact line segment causing the constraint.")

    if not sol_sections:
        st.info("No paired Middle and End NMD devices available for sectional localization.")
    else:
        for sl in sol_sections:
            sl_disp = sl.get("feeder_display") or get_feeder_display_name(sl.get("feeder_key", ""), lookup=feeder_lookup)
            badge_color = "green" if "Compliant" in sl.get("problem_segment", "") else ("orange" if "Outer" in sl.get("problem_segment", "") else "red")
            card_bg = "#1E293B" if dark_mode else "#F8FAFC"
            card_title_col = "#F8FAFC" if dark_mode else "#1E293B"
            card_mid_col = "#CBD5E1" if dark_mode else "#334155"
            card_diag_col = "#94A3B8" if dark_mode else "#475569"
            if badge_color == "green":
                b_badge_bg = "#064E3B" if dark_mode else "#ECFDF5"
                b_badge_txt = "#6EE7B7" if dark_mode else "#065F46"
                b_border_col = "#10B981" if dark_mode else "#059669"
            elif badge_color == "orange":
                b_badge_bg = "#451A03" if dark_mode else "#FFFBEB"
                b_badge_txt = "#FCD34D" if dark_mode else "#B45309"
                b_border_col = "#F59E0B" if dark_mode else "#D97706"
            else:
                b_badge_bg = "#450A0A" if dark_mode else "#FEF2F2"
                b_badge_txt = "#FCA5A5" if dark_mode else "#991B1B"
                b_border_col = "#EF4444" if dark_mode else "#DC2626"

            with st.container():
                st.markdown(f"""
                <div style="border-left: 5px solid {b_border_col}; background: {card_bg}; padding: 14px 18px; border-radius: 8px; margin-bottom: 12px; border: 1px solid {'#334155' if dark_mode else '#E2E8F0'};">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: {card_title_col};">Feeder {sl_disp}: {sl.get('middle_device', '')} (Pole {sl.get('middle_pole', '')}) ➔ {sl.get('end_device', '')} (Pole {sl.get('end_pole', '')})</h4>
                        <span style="background: {b_badge_bg}; color: {b_badge_txt}; padding: 4px 10px; border-radius: 6px; font-weight: 600; font-size: 0.85rem;">
                            {sl.get('problem_segment', '')}
                        </span>
                    </div>
                    <div style="margin-top: 8px; font-size: 0.9rem; color: {card_mid_col};">
                        <b>Middle NMD ({sl.get('middle_device', '')}):</b> {sl.get('middle_avg_v', 0.0):.1f} V (Worst LV: {sl.get('middle_lv_pct', 0.0):.2f}%) &nbsp;|&nbsp; 
                        <b>End NMD ({sl.get('end_device', '')}):</b> {sl.get('end_avg_v', 0.0):.1f} V (Worst LV: {sl.get('end_lv_pct', 0.0):.2f}%) &nbsp;|&nbsp; 
                        <b>Outer Section Drop (ΔV):</b> {sl.get('outer_delta_v', 0.0):.1f} V
                    </div>
                    <p style="margin-top: 8px; margin-bottom: 4px; font-size: 0.88rem; color: {card_diag_col};">
                        <b>Diagnostic Finding:</b> {sl.get('diagnosis', '')}<br>
                        <b>Targeted Action Plan:</b> {sl.get('action_plan', '')}
                    </p>
                </div>
                """, unsafe_allow_html=True)

    st.markdown("---")

    # --------------------------------------------------------------------------
    # STEP 6: MASTER PRIORITIZED MITIGATION ACTION MATRIX
    # --------------------------------------------------------------------------
    st.markdown("#### 6. Master Prioritized Engineering Action Matrix")
    st.caption("Consolidated intervention table detailing priority, target node, observed problem, primary action, and localized line segment.")

    if not df_actions.empty:
        st.dataframe(
            df_actions,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Priority": st.column_config.TextColumn("Priority", width="medium"),
                "Category": st.column_config.TextColumn("Category", width="small"),
                "Target Device / Feeder": st.column_config.TextColumn("Target Node / Feeder", width="medium"),
                "Observed Problem": st.column_config.TextColumn("Observed Problem", width="large"),
                "Affected Phase(s)": st.column_config.TextColumn("Phases", width="small"),
                "Primary Recommended Action": st.column_config.TextColumn("Primary Recommended Action", width="large"),
                "Secondary Options / Alternatives": st.column_config.TextColumn("Secondary Alternatives", width="large"),
                "Target Location": st.column_config.TextColumn("Target Location", width="medium"),
            }
        )

        csv_data = df_actions.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Mitigation Action Matrix (CSV)",
            data=csv_data,
            file_name=f"Mitigation_Action_Matrix_{tf_clean_id}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime="text/csv",
            use_container_width=False
        )


# ==========================================
# TAB 5: NAMES & RAW DATA
# ==========================================
with tab_raw:
    st.markdown("### 📋 Names Mapping & Raw Data Inspector")
    
    col_r1, col_r2 = st.columns([1, 1])
    with col_r1:
        st.markdown("#### 🏷️ Device Mapping (Names Sheet)")
        st.dataframe(names_df, use_container_width=True)
    
    with col_r2:
        st.markdown("#### 📑 Sheets Detected in Workbook")
        st.json(parsed_data.get("sheets_found", []))

    st.markdown("---")
    st.markdown("#### 💾 Download Pre-built Benchmark Datasets (30 Days)")
    st.caption("You can download these sample workbooks to test or share with colleagues.")
    
    c_d1, c_d2, c_d3, c_d4 = st.columns(4)
    with c_d1:
        if os.path.exists("Sample_NMD_Normal_30Days.xlsx"):
            with open("Sample_NMD_Normal_30Days.xlsx", "rb") as f:
                st.download_button("📥 Normal CTs (.xlsx)", data=f.read(), file_name="Sample_NMD_Normal_30Days.xlsx")
    with c_d2:
        if os.path.exists("Sample_NMD_PhaseA_Reversed_30Days.xlsx"):
            with open("Sample_NMD_PhaseA_Reversed_30Days.xlsx", "rb") as f:
                st.download_button("📥 Phase A Reversed (.xlsx)", data=f.read(), file_name="Sample_NMD_PhaseA_Reversed_30Days.xlsx")
    with c_d3:
        if os.path.exists("Sample_NMD_All_Reversed_30Days.xlsx"):
            with open("Sample_NMD_All_Reversed_30Days.xlsx", "rb") as f:
                st.download_button("📥 All 3 CTs Reversed (.xlsx)", data=f.read(), file_name="Sample_NMD_All_Reversed_30Days.xlsx")
    with c_d4:
        if os.path.exists("Sample_NMD_PhaseBC_Reversed_30Days.xlsx"):
            with open("Sample_NMD_PhaseBC_Reversed_30Days.xlsx", "rb") as f:
                st.download_button("📥 Phase B&C Reversed (.xlsx)", data=f.read(), file_name="Sample_NMD_PhaseBC_Reversed_30Days.xlsx")

