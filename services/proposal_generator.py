# python-lead-engine/services/proposal_generator.py

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    HRFlowable, KeepTogether
)
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT
from io import BytesIO
from datetime import datetime
from typing import Optional, List


# ── Brand Colors ──────────────────────────────────────────────────────────────
INDIGO       = colors.HexColor("#4f46e5")
INDIGO_LIGHT = colors.HexColor("#eef2ff")
INDIGO_DARK  = colors.HexColor("#3730a3")
INK_900      = colors.HexColor("#0a0a0f")
INK_700      = colors.HexColor("#1c1c27")
INK_500      = colors.HexColor("#44445a")
INK_200      = colors.HexColor("#c4c4d4")
INK_50       = colors.HexColor("#f4f4f8")
WHITE        = colors.white
EMERALD      = colors.HexColor("#059669")
AMBER        = colors.HexColor("#d97706")
RED          = colors.HexColor("#ef4444")


def _styles():
    base = getSampleStyleSheet()

    return {
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=26,
            textColor=WHITE, leading=32, spaceAfter=4,
        ),
        "h1_sub": ParagraphStyle(
            "h1_sub", fontName="Helvetica", fontSize=12,
            textColor=colors.HexColor("#c7d2fe"), leading=16,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=14,
            textColor=INDIGO_DARK, leading=18, spaceBefore=6, spaceAfter=4,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="Helvetica-Bold", fontSize=11,
            textColor=INK_700, leading=15, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", fontName="Helvetica", fontSize=10,
            textColor=INK_700, leading=15, spaceAfter=4,
        ),
        "body_sm": ParagraphStyle(
            "body_sm", fontName="Helvetica", fontSize=9,
            textColor=INK_500, leading=13,
        ),
        "label": ParagraphStyle(
            "label", fontName="Helvetica-Bold", fontSize=8,
            textColor=INK_500, leading=11,
            spaceAfter=2, spaceBefore=0,
        ),
        "tag": ParagraphStyle(
            "tag", fontName="Helvetica-Bold", fontSize=9,
            textColor=INDIGO, leading=12,
        ),
        "footer": ParagraphStyle(
            "footer", fontName="Helvetica", fontSize=8,
            textColor=INK_500, leading=11, alignment=TA_CENTER,
        ),
        "price": ParagraphStyle(
            "price", fontName="Helvetica-Bold", fontSize=18,
            textColor=INDIGO, leading=22,
        ),
        "total": ParagraphStyle(
            "total", fontName="Helvetica-Bold", fontSize=13,
            textColor=WHITE, leading=17, alignment=TA_RIGHT,
        ),
    }


def _header_block(story, styles, company_name: str, prepared_for: str, ref: str):
    """Dark indigo header banner."""
    header_data = [[
        Paragraph(f"Proposal for<br/><b>{prepared_for or company_name}</b>", styles["h1"]),
        Paragraph(
            f"Ref: {ref}<br/>{datetime.now().strftime('%d %B %Y')}",
            ParagraphStyle("hdr_r", fontName="Helvetica", fontSize=10,
                           textColor=colors.HexColor("#c7d2fe"),
                           leading=15, alignment=TA_RIGHT)
        ),
    ]]
    tbl = Table(header_data, colWidths=[110*mm, 70*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), INDIGO),
        ("TOPPADDING",    (0, 0), (-1, -1), 18),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 18),
        ("LEFTPADDING",   (0, 0), (0, -1), 22),
        ("RIGHTPADDING",  (-1, 0), (-1, -1), 22),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 6*mm))


def _section_title(story, styles, title: str):
    story.append(Paragraph(title.upper(), styles["h2"]))
    story.append(HRFlowable(width="100%", thickness=1, color=INDIGO_LIGHT, spaceAfter=4))


def _info_grid(story, styles, lead: dict):
    """2-column company info grid."""
    _section_title(story, styles, "Client Overview")

    def cell(label, val):
        return [
            Paragraph(label, styles["label"]),
            Paragraph(str(val) if val else "—", styles["body"]),
        ]

    rows = [
        [cell("COMPANY", lead.get("company_name", "")),
         cell("COUNTRY", lead.get("country", ""))],
        [cell("WEBSITE", lead.get("website", "")),
         cell("EMAIL", lead.get("email", ""))],
        [cell("LEAD SCORE", f"{lead.get('score', 0)} / 100"),
         cell("TAG", (lead.get("tag") or "unscored").upper())],
    ]

    flat = []
    for row in rows:
        flat.append([row[0][0], row[0][1], row[1][0], row[1][1]])

    tbl = Table(flat, colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), INK_50),
        ("BACKGROUND",    (0, 0), (0, -1), colors.HexColor("#f0f0f8")),
        ("BACKGROUND",    (2, 0), (2, -1), colors.HexColor("#f0f0f8")),
        ("TOPPADDING",    (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.5, INK_200),
        ("ROUNDEDCORNERS", [4]),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))


def _modules_table(story, styles, modules: List[dict]):
    """Modules / deliverables table."""
    _section_title(story, styles, "Scope of Work")

    header = [
        Paragraph("MODULE", styles["label"]),
        Paragraph("DESCRIPTION", styles["label"]),
        Paragraph("TIMELINE", styles["label"]),
        Paragraph("PRICE (USD)", styles["label"]),
    ]
    rows = [header]

    for i, m in enumerate(modules):
        rows.append([
            Paragraph(m.get("name", ""), styles["h3"]),
            Paragraph(m.get("description", ""), styles["body_sm"]),
            Paragraph(m.get("timeline", ""), styles["body_sm"]),
            Paragraph(f"${m.get('price', 0):,.0f}", styles["body_sm"]),
        ])

    col_w = [42*mm, 72*mm, 28*mm, 28*mm]
    tbl = Table(rows, colWidths=col_w, repeatRows=1)

    style = [
        # Header row
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("TOPPADDING",    (0, 0), (-1, 0), 8),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        # Data rows
        ("TOPPADDING",    (0, 1), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.4, INK_200),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]
    # Alternate row shading
    for i in range(1, len(rows)):
        bg = WHITE if i % 2 == 1 else INK_50
        style.append(("BACKGROUND", (0, i), (-1, i), bg))

    tbl.setStyle(TableStyle(style))
    story.append(tbl)
    story.append(Spacer(1, 4*mm))


def _totals_block(story, styles, modules: List[dict], headcount: int):
    """Summary pricing block."""
    subtotal = sum(m.get("price", 0) for m in modules)
    tax      = round(subtotal * 0.18, 2)   # 18 % GST / VAT — adjust as needed
    total    = subtotal + tax

    data = [
        ["Subtotal",   f"${subtotal:,.2f}"],
        ["Tax (18%)",  f"${tax:,.2f}"],
    ]
    summary = Table(data, colWidths=[130*mm, 50*mm])
    summary.setStyle(TableStyle([
        ("ALIGN",         (1, 0), (1, -1), "RIGHT"),
        ("FONTNAME",      (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("TEXTCOLOR",     (0, 0), (-1, -1), INK_700),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW",     (0, -1), (-1, -1), 0.5, INK_200),
    ]))
    story.append(summary)
    story.append(Spacer(1, 2*mm))

    # Grand total bar
    total_row = Table(
        [[Paragraph(f"TOTAL INVESTMENT&nbsp;&nbsp;&nbsp;${total:,.2f}", styles["total"])]],
        colWidths=[180*mm]
    )
    total_row.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), INDIGO),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(total_row)

    if headcount:
        per_head = total / headcount if headcount > 0 else 0
        story.append(Spacer(1, 2*mm))
        story.append(Paragraph(
            f"<i>Per-seat cost based on {headcount} employees: <b>${per_head:,.2f}</b></i>",
            styles["body_sm"]
        ))
    story.append(Spacer(1, 5*mm))


def _timeline_block(story, styles, modules: List[dict]):
    """Visual timeline bar."""
    _section_title(story, styles, "Delivery Timeline")

    total_weeks = 0
    timeline_rows = [["Phase", "Module", "Duration"]]
    for i, m in enumerate(modules, 1):
        tl = m.get("timeline", "2 weeks")
        timeline_rows.append([f"Phase {i}", m.get("name", ""), tl])
        # crude week extractor
        try:
            wks = int(''.join(filter(str.isdigit, tl.split()[0])))
            total_weeks += wks
        except Exception:
            total_weeks += 2

    timeline_rows.append(["", "Total estimated delivery", f"{total_weeks} weeks"])

    tbl = Table(timeline_rows, colWidths=[28*mm, 102*mm, 50*mm])
    tbl.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), INDIGO_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("BACKGROUND",    (0, -1), (-1, -1), INDIGO_LIGHT),
        ("TEXTCOLOR",     (0, -1), (-1, -1), INDIGO_DARK),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("TOPPADDING",    (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("LEFTPADDING",   (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.4, INK_200),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 5*mm))


def _why_us_block(story, styles):
    """Static 'Why choose us' section."""
    _section_title(story, styles, "Why Choose Us")

    points = [
        ("✔ Custom HRMS Expertise", "Purpose-built for SMEs — attendance, payroll, leaves, assets and more out of the box."),
        ("✔ Rapid Delivery",        "Modular architecture means each phase ships in weeks, not months."),
        ("✔ Dedicated Support",     "Assigned account manager + 12-month post-delivery support included."),
        ("✔ Scalable Platform",     "Grows with your headcount — no per-seat lock-in after deployment."),
    ]
    for title, desc in points:
        story.append(Paragraph(f"<b>{title}</b>", styles["h3"]))
        story.append(Paragraph(desc, styles["body_sm"]))
        story.append(Spacer(1, 3*mm))
    story.append(Spacer(1, 2*mm))


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(INK_500)
    canvas.drawCentredString(
        A4[0] / 2, 18*mm,
        f"Confidential Proposal  •  Generated {datetime.now().strftime('%d %b %Y')}  •  Page {doc.page}"
    )
    # thin top rule on footer
    canvas.setStrokeColor(INK_200)
    canvas.setLineWidth(0.5)
    canvas.line(20*mm, 22*mm, A4[0] - 20*mm, 22*mm)
    canvas.restoreState()


def generate_proposal_pdf(
    lead: dict,
    modules: List[dict],
    headcount: int = 0,
    prepared_for: Optional[str] = None,
) -> bytes:
    """
    Build a branded proposal PDF and return raw bytes.

    lead      : dict with keys: company_name, email, website, country, score, tag
    modules   : list of {name, description, timeline, price}
    headcount : number of employees (for per-seat calc)
    """
    buf = BytesIO()
    ref = f"PROP-{datetime.now().strftime('%Y%m%d')}-{abs(hash(lead.get('company_name','X'))) % 9000 + 1000}"

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        topMargin=12*mm,
        bottomMargin=28*mm,
        leftMargin=20*mm,
        rightMargin=20*mm,
    )

    styles = _styles()
    story  = []

    _header_block(story, styles, lead.get("company_name", ""), prepared_for or lead.get("company_name", ""), ref)
    _info_grid(story, styles, lead)

    if modules:
        _modules_table(story, styles, modules)
        _totals_block(story, styles, modules, headcount)
        _timeline_block(story, styles, modules)

    _why_us_block(story, styles)

    # CTA footer box
    cta = Table(
        [[Paragraph(
            "Ready to move forward? Reply to this proposal or contact us to schedule a kick-off call.",
            ParagraphStyle("cta", fontName="Helvetica-Bold", fontSize=10,
                           textColor=INDIGO_DARK, leading=15, alignment=TA_CENTER)
        )]],
        colWidths=[180*mm]
    )
    cta.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), INDIGO_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(cta)

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    return buf.getvalue()