# shared/clinician_report.py
"""
Generates the full clinician CARS2-ST/HF PDF report.
Includes demographics, item table, domain profile chart, QPC summary,
integrated interpretation, and AI-generated clinical narrative.
"""

import io
import math
from datetime import date
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether, PageBreak
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY
from reportlab.graphics.shapes import Drawing, Rect, Line, String, Circle, PolyLine
from reportlab.graphics import renderPDF
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker

# ── Brand palette ────────────────────────────────────────────────────────────
BRAND_DARK   = colors.HexColor("#1B2A4A")
BRAND_BLUE   = colors.HexColor("#2D6BA0")
BRAND_LIGHT  = colors.HexColor("#EAF2FB")
BRAND_GREEN  = colors.HexColor("#27AE60")
BRAND_ORANGE = colors.HexColor("#E67E22")
BRAND_RED    = colors.HexColor("#C0392B")
BRAND_GREY   = colors.HexColor("#7F8C8D")
BRAND_YELLOW = colors.HexColor("#F1C40F")
WHITE        = colors.white

QPC_RATING_LABELS = {
    "0": "Not a problem",
    "1": "Mild-moderate problem",
    "2": "Severe problem",
    "3": "Past problem",
    "9": "Don't know",
}


def _make_styles():
    styles = {}
    styles["title"] = ParagraphStyle(
        "title", fontName="Helvetica-Bold", fontSize=18,
        textColor=WHITE, alignment=TA_CENTER, spaceAfter=2
    )
    styles["subtitle"] = ParagraphStyle(
        "subtitle", fontName="Helvetica", fontSize=10,
        textColor=WHITE, alignment=TA_CENTER, spaceAfter=2
    )
    styles["h1"] = ParagraphStyle(
        "h1", fontName="Helvetica-Bold", fontSize=13,
        textColor=WHITE, alignment=TA_LEFT, spaceAfter=0
    )
    styles["section_header"] = ParagraphStyle(
        "section_header", fontName="Helvetica-Bold", fontSize=12,
        textColor=BRAND_DARK, spaceBefore=10, spaceAfter=4
    )
    styles["body"] = ParagraphStyle(
        "body", fontName="Helvetica", fontSize=9,
        textColor=colors.black, spaceAfter=4, leading=14
    )
    styles["body_j"] = ParagraphStyle(
        "body_j", fontName="Helvetica", fontSize=9,
        textColor=colors.black, spaceAfter=6, leading=14,
        alignment=TA_JUSTIFY
    )
    styles["small"] = ParagraphStyle(
        "small", fontName="Helvetica", fontSize=8,
        textColor=BRAND_GREY, spaceAfter=2
    )
    styles["footer"] = ParagraphStyle(
        "footer", fontName="Helvetica", fontSize=7,
        textColor=BRAND_GREY, alignment=TA_CENTER
    )
    styles["label"] = ParagraphStyle(
        "label", fontName="Helvetica-Bold", fontSize=9,
        textColor=BRAND_DARK
    )
    styles["score_big"] = ParagraphStyle(
        "score_big", fontName="Helvetica-Bold", fontSize=24,
        textColor=BRAND_DARK, alignment=TA_CENTER
    )
    styles["score_label"] = ParagraphStyle(
        "score_label", fontName="Helvetica", fontSize=8,
        textColor=BRAND_GREY, alignment=TA_CENTER
    )
    return styles


# ─────────────────────────────────────────────────────────────────────────────
# CHART: Domain Profile
# ─────────────────────────────────────────────────────────────────────────────

def _build_profile_chart(item_labels, ratings, threshold=2.5):
    """
    Draws a line chart: 15 domain scores vs clinical threshold.
    Returns a Drawing object.
    """
    W, H = 460, 200
    d = Drawing(W, H)

    margin_left = 30
    margin_right = 10
    margin_top = 20
    margin_bottom = 60
    plot_w = W - margin_left - margin_right
    plot_h = H - margin_top - margin_bottom
    n = len(ratings)
    step_x = plot_w / (n - 1) if n > 1 else plot_w

    # Background
    d.add(Rect(margin_left, margin_bottom, plot_w, plot_h,
               fillColor=colors.HexColor("#F8F9FA"), strokeColor=colors.HexColor("#DEE2E6"),
               strokeWidth=0.5))

    # Gridlines y (1,2,3,4)
    for y_val in [1, 1.5, 2, 2.5, 3, 3.5, 4]:
        yp = margin_bottom + (y_val - 1) / 3 * plot_h
        lc = colors.HexColor("#DEE2E6")
        lw = 0.3
        if y_val == threshold:
            lc = BRAND_ORANGE
            lw = 1.2
        d.add(Line(margin_left, yp, margin_left + plot_w, yp,
                   strokeColor=lc, strokeWidth=lw,
                   strokeDashArray=[4, 3] if y_val == threshold else None))
        d.add(String(margin_left - 5, yp - 3, str(y_val),
                     fontSize=6, fillColor=BRAND_GREY, textAnchor="end"))

    # Shade above-threshold region
    thresh_y = margin_bottom + (threshold - 1) / 3 * plot_h
    d.add(Rect(margin_left, thresh_y, plot_w, plot_h - (thresh_y - margin_bottom),
               fillColor=colors.HexColor("#FDECEA"), strokeColor=None, strokeWidth=0))

    # Domain score line + dots
    pts = []
    for i, r in enumerate(ratings):
        xp = margin_left + i * step_x
        yp = margin_bottom + (r - 1) / 3 * plot_h
        pts.append((xp, yp))

    # Draw connecting lines
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        # color segment by severity
        r_avg = (ratings[i] + ratings[i + 1]) / 2
        if r_avg >= 3:
            lc = BRAND_RED
        elif r_avg >= threshold:
            lc = BRAND_ORANGE
        else:
            lc = BRAND_BLUE
        d.add(Line(x1, y1, x2, y2, strokeColor=lc, strokeWidth=2))

    # Dots
    for i, (xp, yp) in enumerate(pts):
        r = ratings[i]
        if r >= 3:
            dc = BRAND_RED
        elif r >= threshold:
            dc = BRAND_ORANGE
        else:
            dc = BRAND_BLUE
        d.add(Circle(xp, yp, 4, fillColor=dc, strokeColor=WHITE, strokeWidth=1))

    # X-axis labels (rotated via small font, abbreviated)
    abbrevs = [lbl[:8] for lbl in item_labels]
    for i, lbl in enumerate(abbrevs):
        xp = margin_left + i * step_x
        # Draw rotated text as a small label below axis
        d.add(String(xp, margin_bottom - 8, str(i + 1),
                     fontSize=7, fillColor=BRAND_DARK, textAnchor="middle"))

    # Legend
    lix = margin_left
    liy = margin_bottom - 28
    # Blue
    d.add(Line(lix, liy, lix + 15, liy, strokeColor=BRAND_BLUE, strokeWidth=2))
    d.add(String(lix + 18, liy - 3, "Below threshold", fontSize=7, fillColor=BRAND_GREY))
    lix2 = lix + 95
    d.add(Line(lix2, liy, lix2 + 15, liy, strokeColor=BRAND_ORANGE, strokeWidth=2))
    d.add(String(lix2 + 18, liy - 3, "Above threshold", fontSize=7, fillColor=BRAND_GREY))
    lix3 = lix2 + 100
    d.add(Line(lix3, liy, lix3 + 15, liy, strokeColor=BRAND_RED, strokeWidth=2))
    d.add(String(lix3 + 18, liy - 3, "Severe", fontSize=7, fillColor=BRAND_GREY))
    lix4 = lix3 + 65
    d.add(Line(lix4, liy, lix4 + 15, liy,
               strokeColor=BRAND_ORANGE, strokeWidth=1.5,
               strokeDashArray=[4, 3]))
    d.add(String(lix4 + 18, liy - 3, "Clinical threshold (2.5)", fontSize=7, fillColor=BRAND_GREY))

    # Axis labels
    d.add(String(margin_left - 22, margin_bottom + plot_h / 2, "Score",
                 fontSize=7, fillColor=BRAND_GREY))

    # Item number reference
    ref_y = 5
    for i, lbl in enumerate(item_labels):
        xp = margin_left + i * step_x
        d.add(String(xp, ref_y, f"{i+1}:{lbl[:6]}", fontSize=5,
                     fillColor=BRAND_GREY, textAnchor="middle"))

    return d


# ─────────────────────────────────────────────────────────────────────────────
# SCORE BOX ROW
# ─────────────────────────────────────────────────────────────────────────────

def _score_summary_table(raw_score, t_score, percentile, severity_info, styles):
    """Creates a 4-box summary row."""
    sev_color = colors.HexColor(severity_info["color"]) if severity_info else BRAND_GREY

    def box(value, label, bg_color=BRAND_LIGHT, val_color=BRAND_DARK):
        inner = Table(
            [[Paragraph(f"<b>{value}</b>", ParagraphStyle(
                "val", fontName="Helvetica-Bold", fontSize=18,
                textColor=val_color, alignment=TA_CENTER))],
             [Paragraph(label, ParagraphStyle(
                 "lbl", fontName="Helvetica", fontSize=7,
                 textColor=BRAND_GREY, alignment=TA_CENTER))]],
            colWidths=[4*cm]
        )
        inner.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), bg_color),
            ("BOX", (0, 0), (-1, -1), 1, BRAND_BLUE),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ]))
        return inner

    sev_label = severity_info["group"] if severity_info else "—"
    row = [[
        box(str(raw_score), "Total Raw Score"),
        box(str(t_score), "T-Score"),
        box(str(percentile), "Percentile"),
        box(sev_label, "Severity Group", bg_color=sev_color, val_color=WHITE),
    ]]
    outer = Table(row, colWidths=[4*cm, 4*cm, 4*cm, 4*cm],
                  hAlign="CENTER")
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return outer


# ─────────────────────────────────────────────────────────────────────────────
# ITEM RATINGS TABLE
# ─────────────────────────────────────────────────────────────────────────────

def _items_table(items_data, ratings, form_type, styles):
    """Full table of all 15 item ratings."""
    header = [
        Paragraph("<b>#</b>", styles["label"]),
        Paragraph("<b>Domain</b>", styles["label"]),
        Paragraph("<b>Rating</b>", styles["label"]),
        Paragraph("<b>Level</b>", styles["label"]),
    ]
    rows = [header]
    for i, item in enumerate(items_data):
        r = ratings[i]
        if r >= 3:
            level = "Moderate–Severe"
            lc = "#C0392B"
        elif r >= 2.5:
            level = "Borderline"
            lc = "#E67E22"
        elif r >= 2:
            level = "Mild"
            lc = "#F39C12"
        else:
            level = "Age-Appropriate"
            lc = "#27AE60"
        rows.append([
            Paragraph(str(item["id"]), styles["body"]),
            Paragraph(item["en"], styles["body"]),
            Paragraph(f"<b>{r}</b>", styles["body"]),
            Paragraph(f'<font color="{lc}"><b>{level}</b></font>', styles["body"]),
        ])
    t = Table(rows, colWidths=[1*cm, 10*cm, 2*cm, 4*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BLUE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (2, 0), (2, -1), "CENTER"),
    ]))
    return KeepTogether([t])


# ─────────────────────────────────────────────────────────────────────────────
# QPC SECTION (if uploaded)
# ─────────────────────────────────────────────────────────────────────────────

def _qpc_section(qpc_data: dict, styles):
    """Renders a QPC summary block inside the clinician report."""
    elements = []
    elements.append(Paragraph("CARS2-QPC: Parent/Caregiver Report", styles["section_header"]))
    elements.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE, spaceAfter=4))
    elements.append(Paragraph(
        "The following data was extracted from the parent/caregiver QPC submission "
        "and is presented here for integrated interpretation. Items marked as "
        "<font color='#C0392B'><b>Severe</b></font> or "
        "<font color='#E67E22'><b>Mild-Moderate</b></font> "
        "should be considered alongside clinician observations.",
        styles["body_j"]
    ))
    elements.append(Spacer(1, 6))

    # Build a compact item list
    header = [
        Paragraph("<b>Item ID</b>", styles["label"]),
        Paragraph("<b>Parent Rating</b>", styles["label"]),
    ]
    rows = [header]
    severe_items = []
    for k in sorted(qpc_data.keys()):
        val = str(qpc_data[k])
        label = QPC_RATING_LABELS.get(val, "—")
        if val == "2":
            lc = "#C0392B"
            severe_items.append(k)
        elif val == "1":
            lc = "#E67E22"
        elif val == "0":
            lc = "#27AE60"
        else:
            lc = "#7F8C8D"
        rows.append([
            Paragraph(k, styles["body"]),
            Paragraph(f'<font color="{lc}"><b>{label}</b></font>', styles["body"]),
        ])
    t = Table(rows, colWidths=[4*cm, 12*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BRAND_DARK),
        ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BLUE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ]))
    elements.append(t)

    if severe_items:
        elements.append(Spacer(1, 6))
        elements.append(Paragraph(
            f"<b>Items rated as Severe by parent/caregiver:</b> {', '.join(severe_items)}",
            styles["body"]
        ))
    return elements


# ─────────────────────────────────────────────────────────────────────────────
# SECTION BANNER HELPER
# ─────────────────────────────────────────────────────────────────────────────

def _section_banner(title, styles):
    t = Table([[Paragraph(title, styles["h1"])]], colWidths=[18*cm])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    return t


# ─────────────────────────────────────────────────────────────────────────────
# MAIN GENERATOR
# ─────────────────────────────────────────────────────────────────────────────

def generate_clinician_pdf(
    child_name: str,
    age: int,
    gender: str,
    dob: str,
    ethnic_bg: str,
    case_id: str,
    rater_name: str,
    info_from: str,
    test_date,
    form_type: str,          # "ST" or "HF"
    items_data: list,
    ratings: list,           # list of 15 floats
    raw_score: float,
    t_score,
    percentile,
    severity_info: dict,
    clinician_notes: str,
    narrative: str,
    qpc_data: dict = None,   # parsed QPC data dict, or None
) -> bytes:

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8*cm, rightMargin=1.8*cm,
        topMargin=2*cm, bottomMargin=2*cm,
        title=f"CARS2-{form_type} Report – {child_name}",
        author="Wijdan Therapy Center",
    )
    styles = _make_styles()
    story = []

    # ── MAIN HEADER BANNER ───────────────────────────────────────────────────
    hdr = Table([[
        Paragraph("Wijdan Therapy Center", styles["title"]),
        Paragraph(
            f"Childhood Autism Rating Scale – 2nd Edition<br/>"
            f"<b>CARS2-{form_type} Clinician Assessment Report</b><br/>"
            f"<font size='9'>Confidential – For clinical use only</font>",
            styles["subtitle"]
        ),
    ]], colWidths=[18*cm])
    hdr.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_DARK),
        ("TOPPADDING", (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(hdr)
    story.append(Spacer(1, 8))

    # ── SECTION 1: DEMOGRAPHICS ──────────────────────────────────────────────
    story.append(_section_banner("1. Demographics", styles))
    story.append(Spacer(1, 6))
    demo_data = [
        [Paragraph("<b>Child Name:</b>", styles["body"]),
         Paragraph(child_name or "—", styles["body"]),
         Paragraph("<b>Test Date:</b>", styles["body"]),
         Paragraph(str(test_date), styles["body"])],
        [Paragraph("<b>Date of Birth:</b>", styles["body"]),
         Paragraph(str(dob) if dob else "—", styles["body"]),
         Paragraph("<b>Age:</b>", styles["body"]),
         Paragraph(f"{age} years", styles["body"])],
        [Paragraph("<b>Gender:</b>", styles["body"]),
         Paragraph(gender or "—", styles["body"]),
         Paragraph("<b>Ethnic Background:</b>", styles["body"]),
         Paragraph(ethnic_bg or "—", styles["body"])],
        [Paragraph("<b>Case ID:</b>", styles["body"]),
         Paragraph(case_id or "—", styles["body"]),
         Paragraph("<b>Rater:</b>", styles["body"]),
         Paragraph(rater_name or "—", styles["body"])],
        [Paragraph("<b>Form Used:</b>", styles["body"]),
         Paragraph(f"CARS2-{form_type}", styles["body"]),
         Paragraph("<b>Information From:</b>", styles["body"]),
         Paragraph(info_from or "Direct observation", styles["body"])],
    ]
    dt = Table(demo_data, colWidths=[3.5*cm, 6.5*cm, 3.5*cm, 4.5*cm])
    dt.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_BLUE),
        ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#BDC3C7")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]))
    story.append(dt)
    story.append(Spacer(1, 10))

    # ── SECTION 2: SCORES ────────────────────────────────────────────────────
    story.append(_section_banner("2. CARS2 Scores & Classification", styles))
    story.append(Spacer(1, 8))
    story.append(_score_summary_table(raw_score, t_score, percentile, severity_info, styles))
    story.append(Spacer(1, 8))

    # Severity description box
    sev_desc = {
        "Minimal-to-No": (
            "The total raw score falls within the <b>Minimal-to-No Symptoms</b> range. "
            "Scores in this range suggest that the behaviors observed are within normal developmental expectations "
            "and do not indicate clinically significant autism spectrum features at this time. "
            "A comprehensive evaluation is not indicated solely on the basis of this score."
        ),
        "Mild-Moderate": (
            "The total raw score falls within the <b>Mild-to-Moderate Symptoms</b> range. "
            "Scores in this range indicate the presence of some features associated with Autism Spectrum Disorder "
            "that are interfering with daily functioning to a mild-to-moderate degree. "
            "A comprehensive evaluation for ASD is recommended."
        ),
        "Severe": (
            "The total raw score falls within the <b>Severe Symptoms</b> range. "
            "Scores in this range indicate significant and pervasive features associated with Autism Spectrum Disorder "
            "that are substantially interfering with daily functioning. "
            "Comprehensive evaluation and intervention planning are strongly recommended."
        ),
    }
    group = severity_info.get("group", "Minimal-to-No") if severity_info else "Minimal-to-No"
    sev_color_hex = severity_info["color"] if severity_info else "#27AE60"
    desc = sev_desc.get(group, "")
    sev_box = Table([[Paragraph(desc, styles["body_j"])]], colWidths=[18*cm])
    sev_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(sev_color_hex + "22")),
        ("BOX", (0, 0), (-1, -1), 1.5, colors.HexColor(sev_color_hex)),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
    ]))
    story.append(sev_box)
    story.append(Spacer(1, 10))

    # ── SECTION 3: DOMAIN PROFILE CHART ─────────────────────────────────────
    story.append(_section_banner("3. Domain Profile Chart", styles))
    story.append(Spacer(1, 6))
    item_labels = [it["en"] for it in items_data]
    chart = _build_profile_chart(item_labels, ratings, threshold=2.5)
    story.append(chart)
    story.append(Spacer(1, 4))
    story.append(Paragraph(
        "<i>Note: Numbers on x-axis correspond to domain numbers in the table below. "
        "Shaded region above the dashed threshold line (2.5) indicates clinically elevated scores.</i>",
        styles["small"]
    ))
    story.append(Spacer(1, 10))

    # ── SECTION 4: ITEM RATINGS TABLE ────────────────────────────────────────
    story.append(_section_banner("4. Item Ratings", styles))
    story.append(Spacer(1, 6))
    story.append(_items_table(items_data, ratings, form_type, styles))
    story.append(Spacer(1, 10))

    # ── SECTION 5: QPC (if available) ────────────────────────────────────────
    if qpc_data:
        story.append(_section_banner("5. QPC Parent/Caregiver Report", styles))
        story.append(Spacer(1, 6))
        for el in _qpc_section(qpc_data, styles):
            story.append(el)
        story.append(Spacer(1, 10))

    # ── SECTION 6: INTEGRATED INTERPRETATION ─────────────────────────────────
    sec_num = 6 if qpc_data else 5
    story.append(_section_banner(f"{sec_num}. Integrated Interpretation", styles))
    story.append(Spacer(1, 6))

    # Elevations
    elevated = [(items_data[i]["en"], ratings[i]) for i in range(len(ratings)) if ratings[i] >= 2.5]
    story.append(Paragraph(
        f"<b>Clinician-rated domains at or above clinical threshold (≥2.5):</b> "
        f"{len(elevated)} of 15 domains",
        styles["body"]
    ))
    if elevated:
        elev_text = "; ".join([f"{n} ({r})" for n, r in elevated])
        story.append(Paragraph(f"Elevated: {elev_text}", styles["body"]))

    if qpc_data:
        parent_severe = [k for k, v in qpc_data.items() if str(v) == "2"]
        parent_mild   = [k for k, v in qpc_data.items() if str(v) == "1"]
        story.append(Spacer(1, 4))
        story.append(Paragraph(
            f"<b>Parent-reported severe items:</b> {len(parent_severe)}  |  "
            f"<b>Mild-moderate items:</b> {len(parent_mild)}",
            styles["body"]
        ))
        if len(elevated) > 3 and len(parent_severe) > 3:
            agreement = "Both clinician ratings and parent report indicate significant areas of concern, suggesting cross-setting consistency."
        elif len(elevated) > 3 and len(parent_severe) <= 1:
            agreement = "Clinician observations revealed elevated scores in several domains; however, parent report did not identify corresponding severe concerns. This discrepancy warrants further exploration."
        elif len(elevated) <= 2 and len(parent_severe) > 3:
            agreement = "Parent report identified several severe concerns, while clinician ratings were generally lower. Possible differences between home and clinical settings should be explored."
        else:
            agreement = "Clinician ratings and parent report are broadly consistent."
        story.append(Paragraph(agreement, styles["body_j"]))

    story.append(Spacer(1, 10))

    # ── SECTION 7: CLINICAL NARRATIVE ────────────────────────────────────────
    sec_num2 = sec_num + 1
    story.append(_section_banner(f"{sec_num2}. AI-Assisted Clinical Narrative", styles))
    story.append(Spacer(1, 6))
    story.append(Paragraph(
        "<i>The following narrative was generated with AI assistance based on the assessment data "
        "and is intended to support — not replace — clinical judgment. It should be reviewed "
        "and edited by the responsible clinician before inclusion in any formal report.</i>",
        styles["small"]
    ))
    story.append(Spacer(1, 6))
    # Split narrative into paragraphs
    for para in narrative.split("\n\n"):
        if para.strip():
            story.append(Paragraph(para.strip(), styles["body_j"]))
            story.append(Spacer(1, 4))

    # ── CLINICIAN NOTES ───────────────────────────────────────────────────────
    if clinician_notes and clinician_notes.strip():
        story.append(Spacer(1, 8))
        story.append(Paragraph("Clinician's Observations", styles["section_header"]))
        story.append(HRFlowable(width="100%", thickness=1, color=BRAND_BLUE, spaceAfter=4))
        story.append(Paragraph(clinician_notes, styles["body_j"]))

    # ── DISCLAIMER ────────────────────────────────────────────────────────────
    story.append(Spacer(1, 12))
    disc = (
        "<b>Disclaimer:</b> The CARS-2 (Childhood Autism Rating Scale, 2nd Edition) is a copyrighted "
        "instrument (© Western Psychological Services). This report is for clinical use only "
        "and must be interpreted by a qualified professional. The CARS-2 does not provide a "
        "definitive diagnosis of Autism Spectrum Disorder in isolation. Diagnosis requires a "
        "comprehensive evaluation including developmental history, multiple information sources, "
        "and assessment by an authorized clinician."
    )
    disc_box = Table([[Paragraph(disc, styles["small"])]], colWidths=[18*cm])
    disc_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F8F9FA")),
        ("BOX", (0, 0), (-1, -1), 0.5, BRAND_GREY),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(disc_box)

    # ── FOOTER ────────────────────────────────────────────────────────────────
    story.append(Spacer(1, 8))
    story.append(HRFlowable(width="100%", thickness=0.5, color=BRAND_GREY, spaceAfter=4))
    story.append(Paragraph(
        f"CARS2-{form_type} Assessment Report  |  {child_name}  |  "
        f"Generated: {date.today().strftime('%B %d, %Y')}  |  "
        "Wijdan Therapy Center  |  Confidential",
        styles["footer"]
    ))

    doc.build(story)
    buf.seek(0)
    return buf.read()
