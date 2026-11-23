"""
build_presentation.py
Generates the Training Progress Review PowerPoint presentation (.pptx)
for LECO Galle Branch & University of Ruhuna.
Slide 1 is the main project title slide integrating all trainee details:
- Pawani Malshani, Kaveesha Nipuni, Dasitha Nayanapriya, Kaveesha Dewmini
- University of Ruhuna
- Galle Branch
- Training Progress Review
All slides use simple English, short phrases, and large font sizes.
"""

import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE

# Initialize Presentation (16:9 widescreen)
prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
blank_layout = prs.slide_layouts[6]

# Palette
NAVY_PRIMARY = RGBColor(30, 58, 138)     # #1E3A8A
BLUE_ACCENT = RGBColor(2, 132, 199)      # #0284C7
DARK_SLATE = RGBColor(30, 41, 59)        # #1E293B
MUTED_GRAY = RGBColor(100, 116, 139)     # #64748B
BG_LIGHT = RGBColor(248, 250, 252)       # #F8FAFC
CARD_BG = RGBColor(255, 255, 255)        # #FFFFFF
BORDER_COLOR = RGBColor(226, 232, 240)   # #E2E8F0
GREEN_SUCCESS = RGBColor(5, 150, 105)    # #059669
AMBER_WARNING = RGBColor(217, 119, 6)    # #D97706
RED_CRITICAL = RGBColor(220, 38, 38)     # #DC2626
CAMERA_AMBER = RGBColor(254, 243, 199)   # #FEF3C7
CAMERA_BORDER = RGBColor(245, 158, 11)   # #F59E0B

LOGO_PATH = "leco_logo.png" if os.path.exists("leco_logo.png") else None


def add_header(slide, title_text, category_text="LECO GALLE BRANCH • UNIVERSITY OF RUHUNA TRAINING REVIEW"):
    """Adds a standard clean header with category pill, title, and divider."""
    header_box = slide.shapes.add_textbox(Inches(0.8), Inches(0.35), Inches(11.7), Inches(1.15))
    tf = header_box.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0
    
    p0 = tf.paragraphs[0]
    p0.text = category_text.upper()
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = BLUE_ACCENT
    
    p1 = tf.add_paragraph()
    p1.text = title_text
    p1.font.size = Pt(25)
    p1.font.bold = True
    p1.font.color.rgb = NAVY_PRIMARY
    p1.space_before = Pt(2)

    line = slide.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0.8), Inches(1.5), Inches(11.7), Inches(0.04))
    line.fill.solid()
    line.fill.fore_color.rgb = BLUE_ACCENT
    line.line.color.rgb = BLUE_ACCENT

    if LOGO_PATH:
        try:
            slide.shapes.add_picture(LOGO_PATH, Inches(11.6), Inches(0.35), height=Inches(0.95))
        except Exception:
            pass


def add_card(slide, left, top, width, height, bg_color=CARD_BG, border_color=BORDER_COLOR):
    """Creates a rounded rectangle card container."""
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    shape.fill.solid()
    shape.fill.fore_color.rgb = bg_color
    shape.line.color.rgb = border_color
    shape.line.width = Pt(1.2)
    return shape


def add_screenshot_placeholder(slide, left, top, width, height, title, instructions):
    """Adds a stylish, prominent screenshot placeholder box."""
    box = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, left, top, width, height)
    box.fill.solid()
    box.fill.fore_color.rgb = CAMERA_AMBER
    box.line.color.rgb = CAMERA_BORDER
    box.line.width = Pt(1.8)

    tb = slide.shapes.add_textbox(left + Inches(0.2), top + Inches(0.2), width - Inches(0.4), height - Inches(0.4))
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = tf.margin_top = tf.margin_right = tf.margin_bottom = 0

    p0 = tf.paragraphs[0]
    p0.text = f"📸 SCREENSHOT: {title}"
    p0.font.size = Pt(13)
    p0.font.bold = True
    p0.font.color.rgb = RGBColor(146, 64, 14)
    p0.alignment = PP_ALIGN.CENTER

    p1 = tf.add_paragraph()
    p1.text = instructions
    p1.font.size = Pt(11)
    p1.font.color.rgb = RGBColor(120, 53, 15)
    p1.space_before = Pt(8)
    p1.alignment = PP_ALIGN.LEFT


def set_speaker_notes(slide, notes_text):
    """Adds speaker notes to slide."""
    notes_slide = slide.notes_slide
    text_frame = notes_slide.notes_text_frame
    text_frame.text = notes_text


# ==============================================================================
# SLIDE 1: MAIN TITLE SLIDE (WITH ALL USER INFO INTEGRATED NATIVELY)
# ==============================================================================
slide1 = prs.slides.add_slide(blank_layout)

bg_card1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg_card1.fill.solid()
bg_card1.fill.fore_color.rgb = BG_LIGHT
bg_card1.line.fill.background()

top_bar1 = slide1.shapes.add_shape(MSO_SHAPE.RECTANGLE, Inches(0), Inches(0), Inches(13.333), Inches(0.25))
top_bar1.fill.solid()
top_bar1.fill.fore_color.rgb = NAVY_PRIMARY
top_bar1.line.fill.background()

# Top Institution & Branch Header
if LOGO_PATH:
    try:
        slide1.shapes.add_picture(LOGO_PATH, Inches(1.0), Inches(0.75), height=Inches(1.2))
    except Exception:
        pass

tb_head = slide1.shapes.add_textbox(Inches(2.5), Inches(0.85), Inches(9.8), Inches(1.1))
tf_head = tb_head.text_frame
tf_head.word_wrap = True
p_h_0 = tf_head.paragraphs[0]
p_h_0.text = "LANKA ELECTRICITY COMPANY (LECO) • GALLE BRANCH"
p_h_0.font.size = Pt(13)
p_h_0.font.bold = True
p_h_0.font.color.rgb = BLUE_ACCENT
p_h_1 = tf_head.add_paragraph()
p_h_1.text = "TRAINING PROGRESS REVIEW"
p_h_1.font.size = Pt(16)
p_h_1.font.bold = True
p_h_1.font.color.rgb = NAVY_PRIMARY
p_h_1.space_before = Pt(2)

# Main Project Title Box
tb_title = slide1.shapes.add_textbox(Inches(1.0), Inches(2.2), Inches(11.333), Inches(2.8))
tf = tb_title.text_frame
tf.word_wrap = True

p_main = tf.paragraphs[0]
p_main.text = "Automated Distribution Transformer\nAnalytics & Mitigation Dashboard"
p_main.font.size = Pt(36)
p_main.font.bold = True
p_main.font.color.rgb = NAVY_PRIMARY

p_desc = tf.add_paragraph()
p_desc.text = "CT Wiring Error Detection • Diurnal Load Curves • Voltage Regulation • Rooftop Solar"
p_desc.font.size = Pt(16)
p_desc.font.color.rgb = MUTED_GRAY
p_desc.space_before = Pt(10)

# Trainee Information Card (All Info from October Slide)
team_card = add_card(slide1, Inches(1.0), Inches(5.35), Inches(11.333), Inches(1.65), bg_color=CARD_BG)
tb_team = slide1.shapes.add_textbox(Inches(1.3), Inches(5.5), Inches(10.7), Inches(1.35))
tf_tm = tb_team.text_frame
tf_tm.word_wrap = True

p_tm_t = tf_tm.paragraphs[0]
p_tm_t.text = "PRESENTED BY (UNIVERSITY OF RUHUNA TRAINEE TEAM):"
p_tm_t.font.size = Pt(11)
p_tm_t.font.bold = True
p_tm_t.font.color.rgb = BLUE_ACCENT

p_names = tf_tm.add_paragraph()
p_names.text = "PAWANI MALSHANI   •   KAVEESHA NIPUNI   •   DASITHA NAYANAPRIYA   •   KAVEESHA DEWMINI"
p_names.font.size = Pt(14)
p_names.font.bold = True
p_names.font.color.rgb = DARK_SLATE
p_names.space_before = Pt(4)

p_affil = tf_tm.add_paragraph()
p_affil.text = "UNIVERSITY OF RUHUNA   |   GALLE BRANCH"
p_affil.font.size = Pt(12)
p_affil.font.bold = True
p_affil.font.color.rgb = MUTED_GRAY
p_affil.space_before = Pt(4)

set_speaker_notes(slide1, """Good morning/afternoon everyone. Welcome to our Training Progress Review at LECO Galle Branch. We are engineering trainees from the University of Ruhuna: Pawani Malshani, Kaveesha Nipuni, Dasitha Nayanapriya, and Kaveesha Dewmini. Today, we will present our project: the Automated Distribution Transformer Analytics and Mitigation Dashboard.""")


# ==============================================================================
# SLIDE 2: WHY WE BUILT THIS DASHBOARD (USER REQUEST)
# ==============================================================================
slide2 = prs.slides.add_slide(blank_layout)
add_header(slide2, "Why We Built This Dashboard", "PROJECT BACKGROUND")

story_card = add_card(slide2, Inches(0.8), Inches(1.75), Inches(11.733), Inches(1.85), bg_color=RGBColor(239, 246, 255), border_color=BLUE_ACCENT)
tb_story = slide2.shapes.add_textbox(Inches(1.1), Inches(1.9), Inches(11.1), Inches(1.55))
tf_s = tb_story.text_frame
tf_s.word_wrap = True
p_st1 = tf_s.paragraphs[0]
p_st1.text = "🎯 OUR TASK & WHAT WE FOUND:"
p_st1.font.size = Pt(14)
p_st1.font.bold = True
p_st1.font.color.rgb = NAVY_PRIMARY

p_st2 = tf_s.add_paragraph()
p_st2.text = (
    "\"We were assigned to analyze transformers that have solar customers, where errors were suspected. "
    "At first, we did this manually in Excel. But doing it separately in Excel took too much time—checking "
    "thousands of 15-minute readings, multiple sheets, and line drops for each transformer. "
    "So we decided to create an automated dashboard to do it all in seconds!\""
)
p_st2.font.size = Pt(14)
p_st2.font.italic = True
p_st2.font.color.rgb = DARK_SLATE
p_st2.space_before = Pt(6)

card_before = add_card(slide2, Inches(0.8), Inches(3.85), Inches(5.7), Inches(3.2), bg_color=RGBColor(254, 242, 242), border_color=RED_CRITICAL)
tb_bef = slide2.shapes.add_textbox(Inches(1.1), Inches(4.05), Inches(5.1), Inches(2.8))
tf_b = tb_bef.text_frame
tf_b.word_wrap = True
p_b1 = tf_b.paragraphs[0]
p_b1.text = "❌ BEFORE: Manual Excel Work"
p_b1.font.size = Pt(16)
p_b1.font.bold = True
p_b1.font.color.rgb = RED_CRITICAL

points_before = [
    "Over 2,800 rows per meter analyzed by hand",
    "Slow and tiring manual charts and formulas",
    "Easy to miss reversed CT wiring mistakes",
    "Hard to trace feeder branches and solar size",
    "Took 4 to 6 hours for a single transformer!"
]
for pt in points_before:
    p = tf_b.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12.5)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(5)

card_after = add_card(slide2, Inches(6.8), Inches(3.85), Inches(5.7), Inches(3.2), bg_color=RGBColor(236, 253, 245), border_color=GREEN_SUCCESS)
tb_aft = slide2.shapes.add_textbox(Inches(7.1), Inches(4.05), Inches(5.1), Inches(2.8))
tf_a = tb_aft.text_frame
tf_a.word_wrap = True
p_a1 = tf_a.paragraphs[0]
p_a1.text = "✅ AFTER: Automated Dashboard"
p_a1.font.size = Pt(16)
p_a1.font.bold = True
p_a1.font.color.rgb = GREEN_SUCCESS

points_after = [
    "1-click upload of raw LECO Excel files",
    "Instant detection of all 8 CT failure modes",
    "Draws visual network map (Single-Line Diagram)",
    "Suggests exact engineering fixes automatically",
    "Generates official Word report in 5 seconds!"
]
for pt in points_after:
    p = tf_a.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12.5)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(5)

set_speaker_notes(slide2, """Start with our motivation:
'We were assigned at Galle Branch to check transformers with solar customers for errors. When we tried to analyze them manually in Excel, it took 4 to 6 hours per transformer. We realized this was way too slow. That is why we built this automated dashboard.'""")


# ==============================================================================
# SLIDE 3: DATA INGESTION & 4 SHEETS
# ==============================================================================
slide3 = prs.slides.add_slide(blank_layout)
add_header(slide3, "Easy 4-Sheet Excel Data Input", "DATA PIPELINE")

card_sheets = add_card(slide3, Inches(0.8), Inches(1.8), Inches(5.8), Inches(5.2))
tb_sh = slide3.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.4), Inches(4.8))
tf_sh = tb_sh.text_frame
tf_sh.word_wrap = True

p_sh1 = tf_sh.paragraphs[0]
p_sh1.text = "Uses Standard LECO Excel Sheets:"
p_sh1.font.size = Pt(16)
p_sh1.font.bold = True
p_sh1.font.color.rgb = NAVY_PRIMARY

sheets_data = [
    ("1. 'DB' Sheet (Raw Readings)", "15-minute readings: Current (Ia, Ib, Ic), Voltage (Va, Vb, Vc), Import & Export kVA."),
    ("2. 'Names' Sheet (Device List)", "Matches meter nicknames (T/F, F1, F1M) to pole IDs. Auto-detects transformer rating (e.g. 160 kVA)."),
    ("3. 'Poles' Sheet (Feeder Tree)", "Lists poles in physical order: Main feeder line and spur branches."),
    ("4. 'Solar Customers' Sheet", "Customer solar connections. Rule: Solar size = min(Inverter, Panels).")
]

for title, desc in sheets_data:
    p_t = tf_sh.add_paragraph()
    p_t.text = "• " + title
    p_t.font.size = Pt(13)
    p_t.font.bold = True
    p_t.font.color.rgb = BLUE_ACCENT
    p_t.space_before = Pt(10)

    p_d = tf_sh.add_paragraph()
    p_d.text = desc
    p_d.font.size = Pt(12)
    p_d.font.color.rgb = DARK_SLATE
    p_d.space_before = Pt(2)

add_screenshot_placeholder(
    slide3,
    Inches(7.0), Inches(1.8), Inches(5.5), Inches(5.2),
    "Sidebar: File Upload & Auto-Detect",
    "WHAT TO SCREENSHOT:\n"
    "1. Open dashboard at http://localhost:8501\n"
    "2. Screenshot the left sidebar showing:\n"
    "   • File Upload / Demo scenario dropdown\n"
    "   • Green banner: 'Auto-Detected from Excel: 160 kVA'\n\n"
    "TALKING POINT:\n"
    "Engineers just drag and drop the Excel file—no setup needed!"
)

set_speaker_notes(slide3, """Explain the inputs:
'Our dashboard takes the exact 4-sheet Excel file LECO already uses. The system automatically aligns timestamps, cleans data, auto-detects transformer rating, and sets everything up in 1 second.'""")


# ==============================================================================
# SLIDE 4: CT POLARITY CHECK (NIGHTTIME RULE)
# ==============================================================================
slide4 = prs.slides.add_slide(blank_layout)
add_header(slide4, "Checking CT Wiring: The Nighttime Rule", "METER AUDIT")

card_ct_text = add_card(slide4, Inches(0.8), Inches(1.8), Inches(5.8), Inches(5.2))
tb_ct = slide4.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.4), Inches(4.8))
tf_ct = tb_ct.text_frame
tf_ct.word_wrap = True

p_c1 = tf_ct.paragraphs[0]
p_c1.text = "The Simple Science: Zero Solar at Night"
p_c1.font.size = Pt(16)
p_c1.font.bold = True
p_c1.font.color.rgb = NAVY_PRIMARY

ct_notes = [
    ("Why Nighttime (21:00 to 05:00)?", "During the day, solar panels send power back. But at night, solar is ZERO. Power MUST flow from grid to customers."),
    ("Negative Current at Night?", "If a meter records Export or negative current at night, it is 100% a physical wiring error!"),
    ("Statistical Voting Engine:", "Checks every 15-minute night reading across the month. Uses majority voting to ignore temporary spikes."),
    ("⚠️ The Safety Rule:", "If CT wiring is reversed, power calculations are wrong! The dashboard STOPS transformer load checks until wiring is fixed.")
]

for t, d in ct_notes:
    p = tf_ct.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_ct.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

ct_fig_path = "presentation_assets/ct_polarity.png"
if os.path.exists(ct_fig_path):
    slide4.shapes.add_picture(ct_fig_path, Inches(6.8), Inches(1.8), width=Inches(5.7))
    add_screenshot_placeholder(
        slide4,
        Inches(6.8), Inches(4.9), Inches(5.7), Inches(2.1),
        "Tab 1: CT Polarity Alert Banner",
        "WHAT TO SCREENSHOT: Tab 1 ('CT Polarity Analysis') showing the Green 'SYSTEM NORMAL' or Red 'CRITICAL ALERT' banner."
    )
else:
    add_screenshot_placeholder(
        slide4,
        Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.2),
        "Tab 1: CT Polarity Check",
        "WHAT TO SCREENSHOT: Tab 1 banner and voting share bar chart."
    )

set_speaker_notes(slide4, """Explain the nighttime rule:
'Electricians sometimes connect CT leads backwards. During the day, solar export hides this. But at night, there is zero sun. Any export at night is impossible! If the meter shows export at midnight, the CT is reversed.'""")


# ==============================================================================
# SLIDE 5: THE 8 FAILURE MODES IN STRICT PRIORITY ORDER
# ==============================================================================
slide5 = prs.slides.add_slide(blank_layout)
add_header(slide5, "The 8 CT Failure Modes in Strict Priority Order", "DIAGNOSTIC MATRIX")

p_callout = add_card(slide5, Inches(0.8), Inches(1.7), Inches(11.733), Inches(0.7), bg_color=RGBColor(239, 246, 255), border_color=BLUE_ACCENT)
tb_pc = slide5.shapes.add_textbox(Inches(1.0), Inches(1.75), Inches(11.3), Inches(0.6))
tf_pc = tb_pc.text_frame
tf_pc.word_wrap = True
p_pc = tf_pc.paragraphs[0]
p_pc.text = "⚡ WHY STRICT ORDER? Check 3-phase errors first, then 2-phase, then 1-phase. This prevents misdiagnosing a 3-phase error as a 1-phase fault!"
p_pc.font.size = Pt(11)
p_pc.font.bold = True
p_pc.font.color.rgb = NAVY_PRIMARY

table_shape = slide5.shapes.add_table(10, 4, Inches(0.8), Inches(2.55), Inches(11.733), Inches(4.6))
table = table_shape.table
table.columns[0].width = Inches(1.1)
table.columns[1].width = Inches(2.9)
table.columns[2].width = Inches(3.2)
table.columns[3].width = Inches(4.533)

headers = ["Priority", "Failure Mode", "Nighttime Readings", "What Happened & How to Fix"]
for c_idx, h_text in enumerate(headers):
    cell = table.cell(0, c_idx)
    cell.fill.solid()
    cell.fill.fore_color.rgb = NAVY_PRIMARY
    cell.vertical_anchor = MSO_ANCHOR.MIDDLE
    cell.text = h_text
    for p in cell.text_frame.paragraphs:
        p.font.size = Pt(11)
        p.font.bold = True
        p.font.color.rgb = RGBColor(255, 255, 255)
        p.alignment = PP_ALIGN.CENTER if c_idx == 0 else PP_ALIGN.LEFT

failure_modes_data = [
    ("P1", "Failure Mode 1\n(All 3 Reversed)", "Ia, Ib, Ic < 0 AND Export > 0", "❌ All 3 CTs reversed. Swap secondary wires on all 3 phases.", RED_CRITICAL),
    ("P2", "Failure Mode 2\n(Channel Swap)", "Ia, Ib, Ic > 0 AND Export > 0", "❌ Meter channel swapped. Import & Export streams are inverted.", RED_CRITICAL),
    ("P3", "Failure Mode 3\n(Phase A Outlier)", "Ia > 0, Ib & Ic < 0 AND Export > 0", "❌ Phase B and Phase C CTs are physically reversed.", AMBER_WARNING),
    ("P4", "Failure Mode 4\n(Phase A Reversed)", "Ia < 0, Ib & Ic > 0 AND Import > 0", "❌ Phase A CT is reversed. Swap Phase A secondary leads.", AMBER_WARNING),
    ("P5", "Failure Mode 5\n(Phase C Outlier)", "Ic > 0, Ia & Ib < 0 AND Export > 0", "❌ Phase A and Phase B CTs are physically reversed.", AMBER_WARNING),
    ("P6", "Failure Mode 6\n(Phase C Reversed)", "Ic < 0, Ia & Ib > 0 AND Import > 0", "❌ Phase C CT is reversed. Swap Phase C secondary leads.", AMBER_WARNING),
    ("P7", "Failure Mode 7\n(Phase B Outlier)", "Ib > 0, Ia & Ic < 0 AND Export > 0", "❌ Phase A and Phase C CTs are physically reversed.", AMBER_WARNING),
    ("P8", "Failure Mode 8\n(Phase B Reversed)", "Ib < 0, Ia & Ic > 0 AND Import > 0", "❌ Phase B CT is reversed. Swap Phase B secondary leads.", AMBER_WARNING),
    ("SAFE", "Safe State\n(System Normal)", "Ia, Ib, Ic > 0 AND Import > 0\n+ Solar Midday Dip", "✅ SYSTEM NORMAL: All CT wiring matches perfectly across the month.", GREEN_SUCCESS)
]

for r_idx, (prio, mode_name, cond, verd, color_badge) in enumerate(failure_modes_data, start=1):
    bg_row = RGBColor(255, 255, 255) if r_idx % 2 == 1 else RGBColor(248, 250, 252)
    if prio == "SAFE":
        bg_row = RGBColor(236, 253, 245)

    for c_idx, val in enumerate([prio, mode_name, cond, verd]):
        cell = table.cell(r_idx, c_idx)
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg_row
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_top = cell.margin_bottom = Inches(0.03)
        cell.margin_left = cell.margin_right = Inches(0.08)
        cell.text = val
        for p in cell.text_frame.paragraphs:
            p.font.size = Pt(9.5)
            if c_idx == 0:
                p.font.bold = True
                p.alignment = PP_ALIGN.CENTER
                p.font.color.rgb = color_badge
            elif c_idx == 1:
                p.font.bold = True
                p.font.color.rgb = DARK_SLATE
            elif c_idx == 2:
                p.font.color.rgb = DARK_SLATE
            else:
                p.font.bold = (prio in ["P1", "P2", "SAFE"])
                p.font.color.rgb = color_badge if prio in ["P1", "P2", "SAFE"] else DARK_SLATE

set_speaker_notes(slide5, """Explain the 8 modes simply:
'Here are the 8 failure modes. The dashboard checks them in strict priority order:
- Priority 1: All 3 CTs backwards.
- Priority 2: Meter internal channel swap.
- Priority 3, 5, 7: Two CTs backwards.
- Priority 4, 6, 8: One CT backwards.
- Safe State: All normal with expected daytime solar dip.
Checking in this order ensures we never confuse a 3-phase error for a 1-phase error.'""")


# ==============================================================================
# SLIDE 6: WAVEFORM PROOF (NORMAL VS PHASE A REVERSED)
# ==============================================================================
slide6 = prs.slides.add_slide(blank_layout)
add_header(slide6, "Waveform Proof: Normal vs. Phase A Reversed (FM4)", "VISUAL COMPARISON")

card_norm = add_card(slide6, Inches(0.8), Inches(1.8), Inches(5.7), Inches(5.2))
tb_nw = slide6.shapes.add_textbox(Inches(1.0), Inches(1.9), Inches(5.3), Inches(0.45))
tf_nw = tb_nw.text_frame
p_nw = tf_nw.paragraphs[0]
p_nw.text = "✅ Normal Operation (BZ5504)"
p_nw.font.size = Pt(14)
p_nw.font.bold = True
p_nw.font.color.rgb = GREEN_SUCCESS

if os.path.exists("presentation_assets/ct_polarity.png"):
    slide6.shapes.add_picture("presentation_assets/ct_polarity.png", Inches(1.0), Inches(2.4), width=Inches(5.3))

tb_nw_desc = slide6.shapes.add_textbox(Inches(1.0), Inches(5.6), Inches(5.3), Inches(1.2))
tf_nwd = tb_nw_desc.text_frame
tf_nwd.word_wrap = True
p_nd = tf_nwd.paragraphs[0]
p_nd.text = "• All 3 currents stay above zero at night (21:00 – 05:00)\n• Clean daytime solar dip around noon\n• Result: Verified Safe State (100% Confidence)"
p_nd.font.size = Pt(11)
p_nd.font.color.rgb = DARK_SLATE

card_anom = add_card(slide6, Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.2))
tb_aw = slide6.shapes.add_textbox(Inches(7.0), Inches(1.9), Inches(5.3), Inches(0.45))
tf_aw = tb_aw.text_frame
p_aw = tf_aw.paragraphs[0]
p_aw.text = "❌ Phase A CT Reversed (FM4)"
p_aw.font.size = Pt(14)
p_aw.font.bold = True
p_aw.font.color.rgb = RED_CRITICAL

if os.path.exists("presentation_assets/ct_polarity_reversed.png"):
    slide6.shapes.add_picture("presentation_assets/ct_polarity_reversed.png", Inches(7.0), Inches(2.4), width=Inches(5.3))

tb_aw_desc = slide6.shapes.add_textbox(Inches(7.0), Inches(5.6), Inches(5.3), Inches(1.2))
tf_awd = tb_aw_desc.text_frame
tf_awd.word_wrap = True
p_ad = tf_awd.paragraphs[0]
p_ad.text = "• Red line (Phase A) stays below zero (< 0A) all night!\n• Triggers Priority 4 (Failure Mode 4)\n• Action: Dispatch crew to swap Phase A leads at terminal"
p_ad.font.size = Pt(11)
p_ad.font.color.rgb = DARK_SLATE

set_speaker_notes(slide6, """Point out the visual proof:
'Look at the two charts. On the left, in a normal transformer, all 3 phase currents stay positive at night.
On the right, notice the red line for Phase A: it stays completely negative under the zero line all night! The system detects this immediately and tells the crew exactly which wire to swap.'""")


# ==============================================================================
# SLIDE 7: DAILY LOAD PROFILE & SOLAR DUCK CURVE
# ==============================================================================
slide7 = prs.slides.add_slide(blank_layout)
add_header(slide7, "Daily Load Profile & Rooftop Solar Duck Curve", "TRANSFORMER LOADING")

load_fig_path = "presentation_assets/diurnal_load.png"
if os.path.exists(load_fig_path):
    slide7.shapes.add_picture(load_fig_path, Inches(0.8), Inches(1.8), width=Inches(6.2))

card_load_text = add_card(slide7, Inches(7.3), Inches(1.8), Inches(5.2), Inches(5.2))
tb_ld = slide7.shapes.add_textbox(Inches(7.5), Inches(2.0), Inches(4.8), Inches(4.8))
tf_ld = tb_ld.text_frame
tf_ld.word_wrap = True

p_l1 = tf_ld.paragraphs[0]
p_l1.text = "Key Load Landmarks (24 Hours):"
p_l1.font.size = Pt(16)
p_l1.font.bold = True
p_l1.font.color.rgb = NAVY_PRIMARY

load_points = [
    ("Net Load Formula:", "Net Load (kVA) = Import kVA - Export kVA"),
    ("1. Morning Peak (8:30 – 10:30):", "Businesses open and domestic use ramps up."),
    ("2. Solar Dip (11:30 – 14:00):", "Solar export creates the 'duck curve' trough, relieving transformer strain during midday."),
    ("3. Evening Peak (18:30 – 21:00):", "Zero solar contribution. Domestic lighting & cooking create the true maximum daily load!"),
    ("Capacity Assessment:", "Compares peak demand to rating (160 kVA). Tells the utility if transformer is safe or overloaded.")
]

for t, d in load_points:
    p = tf_ld.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_ld.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

set_speaker_notes(slide7, """Explain the load profile simply:
'Here is the 24-hour curve. Around noon, solar dips the load down—that is the duck curve. But at 7 PM, the sun is gone and lights turn on, causing the true daily peak. The dashboard checks if this peak exceeds the transformer rating.'""")


# ==============================================================================
# SLIDE 8: VOLTAGE RULES & SENSOR HEALTH
# ==============================================================================
slide8 = prs.slides.add_slide(blank_layout)
add_header(slide8, "Voltage Limits (230V ± 6%) & Sensor Diagnostics", "POWER QUALITY")

card_v_text = add_card(slide8, Inches(0.8), Inches(1.8), Inches(5.8), Inches(5.2))
tb_vt = slide8.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.4), Inches(4.8))
tf_vt = tb_vt.text_frame
tf_vt.word_wrap = True

p_v1 = tf_vt.paragraphs[0]
p_v1.text = "Statutory Limits & Smart Filtering:"
p_v1.font.size = Pt(16)
p_v1.font.bold = True
p_v1.font.color.rgb = NAVY_PRIMARY

volt_rules = [
    ("Standard Statutory Voltage:", "230 V nominal (± 6% range: 216.2 V to 243.8 V)."),
    ("Quality Benchmarks:", "• Under 1%: Optimal (Green)\n• 1% to 5%: Warning (Yellow)\n• Over 5%: Critical (Red) requiring line upgrades!"),
    ("Real Power Cut vs Broken Sensor:", "• All 3 phases = 0V: Real power outage (logs total blackout hours).\n• Only 1 phase = 0V: Blown sensor fuse or loose clip! Filtered out so it does NOT drag down line averages."),
    ("Per-Phase Reporting:", "Checks Phase A, B, and C individually to catch unbalance.")
]

for t, d in volt_rules:
    p = tf_vt.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_vt.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

v_fig_path = "presentation_assets/network_voltage.png"
if os.path.exists(v_fig_path):
    slide8.shapes.add_picture(v_fig_path, Inches(6.8), Inches(1.8), width=Inches(5.7))
    add_screenshot_placeholder(
        slide8,
        Inches(6.8), Inches(4.9), Inches(5.7), Inches(2.1),
        "Tab 3: HV & LV Violation Tables",
        "WHAT TO SCREENSHOT: Tab 3 ('Voltage Profile & Violations') showing Table 1 (HV) and Table 2 (LV & Outages)."
    )

set_speaker_notes(slide8, """Explain voltage limits simply:
'Voltage must stay between 216.2V and 243.8V.
A smart feature here is how we handle zero readings: if all 3 phases drop to zero, that is a blackout. But if only one phase drops to zero, that is just a loose wire on the meter. Our dashboard filters it out so it doesn't give fake low voltage warnings.'""")


# ==============================================================================
# SLIDE 9: FEEDER NETWORK TOPOLOGY (SLD)
# ==============================================================================
slide9 = prs.slides.add_slide(blank_layout)
add_header(slide9, "Visual Network Map & Solar Distribution (SLD)", "FEEDER TOPOLOGY")

sch_fig_path = "presentation_assets/schematic.png"
if os.path.exists(sch_fig_path):
    slide9.shapes.add_picture(sch_fig_path, Inches(0.8), Inches(1.8), width=Inches(6.8))

card_topo = add_card(slide9, Inches(7.8), Inches(1.8), Inches(4.7), Inches(5.2))
tb_tp = slide9.shapes.add_textbox(Inches(8.0), Inches(2.0), Inches(4.3), Inches(4.8))
tf_tp = tb_tp.text_frame
tf_tp.word_wrap = True

p_tp1 = tf_tp.paragraphs[0]
p_tp1.text = "Electrical Diagram Features:"
p_tp1.font.size = Pt(16)
p_tp1.font.bold = True
p_tp1.font.color.rgb = NAVY_PRIMARY

topo_points = [
    ("Standard Electrical Symbols:", "Central transformer shown with interlocking winding circles (IEC 60617)."),
    ("Feeder Corridors & Spurs:", "Main feeders run horizontally. Lateral spurs branch at 45° angles without overlapping lines."),
    ("Meter Locations:", "Cyan diamonds show meters in the middle (F1M, F2M) and ends (F1, F2)."),
    ("Solar Clusters:", "Amber circles show solar installations, sized by customer capacity (kW)."),
    ("Special Poles Only View:", "Hides intermediate poles to keep the map clean and easy to read for managers.")
]

for t, d in topo_points:
    p = tf_tp.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_tp.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

set_speaker_notes(slide9, """Explain the diagram:
'Instead of messy spreadsheets, our dashboard draws the whole network as a clean Single-Line Diagram. You can see the transformer, the feeder branches, where meters are placed, and where solar customers are located.'""")


# ==============================================================================
# SLIDE 10: SECTIONAL LOCALIZATION (SAVING CAPEX)
# ==============================================================================
slide10 = prs.slides.add_slide(blank_layout)
add_header(slide10, "Pinpointing Voltage Drops: Middle vs. End Meter", "SAVE MONEY")

delta_fig_path = "presentation_assets/voltage_delta.png"
if os.path.exists(delta_fig_path):
    slide10.shapes.add_picture(delta_fig_path, Inches(0.8), Inches(1.8), width=Inches(6.2))

card_sec = add_card(slide10, Inches(7.3), Inches(1.8), Inches(5.2), Inches(5.2))
tb_sc = slide10.shapes.add_textbox(Inches(7.5), Inches(2.0), Inches(4.8), Inches(4.8))
tf_sc = tb_sc.text_frame
tf_sc.word_wrap = True

p_sc1 = tf_sc.paragraphs[0]
p_sc1.text = "Where is the Voltage Dropping?"
p_sc1.font.size = Pt(16)
p_sc1.font.bold = True
p_sc1.font.color.rgb = NAVY_PRIMARY

sec_points = [
    ("The Question:", "When the end of a feeder has low voltage, do you need to upgrade the entire line?"),
    ("Case 1: Outer Branch Drop (Saves Money!):", "If Middle Meter is normal (>225V) and only End Meter is low (<216.2V), the main line is healthy! Upgrade ONLY the outer branch. Do NOT touch the main line!"),
    ("Case 2: Main Line Drop:", "If Middle Meter is already low, the main trunk is constrained. Reconductoring or tap changing the substation is needed."),
    ("Measured Drop (ΔV):", "ΔV = V_Feeder - V_Transformer tracked across 24 hours.")
]

for t, d in sec_points:
    p = tf_sc.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_sc.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

set_speaker_notes(slide10, """Highlight cost savings:
'This slide shows how our system saves LECO money. By comparing the middle meter to the end meter, we find the exact pole span causing the voltage drop. If the middle is fine, LECO only fixes the outer branch—saving hundreds of thousands of rupees in unnecessary conductor replacement.'""")


# ==============================================================================
# SLIDE 11: MITIGATION: LOW VOLTAGE SOLUTIONS
# ==============================================================================
slide11 = prs.slides.add_slide(blank_layout)
add_header(slide11, "Engineering Fixes: Low Voltage (< 216.2 V)", "MITIGATION SOLUTIONS")

col_w = Inches(3.7)

c1 = add_card(slide11, Inches(0.8), Inches(1.8), col_w, Inches(5.2), bg_color=CARD_BG)
tb1 = slide11.shapes.add_textbox(Inches(1.0), Inches(2.0), col_w - Inches(0.4), Inches(4.8))
tf1 = tb1.text_frame
tf1.word_wrap = True
p1 = tf1.paragraphs[0]
p1.text = "1. Phase Load Balancing"
p1.font.size = Pt(16)
p1.font.bold = True
p1.font.color.rgb = GREEN_SUCCESS
p1_sub = tf1.add_paragraph()
p1_sub.text = "Zero Capital Cost (Operational)"
p1_sub.font.size = Pt(12)
p1_sub.font.italic = True
p1_sub.font.color.rgb = MUTED_GRAY

b1_pts = [
    "When: Only 1 phase is low (e.g. Phase A < 216V while B & C are fine).",
    "Action: Rebalance customer service drops.",
    "Move single-phase customers from Phase A to healthy Phases B and C.",
    "Result: Instantly fixes low voltage without buying new equipment!"
]
for pt in b1_pts:
    p = tf1.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(8)

c2 = add_card(slide11, Inches(4.8), Inches(1.8), col_w, Inches(5.2), bg_color=CARD_BG)
tb2 = slide11.shapes.add_textbox(Inches(5.0), Inches(2.0), col_w - Inches(0.4), Inches(4.8))
tf2 = tb2.text_frame
tf2.word_wrap = True
p2 = tf2.paragraphs[0]
p2.text = "2. Feeder Line Upgrades"
p2.font.size = Pt(16)
p2.font.bold = True
p2.font.color.rgb = BLUE_ACCENT
p2_sub = tf2.add_paragraph()
p2_sub.text = "When All Phases Drop at End"
p2_sub.font.size = Pt(12)
p2_sub.font.italic = True
p2_sub.font.color.rgb = MUTED_GRAY

b2_pts = [
    "Short Feeder (≤ 10 poles): Build an Express Feeder direct from substation to the load center.",
    "Long Feeder (> 10 poles): Install a new substation or reconductor with larger 70mm² / 95mm² Aerial Bundled Conductor (ABC).",
    "Result: Permanently eliminates line resistance drop."
]
for pt in b2_pts:
    p = tf2.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(8)

c3 = add_card(slide11, Inches(8.8), Inches(1.8), col_w, Inches(5.2), bg_color=CARD_BG)
tb3 = slide11.shapes.add_textbox(Inches(9.0), Inches(2.0), col_w - Inches(0.4), Inches(4.8))
tf3 = tb3.text_frame
tf3.word_wrap = True
p3 = tf3.paragraphs[0]
p3.text = "3. Transformer Tap Change"
p3.font.size = Pt(16)
p3.font.bold = True
p3.font.color.rgb = NAVY_PRIMARY
p3_sub = tf3.add_paragraph()
p3_sub.text = "When Whole Network is Low"
p3_sub.font.size = Pt(12)
p3_sub.font.italic = True
p3_sub.font.color.rgb = MUTED_GRAY

b3_pts = [
    "When: Substation bus AND all feeder ends are low at the same time.",
    "Step 1: Check upstream 11 kV grid.",
    "Step 2: Raise Off-Circuit Tap Changer (OCTC) to Tap 3 or Tap 4 (+2.5% to +5% boost).",
    "Result: Lifts busbar voltage by 5.7V to 11.5V, bringing all feeders into compliance!"
]
for pt in b3_pts:
    p = tf3.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(8)

set_speaker_notes(slide11, """Explain low voltage solutions simply:
'Here is how we fix low voltage:
1. If only 1 phase is low, do Phase Balancing: move customers to the other phases. Zero cost!
2. If all phases are low on a short feeder, run an Express Feeder.
3. If everything is low, raise the transformer tap to Tap 3 or 4 to give an immediate 6 to 11 volt boost.'""")


# ==============================================================================
# SLIDE 12: MITIGATION: SOLAR OVERVOLTAGE SOLUTIONS
# ==============================================================================
slide12 = prs.slides.add_slide(blank_layout)
add_header(slide12, "Engineering Fixes: Solar High Voltage (> 243.8 V)", "SOLAR SOLUTIONS")

card_hv = add_card(slide12, Inches(0.8), Inches(1.8), Inches(5.8), Inches(5.2))
tb_hv = slide12.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.4), Inches(4.8))
tf_hv = tb_hv.text_frame
tf_hv.word_wrap = True

p_h1 = tf_hv.paragraphs[0]
p_h1.text = "Solar Voltage Rise & Fixes:"
p_h1.font.size = Pt(16)
p_h1.font.bold = True
p_h1.font.color.rgb = NAVY_PRIMARY

hv_points = [
    ("Why Voltage Rises:", "Reverse solar power pushing back through high wire resistance causes voltage to rise above 243.8V."),
    ("1. Rebalance Solar Inverters:", "If 1 phase has high voltage, single-phase solar inverters are crowded on that phase. Move some inverters to other phases."),
    ("2. Parallel Feedering (Best Solution!):", "String a second wire along the same poles. Halving resistance cuts the solar voltage rise in half—with ZERO customer power cuts!"),
    ("3. Smart Inverter Settings (IEEE 1547):", "Turn on Volt-VAr mode so inverters absorb reactive power at midday."),
    ("4. Lower Tap (Tap 1 or 2):", "If voltage is high even at night, lower transformer tap.")
]

for t, d in hv_points:
    p = tf_hv.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_hv.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

add_screenshot_placeholder(
    slide12,
    Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.2),
    "Tab 6: High Voltage & Parallel Feedering",
    "WHAT TO SCREENSHOT:\n"
    "1. Open Tab 6 ('Solutions & Mitigation Advisory')\n"
    "2. Scroll to Section 4: High Voltage Action Plan\n"
    "3. Capture the 'Parallel Feedering' recommendation box\n\n"
    "TALKING POINT:\n"
    "Parallel Feedering strings a 2nd conductor on the existing poles with zero customer downtime!"
)

set_speaker_notes(slide12, """Explain solar overvoltage simply:
'When solar pushes power backwards, line voltage rises. If it passes 243.8V, solar inverters trip off.
Our recommended fix is Parallel Feedering: we run a second wire along the existing poles. That cuts line resistance in half and cuts voltage rise in half, without cutting power to customers!'""")


# ==============================================================================
# SLIDE 13: MASTER PRIORITIZED ACTION MATRIX
# ==============================================================================
slide13 = prs.slides.add_slide(blank_layout)
add_header(slide13, "Master Engineering Action Plan: Who Does What", "ACTION MATRIX")

card_mat = add_card(slide13, Inches(0.8), Inches(1.8), Inches(6.0), Inches(5.2))
tb_mat = slide13.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.6), Inches(4.8))
tf_mat = tb_mat.text_frame
tf_mat.word_wrap = True

p_m1 = tf_mat.paragraphs[0]
p_m1.text = "Prioritized Action Hierarchy:"
p_m1.font.size = Pt(16)
p_m1.font.bold = True
p_m1.font.color.rgb = NAVY_PRIMARY

matrix_summary = [
    ("Priority 1: Fix CT Wiring (Field Crew)", "Target: Substation T/F\nAction: Swap reversed secondary wires at NMD terminal block. (Transformer capacity check blocked until done)."),
    ("Priority 2: Upgrade Transformer (If Overloaded)", "Target: Substation Transformer\nAction: Upgrade capacity (e.g. 160 kVA → 250 kVA) or build new substation to deload branches."),
    ("Priority 3: Fix Feeder Voltage (Lines Team)", "Target: Feeder Branches\nAction: Phase load balancing, Parallel Feedering, Express Feeder, or Tap Changer adjustment."),
    ("Priority 4: Meter Maintenance (Metering Team)", "Target: Faulty NMD Sensors\nAction: Replace blown sensor fuses or fix disconnected crocodile clips.")
]

for t, d in matrix_summary:
    p = tf_mat.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_mat.add_paragraph()
    pd.text = d
    pd.font.size = Pt(11)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

add_screenshot_placeholder(
    slide13,
    Inches(7.1), Inches(1.8), Inches(5.4), Inches(5.2),
    "Tab 6: Action Matrix & CSV Download",
    "WHAT TO SCREENSHOT:\n"
    "1. Open Tab 6 ('Solutions & Mitigation Advisory')\n"
    "2. Scroll down to Section 6: 'Master Action Matrix'\n"
    "3. Capture the table showing Priority, Target, Problem, Action, and the 'Download CSV' button\n\n"
    "TALKING POINT:\n"
    "Engineers can click 'Download CSV' to print work orders for field crews immediately!"
)

set_speaker_notes(slide13, """Explain the Action Matrix:
'At the bottom of Tab 6, all findings are organized into a prioritized action plan:
- Priority 1: Fix CT wiring first.
- Priority 2: Fix transformer overload.
- Priority 3: Fix low or high voltage on lines.
- Priority 4: Replace blown meter fuses.
You can download this table as a CSV with one click.'""")


# ==============================================================================
# SLIDE 14: OFFICIAL WORD REPORT GENERATOR (.DOCX)
# ==============================================================================
slide14 = prs.slides.add_slide(blank_layout)
add_header(slide14, "Official LECO Word Report in 1 Click (.docx)", "AUTOMATED REPORTING")

card_rep = add_card(slide14, Inches(0.8), Inches(1.8), Inches(5.8), Inches(5.2))
tb_rp = slide14.shapes.add_textbox(Inches(1.0), Inches(2.0), Inches(5.4), Inches(4.8))
tf_rp = tb_rp.text_frame
tf_rp.word_wrap = True

p_r1 = tf_rp.paragraphs[0]
p_r1.text = "Official Proposal Document Format:"
p_r1.font.size = Pt(16)
p_r1.font.bold = True
p_r1.font.color.rgb = NAVY_PRIMARY

rep_sections = [
    ("Section 1: Project Identification", "Branch, CSC, Transformer ID, Pole ID, and kVA rating."),
    ("Section 2: Background Information", "Existing network condition, feeder lengths, total solar kW."),
    ("Section 3: Analysis & Justification", "Full engineering writeup with high-resolution figures embedded:\n"
     "• 24-Hour Net Load & Duck Curve chart\n"
     "• CT Polarity check curves\n"
     "• 24-Hour Voltage profiles\n"
     "• Feeder Network Map (SLD)"),
    ("Section 4: Scope of Proposed Works", "Itemized table of conductor upgrades, phase balancing, and pole spans."),
    ("Section 5: Official Sign-Off Block", "Signature lines for Design Engineer, Area Engineer, and Operations Manager.")
]

for t, d in rep_sections:
    p = tf_rp.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(8)

    pd = tf_rp.add_paragraph()
    pd.text = d
    pd.font.size = Pt(11)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

add_screenshot_placeholder(
    slide14,
    Inches(6.8), Inches(1.8), Inches(5.7), Inches(5.2),
    "Official Proposal Report (.docx)",
    "WHAT TO SCREENSHOT:\n"
    "1. Click 'Download Proposal Justification Report (.docx)' at the top of the dashboard\n"
    "2. Open the downloaded Word document\n"
    "3. Take a screenshot showing the official LECO tables and embedded figures\n\n"
    "TALKING POINT:\n"
    "Generates the full official submission document ready for management approval in 5 seconds!"
)

set_speaker_notes(slide14, """Highlight the Word report:
'At the end of the day, engineers have to submit formal paperwork to management. With one click, our dashboard writes the entire official LECO Proposal Justification Report in Microsoft Word. What used to take half a day to write is done in 5 seconds.'""")


# ==============================================================================
# SLIDE 15: CASE STUDY: TRANSFORMER BZ5504
# ==============================================================================
slide15 = prs.slides.add_slide(blank_layout)
add_header(slide15, "Real Case Study: Transformer BZ5504", "RESULTS & FINDINGS")

col_kpi_w = Inches(2.7)
kpi_data = [
    ("CT Wiring Audit", "100% Correct", "Safe State Verified (All 2,880 readings)", GREEN_SUCCESS),
    ("Peak Load", "58.2 kVA", "36.4% Loading on 160 kVA (102 kVA Headroom)", GREEN_SUCCESS),
    ("Solar Size", "26.8 kW", "6 Connected Solar Customer Sites", BLUE_ACCENT),
    ("Voltage Status", "Actionable", "Feeder 1 outer drop & Feeder 2 solar rise", AMBER_WARNING)
]

for idx, (label, val, sub, col) in enumerate(kpi_data):
    k_card = add_card(slide15, Inches(0.8 + idx * 2.95), Inches(1.8), col_kpi_w, Inches(1.5), bg_color=CARD_BG)
    tb_k = slide15.shapes.add_textbox(Inches(0.9 + idx * 2.95), Inches(1.9), col_kpi_w - Inches(0.2), Inches(1.3))
    tf_k = tb_k.text_frame
    tf_k.word_wrap = True
    p0 = tf_k.paragraphs[0]
    p0.text = label.upper()
    p0.font.size = Pt(11)
    p0.font.bold = True
    p0.font.color.rgb = MUTED_GRAY

    p1 = tf_k.add_paragraph()
    p1.text = val
    p1.font.size = Pt(22)
    p1.font.bold = True
    p1.font.color.rgb = col
    p1.space_before = Pt(2)

    p2 = tf_k.add_paragraph()
    p2.text = sub
    p2.font.size = Pt(10)
    p2.font.color.rgb = DARK_SLATE
    p2.space_before = Pt(2)

card_findings = add_card(slide15, Inches(0.8), Inches(3.55), Inches(11.733), Inches(3.45))
tb_fnd = slide15.shapes.add_textbox(Inches(1.0), Inches(3.75), Inches(11.3), Inches(3.05))
tf_fn = tb_fnd.text_frame
tf_fn.word_wrap = True

p_fn1 = tf_fn.paragraphs[0]
p_fn1.text = "Key Findings for Substation BZ5504:"
p_fn1.font.size = Pt(16)
p_fn1.font.bold = True
p_fn1.font.color.rgb = NAVY_PRIMARY

bz_points = [
    ("1. CT Wiring is Correct:", "Nighttime currents are strictly positive import. Apparent power and capacity readings are 100% valid."),
    ("2. Transformer Has Plenty of Capacity:", "Peak load is only 58.2 kVA on a 160 kVA transformer (36% loaded). NO expensive transformer upgrade needed!"),
    ("3. Feeder 1 (Wanarathana Mawatha):", "Low voltage occurs only on the outer branch between middle meter and end meter. Action: Phase load balancing on outer poles."),
    ("4. Feeder 2 (Panvila Side):", "Midday solar voltage rise detected. Action: Rebalance single-phase solar inverters across phases.")
]

for t, d in bz_points:
    p = tf_fn.add_paragraph()
    p.text = "• " + t
    p.font.size = Pt(13)
    p.font.bold = True
    p.font.color.rgb = BLUE_ACCENT
    p.space_before = Pt(7)

    pd = tf_fn.add_paragraph()
    pd.text = d
    pd.font.size = Pt(12)
    pd.font.color.rgb = DARK_SLATE
    pd.space_before = Pt(2)

set_speaker_notes(slide15, """Discuss the real case study:
'Here are the real results for Transformer BZ5504.
The dashboard verified that CT wiring is 100% correct.
The transformer is only 36% loaded, so LECO does not need to spend money upgrading it.
However, Feeder 1 has evening low voltage in its outer section, and Feeder 2 has midday solar overvoltage.
Our dashboard gave the exact targeted fixes in seconds.'""")


# ==============================================================================
# SLIDE 16: CONCLUSION & VALUE FOR LECO
# ==============================================================================
slide16 = prs.slides.add_slide(blank_layout)
add_header(slide16, "Conclusion: Real Value for LECO", "SUMMARY & Q&A")

col_o_w = Inches(3.7)

co1 = add_card(slide16, Inches(0.8), Inches(1.8), col_o_w, Inches(4.5), bg_color=CARD_BG)
tbo1 = slide16.shapes.add_textbox(Inches(1.0), Inches(2.0), col_o_w - Inches(0.4), Inches(4.1))
tfo1 = tbo1.text_frame
tfo1.word_wrap = True
po1 = tfo1.paragraphs[0]
po1.text = "⚡ 95% Time Savings"
po1.font.size = Pt(17)
po1.font.bold = True
po1.font.color.rgb = NAVY_PRIMARY

c1_txt = [
    "Replaces hours of Excel work with instant 1-click analysis",
    "Eliminates human calculation errors",
    "Lets engineers evaluate dozens of substations per week instead of just one"
]
for pt in c1_txt:
    p = tfo1.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12.5)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(10)

co2 = add_card(slide16, Inches(4.8), Inches(1.8), col_o_w, Inches(4.5), bg_color=CARD_BG)
tbo2 = slide16.shapes.add_textbox(Inches(5.0), Inches(2.0), col_o_w - Inches(0.4), Inches(4.1))
tfo2 = tbo2.text_frame
tfo2.word_wrap = True
po2 = tfo2.paragraphs[0]
po2.text = "💰 Big CapEx Savings"
po2.font.size = Pt(17)
po2.font.bold = True
po2.font.color.rgb = GREEN_SUCCESS

c2_txt = [
    "Stops unnecessary transformer upgrades caused by reversed CT readings",
    "Pinpoints exact pole spans so LECO only fixes lines that actually need it",
    "Prioritizes low-cost phase balancing before heavy capital spending"
]
for pt in c2_txt:
    p = tfo2.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12.5)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(10)

co3 = add_card(slide16, Inches(8.8), Inches(1.8), col_o_w, Inches(4.5), bg_color=CARD_BG)
tbo3 = slide16.shapes.add_textbox(Inches(9.0), Inches(2.0), col_o_w - Inches(0.4), Inches(4.1))
tfo3 = tbo3.text_frame
tfo3.word_wrap = True
po3 = tfo3.paragraphs[0]
po3.text = "☀️ Solar Integration"
po3.font.size = Pt(17)
po3.font.bold = True
po3.font.color.rgb = BLUE_ACCENT

c3_txt = [
    "Protects network voltage while adding more customer rooftop solar",
    "Creates official Proposal Reports (.docx) ready for management sign-off",
    "Standardized tool for all LECO branches and engineering teams"
]
for pt in c3_txt:
    p = tfo3.add_paragraph()
    p.text = "• " + pt
    p.font.size = Pt(12.5)
    p.font.color.rgb = DARK_SLATE
    p.space_before = Pt(10)

banner_qa = add_card(slide16, Inches(0.8), Inches(6.5), Inches(11.733), Inches(0.7), bg_color=NAVY_PRIMARY, border_color=NAVY_PRIMARY)
tb_qa = slide16.shapes.add_textbox(Inches(1.0), Inches(6.55), Inches(11.3), Inches(0.6))
tf_qa = tb_qa.text_frame
tf_qa.word_wrap = True
p_q = tf_qa.paragraphs[0]
p_q.text = "Thank You for Your Attention!   •   Questions & Answers / Live Demonstration"
p_q.font.size = Pt(14)
p_q.font.bold = True
p_q.font.color.rgb = RGBColor(255, 255, 255)
p_q.alignment = PP_ALIGN.CENTER

set_speaker_notes(slide16, """Conclude your presentation:
'In conclusion, our dashboard saves 95% of engineering time, stops false equipment purchases by finding CT wiring errors, isolates exact feeder problems, and writes official Word reports in 5 seconds.
Thank you very much. We are now ready for your questions and to show you the live dashboard.'""")

# Save Presentation
output_pptx = "Distribution_Transformer_Analytics_Presentation.pptx"
try:
    prs.save(output_pptx)
    print(f"Presentation successfully updated and saved to: {output_pptx}")
except PermissionError:
    fallback_pptx = "Distribution_Transformer_Analytics_Presentation_Updated.pptx"
    prs.save(fallback_pptx)
    print(f"Main PPTX was open in PowerPoint. Saved updated presentation to: {fallback_pptx}")
