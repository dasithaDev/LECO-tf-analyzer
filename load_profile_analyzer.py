"""
load_profile_analyzer.py
Module for analyzing Transformer Daily Load Profiles based on NMD readings:
Net Load (kVA) = Import kVA - Export kVA

Computes:
1. 24-hour Diurnal Average Load Curve (with min/max envelope, weekday vs weekend)
2. Morning Peak, Midday Solar Trough (Solar Dip), and Evening Peak Identification
3. Single-day 24-hour profiles
4. Daily Peak, Average, Load Factor, Energy Throughput (kVAh), and Capacity Loading %
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, Any, List, Tuple


def compute_daily_load_profiles(df_tf: pd.DataFrame, rated_capacity_kva: float = 160.0) -> Dict[str, Any]:
    """
    Computes comprehensive daily load profile metrics for the transformer.
    Net Load (kVA) = Import kVA - Export kVA
    """
    df = df_tf.copy()
    df["Timestamp"] = pd.to_datetime(df["Timestamp"])
    
    # Ensure Import_kVA, Export_kVA, and Net_Load_kVA exist
    if "Import_kVA" not in df.columns:
        df["Import_kVA"] = 0.0
    if "Export_kVA" not in df.columns:
        df["Export_kVA"] = 0.0
        
    df["Net_Load_kVA"] = df["Import_kVA"] - df["Export_kVA"]
    
    # Fallback if both Import and Export were 0 but currents exist
    if (df["Import_kVA"] == 0.0).all() and (df["Export_kVA"] == 0.0).all():
        if "Ia" in df.columns and df["Ia"].abs().max() > 0:
            calc_kva = (df["Ia"] * df.get("Va", 230.0) + df["Ib"] * df.get("Vb", 230.0) + df["Ic"] * df.get("Vc", 230.0)) / 1000.0
            df["Import_kVA"] = calc_kva.clip(lower=0.0)
            df["Export_kVA"] = (-calc_kva).clip(lower=0.0)
            df["Net_Load_kVA"] = df["Import_kVA"] - df["Export_kVA"]

    df["Date"] = df["Timestamp"].dt.date
    df["Time"] = df["Timestamp"].dt.strftime("%H:%M")
    df["Hour_Float"] = df["Timestamp"].dt.hour + df["Timestamp"].dt.minute / 60.0
    df["DayOfWeek"] = df["Timestamp"].dt.day_name()
    df["Is_Weekend"] = df["Timestamp"].dt.day_of_week >= 5

    # 1. 24-Hour Average Profile (96 intervals)
    time_grouped = df.groupby("Time")
    avg_24h = pd.DataFrame({
        "Time": time_grouped["Net_Load_kVA"].mean().index,
        "Net_Load_Mean": time_grouped["Net_Load_kVA"].mean().round(2).values,
        "Net_Load_Median": time_grouped["Net_Load_kVA"].median().round(2).values,
        "Net_Load_Min": time_grouped["Net_Load_kVA"].min().round(2).values,
        "Net_Load_Max": time_grouped["Net_Load_kVA"].max().round(2).values,
        "Net_Load_P10": time_grouped["Net_Load_kVA"].quantile(0.10).round(2).values,
        "Net_Load_P90": time_grouped["Net_Load_kVA"].quantile(0.90).round(2).values,
        "Import_kVA_Mean": time_grouped["Import_kVA"].mean().round(2).values,
        "Export_kVA_Mean": time_grouped["Export_kVA"].mean().round(2).values,
    }).sort_values("Time").reset_index(drop=True)

    # Weekday vs Weekend 24h profiles
    weekday_df = df[~df["Is_Weekend"]]
    weekend_df = df[df["Is_Weekend"]]

    if len(weekday_df) > 0:
        wk_avg = weekday_df.groupby("Time")["Net_Load_kVA"].mean().round(2).to_dict()
        avg_24h["Weekday_Net_Load"] = avg_24h["Time"].map(wk_avg).fillna(avg_24h["Net_Load_Mean"])
    else:
        avg_24h["Weekday_Net_Load"] = avg_24h["Net_Load_Mean"]

    if len(weekend_df) > 0:
        wknd_avg = weekend_df.groupby("Time")["Net_Load_kVA"].mean().round(2).to_dict()
        avg_24h["Weekend_Net_Load"] = avg_24h["Time"].map(wknd_avg).fillna(avg_24h["Net_Load_Mean"])
    else:
        avg_24h["Weekend_Net_Load"] = avg_24h["Net_Load_Mean"]

    # 2. Key Daily Landmarks on 24-Hour Average Profile
    # Morning window (06:00 - 10:00)
    morn_mask = (avg_24h["Time"] >= "06:00") & (avg_24h["Time"] <= "10:00")
    morn_peak_row = avg_24h[morn_mask].loc[avg_24h[morn_mask]["Net_Load_Mean"].idxmax()] if morn_mask.any() else avg_24h.iloc[32]
    
    # Midday Solar Trough window (11:00 - 14:30)
    mid_mask = (avg_24h["Time"] >= "11:00") & (avg_24h["Time"] <= "14:30")
    mid_trough_row = avg_24h[mid_mask].loc[avg_24h[mid_mask]["Net_Load_Mean"].idxmin()] if mid_mask.any() else avg_24h.iloc[48]

    # Evening Peak window (18:00 - 22:30)
    eve_mask = (avg_24h["Time"] >= "18:00") & (avg_24h["Time"] <= "22:30")
    eve_peak_row = avg_24h[eve_mask].loc[avg_24h[eve_mask]["Net_Load_Mean"].idxmax()] if eve_mask.any() else avg_24h.iloc[80]

    # Solar Dip Reduction (Difference between morning/evening peak baseline and midday valley)
    baseline_peak = max(morn_peak_row["Net_Load_Mean"], eve_peak_row["Net_Load_Mean"])
    solar_dip_kva = round(max(0.0, baseline_peak - mid_trough_row["Net_Load_Mean"]), 2)

    landmarks = {
        "morning_peak": {
            "time": morn_peak_row["Time"],
            "load_kva": morn_peak_row["Net_Load_Mean"]
        },
        "midday_solar_trough": {
            "time": mid_trough_row["Time"],
            "load_kva": mid_trough_row["Net_Load_Mean"],
            "solar_dip_reduction_kva": solar_dip_kva
        },
        "evening_peak": {
            "time": eve_peak_row["Time"],
            "load_kva": eve_peak_row["Net_Load_Mean"]
        }
    }

    # 3. Day-by-Day Load Statistics Table
    daily_records = []
    for d, g in df.groupby("Date"):
        if len(g) < 12:
            continue
        max_idx = g["Net_Load_kVA"].idxmax()
        min_idx = g["Net_Load_kVA"].idxmin()
        peak_val = round(float(g.loc[max_idx, "Net_Load_kVA"]), 2)
        min_val = round(float(g.loc[min_idx, "Net_Load_kVA"]), 2)
        avg_val = round(float(g["Net_Load_kVA"].mean()), 2)
        lf_pct = round((avg_val / peak_val * 100.0) if peak_val > 0 else 0.0, 1)
        loading_pct = round((peak_val / rated_capacity_kva * 100.0) if rated_capacity_kva > 0 else 0.0, 1)
        energy_imp = round(float(g["Import_kVA"].sum() * 0.25), 1)  # 15 min = 0.25 h
        energy_exp = round(float(g["Export_kVA"].sum() * 0.25), 1)

        daily_records.append({
            "Date": d,
            "Day": g["DayOfWeek"].iloc[0],
            "Peak_Net_Load_kVA": peak_val,
            "Peak_Time": g.loc[max_idx, "Time"],
            "Min_Net_Load_kVA": min_val,
            "Min_Time": g.loc[min_idx, "Time"],
            "Avg_Net_Load_kVA": avg_val,
            "Load_Factor_Pct": lf_pct,
            "Peak_Loading_Pct": loading_pct,
            "Energy_Import_kVAh": energy_imp,
            "Energy_Export_kVAh": energy_exp,
            "Intervals_Count": len(g)
        })

    daily_stats_df = pd.DataFrame(daily_records)

    # 4. Monthly Overall Metrics & Average Demand Curve Overload Analysis
    abs_peak_val = round(float(df["Net_Load_kVA"].max()), 2) if len(df) > 0 else 0.0
    abs_peak_idx = df["Net_Load_kVA"].idxmax() if len(df) > 0 else None
    abs_peak_ts = df.loc[abs_peak_idx, "Timestamp"].strftime("%Y-%m-%d %H:%M") if abs_peak_idx is not None else "N/A"

    abs_min_val = round(float(df["Net_Load_kVA"].min()), 2) if len(df) > 0 else 0.0
    abs_min_idx = df["Net_Load_kVA"].idxmin() if len(df) > 0 else None
    abs_min_ts = df.loc[abs_min_idx, "Timestamp"].strftime("%Y-%m-%d %H:%M") if abs_min_idx is not None else "N/A"

    monthly_avg_load = round(float(df["Net_Load_kVA"].mean()), 2) if len(df) > 0 else 0.0
    monthly_load_factor = round((monthly_avg_load / abs_peak_val * 100.0) if abs_peak_val > 0 else 0.0, 1)
    monthly_peak_loading = round((abs_peak_val / rated_capacity_kva * 100.0) if rated_capacity_kva > 0 else 0.0, 1)
    total_energy_import_mvah = round(float(df["Import_kVA"].sum() * 0.25 / 1000.0), 2)
    total_energy_export_mvah = round(float(df["Export_kVA"].sum() * 0.25 / 1000.0), 2)

    # Average demand curve peak & overload statistics
    if not avg_24h.empty:
        avg_peak_idx = avg_24h["Net_Load_Mean"].idxmax()
        avg_peak_demand_kva = round(float(avg_24h.loc[avg_peak_idx, "Net_Load_Mean"]), 2)
        avg_peak_time = str(avg_24h.loc[avg_peak_idx, "Time"])
        avg_demand_loading_pct = round((avg_peak_demand_kva / rated_capacity_kva * 100.0) if rated_capacity_kva > 0 else 0.0, 1)
        is_overloaded_from_avg = bool(avg_peak_demand_kva > rated_capacity_kva)
        avg_headroom_kva = round(max(0.0, rated_capacity_kva - avg_peak_demand_kva), 2)

        # Calculate duration of overload on average demand curve
        overload_rows = avg_24h[avg_24h["Net_Load_Mean"] > rated_capacity_kva]
        if len(overload_rows) > 0:
            avg_overload_hours = round(len(overload_rows) * 0.25, 2)
            avg_overload_start = str(overload_rows["Time"].iloc[0])
            avg_overload_end = str(overload_rows["Time"].iloc[-1])
            avg_overload_time_range = f"{avg_overload_start} to {avg_overload_end}"
        else:
            avg_overload_hours = 0.0
            avg_overload_start = "N/A"
            avg_overload_end = "N/A"
            avg_overload_time_range = "None"
    else:
        avg_peak_demand_kva = 0.0
        avg_peak_time = "N/A"
        avg_demand_loading_pct = 0.0
        is_overloaded_from_avg = False
        avg_headroom_kva = rated_capacity_kva
        avg_overload_hours = 0.0
        avg_overload_start = "N/A"
        avg_overload_end = "N/A"
        avg_overload_time_range = "None"

    # Loading classification (prioritizing average demand curve evaluation)
    if is_overloaded_from_avg:
        loading_status = f"OVERLOADED ON AVG CURVE ({avg_demand_loading_pct}%)"
        loading_color = "red"
    elif monthly_peak_loading > 100.0:
        loading_status = f"OVERLOADED ON MONTHLY PEAK ({monthly_peak_loading}%)"
        loading_color = "red"
    elif avg_demand_loading_pct > 80.0:
        loading_status = "HEAVY LOADING (80% - 100%)"
        loading_color = "orange"
    elif avg_demand_loading_pct > 50.0:
        loading_status = "NORMAL / OPTIMAL (50% - 80%)"
        loading_color = "green"
    else:
        loading_status = "LIGHT LOADING (< 50%)"
        loading_color = "blue"

    return {
        "avg_24h_profile": avg_24h,
        "landmarks": landmarks,
        "daily_stats_df": daily_stats_df,
        "raw_df": df,
        "metrics": {
            "monthly_peak_kva": abs_peak_val,
            "monthly_peak_timestamp": abs_peak_ts,
            "monthly_min_kva": abs_min_val,
            "monthly_min_timestamp": abs_min_ts,
            "monthly_avg_load_kva": monthly_avg_load,
            "monthly_load_factor_pct": monthly_load_factor,
            "rated_capacity_kva": rated_capacity_kva,
            "monthly_peak_loading_pct": monthly_peak_loading,
            "avg_peak_demand_kva": avg_peak_demand_kva,
            "avg_peak_time": avg_peak_time,
            "avg_demand_loading_pct": avg_demand_loading_pct,
            "is_overloaded_from_avg": is_overloaded_from_avg,
            "avg_headroom_kva": avg_headroom_kva,
            "avg_overload_hours": avg_overload_hours,
            "avg_overload_time_range": avg_overload_time_range,
            "loading_status": loading_status,
            "loading_color": loading_color,
            "total_import_mvah": total_energy_import_mvah,
            "total_export_mvah": total_energy_export_mvah,
            "total_days": len(daily_records)
        }
    }

