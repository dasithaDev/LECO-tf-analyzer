# ⚡ Distribution Transformer NMD Analytics Dashboard

An engineering dashboard built with Streamlit and Plotly to analyze Network Monitoring Device (NMD) readings on distribution transformers, detect Current Transformer (CT) polarity wiring anomalies, visualize feeder voltage regulation, and track rooftop solar integration.

---

## 🚀 Quick Start

### 1. Launch the Dashboard
Double-click `run_dashboard.bat` or run in PowerShell:
```powershell
.\run_dashboard.ps1
```
Or directly via Python:
```powershell
& "C:\Users\USER\AppData\Local\Programs\Python\Python312\python.exe" -m streamlit run app.py
```

The dashboard will open automatically in your browser at `http://localhost:8501`.

---

## 🔬 Global Statistical Voting Engine (Nighttime Priority)

Evaluates nighttime intervals (e.g. 21:00 – 05:00, where solar irradiance is zero) to find the globally dominant current polarity profile, calculate statistical confidence levels, and evaluate the 8 failure modes in **strict priority order**:

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

---

## 📊 Excel File Structure (4 Sheets)

| Sheet Name | Content & Description | Key Columns / Rules |
| :--- | :--- | :--- |
| **`DB`** | 15-minute readings for a month for NMDs and Transformer | `CUSTOMER_REF`, `DATE`, `TIME`, `Ia`, `Ib`, `Ic`, `Va`, `Vb`, `Vc`, `AVG._IMPORT_KVA (kVA)`, `AVG._EXPORT_KVA (kVA)` |
| **`Names`** | 3-column device mapping table | Col 1: **Nickname** (`T/F`, `F1`, `F1M`, `F2`)<br>Col 2: **DB Name** (`042/BZ5504`, `wanarathana Mw Side`, etc.)<br>Col 3: **Pole ID** (`ST13/9`, `ST13/10V`, etc.) |
| **`Poles`** | Pole sequence in order for each feeder | Columns named by Feeder, listing ordered poles:<br>• Main Feeder: `ST13/9`, `ST13/10`, `ST13/10A`...<br>• Spur Branches: `ST13/11-1`, `ST13/6-1`... |
| **`Solar Customers`** | Solar customer details | `POLE`, `INV_CAPACITY`, `CAPACITY`<br>⚡ **Rule:** Effective solar capacity = $\min(\text{Inverter Capacity}, \text{Installed Capacity})$ |

---

## 📁 Repository Structure

```
e:\HV LV Mitigation\
├── app.py                                # Main Streamlit dashboard application
├── ct_polarity_analyzer.py               # Global Statistical Voting Engine (Nighttime Priority)
├── excel_parser.py                       # Robust parser for all 4 Excel sheets
├── sample_data_generator.py              # Generator for 30-day realistic test files
├── test_system.py                        # Automated verification test suite
├── run_dashboard.bat                     # Windows batch launcher
├── run_dashboard.ps1                     # PowerShell launcher
├── BZ5504new.xlsx                        # Real field dataset: BZ5504 (Full Month)
├── Sample_NMD_Normal_30Days.xlsx         # Benchmark test file: Normal (Safe State)
├── Sample_NMD_PhaseA_Reversed_30Days.xlsx# Benchmark test file: Phase A reversed (FM4)
├── Sample_NMD_All_Reversed_30Days.xlsx   # Benchmark test file: All 3 reversed (FM1)
└── Sample_NMD_PhaseBC_Reversed_30Days.xlsx# Benchmark test file: Phase B & C reversed (FM3)
```
