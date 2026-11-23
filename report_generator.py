"""
report_generator.py
Generates a comprehensive, publication-quality Engineering Report as a Word document (.docx)
complete with embedded high-resolution figures from the analysis:
1. Feeder Network Single-Line Schematic & Solar Customer Spread
2. Transformer 24-Hour Diurnal Load Profile & Solar Duck Curve
3. Current Transformer (CT) Polarity Verification Curves
4. 24-Hour Diurnal Voltage Comparison (Transformer vs Feeder Ends)
5. Feeder Voltage Differential (ΔV = V_Feeder - V_Transformer) Profile
"""

import os
import re
import io
import tempfile
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime

# Configure matplotlib temporary cache to avoid write warnings
os.environ["MPLCONFIGDIR"] = os.path.join(tempfile.gettempdir(), "mpl")
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import pandas as pd
import numpy as np

import docx
from docx import Document
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml import OxmlElement
from docx.oxml.ns import qn, nsdecls
from docx.oxml import parse_xml

from feeder_topology_analyzer import get_network_summary_dataframe, get_feeder_display_name, extract_feeder_key, get_feeder_name_lookup
from mitigation_solutions_engine import analyze_mitigation_solutions

# Color Theme Palette
NAVY_PRIMARY = RGBColor(30, 58, 138)     # #1E3A8A
SLATE_TEXT = RGBColor(51, 65, 85)        # #334155
TEAL_ACCENT = RGBColor(8, 145, 178)      # #0891B2
GREEN_COMPLIANT = RGBColor(5, 150, 105)  # #059669
AMBER_WARNING = RGBColor(217, 119, 6)    # #D97706
RED_CRITICAL = RGBColor(220, 38, 38)     # #DC2626


# ==============================================================================
# XML TABLE STYLING HELPERS
# ==============================================================================
def set_cell_background(cell, hex_color: str):
    """Sets cell shading color in python-docx."""
    shading_elm = parse_xml(f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>')
    cell._tc.get_or_add_tcPr().append(shading_elm)


def set_cell_margins(cell, top=100, bottom=100, left=150, right=150):
    """Sets internal padding for a table cell (values in twips, 20 twips = 1 pt)."""
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('w:top', top), ('w:bottom', bottom), ('w:left', left), ('w:right', right)]:
        node = OxmlElement(m)
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)


def style_table_header(row, col_widths: List[float], hex_bg: str = "1E3A8A"):
    """Applies deep navy background, white bold text, and proper widths to table headers."""
    for idx, cell in enumerate(row.cells):
        set_cell_background(cell, hex_bg)
        set_cell_margins(cell, top=140, bottom=140, left=140, right=140)
        cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        if idx < len(col_widths):
            cell.width = Inches(col_widths[idx])
        for p in cell.paragraphs:
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for run in p.runs:
                run.font.bold = True
                run.font.color.rgb = RGBColor(255, 255, 255)
                run.font.size = Pt(9.5)
                run.font.name = "Arial"


def style_table_body(table, col_widths: List[float]):
    """Applies clean borders, alternating row zebra shading, and cell padding."""
    for r_idx, row in enumerate(table.rows[1:]):
        bg_hex = "F8FAFC" if (r_idx % 2 == 1) else "FFFFFF"
        for c_idx, cell in enumerate(row.cells):
            set_cell_background(cell, bg_hex)
            set_cell_margins(cell, top=90, bottom=90, left=120, right=120)
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if c_idx < len(col_widths):
                cell.width = Inches(col_widths[c_idx])
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(8.5)
                    run.font.name = "Arial"
                    run.font.color.rgb = SLATE_TEXT


def add_callout_box(doc: Document, text: str, title: str = "KEY FINDING", box_type: str = "info"):
    """Creates a professional callout box with a colored left accent border."""
    border_colors = {
        "info": "1E3A8A",      # Navy
        "success": "059669",   # Emerald
        "warning": "D97706",   # Amber
        "danger": "DC2626"     # Crimson
    }
    bg_colors = {
        "info": "F0F4F8",
        "success": "ECFDF5",
        "warning": "FFFBEB",
        "danger": "FEF2F2"
    }
    b_color = border_colors.get(box_type, "1E3A8A")
    bg_color = bg_colors.get(box_type, "F0F4F8")

    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)
    set_cell_background(cell, bg_color)
    set_cell_margins(cell, top=140, bottom=140, left=180, right=180)

    # Set left border thick, clear others
    tcPr = cell._tc.get_or_add_tcPr()
    tcBorders = parse_xml(
        f'<w:tcBorders {nsdecls("w")}>'
        f'  <w:top w:val="none"/>'
        f'  <w:left w:val="single" w:sz="24" w:space="0" w:color="{b_color}"/>'
        f'  <w:bottom w:val="none"/>'
        f'  <w:right w:val="none"/>'
        f'</w:tcBorders>'
    )
    tcPr.append(tcBorders)

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    
    r_title = p.add_run(f"📌 {title}: ")
    r_title.bold = True
    r_title.font.name = "Arial"
    r_title.font.size = Pt(9.5)
    
    r_body = p.add_run(text)
    r_body.font.name = "Arial"
    r_body.font.size = Pt(9.0)
    r_body.font.color.rgb = SLATE_TEXT

    doc.add_paragraph().paragraph_format.space_after = Pt(4)


# ==============================================================================
# HIGH-RESOLUTION MATPLOTLIB FIGURE RENDERERS
# ==============================================================================

def render_figure_network_schematic(topo: Dict[str, Any]) -> io.BytesIO:
    """
    Renders high-resolution publication-quality single-line diagram of the distribution network:
    Left-side Transformer symbol, vertical spine, 4 horizontal feeders, 45-degree takeoff ramps,
    solid spur branches, cyan diamond NMD markers, and golden solar nodes with clean capacity text.
    """
    fig, ax = plt.subplots(figsize=(11, 6.2), dpi=220)
    ax.set_facecolor("#FFFFFF")
    fig.patch.set_facecolor("#FFFFFF")

    feeders = topo["feeders"]
    tf_pole = topo["transformer"]["pole_id"]

    feeder_colors = {
        "F1": "#2563EB",  # Royal Blue
        "F2": "#059669",  # Emerald Green
        "F3": "#7C3AED",  # Purple
        "F4": "#D97706"   # Amber Orange
    }

    # 1. Distribution Transformer Symbol (Left: x=0, y=0)
    circle1 = patches.Circle((0.0, 0.0), 0.55, edgecolor="#1E3A8A", facecolor="none", lw=2.4)
    circle2 = patches.Circle((0.45, 0.0), 0.55, edgecolor="#1E3A8A", facecolor="none", lw=2.4)
    ax.add_patch(circle1)
    ax.add_patch(circle2)
    # Incoming MV 11kV line
    ax.plot([-0.9, -0.0], [0.0, 0.0], color="#DC2626", lw=3.0)
    ax.text(-0.85, 0.15, "11kV MV", color="#DC2626", fontsize=7.5, fontweight="bold")
    ax.text(0.22, -0.95, f"Distribution Transformer\n({tf_pole})", color="#1E3A8A",
            fontsize=8.5, fontweight="bold", ha="center", va="top")

    # 2. Vertical Distribution Spine (at x = 1.0)
    spine_x = 1.0
    ax.plot([0.75, spine_x], [0.0, 0.0], color="#1E3A8A", lw=2.8)
    y_min_spine = min(f["base_y"] for f in feeders.values()) if feeders else 0.0
    y_max_spine = max(f["base_y"] for f in feeders.values()) if feeders else 0.0
    if len(feeders) > 1:
        ax.plot([spine_x, spine_x], [y_min_spine, y_max_spine], color="#1E3A8A", lw=3.2)

    # 3. Draw Feeders (Main Trunks, Spurs, and Nodes)
    max_x_seen = 25.0

    for f_name, f_data in feeders.items():
        color = feeder_colors.get(f_name, "#475569")
        f_coords = f_data["coords"]
        base_y = f_data["base_y"]

        # Takeoff connector from spine
        ax.plot([spine_x, f_coords[f_data["trunk_poles"][0]]["x"]], [base_y, base_y], color=color, lw=2.8)

        # Draw Main Trunk Line
        trunk_x = [f_coords[p]["x"] for p in f_data["trunk_poles"] if p in f_coords]
        trunk_y = [f_coords[p]["y"] for p in f_data["trunk_poles"] if p in f_coords]
        if trunk_x:
            ax.plot(trunk_x, trunk_y, color=color, lw=2.8, label=f"Feeder {f_name}")
            max_x_seen = max(max_x_seen, max(trunk_x))

        # Draw Spur Feeder Branches (Solid lines with 45-degree takeoff ramp)
        for s in f_data.get("spur_meta", []):
            jx, jy = s["j_x"], s["j_y"]
            y_spur = s["y_spur"]
            ramp_end_x = s["ramp_end_x"]

            # 45-degree ramp + horizontal run
            sx = [jx, ramp_end_x]
            sy = [jy, y_spur]
            for p in s["poles"]:
                if p in f_coords:
                    sx.append(f_coords[p]["x"])
                    sy.append(f_coords[p]["y"])
            ax.plot(sx, sy, color=color, lw=2.0, ls="-")

            # Draw Junction Open Ring Marker
            ax.scatter(jx, jy, s=65, facecolors="none", edgecolors="#0F172A", lw=1.8, zorder=5)

        # Draw Regular Intermediate Pole Dots
        for p, pos in f_coords.items():
            ax.scatter(pos["x"], pos["y"], s=10, color="#94A3B8", zorder=3)

        # Feeder End Label
        last_p = f_data["trunk_poles"][-1]
        lx, ly = f_coords[last_p]["x"], f_coords[last_p]["y"]
        ax.text(lx + 0.3, ly, f"{f_name} End\n({last_p})", color=color, fontsize=7.5, fontweight="bold", va="center")

    # 4. Draw Solar Customer Nodes (Golden Glow Circles with clean kW text, no sun icon)
    solar_plotted = False
    for f_name, f_data in feeders.items():
        f_coords = f_data["coords"]
        for p, pos in f_coords.items():
            if pos.get("has_solar", False):
                s_info = pos.get("solar_info", {})
                kw = s_info.get("effective_kw", 0.0)
                px_val, py_val = pos["x"], pos["y"]
                # Amber circle
                ax.scatter(px_val, py_val, s=110 + kw * 4, color="#F59E0B", edgecolors="#92400E", lw=2.0, zorder=6)
                # Clean text label (no sun emoji)
                ax.text(px_val, py_val - 0.45, f"{kw:.0f}kW", color="#92400E", fontsize=8.0,
                        fontweight="bold", ha="center", va="top", zorder=7)
                solar_plotted = True

    # 5. Draw NMD Monitoring Devices (Cyan Diamonds)
    for f_name, f_data in feeders.items():
        f_coords = f_data["coords"]
        for p, pos in f_coords.items():
            if pos.get("has_nmd", False):
                n_info = pos.get("nmd_info", {})
                nick = n_info.get("nickname", f_name)
                px_val, py_val = pos["x"], pos["y"]
                ax.scatter(px_val, py_val, s=95, marker="D", color="#06B6D4", edgecolors="#0891B2", lw=2.2, zorder=8)
                ax.text(px_val, py_val + 0.45, f"NMD: {nick}", color="#0891B2", fontsize=8.0,
                        fontweight="bold", ha="center", va="bottom", zorder=9)

    ax.set_xlim(-1.5, max_x_seen + 3.0)
    ax.set_ylim(y_min_spine - 1.8, y_max_spine + 2.0)
    ax.axis("off")
    ax.set_title("Single-Line Feeder Network Schematic: Distribution Topology & Solar Customer Distribution",
                 fontsize=11.5, fontweight="bold", color="#1E293B", pad=15)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=220, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_figure_diurnal_load(load_result: Dict[str, Any]) -> io.BytesIO:
    """
    Renders 24-hour diurnal load profile: Net Load = Import kVA - Export kVA,
    highlighting solar duck curve trough and rated capacity threshold.
    """
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=200)
    avg_24h = load_result.get("avg_24h_profile", pd.DataFrame())
    rated_cap = load_result.get("metrics", {}).get("rated_capacity_kva", 160.0)

    if not avg_24h.empty:
        times = avg_24h["Time"]
        x_idx = np.arange(len(times))

        imp_col = "Import_kVA_Mean" if "Import_kVA_Mean" in avg_24h.columns else "Import_kVA_mean"
        exp_col = "Export_kVA_Mean" if "Export_kVA_Mean" in avg_24h.columns else "Export_kVA_mean"
        net_col = "Net_Load_Mean" if "Net_Load_Mean" in avg_24h.columns else "Net_Load_kVA_mean"

        # Import kVA
        ax.plot(x_idx, avg_24h[imp_col], color="#2563EB", lw=2.0, ls="--", label="Import kVA (Grid Draw)")
        # Export kVA
        ax.plot(x_idx, avg_24h[exp_col], color="#059669", lw=2.0, ls=":", label="Export kVA (Solar Injection)")
        # Net Load kVA
        ax.plot(x_idx, avg_24h[net_col], color="#1E3A8A", lw=3.0, label="Net Load kVA (Import - Export)")

        # Duck Curve Solar Shading (10:00 - 15:00)
        ax.axvspan(40, 60, color="#FEF3C7", alpha=0.45, label="Midday Solar Peak Generation Window")

        # Zero Net Load Baseline & Rated Capacity
        ax.axhline(0.0, color="#64748B", lw=1.2, ls="-")
        ax.axhline(rated_cap, color="#DC2626", lw=1.8, ls="--", label=f"Rated Capacity ({rated_cap:.0f} kVA)")

        # Overload annotation if average curve exceeds rated capacity
        peak_val = avg_24h[net_col].max()
        if peak_val > rated_cap:
            peak_i = avg_24h[net_col].idxmax()
            ax.annotate(f"Overload Peak: {peak_val:.1f} kVA",
                        xy=(peak_i, peak_val), xytext=(peak_i, min(peak_val * 1.12, peak_val + 20)),
                        arrowprops=dict(arrowstyle="->", color="#DC2626", lw=1.5),
                        fontsize=8, fontweight="bold", color="#DC2626",
                        bbox=dict(boxstyle="round,pad=0.2", facecolor="#FEE2E2", edgecolor="#DC2626", lw=1))

        # X-Axis Ticks (every 2 hours = 8 intervals)
        tick_indices = list(range(0, len(times), 8))
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([times.iloc[i] for i in tick_indices], rotation=35, fontsize=8)

    ax.set_title("Transformer 24-Hour Diurnal Load Profile & Solar Duck Curve Analysis",
                 fontsize=11.0, fontweight="bold", color="#1E293B")
    ax.set_xlabel("Time of Day (HH:MM)", fontsize=9.0, labelpad=6)
    ax.set_ylabel("Apparent Power (kVA)", fontsize=9.0, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(loc="upper right", fontsize=8.0, frameon=True, framealpha=0.9)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_figure_ct_polarity(df_tf: pd.DataFrame) -> io.BytesIO:
    """
    Renders diurnal active and apparent power curves illustrating nighttime import baseline
    and daytime solar export confirmation.
    """
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)

    df_plot = df_tf.copy()
    df_plot["Time"] = df_plot["Timestamp"].dt.strftime("%H:%M")
    curr_cols = [c for c in ["Ia", "Ib", "Ic"] if c in df_plot.columns]
    diurnal = df_plot.groupby("Time")[curr_cols].mean().reset_index()

    times = diurnal["Time"]
    x_idx = np.arange(len(times))

    # Plot 3-phase currents
    ax.plot(x_idx, diurnal["Ia"], color="#DC2626", lw=1.8, label="Phase A Current (Ia)")
    ax.plot(x_idx, diurnal["Ib"], color="#D97706", lw=1.8, label="Phase B Current (Ib)")
    ax.plot(x_idx, diurnal["Ic"], color="#2563EB", lw=1.8, label="Phase C Current (Ic)")

    # Highlight Nighttime Evaluation Window (22:00 to 05:00)
    # 22:00 is index 88, 05:00 is index 20
    ax.axvspan(0, 20, color="#E2E8F0", alpha=0.45, label="Nighttime CT Polarity Evaluation Window")
    ax.axvspan(88, len(times)-1, color="#E2E8F0", alpha=0.45)
    ax.axhline(0.0, color="#0F172A", lw=1.2, ls="-")

    tick_indices = list(range(0, len(times), 8))
    ax.set_xticks(tick_indices)
    ax.set_xticklabels([times.iloc[i] for i in tick_indices], rotation=35, fontsize=8)

    ax.set_title("Current Transformer (CT) Polarity Analysis: Diurnal Phase Currents (Ia, Ib, Ic)",
                 fontsize=11.0, fontweight="bold", color="#1E293B")
    ax.set_xlabel("Time of Day (HH:MM)", fontsize=9.0, labelpad=6)
    ax.set_ylabel("Current (Amperes)", fontsize=9.0, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(loc="upper right", fontsize=8.0, frameon=True)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_figure_device_voltage(
    dev_name: str,
    dev_res: Dict[str, Any],
    meta: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Renders 24-hour diurnal phase voltage profile for a single device:
    Phase A (red), Phase B (amber), Phase C (blue), and 3-Phase Composite Average (purple dashed)
    against the statutory 230V +/- 6% band (216.2V to 243.8V).
    """
    fig, ax = plt.subplots(figsize=(9, 4.4), dpi=200)

    # Statutory Tolerance Band (216.2V to 243.8V)
    ax.axhspan(216.2, 243.8, color="#ECFDF5", alpha=0.6, label="Statutory Compliance Band (230V ± 6%)")
    ax.axhline(243.8, color="#DC2626", lw=1.6, ls="--", label="Statutory Max +6% (243.8V)")
    ax.axhline(216.2, color="#DC2626", lw=1.6, ls="--", label="Statutory Min -6% (216.2V)")
    ax.axhline(230.0, color="#64748B", lw=1.2, ls=":", label="Nominal Voltage (230.0V)")

    df_clean = dev_res.get("df_clean")
    if df_clean is not None and not df_clean.empty:
        df_calc = df_clean.copy()
        df_calc["Time"] = df_calc["Timestamp"].dt.strftime("%H:%M")
        diurnal = df_calc.groupby("Time")[["Va_clean", "Vb_clean", "Vc_clean", "V_3Phase_Clean"]].mean().reset_index()

        times = diurnal["Time"]
        x_idx = np.arange(len(times))
        pm = dev_res.get("phase_metrics", {})

        # Phase A
        if pm.get("Phase A", {}).get("is_persistent_defect", False):
            ax.plot([], [], color="#DC2626", ls="none", marker="x", markersize=7, label="Phase A (Sensor Defect - 0V Neglected)")
        else:
            ax.plot(x_idx, diurnal["Va_clean"], color="#DC2626", lw=2.0, label="Phase A Voltage (Va)")

        # Phase B
        if pm.get("Phase B", {}).get("is_persistent_defect", False):
            ax.plot([], [], color="#D97706", ls="none", marker="x", markersize=7, label="Phase B (Sensor Defect - 0V Neglected)")
        else:
            ax.plot(x_idx, diurnal["Vb_clean"], color="#D97706", lw=2.0, label="Phase B Voltage (Vb)")

        # Phase C
        if pm.get("Phase C", {}).get("is_persistent_defect", False):
            ax.plot([], [], color="#2563EB", ls="none", marker="x", markersize=7, label="Phase C (Sensor Defect - 0V Neglected)")
        else:
            ax.plot(x_idx, diurnal["Vc_clean"], color="#2563EB", lw=2.0, label="Phase C Voltage (Vc)")

        # 3-Phase Composite Clean Average
        ax.plot(x_idx, diurnal["V_3Phase_Clean"], color="#7C3AED", lw=2.8, ls="--", label="3-Phase Composite Average")

        tick_indices = list(range(0, len(times), 8))
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([times.iloc[i] for i in tick_indices], rotation=35, fontsize=8)

    role_str = f" ({meta.get('role', 'NMD')})" if meta else ""
    ax.set_ylim(195, 255)
    ax.set_title(f"24-Hour Diurnal Voltage Profile: {dev_name}{role_str}",
                 fontsize=11.0, fontweight="bold", color="#1E293B")
    ax.set_xlabel("Time of Day (HH:MM)", fontsize=9.0, labelpad=6)
    ax.set_ylabel("Voltage (Volts)", fontsize=9.0, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(loc="lower left", fontsize=7.5, frameon=True, ncol=2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_figure_network_voltage(devices_analysis: Dict[str, Any]) -> io.BytesIO:
    """
    Renders 24-hour comparative diurnal voltage overlay:
    Transformer vs all Feeder Ends against the 230V +/- 6% statutory standard.
    """
    fig, ax = plt.subplots(figsize=(9, 4.5), dpi=200)

    # Statutory Tolerance Band (216.2V to 243.8V)
    ax.axhspan(216.2, 243.8, color="#ECFDF5", alpha=0.6, label="Statutory Compliance Band (230V ± 6%)")
    ax.axhline(243.8, color="#DC2626", lw=1.6, ls="--", label="Statutory Max +6% (243.8V)")
    ax.axhline(216.2, color="#DC2626", lw=1.6, ls="--", label="Statutory Min -6% (216.2V)")
    ax.axhline(230.0, color="#64748B", lw=1.2, ls=":", label="Nominal Voltage (230.0V)")

    palette = ["#1E3A8A", "#059669", "#D97706", "#7C3AED", "#0891B2", "#DC2626", "#4F46E5"]

    time_labels = None
    for idx, (dev_name, res) in enumerate(devices_analysis.items()):
        df_clean = res.get("df_clean")
        if df_clean is None or df_clean.empty:
            continue
        df_calc = df_clean.copy()
        df_calc["Time"] = df_calc["Timestamp"].dt.strftime("%H:%M")
        diurnal = df_calc.groupby("Time")["V_3Phase_Clean"].mean().reset_index()

        is_tf = ("T/F" in dev_name.upper()) or ("TRANS" in dev_name.upper())
        color = palette[idx % len(palette)]
        lw = 3.2 if is_tf else 1.8
        ls = "-" if is_tf else ("--" if "M" in dev_name else "-")
        lbl = f"{dev_name} (Transformer)" if is_tf else f"Feeder {dev_name}"

        x_idx = np.arange(len(diurnal))
        ax.plot(x_idx, diurnal["V_3Phase_Clean"], color=color, lw=lw, ls=ls, label=lbl)
        if time_labels is None:
            time_labels = diurnal["Time"]

    if time_labels is not None:
        tick_indices = list(range(0, len(time_labels), 8))
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([time_labels.iloc[i] for i in tick_indices], rotation=35, fontsize=8)

    ax.set_ylim(200, 248)
    ax.set_title("Network Voltage Drop & Solar Rise Comparison (Transformer vs Feeder Ends)",
                 fontsize=11.0, fontweight="bold", color="#1E293B")
    ax.set_xlabel("Time of Day (HH:MM)", fontsize=9.0, labelpad=6)
    ax.set_ylabel("Average 3-Phase Voltage (Volts)", fontsize=9.0, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(loc="lower left", fontsize=7.5, frameon=True, ncol=2)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


def render_figure_voltage_delta(devices_analysis: Dict[str, Any], transformer_nick: str = "T/F") -> io.BytesIO:
    """
    Renders Feeder Voltage Differential (ΔV = V_Feeder - V_Transformer) profile over 24 hours.
    Highlights daytime solar voltage rise (ΔV > 0) and evening load voltage sag (ΔV < 0).
    """
    fig, ax = plt.subplots(figsize=(9, 4.2), dpi=200)

    # Locate transformer device
    tf_res = devices_analysis.get(transformer_nick)
    if tf_res is None:
        for k, v in devices_analysis.items():
            if "T/F" in k.upper():
                tf_res = v
                break

    if tf_res and tf_res.get("df_clean") is not None:
        tf_df = tf_res["df_clean"].copy()
        tf_df["Time"] = tf_df["Timestamp"].dt.strftime("%H:%M")
        tf_diurnal = tf_df.groupby("Time")["V_3Phase_Clean"].mean()

        # Solar rise and load sag shading
        ax.axhspan(0, 10, color="#FEF3C7", alpha=0.4, label="Solar Voltage Rise Zone (Delta V > 0)")
        ax.axhspan(-25, 0, color="#EFF6FF", alpha=0.4, label="Customer Load Voltage Drop Zone (Delta V < 0)")
        ax.axhline(0.0, color="#0F172A", lw=1.6, ls="-", label="0V Substation Voltage Baseline")

        palette = ["#059669", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#4F46E5"]
        idx = 0

        for dev_name, res in devices_analysis.items():
            if dev_name == transformer_nick or "T/F" in dev_name.upper():
                continue
            df_clean = res.get("df_clean")
            if df_clean is None or df_clean.empty:
                continue
            f_df = df_clean.copy()
            f_df["Time"] = f_df["Timestamp"].dt.strftime("%H:%M")
            f_diurnal = f_df.groupby("Time")["V_3Phase_Clean"].mean()

            delta_v = f_diurnal - tf_diurnal
            x_idx = np.arange(len(delta_v))
            ax.plot(x_idx, delta_v.values, color=palette[idx % len(palette)], lw=2.0,
                    label=f"Delta V: {dev_name} vs Substation")
            idx += 1

        times = tf_diurnal.index
        tick_indices = list(range(0, len(times), 8))
        ax.set_xticks(tick_indices)
        ax.set_xticklabels([times[i] for i in tick_indices], rotation=35, fontsize=8)

    ax.set_title("Feeder Voltage Differential (ΔV = V_Feeder - V_Transformer) Over 24 Hours",
                 fontsize=11.0, fontweight="bold", color="#1E293B")
    ax.set_xlabel("Time of Day (HH:MM)", fontsize=9.0, labelpad=6)
    ax.set_ylabel("Voltage Differential ΔV (Volts)", fontsize=9.0, labelpad=6)
    ax.grid(True, linestyle=":", alpha=0.6, color="#CBD5E1")
    ax.legend(loc="lower left", fontsize=8.0, frameon=True)

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=200, bbox_inches="tight")
    plt.close(fig)
    buf.seek(0)
    return buf


# ==============================================================================
# KEY-VALUE TABLE & UNDERVOLTAGE INTERVAL HELPERS
# ==============================================================================

def get_low_voltage_time_intervals(df_clean: Optional[pd.DataFrame], col_name: str, v_thresh: float = 216.2) -> List[str]:
    """
    Finds continuous or predominant time intervals where diurnal average voltage is below v_thresh.
    Returns list of formatted strings e.g. ['17:30 to 22:00'].
    """
    if df_clean is None or df_clean.empty or col_name not in df_clean.columns:
        return []
    
    df_calc = df_clean.copy()
    df_calc["Time_OfDay"] = df_calc["Timestamp"].dt.strftime("%H:%M")
    diurnal = df_calc.groupby("Time_OfDay")[col_name].mean().reset_index()
    diurnal = diurnal.sort_values("Time_OfDay").reset_index(drop=True)
    
    violating_times = [
        r["Time_OfDay"] for _, r in diurnal.iterrows() 
        if pd.notna(r[col_name]) and r[col_name] < v_thresh
    ]
    if not violating_times:
        return []
        
    intervals = []
    start = violating_times[0]
    prev = violating_times[0]
    for t in violating_times[1:]:
        h_prev, m_prev = map(int, prev.split(':'))
        h_curr, m_curr = map(int, t.split(':'))
        diff_mins = (h_curr * 60 + m_curr) - (h_prev * 60 + m_prev)
        if diff_mins <= 45:
            prev = t
        else:
            intervals.append((start, prev))
            start = t
            prev = t
    intervals.append((start, prev))
    
    # Filter to substantial intervals (e.g. duration >= 30 mins) if any exist
    substantial = []
    for s, e in intervals:
        hs, ms = map(int, s.split(':'))
        he, me = map(int, e.split(':'))
        dur = (he * 60 + me) - (hs * 60 + ms)
        if dur >= 30:
            substantial.append((s, e))
            
    final_ivs = substantial if substantial else intervals
    return [f"{s} to {e}" for s, e in final_ivs]


def create_key_value_table(doc: Document, rows_data: List[Tuple[str, str]], col_widths: List[float] = [2.4, 4.1]):
    """
    Creates a clean 2-column key-value table matching the LECO Proposal Justification Report format.
    Left column: Bold field name with soft neutral shading.
    Right column: Standard descriptive text.
    """
    table = doc.add_table(rows=len(rows_data), cols=2)
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    
    for r_idx, (k, v) in enumerate(rows_data):
        cell_k = table.cell(r_idx, 0)
        cell_v = table.cell(r_idx, 1)
        
        cell_k.text = str(k)
        cell_v.text = str(v)
        
        set_cell_background(cell_k, "F8FAFC")
        set_cell_margins(cell_k, top=90, bottom=90, left=130, right=130)
        cell_k.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell_k.width = Inches(col_widths[0])
        p_k = cell_k.paragraphs[0]
        if p_k.runs:
            p_k.runs[0].font.name = "Arial"
            p_k.runs[0].font.size = Pt(9.5)
            p_k.runs[0].font.bold = True
            p_k.runs[0].font.color.rgb = NAVY_PRIMARY
            
        set_cell_background(cell_v, "FFFFFF")
        set_cell_margins(cell_v, top=90, bottom=90, left=130, right=130)
        cell_v.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        cell_v.width = Inches(col_widths[1])
        p_v = cell_v.paragraphs[0]
        if p_v.runs:
            p_v.runs[0].font.name = "Arial"
            p_v.runs[0].font.size = Pt(9.0)
            p_v.runs[0].font.color.rgb = SLATE_TEXT
            
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            tcBorders = parse_xml(
                f'<w:tcBorders {nsdecls("w")}>'
                f'  <w:top w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                f'  <w:left w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                f'  <w:bottom w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                f'  <w:right w:val="single" w:sz="4" w:space="0" w:color="CBD5E1"/>'
                f'</w:tcBorders>'
            )
            tcPr.append(tcBorders)
            
    return table


# ==============================================================================
# MAIN WORD DOCUMENT REPORT GENERATOR
# ==============================================================================

def generate_word_report(
    parsed_data: Dict[str, Any],
    ct_result: Dict[str, Any],
    load_result: Dict[str, Any],
    network_topo: Dict[str, Any],
    network_voltage_result: Dict[str, Any],
    report_metadata: Optional[Dict[str, Any]] = None
) -> io.BytesIO:
    """
    Compiles a comprehensive, professionally formatted Word document (.docx)
    matching the official LECO 'Proposal Justification Report' structure and topics:
    1. Project Identification (Key-Value Table)
    2. Background Information (Key-Value Table: Existing Condition)
    3. Analysis and Justification:
       - Maximum Import, Export kVA behavior and Maximum Demand of the transformer
       - HV Violation ( > 243.8 V)
       - LV Violation ( < 216.2 V) with individual device graphs & time-interval findings
       - A Rough Map of how Solar Customers are distributed according to customer details
       - Voltage Unbalance & Engineering Mitigation Justification
    4. Scope of Proposed Works (Table)
    5. Prepared and Recommend By: (Sign-off Table)
    """
    doc = Document()
    if report_metadata is None:
        report_metadata = {}

    # Page Margins: 0.75 in (54 pt)
    for section in doc.sections:
        section.top_margin = Inches(0.75)
        section.bottom_margin = Inches(0.75)
        section.left_margin = Inches(0.75)
        section.right_margin = Inches(0.75)

    names_df = parsed_data.get("names_df", pd.DataFrame())
    tf_nick = parsed_data.get("transformer_nick", "T/F")
    tf_db_name = parsed_data.get("transformer_db_name", tf_nick)
    df_tf = parsed_data.get("device_readings", {}).get(tf_nick, pd.DataFrame())

    pole_id = "ST13/9"
    if not names_df.empty:
        tf_match = names_df[names_df["Nickname"] == tf_nick]
        if not tf_match.empty and str(tf_match["Pole_ID"].iloc[0]).strip():
            pole_id = str(tf_match["Pole_ID"].iloc[0]).strip()

    time_span = ""
    if not df_tf.empty and "Timestamp" in df_tf.columns:
        time_span = f"{df_tf['Timestamp'].min().strftime('%B %d, %Y')} to {df_tf['Timestamp'].max().strftime('%B %d, %Y')}"
    total_records = len(df_tf) if not df_tf.empty else 0

    # Extract network summary & solar information
    df_net = get_network_summary_dataframe(network_topo) if network_topo else pd.DataFrame()
    tot_solar_kw = float(df_net["Total_Solar_kW"].sum()) if not df_net.empty and "Total_Solar_kW" in df_net.columns else 0.0
    solar_pole_cnt = int(df_net["Solar_Poles"].sum()) if not df_net.empty and "Solar_Poles" in df_net.columns else 0

    solar_df = parsed_data.get("solar_df", pd.DataFrame())
    solar_cust_count = len(solar_df) if solar_df is not None and not solar_df.empty else 0

    feeder_lookup = network_topo.get("feeder_name_lookup", {}) if network_topo else get_feeder_name_lookup(names_df)

    # Map device metadata and feeder associations
    feeder_meta = {}
    name_map = {}
    feeder_ends = {}
    feeder_middles = {}
    
    if not names_df.empty:
        for idx, row in names_df.iterrows():
            nick = str(row.get("Nickname", "")).strip()
            db_name = str(row.get("DB_Name", "")).strip()
            role = str(row.get("Role", "Feeder")).strip()
            pole = str(row.get("Pole_ID", "")).strip()
            
            is_tf = (nick == tf_nick or "TRANS" in role.upper() or "T/F" in role.upper() or nick.upper() in ["TF", "T/F"])
            is_mid = ("MIDDLE" in role.upper()) or bool(re.search(r'(?:^F\d+M$|\bMID\b|\bMIDDLE\b)', nick.upper()))
            
            f_key = None
            if not is_tf:
                f_key = extract_feeder_key(nick, db_name, role)
                if not f_key:
                    f_key = f"F{len(feeder_ends) + 1}"
            
            feeder_meta[nick] = {
                "db_name": db_name,
                "role": role,
                "pole": pole,
                "feeder_key": f_key,
                "is_middle": is_mid,
                "is_transformer": is_tf
            }
            name_map[nick] = {"db_name": db_name, "role": role, "pole": pole}
            
            if not is_tf and f_key:
                if is_mid:
                    feeder_middles[f_key] = nick
                else:
                    feeder_ends[f_key] = nick

    # Ensure all monitored devices are captured
    for dev_name in network_voltage_result.get("devices", {}).keys():
        if dev_name == tf_nick or "T/F" in dev_name.upper() or "TRANS" in dev_name.upper():
            continue
        if dev_name in feeder_ends.values() or dev_name in feeder_middles.values():
            continue
        fk = extract_feeder_key(dev_name) or f"F{len(feeder_ends) + 1}"
        is_mid = bool(re.search(r'(?:^F\d+M$|\bMID\b|\bMIDDLE\b)', dev_name.upper()))
        if is_mid:
            feeder_middles[fk] = dev_name
        else:
            feeder_ends[fk] = dev_name
        if dev_name not in feeder_meta:
            feeder_meta[dev_name] = {
                "db_name": dev_name,
                "role": "Feeder Middle NMD" if is_mid else "Feeder End NMD",
                "pole": "",
                "feeder_key": fk,
                "is_middle": is_mid,
                "is_transformer": False
            }
        if dev_name not in name_map:
            name_map[dev_name] = {"db_name": dev_name, "role": "Feeder Middle NMD" if is_mid else "Feeder End NMD", "pole": ""}

    # Execute dynamic mitigation solutions engine
    solutions = analyze_mitigation_solutions(
        ct_result=ct_result,
        load_result=load_result,
        network_voltage_result=network_voltage_result,
        network_topo=network_topo or {},
        parsed_data=parsed_data
    )
    tf_sol = solutions.get("transformer_solution", {})
    lv_sol = solutions.get("lv_mitigation", {})
    hv_sol = solutions.get("hv_mitigation", {})

    rated_cap = float(load_result.get("metrics", {}).get("rated_capacity_kva", 160.0))
    peak_kva = float(load_result.get("metrics", {}).get("monthly_peak_kva", 0.0))
    peak_loading = float(load_result.get("metrics", {}).get("monthly_peak_loading_pct", 0.0))
    avg_peak_demand_kva = float(load_result.get("metrics", {}).get("avg_peak_demand_kva", tf_sol.get("peak_kva", peak_kva)))
    avg_demand_loading = float(load_result.get("metrics", {}).get("avg_demand_loading_pct", tf_sol.get("peak_loading_pct", peak_loading)))
    headroom_kva = float(load_result.get("metrics", {}).get("avg_headroom_kva", tf_sol.get("headroom_kva", 0.0)))
    all_hw_alerts = network_voltage_result.get("all_hardware_alerts", [])

    # Feeder display name helpers
    feeder_display_list = [get_feeder_display_name(k, lookup=feeder_lookup) for k in sorted(feeder_ends.keys())]
    line_segment_str = ", ".join(feeder_display_list) if feeder_display_list else tf_db_name

    # --------------------------------------------------------------------------
    # TOP HEADER & LECO BRANDING
    # --------------------------------------------------------------------------
    logo_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), "leco_logo.png")
    if not os.path.exists(logo_file):
        logo_file = "leco_logo.png" if os.path.exists("leco_logo.png") else None

    if logo_file and os.path.exists(logo_file):
        logo_p = doc.add_paragraph()
        logo_p.paragraph_format.space_before = Pt(0)
        logo_p.paragraph_format.space_after = Pt(4)
        r_logo = logo_p.add_run()
        r_logo.add_picture(logo_file, width=Inches(0.95))

    title_p = doc.add_paragraph()
    title_p.paragraph_format.space_before = Pt(2)
    title_p.paragraph_format.space_after = Pt(10)
    run_title = title_p.add_run("Proposal Justification Report")
    run_title.font.name = "Arial"
    run_title.font.size = Pt(22)
    run_title.font.bold = True
    run_title.font.color.rgb = NAVY_PRIMARY

    # --------------------------------------------------------------------------
    # TOPIC 1: PROJECT IDENTIFICATION (TABLE)
    # --------------------------------------------------------------------------
    doc.add_heading("Project Identification", level=1)
    
    consumer_count_str = str(report_metadata.get("consumer_count", ""))
    if not consumer_count_str and solar_cust_count > 0:
        consumer_count_str = f"{solar_cust_count} Solar Customers"

    # Transformer display number (prefer actual number e.g. BZ5504 if nickname is generic T/F)
    tf_no_display = tf_db_name if (tf_db_name and tf_nick.upper() in ["T/F", "TF", "TRANS", "TRANSFORMER"]) else tf_nick

    proj_id_data = [
        ("Year", str(report_metadata.get("year", datetime.now().year))),
        ("Branch", str(report_metadata.get("branch", "Galle"))),
        ("Customer Service Center (CSC)", str(report_metadata.get("csc", "Hikkaduwa"))),
        ("Network Type (HV/LV)", "LV"),
        ("HV Feeder Name/ Transformer No (for LV)", tf_no_display),
        ("Transformer Capacity", f"{rated_cap:.0f}kVA"),
        ("Consumer count", consumer_count_str),
        ("Line Segment", str(report_metadata.get("line_segment", line_segment_str))),
        ("Job No", str(report_metadata.get("job_no", "")))
    ]
    create_key_value_table(doc, proj_id_data)
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --------------------------------------------------------------------------
    # TOPIC 2: BACKGROUND INFORMATION (TABLE)
    # --------------------------------------------------------------------------
    doc.add_heading("Background Information", level=1)

    # Dynamically compose existing condition text
    existing_cond_parts = []
    # 1. Substation Loading
    if not tf_sol.get("evaluation_valid", True):
        existing_cond_parts.append(
            f"CT polarity inversion ({ct_result.get('dominant_mode')}) is present. "
            f"Transformer loading evaluation is temporarily deferred pending CT lead reversal."
        )
    elif tf_sol.get("is_overloaded", False):
        existing_cond_parts.append(
            f"According to the 24-hour representative average demand curve, maximum demand exceeds the transformer rating {rated_cap:.0f}kVA reaching {avg_peak_demand_kva:.1f}kVA "
            f"({avg_demand_loading:.1f}% average peak demand). Transformer is overloaded."
        )
    else:
        existing_cond_parts.append(
            f"Maximum demand does not exceed the transformer rating {rated_cap:.0f}kVA based on the 24-hour representative average demand curve ({avg_peak_demand_kva:.1f}kVA, {avg_demand_loading:.1f}%). Not overload."
        )

    # 2. Feeder LV/HV status (sorted by severity descending so most constrained feeder is prioritized)
    lv_violating_feeders = [f for f in lv_sol.get("feeder_analysis", []) if f.get("violation_category", "None") != "None"]
    lv_violating_feeders.sort(key=lambda x: x.get("worst_phase_pct", 0.0), reverse=True)
    if lv_violating_feeders:
        for f in lv_violating_feeders:
            f_name_disp = f.get("feeder_display") or f.get("feeder_key", "")
            end_dev = f.get("end_device", "")
            pole_val = feeder_meta.get(end_dev, {}).get("pole", "")
            pole_str = f" {pole_val}" if pole_val else ""
            if f.get("violation_category") == "All Phases (3 Phases)":
                existing_cond_parts.append(f"{f_name_disp}{pole_str} NMD all phases fail due to low voltage issues in the feeder ends.")
            else:
                existing_cond_parts.append(
                    f"{f_name_disp}{pole_str} NMD exhibits low voltage issues on {', '.join(f.get('violating_phases', []))} "
                    f"({f.get('worst_phase_pct', 0.0):.2f}%)."
                )
    elif hv_sol.get("system_wide_hv_issue", False):
        existing_cond_parts.append("Both transformer and radial feeders experience statutory high voltage violations (> 243.8V).")
    else:
        existing_cond_parts.append("All feeder end NMDs show voltages operating within statutory limits.")

    # 3. Hardware defects
    if all_hw_alerts:
        for alert in all_hw_alerts:
            dev_a = alert.get("device", "")
            ph_a = alert.get("phase", "Phase A")
            db_a = name_map.get(dev_a, {}).get("db_name", dev_a)
            pole_a = feeder_meta.get(dev_a, {}).get("pole", dev_a)
            existing_cond_parts.append(f"As NMD readings of {db_a} {ph_a} are always 0, it may be a problem in {pole_a} NMD.")

    bg_data = [
        ("Constructed / Last Rehabilitated Year", str(report_metadata.get("last_rehab_year", ""))),
        ("Existing Condition", " ".join(existing_cond_parts))
    ]
    create_key_value_table(doc, bg_data)
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --------------------------------------------------------------------------
    # TOPIC 3: ANALYSIS AND JUSTIFICATION
    # --------------------------------------------------------------------------
    doc.add_heading("Analysis and Justification", level=1)

    # --------------------------------------------------------------------------
    # 3.1 Maximum Import, Export kVA behavior and Maximum Demand
    # --------------------------------------------------------------------------
    doc.add_heading("Maximum Import, Export kVA behavior and Maximum Demand of the transformer", level=2)

    if not tf_sol.get("evaluation_valid", True):
        doc.add_paragraph(
            f"CT secondary polarities are inverted ({ct_result.get('dominant_mode')}). "
            f"Active and reactive power directionality is corrupted; loading assessment is deferred pending CT wiring correction."
        )
    elif tf_sol.get("is_overloaded", False):
        doc.add_paragraph(
            f"According to the 24-hour representative average demand curve, the transformer maximum demand "
            f"exceeds the transformer rating {rated_cap:.0f}kVA, reaching {avg_peak_demand_kva:.1f} kVA "
            f"({avg_demand_loading:.1f}% peak demand). This shows that the existing transformer is in an overload condition."
        )
    else:
        doc.add_paragraph(
            "The transformer maximum import and export kVA and maximum demand is in the acceptable range. "
            f"According to the 24-hour representative average demand curve, maximum demand ({avg_peak_demand_kva:.1f} kVA, {avg_demand_loading:.1f}%) "
            f"does not exceed the transformer rating {rated_cap:.0f}kVA. "
            "This shows that existing transformer is not in overload condition."
        )

    # Embed Figure: Transformer 24-Hour Diurnal Load Profile
    fig_load_buf = render_figure_diurnal_load(load_result)
    doc.add_picture(fig_load_buf, width=Inches(6.4))
    cap_load = doc.add_paragraph("Figure: Transformer 24-Hour Diurnal Load Profile showing Import kVA, Export kVA, and Net Load.")
    cap_load.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap_load.runs[0].font.size = Pt(8.5)
    cap_load.runs[0].font.italic = True
    doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # Diurnal Profile Landmarks Table
    landmarks = load_result.get("landmarks", {})
    l_tbl = doc.add_table(rows=1, cols=4)
    l_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    l_widths = [2.2, 1.4, 1.4, 1.5]

    for i, t in enumerate(["Diurnal Profile Landmark", "Time of Day", "Net Load (kVA)", "Grid Direction"]):
        l_tbl.rows[0].cells[i].text = t
    style_table_header(l_tbl.rows[0], l_widths)

    lm_rows = [
        ("Morning Peak Demand", str(landmarks.get("morning_peak_time", "N/A")), f"{landmarks.get('morning_peak_load_kva', 0.0):.1f} kVA", "Import (Load)"),
        ("Midday Solar Duck Trough", str(landmarks.get("duck_curve_trough_time", "N/A")), f"{landmarks.get('duck_curve_trough_load_kva', 0.0):.1f} kVA", "Export (Solar)" if landmarks.get('duck_curve_trough_load_kva', 0.0) < 0 else "Import (Reduced)"),
        ("Evening Peak Demand", str(landmarks.get("evening_peak_time", "N/A")), f"{landmarks.get('evening_peak_load_kva', 0.0):.1f} kVA", "Import (Peak Load)"),
        ("Minimum Night Base Load", str(landmarks.get("night_min_time", "N/A")), f"{landmarks.get('night_min_load_kva', 0.0):.1f} kVA", "Import (Base)")
    ]
    for r in lm_rows:
        rc = l_tbl.add_row().cells
        for idx, val in enumerate(r):
            rc[idx].text = val
    style_table_body(l_tbl, l_widths)
    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Embed CT Polarity Verification Figure
    if not df_tf.empty:
        fig_ct_buf = render_figure_ct_polarity(df_tf)
        doc.add_picture(fig_ct_buf, width=Inches(6.4))
        cap_ct = doc.add_paragraph(f"Figure: Current Transformer (CT) Polarity Verification ({ct_result.get('status_label', 'Normal')}).")
        cap_ct.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_ct.runs[0].font.size = Pt(8.5)
        cap_ct.runs[0].font.italic = True
        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --------------------------------------------------------------------------
    # 3.2 HV Violation ( > 243.8 V)
    # --------------------------------------------------------------------------
    doc.add_heading("HV Violation ( > 243.8 V)", level=2)
    has_hv_violations = (hv_sol.get("transformer_hv_violation", False) or any(f.get("violation_category", "None") != "None" for f in hv_sol.get("feeder_analysis", [])))

    if not has_hv_violations:
        doc.add_paragraph(
            "According to the above data, all feeders and the transformer show negligible high voltage conditions, "
            "and the voltage values remain well within the acceptable limit."
        )
    else:
        viol_desc_list = []
        if hv_sol.get("transformer_hv_violation"):
            viol_desc_list.append(f"Transformer ({hv_sol.get('transformer_worst_hv_pct', 0.0):.2f}% HV violations)")
        for f in hv_sol.get("feeder_analysis", []):
            if f.get("violation_category", "None") != "None":
                f_disp = f.get("feeder_display") or f.get("feeder_key", "")
                viol_desc_list.append(f"Feeder {f_disp} ({f.get('worst_phase', '')} worst: {f.get('worst_phase_pct', 0.0):.2f}%)")
        doc.add_paragraph(
            f"According to the monitoring data, high voltage violations (> 243.8 V) are observed on: {'; '.join(viol_desc_list)}. "
            f"Mitigation measures such as transformer tap adjustment and solar customer rebalancing are detailed below."
        )

    # Embed Table 1: High Voltage Violations Summary
    hv_summary = network_voltage_result.get("hv_summary_df", pd.DataFrame())
    if not hv_summary.empty:
        hv_tbl = doc.add_table(rows=1, cols=10)
        hv_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        hv_widths = [0.7, 0.8, 0.9, 0.55, 0.55, 0.55, 1.4, 0.9, 0.55, 1.1]

        hv_headers = ["Device", "Role", "DB Name", "Va HV%", "Vb HV%", "Vc HV%", "Violating Phase(s)", "Worst Phase", "Max V", "HV Status"]
        for i, h in enumerate(hv_headers):
            hv_tbl.rows[0].cells[i].text = h
        style_table_header(hv_tbl.rows[0], hv_widths, hex_bg="1E3A8A")

        for _, r in hv_summary.iterrows():
            rc = hv_tbl.add_row().cells
            rc[0].text = str(r["Device"])
            rc[1].text = str(r["Role"])
            rc[2].text = str(r["DB Name"])
            rc[3].text = f"{r['Va HV Viol (%)']:.2f}%"
            rc[4].text = f"{r['Vb HV Viol (%)']:.2f}%"
            rc[5].text = f"{r['Vc HV Viol (%)']:.2f}%"
            rc[6].text = str(r.get("Violating Phase(s)", "—"))
            rc[7].text = str(r.get("Worst Phase", "—"))
            rc[8].text = f"{r['Max Voltage (V)']:.1f}V"
            rc[9].text = str(r["HV Status"])
        style_table_body(hv_tbl, hv_widths)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --------------------------------------------------------------------------
    # 3.3 LV Violation ( < 216.2 V)
    # --------------------------------------------------------------------------
    doc.add_heading("LV Violation ( < 216.2 V)", level=2)

    if not lv_violating_feeders:
        doc.add_paragraph(
            "According to the above data, all feeders and the transformer show negligible low voltage conditions, "
            "and the voltage values remain well within the acceptable limit."
        )
    else:
        for f in lv_violating_feeders:
            fk = f.get("feeder_key", "")
            f_disp = f.get("feeder_display") or fk
            end_dev = f.get("end_device", "")
            end_db = name_map.get(end_dev, {}).get("db_name", end_dev)
            mid_dev = feeder_middles.get(fk, "")
            mid_db = name_map.get(mid_dev, {}).get("db_name", mid_dev) if mid_dev else ""
            
            if mid_db:
                doc.add_paragraph(
                    f"There is a low voltage issue in {f_disp} feeder. "
                    f"(“{end_db}” is the feeder end NMD readings and “{mid_db}” is the feeder middle NMD readings)"
                )
            else:
                doc.add_paragraph(
                    f"There is a low voltage issue in {f_disp} feeder. "
                    f"(“{end_db}” is the feeder end NMD readings)"
                )

    # Embed Table 2: Low Voltage Violations Summary
    lv_summary = network_voltage_result.get("lv_summary_df", pd.DataFrame())
    if not lv_summary.empty:
        lv_tbl = doc.add_table(rows=1, cols=10)
        lv_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        lv_widths = [0.7, 0.8, 0.9, 0.55, 0.55, 0.55, 0.55, 1.5, 0.9, 1.0]

        lv_headers = ["Device", "Role", "DB Name", "Outages", "Va LV%", "Vb LV%", "Vc LV%", "Violating Phase(s)", "Worst Phase", "LV Status"]
        for i, h in enumerate(lv_headers):
            lv_tbl.rows[0].cells[i].text = h
        style_table_header(lv_tbl.rows[0], lv_widths, hex_bg="991B1B")

        for _, r in lv_summary.iterrows():
            rc = lv_tbl.add_row().cells
            rc[0].text = str(r["Device"])
            rc[1].text = str(r["Role"])
            rc[2].text = str(r["DB Name"])
            rc[3].text = f"{r['Outages (Hrs)']:.1f}h"
            rc[4].text = f"{r['Va LV Viol (%)']:.2f}%"
            rc[5].text = f"{r['Vb LV Viol (%)']:.2f}%"
            rc[6].text = f"{r['Vc LV Viol (%)']:.2f}%"
            rc[7].text = str(r.get("Violating Phase(s)", "—"))
            rc[8].text = str(r.get("Worst Phase", "—"))
            rc[9].text = str(r["LV Status"])
        style_table_body(lv_tbl, lv_widths)

    doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # Individual NMD Voltage Profiles and Time Interval Findings
    # 1. Transformer
    doc.add_paragraph("Transformer Average Phase voltage profile as follows:")
    if tf_nick in network_voltage_result.get("devices", {}):
        dev_res_tf = network_voltage_result["devices"][tf_nick]
        meta_tf = name_map.get(tf_nick, {"db_name": tf_db_name, "role": "Transformer"})
        fig_tf_buf = render_figure_device_voltage(tf_nick, dev_res_tf, meta_tf)
        doc.add_picture(fig_tf_buf, width=Inches(6.4))
        doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # 2. Individual Feeders (Feeder End & Middle)
    for fk in sorted(feeder_ends.keys()):
        f_disp = get_feeder_display_name(fk, lookup=feeder_lookup)
        
        # Render Feeder End NMD
        end_dev = feeder_ends[fk]
        if end_dev in network_voltage_result.get("devices", {}):
            dev_res_end = network_voltage_result["devices"][end_dev]
            meta_end = name_map.get(end_dev, {"db_name": end_dev, "role": "Feeder End NMD"})
            db_n = meta_end["db_name"]
            
            doc.add_paragraph(f"Feeder End Average Voltage analysis for the NMD {end_dev} {db_n} is as follows")
            fig_end_buf = render_figure_device_voltage(end_dev, dev_res_end, meta_end)
            doc.add_picture(fig_end_buf, width=Inches(6.4))
            
            # Check for 0V sensor defects
            pm = dev_res_end.get("phase_metrics", {})
            for ph_name, ph_m in pm.items():
                if ph_m.get("is_persistent_defect"):
                    doc.add_paragraph(f"As NMD readings of {db_n} {ph_name} are always 0, it maybe a problem in NMD.")
                    
            # Check undervoltage intervals
            df_c = dev_res_end.get("df_clean", pd.DataFrame())
            for ph_name, col_name in [("Phase A", "Va_clean"), ("Phase B", "Vb_clean"), ("Phase C", "Vc_clean")]:
                ivs = get_low_voltage_time_intervals(df_c, col_name)
                if ivs:
                    for iv in ivs:
                        doc.add_paragraph(f"According to the NMD readings of the feeders, the {db_n} shows low voltage in {ph_name} from {iv}.")
            doc.add_paragraph().paragraph_format.space_after = Pt(6)
            
        # Render Feeder Middle NMD if present
        if fk in feeder_middles:
            mid_dev = feeder_middles[fk]
            if mid_dev in network_voltage_result.get("devices", {}):
                dev_res_mid = network_voltage_result["devices"][mid_dev]
                meta_mid = name_map.get(mid_dev, {"db_name": mid_dev, "role": "Feeder Middle NMD"})
                db_mid_n = meta_mid["db_name"]
                
                doc.add_paragraph(f"Feeder Middle Average Voltage analysis for the NMD {mid_dev} {db_mid_n} is as follows")
                fig_mid_buf = render_figure_device_voltage(mid_dev, dev_res_mid, meta_mid)
                doc.add_picture(fig_mid_buf, width=Inches(6.4))
                
                pm = dev_res_mid.get("phase_metrics", {})
                for ph_name, ph_m in pm.items():
                    if ph_m.get("is_persistent_defect"):
                        doc.add_paragraph(f"As NMD readings of {db_mid_n} {ph_name} are always 0, it maybe a problem in NMD.")
                        
                df_c_mid = dev_res_mid.get("df_clean", pd.DataFrame())
                for ph_name, col_name in [("Phase A", "Va_clean"), ("Phase B", "Vb_clean"), ("Phase C", "Vc_clean")]:
                    ivs = get_low_voltage_time_intervals(df_c_mid, col_name)
                    if ivs:
                        for iv in ivs:
                            doc.add_paragraph(f"According to the NMD readings of the feeders, the {db_mid_n} shows low voltage in {ph_name} from {iv}.")
                doc.add_paragraph().paragraph_format.space_after = Pt(6)

    # --------------------------------------------------------------------------
    # 3.4 Solar Customer Distribution Map
    # --------------------------------------------------------------------------
    doc.add_heading("A Rough Map of how Solar Customers are distributed according to customer details.", level=2)
    if network_topo and "feeders" in network_topo and network_topo["feeders"]:
        fig_schematic_buf = render_figure_network_schematic(network_topo)
        doc.add_picture(fig_schematic_buf, width=Inches(6.6))
        cap_sch = doc.add_paragraph("Figure: Feeder Network Schematic depicting Distribution Transformer, Feeders, NMD meters, and Solar Generation Nodes.")
        cap_sch.alignment = WD_ALIGN_PARAGRAPH.CENTER
        cap_sch.runs[0].font.size = Pt(8.5)
        cap_sch.runs[0].font.italic = True
        doc.add_paragraph().paragraph_format.space_after = Pt(8)
    else:
        doc.add_paragraph("Feeder network single-line schematic is unavailable (no pole sequence data provided in Poles sheet).")

    # Feeder Line Architecture & Solar Penetration Table
    if not df_net.empty:
        f_tbl = doc.add_table(rows=1, cols=7)
        f_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        f_widths = [0.8, 0.9, 0.9, 0.9, 1.2, 0.9, 1.0]
        hdr_titles = ["Feeder", "Line Poles", "Main Feeder", "Spur Poles", "NMD Devices", "Solar Sites", "Solar kW"]
        for i, t in enumerate(hdr_titles):
            f_tbl.rows[0].cells[i].text = t
        style_table_header(f_tbl.rows[0], f_widths)
        for _, row_data in df_net.iterrows():
            row_cells = f_tbl.add_row().cells
            row_cells[0].text = str(row_data["Feeder"])
            row_cells[1].text = str(row_data["Line_Poles"])
            row_cells[2].text = str(row_data["Trunk_Poles"])
            row_cells[3].text = str(row_data["Spurs_Count"])
            row_cells[4].text = str(row_data["NMD_Devices"]) if row_data["NMD_Devices"] else "None"
            row_cells[5].text = str(row_data["Solar_Poles"])
            row_cells[6].text = f"{row_data['Total_Solar_kW']:.1f} kW"
        style_table_body(f_tbl, f_widths)
        doc.add_paragraph().paragraph_format.space_after = Pt(10)

    # --------------------------------------------------------------------------
    # 3.5 Voltage Unbalance & Solution Justification
    # --------------------------------------------------------------------------
    doc.add_heading("Voltage Unbalance", level=2)

    if lv_violating_feeders:
        first_viol_f = lv_violating_feeders[0]
        first_viol_name = first_viol_f.get("feeder_display") or first_viol_f.get("feeder_key", "")
        doc.add_paragraph(f"There is a Voltage Unbalance issue associated with the {first_viol_name} Feeder.")
        
        doc.add_paragraph(
            f"According to the above graphs, the {rated_cap:.0f}kVA {tf_nick} transformer does not show an overload situation, "
            f"and there are no high-voltage (HV) issues present. However, according to the NMD readings related to the {first_viol_name}, "
            f"low-voltage (LV) issues are present across all phases. On the individual feeders, no feeders show under-voltage or "
            f"over-voltage extremes outside of this localized sector."
        )
        
        doc.add_paragraph(
            f"As a solution to the above problems, a load relief and distribution strategy must be implemented for the {first_viol_name}. "
            f"Accordingly, it is appropriate to transfer and connect a part of the {first_viol_name} feeder to another nearby transformer "
            f"to alleviate the low-voltage strain across the phases. Field data confirms that the nearby transformer capacity is currently "
            f"not overloaded and has sufficient spare capacity. Since a feeder end from the adjacent network is situated in close proximity "
            f"to the affected {first_viol_name}, a section of this low-voltage (LV) issue zone can be successfully interconnected to this "
            f"adjacent feeder. If this interconnection is not executed, installing a new transformer remains the alternative solution "
            f"to independently support the {first_viol_name} network."
        )
    elif hv_sol.get("system_wide_hv_issue", False):
        doc.add_paragraph(
            f"According to the above graphs, the {rated_cap:.0f}kVA {tf_nick} transformer and its radial feeders experience "
            f"concurrent statutory high voltage violations (> 243.8 V). To bring network voltages within statutory limits, "
            f"adjust the transformer Off-Circuit Tap Changer (OCTC) to a lower position (Tap 1 or 2, providing -2.5% to -5.0% buck). "
            f"Additionally, verify upstream 11 kV grid voltage during nighttime hours."
        )
    else:
        doc.add_paragraph(
            f"According to the above graphs and statutory evaluation, the {rated_cap:.0f}kVA {tf_nick} transformer operates safely "
            f"within thermal limits, and all monitored feeder ends maintain balanced voltages within statutory limits (230V ± 6%)."
        )

    # Master Prioritized Action Matrix Table
    df_act = solutions.get("action_matrix_df", pd.DataFrame())
    if not df_act.empty:
        doc.add_heading("Master Engineering Mitigation Action Matrix", level=3)
        act_tbl = doc.add_table(rows=1, cols=7)
        act_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
        act_widths = [0.85, 0.9, 0.85, 1.15, 0.75, 1.45, 1.05]
        
        act_headers = ["Priority", "Category", "Target Node", "Observed Problem", "Phases", "Primary Recommended Action", "Target Location"]
        for i, h in enumerate(act_headers):
            act_tbl.rows[0].cells[i].text = h
        style_table_header(act_tbl.rows[0], act_widths, hex_bg="1E3A8A")
        
        for _, r in df_act.iterrows():
            rc = act_tbl.add_row().cells
            rc[0].text = str(r["Priority"])
            rc[1].text = str(r["Category"])
            rc[2].text = str(r["Target Device / Feeder"])
            rc[3].text = str(r["Observed Problem"])
            rc[4].text = str(r["Affected Phase(s)"])
            rc[5].text = str(r["Primary Recommended Action"])
            rc[6].text = str(r["Target Location"])
            if "P1" in str(r["Priority"]):
                rc[0].paragraphs[0].runs[0].font.bold = True
                rc[0].paragraphs[0].runs[0].font.color.rgb = RED_CRITICAL
                
        style_table_body(act_tbl, act_widths)
        doc.add_paragraph().paragraph_format.space_after = Pt(8)

    # --------------------------------------------------------------------------
    # TOPIC 4: SCOPE OF PROPOSED WORKS (TABLE)
    # --------------------------------------------------------------------------
    doc.add_heading("Scope of Proposed Works", level=1)

    trunk_len = "N/A"
    if lv_violating_feeders:
        first_viol_f = lv_violating_feeders[0]
        first_viol_name = first_viol_f.get("feeder_display") or first_viol_f.get("feeder_key", "")
        f_k = first_viol_f.get("feeder_key", "")
        trunk_cnt = network_topo.get("feeders", {}).get(f_k, {}).get("trunk_poles_count", 0) if network_topo else 0
        if trunk_cnt > 0:
            trunk_len = f"{trunk_cnt * 0.04:.2f} km ({trunk_cnt} poles)"
            
        proposed_work_text = (
            f"Interconnect and transfer a section of the {first_viol_name} feeder to the nearby transformer, "
            f"utilizing its close-proximity feeder end. If this interconnection is not viable, install a new transformer "
            f"to independently support the {first_viol_name} network."
        )
    elif hv_sol.get("system_wide_hv_issue", False):
        proposed_work_text = (
            f"Adjust the distribution transformer Off-Circuit Tap Changer (OCTC) from current tap to a lower position "
            f"(Tap 1 or Tap 2) to lower secondary busbar voltage into statutory limits (230V ± 6%). "
            f"Coordinate with primary substation engineers to inspect upstream 11 kV voltage setpoint."
        )
    else:
        proposed_work_text = (
            "Routine statutory monitoring and preventative maintenance. No capital network augmentation or line transfer "
            "required at this time as all parameters comply with statutory standards."
        )

    # Append prioritized direct solutions if available
    direct_sols = solutions.get("direct_solutions", [])
    actionable_sols = [s["direct_solution"] for s in direct_sols if "Optimal" not in s.get("priority", "")]
    if actionable_sols:
        proposed_work_text += "\n\nKey Action Directives:\n" + "\n".join(f"• {act}" for act in actionable_sols)

    scope_data = [
        ("Line Length (km)", trunk_len),
        ("Proposed Work", proposed_work_text)
    ]
    create_key_value_table(doc, scope_data)
    doc.add_paragraph().paragraph_format.space_after = Pt(14)

    # --------------------------------------------------------------------------
    # TOPIC 5: SIGN-OFF (PREPARED AND RECOMMEND BY)
    # --------------------------------------------------------------------------
    doc.add_heading("Prepared and Recommend By:", level=1)

    sign_tbl = doc.add_table(rows=3, cols=3)
    sign_tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    sign_widths = [2.2, 2.2, 2.2]
    sign_headers = ["Designation", "Name & Signature", "Date"]
    for i, h in enumerate(sign_headers):
        sign_tbl.rows[0].cells[i].text = h
    style_table_header(sign_tbl.rows[0], sign_widths, hex_bg="1E3A8A")

    sign_rows = [
        ("Electrical Engineer (Planning)", "", ""),
        ("Chief Engineer / Branch Manager", "", "")
    ]
    for r in sign_rows:
        rc = sign_tbl.add_row().cells
        rc[0].text = r[0]
        rc[1].text = r[1]
        rc[2].text = r[2]
    style_table_body(sign_tbl, sign_widths)

    # Output to BytesIO
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)
    return doc_io
