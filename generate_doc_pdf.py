"""
Generate the complete system documentation PDF for the Global Mobile Recharge
Revenue Intelligence Dashboard — architecture, data sources, pipeline,
business rules, every tab/visualization, ML models, and the operations runbook.

Run (use the project venv — system Python may be blocked from sklearn,
but this script only needs reportlab + pandas):

    sales_env\\Scripts\\python.exe generate_doc_pdf.py

Output: Sales_Dashboard_Documentation.pdf (in the same folder)
"""

import io
from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.platypus import (
    BaseDocTemplate, Frame, PageTemplate, Paragraph,
    Spacer, Table, TableStyle, HRFlowable, PageBreak,
)

# ── CJK font registration (Chinese column names must render) ─────────────────

FONT, FONT_BOLD = "Helvetica", "Helvetica-Bold"


def _register_cjk():
    global FONT, FONT_BOLD
    normal_candidates = [
        (r"C:\Windows\Fonts\msyh.ttc", 0),     # Microsoft YaHei
        (r"C:\Windows\Fonts\Deng.ttf", None),  # DengXian
        (r"C:\Windows\Fonts\simsun.ttc", 0),   # SimSun
    ]
    bold_candidates = [
        (r"C:\Windows\Fonts\msyhbd.ttc", 0),
        (r"C:\Windows\Fonts\Dengb.ttf", None),
        (r"C:\Windows\Fonts\simhei.ttf", None),
    ]
    ok_normal = ok_bold = False
    for path, idx in normal_candidates:
        try:
            if Path(path).exists():
                kw = {"subfontIndex": idx} if idx is not None else {}
                pdfmetrics.registerFont(TTFont("CJK", path, **kw))
                ok_normal = True
                break
        except Exception:
            continue
    for path, idx in bold_candidates:
        try:
            if Path(path).exists():
                kw = {"subfontIndex": idx} if idx is not None else {}
                pdfmetrics.registerFont(TTFont("CJK-Bold", path, **kw))
                ok_bold = True
                break
        except Exception:
            continue
    if ok_normal:
        FONT = "CJK"
        FONT_BOLD = "CJK-Bold" if ok_bold else "CJK"
        registerFontFamily("CJK", normal="CJK", bold=FONT_BOLD,
                           italic="CJK", boldItalic=FONT_BOLD)


_register_cjk()

# ── Colours ──────────────────────────────────────────────────────────────────
BRAND_BLUE   = colors.HexColor("#4F46E5")
BRAND_PURPLE = colors.HexColor("#8B5CF6")
BRAND_LIGHT  = colors.HexColor("#EEF0FF")
BRAND_DARK   = colors.HexColor("#0F172A")
GREY         = colors.HexColor("#64748B")
SUCCESS      = colors.HexColor("#10B981")
DANGER       = colors.HexColor("#EF4444")
WARN         = colors.HexColor("#F59E0B")
WHITE        = colors.white

PAGE_W, PAGE_H = landscape(A4)
MARGIN = 15 * mm
INNER_W = PAGE_W - 2 * MARGIN

STYLES = getSampleStyleSheet()

H1 = ParagraphStyle("H1", parent=STYLES["Heading1"],
                    fontSize=22, textColor=BRAND_BLUE, fontName=FONT_BOLD,
                    leading=26, spaceAfter=6, alignment=TA_LEFT)
H2 = ParagraphStyle("H2", parent=STYLES["Heading2"],
                    fontSize=15, textColor=BRAND_DARK, fontName=FONT_BOLD,
                    leading=18, spaceBefore=10, spaceAfter=4)
H3 = ParagraphStyle("H3", parent=STYLES["Heading3"],
                    fontSize=12, textColor=BRAND_PURPLE, fontName=FONT_BOLD,
                    leading=14, spaceBefore=6, spaceAfter=3)
BODY = ParagraphStyle("Body", parent=STYLES["Normal"],
                      fontSize=9, textColor=BRAND_DARK, fontName=FONT,
                      leading=13, spaceAfter=4, alignment=TA_JUSTIFY)
BODY_SMALL = ParagraphStyle("BodySm", parent=STYLES["Normal"],
                            fontSize=8, textColor=BRAND_DARK, fontName=FONT,
                            leading=11, spaceAfter=3)
BULLET = ParagraphStyle("Bullet", parent=STYLES["Normal"],
                        fontSize=9, textColor=BRAND_DARK, fontName=FONT,
                        leading=13, leftIndent=14, firstLineIndent=-10,
                        spaceAfter=2)
CAPTION = ParagraphStyle("Caption", parent=STYLES["Normal"],
                         fontSize=7.5, textColor=GREY, fontName=FONT,
                         leading=10, alignment=TA_CENTER)
CODE = ParagraphStyle("Code", parent=STYLES["Normal"],
                      fontSize=8, textColor=colors.HexColor("#2D3748"),
                      fontName="Courier", leading=11,
                      backColor=colors.HexColor("#F7FAFC"),
                      leftIndent=10, rightIndent=10, spaceAfter=4, spaceBefore=4)


def _hr():
    return HRFlowable(width="100%", thickness=0.5,
                      color=colors.HexColor("#C7D2FE"), spaceAfter=4)


def _section_header(text):
    return [Spacer(INNER_W, 4 * mm), Paragraph(text, H2), _hr()]


def _sub(text):
    return Paragraph(text, H3)


def _p(text):
    return Paragraph(text, BODY)


def _b(text):
    return Paragraph(f"• {text}", BULLET)


def _sm(text):
    return Paragraph(text, BODY_SMALL)


def _info_table(rows, col_widths=None):
    data = [[Paragraph(f"<b>{k}</b>", BODY_SMALL),
             Paragraph(v, BODY_SMALL)] for k, v in rows]
    cw = col_widths or [60 * mm, INNER_W - 60 * mm]
    t = Table(data, colWidths=cw)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, -1), BRAND_LIGHT),
        ("BOX",           (0, 0), (-1, -1), 0.3, colors.HexColor("#C7D2FE")),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _grid_table(headers, rows, col_widths=None):
    head_row = [Paragraph(f"<b>{h}</b>", ParagraphStyle(
        "TH", parent=BODY_SMALL, textColor=WHITE)) for h in headers]
    body_rows = [[Paragraph(str(c), BODY_SMALL) for c in r] for r in rows]
    cw = col_widths or [INNER_W / len(headers)] * len(headers)
    t = Table([head_row] + body_rows, colWidths=cw, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), BRAND_BLUE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, BRAND_LIGHT]),
        ("BOX",           (0, 0), (-1, -1), 0.4, GREY),
        ("INNERGRID",     (0, 0), (-1, -1), 0.3, colors.HexColor("#E2E8F0")),
        ("TOPPADDING",    (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING",   (0, 0), (-1, -1), 6),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))
    return t


def _make_hf(title, section):
    def draw(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(BRAND_BLUE)
        canvas.rect(0, PAGE_H - 14 * mm, PAGE_W, 14 * mm, fill=1, stroke=0)
        canvas.setFont(FONT_BOLD, 9)
        canvas.setFillColor(WHITE)
        canvas.drawString(MARGIN, PAGE_H - 9 * mm, title)
        canvas.setFont(FONT, 8)
        canvas.drawRightString(PAGE_W - MARGIN, PAGE_H - 9 * mm, section)
        canvas.setStrokeColor(colors.HexColor("#C7D2FE"))
        canvas.setLineWidth(0.4)
        canvas.line(MARGIN, 10 * mm, PAGE_W - MARGIN, 10 * mm)
        canvas.setFont(FONT, 7)
        canvas.setFillColor(GREY)
        canvas.drawCentredString(PAGE_W / 2, 6.5 * mm, f"Page {canvas.getPageNumber()}")
        canvas.restoreState()
    return draw


def _data_snapshot():
    """Live stats from the parquet cache for the cover page."""
    out = {"rows": "—", "cols": "—", "date_range": "—", "b2b": "—", "b2c": "—"}
    try:
        import pandas as pd
        import pyarrow.parquet as pq
        p = Path(__file__).parent / "database" / "sales_cache.parquet"
        pf = pq.ParquetFile(p)
        out["rows"] = f"{pf.metadata.num_rows:,}"
        out["cols"] = str(len(pf.schema_arrow.names))
        d = pd.read_parquet(p, columns=["order_time", "segment"])
        dt = pd.to_datetime(d["order_time"], errors="coerce")
        out["date_range"] = f"{dt.min():%d %b %Y} → {dt.max():%d %b %Y}"
        seg = d["segment"].value_counts()
        out["b2b"] = f"{int(seg.get('B2B', 0)):,}"
        out["b2c"] = f"{int(seg.get('B2C', 0)):,}"
    except Exception:
        pass
    return out


# ── Visualizations (matplotlib → reportlab Image) ────────────────────────────

def _fig_image(fig, width_mm=None, dpi=150):
    """Render a matplotlib Figure to an aspect-preserved reportlab Image flowable."""
    from reportlab.platypus import Image as RLImage
    from reportlab.lib.utils import ImageReader
    import matplotlib.pyplot as plt
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    iw, ih = ImageReader(buf).getSize()
    buf.seek(0)
    w = (width_mm * mm) if width_mm else INNER_W
    return RLImage(buf, width=w, height=w * ih / iw)


def _flow_diagram(steps, figsize=(11.0, 1.9), accent="#4F46E5"):
    """Horizontal box-and-arrow flow. steps = [(label, sub), ...]."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyBboxPatch
    fig, ax = plt.subplots(figsize=figsize)
    ax.set_xlim(0, 10); ax.set_ylim(0, 2.5); ax.axis("off")
    n = max(len(steps), 1)
    span = 9.4 / n
    bw = span - 0.34
    for i, (label, sub) in enumerate(steps):
        x = 0.3 + i * span
        ax.add_patch(FancyBboxPatch((x, 0.8), bw, 1.05,
                     boxstyle="round,pad=0.04,rounding_size=0.12",
                     fc="#EEF0FF", ec=accent, lw=1.4))
        ax.text(x + bw / 2, 1.52, label, ha="center", va="center",
                fontsize=8.5, fontweight="bold", color="#0F172A")
        if sub:
            ax.text(x + bw / 2, 1.12, sub, ha="center", va="center",
                    fontsize=6.2, color="#64748B")
        if i < n - 1:
            ax.annotate("", xy=(x + bw + 0.30, 1.32), xytext=(x + bw + 0.02, 1.32),
                        arrowprops=dict(arrowstyle="-|>", color="#8B5CF6", lw=1.5))
    return fig


def _sample_charts():
    """A few summary charts rendered from the live cache (充值成功 basis)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import pandas as pd
    imgs = []
    p = Path(__file__).parent / "database" / "sales_cache.parquet"
    try:
        df = pd.read_parquet(p, columns=["order_time", "segment", "sales", "country", "order_status"])
    except Exception:
        return imgs
    if "order_status" in df.columns:
        df = df[df["order_status"].astype(str).str.strip() == "充值成功"]
    df = df[pd.to_numeric(df["sales"], errors="coerce").notna()]

    def _despine(ax):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
        ax.tick_params(labelsize=6)

    try:   # 1 · Monthly GMV
        mon = (df.assign(m=pd.to_datetime(df["order_time"], errors="coerce").dt.to_period("M").astype(str))
                 .groupby("m")["sales"].sum())
        mon = mon[mon.index != "NaT"].tail(8)
        fig, ax = plt.subplots(figsize=(4.6, 2.5))
        ax.bar(range(len(mon)), mon.values / 1e6, color="#4F46E5")
        ax.set_xticks(range(len(mon)))
        ax.set_xticklabels(mon.index, rotation=45, fontsize=6, ha="right")
        ax.set_title("Monthly GMV (RMB M)", fontsize=9, color="#0F172A")
        _despine(ax)
        imgs.append(_fig_image(fig, width_mm=86))
    except Exception:
        pass
    try:   # 2 · Segment split
        seg = df.groupby("segment")["sales"].sum()
        fig, ax = plt.subplots(figsize=(4.6, 2.5))
        ax.pie(seg.values, labels=list(seg.index), autopct="%1.0f%%",
               colors=["#4F46E5", "#10B981"], textprops={"fontsize": 8},
               wedgeprops={"width": 0.45})
        ax.set_title("GMV by segment", fontsize=9, color="#0F172A")
        imgs.append(_fig_image(fig, width_mm=86))
    except Exception:
        pass
    try:   # 3 · Top markets
        top = df.groupby("country")["sales"].sum().nlargest(8).sort_values()
        fig, ax = plt.subplots(figsize=(4.6, 2.5))
        ax.barh(range(len(top)), top.values / 1e6, color="#8B5CF6")
        ax.set_yticks(range(len(top)))
        ax.set_yticklabels(list(top.index), fontsize=6)
        ax.set_title("Top markets GMV (RMB M)", fontsize=9, color="#0F172A")
        _despine(ax)
        imgs.append(_fig_image(fig, width_mm=86))
    except Exception:
        pass
    return imgs


def _viz_block():
    """Flowables: architecture + pipeline diagrams + live-data charts."""
    out = []
    arch = _flow_diagram([
        ("Raw exports", "Master/Agent CSV"),
        ("db_utils", "clean - dedup - audit"),
        ("Cache", "sales_cache.parquet"),
        ("Shiny server", "reactive filters"),
        ("12 tabs", "charts - KPIs - PDF"),
    ])
    out += [_sub("Architecture — raw data to dashboard"), _fig_image(arch),
            Paragraph("Raw daily exports are cleaned &amp; deduplicated by db_utils into one parquet "
                      "cache, loaded once by the Shiny server, then sliced reactively across the 12 "
                      "analysis tabs.", CAPTION), Spacer(INNER_W, 3 * mm)]
    pipe = _flow_diagram([
        ("Download", "daily CSV"),
        ("Validate", "schema - dates"),
        ("Quarantine", "bad rows out"),
        ("Append+dedup", "by order_id"),
        ("Rebuild cache", "to parquet"),
        ("Load", "in-memory"),
    ], accent="#10B981")
    out += [_sub("Import pipeline (hardened)"), _fig_image(pipe),
            Paragraph("Each daily file is content-hashed (dup-file guard), validated, bad rows "
                      "quarantined, appended with order-id dedup + restatement logging, then the cache "
                      "is rebuilt — every step recorded in import_audit.jsonl.", CAPTION),
            Spacer(INNER_W, 3 * mm)]
    charts = _sample_charts()
    if charts:
        row = [c for c in charts[:3]]
        while len(row) < 3:
            row.append("")
        t = Table([row], colWidths=[INNER_W / 3] * 3)
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                               ("ALIGN", (0, 0), (-1, -1), "CENTER")]))
        out += [_sub("Live data snapshot (充值成功 basis)"), t]
    return out


# ── Build story ───────────────────────────────────────────────────────────────

def build_doc_pdf() -> bytes:
    buf = io.BytesIO()
    generated = datetime.now().strftime("%Y-%m-%d %H:%M")
    doc_title = "Global Mobile Recharge — Revenue Intelligence Dashboard"
    section_label = "System Documentation · v7"

    hf = _make_hf(doc_title, section_label)
    frame = Frame(MARGIN, 12 * mm, INNER_W, PAGE_H - 14 * mm - 14 * mm,
                  leftPadding=0, rightPadding=0, topPadding=4, bottomPadding=0)
    template = PageTemplate(id="main", frames=[frame], onPage=hf)
    doc = BaseDocTemplate(buf, pagesize=landscape(A4), pageTemplates=[template],
                          leftMargin=MARGIN, rightMargin=MARGIN,
                          topMargin=16 * mm, bottomMargin=14 * mm,
                          title=doc_title, author="LiuLian Tech Sdn. Bhd.")

    snap = _data_snapshot()
    story = []

    # ════════════════════════════ COVER ════════════════════════════
    story += [
        Spacer(INNER_W, 16 * mm),
        Paragraph(doc_title, ParagraphStyle(
            "Cover", parent=STYLES["Normal"], fontSize=26, textColor=BRAND_BLUE,
            fontName=FONT_BOLD, leading=32, alignment=TA_CENTER)),
        Spacer(INNER_W, 4 * mm),
        Paragraph("全球移动充值 — 收入智能仪表板 · 系统文档",
                  ParagraphStyle("CoverZh", parent=STYLES["Normal"], fontSize=14,
                                 textColor=GREY, fontName=FONT, alignment=TA_CENTER)),
        Spacer(INNER_W, 8 * mm),
        Paragraph("Complete System Documentation — Architecture · Data Sources · "
                  "Pipeline · Business Rules · Visualizations · ML Models · Operations",
                  ParagraphStyle("CoverSub", parent=STYLES["Normal"], fontSize=11,
                                 textColor=BRAND_DARK, fontName=FONT, alignment=TA_CENTER)),
        Spacer(INNER_W, 10 * mm),
        _info_table([
            ("Document version", "Round 6 — full column utilisation, order-status accounting, "
                                 "marketing analytics, bilingual charts"),
            ("Generated", generated),
            ("Data snapshot", f"{snap['rows']} order rows · {snap['cols']} cache columns · "
                              f"{snap['date_range']}"),
            ("Segments", f"B2B (Agent): {snap['b2b']} rows · B2C (Master): {snap['b2c']} rows"),
            ("Owner", "Data & Operations — LiuLian Tech Sdn. Bhd."),
            ("Location", r"C:\Disk\LiuLian Tech Sdn. Bhd\Code\Sales Dashboard"),
        ], col_widths=[55 * mm, INNER_W - 55 * mm]),
        Spacer(INNER_W, 8 * mm),
        _sm("Contents: Visual Overview · 1 System Overview · 2 Data Sources & Schema · 3 Data Pipeline · "
            "4 Business Rules & Calculations · 5 Dashboard Structure (12 tabs) · "
            "6 Filters, UX & Language · 7 AI / ML Models · 8 Reliability & Error Handling · "
            "9 Operations Runbook · 10 Known Caveats & Data-Quality Asks · Appendix: Glossary"),
        PageBreak(),
    ]

    # ════════════════════ VISUAL OVERVIEW ════════════════════
    story += _section_header("Visual Overview — Architecture, Pipeline & Live Data")
    try:
        story += _viz_block()
    except Exception as exc:
        story += [_sm(f"(Visual overview skipped: {exc})")]
    story += [PageBreak()]

    # ════════════════════ 1. SYSTEM OVERVIEW ════════════════════
    story += _section_header("1 · System Overview")
    story += [
        _p("A 12-tab business-intelligence web application for a global mobile-recharge "
           "platform, covering revenue (GMV), order quality, markets, operators/suppliers, "
           "products and denominations, customers, marketing promotions, and ML forecasts. "
           "It serves both <b>B2B (agent/reseller)</b> and <b>B2C (consumer app)</b> order data."),
        _sub("Technology stack"),
        _grid_table(
            ["Layer", "Technology", "Notes"],
            [
                ["Web framework", "Shiny for Python 1.6 (bslib layout)", "Reactive server, per-session state"],
                ["Charts", "Plotly (served locally from /static)", "Consistent theme via theme.py apply_theme()"],
                ["Data", "pandas + PyArrow parquet", "1.1M+ rows load in ~0.2 s from cache"],
                ["ML", "scikit-learn 1.9", "Import is guarded — app still starts if Windows App Control blocks DLLs"],
                ["PDF export", "reportlab", "Per-tab report export + this documentation"],
                ["Runtime", "sales_env virtualenv (Python 3.13)", "MUST use sales_env — system Python is blocked from sklearn"],
            ],
            col_widths=[35 * mm, 80 * mm, INNER_W - 115 * mm]),
        _sub("Module map"),
        _grid_table(
            ["File", "Role"],
            [
                ["sales_dashboard.py", "Main app (~8,700 lines): UI for all 10 tabs, ~120 render functions, "
                                       "filter chain, import handlers, CSS/JS design system"],
                ["db_utils.py", "Storage layer: rolling parquet stores, xlsx backups, dedup/append, "
                                "cache rebuild, import validation, column normalisation (COLUMN_RENAME)"],
                ["theme.py", "Brand palette, Plotly layout defaults, number/percent formatting, "
                             "ISO country codes, region map, calling-code → country map"],
                ["translations.py", "EN↔ZH dictionaries: headings (T_UI), chart-phrase map "
                                    "(CHART_PHRASES, ~150 entries) used by the _tt() runtime translator"],
                ["ml_predictions.py", "Revenue forecast (GBR/RF/MLP), churn prediction (4 models, CV), "
                                      "product demand forecast"],
                ["country_mapping.py", "Chinese → English country-name translation (150+ entries)"],
                ["fx_rates.py", "RMB-base currency conversion table per market"],
                ["pdf_export.py / remarks_utils.py", "Tab PDF report builder · per-tab analyst remarks storage"],
                ["generate_doc_pdf.py", "This documentation generator"],
            ],
            col_widths=[48 * mm, INNER_W - 48 * mm]),
        PageBreak(),
    ]

    # ════════════════════ 2. DATA SOURCES & SCHEMA ════════════════════
    story += _section_header("2 · Data Sources & Schema")
    story += [
        _p("Two daily Excel exports feed the system. <b>Agent Data</b> (B2B, 16 columns) and "
           "<b>Master Data</b> (B2C, 29 columns). They have different column sets — the critical "
           "asymmetries are highlighted below, because they shape every cross-segment chart."),
        _sub("Critical data-model facts"),
        _b("<b>operator (运营商)</b> exists natively only in B2B rows. For B2C it is filled at "
           "load time from <b>品牌商 (brand)</b> — Touch'n Go, Telkomsel, Maxis, Digi… — with a "
           "product-name fallback ('Digi话费' → 'Digi')."),
        _b("<b>product / product_category / brand / SKU / coupon / promo flags</b> exist only in B2C rows."),
        _b("<b>Data-package sizes live in sku名称</b> ('50GB，28天', '3.5G，30天') — NOT in product "
           "names. The volume parser reads SKU first, product name as fallback."),
        _b("<b>区号 (calling code)</b> = the destination market of the recharge (60=Malaysia, 62=Indonesia, "
           "20=Egypt, 964=Iraq…). Egypt is the single largest destination."),
        _b("<b>batch_number</b> is 1-to-1 with orders (601,348 unique in 601,612 rows) — carries no "
           "analytical value and is deliberately not used."),
        _sub("Agent Data (B2B) — 16 source columns"),
        _grid_table(
            ["Source column", "Normalised name", "Used for"],
            [
                ["Date", "date", "(kept, not used directly — order_time preferred)"],
                ["批次号", "batch_number", "Not used (1:1 with orders)"],
                ["订单号", "order_id", "Primary key — dedup on append, order counts"],
                ["订单时间", "order_time", "All time series, date filtering"],
                ["商品信息", "product_info", "B2B product description (fallback product label)"],
                ["运营商", "operator", "Supplier/operator analysis, margins, refund rates"],
                ["面额", "denomination", "Denomination analytics, scorecard, heatmaps"],
                ["售价", "sales_listed → sales", "Revenue (GMV)"],
                ["结算价", "settlement_price", "Cost — gross margin calculations"],
                ["区号", "area_code", "Destination-market analysis"],
                ["充值号码", "recharge_number", "Beneficiary reach / repeat top-ups"],
                ["订单状态", "order_status", "Success/refund accounting (充值成功 / 已退款 / 等待处理)"],
                ["代理商名称", "agent_name", "B2B agent ranking, concentration risk"],
                ["国家", "country", "Market filtering and rankings"],
                ["接口商订单号", "interface_order_id", "Routing/reconciliation coverage metric"],
                ["PIN码", "pin_code", "PIN-delivery share KPI"],
            ],
            col_widths=[42 * mm, 48 * mm, INNER_W - 90 * mm]),
        PageBreak(),
        _sub("Master Data (B2C) — 29 source columns"),
        _grid_table(
            ["Source column", "Normalised name", "Used for"],
            [
                ["用户ID / 用户名", "user_id / —", "Customer analytics, cohorts, churn (用户名 unused)"],
                ["国家", "country", "Market filtering and rankings"],
                ["订单时间 / 注册时间", "order_time / register_time", "Time series · registration funnel & cohorts"],
                ["订单号", "order_id", "Primary key"],
                ["useepay订单号", "useepay_order_id", "Payment-gateway mix KPI (53.9% presence)"],
                ["商品分类", "product_category", "Category Overview (充话费 / 买流量 / Touch'n Go / 电子钱包…)"],
                ["SKU名称", "sku_name", "Package sizes ('50GB，28天') + denomination labels ('RM 50')"],
                ["商品名称", "product", "Product rankings, treemap, trends"],
                ["品牌商", "brand", "Fills B2C operator at load (Telkomsel, Maxis, Digi…)"],
                ["面额", "denomination", "Denomination analytics"],
                ["售价 / 实际支付", "sales_listed / sales", "sales = 实际支付, fallback 售价 (listed kept for discount depth after next rebuild)"],
                ["结算价", "settlement_price", "Cost / margin"],
                ["区号 / 充值号码", "area_code / recharge_number", "Destination & beneficiary analysis"],
                ["订单状态", "order_status", "充值成功 / 已退款 / 已取消 / 等待支付 / 待付款 / 等待处理 / 充值中"],
                ["是否使用优惠券 / 优惠券名称 / 优惠券金额", "coupon_used / coupon_name / coupon_amount",
                 "Marketing tab: coupon ROI, campaign table"],
                ["来源", "user_source", "Acquisition channel analysis (微信小程序 / 公众号 / 支付宝…)"],
                ["是否新人优惠", "new_user_promo", "New-user promo trend"],
                ["是否角标产品", "badge_product", "Featured-product (merchandising) effectiveness"],
                ["取消原因", "—", "Empty upstream — flagged as a data-quality request"],
                ["IP地址 / IP国家", "ip_address / ip_country", "Global IP origin map (B2C)"],
                ["接口商订单号", "interface_order_id", "Routing coverage"],
            ],
            col_widths=[58 * mm, 52 * mm, INNER_W - 110 * mm]),
        PageBreak(),
    ]

    # ════════════════════ 3. DATA PIPELINE ════════════════════
    story += _section_header("3 · Data Pipeline")
    story += [
        _sub("Storage layout (./database/)"),
        _grid_table(
            ["File", "Role", "Write trigger"],
            [
                ["Agent_Database.parquet / Master_Database.parquet",
                 "Rolling stores — primary, deduped order history per segment",
                 "Every daily upload (seconds)"],
                ["Agent_Database.xlsx / Master_Database.xlsx",
                 "Human-readable backups (1M+ rows, minutes to write)",
                 "On demand — '💾 Export Excel Backup' button — or full source rebuild"],
                ["sales_cache.parquet",
                 "Combined B2B+B2C cache (34 columns) the dashboard reads",
                 "Auto after every append; auto-rebuilt when any rolling store is newer"],
            ],
            col_widths=[62 * mm, 90 * mm, INNER_W - 152 * mm]),
        _sub("Flow — daily upload (Import Data, seconds)"),
        _b("<b>1. Upload</b> (.xlsx/.xls/.xlsm/.csv/.tsv, encoding auto-detect) → a copy is archived "
           "unchanged to the long-term archive folders (audit trail)."),
        _b("<b>2. Validate</b> — the import report shows: rows added / duplicates skipped, the batch's "
           "date range, missing key columns (订单号/订单时间), and <b>NEW columns never seen before</b> "
           "(so future schema additions are flagged instead of silently ignored)."),
        _b("<b>3. Dedup</b> — merged on 订单号 (order id); the <b>incoming row wins</b> on conflict "
           "(latest export is authoritative)."),
        _b("<b>4. Write</b> rolling parquet store → <b>5. Rebuild</b> sales_cache.parquet from the "
           "in-memory frame (no re-read) → <b>6. Reload</b> dashboard data + refresh filter choices."),
        _sub("Flow — dashboard load (every start / Refresh Cache)"),
        _b("read_database(DASHBOARD_COLUMNS) — only the ~30 needed columns are read from the cache; "
           "staleness check: cache rebuilt automatically if any rolling store/xlsx is newer."),
        _b("_rename_legacy_columns — Chinese cache names (sku名称, 品牌商, 区号…) → English, "
           "so new columns work <b>without</b> a cache rebuild."),
        _b("_scrub_country_column — drops stray timestamps/app-names from country; "
           "Chinese country names → English."),
        _b("_add_region_column — 6 business regions (Asia, Middle East, Africa, Europe, Americas, Oceania)."),
        _b("_enrich_columns — B2C operator filled from brand (99.99% coverage); 是/否 flag columns "
           "cleaned of stray junk values."),
        _b("_optimise_dtypes — low-cardinality strings cast to pandas category for speed/memory."),
        _sub("Flow — full rebuild ('🔄 Rebuild Data Pipeline', 10–25 min)"),
        _p("Re-reads the authoritative source files (Agent Data.xlsx + Master Data.xlsx 'Whole' sheets "
           "in the Recon folder), overwrites BOTH rolling parquet stores and xlsx backups, then rebuilds "
           "the cache in-memory. Use after manually editing the source files. A full-screen overlay with "
           "elapsed timer is shown; afterwards the report lists cache columns not yet used by the dashboard."),
        _sub("Freshness signals"),
        _b("Sidebar badge: latest order date + cache build time; <b>amber</b> when data ≥2 days old "
           "(with an upload reminder), <b>red</b> ≥7 days."),
        _b("Staleness banner: warns when the source xlsx files are newer than the rolling database "
           "(i.e. someone edited source but didn't rebuild)."),
        PageBreak(),
    ]

    # ════════════════════ 4. BUSINESS RULES ════════════════════
    story += _section_header("4 · Business Rules & Calculations")
    story += [
        _sub("Order status accounting (订单状态)"),
        _grid_table(
            ["Group", "Raw values", "Share of orders"],
            [
                ["Successful", "充值成功", "~91% — the only group counted in default GMV"],
                ["Refunded", "已退款", "~7% (B2B 39.8k + B2C 37.0k orders)"],
                ["Cancelled", "已取消", "~2% (B2C only, 22.6k orders)"],
                ["Pending", "等待支付 · 待付款 · 等待处理 · 充值中", "<0.2%"],
            ],
            col_widths=[30 * mm, 80 * mm, INNER_W - 110 * mm]),
        _b("The sidebar <b>Order Status filter defaults to Successful</b> — all GMV/order KPIs show "
           "realised revenue. Switching to All restores gross numbers (~11% higher GMV)."),
        _b("The <b>Order Status & Quality section</b> (Revenue & Orders tab) deliberately bypasses "
           "this filter (uses the pre-status data) so refunds remain visible for analysis."),
        _b("ML models (forecast/churn/demand) always train on Successful orders only."),
        _sub("Revenue & margin definitions"),
        _b("<b>sales (GMV)</b> = 实际支付 (actually paid) when present, else 售价 (listed price)."),
        _b("<b>Gross margin</b> = sales − settlement_price (结算价); margin % = margin / sales."),
        _b("<b>AOV</b> = revenue ÷ unique orders. <b>Currency</b>: RMB base; USD via fixed rate; "
           "'Local Currency' uses fx_rates per selected market (falls back to RMB when market = All)."),
        _sub("Derivation & parsing rules"),
        _b("<b>B2C operator</b>: operator ← brand (品牌商); if brand empty, product name stripped of "
           "marketing suffixes (话费|流量|充值卡|缴费|数据|Data|Topup)."),
        _b("<b>Data-package volume</b>: parsed from sku_name first, then product. Patterns: TB / GB / "
           "bare G ('3.5G') / MB; '无限流量 / 不限量' → 'Unlimited (无限)' bucket (1 TB sentinel, sorts last). "
           "Parse coverage: 99.85% of 买流量 rows."),
        _b("<b>Data category</b> = product_category matching data|流量|数据. <b>Airtime categories</b> = "
           "充话费|后付费|PIN码|airtime|topup."),
        _b("<b>Denomination display label</b>: sku_name when present ('RM 50', '100000 Rp'), "
           "else formatted numeric denomination."),
        _b("<b>Destination market</b>: 区号 → country via the calling-code map (~100 codes, 99.4% mapped); "
           "<b>billing↔destination mismatch</b> uses containment matching with aliases "
           "(United States↔USA/Canada, DR Congo…) to avoid false positives."),
        _b("<b>Reseller signal</b>: a B2C user recharging ≥4 distinct numbers is counted as reseller-like."),
        _b("<b>Routing gap</b>: order with status 充值成功 but no usable 接口商订单号 "
           "(blank/'--'/'-'/nan treated as missing) — unreconcilable spend."),
        _sub("Display / performance caps (Excel downloads always keep the full data)"),
        _b("Denomination scorecard: top 500 rows on screen · Operator×Category pivot: top 200 rows · "
           "Campaign table: top 100 rows."),
        _sub("Aggregation safety rule (engineering)"),
        _p("Named-tuple/dict groupby aggregation (<font face='Courier'>df.groupby(...).agg(x=('col','fn'))</font>) "
           "is banned in this codebase: with pandas Categorical columns it raises «initializing a Series from a "
           "MultiIndex is not supported», which Shiny swallows into a blank chart. The sanctioned pattern is:"),
        Paragraph("grp = df.groupby(keys, observed=True)<br/>"
                  "agg = pd.DataFrame({'orders': grp['order_id'].nunique(),<br/>"
                  "&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;'revenue': grp['sales'].sum()}).reset_index()",
                  CODE),
        PageBreak(),
    ]

    # ════════════════════ 5. DASHBOARD STRUCTURE ════════════════════
    story += _section_header("5 · Dashboard Structure — 12 Tabs, Every Visualization")

    def tab_block(no, name, zh, desc, visuals):
        return [
            _sub(f"Tab {no} — {name} · {zh}"),
            _p(desc),
            _grid_table(["Visualization", "What it answers"], visuals,
                        col_widths=[78 * mm, INNER_W - 78 * mm]),
            Spacer(INNER_W, 2 * mm),
        ]

    story += tab_block(1, "Executive Overview", "执行概览",
        "The daily management view — anomalies first, then headline KPIs and mix.",
        [
            ["🚨 Anomaly Detection & Alerts", "Auto signals: last 7 days vs prior 4-week baseline"],
            ["📊 KPIs (GMV, Orders, AOV, Users, Markets) with PoP deltas", "Headline performance vs previous equal period"],
            ["⚡ PoP Top Movers strip", "Biggest rising/falling market, operator, product"],
            ["📈 Revenue & Order Volume Trend", "Daily/Weekly/Monthly/Quarterly/Yearly switchable"],
            ["🥧 Revenue by Segment · 🌐 by Region · 🏆 Top 5 Markets", "Mix and concentration at a glance"],
            ["📋 Segment Performance Summary table", "B2B vs B2C: sales, orders, users, AOV, share"],
        ])
    story += tab_block(2, "Performance Comparison", "业绩对比",
        "Pick any two date ranges (A vs B) and compare like-for-like.",
        [
            ["KPI variance cards (A vs B)", "Revenue/orders/AOV deltas with direction colouring"],
            ["Aligned trend overlay", "Day-of-period aligned revenue curves"],
            ["Top movers tables", "Markets/operators/denominations that moved most between periods"],
        ])
    story += tab_block(3, "Revenue & Orders", "收入与订单",
        "Revenue accounting detail plus the Order Status & Quality module (always shows ALL statuses).",
        [
            ["Revenue & Orders KPIs · by-segment charts · AOV by segment", "Core monetisation detail"],
            ["📋 Revenue & Orders by Market table", "Per-market, per-segment breakdown"],
            ["🚦 Order Status KPIs", "Success rate, refund rate + refunded GMV, cancellations, pending"],
            ["📊 Order Count by Status × Segment", "Where failures concentrate"],
            ["📉 Monthly Refund Rate Trend", "Quality trend per segment — spikes = supplier incidents"],
            ["⚠ Refund Rate by Operator (≥200 orders)", "Supplier-quality ranking (e.g. Orange France ~68%)"],
        ])
    story += tab_block(4, "Market Intelligence", "市场洞察",
        "Where revenue comes from (billing) AND where recharges land (destination).",
        [
            ["🗺️ World map · Top-15 markets by revenue/orders · AOV by market", "Geographic performance"],
            ["🚀 Momentum risers/decliners · 💎 Opportunity matrix · 🧭 Expansion radar", "Strategic prioritisation (Orders × AOV quadrants)"],
            ["📅 Monthly heatmap · Market scorecard · Avg denomination by market", "Seasonality and per-market KPIs"],
            ["🌍 Top Recharge Destinations (区号)", "True destination markets — Egypt #1 (414k), MY, ID, IQ, MA"],
            ["🔀 Billing vs Destination Mismatch", "Cross-border gifting/remittance flows by corridor"],
            ["📱 Beneficiary Numbers — reach & stickiness", "Unique numbers, repeat top-ups, ≥4-numbers reseller signal"],
        ])
    story += [PageBreak()]
    story += tab_block(5, "Operational Intelligence", "运营智能",
        "Daily operating rhythm plus the Iraq Pinstore deep-dive.",
        [
            ["Ops KPIs (avg daily revenue/orders, peak day, peak hour)", "Operating cadence"],
            ["📈 Revenue velocity (bars+line) · 📉 Day-over-day change", "Momentum and volatility"],
            ["🕐 Activity heatmap (weekday × hour)", "When customers buy — staffing/promo timing"],
            ["Iraq Pinstore module (KPIs, 12-week trend, denomination heatmap, estimation table)", "PIN-store purchasing plan support"],
        ])
    story += tab_block(6, "Supplier & Operator Performance", "供应商绩效",
        "Operator economics plus fulfillment health.",
        [
            ["🤝 Snapshot KPIs · concentration risk card", "Operator count, top-3 share, margin headline"],
            ["💰 Cost vs margin (top 15) · 📈 margin % trend · 📊 Pareto", "Profitability and concentration"],
            ["📋 Operator scorecard", "Sales/orders/AOV/margin/growth/share per operator"],
            ["🩺 Fulfillment KPIs", "Supplier order-id coverage, unreconcilable successful orders (~10.3k), PIN share, Useepay share"],
            ["⚠ Routing-gap chart", "Successful orders missing 接口商订单号 by operator"],
        ])
    story += tab_block(7, "Product & Denomination Analysis", "产品与面值",
        "Category portfolio → airtime denominations → data packages → operator cross-views. "
        "Page-level product-category filter applies to all charts here.",
        [
            ["🗂️ Category Overview (KPIs, revenue&orders bars, monthly trend top 6)", "Which product line monetises vs drives traffic"],
            ["🌳 Treemap · 📈 top-5 product trend · top products · by-segment", "Product portfolio detail"],
            ["💵 Airtime Sales by Denomination ('RM 50', '100000 Rp')", "Which face values customers buy (充话费/后付费/PIN码)"],
            ["📡 Airtime Denomination × Operator", "Operator ownership of each face value"],
            ["📶 Data Package Orders & Revenue by Volume · 📊 by Size Tier", "Package-size demand curve (sku-parsed, incl. Unlimited)"],
            ["📦 Data Package Orders by Operator × Volume Size", "Each operator's package mix"],
            ["📋 Data Package Sales Matrix (operator × package, Excel)", "Package-level pricing negotiations"],
            ["🔢 Denomination × Operator heatmap · 💰 revenue grouped bars · 🔝 top denominations", "Denomination ownership and volume leaders"],
            ["📋 Denomination Scorecard (top 500 + Excel)", "Orders/sales/cost/margin per operator × denomination × product"],
            ["📡/📦 Revenue & Order Volume by Category × Operator · 📋 pivot (Excel)", "Brand-level category cross view"],
        ])
    story += [PageBreak()]
    story += tab_block(8, "Customer Analytics", "客户分析",
        "B2B agent intelligence + B2C customer lifecycle.",
        [
            ["🏢 B2B agent KPIs · Top-20 agents · performance table (Top 50)", "Agent concentration and ranking by agent_name"],
            ["👥 User metrics · churn-risk panel · registration funnel", "Active/repeat customers, time-to-first-purchase"],
            ["🌍 IP origin map · new vs returning · acquisition rate", "Where B2C users order from; growth quality"],
            ["📊 User Source analysis (来源)", "Channel mix: 微信小程序/公众号/支付宝 revenue & customers"],
            ["📚 Cohort retention heatmap · LTV curves · cohort KPIs", "Retention and lifetime value by acquisition month"],
            ["Order-frequency distribution · per-segment averages · summary table", "Engagement depth"],
        ])
    story += tab_block(9, "Marketing & Promotions", "营销与促销",
        "Built from the previously-unused coupon/promo columns (B2C).",
        [
            ["🎟️ Promotion KPIs", "Coupon usage rate, spend (优惠券金额), coupon-order GMV, new-user promo orders"],
            ["📈 Monthly coupon spend vs coupon-order revenue", "Promotion ROI trajectory"],
            ["🏷️ Campaign performance table (Excel)", "Per-coupon orders, spend, GMV, avg discount, GMV per 1 spend"],
            ["⚖️ Coupon vs non-coupon customers", "AOV and repeat-purchase comparison — do coupons buy loyalty?"],
            ["🆕 New-user promo trend", "Acquisition-promo volume and share of orders"],
            ["⭐ Featured (badge) vs non-featured products", "Merchandising effectiveness (是否角标产品)"],
        ])
    story += tab_block(10, "🤖 AI Predictions", "AI预测",
        "On-demand ML — buttons trigger model runs on successful orders.",
        [
            ["Revenue Forecast (chart, metrics, table)", "4–16 week ensemble forecast with confidence band"],
            ["Churn Prediction (metrics, ROC, feature importance, at-risk table)", "Which B2C customers are about to lapse"],
            ["Product Demand Forecast (table)", "4-week demand outlook per operator/product"],
        ])
    story += [PageBreak()]

    # ════════════════════ 6. FILTERS, UX & LANGUAGE ════════════════════
    story += _section_header("6 · Filters, UX & Language")
    story += [
        _sub("Sidebar filters (applied via the ↵ Enter button)"),
        _grid_table(
            ["Filter", "Options / behaviour"],
            [
                ["Customer Segment", "All / B2B / B2C"],
                ["Order Status", "Successful (default) / All / Non-successful / Refunded / Cancelled / Pending"],
                ["Region / Continent", "Asia, Middle East, Africa, Europe, Americas, Oceania"],
                ["Market (Country)", "Searchable; includes a user-managed 重点国家 (key countries) group"],
                ["Reporting Currency", "RMB / USD / Local Currency (per selected market)"],
                ["Reporting Period", "Daily / Weekly / Monthly / Quarterly / Yearly trend granularity"],
                ["Date Range", "Quick periods (Today…All Time), month pickers, custom dates"],
            ],
            col_widths=[45 * mm, INNER_W - 45 * mm]),
        _sub("Sidebar behaviour"),
        _b("<b>📌 Pin button</b> (next to 'Advanced Filters'): pinned (default) = classic fixed sidebar. "
           "Unpinned = collapses to a slim '☰ FILTERS · 筛选' rail; hover/touch expands it; it re-collapses "
           "350 ms after the pointer leaves (waits while a dropdown is open or a field is focused). "
           "Preference persists in the browser (localStorage)."),
        _b("Navigation tabs are <b>sticky at the top</b> and compact; the active tab is an indigo pill."),
        _b("Per-tab <b>analyst remarks</b> (saved per month, included in PDF exports); "
           "<b>Download/Export</b>: filtered CSV/Excel + multi-page PDF report."),
        _sub("Bilingual system (EN / 中文)"),
        _b("Headings & descriptions: dual <font face='Courier'>lang-en/lang-zh</font> spans toggled by CSS."),
        _b("Chart titles, axis labels, legends and table headers: server-side <b>_tt()</b> translator — "
           "an ordered longest-first substring map (CHART_PHRASES, ~150 entries in translations.py). "
           "Charts re-render on language switch; dynamic parts (currency, numbers) survive."),
        _b("To fix or add a translation: edit one line in CHART_PHRASES — no chart code changes needed."),
        PageBreak(),
    ]

    # ════════════════════ 7. ML MODELS ════════════════════
    story += _section_header("7 · AI / ML Models (ml_predictions.py)")
    story += [
        _grid_table(
            ["Model", "Algorithms", "Features / method", "Output"],
            [
                ["Revenue forecast",
                 "GradientBoosting · RandomForest · MLP (scaled pipeline) — ensemble average",
                 "Weekly series; 12 features: t, lags 1/2/4/8/12, roll 4/8, month & week-of-year sin/cos; "
                 "recursive multi-step forecast; backtest RMSE/MAE/R² per model",
                 "4–16 week forecast + confidence band + best-model metrics"],
                ["Churn prediction",
                 "LogisticRegression · RandomForest · GradientBoosting · ExtraTrees",
                 "10 RFM-style features (recency, frequency, monetary, tenure, intervals, recent activity); "
                 "5-fold stratified CV with out-of-fold probabilities; Youden-J threshold",
                 "AUC/F1 per model, ROC curves, feature importance, at-risk customer table"],
                ["Demand forecast",
                 "Per-product weekly trend (polyfit) with robust per-group error handling",
                 "Operator/product weekly order counts (≥2 weeks history)",
                 "4-week demand outlook table"],
            ],
            col_widths=[30 * mm, 62 * mm, 105 * mm, INNER_W - 197 * mm]),
        _b("All three train on <b>Successful orders only</b> (refunds/cancellations excluded)."),
        _b("If Windows App Control blocks scikit-learn DLLs, the dashboard still starts — the AI tab "
           "shows a clear 'ML unavailable' message instead of crashing (guarded import + per-run try/except)."),
    ]

    # ════════════════════ 8. RELIABILITY ════════════════════
    story += _section_header("8 · Reliability & Error Handling")
    story += [
        _b("<b>safe_render / safe_grid decorators</b> wrap all ~120 render functions: any exception "
           "becomes a visible red error box naming the chart and cause (and is logged as "
           "[render-error]) — Shiny never silently blanks a chart again."),
        _b("<b>_no_data() placeholders</b>: every data-dependent chart shows an explanatory grey message "
           "('needs B2C rows', 'click Refresh Cache', …) instead of empty space."),
        _b("<b>Import guard</b> for ml_predictions (App Control), error-dict plumbing for all three "
           "model runs, and DataGrid error tables for table renderers."),
        _b("<b>Validation on import</b>: unknown-column detection means a schema change in the exports "
           "is reported on the next upload, not discovered weeks later."),
    ]

    # ════════════════════ 9. OPERATIONS RUNBOOK ════════════════════
    story += _section_header("9 · Operations Runbook")
    story += [
        _sub("Start the dashboard"),
        Paragraph(r'cd "C:\Disk\LiuLian Tech Sdn. Bhd\Code\Sales Dashboard"<br/>'
                  r'sales_env\Scripts\python.exe -m shiny run sales_dashboard.py --port 8050',
                  CODE),
        _b("Always use <b>sales_env</b> — the system Python 3.11 is blocked from loading scikit-learn "
           "DLLs by Windows App Control (and the block is intermittent even in sales_env; the app "
           "degrades gracefully)."),
        _sub("Daily routine"),
        _b("1. Import Data tab → upload the day's Agent/Master export → Process (seconds). "
           "Read the validation report (date range, duplicates, new columns)."),
        _b("2. The sidebar freshness badge should show today's date and a green dot."),
        _sub("Maintenance actions (sidebar)"),
        _grid_table(
            ["Action", "When", "Duration"],
            [
                ["🔃 Refresh Cache", "Pipeline was rebuilt outside the dashboard", "<1 s"],
                ["🔄 Rebuild Data Pipeline", "Source xlsx files were edited manually — overwrites rolling stores", "10–25 min"],
                ["💾 Export Excel Backup", "You need the rolling DB as xlsx (it is no longer written on every upload)", "a few min"],
            ],
            col_widths=[48 * mm, 105 * mm, INNER_W - 153 * mm]),
        _sub("Key paths"),
        _info_table([
            ("Project", r"C:\Disk\LiuLian Tech Sdn. Bhd\Code\Sales Dashboard"),
            ("Database folder", r"...\Sales Dashboard\database\ (rolling parquet, xlsx backups, sales_cache.parquet)"),
            ("Source files", r"...\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\Agent Data.xlsx + Master Data.xlsx"),
            ("Upload archive", r"...\Raw Data (30 Nov - 23 Mac)\Data\Agent Data and ...\Data\Master Data"),
            ("Regenerate this PDF", r"sales_env\Scripts\python.exe generate_doc_pdf.py"),
        ], col_widths=[42 * mm, INNER_W - 42 * mm]),
        PageBreak(),
    ]

    # ════════════════════ 10. CAVEATS ════════════════════
    story += _section_header("10 · Known Caveats & Data-Quality Asks")
    story += [
        _b("<b>取消原因 (cancel reason) is empty upstream</b> — refund/cancellation root-cause analysis "
           "is impossible until the platform populates it. → Request to the platform team."),
        _b("<b>B2C operator is derived</b> (from 品牌商 / product name) — treat brand-level operator views "
           "for B2C as 'brand' rather than network operator where the distinction matters."),
        _b("<b>useepay订单号 present on only ~54%</b> of B2C orders — gateway mix is a lower bound for Useepay."),
        _b("<b>sales_listed (售价)</b> becomes available for discount-depth analysis only after the next "
           "full pipeline rebuild (normalisation now keeps it); coupon_amount already covers coupon ROI."),
        _b("<b>Destination mismatch</b> uses calling-code granularity — shared codes (+1 USA/Canada, "
           "+7 Russia/Kazakhstan) are aliased, not split."),
        _b("Notable findings baked into current data: ~11% of raw GMV is non-successful; Egypt is the top "
           "recharge destination; refund-rate outliers: Orange France ~68%, Orange Spain ~45%, "
           "Ultra Mobile PayGo ~38%; ~10.3k successful orders lack a supplier order id."),
    ]

    # ════════════════════ APPENDIX ════════════════════
    story += _section_header("Appendix · Glossary 术语表")
    story += [
        _grid_table(
            ["Term", "中文", "Definition"],
            [
                ["GMV", "商品交易总额", "Gross Merchandise Value — sum of sales (实际支付 preferred)"],
                ["AOV", "平均订单价值", "Average Order Value = revenue ÷ unique orders"],
                ["Segment", "客户分类", "B2B (Agent resellers) vs B2C (consumer app)"],
                ["Operator", "运营商", "Mobile network / supplier; for B2C derived from 品牌商"],
                ["Denomination", "面值", "Face value of the recharge (e.g. RM 50)"],
                ["Data package", "流量套餐", "Mobile-data product; size parsed from SKU名称"],
                ["Settlement price", "结算价", "Cost paid to the supplier — basis of gross margin"],
                ["Refund rate", "退款率", "已退款 orders ÷ all orders in scope"],
                ["Routing gap", "路由缺口", "Successful order missing 接口商订单号 (unreconcilable)"],
                ["Coupon ROI", "优惠券回报", "Coupon-order GMV relative to 优惠券金额 spend"],
                ["Destination", "充值目的地", "Market implied by the 区号 calling code"],
                ["Beneficiary", "受益号码", "The 充值号码 phone number receiving the top-up"],
                ["Cohort", "客群批次", "Customers grouped by month of first order"],
                ["LTV", "客户终身价值", "Cumulative revenue per customer since first order"],
                ["PoP", "环比", "Period-over-period — vs the previous equally-long period"],
            ],
            col_widths=[35 * mm, 32 * mm, INNER_W - 67 * mm]),
        Spacer(INNER_W, 6 * mm),
        Paragraph(f"— End of documentation · generated {generated} —", CAPTION),
    ]

    doc.build(story)
    return buf.getvalue()


if __name__ == "__main__":
    out = Path(__file__).parent / "Sales_Dashboard_Documentation.pdf"
    pdf = build_doc_pdf()
    out.write_bytes(pdf)
    print(f"Written: {out} ({len(pdf):,} bytes)")
