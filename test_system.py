"""
test_system.py
Validates Global Statistical Voting Engine (Nighttime Priority) across all scenarios.
"""

from sample_data_generator import generate_nmd_excel
from excel_parser import parse_nmd_excel
from ct_polarity_analyzer import analyze_transformer_ct_polarities

def test_engine():
    scenarios = [
        ("normal", "NORMAL_IMPORT", "✅ SYSTEM NORMAL"),
        ("phase_a_reversed", "FM4", "Phase A CT is physically reversed"),
        ("all_reversed", "FM1", "All three CTs (Phases A, B, and C) are physically reversed"),
        ("phase_bc_reversed", "FM3", "Phase B and Phase C CTs are physically reversed"),
    ]

    for sc_name, expected_mode, expected_text in scenarios:
        print(f"\n==========================================")
        print(f"Testing Scenario: {sc_name}")
        print(f"Expected Mode: {expected_mode}")
        print(f"==========================================")
        
        excel_bytes = generate_nmd_excel(sc_name, num_days=10)
        parsed = parse_nmd_excel(excel_bytes)
        assert parsed["status"] == "success"
        
        tf_nick = parsed["transformer_nick"]
        df_tf = parsed["device_readings"][tf_nick]
        
        result = analyze_transformer_ct_polarities(df_tf)
        assert result["status"] == "success"
        
        print(f"Dominant Mode: {result['dominant_mode']}")
        print(f"Confidence Level: {result['confidence_percent']}%")
        print("Status Label:", result['status_label'].encode('ascii', 'replace').decode('ascii'))
        
        assert result["dominant_mode"] == expected_mode, f"Expected {expected_mode} but got {result['dominant_mode']}"
        assert expected_text in result["status_label"], f"Expected '{expected_text}' in status label"
        print(f"--> Scenario {sc_name} PASSED!")

    # Also test real file BZ5504new.xlsx
    print(f"\n==========================================")
    print("Testing Real Field File: BZ5504new.xlsx")
    print(f"==========================================")
    parsed_real = parse_nmd_excel("BZ5504new.xlsx")
    tf_df = parsed_real["device_readings"][parsed_real["transformer_nick"]]
    res_real = analyze_transformer_ct_polarities(tf_df)
    print("Dominant Mode:", res_real["dominant_mode"])
    print("Confidence:", f"{res_real['confidence_percent']}%")
    print("Status Label:", res_real["status_label"].encode('ascii', 'replace').decode('ascii'))
    assert res_real["dominant_mode"] == "NORMAL_IMPORT"
    print("--> Real Field File BZ5504new.xlsx PASSED!")

    # Test Feeder Network Topology & Schematic
    print(f"\n==========================================")
    print("Testing Feeder Network Topology Analyzer")
    print(f"==========================================")
    import feeder_topology_analyzer
    topo = feeder_topology_analyzer.build_network_topology(
        parsed_real["poles_dict"], parsed_real["names_df"], parsed_real["solar_df"]
    )
    assert topo["transformer"]["pole_id"] == "ST13/9"
    assert len(topo["feeders"]) == 4
    fig_schematic = feeder_topology_analyzer.create_network_schematic_figure(topo, "All Feeders")
    assert fig_schematic is not None
    fig_dist = feeder_topology_analyzer.create_feeder_distance_solar_chart(topo, "F1")
    assert fig_dist is not None
    df_net = feeder_topology_analyzer.get_network_summary_dataframe(topo)
    assert len(df_net) == 4
    print("--> Feeder Network Topology PASSED!")

    # Test Voltage Profile & Statutory Violation Analyzer
    print(f"\n==========================================")
    print("Testing Voltage Profile & Statutory Violation Analyzer")
    print(f"==========================================")
    import voltage_profile_analyzer
    v_res = voltage_profile_analyzer.analyze_all_network_voltages(
        parsed_real["device_readings"], parsed_real["names_df"], nominal_v=230.0, tolerance_pct=6.0
    )
    assert len(v_res["devices"]) == 8
    assert len(v_res["all_hardware_alerts"]) == 1
    assert "F4" in v_res["all_hardware_alerts"][0]["device"]
    assert "Phase A" in v_res["all_hardware_alerts"][0]["phase"]
    
    # Check Transformer is compliant
    tf_v = v_res["devices"][parsed_real["transformer_nick"]]
    assert tf_v["overall_hv_pct"] <= 1.0
    assert tf_v["overall_lv_pct"] <= 1.0

    # Test Diurnal & Delta charts
    diurnal_tf = voltage_profile_analyzer.compute_diurnal_voltage_profile(tf_v["df_clean"], include_interruptions=True)
    assert len(diurnal_tf) == 96  # 24h * 4 intervals per hour
    fig_diurnal = voltage_profile_analyzer.create_diurnal_voltage_chart(diurnal_tf, "T/F")
    assert fig_diurnal is not None
    fig_comp = voltage_profile_analyzer.create_network_voltage_comparison_chart(v_res["devices"], parsed_real["names_df"])
    assert fig_comp is not None
    fig_delta = voltage_profile_analyzer.create_voltage_drop_delta_chart(v_res["devices"], parsed_real["names_df"], parsed_real["transformer_nick"])
    assert fig_delta is not None
    print("--> Voltage Profile & Statutory Violation Analyzer PASSED!")

    # Test Load Profile Analyzer
    from load_profile_analyzer import compute_daily_load_profiles
    load_res = compute_daily_load_profiles(tf_df, rated_capacity_kva=160.0)

    # Test Mitigation Solutions & Engineering Advisory Engine
    print(f"\n==========================================")
    print("Testing Mitigation Solutions & Engineering Advisory Engine")
    print(f"==========================================")
    from mitigation_solutions_engine import analyze_mitigation_solutions
    sol_real = analyze_mitigation_solutions(res_real, load_res, v_res, topo, parsed_real)
    assert sol_real["status"] == "success"
    assert sol_real["ct_solution"]["is_normal"] is True
    assert sol_real["ct_solution"]["overload_assessment_blocked"] is False
    assert sol_real["transformer_solution"]["is_overloaded"] is False
    assert len(sol_real["action_matrix_df"]) > 0
    print(f"--> Generated {len(sol_real['action_matrix_df'])} Action Matrix items for BZ5504.")

    # Test CT Inversion Gate on Solutions Engine
    fake_ct_reversed = {"dominant_mode": "FM4", "confidence_percent": 100.0, "status_label": "CRITICAL: Phase A Reversed"}
    sol_ct_rev = analyze_mitigation_solutions(fake_ct_reversed, load_res, v_res, topo, parsed_real)
    assert sol_ct_rev["ct_solution"]["overload_assessment_blocked"] is True
    assert "Phase A" in sol_ct_rev["ct_solution"]["affected_phases"]
    print("--> CT Inversion Gate & Overload Indeterminacy PASSED!")

    # Test Word Document (.docx) Report Generator
    print(f"\n==========================================")
    print("Testing Word Document (.docx) Report Generator")
    print(f"==========================================")
    from report_generator import generate_word_report
    doc_bytes = generate_word_report(parsed_real, res_real, load_res, topo, v_res)
    assert doc_bytes is not None
    assert len(doc_bytes.getvalue()) > 500000  # Over 500KB with 5 embedded high-res figures
    print(f"--> Word Document Report Generated Successfully! (Size: {len(doc_bytes.getvalue()):,} bytes)")

    print("\nALL TEST SCENARIOS PASSED PERFECTLY!")

if __name__ == "__main__":
    test_engine()
