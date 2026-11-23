"""
Distribution Transformer & Feeder Voltage Profile and Statutory Violation Analyzer.

Standards & Statutory Framework:
- Nominal Voltage: 230.0 V (Phase-to-Neutral, LV Distribution)
- Statutory Tolerance: +/- 6.0% (216.2 V to 243.8 V)
- Benchmark Limit Standards (EN 50160 & Utility Best Practice):
  * EN 50160: 95% of 10-min/15-min average RMS readings in a weekly window
    must remain within the statutory band (+/- 6% or +/- 10%).
    Permissible Violation Threshold: <= 5.0% maximum allowable violation rate.
  * Utility Best Practice / High Quality: <= 1.0% violation rate (Normal / Compliant).
  * Warning Zone: 1.0% to 5.0% violation rate (Actionable for planning / phase balancing).
  * Critical Non-Compliance: > 5.0% violation rate (Statutory breach; immediate intervention).

Data Processing & Outage Rules:
1. Single-Phase Zero Voltage (1 or 2 phases = 0 while another > 5V):
   - Classified as an NMD Sensor / Instrument PT Channel Defect or missing sample.
   - Neglected (set to NaN) for calculating the average phase voltage and 3-phase average,
     preventing artificial distortion of network voltage profiles.
   - If a phase is persistently 0V (>90% of entire dataset), flagged as a Critical
     NMD Hardware / Wiring Defect (disconnected alligator clip, blown fuse, faulty ADC).
2. All-Phase Zero Voltage (Va = 0 AND Vb = 0 AND Vc = 0):
   - Classified as a System Interruption / Power Outage.
   - Included in average voltage calculations as requested by the user, while tracking
     outage frequency and total duration in hours.
"""

from typing import Dict, Any, List, Optional
import re
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px

# Standard Constants
NOMINAL_VOLTAGE = 230.0
STATUTORY_TOLERANCE_PCT = 6.0
UPPER_LIMIT_V = NOMINAL_VOLTAGE * (1.0 + STATUTORY_TOLERANCE_PCT / 100.0)  # 243.8 V
LOWER_LIMIT_V = NOMINAL_VOLTAGE * (1.0 - STATUTORY_TOLERANCE_PCT / 100.0)  # 216.2 V
ZERO_VOLTAGE_THRESHOLD = 5.0  # Readings <= 5.0 V considered zero / de-energized

# Benchmark Limits for Voltage Violations
BENCHMARK_COMPLIANT_PCT = 1.0   # <= 1.0% is Green / High Quality
BENCHMARK_WARNING_PCT = 5.0     # 1.0% - 5.0% is Yellow / EN 50160 95% Limit
# > 5.0% is Red / Critical Statutory Non-Compliance


def analyze_device_voltage(
    df_dev: pd.DataFrame,
    device_name: str,
    nominal_v: float = NOMINAL_VOLTAGE,
    tolerance_pct: float = STATUTORY_TOLERANCE_PCT
) -> Dict[str, Any]:
    """
    Analyzes voltage readings for a single monitoring device (Transformer or Feeder NMD).
    Evaluates HV/LV violations, system interruptions, single-phase sensor defects, and diurnal curves.
    """
    total_records = len(df_dev)
    if total_records == 0:
        return {"error": f"No records available for device {device_name}"}

    v_upper = nominal_v * (1.0 + tolerance_pct / 100.0)
    v_lower = nominal_v * (1.0 - tolerance_pct / 100.0)

    # 1. Identify System Interruptions (All 3 phases simultaneously <= ZERO_VOLTAGE_THRESHOLD)
    all_zero_mask = (
        (df_dev["Va"] <= ZERO_VOLTAGE_THRESHOLD) &
        (df_dev["Vb"] <= ZERO_VOLTAGE_THRESHOLD) &
        (df_dev["Vc"] <= ZERO_VOLTAGE_THRESHOLD)
    )
    interruption_count = int(all_zero_mask.sum())
    interruption_hours = round(interruption_count * 15.0 / 60.0, 2)
    interruption_pct = round((interruption_count / total_records) * 100.0, 2)

    # Cleaned DataFrame for processing
    df_clean = df_dev.copy()
    
    phase_metrics = {}
    hardware_alerts = []

    for ph, col_name in [("Phase A", "Va"), ("Phase B", "Vb"), ("Phase C", "Vc")]:
        v_raw = df_dev[col_name]
        
        # Single-phase zero check: zero on this phase while NOT an all-phase interruption
        single_zero_mask = (v_raw <= ZERO_VOLTAGE_THRESHOLD) & ~all_zero_mask
        single_zero_count = int(single_zero_mask.sum())
        single_zero_pct = round((single_zero_count / total_records) * 100.0, 2)
        
        # Check if phase is persistently dead (e.g. >90% zeros)
        is_persistent_defect = (single_zero_count / total_records) > 0.90
        
        if is_persistent_defect:
            hardware_alerts.append({
                "device": device_name,
                "phase": ph,
                "zero_count": single_zero_count,
                "zero_pct": single_zero_pct,
                "message": (
                    f"⚠️ CRITICAL NMD SENSOR DEFECT: {device_name} {ph} voltage is continuously 0.0V "
                    f"({single_zero_count} of {total_records} intervals = {single_zero_pct}%)."
                )
            })

        # For average calculation: neglect single-phase zero readings (set to NaN)
        v_clean = v_raw.where(~single_zero_mask, np.nan)
        df_clean[f"{col_name}_clean"] = v_clean

        # Violations calculation
        hv_mask = v_raw > v_upper
        hv_count = int(hv_mask.sum())
        hv_pct = round((hv_count / total_records) * 100.0, 2)

        # LV violations: count all readings < v_lower (excluding single-phase sensor faults)
        # Note: All-phase interruptions (all 0V) are part of the total dataset
        lv_total_mask = v_raw < v_lower
        lv_total_count = int(lv_total_mask.sum())
        lv_total_pct = round((lv_total_count / total_records) * 100.0, 2)

        # Operational LV violations (excluding single-phase sensor defects)
        lv_clean_mask = lv_total_mask & ~single_zero_mask
        lv_clean_count = int(lv_clean_mask.sum())
        lv_clean_pct = round((lv_clean_count / total_records) * 100.0, 2)

        # Non-zero under-voltage (grid energized between 5V and 216.2V)
        lv_energized_mask = (v_raw < v_lower) & (v_raw > ZERO_VOLTAGE_THRESHOLD)
        lv_energized_count = int(lv_energized_mask.sum())
        lv_energized_pct = round((lv_energized_count / total_records) * 100.0, 2)

        # Maximum & Minimum Voltages (excluding sensor zeros)
        v_energized = v_raw[v_raw > ZERO_VOLTAGE_THRESHOLD]
        max_v = round(float(v_raw.max()), 1) if not v_raw.empty else 0.0
        min_energized_v = round(float(v_energized.min()), 1) if not v_energized.empty else 0.0
        mean_v = round(float(v_clean.mean()), 1) if not v_clean.isna().all() else np.nan

        # Statutory Compliance Status for this phase
        if is_persistent_defect:
            status = "⚠️ Sensor Defect"
            badge = "sensor_defect"
        elif hv_pct > BENCHMARK_WARNING_PCT or lv_clean_pct > BENCHMARK_WARNING_PCT:
            status = "🔴 Critical"
            badge = "critical"
        elif hv_pct > BENCHMARK_COMPLIANT_PCT or lv_clean_pct > BENCHMARK_COMPLIANT_PCT:
            status = "🟡 Warning"
            badge = "warning"
        else:
            status = "🟢 Optimal"
            badge = "optimal"

        phase_metrics[ph] = {
            "col": col_name,
            "mean_v": mean_v,
            "max_v": max_v,
            "min_energized_v": min_energized_v,
            "hv_count": hv_count,
            "hv_pct": hv_pct,
            "lv_total_count": lv_total_count,
            "lv_total_pct": lv_total_pct,
            "lv_clean_count": lv_clean_count,
            "lv_clean_pct": lv_clean_pct,
            "lv_energized_count": lv_energized_count,
            "lv_energized_pct": lv_energized_pct,
            "single_zero_count": single_zero_count,
            "single_zero_pct": single_zero_pct,
            "is_persistent_defect": is_persistent_defect,
            "status": status,
            "badge": badge
        }

    # Clean 3-Phase Average per timestamp (averaging available non-defective phases)
    df_clean["V_3Phase_Clean"] = df_clean[["Va_clean", "Vb_clean", "Vc_clean"]].mean(axis=1)

    # Identify Violating Phases & Worst Phase Metrics (Considerable threshold: > 1.0%)
    CONSIDERABLE_THRESHOLD_PCT = BENCHMARK_COMPLIANT_PCT  # 1.0%

    active_phases = [ph for ph, m in phase_metrics.items() if not m["is_persistent_defect"]]
    
    # 1. High Voltage Violations (> 243.8V)
    viol_hv_list = [
        (ph, phase_metrics[ph]["hv_pct"]) 
        for ph in active_phases 
        if phase_metrics[ph]["hv_pct"] > CONSIDERABLE_THRESHOLD_PCT
    ]
    viol_hv_list.sort(key=lambda x: x[1], reverse=True)
    worst_hv_pct = max([phase_metrics[ph]["hv_pct"] for ph in active_phases], default=0.0)

    if viol_hv_list:
        worst_hv_phase = viol_hv_list[0][0]
        worst_hv_display = f"{worst_hv_phase} ({viol_hv_list[0][1]:.2f}%)"
        violating_hv_str = ", ".join([f"{ph} ({pct:.2f}%)" for ph, pct in viol_hv_list])
    else:
        worst_hv_phase = "None"
        worst_hv_display = "—"
        violating_hv_str = "—"

    # 2. Low Voltage Violations (< 216.2V, excluding sensor defects)
    viol_lv_list = [
        (ph, phase_metrics[ph]["lv_clean_pct"]) 
        for ph in active_phases 
        if phase_metrics[ph]["lv_clean_pct"] > CONSIDERABLE_THRESHOLD_PCT
    ]
    viol_lv_list.sort(key=lambda x: x[1], reverse=True)
    worst_lv_pct = max([phase_metrics[ph]["lv_clean_pct"] for ph in active_phases], default=0.0)

    if viol_lv_list:
        worst_lv_phase = viol_lv_list[0][0]
        worst_lv_display = f"{worst_lv_phase} ({viol_lv_list[0][1]:.2f}%)"
        violating_lv_str = ", ".join([f"{ph} ({pct:.2f}%)" for ph, pct in viol_lv_list])
    else:
        worst_lv_phase = "None"
        worst_lv_display = "—"
        violating_lv_str = "—"

    # 3. Overall device compliance status (identifying all violating phases)
    has_sensor_defect = any(m["is_persistent_defect"] for m in phase_metrics.values())
    
    critical_items = []
    warning_items = []

    for ph, pct in viol_lv_list:
        if pct > BENCHMARK_WARNING_PCT:
            critical_items.append(f"{ph} LV: {pct:.1f}%")
        else:
            warning_items.append(f"{ph} LV: {pct:.1f}%")

    for ph, pct in viol_hv_list:
        if pct > BENCHMARK_WARNING_PCT:
            critical_items.append(f"{ph} HV: {pct:.1f}%")
        else:
            warning_items.append(f"{ph} HV: {pct:.1f}%")

    if critical_items:
        overall_status = f"🔴 Critical ({', '.join(critical_items)})"
        overall_badge = "critical"
    elif warning_items:
        overall_status = f"🟡 Warning ({', '.join(warning_items)})"
        overall_badge = "warning"
    elif has_sensor_defect:
        overall_status = "⚠️ Sensor Defect on 1 Phase"
        overall_badge = "sensor_defect"
    else:
        overall_status = "🟢 Optimal (All Phases <= 1%)"
        overall_badge = "optimal"

    return {
        "device_name": device_name,
        "total_records": total_records,
        "v_upper": v_upper,
        "v_lower": v_lower,
        "interruption_count": interruption_count,
        "interruption_hours": interruption_hours,
        "interruption_pct": interruption_pct,
        "phase_metrics": phase_metrics,
        "hardware_alerts": hardware_alerts,
        "viol_hv_list": viol_hv_list,
        "viol_lv_list": viol_lv_list,
        "violating_hv_str": violating_hv_str,
        "violating_lv_str": violating_lv_str,
        "worst_hv_display": worst_hv_display,
        "worst_lv_display": worst_lv_display,
        "worst_hv_pct": worst_hv_pct,
        "worst_hv_phase": worst_hv_phase,
        "worst_lv_pct": worst_lv_pct,
        "worst_lv_phase": worst_lv_phase,
        "overall_hv_pct": worst_hv_pct,
        "overall_lv_pct": worst_lv_pct,
        "overall_status": overall_status,
        "overall_badge": overall_badge,
        "df_clean": df_clean
    }


def compute_diurnal_voltage_profile(
    df_clean: pd.DataFrame,
    include_interruptions: bool = True
) -> pd.DataFrame:
    """
    Computes 24-hour diurnal average voltage profile (00:00 to 23:45, 96 intervals).
    - Neglects single-phase 0V readings (already NaN in Va_clean, Vb_clean, Vc_clean).
    - If include_interruptions is True, all-phase blackouts (0V on all 3 phases) are kept in the average.
    - If False, all-phase blackouts are also omitted to show energized grid voltage only.
    """
    df_calc = df_clean.copy()

    if not include_interruptions:
        # Mask out interruption rows
        all_zero_mask = (
            (df_calc["Va"] <= ZERO_VOLTAGE_THRESHOLD) &
            (df_calc["Vb"] <= ZERO_VOLTAGE_THRESHOLD) &
            (df_calc["Vc"] <= ZERO_VOLTAGE_THRESHOLD)
        )
        for ph in ["Va_clean", "Vb_clean", "Vc_clean", "V_3Phase_Clean"]:
            if ph in df_calc.columns:
                df_calc.loc[all_zero_mask, ph] = np.nan

    df_calc["Time_OfDay"] = df_calc["Timestamp"].dt.strftime("%H:%M")

    # Aggregate means and percentiles
    agg_funcs = {
        "Va_clean": ["mean", "min", "max"],
        "Vb_clean": ["mean", "min", "max"],
        "Vc_clean": ["mean", "min", "max"],
        "V_3Phase_Clean": ["mean", "min", "max"]
    }

    grouped = df_calc.groupby("Time_OfDay").agg(agg_funcs)
    grouped.columns = [f"{col}_{stat}" for col, stat in grouped.columns]
    grouped = grouped.reset_index().rename(columns={"Time_OfDay": "Time"})

    # Sort strictly by time
    grouped = grouped.sort_values("Time").reset_index(drop=True)
    return grouped


def analyze_all_network_voltages(
    device_readings: Dict[str, pd.DataFrame],
    names_df: Optional[pd.DataFrame] = None,
    nominal_v: float = NOMINAL_VOLTAGE,
    tolerance_pct: float = STATUTORY_TOLERANCE_PCT
) -> Dict[str, Any]:
    """
    Analyzes voltage profiles and statutory violations across all monitored network nodes.
    Returns per-device results, global violation summary table, and hardware diagnostic alerts.
    """
    devices_analysis = {}
    summary_rows = []
    all_hardware_alerts = []

    # Map device nickname to role & db name
    name_map = {}
    if names_df is not None and not names_df.empty:
        for _, row in names_df.iterrows():
            nick = str(row.get("Nickname", "")).strip()
            db_name = str(row.get("DB_Name", "")).strip()
            role = str(row.get("Role", "Feeder")).strip()
            name_map[nick] = {"db_name": db_name, "role": role}

    # Logical ordering helper
    def dev_sort_key(name):
        u = str(name).upper().strip()
        if "T/F" in u or "TRANS" in u or u in ["TF", "T/F"]:
            return (0, 0, name)
        m = re.search(r'(?:FEEDER|F)?[\s,\-_:]*(\d+)', u)
        if m:
            feeder_num = int(m.group(1))
            is_mid = 0 if ("M" in u or "MID" in u) else 1
            return (feeder_num, is_mid, name)
        return (99, 0, name)

    ordered_device_names = sorted(device_readings.keys(), key=dev_sort_key)

    hv_summary_rows = []
    lv_summary_rows = []

    for dev_name in ordered_device_names:
        df_dev = device_readings[dev_name]
        dev_res = analyze_device_voltage(df_dev, dev_name, nominal_v, tolerance_pct)
        devices_analysis[dev_name] = dev_res
        all_hardware_alerts.extend(dev_res.get("hardware_alerts", []))

        meta = name_map.get(dev_name, {"db_name": dev_name, "role": "Feeder"})
        pm = dev_res["phase_metrics"]

        # Combined summary row (backward compatibility)
        summary_rows.append({
            "Device": dev_name,
            "Role": meta["role"],
            "DB Name": meta["db_name"],
            "Total Records": dev_res["total_records"],
            "Outages (Hrs)": dev_res["interruption_hours"],
            "Va HV Viol (%)": pm["Phase A"]["hv_pct"],
            "Va LV Viol (%)": pm["Phase A"]["lv_clean_pct"],
            "Vb HV Viol (%)": pm["Phase B"]["hv_pct"],
            "Vb LV Viol (%)": pm["Phase B"]["lv_clean_pct"],
            "Vc HV Viol (%)": pm["Phase C"]["hv_pct"],
            "Vc LV Viol (%)": pm["Phase C"]["lv_clean_pct"],
            "HV Violating Phase(s)": dev_res["violating_hv_str"],
            "HV Worst Phase": dev_res["worst_hv_display"],
            "LV Violating Phase(s)": dev_res["violating_lv_str"],
            "LV Worst Phase": dev_res["worst_lv_display"],
            "Worst Phase HV (%)": dev_res["worst_hv_pct"],
            "Worst Phase LV (%)": dev_res["worst_lv_pct"],
            "Compliance Status": dev_res["overall_status"]
        })

        # Separate High Voltage (HV > 243.8V) Summary Row (Per-Phase Evaluation)
        max_v_seen = max(pm["Phase A"]["max_v"], pm["Phase B"]["max_v"], pm["Phase C"]["max_v"])
        if dev_res["viol_hv_list"]:
            crit_hv = [f"{ph} ({pct:.2f}%)" for ph, pct in dev_res["viol_hv_list"] if pct > BENCHMARK_WARNING_PCT]
            warn_hv = [f"{ph} ({pct:.2f}%)" for ph, pct in dev_res["viol_hv_list"] if pct <= BENCHMARK_WARNING_PCT]
            if crit_hv:
                hv_status = f"🔴 Critical ({', '.join(crit_hv)})"
            else:
                hv_status = f"🟡 Warning ({', '.join(warn_hv)})"
        else:
            hv_status = "🟢 Optimal (All Phases <= 1%)"

        hv_summary_rows.append({
            "Device": dev_name,
            "Role": meta["role"],
            "DB Name": meta["db_name"],
            "Total Records": dev_res["total_records"],
            "Va HV Viol (%)": pm["Phase A"]["hv_pct"],
            "Vb HV Viol (%)": pm["Phase B"]["hv_pct"],
            "Vc HV Viol (%)": pm["Phase C"]["hv_pct"],
            "Violating Phase(s)": dev_res["violating_hv_str"],
            "Worst Phase": dev_res["worst_hv_display"],
            "Worst Phase HV (%)": dev_res["worst_hv_pct"],
            "Max Voltage (V)": max_v_seen,
            "HV Status": hv_status
        })

        # Separate Low Voltage (LV < 216.2V) Summary Row (Per-Phase Evaluation)
        has_sensor_defect = any(m["is_persistent_defect"] for m in pm.values())
        min_v_cands = [m["min_energized_v"] for m in pm.values() if m["min_energized_v"] > ZERO_VOLTAGE_THRESHOLD]
        min_v_seen = min(min_v_cands) if min_v_cands else 0.0

        if dev_res["viol_lv_list"]:
            crit_lv = [f"{ph} ({pct:.2f}%)" for ph, pct in dev_res["viol_lv_list"] if pct > BENCHMARK_WARNING_PCT]
            warn_lv = [f"{ph} ({pct:.2f}%)" for ph, pct in dev_res["viol_lv_list"] if pct <= BENCHMARK_WARNING_PCT]
            if crit_lv:
                lv_status = f"🔴 Critical ({', '.join(crit_lv)})"
            else:
                lv_status = f"🟡 Warning ({', '.join(warn_lv)})"
        elif has_sensor_defect:
            lv_status = "⚠️ Sensor Defect on 1 Phase"
        else:
            lv_status = "🟢 Optimal (All Phases <= 1%)"

        lv_summary_rows.append({
            "Device": dev_name,
            "Role": meta["role"],
            "DB Name": meta["db_name"],
            "Total Records": dev_res["total_records"],
            "Outages (Hrs)": dev_res["interruption_hours"],
            "Va LV Viol (%)": pm["Phase A"]["lv_clean_pct"],
            "Vb LV Viol (%)": pm["Phase B"]["lv_clean_pct"],
            "Vc LV Viol (%)": pm["Phase C"]["lv_clean_pct"],
            "Violating Phase(s)": dev_res["violating_lv_str"],
            "Worst Phase": dev_res["worst_lv_display"],
            "Worst Phase LV (%)": dev_res["worst_lv_pct"],
            "Min Energized V": min_v_seen,
            "LV Status": lv_status
        })

    summary_df = pd.DataFrame(summary_rows)
    hv_summary_df = pd.DataFrame(hv_summary_rows)
    lv_summary_df = pd.DataFrame(lv_summary_rows)

    return {
        "nominal_v": nominal_v,
        "tolerance_pct": tolerance_pct,
        "v_upper": nominal_v * (1.0 + tolerance_pct / 100.0),
        "v_lower": nominal_v * (1.0 - tolerance_pct / 100.0),
        "devices": devices_analysis,
        "summary_df": summary_df,
        "hv_summary_df": hv_summary_df,
        "lv_summary_df": lv_summary_df,
        "all_hardware_alerts": all_hardware_alerts
    }


def create_diurnal_voltage_chart(
    df_diurnal: pd.DataFrame,
    device_name: str,
    nominal_v: float = NOMINAL_VOLTAGE,
    tolerance_pct: float = STATUTORY_TOLERANCE_PCT,
    hardware_alerts: Optional[List[Dict[str, Any]]] = None
) -> go.Figure:
    """
    Renders an interactive Plotly figure of the 24-hour diurnal voltage profile for a device.
    """
    v_upper = nominal_v * (1.0 + tolerance_pct / 100.0)
    v_lower = nominal_v * (1.0 - tolerance_pct / 100.0)

    fig = go.Figure()

    # Shaded Statutory Compliance Band (216.2V to 243.8V)
    fig.add_hrect(
        y0=v_lower, y1=v_upper,
        fillcolor="rgba(16, 185, 129, 0.08)",
        layer="below",
        line_width=0,
        annotation_text="Statutory Compliance Zone (230V +/- 6%)",
        annotation_position="top left",
        annotation=dict(font_size=10, font_color="#059669")
    )

    # Reference Lines
    fig.add_hline(y=v_upper, line_dash="dash", line_color="#EF4444", line_width=1.8,
                  annotation_text=f"Statutory Max +6% ({v_upper:.1f}V)", annotation_position="top right")
    fig.add_hline(y=v_lower, line_dash="dash", line_color="#EF4444", line_width=1.8,
                  annotation_text=f"Statutory Min -6% ({v_lower:.1f}V)", annotation_position="bottom right")
    fig.add_hline(y=nominal_v, line_dash="dot", line_color="#64748B", line_width=1.5,
                  annotation_text=f"Nominal ({nominal_v:.0f}V)", annotation_position="top left")

    # Diurnal Curves
    phase_colors = {
        "Va_clean_mean": ("#DC2626", "Phase A Voltage (Va)", "solid"),
        "Vb_clean_mean": ("#D97706", "Phase B Voltage (Vb)", "solid"),
        "Vc_clean_mean": ("#2563EB", "Phase C Voltage (Vc)", "solid"),
        "V_3Phase_Clean_mean": ("#7C3AED", "3-Phase Composite Average", "dash")
    }

    defect_phases = [a["phase"] for a in (hardware_alerts or [])]

    for col, (color, label, dash_style) in phase_colors.items():
        if col in df_diurnal.columns:
            # Check if this phase is entirely NaN due to persistent sensor defect
            is_dead = df_diurnal[col].isna().all()
            if is_dead:
                # Add dummy line for legend indicating defect
                fig.add_trace(go.Scatter(
                    x=[df_diurnal["Time"].iloc[0]], y=[nominal_v],
                    mode="markers",
                    marker=dict(size=10, color=color, symbol="x"),
                    name=f"{label} (⚠️ SENSOR DEFECT - 0V)",
                    hoverinfo="text",
                    hovertext=f"⚠️ {label}: All readings neglected due to persistent 0V sensor failure."
                ))
            else:
                fig.add_trace(go.Scatter(
                    x=df_diurnal["Time"],
                    y=df_diurnal[col],
                    mode="lines",
                    name=label,
                    line=dict(color=color, width=2.8 if "3Phase" in col else 2.0, dash=dash_style),
                    hovertemplate="<b>%{x}</b><br>" + label + ": <b>%{y:.1f} V</b><extra></extra>"
                ))

    title_text = f"<b>24-Hour Diurnal Voltage Profile: {device_name}</b> (15-Minute Daily Averages)"
    if defect_phases:
        title_text += f" <span style='color:red;'>[⚠️ Sensor Defect: {', '.join(defect_phases)}]</span>"

    fig.update_layout(
        title=dict(text=title_text, font=dict(size=15, color="#1E293B")),
        xaxis=dict(
            title="Time of Day (HH:MM)",
            tickangle=-45,
            gridcolor="#E2E8F0",
            showgrid=True,
            dtick=8
        ),
        yaxis=dict(
            title="Voltage (V)",
            gridcolor="#E2E8F0",
            showgrid=True,
            range=[190, 255]
        ),
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1.0),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=45, r=45, t=75, b=45)
    )
    return fig


def create_network_voltage_comparison_chart(
    devices_analysis: Dict[str, Any],
    names_df: Optional[pd.DataFrame] = None,
    nominal_v: float = NOMINAL_VOLTAGE,
    tolerance_pct: float = STATUTORY_TOLERANCE_PCT,
    title: Optional[str] = None
) -> go.Figure:
    """
    Renders multi-device 24-hour comparative diurnal voltage overlay (Transformer vs Feeder Ends).
    Highlights feeder voltage sag during evening peak load and voltage rise during solar injection.
    """
    v_upper = nominal_v * (1.0 + tolerance_pct / 100.0)
    v_lower = nominal_v * (1.0 - tolerance_pct / 100.0)

    fig = go.Figure()

    # Shaded Statutory Compliance Band
    fig.add_hrect(
        y0=v_lower, y1=v_upper,
        fillcolor="rgba(16, 185, 129, 0.08)",
        layer="below",
        line_width=0,
        annotation_text="Statutory Compliance Zone (230V +/- 6%)",
        annotation_position="top left",
        annotation=dict(font_size=10, font_color="#059669")
    )

    fig.add_hline(y=v_upper, line_dash="dash", line_color="#EF4444", line_width=1.5,
                  annotation_text=f"+6% ({v_upper:.1f}V)", annotation_position="top right")
    fig.add_hline(y=v_lower, line_dash="dash", line_color="#EF4444", line_width=1.5,
                  annotation_text=f"-6% ({v_lower:.1f}V)", annotation_position="bottom right")
    fig.add_hline(y=nominal_v, line_dash="dot", line_color="#94A3B8", line_width=1.2,
                  annotation_text="230V Nominal", annotation_position="top left")

    palette = [
        "#1E3A8A", "#059669", "#D97706", "#7C3AED", 
        "#DC2626", "#0891B2", "#4F46E5", "#BE123C"
    ]

    for idx, (dev_name, res) in enumerate(devices_analysis.items()):
        df_clean = res.get("df_clean")
        if df_clean is None or df_clean.empty:
            continue

        diurnal = compute_diurnal_voltage_profile(df_clean, include_interruptions=True)
        if "V_3Phase_Clean_mean" not in diurnal.columns:
            continue

        is_tf = ("T/F" in dev_name.upper()) or ("TRANS" in dev_name.upper())
        color = palette[idx % len(palette)]
        line_width = 3.5 if is_tf else 2.2
        dash_style = "solid" if is_tf else ("dash" if "M" in dev_name else "solid")

        # Construct descriptive trace label including feeder/side name if available
        if is_tf:
            label = f"⚡ {dev_name} (Transformer)" if dev_name.upper() not in ["TRANSFORMER"] else f"⚡ {dev_name}"
        else:
            dev_label = dev_name
            if names_df is not None and not names_df.empty:
                m_row = names_df[names_df["Nickname"] == dev_name]
                if not m_row.empty:
                    db_n = str(m_row["DB_Name"].iloc[0]).strip()
                    clean_n = re.sub(r'^[Ff]\d+[\s,\-_:]+', '', db_n).strip().replace('_', ' ')
                    if clean_n.isupper(): clean_n = clean_n.title()
                    if clean_n and clean_n != dev_name:
                        dev_label = f"{dev_name} - {clean_n}"
            label = dev_label

        fig.add_trace(go.Scatter(
            x=diurnal["Time"],
            y=diurnal["V_3Phase_Clean_mean"],
            mode="lines",
            name=label,
            line=dict(color=color, width=line_width, dash=dash_style),
            hovertemplate="<b>%{x}</b><br>" + label + ": <b>%{y:.1f} V</b><extra></extra>"
        ))

    layout_args = dict(
        xaxis=dict(
            title="Time of Day (HH:MM)",
            tickangle=-45,
            gridcolor="#E2E8F0",
            showgrid=True,
            dtick=8
        ),
        yaxis=dict(
            title="Average 3-Phase Voltage (V)",
            gridcolor="#E2E8F0",
            showgrid=True,
            range=[195, 250]
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=45, r=25, t=35, b=45)
    )
    if title:
        layout_args["title"] = dict(text=title, font=dict(size=14, color="#1E293B"))
        layout_args["margin"]["t"] = 75

    fig.update_layout(**layout_args)
    return fig


def create_voltage_drop_delta_chart(
    devices_analysis: Dict[str, Any],
    names_df: Optional[pd.DataFrame] = None,
    transformer_nick: str = "T/F",
    title: Optional[str] = None
) -> Optional[go.Figure]:
    """
    Renders Feeder Voltage Delta (ΔV = V_Feeder - V_Transformer) over 24 hours.
    - ΔV > 0: Solar Reverse Power Voltage Rise at feeder ends.
    - ΔV < 0: Resistive & Inductive Voltage Drop along feeder conductors due to customer load.
    """
    # Locate transformer device
    tf_res = devices_analysis.get(transformer_nick)
    if tf_res is None:
        for k, v in devices_analysis.items():
            if "T/F" in k.upper() or "TRANS" in k.upper():
                tf_res = v
                transformer_nick = k
                break

    if tf_res is None or tf_res.get("df_clean") is None:
        return None

    tf_diurnal = compute_diurnal_voltage_profile(tf_res["df_clean"], include_interruptions=True)
    if "V_3Phase_Clean_mean" not in tf_diurnal.columns:
        return None

    tf_series = tf_diurnal.set_index("Time")["V_3Phase_Clean_mean"]

    fig = go.Figure()

    # Zero Reference Line (Transformer Voltage Baseline)
    fig.add_hline(y=0.0, line_dash="solid", line_color="#334155", line_width=2.0,
                  annotation_text="0V (Transformer Voltage Baseline)", annotation_position="top left")

    # High Voltage Rise and Low Voltage Sag Guidance Bands
    fig.add_hrect(y0=0.0, y1=15.0, fillcolor="rgba(245, 158, 11, 0.06)", layer="below", line_width=0,
                  annotation_text="☀️ Solar Voltage Rise Zone (ΔV > 0)", annotation_position="top right",
                  annotation=dict(font_size=10, font_color="#D97706"))
    fig.add_hrect(y0=-25.0, y1=0.0, fillcolor="rgba(59, 130, 246, 0.06)", layer="below", line_width=0,
                  annotation_text="📉 Load Voltage Drop Zone (ΔV < 0)", annotation_position="bottom right",
                  annotation=dict(font_size=10, font_color="#2563EB"))

    palette = ["#059669", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#4F46E5", "#BE123C"]
    trace_idx = 0

    for dev_name, res in devices_analysis.items():
        if dev_name == transformer_nick:
            continue
        df_clean = res.get("df_clean")
        if df_clean is None or df_clean.empty:
            continue

        diurnal = compute_diurnal_voltage_profile(df_clean, include_interruptions=True)
        if "V_3Phase_Clean_mean" not in diurnal.columns:
            continue

        f_series = diurnal.set_index("Time")["V_3Phase_Clean_mean"]
        delta_v = f_series - tf_series

        color = palette[trace_idx % len(palette)]
        trace_idx += 1
        dash_style = "dash" if "M" in dev_name else "solid"

        # Construct descriptive trace label including feeder/side name
        dev_label = dev_name
        if names_df is not None and not names_df.empty:
            m_row = names_df[names_df["Nickname"] == dev_name]
            if not m_row.empty:
                db_n = str(m_row["DB_Name"].iloc[0]).strip()
                clean_n = re.sub(r'^[Ff]\d+[\s,\-_:]+', '', db_n).strip().replace('_', ' ')
                if clean_n.isupper(): clean_n = clean_n.title()
                if clean_n and clean_n != dev_name:
                    dev_label = f"{dev_name} - {clean_n}"

        fig.add_trace(go.Scatter(
            x=delta_v.index,
            y=delta_v.values,
            mode="lines",
            name=f"ΔV: {dev_label}",
            line=dict(color=color, width=2.4, dash=dash_style),
            hovertemplate="<b>%{x}</b><br>" + f"ΔV ({dev_label}): " + "<b>%{y:+.2f} V</b><extra></extra>"
        ))

    layout_args = dict(
        xaxis=dict(
            title="Time of Day (HH:MM)",
            tickangle=-45,
            gridcolor="#E2E8F0",
            showgrid=True,
            dtick=8
        ),
        yaxis=dict(
            title="Voltage Differential ΔV (Volts)",
            gridcolor="#E2E8F0",
            showgrid=True
        ),
        hovermode="x unified",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        margin=dict(l=45, r=25, t=35, b=45)
    )
    if title:
        layout_args["title"] = dict(text=title, font=dict(size=14, color="#1E293B"))
        layout_args["margin"]["t"] = 75

    fig.update_layout(**layout_args)
    return fig

