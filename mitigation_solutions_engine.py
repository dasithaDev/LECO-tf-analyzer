"""
mitigation_solutions_engine.py
================================================================================
Comprehensive Engineering Mitigation & Solution Advisory Engine for Distribution
Transformers and LV Radial Feeder Networks.

Provides rule-based, prioritized engineering solutions for:
1. CT Polarity Inversion & Transformer Overload Indeterminacy Gate.
2. Transformer Capacity Overload Mitigation (Augmentation vs. New Substation).
3. Low Voltage (LV < 216.2V) Mitigation (Phase Balancing, Load Transferring,
   Express Feeder, Off-Circuit Tap Changer Adjustment).
4. High Voltage (HV > 243.8V) Mitigation (Solar Inverter Phase Balancing,
   Parallel Feedering, Voltage Regulation / Tap Lowering).
5. Sectional Problem Localization (Middle NMD vs. Feeder End NMD Comparison).
6. NMD Hardware Metering Channel Fault Rectification.
================================================================================
"""

import re
from typing import Dict, Any, List, Optional
import pandas as pd
import numpy as np
from feeder_topology_analyzer import get_feeder_name_lookup, get_feeder_display_name, extract_feeder_key, clean_feeder_name


def get_feeder_direct_name(feeder_key: str, lookup: Optional[Dict[str, str]] = None) -> str:
    """
    Formats a feeder key into user-preferred direct naming:
    e.g. 'Feeder 1 (Wanarathana mawatha)' or 'Feeder 2 (Panvila Side)'.
    If no descriptive name exists in lookup, returns 'Feeder 1' (or 'Feeder {num}').
    """
    lookup = lookup or {}
    fk_clean = str(feeder_key).strip()
    m_num = re.search(r'\d+', fk_clean)
    num_str = m_num.group(0) if m_num else fk_clean
    
    name = (
        lookup.get(fk_clean, "")
        or lookup.get(f"F{num_str}", "")
        or lookup.get(num_str, "")
        or lookup.get(f"Feeder {num_str}", "")
        or lookup.get(f"Feeder-{num_str}", "")
    )
    if name and str(name).strip():
        cleaned_name = clean_feeder_name(name)
        if cleaned_name:
            return f"Feeder {num_str} ({cleaned_name})"
    return f"Feeder {num_str}"


def analyze_mitigation_solutions(
    ct_result: Dict[str, Any],
    load_result: Dict[str, Any],
    network_voltage_result: Dict[str, Any],
    network_topo: Dict[str, Any],
    parsed_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Executes the full diagnostic mitigation advisory workflow.
    
    Returns a structured dictionary containing prioritized actions,
    domain-specific mitigation plans, sectional localizations, and a
    comprehensive action matrix DataFrame.
    """
    names_df = parsed_data.get("names_df", pd.DataFrame())
    tf_nick = parsed_data.get("transformer_nick", "T/F")
    
    # -------------------------------------------------------------------------
    # STEP 1: CURRENT TRANSFORMER (CT) POLARITY VERIFICATION & OVERLOAD GATE
    # -------------------------------------------------------------------------
    ct_mode = ct_result.get("dominant_mode", "NORMAL_IMPORT")
    is_ct_normal = (ct_mode == "NORMAL_IMPORT")
    ct_confidence = ct_result.get("confidence_percent", 100.0)
    ct_status_label = ct_result.get("status_label", "System Normal")
    
    ct_solution: Dict[str, Any] = {
        "is_normal": is_ct_normal,
        "mode": ct_mode,
        "confidence": ct_confidence,
        "status_label": ct_status_label,
        "affected_phases": [],
        "solution_title": "",
        "solution_desc": "",
        "overload_assessment_blocked": not is_ct_normal,
        "overload_blocked_reason": ""
    }
    
    if not is_ct_normal:
        # Determine which phases are reversed
        mode_phase_map = {
            "FM1": ["Phase A", "Phase B", "Phase C"],
            "FM2": ["Phase A", "Phase B"],
            "FM3": ["Phase B", "Phase C"],
            "FM4": ["Phase A"],
            "FM5": ["Phase B"],
            "FM6": ["Phase C"]
        }
        affected = mode_phase_map.get(ct_mode, ["Affected Phase(s)"])
        ct_solution["affected_phases"] = affected
        phases_str = ", ".join(affected)
        
        ct_solution["solution_title"] = f"Correct Physical CT Polarity on {phases_str}"
        ct_solution["solution_desc"] = (
            f"Dispatch a field maintenance crew to immediately swap the physical polarity orientation "
            f"of the Current Transformer secondary wiring leads ({phases_str}) at the NMD terminal block. "
            f"Ensure the secondary dot (S1/k) aligns with the line source (P1/K) on the LV busbar."
        )
        ct_solution["overload_blocked_reason"] = (
            f"CRITICAL ENGINEERING NOTICE: Because Current Transformer polarity is physically inverted on {phases_str}, "
            f"active power (kW), reactive power (kVAr), and net apparent power (kVA) calculations are corrupted "
            f"(customer consumption is registering as solar export or power factor signs are inverted). "
            f"Therefore, it is impossible to determine whether the transformer is overloaded or underloaded. "
            f"Transformer capacity assessment must remain DEFERRED until CT wiring polarity is rectified."
        )
    else:
        ct_solution["solution_title"] = "CT Secondary Polarity Verified Normal"
        ct_solution["solution_desc"] = (
            "All Current Transformer secondary circuits are correctly wired with proper polarity across "
            "all three phases (100% confidence). Net power flow calculations are physically accurate."
        )

    # -------------------------------------------------------------------------
    # STEP 2: TRANSFORMER LOADING & OVERLOAD CAPACITY PLAN
    # -------------------------------------------------------------------------
    lm = load_result.get("metrics", {})
    peak_kva = lm.get("monthly_peak_kva", 0.0)
    rated_cap = lm.get("rated_capacity_kva", 160.0)
    peak_pct = lm.get("monthly_peak_loading_pct", 0.0)
    
    # Overload is evaluated strictly from the 24-hour representative average demand curve
    avg_peak_kva = lm.get("avg_peak_demand_kva", lm.get("monthly_avg_load_kva", peak_kva))
    avg_peak_pct = lm.get("avg_demand_loading_pct", round((avg_peak_kva / rated_cap * 100.0) if rated_cap > 0 else 0.0, 1))
    avg_peak_time = lm.get("avg_peak_time", "N/A")
    is_overloaded = bool(avg_peak_kva > rated_cap)
    headroom_kva = max(0.0, rated_cap - avg_peak_kva)
    
    transformer_solution: Dict[str, Any] = {
        "is_overloaded": is_overloaded,
        "is_overloaded_from_avg": is_overloaded,
        "peak_kva": avg_peak_kva,
        "monthly_abs_peak_kva": peak_kva,
        "avg_peak_demand_kva": avg_peak_kva,
        "avg_peak_time": avg_peak_time,
        "avg_demand_loading_pct": avg_peak_pct,
        "rated_cap": rated_cap,
        "peak_loading_pct": avg_peak_pct,
        "headroom_kva": headroom_kva,
        "status": "OVERLOADED" if is_overloaded else "NORMAL",
        "evaluation_valid": is_ct_normal,
        "recommendations": []
    }
    
    if not is_ct_normal:
        transformer_solution["status"] = "BLOCKED_BY_CT"
        transformer_solution["recommendations"].append({
            "title": "Deferred Capacity Assessment (Pending CT Rectification)",
            "type": "Prerequisite",
            "description": (
                "Accurate transformer loading cannot be confirmed due to inverted CT polarity. "
                "Re-run loading analysis immediately after CT secondary leads are physically corrected in the field."
            )
        })
    elif is_overloaded:
        transformer_solution["is_overloaded"] = True
        transformer_solution["status"] = "OVERLOADED"
        
        # Suggest next standard IEC transformer rating based on average peak demand
        standard_ratings = [50.0, 100.0, 160.0, 250.0, 400.0, 630.0, 1000.0]
        next_rating = next((r for r in standard_ratings if r > avg_peak_kva * 1.25), rated_cap * 1.5)
        
        transformer_solution["recommendations"].append({
            "title": f"Substation Augmentation (Upgrade to {next_rating:.0f} kVA)",
            "type": "Primary",
            "description": (
                f"The 24-hour representative average demand curve exceeds the transformer rating {rated_cap:.0f} kVA, "
                f"reaching a peak average demand of {avg_peak_kva:.1f} kVA ({avg_peak_pct:.1f}% loading) at {avg_peak_time}. "
                f"Replace the existing unit with a higher capacity {next_rating:.0f} kVA transformer to restore operating thermal headroom (targeting < 80% loading)."
            )
        })
        transformer_solution["recommendations"].append({
            "title": "New Distribution Transformer Installation & Load Deloading",
            "type": "Alternative",
            "description": (
                "Construct a new 11kV/400V distribution substation closer to downstream load concentrations. "
                "Bifurcate the network and transfer one or more heavily loaded radial feeders (or major spur branches) "
                "to the new substation, directly reducing load stress on the existing unit."
            )
        })
    elif avg_peak_pct >= 90.0:
        transformer_solution["status"] = "NEAR_CAPACITY"
        transformer_solution["recommendations"].append({
            "title": "Substation Load Monitoring & Growth Planning",
            "type": "Advisory",
            "description": (
                f"Transformer average peak loading has reached {avg_peak_pct:.1f}% ({avg_peak_kva:.1f} kVA of {rated_cap:.0f} kVA capacity at {avg_peak_time}). "
                f"Remaining headroom is only {headroom_kva:.1f} kVA. Plan for transformer augmentation or branch transfer "
                f"before upcoming seasonal peak or new service connections."
            )
        })
    else:
        transformer_solution["status"] = "NORMAL"
        transformer_solution["recommendations"].append({
            "title": "Adequate Substation Capacity Headroom",
            "type": "Informational",
            "description": (
                f"Transformer representative 24-hour average demand is within safe operational limits ({avg_peak_pct:.1f}% loading, {avg_peak_kva:.1f} kVA at {avg_peak_time}). "
                f"Adequate reserve capacity ({headroom_kva:.1f} kVA headroom) is available."
            )
        })

    # -------------------------------------------------------------------------
    # GATHER NETWORK VOLTAGE & DEVICE DATA
    # -------------------------------------------------------------------------
    lv_summary = network_voltage_result.get("lv_summary_df", pd.DataFrame())
    hv_summary = network_voltage_result.get("hv_summary_df", pd.DataFrame())
    devices_dict = network_voltage_result.get("devices", {})
    all_hw_alerts = network_voltage_result.get("all_hardware_alerts", [])
    
    # Extract human-readable feeder names lookup (e.g. {'F1': 'Wanarathana mawatha', ...})
    feeder_lookup = get_feeder_name_lookup(names_df)

    # Map device role and feeder association
    feeder_meta = {}
    assigned_keys = set()
    unassigned_count = 0

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
                    unassigned_count += 1
                    f_key = f"F{unassigned_count}"
                assigned_keys.add(f_key)
            
            feeder_meta[nick] = {
                "db_name": db_name,
                "role": role,
                "pole": pole,
                "feeder_key": f_key,
                "is_middle": is_mid,
                "is_transformer": is_tf
            }

    # Identify End NMD devices per feeder
    feeder_ends = {}
    feeder_middles = {}
    for nick, meta in feeder_meta.items():
        if meta["is_transformer"]:
            continue
        fk = meta["feeder_key"]
        if not fk:
            continue
        if meta["is_middle"]:
            feeder_middles[fk] = nick
        else:
            feeder_ends[fk] = nick

    # Also check if any feeder in topo has no explicit end NMD in names_df
    for fk in network_topo.get("feeders", {}).keys():
        if fk not in feeder_ends:
            # Fallback to any device matching fk that isn't middle
            for nick, meta in feeder_meta.items():
                if meta["feeder_key"] == fk and not meta["is_transformer"]:
                    feeder_ends[fk] = nick
                    break

    # Comprehensive fallback: Check lv_summary and hv_summary to ensure EVERY non-transformer device is captured
    for sum_df in [lv_summary, hv_summary]:
        if sum_df is not None and not sum_df.empty:
            for _, row in sum_df.iterrows():
                dev = str(row.get("Device", "")).strip()
                role_val = str(row.get("Role", "")).strip()
                db_n = str(row.get("DB Name", "")).strip()
                if not dev or dev == tf_nick or "TRANS" in role_val.upper() or "T/F" in role_val.upper():
                    continue
                # If this device is already in feeder_ends or feeder_middles, skip
                if dev in feeder_ends.values() or dev in feeder_middles.values():
                    continue
                # Determine its feeder key
                fk = extract_feeder_key(dev, db_n, role_val)
                if not fk or fk in feeder_ends:
                    unassigned_count += 1
                    fk = f"F{unassigned_count}"
                    while fk in feeder_ends:
                        unassigned_count += 1
                        fk = f"F{unassigned_count}"
                is_mid = ("MIDDLE" in role_val.upper()) or bool(re.search(r'(?:^F\d+M$|\bMID\b|\bMIDDLE\b)', dev.upper()))
                if is_mid:
                    feeder_middles[fk] = dev
                else:
                    feeder_ends[fk] = dev
                if dev not in feeder_meta:
                    feeder_meta[dev] = {
                        "db_name": db_n or dev,
                        "role": role_val or ("Feeder Middle NMD" if is_mid else "Feeder End NMD"),
                        "pole": "",
                        "feeder_key": fk,
                        "is_middle": is_mid,
                        "is_transformer": False
                    }

    # -------------------------------------------------------------------------
    # STEP 3: LOW VOLTAGE (LV < 216.2V) MITIGATION ANALYSIS
    # -------------------------------------------------------------------------
    # Check Transformer LV status
    tf_lv_row = lv_summary[lv_summary["Device"] == tf_nick]
    if tf_lv_row.empty:
        tf_lv_row = lv_summary[lv_summary["Role"].astype(str).str.upper().str.contains("TRANS")]
    if tf_lv_row.empty and not lv_summary.empty:
        tf_lv_row = lv_summary.iloc[[0]]

    tf_lv_violation = False
    tf_worst_lv = 0.0
    if not tf_lv_row.empty:
        r = tf_lv_row.iloc[0]
        v_a = float(r.get("Va LV Viol (%)", 0.0))
        v_b = float(r.get("Vb LV Viol (%)", 0.0))
        v_c = float(r.get("Vc LV Viol (%)", 0.0))
        tf_worst_lv = max(v_a, v_b, v_c)
        if tf_worst_lv > 1.0:
            tf_lv_violation = True

    # Check Feeder Ends LV status
    feeder_lv_analysis = []
    all_ends_have_lv = True if feeder_ends else False
    
    for fk, end_nick in sorted(feeder_ends.items()):
        row = lv_summary[lv_summary["Device"] == end_nick]
        if row.empty:
            meta = feeder_meta.get(end_nick, {})
            db_n = meta.get("db_name", "")
            if db_n:
                row = lv_summary[lv_summary["DB Name"] == db_n]
        if row.empty:
            row = lv_summary[lv_summary["Device"].astype(str).str.strip().str.upper() == str(end_nick).strip().upper()]
        if row.empty:
            continue
        r = row.iloc[0]
        va_lv = float(r.get("Va LV Viol (%)", 0.0))
        vb_lv = float(r.get("Vb LV Viol (%)", 0.0))
        vc_lv = float(r.get("Vc LV Viol (%)", 0.0))
        
        # Human-readable feeder display name (e.g. F1 - Wanarathana mawatha or F1 - Kalegana Side)
        f_disp = get_feeder_display_name(fk, lookup=feeder_lookup)
        f_direct_label = get_feeder_direct_name(fk, lookup=feeder_lookup)

        # Consider a phase violating only if rate > 1.0%
        viol_phases = []
        if va_lv > 1.0: viol_phases.append(("Phase A", va_lv))
        if vb_lv > 1.0: viol_phases.append(("Phase B", vb_lv))
        if vc_lv > 1.0: viol_phases.append(("Phase C", vc_lv))
        
        # Sort violating phases by severity descending
        viol_phases.sort(key=lambda x: x[1], reverse=True)
        viol_phase_names = [p[0] for p in viol_phases]
        
        worst_phase_str = viol_phases[0][0] if viol_phases else "—"
        worst_pct = viol_phases[0][1] if viol_phases else 0.0
        
        if len(viol_phases) == 0:
            all_ends_have_lv = False
            cat = "None"
        elif len(viol_phases) == 1:
            cat = "Single-Phase (1 Phase)"
        elif len(viol_phases) == 2:
            cat = "Multi-Phase (2 Phases)"
        else:
            cat = "All Phases (3 Phases)"

        # Check feeder line length or pole count
        f_topo = network_topo.get("feeders", {}).get(fk, {})
        trunk_poles = f_topo.get("trunk_poles_count", 0)
        is_short_feeder = (trunk_poles <= 10)  # Short feeder threshold
        
        # Direct action directive and detailed engineering recommendations
        recs = []
        direct_sol = ""
        if cat == "Single-Phase (1 Phase)":
            aff_phase = viol_phases[0][0]
            healthy_phases = [p for p in ["Phase A", "Phase B", "Phase C"] if p != aff_phase]
            healthy_str = " and ".join(healthy_phases)
            direct_sol = f"Phase balancing in {f_direct_label}, {aff_phase} to other phases"
            
            recs.append({
                "title": f"Phase Load Balancing ({aff_phase} to {healthy_str})",
                "type": "Primary",
                "description": (
                    f"Feeder {f_disp} exhibits localized undervoltage exclusively on {aff_phase} ({worst_pct:.2f}% LV violations), "
                    f"while {healthy_str} remain within statutory limits. Rebalance service connections along the feeder by "
                    f"transferring single-phase customer service drops from {aff_phase} to {healthy_str}. "
                    f"This directly eliminates excessive single-phase neutral and resistive drop without capital expenditure."
                )
            })
        elif cat in ["Multi-Phase (2 Phases)", "All Phases (3 Phases)"]:
            aff_phases_str = ", ".join(viol_phase_names)
            direct_sol = f"Load transfer from {f_direct_label} to adjacent substation / feeder"
            
            recs.append({
                "title": f"Load Transferring to Adjacent Substation / Feeder",
                "type": "Primary",
                "description": (
                    f"Feeder {f_disp} experiences severe voltage depression across {len(viol_phases)} phases ({aff_phases_str}) "
                    f"reaching up to {worst_pct:.2f}% LV violations. Identify lateral spur branches or downstream load clusters "
                    f"and transfer them to a neighboring feeder or adjacent distribution transformer with available capacity."
                )
            })
            if is_short_feeder:
                recs.append({
                    "title": "Construct Express Feeder Direct from Substation",
                    "type": "Secondary",
                    "description": (
                        f"Feeder {f_disp} has a relatively short corridor ({trunk_poles} poles). Constructing an Express Feeder "
                        f"(a dedicated, uninterrupted conductor run from the substation LV bus directly to the load center, "
                        f"bypassing distributed tap-offs) is highly cost-effective and will instantly eliminate end voltage drop."
                    )
                })
            else:
                recs.append({
                    "title": "New Distribution Transformer Installation & Feeder Bifurcation",
                    "type": "Secondary",
                    "description": (
                        f"Feeder {f_disp} spans an extensive radial backbone ({trunk_poles} poles) with heavy multi-phase loading. "
                        f"Install a new 11kV/400V distribution transformer near the midpoint/load center and bifurcate the line "
                        f"to permanently relieve resistive line impedance drop."
                    )
                })
            recs.append({
                "title": "Conductor Augmentation / Reconductoring",
                "type": "Alternative",
                "description": (
                    f"Reconductor undersized backbone spans on Feeder {f_disp} with larger cross-section conductor "
                    f"(e.g., upgrade to 70mm² or 95mm² Aerial Bundled Conductor) to reduce loop resistance (Ω/km)."
                )
            })
        else:
            direct_sol = f"{f_direct_label}: Feeder voltage compliant"
            recs.append({
                "title": "Feeder Voltage Compliant",
                "type": "Informational",
                "description": f"Feeder {f_disp} operates fully within statutory limits (LV violations <= 1.0% across all phases)."
            })
            
        feeder_lv_analysis.append({
            "feeder_key": fk,
            "feeder_display": f_disp,
            "feeder_direct_label": f_direct_label,
            "end_device": end_nick,
            "violating_phases": viol_phase_names,
            "worst_phase": worst_phase_str,
            "worst_phase_pct": worst_pct,
            "violation_category": cat,
            "direct_solution": direct_sol,
            "recommendations": recs
        })

    # System-wide LV condition: Transformer + Feeder Ends have LV violations
    lv_viol_ends_count = sum(1 for f in feeder_lv_analysis if f.get("violation_category", "None") != "None")
    majority_ends_have_lv = (len(feeder_ends) > 0 and (lv_viol_ends_count / len(feeder_ends)) >= 0.50)
    system_wide_lv = (tf_lv_violation and (all_ends_have_lv or majority_ends_have_lv) and len(feeder_ends) > 0)
    system_wide_lv_solutions = []
    
    if system_wide_lv:
        affected_count_str = f"all {len(feeder_ends)}" if all_ends_have_lv else f"{lv_viol_ends_count} of {len(feeder_ends)}"
        system_wide_lv_solutions.append({
            "title": "Cross-Check Upstream 11 kV Primary Substation",
            "type": "Primary",
            "description": (
                f"Both the distribution transformer ({tf_worst_lv:.2f}% LV violations) and {affected_count_str} radial feeder ends "
                f"display simultaneous statutory low voltage. Cross-check voltage logs of adjacent distribution substations connected to the same 11 kV feeder. "
                f"Concurrent undervoltage across multiple substations indicates upstream MV line depression or primary grid transformer tap deviation."
            )
        })
        system_wide_lv_solutions.append({
            "title": "Adjust Transformer Off-Circuit Tap Changer (OCTC) to Higher Position (Tap 3 or 4)",
            "type": "Direct Action",
            "description": (
                "If upstream 11 kV primary voltage is within normal operational range, the secondary voltage baseline is suppressed. "
                "De-energize the transformer and raise the Off-Circuit Tap Changer (OCTC) to a higher position (typically Tap 3 or Tap 4, "
                "providing a +2.5% to +5.0% voltage boost). This will lift the secondary busbar voltage by ~5.7V to 11.5V, "
                "bringing all downstream feeder ends into statutory compliance."
            )
        })

    lv_mitigation = {
        "transformer_lv_violation": tf_lv_violation,
        "transformer_worst_lv_pct": tf_worst_lv,
        "system_wide_lv_issue": system_wide_lv,
        "system_wide_solutions": system_wide_lv_solutions,
        "feeder_analysis": feeder_lv_analysis
    }

    # -------------------------------------------------------------------------
    # STEP 4: HIGH VOLTAGE (HV > 243.8V) MITIGATION ANALYSIS
    # -------------------------------------------------------------------------
    tf_hv_row = hv_summary[hv_summary["Device"] == tf_nick]
    if tf_hv_row.empty:
        tf_hv_row = hv_summary[hv_summary["Role"].astype(str).str.upper().str.contains("TRANS")]
    if tf_hv_row.empty and not hv_summary.empty:
        tf_hv_row = hv_summary.iloc[[0]]

    tf_hv_violation = False
    tf_worst_hv = 0.0
    if not tf_hv_row.empty:
        r = tf_hv_row.iloc[0]
        v_a = float(r.get("Va HV Viol (%)", 0.0))
        v_b = float(r.get("Vb HV Viol (%)", 0.0))
        v_c = float(r.get("Vc HV Viol (%)", 0.0))
        tf_worst_hv = max(v_a, v_b, v_c)
        if tf_worst_hv > 1.0:
            tf_hv_violation = True

    feeder_hv_analysis = []
    all_ends_have_hv = True if feeder_ends else False

    for fk, end_nick in sorted(feeder_ends.items()):
        row = hv_summary[hv_summary["Device"] == end_nick]
        if row.empty:
            meta = feeder_meta.get(end_nick, {})
            db_n = meta.get("db_name", "")
            if db_n:
                row = hv_summary[hv_summary["DB Name"] == db_n]
        if row.empty:
            row = hv_summary[hv_summary["Device"].astype(str).str.strip().str.upper() == str(end_nick).strip().upper()]
        if row.empty:
            continue
        r = row.iloc[0]
        va_hv = float(r.get("Va HV Viol (%)", 0.0))
        vb_hv = float(r.get("Vb HV Viol (%)", 0.0))
        vc_hv = float(r.get("Vc HV Viol (%)", 0.0))
        
        # Human-readable feeder display name (e.g. F1 - Wanarathana mawatha or F1 - Kalegana Side)
        f_disp = get_feeder_display_name(fk, lookup=feeder_lookup)
        f_direct_label = get_feeder_direct_name(fk, lookup=feeder_lookup)

        viol_phases = []
        if va_hv > 1.0: viol_phases.append(("Phase A", va_hv))
        if vb_hv > 1.0: viol_phases.append(("Phase B", vb_hv))
        if vc_hv > 1.0: viol_phases.append(("Phase C", vc_hv))
        
        viol_phases.sort(key=lambda x: x[1], reverse=True)
        viol_phase_names = [p[0] for p in viol_phases]
        
        worst_phase_str = viol_phases[0][0] if viol_phases else "—"
        worst_pct = viol_phases[0][1] if viol_phases else 0.0
        
        f_topo = network_topo.get("feeders", {}).get(fk, {})
        f_solar_kw = float(f_topo.get("total_solar_kw", 0.0))
        has_solar = (f_solar_kw > 0.0)
        
        if len(viol_phases) == 0:
            all_ends_have_hv = False
            cat = "None"
        elif len(viol_phases) == 1:
            cat = "Single-Phase (1 Phase)"
        else:
            cat = "Multi-Phase (2-3 Phases)"

        recs = []
        direct_sol = ""
        
        # Check all three phases to find the absolute worst and lowest phases
        all_phase_tuples = [("Phase A", va_hv), ("Phase B", vb_hv), ("Phase C", vc_hv)]
        all_phase_tuples.sort(key=lambda x: x[1], reverse=True)
        worst_phase_name = all_phase_tuples[0][0]
        worst_phase_val = all_phase_tuples[0][1]
        lowest_phase_name = all_phase_tuples[-1][0]
        lowest_phase_val = all_phase_tuples[-1][1]
        
        # Severe disparity exists when worst phase is >= 2.5% and noticeably higher than the lowest phase
        is_phase_disparity = (
            (worst_phase_val >= 2.5)
            and ((worst_phase_val - lowest_phase_val >= 2.5) or (worst_phase_val >= 1.5 * max(0.5, lowest_phase_val)))
        )

        if cat == "Single-Phase (1 Phase)":
            aff_phase = viol_phases[0][0]
            healthy_phases = [p for p in ["Phase A", "Phase B", "Phase C"] if p != aff_phase]
            healthy_str = " and ".join(healthy_phases)
            target_healthy = healthy_phases[0] if healthy_phases else "Phase A"
            
            direct_sol = (
                f"First, rebalance single-phase solar connections in {f_direct_label} from {aff_phase} to {target_healthy}. "
                f"Second, adjust transformer tap setting (OCTC Tap 1 or 2) if balanced voltage exceeds 243.8 V."
            )
            recs.append({
                "title": f"1. Balance Solar Inverter Connections Across Phases ({aff_phase} to {healthy_str})",
                "type": "Primary (Step 1)",
                "description": (
                    f"Feeder {f_disp} experiences statutory overvoltage exclusively on {aff_phase} ({worst_pct:.2f}% HV violations), "
                    f"while {healthy_str} remain within statutory limits. Single-phase rooftop solar PV inverters are concentrated on {aff_phase}, "
                    f"injecting reverse active power and driving up localized voltage (ΔV ≈ P·R/V). Re-distribute single-phase customer "
                    f"solar inverters from {aff_phase} to {healthy_str} to equalize voltage profiles."
                )
            })
            recs.append({
                "title": "2. Distribution Transformer Tap Adjustment (OCTC)",
                "type": "Primary (Step 2)",
                "description": (
                    f"Once solar customer inverters are balanced across {healthy_str}, inspect the balanced voltage baseline. "
                    f"If midday solar generation keeps the feeder near upper limits, adjust the transformer Off-Circuit Tap Changer "
                    f"to Tap 1 or Tap 2 (-2.5% buck) to bring all three phases comfortably below 243.8 V."
                )
            })
        elif cat == "Multi-Phase (2-3 Phases)":
            aff_phases_str = ", ".join(viol_phase_names)
            
            if is_phase_disparity:
                # Severe inter-phase disparity (e.g. Madawalamulla side Phase B 10.34% vs Phase A 1.89%)
                # Fingerprint of single-phase solar PV inverters clustered on the worst phase
                direct_sol = (
                    f"First, rebalance single-phase solar connections in {f_direct_label} from {worst_phase_name} to {lowest_phase_name}. "
                    f"Second, adjust transformer tap setting (OCTC Tap 1 or 2) to bring all balanced phases safely below 243.8 V."
                )
                recs.append({
                    "title": f"1. Rebalance Solar Inverter Connections ({worst_phase_name} to {lowest_phase_name})",
                    "type": "Primary (Step 1)",
                    "description": (
                        f"Feeder {f_disp} displays severe inter-phase overvoltage disparity: {worst_phase_name} suffers {worst_phase_val:.2f}% HV violations "
                        f"(with peak voltages reaching 250+ V), whereas {lowest_phase_name} remains substantially lower ({lowest_phase_val:.2f}%). "
                        f"This disparity is the classic signature of single-phase rooftop solar PV inverters concentrated heavily on {worst_phase_name}. "
                        f"Re-distribute single-phase customer solar inverters from {worst_phase_name} to {lowest_phase_name} (and healthy phases) "
                        f"so that reverse active power injection is equalized across all three phases, dropping {worst_phase_name} voltage to a uniform, balanced level."
                    )
                })
                recs.append({
                    "title": "2. Adjust Distribution Transformer Off-Circuit Tap Changer (OCTC) to Lower Position",
                    "type": "Primary (Step 2)",
                    "description": (
                        f"Once all three phases are balanced uniformly along {f_disp}, adjust the distribution transformer Off-Circuit Tap Changer (OCTC) "
                        f"to a lower position (Tap 1 or Tap 2, providing a -2.5% to -5.0% voltage reduction / buck). "
                        f"This steps down the baseline secondary voltage across all three balanced phases safely below the 243.8 V statutory limit."
                    )
                })
                if has_solar:
                    recs.append({
                        "title": "Parallel Feedering / Inverter Volt-VAr Controls",
                        "type": "Secondary",
                        "description": (
                            f"If high solar penetration persists after rebalancing, activate inverter Volt-VAr curves (absorbing inductive reactive power) "
                            f"or string a second parallel trunk conductor to halve line loop resistance (R/2)."
                        )
                    })
            elif has_solar:
                # Symmetrical multi-phase solar rise (all phases equally elevated)
                direct_sol = f"Parallel feedering along {f_direct_label} (string 2nd trunk conductor to halve line resistance)"
                recs.append({
                    "title": "Parallel Feedering (Double Circuit Backbone Conductor)",
                    "type": "Primary",
                    "description": (
                        f"Feeder {f_disp} has significant solar penetration ({f_solar_kw:.1f} kW) causing multi-phase solar voltage rise "
                        f"({aff_phases_str} up to {worst_pct:.2f}% HV violations). Heavy reverse solar power flows across high line resistance. "
                        f"Implement **Parallel Feedering** (stringing a second parallel conductor along the main trunk backbone). "
                        f"Halving the line resistance (R/2) directly halves the solar voltage rise (ΔV ≈ P·R/V)."
                    )
                })
                recs.append({
                    "title": "Enforce Inverter Volt-VAr & Volt-Watt Grid Support Curves",
                    "type": "Secondary",
                    "description": (
                        f"Program customer solar inverters (IEEE 1547 / EN 50549 compliant) to activate Volt-VAr mode (absorbing inductive reactive "
                        f"power during midday peak sunshine) and Volt-Watt curtailment as a secondary safeguard against upper statutory violations."
                    )
                })
            else:
                # Symmetrical multi-phase overvoltage without solar
                direct_sol = f"Inspect line voltage regulation and capacitor banks on {f_direct_label}"
                recs.append({
                    "title": "Investigate Feeder Voltage Regulation & Fixed Capacitor Banks",
                    "type": "Primary",
                    "description": (
                        f"Feeder {f_disp} displays multi-phase overvoltage ({aff_phases_str} up to {worst_pct:.2f}% HV violations) without solar generation. "
                        f"Inspect line regulation, disconnected line neutral, or improperly sized power factor correction capacitor banks."
                    )
                })
        else:
            direct_sol = f"{f_direct_label}: Feeder voltage compliant"
            recs.append({
                "title": "Feeder Voltage Compliant",
                "type": "Informational",
                "description": f"Feeder {f_disp} operates fully within statutory limits (HV violations <= 1.0% across all phases)."
            })

        feeder_hv_analysis.append({
            "feeder_key": fk,
            "feeder_display": f_disp,
            "feeder_direct_label": f_direct_label,
            "end_device": end_nick,
            "violating_phases": viol_phase_names,
            "worst_phase": worst_phase_str,
            "worst_phase_pct": worst_pct,
            "has_solar": has_solar,
            "feeder_solar_kw": f_solar_kw,
            "violation_category": cat,
            "direct_solution": direct_sol,
            "recommendations": recs
        })

    # System-wide HV condition: Transformer + Feeder Ends have HV violations
    hv_viol_ends_count = sum(1 for f in feeder_hv_analysis if f.get("violation_category", "None") != "None")
    majority_ends_have_hv = (len(feeder_ends) > 0 and (hv_viol_ends_count / len(feeder_ends)) >= 0.50)
    system_wide_hv = (tf_hv_violation and (all_ends_have_hv or majority_ends_have_hv) and len(feeder_ends) > 0)
    system_wide_hv_solutions = []
    
    if system_wide_hv:
        affected_count_str = f"all {len(feeder_ends)}" if all_ends_have_hv else f"{hv_viol_ends_count} of {len(feeder_ends)}"
        system_wide_hv_solutions.append({
            "title": "Cross-Check Upstream 11 kV Substation Voltage (Nighttime Swell Check)",
            "type": "Primary",
            "description": (
                f"Both the distribution transformer ({tf_worst_hv:.2f}% HV violations) and {affected_count_str} radial feeder ends "
                f"experience concurrent high voltage violations (> 243.8V). "
                f"Check nearby 11 kV distribution transformer readings. If high voltage persists during nighttime or across non-solar substations, "
                f"the primary 11 kV grid voltage is elevated (often due to light grid loading, MV cable capacitive charging, or primary substation AVR setpoint)."
            )
        })
        system_wide_hv_solutions.append({
            "title": "Adjust Transformer Off-Circuit Tap Changer (OCTC) to Lower Position (Tap 1 or 2)",
            "type": "Direct Action",
            "description": (
                "If upstream 11 kV grid voltage is persistently on the higher side, adjust the transformer Off-Circuit Tap Changer (OCTC) "
                "to a lower position (typically Tap 1 or Tap 2, providing a -2.5% to -5.0% voltage reduction). "
                "This steps down secondary voltage into the statutory band (230V ± 6%)."
            )
        })

    hv_mitigation = {
        "transformer_hv_violation": tf_hv_violation,
        "transformer_worst_hv_pct": tf_worst_hv,
        "system_wide_hv_issue": system_wide_hv,
        "system_wide_solutions": system_wide_hv_solutions,
        "feeder_analysis": feeder_hv_analysis
    }

    # -------------------------------------------------------------------------
    # STEP 5: SECTIONAL PROBLEM LOCALIZATION (MIDDLE NMD vs. END NMD)
    # -------------------------------------------------------------------------
    sectional_localizations = []
    
    for fk in sorted(feeder_ends.keys()):
        if fk not in feeder_middles:
            continue
        mid_nick = feeder_middles[fk]
        end_nick = feeder_ends[fk]
        
        # Human-readable feeder display name (e.g. F1 - Wanarathana mawatha or F1 - Kalegana Side)
        f_disp = get_feeder_display_name(fk, lookup=feeder_lookup)

        mid_meta = feeder_meta.get(mid_nick, {})
        end_meta = feeder_meta.get(end_nick, {})
        
        # Pull clean readings or summary metrics
        mid_dev = devices_dict.get(mid_nick, {})
        end_dev = devices_dict.get(end_nick, {})
        
        mid_avg_v = float(mid_dev.get("overall_avg_v", 230.0))
        end_avg_v = float(end_dev.get("overall_avg_v", 230.0))
        outer_delta_v = mid_avg_v - end_avg_v  # Positive = drop between middle and end
        
        mid_lv_row = lv_summary[lv_summary["Device"] == mid_nick]
        end_lv_row = lv_summary[lv_summary["Device"] == end_nick]
        
        mid_lv_pct = 0.0
        if not mid_lv_row.empty:
            r = mid_lv_row.iloc[0]
            mid_lv_pct = max(float(r.get("Va LV Viol (%)", 0)), float(r.get("Vb LV Viol (%)", 0)), float(r.get("Vc LV Viol (%)", 0)))
            
        end_lv_pct = 0.0
        if not end_lv_row.empty:
            r = end_lv_row.iloc[0]
            end_lv_pct = max(float(r.get("Va LV Viol (%)", 0)), float(r.get("Vb LV Viol (%)", 0)), float(r.get("Vc LV Viol (%)", 0)))
            
        mid_hv_row = hv_summary[hv_summary["Device"] == mid_nick]
        end_hv_row = hv_summary[hv_summary["Device"] == end_nick]
        
        mid_hv_pct = 0.0
        if not mid_hv_row.empty:
            r = mid_hv_row.iloc[0]
            mid_hv_pct = max(float(r.get("Va HV Viol (%)", 0)), float(r.get("Vb HV Viol (%)", 0)), float(r.get("Vc HV Viol (%)", 0)))
            
        end_hv_pct = 0.0
        if not end_hv_row.empty:
            r = end_hv_row.iloc[0]
            end_hv_pct = max(float(r.get("Va HV Viol (%)", 0)), float(r.get("Vb HV Viol (%)", 0)), float(r.get("Vc HV Viol (%)", 0)))

        # Localization Logic
        has_mid_issue = (mid_lv_pct > 1.0 or mid_hv_pct > 1.0)
        has_end_issue = (end_lv_pct > 1.0 or end_hv_pct > 1.0)
        
        if not has_mid_issue and has_end_issue:
            problem_segment = "Outer Section (Between Middle NMD and Feeder End)"
            diagnosis = (
                f"Middle NMD ({mid_nick} at Pole {mid_meta.get('pole', 'N/A')}) is compliant (Average: {mid_avg_v:.1f}V, LV: {mid_lv_pct:.2f}%, HV: {mid_hv_pct:.2f}%), "
                f"whereas End NMD ({end_nick} at Pole {end_meta.get('pole', 'N/A')}) violates statutory limits (Average: {end_avg_v:.1f}V, LV: {end_lv_pct:.2f}%, HV: {end_hv_pct:.2f}%). "
                f"The inner trunk from Substation to Middle NMD is healthy and adequately sized. "
                f"The entire excessive voltage drop of {outer_delta_v:.1f}V develops exclusively along the **outer section of Feeder {f_disp} (between {mid_nick} and {end_nick})**."
            )
            action_plan = (
                f"Target engineering interventions (phase balancing, conductor upgrade, or spur deloading) "
                f"exclusively on the outer section of Feeder {f_disp} between Pole {mid_meta.get('pole', 'N/A')} and Pole {end_meta.get('pole', 'N/A')}."
            )
        elif has_mid_issue:
            problem_segment = "Inner Trunk Backbone (Between Substation and Middle NMD)"
            diagnosis = (
                f"Middle NMD ({mid_nick}) already exhibits significant statutory violations (Average: {mid_avg_v:.1f}V, LV: {mid_lv_pct:.2f}%, HV: {mid_hv_pct:.2f}%), "
                f"which persist or worsen at the End NMD ({end_nick}: {end_avg_v:.1f}V, LV: {end_lv_pct:.2f}%). "
                f"The voltage constraint on Feeder {f_disp} originates right in the **inner main backbone between the Substation and Middle NMD**."
            )
            action_plan = (
                f"The entire backbone of Feeder {f_disp} is constrained. Substation tap adjustment, primary riser upgrading, or "
                f"reconductoring the main feeder trunk from the Substation to Pole {mid_meta.get('pole', 'N/A')} is required."
            )
        else:
            problem_segment = "Feeder Section Compliant"
            diagnosis = (
                f"Both Middle NMD ({mid_nick}: {mid_avg_v:.1f}V) and End NMD ({end_nick}: {end_avg_v:.1f}V) on Feeder {f_disp} operate safely "
                f"within statutory tolerance (LV <= 1.0%, HV <= 1.0%). Delta drop is only {outer_delta_v:.1f}V."
            )
            action_plan = "No line modifications required. Continue routine monitoring."

        sectional_localizations.append({
            "feeder_key": fk,
            "feeder_display": f_disp,
            "middle_device": mid_nick,
            "middle_pole": mid_meta.get("pole", "N/A"),
            "end_device": end_nick,
            "end_pole": end_meta.get("pole", "N/A"),
            "middle_avg_v": mid_avg_v,
            "end_avg_v": end_avg_v,
            "outer_delta_v": outer_delta_v,
            "middle_lv_pct": mid_lv_pct,
            "end_lv_pct": end_lv_pct,
            "middle_hv_pct": mid_hv_pct,
            "end_hv_pct": end_hv_pct,
            "problem_segment": problem_segment,
            "diagnosis": diagnosis,
            "action_plan": action_plan
        })

    # -------------------------------------------------------------------------
    # STEP 6: COMPILE MASTER MITIGATION ACTION MATRIX (DATAFRAME)
    # -------------------------------------------------------------------------
    rows = []
    
    # 1. CT Polarity Row
    if not is_ct_normal:
        rows.append({
            "Priority": "P1 - Immediate / Safety",
            "Category": "CT Secondary Wiring",
            "Target Device / Feeder": f"Transformer ({tf_nick})",
            "Observed Problem": f"CT Polarity Inversion ({ct_mode}) on {', '.join(ct_solution['affected_phases'])}",
            "Affected Phase(s)": ", ".join(ct_solution["affected_phases"]),
            "Primary Recommended Action": ct_solution["solution_title"],
            "Secondary Options / Alternatives": "Re-run NMD load audit post-rectification",
            "Target Location": "Substation NMD Secondary Terminal Block"
        })
        
    # 2. Hardware Alerts (e.g. 0V lead)
    for alert in all_hw_alerts:
        rows.append({
            "Priority": "P1 - Immediate / Metering",
            "Category": "NMD Sensor Hardware",
            "Target Device / Feeder": alert.get("device", "NMD"),
            "Observed Problem": f"Persistent Sensor Defect on {alert.get('phase', 'Phase')} (100% 0V readings)",
            "Affected Phase(s)": alert.get("phase", "Phase"),
            "Primary Recommended Action": "Reconnect Voltage Sensing Lead / Replace VT Fuse",
            "Secondary Options / Alternatives": "Check transducer channel & alligator clip continuity",
            "Target Location": f"{alert.get('device', 'NMD')} Installation Pole"
        })

    # 3. Transformer Loading Row
    if not is_ct_normal:
        rows.append({
            "Priority": "P2 - Capacity Assessment",
            "Category": "Substation Capacity",
            "Target Device / Feeder": f"Transformer ({tf_nick})",
            "Observed Problem": "Loading Assessment Blocked by CT Inversion",
            "Affected Phase(s)": "All Phases",
            "Primary Recommended Action": "Deferred pending CT lead swap",
            "Secondary Options / Alternatives": "Verify CT secondary polarity first",
            "Target Location": f"Substation ({tf_nick})"
        })
    elif transformer_solution["is_overloaded"]:
        rows.append({
            "Priority": "P2 - Substation Overload",
            "Category": "Transformer Capacity",
            "Target Device / Feeder": f"Transformer ({tf_nick})",
            "Observed Problem": f"Substation Overloaded on Average Demand Curve at {avg_peak_pct:.1f}% ({avg_peak_kva:.1f} kVA of {rated_cap:.0f} kVA at {avg_peak_time})",
            "Affected Phase(s)": "Composite 3-Phase",
            "Primary Recommended Action": transformer_solution["recommendations"][0]["title"],
            "Secondary Options / Alternatives": transformer_solution["recommendations"][1]["title"] if len(transformer_solution["recommendations"]) > 1 else "Load shed",
            "Target Location": f"Substation ({tf_nick})"
        })

    # 4. System-Wide Voltage Rows
    if system_wide_lv:
        rows.append({
            "Priority": "P2 - Statutory Voltage",
            "Category": "System-Wide LV Mitigation",
            "Target Device / Feeder": f"All Feeders & Transformer ({tf_nick})",
            "Observed Problem": f"Concurrent System-Wide Undervoltage (Transformer LV: {tf_worst_lv:.1f}%)",
            "Affected Phase(s)": "System-Wide",
            "Primary Recommended Action": "Cross-Check 11kV Substation; Raise Transformer Tap to Tap 3 or 4",
            "Secondary Options / Alternatives": "Inspect 11kV Grid Substation AVR setpoints",
            "Target Location": f"Distribution Transformer Off-Circuit Tap Changer"
        })
        
    if system_wide_hv:
        rows.append({
            "Priority": "P2 - Statutory Voltage",
            "Category": "System-Wide HV Mitigation",
            "Target Device / Feeder": f"All Feeders & Transformer ({tf_nick})",
            "Observed Problem": f"Concurrent System-Wide Overvoltage (Transformer HV: {tf_worst_hv:.1f}%)",
            "Affected Phase(s)": "System-Wide",
            "Primary Recommended Action": "Cross-Check 11kV Grid; Lower Transformer Tap to Tap 1 or 2",
            "Secondary Options / Alternatives": "Investigate light-load grid voltage swell",
            "Target Location": f"Distribution Transformer Off-Circuit Tap Changer"
        })

    # 5. Feeder-Specific LV Rows
    for fa in feeder_lv_analysis:
        if fa.get("violation_category", "None") != "None":
            prio = "P2 - Statutory Compliance" if fa.get("worst_phase_pct", 0.0) > 15.0 else "P3 - Operational Improvement"
            recs = fa.get("recommendations", [])
            prim = fa.get("direct_solution") or (recs[0]["title"] if recs else "Mitigate LV")
            sec = recs[1]["title"] if len(recs) > 1 else "Conductor augmentation"
            
            f_disp = fa.get("feeder_display") or get_feeder_display_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            # Determine target location from sectional localization if available
            target_loc = f"Feeder {f_disp} Backbone"
            for sec_loc in sectional_localizations:
                if sec_loc.get("feeder_key") == fa.get("feeder_key"):
                    if "Outer Section" in sec_loc.get("problem_segment", ""):
                        target_loc = f"Outer Section of Feeder {f_disp} ({sec_loc.get('middle_pole')} to {sec_loc.get('end_pole')})"
                    elif "Inner Trunk" in sec_loc.get("problem_segment", ""):
                        target_loc = f"Inner Backbone of Feeder {f_disp} (Substation to {sec_loc.get('middle_pole')})"
                    break
                    
            rows.append({
                "Priority": prio,
                "Category": "Feeder Low Voltage (LV)",
                "Target Device / Feeder": f"Feeder {f_disp} ({fa.get('end_device', '')})",
                "Observed Problem": f"{fa.get('violation_category', '')} Undervoltage ({fa.get('worst_phase', '—')} worst: {fa.get('worst_phase_pct', 0.0):.2f}%)",
                "Affected Phase(s)": ", ".join(fa.get("violating_phases", [])),
                "Primary Recommended Action": prim,
                "Secondary Options / Alternatives": sec,
                "Target Location": target_loc
            })

    # 6. Feeder-Specific HV Rows
    for fa in feeder_hv_analysis:
        if fa.get("violation_category", "None") != "None":
            prio = "P3 - Power Quality / Solar"
            recs = fa.get("recommendations", [])
            prim = fa.get("direct_solution") or (recs[0]["title"] if recs else "Mitigate HV")
            sec = recs[1]["title"] if len(recs) > 1 else "Inverter Volt-VAr control"
            
            f_disp = fa.get("feeder_display") or get_feeder_display_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            rows.append({
                "Priority": prio,
                "Category": "Feeder High Voltage (HV)",
                "Target Device / Feeder": f"Feeder {f_disp} ({fa.get('end_device', '')})",
                "Observed Problem": f"{fa.get('violation_category', '')} Overvoltage ({fa.get('worst_phase', '—')} worst: {fa.get('worst_phase_pct', 0.0):.2f}%)",
                "Affected Phase(s)": ", ".join(fa.get("violating_phases", [])),
                "Primary Recommended Action": prim,
                "Secondary Options / Alternatives": sec,
                "Target Location": f"Feeder {f_disp} Solar Customer Connections"
            })

    # 7. Sectional Localizations Summary Rows
    for sl in sectional_localizations:
        if "Compliant" not in sl.get("problem_segment", ""):
            sl_disp = sl.get("feeder_display") or get_feeder_display_name(sl.get("feeder_key", ""), lookup=feeder_lookup)
            rows.append({
                "Priority": "P3 - Segmental Targeting",
                "Category": "Sectional Localization",
                "Target Device / Feeder": f"Feeder {sl_disp}: {sl.get('middle_device', '')} ➔ {sl.get('end_device', '')}",
                "Observed Problem": f"Sectional Voltage Drop ΔV = {sl.get('outer_delta_v', 0.0):.1f}V",
                "Affected Phase(s)": "Feeder Line Segment",
                "Primary Recommended Action": sl.get("action_plan", ""),
                "Secondary Options / Alternatives": "Targeted line reconductoring / deloading",
                "Target Location": sl.get("problem_segment", "")
            })

    df_action_matrix = pd.DataFrame(rows)

    # -------------------------------------------------------------------------
    # STEP 7: COMPILE DIRECT ENGINEERING ACTION DIRECTIVES
    # -------------------------------------------------------------------------
    direct_solutions = []

    # Priority 1: CT Polarity Correction
    if not is_ct_normal:
        phases_str = ", ".join(ct_solution.get("affected_phases", []))
        direct_solutions.append({
            "action_type": "CT Polarity Wiring Correction",
            "priority": "P1 - Critical",
            "icon": "🚨",
            "direct_solution": f"Correct physical CT polarity wiring on {phases_str} at Substation ({tf_nick})",
            "details": f"Inverted CT secondary leads ({ct_mode}) corrupt directional power calculations and block accurate overload assessment. Swap S1/S2 leads at NMD secondary terminal block.",
            "target": f"Substation ({tf_nick})"
        })

    # Priority 1: Metering / Sensor Hardware Defects
    for alert in all_hw_alerts:
        dev_label = alert.get("device", "NMD")
        dev_meta = feeder_meta.get(dev_label, {})
        fk_dev = dev_meta.get("feeder_key", "")
        if fk_dev:
            target_name = get_feeder_direct_name(fk_dev, lookup=feeder_lookup)
        else:
            target_name = dev_label
        direct_solutions.append({
            "action_type": "Voltage Sensor Lead Reconnection",
            "priority": "P1 - Critical",
            "icon": "🔧",
            "direct_solution": f"Reconnect disconnected voltage sensor lead on {target_name}, {alert.get('phase', 'Phase')}",
            "details": "Continuous 0.0V readings indicate detached PT crocodile test clip, blown internal fuse, or open sensor circuit.",
            "target": target_name
        })

    # Priority 2: Transformer Overload
    if is_ct_normal and transformer_solution.get("is_overloaded", False):
        standard_ratings = [50.0, 100.0, 160.0, 250.0, 400.0, 630.0, 1000.0]
        next_rating_val = next((r for r in standard_ratings if r > avg_peak_kva * 1.25), rated_cap * 1.5)
        direct_solutions.append({
            "action_type": "Substation Augmentation / Capacity Upgrade",
            "priority": "P2 - High",
            "icon": "⚡",
            "direct_solution": f"Substation augmentation: upgrade transformer from {rated_cap:.0f} kVA to {next_rating_val:.0f} kVA (or install new deloading substation)",
            "details": f"Representative 24-hour average peak demand reached {avg_peak_kva:.1f} kVA ({avg_peak_pct:.1f}% loading) at {avg_peak_time} against rated capacity of {rated_cap:.0f} kVA.",
            "target": f"Substation ({tf_nick})"
        })

    # Priority 2: System-Wide Low Voltage (Concurrent Transformer + Feeder Ends LV)
    if system_wide_lv:
        direct_solutions.append({
            "action_type": "Transformer Tap Changer Adjustment (Boost)",
            "priority": "P2 - High",
            "icon": "⚙️",
            "direct_solution": "Adjust Transformer Tap Changer (OCTC) to Tap 3 or Tap 4 (+2.5% to +5.0% boost) & cross-check upstream 11 kV grid",
            "details": f"Concurrent undervoltage detected at transformer secondary busbar ({tf_worst_lv:.1f}%) and feeder ends. Adjusting OCTC elevates secondary 400V/230V baseline by ~5.7V to 11.5V.",
            "target": f"Transformer ({tf_nick}) Tap Changer"
        })

    # Priority 2: System-Wide High Voltage (Concurrent Transformer + Feeder Ends HV)
    if system_wide_hv:
        direct_solutions.append({
            "action_type": "Transformer Tap Changer Adjustment (Buck)",
            "priority": "P2 - High",
            "icon": "⚙️",
            "direct_solution": "Adjust Transformer Tap Changer (OCTC) to Tap 1 or Tap 2 (-2.5% to -5.0% buck) & cross-check upstream 11 kV grid",
            "details": f"Concurrent overvoltage detected at transformer secondary busbar ({tf_worst_hv:.1f}%) and feeder ends. Steps down secondary voltage baseline into statutory band (230V ± 6%).",
            "target": f"Transformer ({tf_nick}) Tap Changer"
        })

    # Priority 2 / 3: Feeder Low Voltage Mitigations (Load Transfer vs. Phase Balancing)
    for fa in feeder_lv_analysis:
        if fa.get("violation_category", "None") != "None":
            f_direct_label = fa.get("feeder_direct_label") or get_feeder_direct_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            worst_p = fa.get("worst_phase", "—")
            worst_pct_val = fa.get("worst_phase_pct", 0.0)
            prio = "P2 - High" if worst_pct_val > 10.0 else "P3 - Medium"
            
            if fa.get("violation_category") == "Single-Phase (1 Phase)":
                act_text = f"Phase balancing in {f_direct_label}, {worst_p} to other phases"
                det = f"Localized undervoltage exclusively on {worst_p} ({worst_pct_val:.2f}%). Transfer single-phase customer service drops from {worst_p} to healthy phases to eliminate resistive unbalance."
                icon_s = "⚖️"
                act_cat = "Feeder Phase Balancing"
            else:
                act_text = f"Load transfer from {f_direct_label} to adjacent substation / feeder"
                viol_str = ", ".join(fa.get("violating_phases", []))
                det = f"Multi-phase undervoltage across {viol_str} (Worst: {worst_p} at {worst_pct_val:.2f}%). Transfer lateral spur branches or downstream load clusters to deload the feeder."
                icon_s = "🔄"
                act_cat = "Feeder Load Transfer"
                
            direct_solutions.append({
                "action_type": act_cat,
                "priority": prio,
                "icon": icon_s,
                "direct_solution": act_text,
                "details": det,
                "target": f_direct_label
            })

    # Priority 3: Feeder High Voltage Mitigations
    for fa in feeder_hv_analysis:
        if fa.get("violation_category", "None") != "None":
            f_direct_label = fa.get("feeder_direct_label") or get_feeder_direct_name(fa.get("feeder_key", ""), lookup=feeder_lookup)
            worst_p = fa.get("worst_phase", "—")
            worst_pct_val = fa.get("worst_phase_pct", 0.0)
            act_text = fa.get("direct_solution", "")
            recs_list = fa.get("recommendations", [])
            
            # Extract detailed description from recommendations
            det = recs_list[0].get("description", "") if recs_list else ""
            if not det:
                det = f"High voltage violations ({worst_pct_val:.2f}% on {worst_p}) require solar inverter rebalancing and tap optimization."
            
            if "rebalance" in act_text.lower():
                icon_s = "☀️"
                act_cat = "Solar Inverter Balancing & Tap Adjustment"
            elif "parallel" in act_text.lower():
                icon_s = "⚡"
                act_cat = "Parallel Feedering"
            else:
                icon_s = "🔍"
                act_cat = "Voltage Regulation Inspection"
                    
            direct_solutions.append({
                "action_type": act_cat,
                "priority": "P2 - High" if worst_pct_val > 10.0 else "P3 - Medium",
                "icon": icon_s,
                "direct_solution": act_text,
                "details": det,
                "target": f_direct_label
            })

    # Default if everything is compliant
    if not direct_solutions:
        direct_solutions.append({
            "action_type": "Routine Monitoring",
            "priority": "P3 - Optimal",
            "icon": "🟢",
            "direct_solution": "All feeders and substation operate within statutory limits (No physical intervention required)",
            "details": "CT polarity normal, transformer loading within nameplate capacity, and all feeder voltages strictly compliant (<= 1.0% statutory violations).",
            "target": "Network Overall"
        })
    
    # Generate executive advisory summary markdown
    exec_lines = []
    if not is_ct_normal:
        exec_lines.append(
            f"⚠️ **CRITICAL PRIORITY: CT Polarity Reversal Detected**: "
            f"The NMD installation operates with inverted CT wiring ({ct_mode}) on {', '.join(ct_solution['affected_phases'])}. "
            f"Because active and reactive power directions are corrupted, **transformer overloading cannot be determined**. "
            f"Swapping the physical CT secondary leads is the prerequisite before any capacity or power flow assessment."
        )
    elif transformer_solution["is_overloaded"]:
        exec_lines.append(
            f"⚡ **TRANSFORMER OVERLOAD ALERT (AVERAGE DEMAND)**: Representative 24-hour average demand curve peaks at "
            f"{avg_peak_kva:.1f} kVA ({avg_peak_pct:.1f}% of {rated_cap:.0f} kVA at {avg_peak_time}). "
            f"Augmentation to higher capacity or new substation installation is required."
        )
    else:
        exec_lines.append(
            f"✅ **Substation Baseline Normal (Average Demand Baseline)**: CT polarities verified (100% confidence), and transformer average demand "
            f"is safe at {avg_peak_pct:.1f}% loading ({avg_peak_kva:.1f} kVA of {rated_cap:.0f} kVA, {headroom_kva:.1f} kVA reserve headroom). Transformer is not overloaded."
        )

    if all_hw_alerts:
        for alert in all_hw_alerts:
            exec_lines.append(f"🔧 **HARDWARE ALERT**: Sensor defect on {alert['device']} {alert['phase']}. Reconnect sensing lead.")

    # High-level LV finding
    severe_lv_feeders = [f.get("feeder_display") or f.get("feeder_key", "") for f in feeder_lv_analysis if f.get("worst_phase_pct", 0.0) > 1.0]
    if severe_lv_feeders:
        exec_lines.append(
            f"📉 **Statutory Undervoltage Identified**: Feeder(s) {', '.join(severe_lv_feeders)} experience low voltage violations. "
            f"Phase balancing and feeder load transferring are the primary recommended mitigations."
        )

    # High-level HV finding
    hv_feeders = [f.get("feeder_display") or f.get("feeder_key", "") for f in feeder_hv_analysis if f.get("violation_category", "None") != "None"]
    if hv_feeders:
        exec_lines.append(
            f"☀️ **Solar Voltage Rise Identified**: Feeder(s) {', '.join(hv_feeders)} experience midday solar voltage rise. "
            f"Solar customer phase rebalancing and parallel feedering are recommended."
        )

    return {
        "status": "success",
        "executive_summary_text": "\n\n".join(exec_lines),
        "ct_solution": ct_solution,
        "transformer_solution": transformer_solution,
        "lv_mitigation": lv_mitigation,
        "hv_mitigation": hv_mitigation,
        "sectional_localizations": sectional_localizations,
        "action_matrix_df": df_action_matrix,
        "direct_solutions": direct_solutions,
        "direct_solutions_summary": [s["direct_solution"] for s in direct_solutions]
    }

