"""PDF export for the Sales Dashboard.

Produces an A4-landscape multi-page PDF where each dashboard tab occupies
one page (overflowing to a continuation page when there are > 4 charts).

Usage (from inside a Shiny download handler):
    from pdf_export import build_pdf
    pdf_bytes = build_pdf(tab_data, filters_summary, date_range)

tab_data is a list of dicts:
    {
        "tab":     "Executive Overview",
        "kpis":    [("Total Revenue (GMV)", "¥ 1.23M", "+5.2%"), ...],  # (label, value, delta)
        "figures": [plotly_fig, plotly_fig, ...],   # up to 4 Plotly figures
        "tables":  [pandas_df, ...],                 # 0-1 DataFrames
        "remark":  "Analyst note text or empty string",
    }
"""

import io
from datetime import datetime
from typing import Any

import pandas as pd
import plotly.io as pio
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, Image, PageTemplate, Paragraph,
    Spacer, Table, TableStyle,
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT


# ── Constants ──────────────────────────────────────────────────────────────────
PAGE_W, PAGE_H = landscape(A4)   # 297 × 210 mm in points
MARGIN = 14 * mm
INNER_W = PAGE_W - 2 * MARGIN

BRAND_BLUE   = colors.HexColor("#5B6CFF")
BRAND_PURPLE = colors.HexColor("#8B5CF6")
BRAND_LIGHT  = colors.HexColor("#EEF0FF")
GREY         = colors.HexColor("#64748B")
DARK         = colors.HexColor("#0F172A")
SUCCESS      = colors.HexColor("#10B981")
DANGER       = colors.HexColor("#EF4444")
WARNING      = colors.HexColor("#F59E0B")

STYLES = getSampleStyleSheet()

_HEADER_STYLE = ParagraphStyle(
    "DashHeader", parent=STYLES["Normal"],
    fontSize=10, textColor=colors.white, fontName="Helvetica-Bold", leading=13,
)
_TITLE_STYLE = ParagraphStyle(
    "TabTitle", parent=STYLES["Normal"],
    fontSize=15, textColor=DARK, fontName="Helvetica-Bold", leading=18,
)
_BODY_STYLE = ParagraphStyle(
    "Body", parent=STYLES["Normal"],
    fontSize=8, textColor=DARK, fontName="Helvetica", leading=11,
)
_REMARK_STYLE = ParagraphStyle(
    "Remark", parent=STYLES["Normal"],
    fontSize=8, textColor=GREY, fontName="Helvetica-Oblique", leading=11,
)
_KPI_LABEL_STYLE = ParagraphStyle(
    "KpiLabel", parent=STYLES["Normal"],
    fontSize=7.5, textColor=GREY, fontName="Helvetica", leading=10,
)
_KPI_VALUE_STYLE = ParagraphStyle(
    "KpiValue", parent=STYLES["Normal"],
    fontSize=13, textColor=DARK, fontName="Helvetica-Bold", leading=16,
)
_KPI_DELTA_STYLE_POS = ParagraphStyle(
    "KpiDeltaPos", parent=STYLES["Normal"],
    fontSize=8, textColor=SUCCESS, fontName="Helvetica-Bold", leading=10,
)
_KPI_DELTA_STYLE_NEG = ParagraphStyle(
    "KpiDeltaNeg", parent=STYLES["Normal"],
    fontSize=8, textColor=DANGER, fontName="Helvetica-Bold", leading=10,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _fig_to_image(fig, width_pt: float, height_pt: float) -> Image | None:
    """Render a Plotly figure to a ReportLab Image object."""
    try:
        dpi = 150
        px_w = int(width_pt / 72 * dpi)
        px_h = int(height_pt / 72 * dpi)
        fig_bytes = pio.to_image(
            fig, format="png", width=px_w, height=px_h, scale=1,
            engine="kaleido",
        )
        buf = io.BytesIO(fig_bytes)
        return Image(buf, width=width_pt, height=height_pt)
    except Exception:
        return None


def _kpi_table(kpis: list[tuple]) -> Table | None:
    """Render a row of KPI cards as a ReportLab Table."""
    if not kpis:
        return None
    cell_w = INNER_W / len(kpis)
    data = []
    labels_row, values_row, deltas_row = [], [], []
    for label, value, delta in kpis:
        labels_row.append(Paragraph(str(label), _KPI_LABEL_STYLE))
        values_row.append(Paragraph(str(value), _KPI_VALUE_STYLE))
        if delta:
            d = str(delta)
            style = _KPI_DELTA_STYLE_NEG if d.startswith("-") else _KPI_DELTA_STYLE_POS
            deltas_row.append(Paragraph(d, style))
        else:
            deltas_row.append(Paragraph("", _KPI_DELTA_STYLE_POS))

    data = [labels_row, values_row, deltas_row]
    col_widths = [cell_w] * len(kpis)
    t = Table(data, colWidths=col_widths)
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), BRAND_LIGHT),
        ("BOX",          (0, 0), (-1, -1), 0.5, colors.HexColor("#C7D2FE")),
        ("INNERGRID",    (0, 0), (-1, -1), 0.5, colors.white),
        ("TOPPADDING",   (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


def _df_table(df: pd.DataFrame, max_rows: int = 10) -> Table | None:
    """Render a small DataFrame as a ReportLab Table (max_rows rows)."""
    if df is None or df.empty:
        return None
    df = df.head(max_rows)
    header = [Paragraph(str(c), ParagraphStyle(
        "TH", parent=STYLES["Normal"],
        fontSize=7, textColor=colors.white, fontName="Helvetica-Bold",
    )) for c in df.columns]
    rows = [header]
    for _, row in df.iterrows():
        rows.append([
            Paragraph(str(v), ParagraphStyle(
                "TD", parent=STYLES["Normal"],
                fontSize=7, textColor=DARK, fontName="Helvetica",
            ))
            for v in row
        ])
    col_w = INNER_W / len(df.columns)
    t = Table(rows, colWidths=[col_w] * len(df.columns))
    t.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, 0), BRAND_BLUE),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.white, BRAND_LIGHT]),
        ("BOX",          (0, 0), (-1, -1), 0.3, GREY),
        ("INNERGRID",    (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 3),
        ("LEFTPADDING",  (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return t


# ── Header/footer drawn on every page ─────────────────────────────────────────

def _make_header_footer(doc_title: str, filters: str, generated: str):
    """Returns an onFirstPage / onLaterPages function for the PageTemplate."""

    def draw_hf(canvas, doc):
        canvas.saveState()
        # Top header bar
        canvas.setFillColor(BRAND_BLUE)
        canvas.rect(0, PAGE_H - 20 * mm, PAGE_W, 20 * mm, fill=1, stroke=0)
        canvas.setFont("Helvetica-Bold", 10)
        canvas.setFillColor(colors.white)
        canvas.drawString(MARGIN, PAGE_H - 13 * mm, doc_title)
        canvas.setFont("Helvetica", 8)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 13 * mm, f"Generated: {generated}")
        canvas.setFont("Helvetica", 7.5)
        canvas.drawString(MARGIN, PAGE_H - 18 * mm, f"Filters: {filters}")
        # Bottom rule + page number
        canvas.setStrokeColor(colors.HexColor("#C7D2FE"))
        canvas.setLineWidth(0.5)
        canvas.line(MARGIN, 10 * mm, PAGE_W - MARGIN, 10 * mm)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(PAGE_W / 2, 7 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()

    return draw_hf


# ── Cover page ─────────────────────────────────────────────────────────────────

def _cover_story(title: str, date_range: str, filters: str, generated: str) -> list:
    spacer_top = Spacer(INNER_W, 30 * mm)
    title_p = Paragraph(title, ParagraphStyle(
        "CoverTitle", parent=STYLES["Normal"],
        fontSize=26, textColor=BRAND_BLUE, fontName="Helvetica-Bold",
        leading=30, alignment=TA_CENTER,
    ))
    sub_p = Paragraph(
        "Revenue Intelligence Report",
        ParagraphStyle("CoverSub", parent=STYLES["Normal"],
                       fontSize=14, textColor=BRAND_PURPLE,
                       fontName="Helvetica", leading=18, alignment=TA_CENTER),
    )
    date_p = Paragraph(
        f"<b>Period:</b> {date_range}",
        ParagraphStyle("CoverDate", parent=STYLES["Normal"],
                       fontSize=11, textColor=DARK, fontName="Helvetica",
                       leading=14, alignment=TA_CENTER),
    )
    filter_p = Paragraph(
        f"<b>Filters applied:</b> {filters}",
        ParagraphStyle("CoverFilter", parent=STYLES["Normal"],
                       fontSize=9, textColor=GREY, fontName="Helvetica",
                       leading=12, alignment=TA_CENTER),
    )
    gen_p = Paragraph(
        f"<i>Generated {generated}</i>",
        ParagraphStyle("CoverGen", parent=STYLES["Normal"],
                       fontSize=8, textColor=GREY, fontName="Helvetica-Oblique",
                       leading=11, alignment=TA_CENTER),
    )
    return [spacer_top, title_p, Spacer(INNER_W, 4 * mm),
            sub_p, Spacer(INNER_W, 8 * mm),
            date_p, Spacer(INNER_W, 3 * mm),
            filter_p, Spacer(INNER_W, 6 * mm),
            gen_p]


# ── Per-tab page story ─────────────────────────────────────────────────────────

def _tab_story(tab_info: dict) -> list:
    """Build the flowable story for one tab page."""
    story = []
    tab_name = tab_info.get("tab", "")
    kpis     = tab_info.get("kpis", [])
    figures  = tab_info.get("figures", [])
    tables   = tab_info.get("tables", [])
    remark   = tab_info.get("remark", "")

    # Tab title
    story.append(Paragraph(tab_name, _TITLE_STYLE))
    story.append(Spacer(INNER_W, 3 * mm))

    # KPI row
    kpi_t = _kpi_table(kpis)
    if kpi_t:
        story.append(kpi_t)
        story.append(Spacer(INNER_W, 4 * mm))

    # Charts — up to 4 in a 2×2 grid
    figs = [f for f in figures if f is not None][:4]
    if figs:
        # Available height after KPI row, tables, remark footer
        avail_h = PAGE_H - 20 * mm - 12 * mm   # header + bottom margin
        if kpi_t:
            avail_h -= 22 * mm
        if tables:
            avail_h -= 30 * mm
        avail_h -= 14 * mm  # remark + spacers

        cols = 2 if len(figs) > 1 else 1
        chart_w = (INNER_W - (cols - 1) * 4 * mm) / cols
        rows = (len(figs) + 1) // 2
        chart_h = max((avail_h - (rows - 1) * 4 * mm) / rows, 40 * mm)

        grid_data, row_buf = [], []
        for i, fig in enumerate(figs):
            img = _fig_to_image(fig, chart_w, chart_h)
            row_buf.append(img if img else Paragraph("[Chart unavailable]", _BODY_STYLE))
            if len(row_buf) == cols:
                grid_data.append(row_buf)
                row_buf = []
        if row_buf:
            while len(row_buf) < cols:
                row_buf.append(Spacer(chart_w, chart_h))
            grid_data.append(row_buf)

        col_widths = [chart_w] * cols
        grid = Table(grid_data, colWidths=col_widths,
                     rowHeights=[chart_h] * len(grid_data))
        grid.setStyle(TableStyle([
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("INNERGRID",     (0, 0), (-1, -1), 3, colors.white),
        ]))
        story.append(grid)
        story.append(Spacer(INNER_W, 3 * mm))

    # Optional table (first one only, capped at 10 rows)
    if tables:
        df_t = _df_table(tables[0])
        if df_t:
            story.append(df_t)
            story.append(Spacer(INNER_W, 2 * mm))

    # Remark footer
    remark_text = remark.strip() if remark else "No analyst notes for this period."
    story.append(Paragraph(f"Analyst Notes: {remark_text}", _REMARK_STYLE))

    return story


# ── Public entry point ─────────────────────────────────────────────────────────

def build_pdf(
    tab_data: list[dict],
    filters_summary: str = "All",
    date_range: str = "—",
    dashboard_title: str = "Global Mobile Recharge — Revenue Intelligence Dashboard",
) -> bytes:
    """
    Build and return a complete PDF as bytes.

    Parameters
    ----------
    tab_data : list of tab_info dicts (see module docstring)
    filters_summary : human-readable string of applied filters
    date_range : date range string
    dashboard_title : dashboard name shown in header and cover
    """
    buf = io.BytesIO()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")

    hf = _make_header_footer(dashboard_title, filters_summary, generated)

    frame = Frame(
        MARGIN,
        10 * mm,
        INNER_W,
        PAGE_H - 20 * mm - 12 * mm,
        leftPadding=0, rightPadding=0,
        topPadding=0, bottomPadding=0,
    )
    page_template = PageTemplate(id="main", frames=[frame], onPage=hf)

    doc = BaseDocTemplate(
        buf,
        pagesize=landscape(A4),
        pageTemplates=[page_template],
        leftMargin=MARGIN, rightMargin=MARGIN,
        topMargin=22 * mm, bottomMargin=12 * mm,
        title=dashboard_title,
        author="Revenue Intelligence Dashboard",
    )

    story = []

    # Cover page
    story.extend(_cover_story(dashboard_title, date_range, filters_summary, generated))
    story.append(Spacer(INNER_W, PAGE_H))   # force page break after cover

    # One page per tab
    for tab_info in tab_data:
        story.extend(_tab_story(tab_info))
        story.append(Spacer(INNER_W, PAGE_H))  # force page break between tabs

    doc.build(story)
    return buf.getvalue()
