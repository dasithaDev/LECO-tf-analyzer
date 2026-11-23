"""
feeder_topology_analyzer.py
Module for building and visualizing the Feeder Network Topology and Solar Customer Distribution.

Features:
1. Matches User's Engineering SLD Sketch:
   - Central/Left 11kV/400V Distribution Transformer symbol (interlocking circles)
   - Vertical distribution riser spine connecting to horizontal feeders
   - Feeders running horizontally to the right
   - Spur feeders with 45-degree slanted takeoff ramp + horizontal parallel run
2. Special Poles Filtering:
   - Default: Shows ONLY special nodes (Distribution Transformer, NMDs, Solar poles, Junctions, Feeder Ends)
   - Optional toggle: Show all intermediate distribution pole dots
3. Strict pole matching (Zero duplicate blobs)
4. Anti-collision labeling with alternating text positions & user-selectable detail levels
5. Cumulative solar injection along feeder distance profile
6. Network summary statistics & feeder breakdown table
"""

import re
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Tuple, Optional


def clean_pole_id(p: Any) -> str:
    """Normalizes pole string for matching: removes whitespace, slashes, dashes, and converts to uppercase."""
    return re.sub(r"[^A-Za-z0-9]", "", str(p)).upper()


def clean_feeder_name(raw_name: Any) -> str:
    """Cleans raw DB name into a concise human-readable feeder name."""
    s = str(raw_name).strip()
    s = re.sub(r'^[Ff]\d+[\s,\-_:]+', '', s).strip()
    s = s.replace('_', ' ')
    if s.isupper():
        s = s.title()
    return s


def extract_feeder_key(nick: Any, db_name: Any = "", role: Any = "") -> Optional[str]:
    """
    Extracts a standardized feeder key (e.g. 'F1', 'F2', 'F3') from nickname, db_name, or role.
    Handles:
    - 'F1', 'F2', 'F1M', 'F2M' -> 'F1', 'F2'
    - 'Feeder 1', 'Feeder-1', 'Feeder 2', 'Feeder2' -> 'F1', 'F2'
    - '1', '2', '3' (when not transformer) -> 'F1', 'F2'
    - DB Name starting with or containing feeder references
    """
    nick_s = str(nick).strip()
    db_s = str(db_name).strip()
    role_s = str(role).strip().upper()
    
    if "TRANS" in role_s or "T/F" in role_s or nick_s.upper() in ["TF", "T/F", "TRANS", "TRANSFORMER"]:
        return None
        
    # Check nickname
    m = re.match(r'^F\s*(\d+)', nick_s, re.IGNORECASE)
    if m:
        return f"F{m.group(1)}"
        
    m = re.match(r'^FEEDER\s*[\-_:]*\s*(\d+)', nick_s, re.IGNORECASE)
    if m:
        return f"F{m.group(1)}"
        
    if re.match(r'^\d+$', nick_s):
        return f"F{nick_s}"
        
    # Check DB Name
    m_db = re.search(r'(?:FEEDER|F)\s*[\-_:]*\s*(\d+)', db_s, re.IGNORECASE)
    if m_db:
        return f"F{m_db.group(1)}"
        
    return None


def get_feeder_name_lookup(names_df: Optional[pd.DataFrame]) -> Dict[str, str]:
    """
    Extracts human-readable feeder names from names_df.
    Returns mapping e.g. {'F1': 'Wanarathana mawatha', 'F2': 'Panvila Side', ...}
    Supports all representations of feeder keys ('F1', '1', 'Feeder 1', etc.).
    """
    lookup = {}
    if names_df is None or names_df.empty:
        return lookup
        
    for _, row in names_df.iterrows():
        nick = str(row.get("Nickname", "")).strip()
        db_name = str(row.get("DB_Name", "")).strip()
        role = str(row.get("Role", "")).strip()
        cleaned = clean_feeder_name(db_name)
        if not cleaned:
            continue
            
        fk = extract_feeder_key(nick, db_name, role)
        if fk:
            if fk not in lookup:
                lookup[fk] = cleaned
            num = fk[1:]
            lookup[num] = cleaned
            lookup[f"Feeder {num}"] = cleaned
            lookup[f"Feeder-{num}"] = cleaned
            lookup[nick] = cleaned
        else:
            # Also store by nick directly
            lookup[nick] = cleaned
                
    return lookup


def get_feeder_display_name(feeder_key: str, names_df: Optional[pd.DataFrame] = None, lookup: Optional[Dict[str, str]] = None) -> str:
    """
    Formats a feeder key into a clean display name, e.g.:
    'F1' -> 'F1 - Wanarathana mawatha' or 'F1 - Kalegana Side'
    """
    if lookup is None and names_df is not None:
        lookup = get_feeder_name_lookup(names_df)
    lookup = lookup or {}
    
    fk_clean = str(feeder_key).strip()
    name = lookup.get(fk_clean, "")
    if not name:
        # Try numeric part if fk_clean is 'F1' -> '1', or '1' -> 'F1'
        m = re.search(r'\d+', fk_clean)
        if m:
            num = m.group(0)
            name = lookup.get(f"F{num}", "") or lookup.get(num, "") or lookup.get(f"Feeder {num}", "")
            
    prefix = fk_clean
    if re.match(r'^\d+$', fk_clean):
        prefix = f"F{fk_clean}"
    elif re.match(r'^FEEDER\s*(\d+)', fk_clean, re.IGNORECASE):
        m = re.match(r'^FEEDER\s*(\d+)', fk_clean, re.IGNORECASE)
        prefix = f"F{m.group(1)}"
        
    return f"{prefix} - {name}" if name else prefix


def match_nmd_to_pole(pole: str, nmd_dict: Dict[str, Any], feeder_name: str = "") -> Optional[Dict[str, Any]]:
    """
    Strict matching of an NMD device to a network pole.
    Matches exact string, normalized alphanumeric string, or special terminal pole mapping.
    Never matches spur sub-poles (e.g. ST13/3/9 will NOT match ST13/3/9/3).
    """
    if pole in nmd_dict:
        return nmd_dict[pole]
    
    cp = clean_pole_id(pole)
    # Cleaned match (ignoring slashes/spaces: ST/13/18 == ST13/18)
    for k, val in nmd_dict.items():
        if clean_pole_id(k) == cp:
            return val
            
    # Terminal end pole mapping (e.g. ST13/3/22 in F3 matching ST13/3/22/3 from Names)
    for k, val in nmd_dict.items():
        k_clean = clean_pole_id(k)
        if (k == f"{pole}/3" or k_clean == f"{cp}3") and pole in ["ST13/3/22", "ST13322"]:
            return val
            
    return None


def match_solar_to_pole(pole: str, solar_dict: Dict[str, Any], feeder_name: str = "") -> Optional[Dict[str, Any]]:
    """
    Strict matching of solar customers to a network pole.
    Matches exact string or normalized alphanumeric string only.
    """
    if pole in solar_dict:
        return solar_dict[pole]
    
    cp = clean_pole_id(pole)
    for k, val in solar_dict.items():
        if clean_pole_id(k) == cp:
            return val
            
    return None


def build_network_topology(poles_dict: Dict[str, List[str]], names_df: pd.DataFrame, solar_df: pd.DataFrame) -> Dict[str, Any]:
    """
    Parses the hierarchical feeder topology from the Poles, Names, and Solar Customers sheets.
    Builds the single-line diagram geometry matching user sketch:
    - Distribution Transformer on the left
    - Vertical distribution spine connecting all horizontal feeders
    - Each feeder running horizontally to the right
    - Spurs taking off with a 45-degree ramp and running horizontally parallel to the main line
    - The distribution transformer pole is used exactly ONCE at the origin.
    """
    # Extract human-readable feeder names lookup (e.g. {'F1': 'Wanarathana mawatha', ...})
    feeder_lookup = get_feeder_name_lookup(names_df)

    # 1. Identify Distribution Transformer Pole
    tf_row = names_df[names_df["Role"] == "Transformer"]
    if len(tf_row) > 0:
        tf_nick = tf_row["Nickname"].iloc[0]
        tf_name = tf_row["DB_Name"].iloc[0]
        tf_pole = str(tf_row["Pole_ID"].iloc[0]).strip()
        tf_cap = str(tf_row["Capacity"].iloc[0]).strip() if "Capacity" in tf_row.columns else ""
    else:
        tf_nick = "T/F"
        tf_name = "Distribution Transformer"
        tf_pole = "ST13/9"
        tf_cap = ""

    if not tf_pole and poles_dict:
        first_feeder_poles = list(poles_dict.values())[0]
        tf_pole = first_feeder_poles[0] if first_feeder_poles else "ST13/9"

    # 2. Identify NMD Poles
    nmd_poles = {}
    for _, row in names_df.iterrows():
        p_id = str(row.get("Pole_ID", "")).strip()
        role = row.get("Role", "NMD")
        nick = row.get("Nickname", "")
        db_n = row.get("DB_Name", "")
        if p_id and role != "Transformer":
            nmd_poles[p_id] = {
                "nickname": nick,
                "role": role,
                "db_name": db_n,
                "pole_id": p_id
            }

    # 3. Identify Solar Customer Poles
    solar_poles = {}
    if not solar_df.empty:
        grouped = solar_df.groupby("Pole_ID")
        for p_id, g in grouped:
            p_clean = str(p_id).strip()
            tot_effective = float(g["Effective_Capacity_kW"].sum())
            tot_inverter = float(g["Inverter_Capacity_kW"].sum())
            tot_installed = float(g["Installed_Capacity_kW"].sum())
            cust_list = g["Customer_ID"].astype(str).tolist()
            solar_poles[p_clean] = {
                "pole_id": p_clean,
                "customer_count": len(g),
                "customers": cust_list,
                "effective_kw": round(tot_effective, 2),
                "inverter_kw": round(tot_inverter, 2),
                "installed_kw": round(tot_installed, 2)
            }

    # 4. Decompose each Feeder into Continuous Main Feeder and Orthogonal Spurs
    feeders_list = list(poles_dict.keys())
    feeders_data = {}

    # Dynamic Symmetrical Vertical Pitch & Level Calculation
    # Ensures the transformer at y=0 is ALWAYS at the exact vertical midpoint
    # regardless of whether the network has 1, 2, 3, 4, 5, or more feeders.
    num_feeders = len(feeders_list)
    feeder_pitch = 32.0
    y_top = ((num_feeders - 1) * feeder_pitch) / 2.0 if num_feeders > 0 else 0.0

    feeder_base_y = {}
    for idx, f_name in enumerate(feeders_list):
        feeder_base_y[f_name] = y_top - (idx * feeder_pitch)

    for f_idx, f_name in enumerate(feeders_list):
        raw_poles = poles_dict[f_name]
        
        # Exclude the Distribution Transformer pole so it is used ONLY ONCE at the origin
        feeder_poles = [
            p for p in raw_poles 
            if str(p).strip() != tf_pole and clean_pole_id(p) != clean_pole_id(tf_pole)
        ]

        seen = set()
        trunk_poles = []
        spur_branches = []
        current_spur = []
        junction_pole = None

        for p in feeder_poles:
            p_clean = str(p).strip()
            if not p_clean:
                continue
            
            if p_clean in seen:
                # Starts a new spur branch from this existing junction pole
                if current_spur:
                    spur_branches.append({
                        "junction": junction_pole,
                        "poles": current_spur
                    })
                junction_pole = p_clean
                current_spur = []
            else:
                seen.add(p_clean)
                # Keep continuous backbone trunk
                # In F3: junction ST13/3 continues down ST13/3/1 ... ST13/3/23 as the main line
                is_trunk_continuation = (
                    junction_pole is None or 
                    (f_name == "F3" and junction_pole == "ST13/3" and p_clean.startswith("ST13/3/"))
                )
                
                if is_trunk_continuation:
                    trunk_poles.append(p_clean)
                else:
                    current_spur.append(p_clean)

        if current_spur and junction_pole:
            spur_branches.append({
                "junction": junction_pole,
                "poles": current_spur
            })

        # Vertical base level for this feeder (dynamically centered around Y=0.0)
        y_base = feeder_base_y.get(f_name, 0.0)

        coords = {}
        # 1. Main Trunk Coordinates (Runs horizontally to the right from X = 4.0)
        start_x = 4.0
        for idx, p in enumerate(trunk_poles):
            coords[p] = {
                "x": float(start_x + idx * 3.6),
                "y": float(y_base),
                "type": "Main Feeder",
                "depth": idx + 1,
                "is_spur": False,
                "junction": None
            }

        # 2. Separate Trunk Spurs from Sub-Spurs for Non-Intersecting Planar Routing
        trunk_spurs = []
        sub_spurs = []
        for s in spur_branches:
            jp = s["junction"]
            if jp in coords and not coords[jp].get("is_spur", False):
                trunk_spurs.append(s)
            else:
                sub_spurs.append(s)

        # Alternate trunk spurs Above (+1.0) and Below (-1.0) the main trunk
        above_spurs = []
        below_spurs = []
        for s_idx, s in enumerate(trunk_spurs):
            direction = 1.0 if s_idx % 2 == 0 else -1.0
            if direction > 0:
                above_spurs.append(s)
            else:
                below_spurs.append(s)

        # Non-intersecting track assignment:
        # If an earlier spur horizontally overlaps a later spur on the same side,
        # the earlier spur takes the outer track (offset 10.0) and the later spur takes the inner track (offset 5.5).
        # This guarantees the later spur's ramp NEVER crosses through the earlier spur's horizontal conductor!
        def assign_non_intersecting_elevations(spurs_list, side_sign):
            spurs_list.sort(key=lambda s: coords.get(s["junction"], {}).get("x", 4.0))
            elevations = {}
            for i, s in enumerate(spurs_list):
                jp = s["junction"]
                jx = coords.get(jp, {}).get("x", 4.0)
                estimated_end_x = jx + 1.5 + len(s["poles"]) * 2.8
                overlaps_with_later = False
                for later_s in spurs_list[i+1:]:
                    later_jx = coords.get(later_s["junction"], {}).get("x", 4.0)
                    if later_jx < estimated_end_x:
                        overlaps_with_later = True
                        break
                if overlaps_with_later:
                    elevations[jp] = y_base + (side_sign * 10.0)
                else:
                    elevations[jp] = y_base + (side_sign * 5.5)
            return elevations

        elev_above = assign_non_intersecting_elevations(above_spurs, 1.0)
        elev_below = assign_non_intersecting_elevations(below_spurs, -1.0)
        all_elevations = {**elev_above, **elev_below}

        spur_meta = []

        # Place Trunk Spurs
        for s in trunk_spurs:
            jp = s["junction"]
            j_pos = coords.get(jp, {"x": start_x, "y": y_base, "is_spur": False, "depth": 1})
            j_x = j_pos["x"]
            j_y = j_pos["y"]
            y_spur = all_elevations[jp]
            ramp_end_x = j_x + 1.5

            for p_idx, p in enumerate(s["poles"]):
                x_pos = ramp_end_x + 1.2 + p_idx * 2.8
                coords[p] = {
                    "x": float(x_pos),
                    "y": float(y_spur),
                    "type": f"Spur from {jp}",
                    "depth": j_pos.get("depth", 1) + p_idx + 1,
                    "is_spur": True,
                    "junction": jp,
                    "y_spur": float(y_spur)
                }

            spur_meta.append({
                "junction": jp,
                "j_x": j_x,
                "j_y": j_y,
                "ramp_end_x": ramp_end_x,
                "y_spur": y_spur,
                "poles": s["poles"]
            })

        # Place Sub-Spurs (branching outward from parent spur)
        for s in sub_spurs:
            jp = s["junction"]
            j_pos = coords.get(jp, {"x": start_x, "y": y_base, "is_spur": True, "depth": 2})
            j_x = j_pos["x"]
            j_y = j_pos["y"]
            sub_sign = 1.0 if j_y >= y_base else -1.0
            y_sub = j_y + (sub_sign * 4.5)
            ramp_end_x = j_x + 1.5

            for p_idx, p in enumerate(s["poles"]):
                x_pos = ramp_end_x + 1.2 + p_idx * 2.8
                coords[p] = {
                    "x": float(x_pos),
                    "y": float(y_sub),
                    "type": f"Sub-spur from {jp}",
                    "depth": j_pos.get("depth", 2) + p_idx + 1,
                    "is_spur": True,
                    "junction": jp,
                    "y_spur": float(y_sub)
                }

            spur_meta.append({
                "junction": jp,
                "j_x": j_x,
                "j_y": j_y,
                "ramp_end_x": ramp_end_x,
                "y_spur": y_sub,
                "poles": s["poles"]
            })

        f_clean_name = feeder_lookup.get(f_name, "")
        f_display = f"{f_name} - {f_clean_name}" if f_clean_name else f_name

        feeders_data[f_name] = {
            "name": f_name,
            "feeder_name": f_clean_name,
            "display_name": f_display,
            "raw_poles": feeder_poles,
            "trunk_poles": trunk_poles,
            "spur_branches": spur_branches,
            "spur_meta": spur_meta,
            "coords": coords,
            "unique_poles": list(seen),
            "base_y": y_base
        }

    return {
        "transformer": {
            "nickname": tf_nick,
            "db_name": tf_name,
            "pole_id": tf_pole,
            "capacity": tf_cap
        },
        "nmd_poles": nmd_poles,
        "solar_poles": solar_poles,
        "feeders": feeders_data,
        "feeders_list": feeders_list,
        "feeder_name_lookup": feeder_lookup
    }


def create_network_schematic_figure(
    network_data: Dict[str, Any],
    selected_feeder: str = "All Feeders",
    show_all_poles: bool = False,
    label_mode: str = "Standard"
) -> go.Figure:
    """
    Renders an interactive Plotly single-line schematic matching the user's sketch:
    - Distribution Transformer symbol on the left
    - Vertical distribution spine connecting all horizontal feeders
    - Feeders running horizontally to the right
    - Spurs branching with 45-degree slanted takeoff + horizontal parallel run
    - Special Poles Display: Shows only important nodes by default, with toggle to show all poles
    """
    fig = go.Figure()

    tf_info = network_data["transformer"]
    tf_pole = tf_info["pole_id"]
    nmd_dict = network_data["nmd_poles"]
    solar_dict = network_data["solar_poles"]
    feeders = network_data["feeders"]

    feeder_palette = {
        "F1": "#2563EB",  # Royal Blue
        "F2": "#059669",  # Emerald Green
        "F3": "#7C3AED",  # Purple
        "F4": "#D97706",  # Amber Orange
    }
    default_colors = ["#2563EB", "#059669", "#7C3AED", "#D97706", "#DB2777", "#0891B2"]

    is_all_view = (selected_feeder == "All Feeders")
    display_feeders = list(feeders.keys()) if is_all_view else [selected_feeder]

    # Center/Left Transformer Position
    tf_x = -7.0
    tf_y = 0.0

    # 1. Draw Vertical Distribution Spine & Transformer Links (As in user's sketch)
    feeder_ys = [feeders[f]["base_y"] for f in display_feeders]
    min_spine_y = min(feeder_ys) if feeder_ys else 0.0
    max_spine_y = max(feeder_ys) if feeder_ys else 0.0

    if is_all_view and len(display_feeders) > 1:
        # Vertical line connecting all horizontal feeder lines at X = 0
        fig.add_trace(go.Scatter(
            x=[0.0, 0.0],
            y=[min_spine_y, max_spine_y],
            mode="lines",
            line=dict(color="#1E3A8A", width=4.5),
            name="Distribution Spine",
            hoverinfo="text",
            hovertext="⚡ Distribution Transformer Secondary Riser"
        ))

    # Horizontal link from Transformer to Vertical Spine (or directly to feeder at Y=0)
    fig.add_trace(go.Scatter(
        x=[tf_x + 1.2, 0.0],
        y=[0.0, 0.0],
        mode="lines",
        line=dict(color="#1E3A8A", width=4.5),
        hoverinfo="skip",
        showlegend=False
    ))

    # 2. Draw Feeder Conductors: Main Trunk (Solid) and Spurs (45-degree ramp + horizontal run)
    junction_nodes_x = []
    junction_nodes_y = []
    junction_nodes_hover = []

    for f_idx, f_name in enumerate(display_feeders):
        f_data = feeders[f_name]
        edge_color = feeder_palette.get(f_name[:2], default_colors[f_idx % len(default_colors)])
        f_coords = f_data["coords"]
        y_base = f_data["base_y"] if is_all_view else 0.0

        f_display = f_data.get("display_name", f_name)

        # Adjust Y coordinates for single feeder view if needed
        y_shift = 0.0 if is_all_view else -f_data["base_y"]
        
        # A. MAIN TRUNK CONDUCTOR (Straight horizontal solid line)
        trunk_x = [0.0]  # Starts from vertical spine at X = 0
        trunk_y = [y_base + y_shift]
        
        for p in f_data["trunk_poles"]:
            if p in f_coords:
                trunk_x.append(f_coords[p]["x"])
                trunk_y.append(f_coords[p]["y"] + y_shift)

        fig.add_trace(go.Scatter(
            x=trunk_x, y=trunk_y,
            mode="lines",
            line=dict(color=edge_color, width=3.8),
            name=f"Feeder {f_display} (Main Feeder)",
            hoverinfo="text",
            hovertext=f"━ Feeder {f_display} Main Feeder Conductor ({len(f_data['trunk_poles'])} poles)"
        ))

        # B. SPUR FEEDER CONDUCTORS (45-degree ramp + horizontal parallel run, exactly as sketch)
        spur_x = []
        spur_y = []
        
        for s in f_data.get("spur_meta", []):
            j_x = s["j_x"]
            j_y = s["j_y"] + y_shift
            ramp_end_x = s["ramp_end_x"]
            y_spur = s["y_spur"] + y_shift
            
            # Record junction pole
            jp = s["junction"]
            junction_nodes_x.append(j_x)
            junction_nodes_y.append(j_y)
            junction_nodes_hover.append(
                f"<b>🔗 JUNCTION POLE: {jp}</b><br>"
                f"Feeder: {f_display}<br>"
                f"Spur Branch: {len(s['poles'])} poles ({s['poles'][0]} to {s['poles'][-1]})"
            )

            # 1. 45-degree ramp: (j_x, j_y) -> (ramp_end_x, y_spur)
            # 2. Horizontal run: (ramp_end_x, y_spur) -> spur poles
            spur_x.extend([j_x, ramp_end_x])
            spur_y.extend([j_y, y_spur])
            
            for p in s["poles"]:
                if p in f_coords:
                    spur_x.append(f_coords[p]["x"])
                    spur_y.append(f_coords[p]["y"] + y_shift)
                    
            spur_x.append(None)
            spur_y.append(None)

        if spur_x:
            fig.add_trace(go.Scatter(
                x=spur_x, y=spur_y,
                mode="lines",
                line=dict(color=edge_color, width=2.5),
                name=f"Feeder {f_display} (Spurs)",
                hoverinfo="text",
                hovertext=f"━ Feeder {f_display} Spur Feeders ({len(f_data['spur_branches'])} branches)"
            ))

    # 3. Draw Junction Poles (Open Ring Marker)
    if junction_nodes_x:
        fig.add_trace(go.Scatter(
            x=junction_nodes_x, y=junction_nodes_y,
            mode="markers",
            marker=dict(
                size=13,
                color="rgba(255, 255, 255, 0)",
                symbol="circle-open",
                line=dict(color="#0F172A", width=2.2)
            ),
            hovertext=junction_nodes_hover,
            hoverinfo="text",
            name="🔗 Junction Poles (Spur Tap-offs)"
        ))

    # 4. Categorize Nodes: Separate Special Poles from Intermediate Regular Poles
    reg_x, reg_y, reg_hover = [], [], []
    solar_x, solar_y, solar_text, solar_hover, solar_size, solar_pos = [], [], [], [], [], []
    nmd_x, nmd_y, nmd_text, nmd_hover, nmd_pos = [], [], [], [], []

    solar_count = 0
    nmd_count = 0

    for f_name in display_feeders:
        f_data = feeders[f_name]
        f_coords = f_data["coords"]
        y_shift = 0.0 if is_all_view else -f_data["base_y"]
        
        sorted_poles = sorted(f_coords.items(), key=lambda item: item[1]["x"])

        for p, pos in sorted_poles:
            x, y = pos["x"], pos["y"] + y_shift
            is_spur = pos.get("is_spur", False)
            j_name = pos.get("junction")
            branch_label = f"Spur from {j_name}" if is_spur else "Main Feeder"
            
            nmd_info = match_nmd_to_pole(p, nmd_dict, f_name)
            solar_info = match_solar_to_pole(p, solar_dict, f_name)

            hover_parts = [
                f"<b>Pole: {p}</b>", 
                f"Feeder: {f_name}",
                f"Branch: <i>{branch_label}</i>"
            ]
            if nmd_info:
                hover_parts.append(f"📌 <b>NMD Installed:</b> {nmd_info['nickname']} ({nmd_info['role']})")
                hover_parts.append(f"DB Reference: {nmd_info['db_name']}")
            if solar_info:
                hover_parts.append(f"<b>Solar Capacity:</b> {solar_info['effective_kw']:.1f} kW")
                hover_parts.append(f"Inverter: {solar_info['inverter_kw']:.1f} kW | Installed: {solar_info['installed_kw']:.1f} kWp")
                hover_parts.append(f"Customers ({solar_info['customer_count']}): {', '.join(solar_info['customers'])}")

            hover_html = "<br>".join(hover_parts)

            if solar_info:
                solar_count += 1
                solar_x.append(x)
                solar_y.append(y)
                
                # Alternate top and bottom labels so adjacent poles don't collide
                pos_tag = "top center" if (solar_count % 2 != 0) else "bottom center"
                solar_pos.append(pos_tag)
                
                if label_mode == "Standard":
                    solar_text.append(f"{solar_info['effective_kw']:.0f}kW")
                elif label_mode == "Detailed":
                    solar_text.append(f"{p} ({solar_info['effective_kw']:.1f}kW)")
                elif label_mode == "All Poles":
                    solar_text.append(f"{p} ({solar_info['effective_kw']:.0f}kW)")
                else:
                    solar_text.append("")

                solar_hover.append(hover_html)
                s_size = min(28, max(15, int(14 + solar_info['effective_kw'] * 0.7)))
                solar_size.append(s_size)

            elif nmd_info:
                nmd_count += 1
                nmd_x.append(x)
                nmd_y.append(y)
                
                pos_tag = "bottom center" if (nmd_count % 2 != 0) else "top center"
                nmd_pos.append(pos_tag)
                
                if label_mode in ["Standard", "Minimal"]:
                    nmd_text.append(f"📌 {nmd_info['nickname']}")
                elif label_mode == "Detailed":
                    nmd_text.append(f"📌 {nmd_info['nickname']} ({p})")
                elif label_mode == "All Poles":
                    nmd_text.append(f"📌 {nmd_info['nickname']} [{p}]")
                else:
                    nmd_text.append("")

                nmd_hover.append(hover_html)

            else:
                # Intermediate regular pole without solar and without NMD
                reg_x.append(x)
                reg_y.append(y)
                reg_hover.append(hover_html)

    # 5. Draw Regular Line Poles (ONLY IF show_all_poles is True)
    if show_all_poles and reg_x:
        fig.add_trace(go.Scatter(
            x=reg_x, y=reg_y,
            mode="markers",
            marker=dict(size=5, color="#94A3B8", line=dict(color="#FFFFFF", width=0.8)),
            hovertext=reg_hover,
            hoverinfo="text",
            name="Intermediate Poles (Toggled)"
        ))

    # 6. Draw Special Poles: Solar Customer Poles (Golden Glow)
    if solar_x:
        fig.add_trace(go.Scatter(
            x=solar_x, y=solar_y,
            mode="markers+text" if label_mode != "Minimal" else "markers",
            marker=dict(
                size=solar_size,
                color="#F59E0B",
                symbol="circle",
                line=dict(color="#92400E", width=2.5)
            ),
            text=solar_text,
            textposition=solar_pos,
            textfont=dict(size=11, color="#92400E", family="Arial Black"),
            hovertext=solar_hover,
            hoverinfo="text",
            name="Poles with Solar Customers"
        ))

    # 7. Draw Special Poles: NMD Monitoring Devices (Teal Diamonds)
    if nmd_x:
        fig.add_trace(go.Scatter(
            x=nmd_x, y=nmd_y,
            mode="markers+text" if label_mode != "Minimal" else "markers",
            marker=dict(
                size=20,
                color="#06B6D4",
                symbol="diamond",
                line=dict(color="#0891B2", width=2.8)
            ),
            text=nmd_text,
            textposition=nmd_pos,
            textfont=dict(size=11, color="#0E7490", family="Arial Black"),
            hovertext=nmd_hover,
            hoverinfo="text",
            name="📌 NMD Monitoring Devices"
        ))

    # ==========================================
    # 8. CENTRAL / LEFT 11kV / 400V DISTRIBUTION TRANSFORMER (USED ONCE)
    # Interlocking circles matching user's sketch on left
    # ==========================================
    # MV 11kV Grid Supply Line (Incoming horizontally from left)
    fig.add_trace(go.Scatter(
        x=[tf_x - 5.0, tf_x - 1.4],
        y=[0.0, 0.0],
        mode="lines",
        line=dict(color="#DC2626", width=4.0),
        name="MV 11kV Supply Line",
        hoverinfo="text",
        hovertext="⚡ Medium Voltage 11kV Incoming Supply"
    ))

    # Primary Winding Circle (left circle)
    fig.add_trace(go.Scatter(
        x=[tf_x - 1.2],
        y=[0.0],
        mode="markers",
        marker=dict(
            symbol="circle-open",
            size=44,
            color="#1E3A8A",
            line=dict(color="#1E3A8A", width=4.0)
        ),
        name="Primary Winding (11kV)",
        hoverinfo="text",
        hovertext="⚡ Distribution Transformer Primary Winding (Delta 11kV)"
    ))

    # Secondary Winding Circle (overlapping right circle)
    fig.add_trace(go.Scatter(
        x=[tf_x + 0.2],
        y=[0.0],
        mode="markers",
        marker=dict(
            symbol="circle-open",
            size=44,
            color="#1E3A8A",
            line=dict(color="#1E3A8A", width=4.0)
        ),
        name="Secondary Winding (400V)",
        hoverinfo="text",
        hovertext="⚡ Distribution Transformer Secondary Winding (Star 400V/230V)"
    ))

    # Core Distribution Transformer Pole Node (Used exactly once)
    cap_line = f"Rated Capacity: {tf_info['capacity']}<br>" if tf_info.get('capacity') else ""
    tf_hover = (
        f"<b>⚡ 11kV / 400V DISTRIBUTION TRANSFORMER</b><br>"
        f"Unit Nickname: {tf_info['nickname']}<br>"
        f"DB Reference: {tf_info['db_name']}<br>"
        f"Distribution Transformer Pole: {tf_pole}<br>"
        f"{cap_line}"
        f"Connected Feeders: {', '.join(network_data.get('feeders_list', []))}"
    )

    fig.add_trace(go.Scatter(
        x=[tf_x + 0.2],
        y=[0.0],
        mode="markers+text",
        marker=dict(
            size=22,
            color="#1E3A8A",
            symbol="square",
            line=dict(color="#FFFFFF", width=2.5)
        ),
        text=[f"⚡ Distribution Transformer ({tf_pole})"],
        textposition="top center",
        textfont=dict(size=12, color="#1E3A8A", family="Arial Black"),
        hovertext=[tf_hover],
        hoverinfo="text",
        name="⚡ Distribution Transformer"
    ))

    # Format layout with wide horizontal canvas & clean bottom legend
    fig.update_layout(
        title=dict(
            text=f"11kV/400V Distribution Transformer Network Schematic ({selected_feeder})",
            font=dict(size=16, color="#1E3A8A"),
            x=0.02,
            y=0.98
        ),
        showlegend=True,
        hovermode="closest",
        plot_bgcolor="#F8FAFC",
        xaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title=f"Distribution Transformer ({tf_pole}) ─── Distribution Feeders ───►"
        ),
        yaxis=dict(
            showgrid=False,
            zeroline=False,
            showticklabels=False,
            title=""
        ),
        margin=dict(l=30, r=30, t=50, b=70),
        height=max(450, min(1000, 220 + len(display_feeders) * 135)) if is_all_view else 480,
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.06,
            xanchor="center",
            x=0.5,
            font=dict(size=11)
        )
    )

    return fig


def create_feeder_distance_solar_chart(network_data: Dict[str, Any], selected_feeder: str = "F1") -> go.Figure:
    """
    Plots cumulative solar capacity along the feeder distance (hop sequence from Distribution Transformer).
    Shows how solar generation accumulates along the feeder line and indicates NMD meter positions.
    """
    feeders = network_data["feeders"]
    tf_pole = network_data["transformer"]["pole_id"]
    solar_dict = network_data["solar_poles"]
    nmd_dict = network_data["nmd_poles"]
    
    if selected_feeder not in feeders:
        selected_feeder = list(feeders.keys())[0]

    f_data = feeders[selected_feeder]
    coords = f_data["coords"]
    
    # Sort poles by distance/depth from distribution transformer
    sorted_poles = sorted(coords.keys(), key=lambda p: coords[p]["depth"])
    
    hops = []
    poles_labels = []
    solar_added = []
    cumulative_solar = []
    
    running_total = 0.0
    for idx, p in enumerate(sorted_poles):
        hops.append(coords[p]["depth"])
        poles_labels.append(p)
        
        sol_info = match_solar_to_pole(p, solar_dict, selected_feeder)
        sol_kw = sol_info["effective_kw"] if sol_info else 0.0
        running_total += sol_kw
        solar_added.append(sol_kw)
        cumulative_solar.append(running_total)

    df_plot = pd.DataFrame({
        "Pole": poles_labels,
        "Distance_Hop": hops,
        "Solar_Injected_kW": solar_added,
        "Cumulative_Solar_kW": cumulative_solar
    })

    fig = go.Figure()
    
    # Cumulative solar line
    fig.add_trace(go.Scatter(
        x=df_plot["Pole"],
        y=df_plot["Cumulative_Solar_kW"],
        mode="lines+markers",
        name="Cumulative Solar (kW)",
        line=dict(color="#F59E0B", width=3.2),
        marker=dict(size=6, color="#B45309")
    ))

    # Point solar capacity bars
    fig.add_trace(go.Bar(
        x=df_plot["Pole"],
        y=df_plot["Solar_Injected_kW"],
        name="Solar at Pole (kW)",
        marker_color="rgba(245, 158, 11, 0.45)",
        yaxis="y"
    ))

    # Mark NMD poles using numeric index on categorical x-axis
    for p in sorted_poles:
        nmd_info = match_nmd_to_pole(p, nmd_dict, selected_feeder)
        if nmd_info:
            matches = df_plot.index[df_plot["Pole"] == p].tolist()
            if matches:
                idx = matches[0]
                fig.add_vline(
                    x=idx,
                    line_dash="dash",
                    line_color="#06B6D4",
                    annotation_text=f"📌 {nmd_info['nickname']}",
                    annotation_position="top left"
                )

    fig.update_layout(
        title=f"Cumulative Solar Capacity along Feeder {selected_feeder} Path",
        xaxis_title=f"Poles along Feeder Path (from Distribution Transformer {tf_pole} to Line End)",
        yaxis_title="Effective Solar Capacity (kW)",
        hovermode="x unified",
        margin=dict(l=40, r=40, t=50, b=60),
        legend=dict(orientation="h", yanchor="top", y=-0.15, xanchor="center", x=0.5)
    )

    return fig


def get_network_summary_dataframe(network_data: Dict[str, Any]) -> pd.DataFrame:
    """
    Constructs a comprehensive tabular summary for all feeders:
    - Feeder Name
    - Total Poles (excluding Distribution Transformer pole which is counted once at origin)
    - Main Trunk Poles
    - Spur Count
    - NMD Count & Devices
    - Solar Customer Count & Total Solar kW
    """
    feeders = network_data["feeders"]
    solar_dict = network_data["solar_poles"]
    nmd_dict = network_data["nmd_poles"]
    
    records = []
    for f_name, f_data in feeders.items():
        total_p = len(f_data["unique_poles"])
        trunk_p = len(f_data["trunk_poles"])
        spur_count = len(f_data["spur_branches"])
        
        nmds_found = []
        for p in f_data["unique_poles"]:
            info = match_nmd_to_pole(p, nmd_dict, f_name)
            if info:
                nmds_found.append(f"{info['nickname']} ({p})")
                
        solar_p_count = 0
        tot_sol_kw = 0.0
        tot_cust = 0
        for p in f_data["unique_poles"]:
            sol = match_solar_to_pole(p, solar_dict, f_name)
            if sol:
                solar_p_count += 1
                tot_sol_kw += sol["effective_kw"]
                tot_cust += sol["customer_count"]

        f_display = f_data.get("display_name", f_name)
        records.append({
            "Feeder": f_display,
            "Feeder_Key": f_name,
            "Feeder_Name": f_data.get("feeder_name", ""),
            "Line_Poles": total_p,
            "Main_Feeder_Poles": trunk_p,
            "Trunk_Poles": trunk_p,
            "Spurs_Count": spur_count,
            "NMD_Devices": ", ".join(nmds_found) if nmds_found else "None",
            "Solar_Poles": solar_p_count,
            "Solar_Customers": tot_cust,
            "Total_Solar_kW": round(tot_sol_kw, 2)
        })

    return pd.DataFrame(records)
