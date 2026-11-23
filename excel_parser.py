"""
excel_parser.py
Robust parser for the 4 sheets of NMD Transformer Excel files:
1. DB: 15-min interval readings of NMDs and Transformer meter
2. Names: Nickname (T/F, F1, F1M, F2), DB Name, Pole ID
3. Poles: Pole sequence for each feeder (main feeder & spurs)
4. Solar Customers: Solar customer details (pole, inverter capacity, installed capacity)
"""

import io
import re
import pandas as pd
import numpy as np
from typing import Dict, Any, Tuple, Optional, List


def find_sheet_name(sheet_names: List[str], targets: List[str]) -> Optional[str]:
    """Finds a matching sheet name from a list of targets (case-insensitive substring)."""
    for target in targets:
        for name in sheet_names:
            if target.lower() == name.strip().lower():
                return name
    for target in targets:
        for name in sheet_names:
            if target.lower() in name.strip().lower():
                return name
    return None


def clean_string_key(s: Any) -> str:
    """Strips whitespace, underscores, dashes, commas, and slashes for fuzzy matching."""
    return re.sub(r"[\s\-_,\./\\]+", "", str(s)).lower()


def extract_capacity_value(val: Any) -> Optional[float]:
    """
    Extracts a numeric transformer capacity (kVA) from a cell string or numeric value.
    Examples:
      '160kVA', '160 kVA', '160KVA' -> 160.0
      '250', 250, 250.0 -> 250.0
      'ST13/9' -> None (ignored, not a capacity)
    """
    if val is None or pd.isna(val):
        return None
    s = str(val).strip()
    if not s or s.lower() in ["nan", "none", "-", ""]:
        return None
    
    # Priority 1: explicitly contains kVA or k.v.a (e.g. 160kVA, 160 kVA, 250 kva)
    m_kva = re.search(r'(\d+(?:\.\d+)?)\s*(?:kva|k\.v\.a)\b', s, re.IGNORECASE)
    if m_kva:
        try:
            cap = float(m_kva.group(1))
            if 10.0 <= cap <= 5000.0:
                return cap
        except (ValueError, TypeError):
            pass

    # Priority 2: Purely numeric string or number (e.g. "160", "250", 160)
    m_num = re.fullmatch(r'(\d+(?:\.\d+)?)', s)
    if m_num:
        try:
            cap = float(m_num.group(1))
            if 10.0 <= cap <= 5000.0:
                return cap
        except (ValueError, TypeError):
            pass

    return None


def parse_names_sheet(df_names_raw: pd.DataFrame) -> pd.DataFrame:
    """
    Parses Names sheet:
    Col 1: Nickname (e.g. T/F, F1, F1M, F2)
    Col 2: Name in DB (e.g. 042/BZ5000, 042/BZ5504, Kalegana Side, Wakvalla side)
    Col 3: Pole ID (e.g. AB1, ST13/9, etc.)
    Col 4 (Optional): Transformer Capacity (e.g. 160kVA in cell next to Pole ID)
    
    Handles cases where the sheet has NO header row (first row is data).
    """
    df = df_names_raw.copy()
    
    # Check if pandas treated the first data row as a header
    # e.g. columns might be ['F1M', 'wanarathana Mw Side', 'ST13/10H']
    first_col_name = str(df.columns[0]).strip().upper()
    is_headerless = (
        first_col_name in ["T/F", "TF", "F1", "F2", "F3", "F4", "F1M", "F2M", "F3M", "F4M"]
        or not any(term in "".join(str(c).lower() for c in df.columns) for term in ["nick", "name", "feeder", "device", "meter", "pole"])
    )
    
    if is_headerless:
        # Prepend the column names as the first data row
        header_row = pd.DataFrame([list(df.columns)], columns=df.columns)
        df = pd.concat([header_row, df], ignore_index=True)

    # Drop columns that are completely all NaN/empty (e.g. empty columns E, F, G)
    df = df.dropna(axis=1, how="all")

    # Map columns based on available width
    if df.shape[1] >= 4:
        df = df.iloc[:, :4]
        df.columns = ["Nickname", "DB_Name", "Pole_ID", "Capacity"]
    elif df.shape[1] == 3:
        df = df.iloc[:, :3]
        df.columns = ["Nickname", "DB_Name", "Pole_ID"]
        df["Capacity"] = ""
    elif df.shape[1] == 2:
        df.columns = ["Nickname", "DB_Name"]
        df["Pole_ID"] = ""
        df["Capacity"] = ""
    else:
        raise ValueError("Names sheet must contain at least 2 columns (Nickname, DB Name).")

    # Drop fully NaN rows
    df = df.dropna(how="all")
    # Clean strings
    df["Nickname"] = df["Nickname"].astype(str).str.strip()
    df["DB_Name"] = df["DB_Name"].astype(str).str.strip()
    if "Pole_ID" in df.columns:
        df["Pole_ID"] = df["Pole_ID"].astype(str).str.strip().replace("nan", "").replace("None", "")
    if "Capacity" in df.columns:
        df["Capacity"] = df["Capacity"].astype(str).str.strip().replace("nan", "").replace("None", "")

    # Classify role
    def classify_role(nickname: str) -> str:
        nick = nickname.upper().strip()
        if "T/F" in nick or "TRANS" in nick or nick == "TF":
            return "Transformer"
        elif "M" in nick:
            return "Middle NMD"
        elif nick.startswith("F") or "FEEDER" in nick:
            return "Feeder End NMD"
        return "NMD"

    df["Role"] = df["Nickname"].apply(classify_role)
    return df


def parse_poles_sheet(df_poles: pd.DataFrame) -> Dict[str, List[str]]:
    """
    Parses Poles sheet:
    Each column represents a feeder with its sequence of pole IDs in order.
    """
    feeders_poles = {}
    
    for col in df_poles.columns:
        col_name = str(col).strip()
        series = df_poles[col].dropna().astype(str).str.strip()
        
        # Filter out comment / separator lines like "---- Main Feeder ----"
        clean_poles = []
        for val in series:
            if not val or val.lower() == "nan":
                continue
            if set(val).issubset({"-", "=", "_", " "}):
                continue
            if "----" in val or "=====" in val:
                continue
            if val.lower().startswith("main feeder") or val.lower().startswith("spur feeder"):
                continue
            clean_poles.append(val)
            
        if clean_poles:
            feeders_poles[col_name] = clean_poles
        
    return feeders_poles


def parse_solar_customers_sheet(df_solar: pd.DataFrame) -> pd.DataFrame:
    """
    Parses Solar Customers sheet:
    Extracts:
    - Connected pole number
    - Inverter capacity
    - Installed capacity
    - Effective solar capacity = min(inverter_capacity, installed_capacity)
    """
    df = df_solar.copy()
    
    # Normalize column names
    col_map = {}
    for col in df.columns:
        c_lower = str(col).lower().strip()
        if "inv" in c_lower and "cap" in c_lower:
            col_map[col] = "Inverter_Capacity_kW"
        elif "cap" in c_lower and "inv" not in c_lower:
            col_map[col] = "Installed_Capacity_kW"
        elif "pole" in c_lower:
            col_map[col] = "Pole_ID"
        elif any(k in c_lower for k in ["account", "cust", "sin", "meter"]):
            col_map[col] = "Customer_ID"
        elif "phase" in c_lower:
            col_map[col] = "Phase"

    df = df.rename(columns=col_map)
    
    # Ensure Pole_ID exists
    if "Pole_ID" not in df.columns:
        for c in df.columns:
            if "pole" in str(c).lower():
                df["Pole_ID"] = df[c]
                break
        if "Pole_ID" not in df.columns:
            df["Pole_ID"] = "Unknown"
            
    df["Pole_ID"] = df["Pole_ID"].astype(str).str.strip()
    
    # Customer ID fallback
    if "Customer_ID" not in df.columns:
        df["Customer_ID"] = [f"CUST-{i+1}" for i in range(len(df))]
    else:
        df["Customer_ID"] = df["Customer_ID"].astype(str).str.strip()

    # Convert capacities to float
    for cap_col in ["Inverter_Capacity_kW", "Installed_Capacity_kW"]:
        if cap_col in df.columns:
            df[cap_col] = pd.to_numeric(
                df[cap_col].astype(str).str.replace(r"[^\d.]", "", regex=True),
                errors="coerce"
            ).fillna(0.0)
        else:
            df[cap_col] = 0.0

    # Effective capacity rule: min(inverter_capacity, installed_capacity)
    def calculate_effective(row):
        inv = row["Inverter_Capacity_kW"]
        inst = row["Installed_Capacity_kW"]
        if inv > 0 and inst > 0:
            return min(inv, inst)
        elif inv > 0:
            return inv
        elif inst > 0:
            return inst
        return 0.0

    df["Effective_Capacity_kW"] = df.apply(calculate_effective, axis=1)
    
    return df


def parse_db_sheet(df_db: pd.DataFrame, names_df: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    """
    Parses DB sheet:
    Contains 15-minute readings for a month for NMDs and Transformer.
    Handles both Long format (Device column like CUSTOMER_REF) and Wide format.
    """
    device_data = {}
    
    # 1. Parse Date and Time / Timestamp
    date_col = None
    time_col = None
    timestamp_col = None
    
    for col in df_db.columns:
        c_lower = str(col).lower().strip()
        if c_lower == "date":
            date_col = col
        elif c_lower == "time":
            time_col = col
        elif "timestamp" in c_lower or "date_time" in c_lower or "datetime" in c_lower:
            timestamp_col = col

    # Check for Device / Meter column (e.g. CUSTOMER_REF, DEVICE_NAME, METER_ID)
    device_col = None
    for col in df_db.columns:
        c_lower = str(col).lower().strip()
        if any(term in c_lower for term in [
            "customer_ref", "device", "meter", "nmd", "feeder_name", 
            "customer", "site", "location", "meter_id", "station"
        ]):
            device_col = col
            break

    # Helper function to extract and standardize columns from a sub-DataFrame
    def map_standard_cols(sub_df: pd.DataFrame) -> pd.DataFrame:
        clean_df = pd.DataFrame()
        
        # Build datetime Timestamp
        if date_col and time_col and date_col in sub_df.columns and time_col in sub_df.columns:
            date_part = sub_df[date_col].astype(str).str.split().str[0]
            time_part = sub_df[time_col].astype(str)
            clean_df["Timestamp"] = pd.to_datetime(date_part + " " + time_part, errors="coerce")
        elif timestamp_col and timestamp_col in sub_df.columns:
            sample_val = sub_df[timestamp_col].dropna().iloc[0] if len(sub_df[timestamp_col].dropna()) > 0 else 0
            # If numeric epoch milliseconds
            if isinstance(sample_val, (int, float)) and sample_val > 1e11:
                clean_df["Timestamp"] = pd.to_datetime(sub_df[timestamp_col], unit="ms", errors="coerce")
            else:
                clean_df["Timestamp"] = pd.to_datetime(sub_df[timestamp_col], errors="coerce")
        elif date_col and date_col in sub_df.columns:
            clean_df["Timestamp"] = pd.to_datetime(sub_df[date_col], errors="coerce")
        else:
            # Fallback
            clean_df["Timestamp"] = pd.date_range("2026-08-01 00:00", periods=len(sub_df), freq="15min")
            
        clean_df = clean_df.dropna(subset=["Timestamp"])

        # Currents: Phase A, Phase B, Phase C
        # Note: Must NEVER match 'SERIAL'!
        ia_pattern = re.compile(r"(phase[_\s]*a.*curr|curr.*phase[_\s]*a|current[_\s]*a\b|\bia\b|\bir\b|phase[_\s]*r.*curr|phase[_\s]*1.*curr)", re.IGNORECASE)
        ib_pattern = re.compile(r"(phase[_\s]*b.*curr|curr.*phase[_\s]*b|current[_\s]*b\b|\bib\b|\biy\b|phase[_\s]*y.*curr|phase[_\s]*2.*curr)", re.IGNORECASE)
        ic_pattern = re.compile(r"(phase[_\s]*c.*curr|curr.*phase[_\s]*c|current[_\s]*c\b|\bic\b|phase[_\s]*3.*curr|phase[_\s]*b.*curr.*\(blue\))", re.IGNORECASE)

        # Match columns
        matched_ia = None
        matched_ib = None
        matched_ic = None

        for c in sub_df.columns:
            c_str = str(c).strip()
            if "serial" in c_str.lower() or "volt" in c_str.lower():
                continue
            if not matched_ia and ia_pattern.search(c_str):
                matched_ia = c
            elif not matched_ib and ib_pattern.search(c_str):
                matched_ib = c
            elif not matched_ic and ic_pattern.search(c_str):
                matched_ic = c

        clean_df["Ia"] = pd.to_numeric(sub_df[matched_ia], errors="coerce").fillna(0.0) if matched_ia else 0.0
        clean_df["Ib"] = pd.to_numeric(sub_df[matched_ib], errors="coerce").fillna(0.0) if matched_ib else 0.0
        clean_df["Ic"] = pd.to_numeric(sub_df[matched_ic], errors="coerce").fillna(0.0) if matched_ic else 0.0

        # Voltages: Phase A, Phase B, Phase C
        va_pattern = re.compile(r"(phase[_\s]*a.*volt|volt.*phase[_\s]*a|voltage[_\s]*a\b|\bva\b|\bvr\b|phase[_\s]*r.*volt|phase[_\s]*1.*volt)", re.IGNORECASE)
        vb_pattern = re.compile(r"(phase[_\s]*b.*volt|volt.*phase[_\s]*b|voltage[_\s]*b\b|\bvb\b|\bvy\b|phase[_\s]*y.*volt|phase[_\s]*2.*volt)", re.IGNORECASE)
        vc_pattern = re.compile(r"(phase[_\s]*c.*volt|volt.*phase[_\s]*c|voltage[_\s]*c\b|\bvc\b|phase[_\s]*3.*volt)", re.IGNORECASE)

        matched_va = None
        matched_vb = None
        matched_vc = None

        for c in sub_df.columns:
            c_str = str(c).strip()
            if "curr" in c_str.lower():
                continue
            if not matched_va and va_pattern.search(c_str):
                matched_va = c
            elif not matched_vb and vb_pattern.search(c_str):
                matched_vb = c
            elif not matched_vc and vc_pattern.search(c_str):
                matched_vc = c

        clean_df["Va"] = pd.to_numeric(sub_df[matched_va], errors="coerce").fillna(230.0) if matched_va else 230.0
        clean_df["Vb"] = pd.to_numeric(sub_df[matched_vb], errors="coerce").fillna(230.0) if matched_vb else 230.0
        clean_df["Vc"] = pd.to_numeric(sub_df[matched_vc], errors="coerce").fillna(230.0) if matched_vc else 230.0

        # Active Power (kW) and Apparent Power (kVA)
        matched_p = None
        matched_import_kva = None
        matched_export_kva = None
        matched_import_kw = None
        matched_export_kw = None

        for c in sub_df.columns:
            c_str = str(c).lower().strip()
            # Explicitly exclude cumulative energy registers (kvarh, kwh)
            if "kvar" in c_str or "kwh" in c_str:
                continue
            if "import" in c_str and "kva" in c_str:
                matched_import_kva = c
            elif "export" in c_str and "kva" in c_str:
                matched_export_kva = c
            elif "import" in c_str and "kw" in c_str:
                matched_import_kw = c
            elif "export" in c_str and "kw" in c_str:
                matched_export_kw = c
            elif any(k in c_str for k in ["active_power", "active power", "total_kw"]):
                matched_p = c

        clean_df["Import_kVA"] = pd.to_numeric(sub_df[matched_import_kva], errors="coerce").fillna(0.0) if matched_import_kva else 0.0
        clean_df["Export_kVA"] = pd.to_numeric(sub_df[matched_export_kva], errors="coerce").fillna(0.0) if matched_export_kva else 0.0
        clean_df["Import_kW"] = pd.to_numeric(sub_df[matched_import_kw], errors="coerce").fillna(0.0) if matched_import_kw else 0.0
        clean_df["Export_kW"] = pd.to_numeric(sub_df[matched_export_kw], errors="coerce").fillna(0.0) if matched_export_kw else 0.0

        # Net Load (kVA) = Import kVA - Export kVA (as specified)
        clean_df["Net_Load_kVA"] = clean_df["Import_kVA"] - clean_df["Export_kVA"]
        clean_df["Net_Load_kW"] = clean_df["Import_kW"] - clean_df["Export_kW"]

        # Fallback if kVA columns are zero but phase currents & voltages are present
        if (clean_df["Import_kVA"] == 0.0).all() and (clean_df["Export_kVA"] == 0.0).all():
            if "Ia" in clean_df.columns and clean_df["Ia"].abs().max() > 0:
                calc_kva = (clean_df["Ia"] * clean_df["Va"] + clean_df["Ib"] * clean_df["Vb"] + clean_df["Ic"] * clean_df["Vc"]) / 1000.0
                clean_df["Import_kVA"] = calc_kva.clip(lower=0.0)
                clean_df["Export_kVA"] = (-calc_kva).clip(lower=0.0)
                clean_df["Net_Load_kVA"] = clean_df["Import_kVA"] - clean_df["Export_kVA"]

        # Primary P fallback
        if matched_p:
            clean_df["P"] = pd.to_numeric(sub_df[matched_p], errors="coerce").fillna(0.0)
        elif matched_import_kw:
            clean_df["P"] = clean_df["Import_kW"]
        else:
            clean_df["P"] = clean_df["Import_kVA"] * 0.95

        # Power Factor
        matched_pf = None
        for c in sub_df.columns:
            c_str = str(c).lower().strip()
            if "power_factor" in c_str or "pf" in c_str:
                matched_pf = c
                break
        clean_df["PF"] = pd.to_numeric(sub_df[matched_pf], errors="coerce").fillna(1.0) if matched_pf else 1.0

        clean_df = clean_df.sort_values("Timestamp").reset_index(drop=True)
        return clean_df

    # Case 1: Long format (device_col present like CUSTOMER_REF)
    if device_col is not None:
        db_unique_devices = df_db[device_col].dropna().unique()
        
        for _, row in names_df.iterrows():
            nickname = row["Nickname"]
            db_name = row["DB_Name"]
            clean_target = clean_string_key(db_name)
            
            # Find matching device in DB
            matched_val = None
            # 1. Exact match
            for val in db_unique_devices:
                if str(val).strip().lower() == str(db_name).strip().lower():
                    matched_val = val
                    break
            # 2. Fuzzy clean match (ignoring spaces, punctuation)
            if matched_val is None:
                for val in db_unique_devices:
                    if clean_string_key(val) == clean_target:
                        matched_val = val
                        break
            # 3. Substring match
            if matched_val is None:
                for val in db_unique_devices:
                    if clean_target in clean_string_key(val) or clean_string_key(val) in clean_target:
                        matched_val = val
                        break
            # 4. Nickname match
            if matched_val is None:
                for val in db_unique_devices:
                    if clean_string_key(nickname) == clean_string_key(val):
                        matched_val = val
                        break

            if matched_val is not None:
                sub_df = df_db[df_db[device_col] == matched_val].copy()
                device_data[nickname] = map_standard_cols(sub_df)

    # Case 2: Wide format (columns prefixed by device name)
    if len(device_data) == 0:
        for _, row in names_df.iterrows():
            nickname = row["Nickname"]
            db_name = row["DB_Name"]
            clean_target = clean_string_key(db_name)
            
            matched_cols = []
            for col in df_db.columns:
                c_str = str(col)
                if clean_target in clean_string_key(c_str) or clean_string_key(nickname) in clean_string_key(c_str):
                    matched_cols.append(col)
            
            if matched_cols:
                extra_cols = [c for c in [date_col, time_col, timestamp_col] if c and c in df_db.columns]
                sub_cols = list(dict.fromkeys(extra_cols + matched_cols))
                sub_df = df_db[sub_cols].copy()
                device_data[nickname] = map_standard_cols(sub_df)

    # Case 3: Fallback (assign whole df to Transformer)
    if len(device_data) == 0:
        tf_row = names_df[names_df["Role"] == "Transformer"]
        tf_nick = tf_row["Nickname"].iloc[0] if len(tf_row) > 0 else "T/F"
        device_data[tf_nick] = map_standard_cols(df_db)

    return device_data


def parse_nmd_excel(file_path_or_bytes: Any) -> Dict[str, Any]:
    """
    Main entry point: loads Excel file and parses all 4 sheets.
    Accepts file path string, bytes, or file-like object.
    """
    try:
        if isinstance(file_path_or_bytes, bytes):
            file_obj = io.BytesIO(file_path_or_bytes)
        else:
            file_obj = file_path_or_bytes

        excel_file = pd.ExcelFile(file_obj)
        sheet_names = excel_file.sheet_names
        
        # 1. Sheet: Names
        names_sheet = find_sheet_name(sheet_names, ["Names", "Name", "Feeders", "Devices"])
        if not names_sheet:
            return {"status": "error", "error_message": f"Could not find 'Names' sheet. Available sheets: {sheet_names}"}
        
        # Read raw names sheet (try without header first if first row contains data)
        df_names_raw = pd.read_excel(excel_file, sheet_name=names_sheet)
        names_df = parse_names_sheet(df_names_raw)
        
        # Identify Transformer
        tf_row = names_df[names_df["Role"] == "Transformer"]
        if len(tf_row) == 0:
            tf_nick = names_df["Nickname"].iloc[0]
            tf_db_name = names_df["DB_Name"].iloc[0]
        else:
            tf_nick = tf_row["Nickname"].iloc[0]
            tf_db_name = tf_row["DB_Name"].iloc[0]

        # Extract Transformer Capacity if present in Names sheet (in front of Transformer Pole ID)
        detected_tf_capacity = None
        raw_capacity_str = ""

        # Priority 1: Check Capacity column in names_df for the transformer row
        if len(tf_row) > 0 and "Capacity" in tf_row.columns:
            raw_val = tf_row["Capacity"].iloc[0]
            c_val = extract_capacity_value(raw_val)
            if c_val is not None:
                detected_tf_capacity = c_val
                raw_capacity_str = str(raw_val).strip()

        # Priority 2: Scan all columns of transformer row in raw df_names_raw
        if detected_tf_capacity is None and len(tf_row) > 0:
            tf_idx = tf_row.index[0]
            for check_idx in [tf_idx, tf_idx - 1, tf_idx + 1]:
                if 0 <= check_idx < len(df_names_raw):
                    for cell in df_names_raw.iloc[check_idx]:
                        c_val = extract_capacity_value(cell)
                        if c_val is not None:
                            detected_tf_capacity = c_val
                            raw_capacity_str = str(cell).strip()
                            break
                if detected_tf_capacity is not None:
                    break

        # Priority 3: Scan any cell in df_names_raw that contains 'kva'
        if detected_tf_capacity is None:
            for r_idx in range(len(df_names_raw)):
                for c_idx in range(df_names_raw.shape[1]):
                    cell = df_names_raw.iloc[r_idx, c_idx]
                    if cell is not None and not pd.isna(cell):
                        s_cell = str(cell).strip()
                        if "kva" in s_cell.lower():
                            c_val = extract_capacity_value(s_cell)
                            if c_val is not None:
                                detected_tf_capacity = c_val
                                raw_capacity_str = s_cell
                                break
                if detected_tf_capacity is not None:
                    break

        # 2. Sheet: DB
        db_sheet = find_sheet_name(sheet_names, ["DB", "Data", "Readings", "Database"])
        if not db_sheet:
            return {"status": "error", "error_message": f"Could not find 'DB' sheet. Available sheets: {sheet_names}"}
        df_db_raw = pd.read_excel(excel_file, sheet_name=db_sheet)
        device_readings = parse_db_sheet(df_db_raw, names_df)
        
        # 3. Sheet: Poles
        poles_sheet = find_sheet_name(sheet_names, ["Poles", "Pole", "Feeder_Poles", "Network"])
        poles_dict = {}
        if poles_sheet:
            df_poles_raw = pd.read_excel(excel_file, sheet_name=poles_sheet)
            poles_dict = parse_poles_sheet(df_poles_raw)

        # 4. Sheet: Solar Customers
        solar_sheet = find_sheet_name(sheet_names, ["Solar Customers", "Solar", "Customers", "Solar_Customers", "PV"])
        solar_df = pd.DataFrame()
        if solar_sheet:
            df_solar_raw = pd.read_excel(excel_file, sheet_name=solar_sheet)
            solar_df = parse_solar_customers_sheet(df_solar_raw)

        return {
            "status": "success",
            "names_df": names_df,
            "poles_dict": poles_dict,
            "solar_df": solar_df,
            "device_readings": device_readings,
            "transformer_nick": tf_nick,
            "transformer_db_name": tf_db_name,
            "transformer_capacity_kva": detected_tf_capacity,
            "transformer_capacity_raw": raw_capacity_str,
            "capacity_from_excel": bool(detected_tf_capacity is not None),
            "sheets_found": sheet_names,
            "summary": {
                "devices_count": len(names_df),
                "feeders_count": len([k for k in poles_dict.keys()]),
                "solar_customers_count": len(solar_df),
                "total_solar_kw": solar_df["Effective_Capacity_kW"].sum() if len(solar_df) > 0 else 0.0,
                "tf_readings_count": len(device_readings.get(tf_nick, []))
            }
        }
    except Exception as e:
        return {
            "status": "error",
            "error_message": f"Error parsing Excel file: {str(e)}"
        }
