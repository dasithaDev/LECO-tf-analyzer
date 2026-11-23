"""
sample_data_generator.py
Utility to generate realistic 30-day (15-min interval) NMD Excel workbooks
with all 4 sheets (DB, Names, Poles, Solar Customers) under various CT scenarios:
1. All CTs Normal (Safe State)
2. Phase A CT Reversed (Failure Mode 4)
3. All 3 CTs Reversed (Failure Mode 1)
4. Phase B & C Reversed (Failure Mode 3)
5. Channel Swap (Failure Mode 2)
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import io


def generate_nmd_excel(scenario: str = "normal", num_days: int = 30) -> bytes:
    """
    Generates an in-memory Excel file (bytes) with 4 sheets:
    - DB
    - Names
    - Poles
    - Solar Customers
    """
    # 1. Sheet: Names
    names_data = [
        {"Nickname": "T/F", "DB_Name": "042/BZ5000", "Pole_ID": "AB1", "Capacity": "160kVA"},
        {"Nickname": "F1", "DB_Name": "Kalegana Side", "Pole_ID": "AB5", "Capacity": ""},
        {"Nickname": "F1M", "DB_Name": "Kalegane Side 2", "Pole_ID": "AB2/2", "Capacity": ""},
        {"Nickname": "F2", "DB_Name": "Wakvalla side", "Pole_ID": "CD7", "Capacity": ""},
    ]
    df_names = pd.DataFrame(names_data)

    # 2. Sheet: Poles
    poles_f1 = [
        "AB1", "AB2", "AB3", "AB4", "AB4-1", "AB5",
        "AB2/1", "AB2/2", "AB2/3", "AB2/1A", "AB2/1B", "AB5A"
    ]
    poles_f2 = [
        "CD1", "CD2", "CD3", "CD4", "CD5", "CD6", "CD7",
        "CD3/1", "CD3/2", "CD5A"
    ]
    max_len = max(len(poles_f1), len(poles_f2))
    poles_f1_padded = poles_f1 + [""] * (max_len - len(poles_f1))
    poles_f2_padded = poles_f2 + [""] * (max_len - len(poles_f2))
    
    df_poles = pd.DataFrame({
        "F1 (Kalegana Side)": poles_f1_padded,
        "F2 (Wakvalla side)": poles_f2_padded
    })

    # 3. Sheet: Solar Customers
    solar_customers = [
        {"Customer_ID": "SOL-001", "Pole_ID": "AB3", "Inverter_Capacity_kW": 10.0, "Installed_Capacity_kW": 11.2, "Phase": "3-Phase"},
        {"Customer_ID": "SOL-002", "Pole_ID": "AB4", "Inverter_Capacity_kW": 5.0, "Installed_Capacity_kW": 5.0, "Phase": "Single Phase (R)"},
        {"Customer_ID": "SOL-003", "Pole_ID": "AB2/1", "Inverter_Capacity_kW": 15.0, "Installed_Capacity_kW": 18.0, "Phase": "3-Phase"},
        {"Customer_ID": "SOL-004", "Pole_ID": "AB2/3", "Inverter_Capacity_kW": 8.0, "Installed_Capacity_kW": 7.5, "Phase": "3-Phase"},
        {"Customer_ID": "SOL-005", "Pole_ID": "AB5A", "Inverter_Capacity_kW": 6.0, "Installed_Capacity_kW": 6.0, "Phase": "Single Phase (Y)"},
        {"Customer_ID": "SOL-006", "Pole_ID": "CD3", "Inverter_Capacity_kW": 12.0, "Installed_Capacity_kW": 12.5, "Phase": "3-Phase"},
        {"Customer_ID": "SOL-007", "Pole_ID": "CD5A", "Inverter_Capacity_kW": 5.0, "Installed_Capacity_kW": 4.8, "Phase": "Single Phase (B)"},
    ]
    df_solar = pd.DataFrame(solar_customers)

    # 4. Sheet: DB (15-min time series for num_days)
    start_dt = datetime(2026, 8, 1, 0, 0)
    total_steps = num_days * 96
    timestamps = [start_dt + timedelta(minutes=15 * i) for i in range(total_steps)]

    np.random.seed(42)
    db_rows = []
    
    devices = [
        ("042/BZ5000", 1.0, 1.0),
        ("Kalegana Side", 0.45, 0.96),
        ("Kalegane Side 2", 0.70, 0.98),
        ("Wakvalla side", 0.40, 0.97)
    ]

    for dev_name, load_scale, v_scale in devices:
        is_tf = (dev_name == "042/BZ5000")
        
        for ts in timestamps:
            hour = ts.hour + ts.minute / 60.0
            is_night = (hour >= 21.0) or (hour < 5.0)
            
            # Base consumer load profile
            base_load = (
                25.0
                + 30.0 * np.exp(-0.5 * ((hour - 8.0) / 1.5) ** 2)
                + 55.0 * np.exp(-0.5 * ((hour - 20.0) / 2.0) ** 2)
                + 15.0 * np.exp(-0.5 * ((hour - 13.0) / 3.0) ** 2)
            )
            
            # Solar generation between 06:00 and 18:00
            if 6.0 <= hour <= 18.0:
                solar_gen = 50.0 * np.sin(np.pi * (hour - 6.0) / 12.0) ** 2
            else:
                solar_gen = 0.0

            day_idx = (ts - start_dt).days
            cloud_factor = 1.0 - 0.15 * np.sin(day_idx * 0.8)
            solar_gen *= cloud_factor

            # Raw forward currents
            i_a = abs((base_load * 1.05 - solar_gen * 1.0) * load_scale + np.random.normal(0, 1.0))
            i_b = abs((base_load * 0.98 - solar_gen * 0.95) * load_scale + np.random.normal(0, 1.0))
            i_c = abs((base_load * 1.02 - solar_gen * 1.05) * load_scale + np.random.normal(0, 1.0))

            # Power calculations
            total_i = i_a + i_b + i_c
            total_kva = round((total_i * 230.0) / 1000.0, 2)
            total_kw = round(total_kva * 0.95, 2)
            
            # Default normal powers:
            # Daytime with excess solar could have export; nighttime is 100% import
            imp_kva = total_kva
            exp_kva = 0.0
            imp_kw = total_kw
            exp_kw = 0.0

            # Scenario adjustments for Transformer
            if is_tf:
                if scenario == "phase_a_reversed":
                    # FM4: Phase A Negative & Nighttime Import
                    i_a = -i_a
                    imp_kva = total_kva
                    exp_kva = 0.0
                elif scenario == "all_reversed":
                    # FM1: All Negative & Nighttime Export
                    i_a = -i_a
                    i_b = -i_b
                    i_c = -i_c
                    exp_kva = total_kva
                    imp_kva = 0.0
                    exp_kw = total_kw
                    imp_kw = 0.0
                elif scenario == "phase_bc_reversed":
                    # FM3: Phase A Outlier (A pos, B/C neg) & Nighttime Export
                    i_b = -i_b
                    i_c = -i_c
                    exp_kva = total_kva
                    imp_kva = 0.0
                elif scenario == "channel_swap":
                    # FM2: All Positive & Nighttime Export (Channel Swap)
                    exp_kva = total_kva
                    imp_kva = 0.0
                # normal: i_a, i_b, i_c > 0 and imp_kva > 0, exp_kva = 0.0

            v_drop = (base_load - solar_gen) * 0.12 * (1.0 - v_scale)
            v_a = round(230.0 * v_scale - v_drop + np.random.normal(0, 0.5), 1)
            v_b = round(229.0 * v_scale - v_drop + np.random.normal(0, 0.5), 1)
            v_c = round(231.0 * v_scale - v_drop + np.random.normal(0, 0.5), 1)

            db_rows.append({
                "SERIAL": 23400385,
                "CUSTOMER_REF": dev_name,
                "DATE": ts.strftime("%Y-%m-%d"),
                "TIME": ts.strftime("%H:%M:%S"),
                "AVG._IMPORT_KW (kW)": imp_kw,
                "AVG._EXPORT_KW (kW)": exp_kw,
                "AVG._IMPORT_KVA (kVA)": imp_kva,
                "AVG._EXPORT_KVA (kVA)": exp_kva,
                "PHASE_A_INST._CURRENT (A)": round(i_a, 2),
                "PHASE_B_INST._CURRENT (A)": round(i_b, 2),
                "PHASE_C_INST._CURRENT (A)": round(i_c, 2),
                "PHASE_A_INST._VOLTAGE (V)": v_a,
                "PHASE_B_INST._VOLTAGE (V)": v_b,
                "PHASE_C_INST._VOLTAGE (V)": v_c,
                "INST._POWER_FACTOR": 0.95
            })

    df_db = pd.DataFrame(db_rows)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df_db.to_excel(writer, sheet_name="DB", index=False)
        df_names.to_excel(writer, sheet_name="Names", index=False)
        df_poles.to_excel(writer, sheet_name="Poles", index=False)
        df_solar.to_excel(writer, sheet_name="Solar Customers", index=False)
        
    return output.getvalue()


if __name__ == "__main__":
    for sc, fname in [
        ("normal", "Sample_NMD_Normal_30Days.xlsx"),
        ("phase_a_reversed", "Sample_NMD_PhaseA_Reversed_30Days.xlsx"),
        ("all_reversed", "Sample_NMD_All_Reversed_30Days.xlsx"),
        ("phase_bc_reversed", "Sample_NMD_PhaseBC_Reversed_30Days.xlsx")
    ]:
        data = generate_nmd_excel(sc, num_days=30)
        with open(fname, "wb") as f:
            f.write(data)
        print(f"Generated {fname} ({len(data)} bytes)")
