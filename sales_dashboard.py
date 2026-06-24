import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from shiny import App, ui, reactive, render
import json
import re as _re
from pathlib import Path

import db_utils
from country_mapping import translate_country, CN_TO_EN
import theme as T
import charts
import fx_rates
import remarks_utils
try:
    import ml_predictions
    ML_IMPORT_ERROR = None
except Exception as _ml_exc:  # e.g. Windows App Control blocking sklearn DLLs
    ml_predictions = None
    ML_IMPORT_ERROR = f"{type(_ml_exc).__name__}: {_ml_exc}"
    print(f"[startup] ml_predictions unavailable — AI Predictions tab degraded: {ML_IMPORT_ERROR}",
          flush=True)
from translations import T_UI, translate_chart_text

_KNOWN_SUPPLIER_COUNT = 16  # Configured: total distinct supplier companies on platform

# Pattern matching values like "2023-02-23 12:25:34" or "2023/2/23" — used
# to scrub stray timestamps that occasionally land in the country column
# because of bad cells in source Excel files.
_DATE_LIKE = _re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def _clean_country_choices(series):
    """Sorted unique country names with stray timestamps / blank rows removed."""
    s = series.dropna().astype(str)
    s = s[s.str.strip() != ""]
    s = s[~s.str.match(_DATE_LIKE)]
    return sorted(s.unique().tolist())

# Custom CSS for professional styling
css = """
/* ============================================================
   Design system — enterprise BI look
   Brand: indigo #4F46E5 / #5B6CFF · Neutrals: slate
   ============================================================ */
:root {
    --brand:        #4F46E5;
    --brand-soft:   #EEF2FF;
    --brand-strong: #4338CA;
    --ink:          #0F172A;
    --ink-2:        #334155;
    --muted:        #64748B;
    --line:         #E6EAF2;
    --surface:      #FFFFFF;
    --canvas:       #F4F6FB;
    --radius:       14px;
    --shadow-sm:    0 1px 2px rgba(15, 23, 42, 0.05);
    --shadow-md:    0 2px 6px rgba(15, 23, 42, 0.05), 0 1px 2px rgba(15, 23, 42, 0.04);
    --shadow-lg:    0 12px 28px rgba(15, 23, 42, 0.10), 0 4px 10px rgba(15, 23, 42, 0.05);
}

body {
    font-family: 'Inter', 'Segoe UI Variable Text', 'Segoe UI', system-ui,
                 -apple-system, 'PingFang SC', 'Microsoft YaHei', sans-serif;
    background-color: var(--canvas);
    color: var(--ink);
    -webkit-font-smoothing: antialiased;
    text-rendering: optimizeLegibility;
}

/* Subtle, consistent scrollbars */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb { background: #CBD5E1; border-radius: 6px; border: 2px solid var(--canvas); }
::-webkit-scrollbar-thumb:hover { background: #94A3B8; }

::selection { background: var(--brand-soft); color: var(--brand-strong); }

/* ---- Sidebar: bright indigo-violet (white text stays readable) ---- */
.sidebar {
    background: linear-gradient(168deg, #4F46E5 0%, #5B50E6 50%, #6D28D9 100%);
    color: white;
    border-radius: var(--radius);
    padding: 20px;
    margin: 10px;
    box-shadow: var(--shadow-lg);
    font-size: 0.9em;
    border: 1px solid rgba(255, 255, 255, 0.10);
}

.sidebar h2 {
    color: white;
    border-bottom: 1px solid rgba(255, 255, 255, 0.18);
    padding-bottom: 12px;
    margin-bottom: 18px;
    font-size: 1.12em;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
}

.sidebar h4 {
    color: rgba(255, 255, 255, 0.92);
    font-size: 0.8em;
    margin-bottom: 8px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.06em;
}

.sidebar p,
.sidebar .form-group label,
.sidebar .selectize-control.single .item {
    font-size: 0.85em;
}

.sidebar .selectize-control.single .item {
    color: #1E293B;
}

.sidebar .form-group label {
    color: white;
    font-weight: 600;
}

.sidebar select, .sidebar input {
    background-color: rgba(255, 255, 255, 0.96);
    border: none;
    border-radius: 8px;
    padding: 8px 12px;
    color: #1E293B;
}

.sidebar select:focus, .sidebar input:focus,
.sidebar .selectize-input.focus {
    outline: none;
    box-shadow: 0 0 0 3px rgba(255, 255, 255, 0.55);
}

.sidebar .selectize-input {
    border-radius: 8px;
    border: none;
    color: #1E293B;
}

/* Dark-on-white contrast for EVERYTHING the user types/picks in the sidebar */
.sidebar .selectize-input input,
.sidebar .selectize-input .item,
.sidebar select, .sidebar select option,
.sidebar input[type="date"], .sidebar input[type="text"],
.sidebar textarea, .sidebar .form-control {
    color: #1E293B !important;
    background-color: rgba(255, 255, 255, 0.96);
}

.selectize-dropdown, .selectize-dropdown .option,
.selectize-dropdown .optgroup-header {
    color: #1E293B !important;
}

.selectize-dropdown .option.active {
    background: #EEF2FF;
    color: #4338CA !important;
}

/* ---- Sidebar pin button (injected by SIDEBAR_UX_JS) ---- */
#sb-pin-btn {
    float: right;
    background: rgba(255, 255, 255, 0.16);
    color: white;
    border: 1px solid rgba(255, 255, 255, 0.45);
    border-radius: 7px;
    font-size: 0.62em;
    font-weight: 700;
    padding: 3px 9px;
    cursor: pointer;
    letter-spacing: 0.02em;
    transition: all 0.15s;
}
#sb-pin-btn:hover { background: rgba(255, 255, 255, 0.32); }
#sb-pin-btn.pinned { background: white; color: #4F46E5; border-color: white; }

/* ---- Collapsed sidebar: turn bslib's toggle into a clear rail ---- */
.bslib-sidebar-layout > .collapse-toggle {
    color: #4F46E5;
}

.bslib-sidebar-layout.sidebar-collapsed > .collapse-toggle {
    background: linear-gradient(180deg, #4F46E5 0%, #6D28D9 100%);
    color: white !important;
    width: 30px;
    height: 64vh;
    min-height: 220px;
    top: 16px;
    border-radius: 0 12px 12px 0;
    box-shadow: 4px 0 14px rgba(79, 70, 229, 0.35);
    display: flex;
    align-items: center;
    justify-content: center;
}

.bslib-sidebar-layout.sidebar-collapsed > .collapse-toggle::after {
    content: "☰ FILTERS · 筛选";
    writing-mode: vertical-rl;
    font-size: 0.72em;
    font-weight: 700;
    letter-spacing: 0.18em;
    color: rgba(255, 255, 255, 0.95);
    white-space: nowrap;
}

/* ---- Page header: deep slate → indigo, left aligned ---- */
.main-header {
    background:
        radial-gradient(900px 240px at 90% -40%, rgba(99, 102, 241, 0.35), transparent 60%),
        linear-gradient(120deg, #0F172A 0%, #1E1B4B 55%, #3730A3 100%);
    color: white;
    padding: 26px 32px;
    margin: 10px 10px 18px 10px;
    border-radius: var(--radius);
    text-align: left;
    box-shadow: var(--shadow-lg);
    border: 1px solid rgba(255, 255, 255, 0.06);
}

.main-header h1 {
    margin: 0;
    font-size: 1.55em;
    font-weight: 700;
    letter-spacing: -0.015em;
    line-height: 1.25;
}

.main-header p {
    font-size: 0.88em;
    color: rgba(255, 255, 255, 0.72);
    letter-spacing: 0.01em;
}

/* ---- KPI metric cards ---- */
.metric-card {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 20px 22px;
    margin: 8px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-md);
    text-align: left;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    position: relative;
    overflow: hidden;
    min-width: 200px;
    flex: 1;
}

.metric-card::before {
    content: "";
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #4F46E5 0%, #8B5CF6 60%, #EC4899 130%);
    opacity: 0.9;
}

.metric-card:hover {
    transform: translateY(-2px);
    box-shadow: var(--shadow-lg);
    border-color: #C7D2FE;
}

.metric-card h4 {
    color: var(--muted);
    margin: 8px 0 6px 0;
    font-size: 0.74em;
    text-transform: uppercase;
    letter-spacing: 0.07em;
    font-weight: 700;
}

.metric-card p {
    font-size: 1.9em;
    font-weight: 750;
    margin: 0 0 4px 0;
    color: var(--ink);
    letter-spacing: -0.025em;
    line-height: 1.12;
    font-variant-numeric: tabular-nums;
}

.metric-card small { font-variant-numeric: tabular-nums; }

/* KPI grid used by Order Status & other KPI strips */
.metrics-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(225px, 1fr));
    gap: 4px;
}

/* ---- Chart / table cards ---- */
.chart-container {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 22px 24px;
    margin: 12px 8px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-md);
}

.chart-container h3 {
    color: var(--ink);
    border-bottom: 1px solid #EEF1F7;
    padding-bottom: 12px;
    margin-bottom: 18px;
    font-weight: 650;
    font-size: 1.02em;
    letter-spacing: -0.01em;
}

/* ---- Navigation tabs: compact pill toolbar, fixed to the top ---- */
.nav-tabs {
    position: sticky;
    top: 0;
    z-index: 1030;
    background: rgba(255, 255, 255, 0.97);
    backdrop-filter: blur(6px);
    border: 1px solid var(--line);
    border-radius: var(--radius);
    box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08);
    padding: 4px;
    margin: 0 8px 12px 8px;
    gap: 2px;
}

.nav-tabs .nav-item { margin-bottom: 0; }

.nav-tabs .nav-link {
    border: none !important;
    border-radius: 8px;
    font-weight: 600;
    font-size: 0.8em;
    color: #475569;
    padding: 6px 11px;
    white-space: nowrap;
    transition: background 0.15s ease, color 0.15s ease;
}

.nav-tabs .nav-link:hover {
    background: #F1F5F9;
    color: var(--ink);
    isolation: isolate;
}

.nav-tabs .nav-link.active {
    background: var(--brand-soft);
    color: var(--brand-strong);
    box-shadow: inset 0 0 0 1px #C7D2FE;
}

.data-table {
    background: var(--surface);
    border-radius: var(--radius);
    padding: 20px 24px;
    margin: 12px 8px;
    border: 1px solid var(--line);
    box-shadow: var(--shadow-md);
}

.data-table h3 {
    color: var(--ink);
    border-bottom: 1px solid #EEF1F7;
    padding-bottom: 12px;
    margin-bottom: 18px;
    font-weight: 650;
    font-size: 1.02em;
    letter-spacing: -0.01em;
}

/* Shiny data-grid polish (selectors are defensive: harmless if unmatched) */
shiny-data-frame { font-size: 0.875em; }
shiny-data-frame .shiny-data-grid { border: 1px solid var(--line); border-radius: 10px; }
shiny-data-frame thead th {
    background: #F8FAFC;
    color: #475569;
    font-size: 0.82em;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 700;
    border-bottom: 1px solid var(--line) !important;
}
shiny-data-frame tbody td {
    font-variant-numeric: tabular-nums;
    border-bottom: 1px solid #F1F5F9;
}
shiny-data-frame tbody tr:hover td { background: #F6F8FE; }

/* ---- Metric icons: tinted chips instead of bare emoji ---- */
.metric-icon {
    font-size: 1.35em;
    margin-bottom: 10px;
    width: 44px;
    height: 44px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 11px;
    opacity: 1;
}

.sales-icon     { background: #ECFDF5; color: #059669; }
.orders-icon    { background: var(--brand-soft); color: var(--brand); }
.users-icon     { background: #FFFBEB; color: #D97706; }
.countries-icon { background: #FEF2F2; color: #DC2626; }
.supplier-icon  { background: #F0F9FF; color: #0284C7; }

.filter-section {
    background-color: rgba(255, 255, 255, 0.08);
    padding: 14px;
    margin: 10px 0;
    border-radius: 10px;
    border: 1px solid rgba(255, 255, 255, 0.08);
}

.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
    gap: 15px;
}

.detail-stat {
    background: var(--surface);
    padding: 16px;
    border-radius: 10px;
    border: 1px solid var(--line);
    border-left: 4px solid var(--brand);
    box-shadow: var(--shadow-sm);
}

.detail-stat-label {
    font-size: 0.78em;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: 0.05em;
    font-weight: 700;
    margin-bottom: 8px;
}

.detail-stat-value {
    font-size: 1.5em;
    font-weight: 700;
    color: var(--brand-strong);
    margin-bottom: 5px;
    font-variant-numeric: tabular-nums;
}

.detail-stat-change {
    font-size: 0.8em;
    color: var(--muted);
}

.refresh-btn {
    background: rgba(255, 255, 255, 0.14) !important;
    color: white !important;
    border: 1px solid rgba(255, 255, 255, 0.45) !important;
    border-radius: 9px !important;
    padding: 8px 20px !important;
    font-size: 0.9em !important;
    font-weight: 600 !important;
    cursor: pointer !important;
    width: 100% !important;
    transition: all 0.18s !important;
    margin-top: 10px !important;
}

.refresh-btn:hover {
    background: rgba(255, 255, 255, 0.30) !important;
    border-color: white !important;
    transform: translateY(-1px) !important;
}

.refresh-btn:active {
    transform: translateY(0) !important;
}

.help-icon {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #E8ECF6;
    color: #475569;
    font-size: 0.72em;
    font-weight: 700;
    margin-left: 8px;
    cursor: help;
    transition: all 0.15s;
    user-select: none;
}

.help-icon:hover {
    background: var(--brand);
    color: white;
}

/* Generic buttons / inputs in the light content area */
.btn-primary, .btn-default.action-button {
    border-radius: 9px;
}

a { color: var(--brand); }
a:hover { color: var(--brand-strong); }

/* ---- Full-screen loading overlay (shown during Reload from source) ---- */
#reload-overlay {
    position: fixed;
    inset: 0;
    background: rgba(15, 23, 42, 0.85);
    backdrop-filter: blur(6px);
    display: none;
    align-items: center;
    justify-content: center;
    z-index: 9999;
    animation: fadeIn 0.2s ease-out;
}
#reload-overlay.visible { display: flex; }

#reload-overlay .card {
    background: white;
    padding: 44px 56px;
    border-radius: 16px;
    box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
    text-align: center;
    max-width: 520px;
    width: 90%;
}

#reload-overlay .spinner {
    margin: 0 auto 24px auto;
    width: 60px;
    height: 60px;
    border: 6px solid #E2E8F0;
    border-top-color: #5B6CFF;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}

#reload-overlay .title {
    font-size: 1.25em;
    font-weight: 700;
    color: #0F172A;
    margin-bottom: 10px;
}

#reload-overlay .subtitle {
    color: #475569;
    font-size: 0.95em;
    line-height: 1.55;
    margin-bottom: 18px;
}

#reload-overlay .warning {
    color: #92400E;
    background: #FEF3C7;
    border-left: 4px solid #D97706;
    padding: 10px 14px;
    border-radius: 6px;
    font-size: 0.88em;
    text-align: left;
    margin-bottom: 18px;
}

#reload-overlay .elapsed {
    color: #94A3B8;
    font-size: 0.85em;
    font-variant-numeric: tabular-nums;
    margin-bottom: 18px;
}

#reload-overlay .close-btn {
    padding: 8px 20px;
    background: #F1F5F9;
    border: 1px solid #CBD5E1;
    border-radius: 8px;
    cursor: pointer;
    color: #475569;
    font-size: 0.85em;
}

#reload-overlay .close-btn:hover {
    background: #E2E8F0;
}

@keyframes spin {
    to { transform: rotate(360deg); }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to   { opacity: 1; }
}
"""


# JS for sidebar hover-expand + pin behaviour. Injected once in head.
SIDEBAR_UX_JS = """
(function() {
    function init() {
        var layout = document.querySelector('.bslib-sidebar-layout');
        if (!layout) { setTimeout(init, 500); return; }
        var aside  = layout.querySelector('aside.sidebar');
        var toggle = layout.querySelector('button.collapse-toggle');
        if (!aside || !toggle) return;

        var pinned = (localStorage.getItem('dash_sidebar_pinned') || '1') === '1';
        var collapseTimer = null;

        function isCollapsed() { return layout.classList.contains('sidebar-collapsed'); }
        function expand()   { if (isCollapsed())  toggle.click(); }
        function collapse() { if (!isCollapsed()) toggle.click(); }

        // --- pin button in the sidebar header ---
        var pinBtn = document.createElement('button');
        pinBtn.id = 'sb-pin-btn';
        pinBtn.type = 'button';
        pinBtn.title = 'Pinned: sidebar stays open. Unpinned: collapses to a rail, expands on hover.';
        function renderPin() {
            pinBtn.textContent = pinned ? '\\ud83d\\udccc Pinned' : '\\ud83d\\udccd Pin';
            pinBtn.classList.toggle('pinned', pinned);
        }
        renderPin();
        pinBtn.addEventListener('click', function(e) {
            e.stopPropagation();
            pinned = !pinned;
            localStorage.setItem('dash_sidebar_pinned', pinned ? '1' : '0');
            renderPin();
            if (pinned) { cancelCollapse(); expand(); }
            else { scheduleCollapse(700); }
        });
        var h2 = aside.querySelector('h2');
        if (h2) h2.appendChild(pinBtn); else aside.prepend(pinBtn);

        function cancelCollapse() {
            if (collapseTimer) { clearTimeout(collapseTimer); collapseTimer = null; }
        }
        function dropdownOpen() {
            return !!document.querySelector('.selectize-input.dropdown-active');
        }
        function scheduleCollapse(delay) {
            cancelCollapse();
            if (pinned) return;
            collapseTimer = setTimeout(function() {
                // don't yank the sidebar away mid-interaction
                if (dropdownOpen() || aside.contains(document.activeElement)) {
                    scheduleCollapse(900);
                    return;
                }
                collapse();
            }, delay || 350);
        }

        [aside, toggle].forEach(function(el) {
            el.addEventListener('mouseenter', function() { cancelCollapse(); expand(); });
            el.addEventListener('mouseleave', function() { scheduleCollapse(350); });
            el.addEventListener('touchstart', function() { cancelCollapse(); expand(); },
                                {passive: true});
        });

        // start collapsed when unpinned
        if (!pinned) scheduleCollapse(1000);
    }
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() { setTimeout(init, 400); });
    } else {
        setTimeout(init, 400);
    }
})();
"""


# JS that wires the overlay to the Reload button. Injected once in head.
RELOAD_OVERLAY_JS = """
(function() {
    function init() {
        // Build the overlay once
        if (document.getElementById('reload-overlay')) return;
        var overlay = document.createElement('div');
        overlay.id = 'reload-overlay';
        overlay.innerHTML = '' +
            '<div class="card">' +
                '<div class="spinner"></div>' +
                '<div class="title">Reloading from source xlsx</div>' +
                '<div class="subtitle">' +
                    'Re-reading <b>Master Data.xlsx</b> + <b>Agent Data.xlsx</b>,<br>' +
                    'rebuilding the rolling database and parquet cache.' +
                '</div>' +
                '<div class="warning">' +
                    '⚠ This typically takes 5–10 minutes. Please don\\'t close this tab — ' +
                    'the dashboard will refresh automatically when done.' +
                '</div>' +
                '<div class="elapsed">Elapsed: <span id="reload-elapsed">0:00</span></div>' +
                '<button class="close-btn" id="reload-overlay-close">' +
                    'Dismiss (reload keeps running in the background)' +
                '</button>' +
            '</div>';
        document.body.appendChild(overlay);

        var startTs = null;
        var timer = null;
        var pollTimer = null;
        var safetyTimer = null;

        function formatElapsed(ms) {
            var s = Math.floor(ms / 1000);
            var m = Math.floor(s / 60);
            s = s % 60;
            return m + ':' + (s < 10 ? '0' : '') + s;
        }

        function show() {
            overlay.classList.add('visible');
            startTs = Date.now();
            if (timer) clearInterval(timer);
            timer = setInterval(function() {
                var el = document.getElementById('reload-elapsed');
                if (el) el.textContent = formatElapsed(Date.now() - startTs);
            }, 1000);

            // Poll the sidebar status panel for the done marker
            if (pollTimer) clearInterval(pollTimer);
            pollTimer = setInterval(checkDone, 2000);

            // Safety: auto-hide after 30 minutes (full reload takes ~10-25 min)
            if (safetyTimer) clearTimeout(safetyTimer);
            safetyTimer = setTimeout(hide, 30 * 60 * 1000);
        }

        function hide() {
            overlay.classList.remove('visible');
            if (timer) { clearInterval(timer); timer = null; }
            if (pollTimer) { clearInterval(pollTimer); pollTimer = null; }
            if (safetyTimer) { clearTimeout(safetyTimer); safetyTimer = null; }
        }

        function checkDone() {
            var panel = document.getElementById('import_status_ui');
            if (!panel) return;
            var text = panel.innerText || '';
            if (text.indexOf('Source xlsx reloaded successfully') !== -1 ||
                text.indexOf('Reload failed') !== -1) {
                hide();
            }
        }

        // Wire close button
        document.getElementById('reload-overlay-close')
            .addEventListener('click', hide);

        // Listen for the Reload button click. Shiny may swap the DOM, so
        // use event delegation on the document.
        document.addEventListener('click', function(ev) {
            var target = ev.target;
            while (target && target !== document) {
                if (target.id === 'reload_source_btn' ||
                    (target.parentElement && target.parentElement.id === 'reload_source_btn')) {
                    show();
                    return;
                }
                target = target.parentElement;
            }
        }, true);
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
"""


def _help(text):
    """Tooltip 'help' icon (?) with a native browser tooltip."""
    from shiny import ui as _ui
    return _ui.tags.span("?", class_="help-icon", title=text)


def _no_data(msg="No data available for the current selection."):
    """Visible grey placeholder instead of a silently blank chart."""
    from shiny import ui as _ui
    return _ui.HTML(f'<div style="color:#64748B;padding:16px;">{msg}</div>')


def _settle_col(df):
    """Cost column for margin math — the RMB-converted settlement when the
    enrichment has run, raw settlement_price as a fallback."""
    return 'settlement_rmb' if 'settlement_rmb' in df.columns else 'settlement_price'


def safe_render(fn):
    """Wrap a @render.ui body so exceptions surface as a visible error box
    instead of being silently swallowed by Shiny (which leaves the chart
    blank with no clue why)."""
    import functools

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            try:
                from shiny.types import SilentException, SilentCancelOutputException
                if isinstance(exc, (SilentException, SilentCancelOutputException)):
                    raise
            except ImportError:
                pass
            print(f"[render-error] {fn.__name__}: {type(exc).__name__}: {exc}", flush=True)
            from shiny import ui as _ui
            return _ui.HTML(
                '<div style="color:#B91C1C;background:#FEF2F2;border:1px solid #FECACA;'
                'padding:14px;border-radius:8px;font-size:0.9em;">'
                f'⚠ <b>Chart error</b> ({fn.__name__}): {type(exc).__name__}: {exc}</div>'
            )
    return _wrapped


def safe_grid(fn):
    """Like safe_render but for @render.data_frame — returns a one-row
    error table instead of a blank grid."""
    import functools

    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            try:
                from shiny.types import SilentException, SilentCancelOutputException
                if isinstance(exc, (SilentException, SilentCancelOutputException)):
                    raise
            except ImportError:
                pass
            print(f"[render-error] {fn.__name__}: {type(exc).__name__}: {exc}", flush=True)
            return pd.DataFrame({'Error': [f"{fn.__name__}: {type(exc).__name__}: {exc}"]})
    return _wrapped


DASHBOARD_COLUMNS = [
    "country", "order_id", "sales", "user_id", "segment",
    "order_time", "operator", "product", "product_category",
    "product_info", "settlement_price", "register_time", "ip_country",
    "denomination",
    "order_status", "agent_name", "user_source", "ip_address", "coupon_used",
    "sku_name", "brand", "coupon_name", "coupon_amount", "new_user_promo",
    "badge_product", "area_code", "recharge_number", "interface_order_id",
    "sales_listed",
    "pin_code", "useepay_order_id",
    # Old parquet caches still have the original Chinese names — read them
    # too so the rename below picks them up without forcing a cache rebuild.
    "面额", "商品信息", "sku名称", "品牌商", "优惠券名称", "优惠券金额",
    "是否新人优惠", "是否角标产品", "区号", "充值号码", "接口商订单号",
    "pin码", "useepay订单号",
]
CATEGORY_COLUMNS = ["country", "segment", "operator", "product", "product_category",
                    "ip_country", "region", "order_status", "user_source", "brand",
                    "coupon_used", "new_user_promo", "badge_product", "coupon_name"]

# Order status groups (订单状态). Raw values observed in the data:
#   B2B: 充值成功 / 已退款 / 等待处理
#   B2C: 充值成功 / 已退款 / 已取消 / 等待支付 / 待付款 / 等待处理 / 充值中
ORDER_STATUS_GROUPS = {
    "Successful": {"充值成功"},
    "Refunded":   {"已退款"},
    "Cancelled":  {"已取消"},
    "Pending":    {"等待支付", "待付款", "等待处理", "充值中"},
}
ORDER_STATUS_CHOICES = {
    "Successful":     "✅ Successful (充值成功)",
    "All":            "🔁 All statuses (全部)",
    "Non-successful": "⚠ Non-successful (非成功)",
    "Refunded":       "↩ Refunded (已退款)",
    "Cancelled":      "✖ Cancelled (已取消)",
    "Pending":        "⏳ Pending (待处理/待支付)",
}


def filter_by_order_status(df, selection):
    """Apply the order-status filter. Gracefully no-op when the column
    is missing (old parquet cache) or when 'All' is selected."""
    if df is None or selection in (None, "", "All") or 'order_status' not in df.columns:
        return df
    s = df['order_status'].astype(str).str.strip()
    if selection == "Non-successful":
        return df[~s.isin(ORDER_STATUS_GROUPS["Successful"])]
    values = ORDER_STATUS_GROUPS.get(selection)
    if not values:
        return df
    return df[s.isin(values)]


def _rename_legacy_columns(df):
    """Translate any leftover Chinese column names from older parquet caches."""
    legacy = {
        "面额": "denomination", "商品信息": "product_info",
        "sku名称": "sku_name", "品牌商": "brand",
        "优惠券名称": "coupon_name", "优惠券金额": "coupon_amount",
        "是否新人优惠": "new_user_promo", "是否角标产品": "badge_product",
        "区号": "area_code", "充值号码": "recharge_number",
        "接口商订单号": "interface_order_id",
        "pin码": "pin_code", "useepay订单号": "useepay_order_id",
    }
    to_rename = {k: v for k, v in legacy.items() if k in df.columns and v not in df.columns}
    if to_rename:
        df = df.rename(columns=to_rename)
    # If both old and new names happened to be present, drop the old one
    for k in legacy:
        if k in df.columns and legacy[k] in df.columns:
            df = df.drop(columns=[k])
    return df


def _optimise_dtypes(df):
    """Down-cast low-cardinality string cols to 'category' for speed/memory."""
    for col in CATEGORY_COLUMNS:
        if col in df.columns and df[col].dtype != "category":
            df[col] = df[col].astype("category")
    return df


_APP_LIKE = _re.compile(r'[（\(](小程序|微信|App|APP|WeChat|applet)', _re.UNICODE | _re.IGNORECASE)

def _scrub_country_column(df):
    """Normalise the country column:
    1. Remove stray timestamps, blanks, 'nan' strings.
    2. Filter app/product names (e.g. 'easy大马生活(小程序)').
    3. Translate Chinese country names → English via translate_country().
    """
    if 'country' not in df.columns:
        return df
    df = df.copy()
    s = df['country'].astype(str).str.strip()
    bad = (s.str.match(_DATE_LIKE)
           | (s == "")
           | s.str.lower().isin({"nan", "none", "nat"})
           | s.str.contains(_APP_LIKE, regex=True, na=False))
    n_bad = int(bad.sum())
    if n_bad:
        print(f"[load_data] scrubbing {n_bad:,} non-country rows in 'country'", flush=True)
        df.loc[bad, 'country'] = None
    # Translate Chinese country names → English
    df['country'] = df['country'].astype(str).map(translate_country)
    df.loc[df['country'].isin({"nan", "None"}), 'country'] = None
    return df


def _add_region_column(df):
    """Derive a 'region' column from country (Asia / Middle East / Africa / etc)."""
    if 'country' not in df.columns:
        return df
    df = df.copy()
    df['region'] = df['country'].astype(str).map(T.to_region).astype('category')
    return df


_BRAND_SUFFIX = _re.compile(r"(话费|流量|充值卡|缴费|数据|data|topup|top-up)\s*$", _re.IGNORECASE)
_YESNO_OK = {"是", "否"}

# ── Settlement currency rules ────────────────────────────────────────────────
# settlement_price (结算价) arrives in MIXED currencies depending on the
# supplier contract. sales (售价/实际支付) is ALWAYS RMB. Margin math must
# therefore convert settlement to RMB first (settlement_rmb).
#
#   - Local-currency countries: settlement is in that market's currency.
#   - Saudi Arabia exception: products containing 'Quicknet' settle in USD.
#   - Mexico & Sri Lanka: mixed per product / per supplier-migration date —
#     decided per row by scale: settlement ≥ 50% of the denomination face
#     value means it IS the face value → local currency; otherwise USD.
#   - Everything else: USD.
SETTLEMENT_LOCAL_COUNTRIES = {
    "Malaysia": "MYR", "Indonesia": "IDR", "Kyrgyzstan": "KGS",
    "Saudi Arabia": "SAR", "Myanmar": "MMK", "Vietnam": "VND",
}
# UAE added from data evidence: settlement scale matches AED face values
# (USD assumption produced −180% margins). The audit table flags it for review.
SETTLEMENT_HEURISTIC_COUNTRIES = {"Mexico": "MXN", "Sri Lanka": "LKR",
                                  "United Arab Emirates": "AED"}

# RMB→local rates reused from fx_rates so there is one rate table to maintain.
_SETTLE_RATES = {iso: rate for (_s, iso, rate) in fx_rates.COUNTRY_CURRENCY.values()}
_USD_PER_RMB = _SETTLE_RATES.get("USD", 0.14)


def _apply_settlement_currency(df):
    """Add settlement_currency + settlement_rmb columns (vectorised)."""
    if 'settlement_price' not in df.columns or 'country' not in df.columns:
        return df
    settle = pd.to_numeric(df['settlement_price'], errors='coerce')
    country = df['country'].astype(str).str.strip()
    cur = pd.Series("USD", index=df.index, dtype="object")

    for cty, iso in SETTLEMENT_LOCAL_COUNTRIES.items():
        cur = cur.mask(country == cty, iso)

    # Saudi exception: Quicknet products settle in USD
    if 'product' in df.columns or 'product_info' in df.columns:
        prod = pd.Series("", index=df.index, dtype="object")
        if 'product' in df.columns:
            prod = df['product'].astype('string').fillna("")
        if 'product_info' in df.columns:
            prod = prod.where(prod != "", df['product_info'].astype('string').fillna(""))
        quicknet = prod.str.contains("quicknet", case=False, na=False)
        cur = cur.mask((country == "Saudi Arabia") & quicknet, "USD")

    # Mexico / Sri Lanka: per-row scale heuristic vs denomination face value
    if 'denomination' in df.columns:
        denom = pd.to_numeric(df['denomination'], errors='coerce')
        for cty, iso in SETTLEMENT_HEURISTIC_COUNTRIES.items():
            in_cty = country == cty
            looks_local = in_cty & denom.notna() & settle.notna() & (settle >= 0.5 * denom)
            cur = cur.mask(in_cty, "USD")          # default for the country
            cur = cur.mask(looks_local, iso)       # face-value scale → local

    rate = cur.map(_SETTLE_RATES).fillna(_USD_PER_RMB).astype(float)
    df['settlement_currency'] = cur
    df['settlement_rmb'] = settle / rate
    return df


def _enrich_columns(df):
    """Cross-segment enrichment using the newly-loaded columns.

    1. B2C rows have no 运营商 — fill `operator` from `brand` (品牌商), which
       holds clean operator names (Telkomsel, Maxis, Digi...). Fall back to
       the product name with marketing suffixes stripped ('Digi话费' → 'Digi').
    2. Normalise the 是/否 flag columns — the raw exports contain occasional
       stray values (e.g. a country name) that would pollute groupbys.
    """
    df = df.copy()
    if 'operator' in df.columns:
        op = df['operator'].astype('string')
        need = op.isna() | (op.str.strip() == "")
        if 'brand' in df.columns:
            b = df['brand'].astype('string').str.strip()
            fill = b.where(b.notna() & (b != ""), None)
            op = op.mask(need & fill.notna(), fill)
            need = op.isna() | (op.str.strip() == "")
        if 'product' in df.columns and need.any():
            p = (df['product'].astype('string').str.strip()
                   .str.replace(_BRAND_SUFFIX, '', regex=True).str.strip())
            p = p.where(p.notna() & (p != ""), df['product'].astype('string'))
            op = op.mask(need & p.notna(), p)
        df['operator'] = op
    for col in ('coupon_used', 'new_user_promo', 'badge_product'):
        if col in df.columns:
            s = df[col].astype('string').str.strip()
            df[col] = s.where(s.isin(_YESNO_OK), pd.NA)
    df = _apply_settlement_currency(df)
    return df


def load_data():
    """Load combined sales data for the dashboard.

    Reads from the local database (./database/sales_cache.parquet, regenerated
    from Agent_Database.xlsx + Master_Database.xlsx as needed). If the
    database hasn't been initialised yet, falls back to reading the source
    Recon Excel files directly. Only the columns the dashboard actually uses
    are loaded; low-cardinality strings are cast to 'category' dtype.
    """
    def log(msg):
        print(f"[load_data] {msg}", flush=True)

    try:
        log("Loading from local database ...")
        df = db_utils.read_database(columns=DASHBOARD_COLUMNS)
        df = _rename_legacy_columns(df)
        df = _scrub_country_column(df)
        df = _add_region_column(df)
        df = _enrich_columns(df)
        return _optimise_dtypes(df)
    except FileNotFoundError as exc:
        log(f"Database not initialised: {exc}")
        log("Falling back to source Recon Excel files ...")

    # Fallback: read original source files directly (slow, used only on first
    # run before init_database.py / Import Data tab has been used).
    import time

    def read_excel_file(path):
        try:
            return pd.read_excel(path, sheet_name='Whole')
        except ValueError:
            xls = pd.ExcelFile(path)
            return pd.read_excel(xls, sheet_name=xls.sheet_names[0])

    t0 = time.time()
    log("Reading Agent Data.xlsx ...")
    agent_data = read_excel_file(
        r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\Agent Data.xlsx"
    )
    log(f"  Agent loaded: {len(agent_data):,} rows in {time.time()-t0:.1f}s")
    t1 = time.time()
    log("Reading Master Data.xlsx ...")
    master_data = read_excel_file(
        r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\Master Data.xlsx"
    )
    log(f"  Master loaded: {len(master_data):,} rows in {time.time()-t1:.1f}s")
    agent_data['segment'] = 'B2B'
    master_data['segment'] = 'B2C'
    combined = pd.concat([agent_data, master_data], ignore_index=True)
    combined = db_utils._normalize_columns(combined)
    combined = combined.drop_duplicates()
    keep = [c for c in DASHBOARD_COLUMNS if c in combined.columns]
    combined = combined[keep]
    combined = _scrub_country_column(combined)
    combined = _add_region_column(combined)
    combined = _enrich_columns(combined)
    return _optimise_dtypes(combined)


try:
    data = load_data()
except FileNotFoundError as exc:
    raise SystemExit(str(exc))

segment_choices = ["All"] + sorted(data['segment'].dropna().astype(str).unique().tolist())
_raw_country_choices = _clean_country_choices(data['country'])

# Country pseudo-filters (China-team 全球共用标准): 汇总 = all countries except
# Malaysia; 全球 = countries NOT in 重点国家, also excluding Malaysia.
_MALAYSIA = "Malaysia"
_SUMMARY_LABEL = "📊 汇总 (Summary · 剔除大马)"
_GLOBAL_LABEL  = "🌐 全球 (Global · 剔除大马)"
_KEY_COUNTRIES_LABEL = "🔑 重点国家 (Key Countries)"
country_choices = ["All", _SUMMARY_LABEL, _KEY_COUNTRIES_LABEL, _GLOBAL_LABEL] + _raw_country_choices

_KEY_COUNTRIES_FILE = Path(__file__).parent / "database" / "key_countries.json"
_KEY_COUNTRIES_DEFAULT = [
    "Malaysia", "Indonesia", "Saudi Arabia", "Mexico",
    "UAE", "Sri Lanka", "Iraq", "Kyrgyzstan",
]

def _load_key_countries() -> list:
    if _KEY_COUNTRIES_FILE.exists():
        try:
            return json.load(open(_KEY_COUNTRIES_FILE, encoding="utf-8"))
        except Exception:
            pass
    return list(_KEY_COUNTRIES_DEFAULT)

def _save_key_countries(lst: list) -> None:
    _KEY_COUNTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(_KEY_COUNTRIES_FILE, "w", encoding="utf-8") as f:
        json.dump(lst, f, ensure_ascii=False, indent=2)


def _filter_by_country(df, country):
    """Apply the country selector incl. the China-team pseudo-options.

    All/'' → no filter · 汇总 → all except Malaysia · 全球 → non-key countries
    except Malaysia · 重点国家 → the key-country list · else → that single country.
    """
    if df is None or 'country' not in df.columns:
        return df
    if not country or country in ("All", ""):
        return df
    c = df['country'].astype(str)
    if country == _SUMMARY_LABEL:
        return df[c != _MALAYSIA]
    if country == _GLOBAL_LABEL:
        kc = set(_load_key_countries())
        return df[(~c.isin(kc)) & (c != _MALAYSIA)]
    if country == _KEY_COUNTRIES_LABEL:
        kc = _load_key_countries()
        return df[c.isin(kc)] if kc else df
    return df[c == country]


# ── Global exclusions (China-team 全球共用标准): core metrics drop 电子钱包 + TNG ──
_EXCLUDE_EWALLET_TNG = True   # set False to include 电子钱包 / Touch'n Go dashboard-wide


def _apply_global_exclusions(df):
    """Drop 电子钱包 (e-wallet) and Touch'n Go (TNG) rows from core-metric frames."""
    if not _EXCLUDE_EWALLET_TNG or df is None or 'product_category' not in df.columns:
        return df
    cat = df['product_category'].astype(str)
    keep = ~(cat.str.contains('电子钱包', na=False)
             | cat.str.contains('e-?wallet', case=False, na=False, regex=True)
             | cat.str.contains('Touch', case=False, na=False))
    return df[keep]


def _reg_new_user_set(d):
    """Standard 新客 set: B2C users whose 注册月 == 订单月 within d. {} if unavailable."""
    if d is None or len(d) == 0 or not {'register_time', 'order_time', 'user_id'}.issubset(d.columns):
        return set()
    dd = d.dropna(subset=['register_time', 'order_time', 'user_id'])
    if dd.empty:
        return set()
    regm = pd.to_datetime(dd['register_time'], errors='coerce').dt.to_period('M')
    ordm = pd.to_datetime(dd['order_time'], errors='coerce').dt.to_period('M')
    return set(dd.loc[regm == ordm, 'user_id'].astype(str).unique())


_targets_cache = None


def _load_targets():
    """3.2 Targets / budget. Optional database/targets.csv
    (columns: month [YYYY-MM], metric, target[RMB]). {} if absent.
    metric 'revenue'/'gmv' drives the dashed plan line on the revenue trend."""
    global _targets_cache
    if _targets_cache is not None:
        return _targets_cache
    import csv
    from pathlib import Path
    out = {}
    path = Path(__file__).parent / "database" / "targets.csv"
    if path.exists():
        try:
            with open(path, encoding="utf-8-sig", newline="") as f:
                for row in csv.DictReader(f):
                    metric = (row.get("metric") or "revenue").strip().lower()
                    mon = (row.get("month") or "").strip()
                    try:
                        tgt = float(row.get("target"))
                    except (TypeError, ValueError):
                        continue
                    if mon:
                        out[(metric, mon)] = tgt
        except Exception:
            out = {}
    _targets_cache = out
    return _targets_cache


# ── 用户列表 (Users registration table) — exact 新客数 / 转化率 ─────────────────
# Per 全球共用计算取数公式及标准, 新客数 & 转化率 come from the Users table, not the
# order table. We look for 用户列表*.csv in database/ first, then the Report folder.
_USER_LIST_GLOBS = [
    str(Path(__file__).parent / "database" / "用户列表*.csv"),
    r"C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\用户列表*.csv",
]
_user_list_cache = None


def _load_user_list():
    """Load + cache the 用户列表 → frame [uid, reg_time, wechat, country_en].
    Empty frame when no file is found. 渠道(微信/支付宝) from 会员来源."""
    global _user_list_cache
    if _user_list_cache is not None:
        return _user_list_cache
    import glob
    path = None
    for pattern in _USER_LIST_GLOBS:
        hits = sorted(glob.glob(pattern))
        if hits:
            path = hits[-1]          # latest by filename (timestamped)
            break
    cols = ['uid', 'reg_time', 'wechat', 'country_en']
    if not path:
        _user_list_cache = pd.DataFrame(columns=cols)
        return _user_list_cache
    u = None
    for enc in ('utf-8-sig', 'gb18030', 'utf-8'):
        try:
            u = pd.read_csv(path, encoding=enc, dtype=str)
            break
        except Exception:
            continue
    if u is None or 'ID' not in u.columns:
        _user_list_cache = pd.DataFrame(columns=cols)
        return _user_list_cache
    out = pd.DataFrame()
    out['uid'] = u['ID'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
    out['reg_time'] = pd.to_datetime(u.get('注册时间'), errors='coerce')
    src = u.get('会员来源', pd.Series('', index=u.index)).astype(str)
    out['channel'] = src.str.strip()                 # normalized 会员来源 (the source map)
    out['wechat'] = ~src.str.contains('支付宝', na=False)
    cn = u.get('来源国家', pd.Series(pd.NA, index=u.index)).astype('string').str.strip()
    country_en = cn.map(CN_TO_EN).fillna(cn)
    country_en = country_en.mask(cn.isna() | (cn == ''), pd.NA)
    out['country_en'] = country_en
    out = out[(out['uid'].notna()) & (out['uid'] != '') & (out['uid'] != 'nan')]
    out = out[out['reg_time'].notna() & (out['reg_time'].dt.year > 1970)]
    _user_list_cache = out.reset_index(drop=True)
    print(f"[user_list] loaded {len(_user_list_cache):,} users from {path}", flush=True)
    return _user_list_cache


def _new_customer_ids(date_from, date_to, country):
    """IDs registered within [date_from, date_to], scoped by the country selector
    and channel rules (汇总 = WeChat only; WeChat needs non-empty country; Alipay
    allowed). Returns (ids:set, available:bool)."""
    ul = _load_user_list()
    if ul is None or ul.empty:
        return set(), False
    d = ul
    if date_from and date_to:
        start = pd.to_datetime(date_from, errors='coerce')
        end = pd.to_datetime(date_to, errors='coerce')
        if pd.notna(start) and pd.notna(end):
            if start > end:
                start, end = end, start
            d = d[(d['reg_time'] >= start) & (d['reg_time'] < end + pd.Timedelta(days=1))]
    c = d['country_en'].astype('string')
    wechat = d['wechat'].fillna(True)
    if country == _SUMMARY_LABEL:
        mask = wechat & c.notna() & (c != _MALAYSIA)            # 汇总 = 仅微信端, 剔除大马
    elif country == _GLOBAL_LABEL:
        kc = set(_load_key_countries())
        mask = c.notna() & (~c.isin(kc)) & (c != _MALAYSIA)
    elif country == _KEY_COUNTRIES_LABEL:
        kc = set(_load_key_countries())
        mask = c.notna() & c.isin(kc)
    elif country and country not in ("All", ""):
        mask = (c == country)
    else:                                                       # All
        mask = (wechat & c.notna()) | (~wechat)
    mask = mask & ~(wechat & c.isna())                          # 微信端剔除国家为空
    return set(d.loc[mask, 'uid'].unique()), True


_channel_map_cache = None


def _channel_map():
    """uid → 会员来源 (normalized channel) from the 用户列表 — the 'dim_source_map'."""
    global _channel_map_cache
    if _channel_map_cache is not None:
        return _channel_map_cache
    ul = _load_user_list()
    if ul is None or ul.empty or 'channel' not in ul.columns:
        _channel_map_cache = {}
    else:
        cc = ul[ul['channel'].notna() & (ul['channel'] != '')]
        _channel_map_cache = dict(zip(cc['uid'], cc['channel']))
    return _channel_map_cache


def _with_channel(d):
    """Attach a normalized 'channel' (会员来源) column by joining order user_id to
    the 用户列表. No-op if the userlist is unavailable."""
    if d is None or len(d) == 0 or 'user_id' not in d.columns:
        return d
    m = _channel_map()
    if not m:
        return d
    d = d.copy()
    d['channel'] = d['user_id'].astype(str).str.replace(r'\.0$', '', regex=True).map(m)
    return d
# Only list regions that actually appear in the data, in the canonical order.
_present_regions = set(data['region'].dropna().astype(str).unique().tolist()) if 'region' in data.columns else set()
region_choices = ["All"] + [r for r in T.REGION_ORDER if r in _present_regions]
currency_choices = ["USD", "RMB", "Local Currency"]
exchange_rate = 6.83  # 1 USD = 6.83 RMB, adjust if needed

if 'order_time' in data.columns and not data['order_time'].isna().all():
    min_date = data['order_time'].min().date()
    max_date = data['order_time'].max().date()
    month_choices = ["—"] + sorted(
        data['order_time'].dropna().dt.to_period('M').astype(str).unique().tolist()
    )
    from datetime import timedelta as _td
    compare_a_default_start = max(min_date, max_date - _td(days=13))
    compare_a_default_end   = max_date
    compare_b_default_start = max(min_date, max_date - _td(days=27))
    compare_b_default_end   = max(min_date, max_date - _td(days=14))
else:
    min_date = None
    max_date = None
    month_choices = ["—"]
    compare_a_default_start = compare_a_default_end = None
    compare_b_default_start = compare_b_default_end = None

def _bh3(en_text: str, zh_text: str, help_widget=None, **kwargs):
    """Bilingual h3 heading — CSS switches on body[data-lang]."""
    inner = [
        ui.tags.span(en_text, class_="lang-en"),
        ui.tags.span(zh_text, class_="lang-zh"),
    ]
    if help_widget:
        inner.append(help_widget)
    return ui.h3(*inner, **kwargs)


def _bp(en_text: str, zh_text: str):
    """Bilingual description paragraph below a chart heading."""
    return ui.p(
        ui.tags.span(en_text, class_="lang-en"),
        ui.tags.span(zh_text, class_="lang-zh"),
        style="color:#64748B; font-size:0.88em; margin-top:-8px;"
    )


def _bnav(en_text: str, zh_text: str):
    """Bilingual nav-tab label (CSS switches on body[data-lang])."""
    return ui.span(
        ui.tags.span(en_text, class_="lang-en"),
        ui.tags.span(zh_text, class_="lang-zh"),
    )


def _bl(en: str, zh: str):
    """Bilingual inline label usable in module-level UI (CSS body[data-lang]).
    The server defines a local `_bl` with identical behaviour for use inside
    render functions; this module-level one serves the static UI."""
    return ui.HTML(f'<span class="lang-en">{en}</span><span class="lang-zh">{zh}</span>')


# ── Guideline tab content ─────────────────────────────────────────────────────
# Static catalogue of every visualization grouped by tab, a bitsbang↔dashboard
# terminology quick-reference, and the proposed-removals list. No reactivity.

_GTYPE_ZH = {
    "KPI strip": "KPI卡组", "KPI alerts": "预警卡", "KPI cards": "KPI卡", "Delta cards": "差异卡",
    "Bar + line": "柱+线", "Donut": "环形图", "Bar (H)": "横向柱", "Grouped bars": "分组柱",
    "Table": "表格", "Controls": "控件", "Dual line": "双线", "3 tables": "3个表",
    "Bars": "柱状图", "Stacked bar": "堆叠柱", "Line": "折线", "Choropleth map": "地图",
    "Bubble scatter": "气泡散点", "Quadrant scatter": "象限散点", "Heatmap": "热力图",
    "Table (Excel)": "表格(Excel)", "Bars (H)": "横向柱", "Colored bars": "涨跌柱",
    "KPI flag": "指标标记", "Bar & lines": "柱+多线", "Bar + cum. line": "柱+累计线",
    "Bar": "柱状图", "KPI + bar": "KPI+柱", "Treemap": "树图", "KPI + bar/line": "KPI+柱/线",
    "Bars & lines": "柱与线", "Bars & matrix": "柱与矩阵", "Heatmaps": "热力图",
    "Tables (Excel)": "表格(Excel)", "Stacked bars + pivot": "堆叠柱+透视",
    "KPI, bar, table": "KPI/柱/表", "Funnel": "漏斗", "Badge + bar": "标记+柱",
    "Donut / bar": "环形/柱", "Grouped bar": "分组柱", "Table (Excel/CSV)": "表格(Excel/CSV)",
    "Line + band": "线+区间", "Feature bar + table": "特征柱+表", "Reference": "参考",
}

# Rows: (title_en, title_zh, type, use_en, use_zh)
_GUIDELINE_TABS = [
    ("📊", "Executive Overview", "执行概览", [
        ("🧭 Operating Summary", "🧭 运营概览", "KPI strip", "11 China-team KPIs (营业额…转化率) on the 充值成功 basis with MoM.", "11项中国团队核心指标（营业额…转化率），充值成功口径，含环比。"),
        ("🚨 Anomaly Detection & Alerts", "🚨 异常检测与预警", "KPI alerts", "Auto-flags slipping/surging operators & markets (7d vs 4-wk).", "自动标记异常的运营商与市场（近7天 vs 前4周）。"),
        ("📊 Key Performance Indicators", "📊 核心绩效指标", "KPI cards", "GMV/orders/客单价/customers/markets/MoM/margin.", "营业额/订单/客单价/客户/市场/环比/毛利。"),
        ("⚡ PoP Top Movers", "⚡ 环比变动榜", "Delta cards", "Biggest revenue movers vs the prior equal period.", "与上期相比变动最大的市场与运营商。"),
        ("📈 Revenue & Order Volume Trend", "📈 收入与订单量趋势", "Bar + line", "GMV bars vs orders line — momentum.", "营业额柱 vs 订单线 — 走势。"),
        ("🥧 Revenue by Customer Segment", "🥧 各客户分类收入", "Donut", "B2B vs B2C share of GMV.", "B2B 与 B2C 营业额占比。"),
        ("🌐 Revenue Contribution by Region", "🌐 各地区收入贡献", "Donut", "Regional concentration / diversification.", "区域集中度 / 多元化。"),
        ("🏆 Top 5 Markets by Revenue", "🏆 收入前5市场", "Bar (H)", "Highest-value countries at a glance.", "价值最高的国家速览。"),
        ("🌏 Key Countries — Last 3 Months", "🌏 重点国家近3个月", "Grouped bars", "Last-3-month GMV per key country (充值成功).", "各重点国家近3个月营业额（充值成功）。"),
        ("📋 Segment Performance Summary", "📋 分部业绩汇总", "Table", "GMV/orders/客单价/MoM/margin per segment.", "各分部 营业额/订单/客单价/环比/毛利。"),
    ]),
    ("🆚", "Performance Comparison", "业绩对比", [
        ("🆚 Period A vs B picker", "🆚 时段A vs B 选择", "Controls", "Choose any two windows; swap A/B.", "选择任意两个时段；A/B 互换。"),
        ("📊 KPI Variance A vs B", "📊 A vs B 指标差异", "Delta cards", "Revenue/orders/customers/客单价 side-by-side.", "营业额/订单/客户/客单价 并排对比。"),
        ("📈 Revenue Trend Overlay", "📈 收入趋势叠加", "Dual line", "Both periods aligned to day-1.", "两个时段按首日对齐对比。"),
        ("🏃 Top Movers (Market/Operator/Denomination)", "🏃 变动榜（市场/运营商/面值）", "3 tables", "Largest absolute revenue deltas.", "绝对营业额变化最大项。"),
    ]),
    ("💰", "Revenue & Orders", "收入与订单", [
        ("💰 Revenue & Orders KPIs", "💰 收入与订单核心指标", "KPI cards", "营业额/orders/客单价/customers/margin/success.", "营业额/订单/客单价/客户/毛利/成单率。"),
        ("💎 Revenue / Orders / 客单价 by Segment", "💎 各分部 收入/订单/客单价", "Bars", "B2B vs B2C on each money metric.", "B2B vs B2C 各金额指标。"),
        ("📋 Revenue & Orders by Market", "📋 各市场收入与订单", "Table", "Per-country B2B/B2C revenue/orders/客单价/margin.", "各国 B2B/B2C 营业额/订单/客单价/毛利。"),
        ("🚦 Order Status KPIs", "🚦 订单状态指标", "KPI cards", "Success / refund / cancellation rates.", "成单率 / 退款率 / 取消率。"),
        ("📊 Order Count by Status × Segment", "📊 各状态×分部订单量", "Stacked bar", "Where refunds/cancellations concentrate.", "退款/取消集中在哪。"),
        ("📉 Monthly Refund Rate Trend", "📉 月度退款率趋势", "Line", "Refund-rate trajectory by segment.", "各分部退款率走势。"),
        ("⚠ Refund Rate by Operator (Top 10)", "⚠ 各运营商退款率（前10）", "Bar (H)", "Operators with worst refund rates (≥200).", "退款率最高的运营商（≥200单）。"),
    ]),
    ("🌍", "Market Intelligence", "市场洞察", [
        ("🗺️ Global Revenue Distribution", "🗺️ 全球收入分布", "Choropleth map", "Revenue intensity by country worldwide.", "全球各国营业额强度。"),
        ("🚀 Risers vs 📉 Decliners", "🚀 增长 vs 📉 下滑", "Table", "Fastest-growing/declining markets.", "增长/下滑最快的市场。"),
        ("🌍 Top Markets by Revenue/Orders/客单价", "🌍 市场排名 收入/订单/客单价", "Bars (H)", "Market rankings on each dimension.", "各维度市场排名。"),
        ("💎 Market Opportunity Matrix", "💎 市场机会矩阵", "Bubble scatter", "Volume × 客单价 × GMV — where to invest.", "订单量 × 客单价 × 营业额 — 投资方向。"),
        ("🧭 Market Expansion Radar", "🧭 市场拓展雷达", "Quadrant scatter", "Core/Upsell/Growth/Long-tail.", "核心/增购/增长/长尾 分类。"),
        ("📅 Monthly Revenue Heatmap (Top 15)", "📅 月度收入热力图（前15）", "Heatmap", "Seasonality & momentum per market.", "各市场季节性与势头。"),
        ("📊 Orders by Market × Segment", "📊 各市场×分部订单", "Stacked bar", "B2B/B2C mix per top market.", "各市场 B2B/B2C 结构。"),
        ("📋 Market KPI Scorecard", "📋 市场指标评分卡", "Table (Excel)", "Full per-market KPI export.", "各市场完整指标导出。"),
        ("💲 Recharge Destinations / Beneficiary Reach", "💲 充值目的地 / 受益号触达", "Bars", "Cross-border recharge & reseller signals.", "跨境充值与分销信号。"),
    ]),
    ("⚙️", "Operational Intelligence", "运营智能", [
        ("📊 Operational KPIs", "📊 运营核心指标", "KPI cards", "Avg daily revenue/orders, peak day/hour.", "日均收入/订单、高峰日/时段。"),
        ("📈 Revenue Velocity", "📈 收入速度", "Bar + line", "Daily orders vs revenue.", "每日订单 vs 收入。"),
        ("📉 Day-over-Day Revenue Change", "📉 日环比收入变化", "Colored bars", "Daily % swings (green up/red down).", "每日涨跌幅（绿涨红跌）。"),
        ("📅 Activity Heatmap (Weekday × Hour)", "📅 活跃度热力图（星期×小时）", "Heatmap", "When orders happen — staffing/promo timing.", "下单时段 — 排班/促销时机。"),
    ]),
    ("🤝", "Supplier & Operator Performance", "供应商绩效", [
        ("🤝 Operator Snapshot", "🤝 运营商快照", "KPI cards", "GMV/orders/客单价/margin/Top-3 conc.", "营业额/订单/客单价/毛利/前3集中度。"),
        ("⚠️ Supplier Concentration Risk", "⚠️ 供应商集中度风险", "KPI flag", "Top-3 operator share (🔴 if >80%).", "前3运营商占比（>80% 标红）。"),
        ("💰 Gross Margin by Operator / 📈 Margin % Trend", "💰 各运营商毛利 / 📈 毛利率趋势", "Bar & lines", "Absolute & rate margin per operator.", "各运营商毛利额与毛利率。"),
        ("🥧 Revenue Pareto", "🥧 收入帕累托", "Bar + cum. line", "How few operators drive most revenue.", "少数运营商贡献大部分收入。"),
        ("🚀 Top Operators by Revenue / Orders", "🚀 运营商排名 收入/订单", "Bars", "Operator rankings & momentum.", "运营商排名与势头。"),
        ("📋 Operator Scorecard", "📋 运营商评分卡", "Table (Excel)", "Full per-operator KPIs.", "各运营商完整指标。"),
        ("💹 Gross Margin by Product Category", "💹 各产品类别毛利", "Bar", "Which categories are most profitable.", "哪些类别最赚钱。"),
        ("🩺 Fulfillment / ⚠ Missing Supplier Order ID", "🩺 履约 / ⚠ 缺接口商订单号", "KPI + bar", "Routing coverage & reconciliation risk.", "路由覆盖率与对账风险。"),
        ("💱 Settlement Currency Audit", "💱 结算币种审计", "Table (Excel)", "Per-market settlement currency & margin.", "各市场结算币种与毛利核查。"),
        ("🇮🇶 Iraq Pinstore Purchase Planner", "🇮🇶 伊拉克 Pinstore 采购计划", "KPI + heatmap + table", "Weekly PIN demand & stock-purchase estimation (Pinstore supplier).", "每周PIN需求与备货采购估算（Pinstore 供应商）。"),
    ]),
    ("🏷️", "Product & Denomination Analysis", "产品与面值", [
        ("🏷️ Category + 🏢 Operator filters", "🏷️ 类别 + 🏢 运营商筛选", "Controls", "Scope the tab by category & operator (all or pick).", "按类别与运营商筛选本页（全部或指定）。"),
        ("🗂️ Category KPIs / Revenue & Orders / Trend", "🗂️ 类别指标 / 收入订单 / 趋势", "KPI + bar/line", "Which line drives revenue vs traffic.", "哪条产品线带收入/带流量。"),
        ("🌳 Product Revenue Mix", "🌳 产品收入结构", "Treemap", "Portfolio concentration by product.", "产品组合集中度。"),
        ("📦 Top Products / by Segment / Top-5 trend", "📦 产品排名 / 分部 / 前5趋势", "Bars & lines", "Best sellers & their trajectories.", "畅销品及其走势。"),
        ("💵 Denomination Band Contribution", "💵 面值档位贡献", "Bar", "Low/Mid/High face-value share of GMV.", "低/中/高面值的营业额占比。"),
        ("📶 Data Package by Volume / Tier / Operator×Size", "📶 流量套餐 规格/档位/运营商×规格", "Bars & matrix", "买流量: which data sizes sell, per operator.", "买流量：各规格销量，按运营商。"),
        ("💵 Airtime by Denomination / × Operator", "💵 话费 各面值 / ×运营商", "Bars", "充话费: which top-up values sell.", "充话费：各面值销量。"),
        ("⏰ Peak Hours / Denomination × Operator", "⏰ 高峰时段 / 面值×运营商", "Heatmaps", "When & what denominations are bought.", "何时购买、买什么面值。"),
        ("📋 Denomination & Product scorecards", "📋 面值与产品评分卡", "Tables (Excel)", "Full denomination/product KPIs.", "面值/产品完整指标。"),
        ("📊 Operator × Category mix", "📊 运营商×类别结构", "Stacked bars + pivot", "Each operator's product spread.", "各运营商的产品分布。"),
    ]),
    ("👥", "Customer Analytics", "客户分析", [
        ("🏢 B2B Agent Snapshot / Top 20 / Table", "🏢 B2B代理快照 / 前20 / 表", "KPI, bar, table", "Agent revenue concentration & ranking.", "代理商收入集中度与排名。"),
        ("👥 Customer KPIs (B2C)", "👥 客户核心指标 (B2C)", "KPI cards", "Active customers, 复购率, 留存率, ARPU (standard).", "活跃客户、复购率、留存率、ARPU（标准口径）。"),
        ("⚠️ Churn Risk Buckets", "⚠️ 流失风险分层", "KPI cards", "Active / at-risk / lapsed & revenue at risk.", "活跃/有风险/流失 及风险收入。"),
        ("⏱️ Registration → First Purchase Funnel", "⏱️ 注册→首购漏斗", "Funnel", "Activation speed of new customers.", "新客激活速度。"),
        ("🌐 IP Geographic Origin (B2C)", "🌐 IP来源地分析 (B2C)", "Badge + bar", "Country–IP mismatch signal (world map removed).", "下单国与IP国错配信号（地图已移除）。"),
        ("🔄 New vs Returning (新客/老客)", "🔄 新客 vs 老客", "Donut / bar", "新客=注册月==订单月; 老客=注册月<订单月.", "新客=注册月==订单月；老客=注册月<订单月。"),
        ("🔗 Channel Performance (会员来源)", "🔗 渠道来源绩效（会员来源）", "Bar (H)", "Revenue per normalized channel (用户列表 join).", "按统一渠道（会员来源）的营业额（用户列表关联）。"),
        ("📈 Monthly Acquisition / 📊 Channel Analysis", "📈 月度获客 / 📊 渠道来源分析", "Bars", "New-customer intake & acquisition channels.", "新客获取量与获客渠道。"),
        ("📚 Cohort Retention & CLV", "📚 批次留存与CLV", "Heatmap", "Retention/LTV by acquisition month (complementary).", "按获客月的留存/LTV（补充视角）。"),
        ("📊 Order Frequency / Orders per Customer", "📊 下单频次 / 客均订单", "Bars", "Purchase-frequency distribution.", "购买频次分布。"),
    ]),
    ("🎟️", "Marketing & Promotions", "营销与促销", [
        ("🎟️ Promotion KPIs", "🎟️ 促销核心指标", "KPI cards", "Coupon spend, coupon-order revenue, ROI, usage.", "券支出、券单收入、ROI、使用量。"),
        ("📈 Coupon Spend vs Revenue", "📈 券支出 vs 收入", "Bar + line", "Monthly promo cost vs return.", "月度促销成本 vs 回报。"),
        ("🏷️ Campaign Performance", "🏷️ 活动绩效", "Table (Excel)", "Per-coupon orders, spend, ROI, repeat.", "各券 订单/支出/ROI/复购。"),
        ("⚖️ Coupon vs Non-Coupon Customers", "⚖️ 用券 vs 未用券客户", "Grouped bar", "Build loyalty or just discount?", "用券是建立忠诚还是单纯打折？"),
        ("🆕 New-User Promo Orders", "🆕 新人优惠订单", "Bar", "New-user promo volume by month.", "新人优惠订单月度量。"),
        ("⭐ Featured (Badge) Product Performance", "⭐ 角标产品表现", "Grouped bar", "Lift from badging products.", "角标对产品的提升。"),
    ]),
    ("⏱", "Sales Explorer", "时段销售查询", [
        ("🔎 Ad-hoc filters", "🔎 自定义筛选", "Controls", "Region/country/segment/status/date/time/weekday/product/operator/denom.", "地区/国家/分部/状态/日期/时段/星期/产品/运营商/面值。"),
        ("📊 Window KPIs", "📊 时段核心指标", "KPI cards", "Headline metrics for the slice vs prior.", "所选时段指标 vs 上期。"),
        ("🕐 Orders & Revenue by Hour", "🕐 分时订单与收入", "Bar + line", "Intraday pattern, selected band shaded.", "日内规律，选定时段高亮。"),
        ("📈 Daily Trend", "📈 每日趋势", "Line", "Orders & revenue across the range.", "区间内订单与收入。"),
        ("📋 Breakdown pivot", "📋 透视拆分", "Table (Excel/CSV)", "Group by operator/product/denom/country/day/hour.", "按 运营商/产品/面值/国家/日/小时 透视。"),
    ]),
    ("🤖", "AI Predictions", "AI预测", [
        ("📈 Revenue Forecast", "📈 收入预测", "Line + band", "4/8/12-week forecast with confidence & MAPE.", "4/8/12周预测，含置信区间与MAPE。"),
        ("🔮 Churn Prediction", "🔮 流失预测", "Feature bar + table", "Churn drivers + top at-risk customers.", "流失驱动因素 + 高风险客户。"),
        ("📦 Product Demand Forecast", "📦 产品需求预测", "Table", "Weekly order forecast per operator × category.", "各运营商×类别 周订单预测。"),
    ]),
    ("📖", "Guideline", "使用指南", [
        ("📖 Guideline (this tab)", "📖 使用指南（本页）", "Reference", "Catalogue of every visualization + terminology + removals.", "全部可视化目录 + 术语表 + 移除清单。"),
    ]),
]

_GUIDELINE_TERMS = [
    ("Revenue / GMV", "营业额 (GMV)", "Total paid amount (turnover)."),
    ("Old-customer revenue", "老客营业额", "GMV from returning customers."),
    ("New-customer revenue", "新客营业额", "GMV from first-time customers."),
    ("Successful orders", "成单数", "Count of successful orders."),
    ("Successful users", "成单人数", "Distinct customers with a successful order."),
    ("Success rate", "成单率", "Successful ÷ total orders."),
    ("AOV", "客单价", "Revenue ÷ orders."),
    ("Repurchase rate", "复购率", "|上月成功用户 ∩ 本月成功用户| / |本月成功用户|."),
    ("Retention rate", "留存率", "|上月新客成功 ∩ 本月成功| / |上月新客成功|."),
    ("New customers", "新客数", "DISTINCT 用户ID, 注册时间 ∈ period (from 用户列表)."),
    ("Conversion rate", "转化率", "|期内新客 ∩ 期内成功订单用户| / |期内新客|."),
    ("Returning / New", "老客 / 新客", "新客 = 注册月 == 订单月; 老客 = 注册月 < 订单月 (B2C)."),
    ("Airtime / Data", "充话费 / 买流量", "Two main product lines (话费 / 流量 in axes)."),
    ("Channel / source", "渠道来源 (来源汇总)", "Acquisition / payment channel."),
    ("Summary / Key countries / Global", "汇总 / 重点国家 / 全球", "Country grouping levels."),
]

_GUIDELINE_REMOVALS = [
    ("✅ Removed", "IP world choropleth — 'Global IP Origin Distribution (B2C)'", "Customer Analytics",
     "Low decision value vs visual weight. The country–IP mismatch badge + Top-15 IP-countries bar are kept (useful fraud / VPN signal)."),
    ("✅ Kept (moved)", "Iraq Pinstore weekly modules", "Supplier & Operator Performance",
     "Needed for estimation — relocated from Operational Intelligence to the Supplier & Operator Performance tab."),
    ("🟡 Candidate", "Redundant Top-N revenue/orders variants", "several tabs",
     "Some markets/operators are ranked 2–3 ways. Consolidate after review."),
]


def _guideline_children():
    """Build the static 'Guideline' tab: per-tab visualization catalogue,
    terminology quick-reference (bitsbang ↔ dashboard) and proposed removals."""
    def _esc(s):
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    cards = [ui.HTML(
        '<div class="chart-container" style="margin-bottom:18px;">'
        '<h2 style="margin:0 0 6px;">📖 <span class="lang-en">Dashboard Guideline</span>'
        '<span class="lang-zh">仪表盘使用指南</span></h2>'
        '<p style="color:#475569;margin:0;font-size:0.92em;">'
        '<span class="lang-en">Every visualization in this dashboard, grouped by tab — what it is and the '
        'business question it answers — plus a China-team terminology reference and the proposed-removals list.</span>'
        '<span class="lang-zh">本仪表盘所有可视化（按标签页分组）：图表类型与它回答的业务问题；'
        '另含与中国团队对齐的术语表和拟移除清单。</span></p></div>'
    )]

    def _bi(en_text, zh_text):
        return (f'<span class="lang-en">{_esc(en_text)}</span>'
                f'<span class="lang-zh">{_esc(zh_text)}</span>')

    for icon, en, zh, rows in _GUIDELINE_TABS:
        body = "".join(
            f'<tr style="border-bottom:1px solid #F1F5F9;">'
            f'<td style="padding:6px 10px;font-weight:600;color:#0F172A;">{_bi(t_en, t_zh)}</td>'
            f'<td style="padding:6px 10px;color:#5B6CFF;white-space:nowrap;">{_bi(ty, _GTYPE_ZH.get(ty, ty))}</td>'
            f'<td style="padding:6px 10px;color:#475569;">{_bi(u_en, u_zh)}</td></tr>'
            for (t_en, t_zh, ty, u_en, u_zh) in rows
        )
        cards.append(ui.HTML(
            f'<div class="chart-container" style="margin-bottom:14px;">'
            f'<h3 style="margin:0 0 8px;">{icon} '
            f'<span class="lang-en">{_esc(en)}</span><span class="lang-zh">{_esc(zh)}</span></h3>'
            f'<table style="width:100%;border-collapse:collapse;font-size:0.85em;">'
            f'<thead><tr style="text-align:left;border-bottom:2px solid #E2E8F0;color:#64748B;">'
            f'<th style="padding:6px 10px;">{_bi("Visualization", "可视化")}</th>'
            f'<th style="padding:6px 10px;">{_bi("Type", "类型")}</th>'
            f'<th style="padding:6px 10px;">{_bi("What it shows / question it answers", "用途 / 回答的问题")}</th></tr></thead>'
            f'<tbody>{body}</tbody></table></div>'
        ))

    term_rows = "".join(
        f'<tr style="border-bottom:1px solid #F1F5F9;">'
        f'<td style="padding:6px 10px;color:#475569;">{_esc(en)}</td>'
        f'<td style="padding:6px 10px;font-weight:700;color:#5B6CFF;white-space:nowrap;">{_esc(zh)}</td>'
        f'<td style="padding:6px 10px;color:#475569;">{_esc(desc)}</td></tr>'
        for (en, zh, desc) in _GUIDELINE_TERMS
    )
    cards.append(ui.HTML(
        '<div class="chart-container" style="margin-bottom:14px;">'
        '<h3 style="margin:0 0 8px;">🈯 <span class="lang-en">Terminology — bitsbang (China team) ↔ dashboard</span>'
        '<span class="lang-zh">术语对照 — 中国团队（bitsbang）↔ 仪表盘</span></h3>'
        '<table style="width:100%;border-collapse:collapse;font-size:0.85em;">'
        '<thead><tr style="text-align:left;border-bottom:2px solid #E2E8F0;color:#64748B;">'
        '<th style="padding:6px 10px;">Metric / concept</th><th style="padding:6px 10px;">术语 (adopted)</th>'
        '<th style="padding:6px 10px;">Definition</th></tr></thead>'
        f'<tbody>{term_rows}</tbody></table></div>'
    ))

    rem_rows = "".join(
        f'<tr style="border-bottom:1px solid #F1F5F9;">'
        f'<td style="padding:6px 10px;white-space:nowrap;font-weight:600;">{_esc(status)}</td>'
        f'<td style="padding:6px 10px;color:#0F172A;">{_esc(item)}</td>'
        f'<td style="padding:6px 10px;color:#94A3B8;white-space:nowrap;">{_esc(where)}</td>'
        f'<td style="padding:6px 10px;color:#475569;">{_esc(why)}</td></tr>'
        for (status, item, where, why) in _GUIDELINE_REMOVALS
    )
    cards.append(ui.HTML(
        '<div class="chart-container" style="margin-bottom:14px;">'
        '<h3 style="margin:0 0 8px;">🗑️ <span class="lang-en">Proposed removals (awaiting sign-off)</span>'
        '<span class="lang-zh">拟移除清单（待确认）</span></h3>'
        '<table style="width:100%;border-collapse:collapse;font-size:0.85em;">'
        '<thead><tr style="text-align:left;border-bottom:2px solid #E2E8F0;color:#64748B;">'
        '<th style="padding:6px 10px;">Status</th><th style="padding:6px 10px;">Item</th>'
        '<th style="padding:6px 10px;">Where</th><th style="padding:6px 10px;">Rationale</th></tr></thead>'
        f'<tbody>{rem_rows}</tbody></table></div>'
    ))
    return cards


def _remarks_accordion(tab_id: str):
    """Collapsible analyst remarks section appended to each tab."""
    saved = remarks_utils.get_remark(tab_id)
    return ui.div(
        ui.tags.details(
            ui.tags.summary(
                "💬 Analyst Notes & Remarks",
                style=("cursor: pointer; font-weight: 600; padding: 10px 14px; "
                       "background: #EEF0FF; color: #5B6CFF; border-radius: 8px; "
                       "margin-top: 16px; user-select: none; list-style: none; "
                       "border: 1px solid #C7D2FE;")
            ),
            ui.div(
                ui.p("Add analyst commentary, action items, or business context for this tab. "
                     "Notes are saved per tab per month and included in PDF exports.",
                     style="font-size: 0.82em; color: #64748B; margin: 8px 0;"),
                ui.input_text_area(
                    f"remark_{tab_id}", None,
                    value=saved,
                    placeholder="e.g. 'Strong MoM growth driven by Asia. Investigate Indonesia AOV decline. "
                                "Follow up with ops team on supplier capacity.'",
                    rows=3,
                ),
                ui.input_action_button(
                    f"save_remark_{tab_id}", "💾 Save Remark",
                    class_="refresh-btn",
                    style=("background: #5B6CFF !important; color: white !important; "
                           "border: none !important; padding: 7px 18px !important; "
                           "font-size: 0.88em !important; margin-top: 6px !important;")
                ),
                ui.output_text(f"remark_saved_msg_{tab_id}"),
                style="padding: 10px 4px;"
            ),
        ),
        style="margin-top: 8px;"
    )


app_ui = ui.page_sidebar(
    ui.sidebar(
        ui.h2(ui.tags.span("📊 Advanced Filters", class_="lang-en"),
              ui.tags.span("📊 高级筛选", class_="lang-zh")),

        ui.output_ui("sidebar_freshness_badge"),

        ui.div(
            ui.input_radio_buttons(
                "ui_lang", None,
                choices={"en": "🇬🇧 EN", "zh": "🇨🇳 中文"},
                selected="en", inline=True
            ),
            ui.tags.style("""
                #ui_lang .shiny-options-group { gap: 18px !important; }
                #ui_lang label { margin-right: 0 !important; font-size: 0.9em; }
                body[data-lang=zh] .lang-en { display: none !important; }
                body[data-lang=zh] .lang-zh { display: inline !important; }
                body[data-lang=en] .lang-zh { display: none !important; }
                body[data-lang=en] .lang-en { display: inline !important; }
                .lang-zh { display: none; }
            """),
            ui.tags.script("""
                (function() {
                    function setLang(l) { document.body.setAttribute('data-lang', l || 'en'); }
                    setLang('en');  // correct initial state before any server message
                    // Instant client-side flip on radio change (no server round-trip needed)
                    document.addEventListener('change', function(e) {
                        if (e.target && e.target.name === 'ui_lang') { setLang(e.target.value); }
                    });
                    // Also honour the server-pushed message once Shiny is ready
                    (function reg() {
                        if (window.Shiny && Shiny.addCustomMessageHandler) {
                            Shiny.addCustomMessageHandler('setDashLang', function(lang) { setLang(lang); });
                        } else { setTimeout(reg, 200); }
                    })();
                })();
            """),
            style="text-align:center; margin-bottom: 10px; padding-bottom: 6px; border-bottom: 1px solid rgba(255,255,255,0.2);"
        ),

        ui.div(
            ui.output_ui("label_segment"),
            ui.input_select("segment", None, choices=segment_choices, selected="All"),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_order_status"),
            ui.input_select("order_status_f", None,
                            choices=ORDER_STATUS_CHOICES, selected="Successful"),
            ui.p("Default counts only successful recharges in GMV/orders. "
                 "Switch to All/Refunded to analyse failures.",
                 style="font-size: 0.70em; color: rgba(255,255,255,0.65); margin: 4px 0 0 0;"),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_region"),
            ui.input_select("region", None, choices=region_choices, selected="All"),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_country"),
            ui.input_selectize(
                "country",
                None,
                choices=country_choices,
                selected="All",
                multiple=False,
                options={"placeholder": "Search market..."}
            ),
            ui.tags.details(
                ui.tags.summary(
                    "⚙️ Manage 重点国家",
                    style=("cursor:pointer; font-size:0.78em; color:rgba(255,255,255,0.8); "
                           "margin-top:6px; user-select:none; list-style:none;")
                ),
                ui.div(
                    ui.p("Current key countries (one per line):",
                         style="font-size:0.75em; color:rgba(255,255,255,0.7); margin:4px 0;"),
                    ui.input_text_area(
                        "key_countries_text", None,
                        value="\n".join(_load_key_countries()),
                        rows=6,
                        placeholder="One country name per line...",
                    ),
                    ui.input_action_button(
                        "save_key_countries", "💾 Save",
                        class_="refresh-btn",
                        style=("background:rgba(255,255,255,0.9)!important; "
                               "color:#5B6CFF!important; border:none!important; "
                               "padding:4px 12px!important; font-size:0.8em!important; "
                               "margin-top:4px!important;")
                    ),
                    ui.output_text("key_countries_saved_msg"),
                    style="padding:4px 0;"
                ),
            ),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_currency"),
            ui.input_radio_buttons("currency", None, choices=currency_choices, selected="RMB"),
            ui.tags.small(
                "💡 'Local Currency' uses the selected Market's local FX rate. "
                "Falls back to RMB when Market = All.",
                style="display:block; font-size:0.75em; color:rgba(255,255,255,0.75); margin-top:6px;"
            ),
            ui.output_ui("currency_status_badge"),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_trend_period"),
            ui.input_select("trend_period", None, choices=["Daily", "Weekly", "Monthly", "Quarterly", "Yearly"], selected="Daily"),
            class_="filter-section"
        ),

        ui.div(
            ui.output_ui("label_date_range"),
            ui.input_select(
                "quick_period",
                "Quick Period:",
                choices=["—", "Today", "Yesterday", "Past 7 Days", "This Month", "This Year", "All Time"],
                selected="—"
            ),
            ui.input_select("from_month", "From Month", choices=month_choices, selected="—"),
            ui.input_select("to_month", "To Month", choices=month_choices, selected="—"),
            (
                ui.tags.div(
                    ui.tags.label("Custom Range:", style="font-weight: 600; margin-top: 6px; display: block;"),
                    ui.input_date("date_from", "From date:",
                                  value=min_date, min=min_date, max=max_date,
                                  format="yyyy-mm-dd"),
                    ui.input_date("date_to", "To date:",
                                  value=max_date, min=min_date, max=max_date,
                                  format="yyyy-mm-dd"),
                ) if min_date and max_date else ui.p("Date range not available.")
            ),
            class_="filter-section"
        ),

        # ---- Apply filters: the big "Enter" button ----------------------
        ui.div(
            ui.input_action_button(
                "apply_btn",
                "↵  Enter",
                class_="refresh-btn",
                style=("width: 100%; font-size: 1.05em; font-weight: 700; "
                       "padding: 12px 16px; letter-spacing: 0.5px; "
                       "background: rgba(255,255,255,0.95) !important; "
                       "color: #5B6CFF !important; "
                       "border: 2px solid rgba(255,255,255,0.95) !important;")
            ),
            ui.tags.span(
                ui.output_text("apply_status"),
                style="font-size: 0.75em; color: rgba(255,255,255,0.85); "
                      "display: block; text-align: center; margin-top: 6px;"
            ),
            style="padding: 8px 4px;"
        ),

        # ---- Download current view + PDF Report -------------------------
        ui.tags.details(
            ui.tags.summary(
                "⬇ Download / Export",
                style=("cursor: pointer; font-weight: 600; padding: 10px 12px;"
                       "background: rgba(255,255,255,0.18); color: white;"
                       "border-radius: 8px; margin-top: 12px; user-select: none;"
                       "list-style: none;")
            ),
            ui.div(
                ui.p("Export the rows matching your current filters.",
                     style="font-size: 0.78em; color: rgba(255,255,255,0.85); margin: 8px 0;"),
                ui.download_button(
                    "download_filtered_csv", "📄 Download CSV",
                    class_="refresh-btn",
                    style="width: 100%; margin-bottom: 6px;"
                ),
                ui.download_button(
                    "download_filtered_xlsx", "📊 Download Excel",
                    class_="refresh-btn",
                    style="width: 100%; margin-bottom: 6px;"
                ),
                ui.download_button(
                    "download_pdf", "🖨 Export PDF Report",
                    class_="refresh-btn",
                    style=("width: 100%; background: rgba(255,255,255,0.95) !important; "
                           "color: #5B6CFF !important; font-weight: 700 !important;")
                ),
                ui.p("PDF contains one A4-landscape page per dashboard tab with KPIs, "
                     "charts, key table, and analyst remarks. May take 30–60 seconds to generate.",
                     style="font-size: 0.72em; color: rgba(255,255,255,0.7); margin-top: 8px;"),
                ui.p("CSV is fast for any size. Excel may be slow if the filtered "
                     "view exceeds ~200K rows — narrow the date range first.",
                     style="font-size: 0.72em; color: rgba(255,255,255,0.7); margin-top: 4px;"),
                style="padding: 8px 4px;"
            ),
        ),

        ui.hr(),
        ui.p("💡 Tip: pick your Customer Segment / Region / Market / Currency / Dates above, then press Enter to apply.",
             style="font-size: 0.78em;"),

        # ---- Quick refresh: re-read the parquet (fast, ~0.5s) ------------
        ui.div(
            ui.tags.label("Dashboard not showing latest data?",
                          style="font-weight:700; color: white; display:block; margin-bottom:4px;"),
            ui.p("Refresh Cache: re-reads the parquet cache file. Use this when the data pipeline "
                 "was rebuilt outside the dashboard.",
                 style="font-size: 0.72em; color: rgba(255,255,255,0.85); margin: 0 0 8px 0;"),
            ui.input_action_button(
                "refresh_disk_btn", "🔃 Refresh Cache",
                class_="refresh-btn",
                style="width: 100%;"
            ),
            ui.p("⚡ Instant (<1 second). Does not re-process source xlsx files.",
                 style="font-size: 0.70em; color: rgba(255,255,255,0.65); margin: 6px 0 0 0;"),
            style="margin-top: 14px; padding: 10px 12px; background: rgba(255,255,255,0.10); border-radius: 8px;"
        ),

        # ---- Reload from source xlsx (heavy: rebuilds DB from source) ----
        ui.div(
            ui.tags.label("Updated the source data files?",
                          style="font-weight:700; color: white; display:block; margin-bottom:4px;"),
            ui.p("Rebuild Data Pipeline: re-reads Master Data.xlsx + Agent Data.xlsx 'Whole' sheets "
                 "and rebuilds the entire database from source.",
                 style="font-size: 0.72em; color: rgba(255,255,255,0.85); margin: 0 0 8px 0;"),
            ui.input_action_button(
                "reload_source_btn", "🔄 Rebuild Data Pipeline",
                class_="refresh-btn",
                style="width: 100%;"
            ),
            ui.p("⚠ Takes 10–25 minutes. Overwrites the rolling database "
                 "files — any prior daily imports not in the source xlsx will be replaced.",
                 style="font-size: 0.70em; color: rgba(255,255,255,0.65); margin: 6px 0 0 0;"),
            style="margin-top: 10px; padding: 10px 12px; background: rgba(255,255,255,0.10); border-radius: 8px;"
        ),

        # ---- Export the rolling stores back to human-readable Excel -------
        ui.div(
            ui.tags.label("Need the Excel backup files?",
                          style="font-weight:700; color: white; display:block; margin-bottom:4px;"),
            ui.p("Daily imports now save to fast parquet stores. Click below to "
                 "rewrite Agent_Database.xlsx / Master_Database.xlsx from them.",
                 style="font-size: 0.72em; color: rgba(255,255,255,0.85); margin: 0 0 8px 0;"),
            ui.input_action_button(
                "export_excel_btn", "💾 Export Excel Backup",
                class_="refresh-btn",
                style="width: 100%;"
            ),
            ui.p("Takes a few minutes for 1M+ rows. Only needed when you want "
                 "to open the rolling database in Excel.",
                 style="font-size: 0.70em; color: rgba(255,255,255,0.65); margin: 6px 0 0 0;"),
            style="margin-top: 10px; padding: 10px 12px; background: rgba(255,255,255,0.10); border-radius: 8px;"
        ),

        # ---- Shared status panel (shows latest result of Import or Reload) ---
        ui.div(
            ui.output_ui("import_status_ui"),
            style=("background: rgba(0,0,0,0.18); padding: 10px;"
                   "border-radius: 6px; margin-top: 10px;"
                   "font-size: 0.78em; color: white; max-height: 240px;"
                   "overflow-y: auto;")
        ),

        # ---- Daily-file Import (collapsible — used less often) ----------
        ui.tags.details(
            ui.tags.summary(
                "📥 Import Daily Data",
                style=("cursor: pointer; font-weight: 600; padding: 10px 12px;"
                       "background: rgba(255,255,255,0.18); color: white;"
                       "border-radius: 8px; margin-top: 12px; user-select: none;"
                       "list-style: none;")
            ),
            ui.div(
                ui.p("Upload daily Master and/or Agent xlsx/csv. Duplicate orders "
                     "auto-skipped. Each uploaded file is also copied to its dedicated "
                     "archive folder for audit.",
                     style="font-size: 0.78em; color: rgba(255,255,255,0.85); margin: 8px 0;"),
                ui.tags.details(
                    ui.tags.summary("📁 Archive locations",
                                    style="cursor: pointer; font-size: 0.78em; "
                                          "color: rgba(255,255,255,0.85); user-select:none;"),
                    ui.div(
                        ui.div("Agent:", style="font-weight:600; margin-top:6px;"),
                        ui.div(str(db_utils.AGENT_ARCHIVE_DIR),
                               style="font-family: Consolas, monospace; word-break: break-all; opacity: 0.85;"),
                        ui.div("Master:", style="font-weight:600; margin-top:6px;"),
                        ui.div(str(db_utils.MASTER_ARCHIVE_DIR),
                               style="font-family: Consolas, monospace; word-break: break-all; opacity: 0.85;"),
                        style="font-size: 0.72em; color: rgba(255,255,255,0.85); margin-top: 4px;"
                    ),
                ),
                ui.input_file(
                    "agent_upload", "Agent (B2B) file",
                    accept=[".xlsx", ".xls", ".xlsm", ".csv", ".tsv"],
                    multiple=False,
                    button_label="Browse", placeholder="No file"
                ),
                ui.input_file(
                    "master_upload", "Master (B2C) file",
                    accept=[".xlsx", ".xls", ".xlsm", ".csv", ".tsv"],
                    multiple=False,
                    button_label="Browse", placeholder="No file"
                ),
                ui.input_action_button(
                    "import_btn", "▶ Process & Append",
                    class_="refresh-btn",
                    style="margin-top: 8px; width: 100%;"
                ),
                style="padding: 8px 4px;"
            ),
        ),
        class_="sidebar"
    ),
    ui.div(
        ui.head_content(
            ui.tags.style(css),
            # Serve plotly.min.js locally so the browser doesn't fetch it
            # from cdn.plot.ly every time. Saves ~2-3s on first-load.
            ui.tags.script(src="static/plotly.min.js"),
            # Loading overlay shown immediately when 'Reload from source' is clicked
            ui.tags.script(RELOAD_OVERLAY_JS),
            # Sidebar hover-expand + pin behaviour
            ui.tags.script(SIDEBAR_UX_JS),
        ),
        ui.div(
            ui.h1(
                ui.tags.span("📈 Global Mobile Recharge — Revenue Intelligence Dashboard", class_="lang-en"),
                ui.tags.span("📈 全球移动充值 — 收入智能仪表板", class_="lang-zh"),
            ),
            ui.p(
                ui.tags.span("Comprehensive analytics for Revenue (GMV), Operational Performance, Supplier Margins, Product Mix, and Customer Lifetime Value", class_="lang-en"),
                ui.tags.span("收入(GMV)、运营绩效、供应商利润、产品结构及客户终身价值综合分析", class_="lang-zh"),
                style="margin: 10px 0 0 0; opacity: 0.8;"),
            class_="main-header"
        ),
        ui.output_ui("staleness_banner"),
        ui.HTML(
            '<div style="background:#FFF7ED;border:1px solid #FED7AA;color:#9A3412;'
            'padding:8px 14px;border-radius:8px;margin:6px 0 4px;font-size:0.82em;line-height:1.5;">'
            'ℹ️ <b>China-team 基准 (全球共用计算取数公式及标准)</b>：核心指标默认<b>剔除「电子钱包 / Touch\'n Go」</b>'
            '（约占 GMV 22%），以 <b>充值成功</b> 为口径；<b>汇总 / 全球</b> 视图剔除马来西亚。 '
            '<span style="opacity:.8;">Core metrics exclude e-wallet &amp; Touch\'n Go (≈22% of GMV) on the 充值成功 basis; '
            'Summary/Global views exclude Malaysia.</span></div>'
        ),
        ui.navset_tab(
            ui.nav_panel(
                _bnav("Executive Overview", "执行概览"),
                ui.div(
                    _bh3("🧭 Operating Summary", "🧭 运营概览",
                         _help("Bitsbang-style operating KPIs on the successful-order (充值成功) basis, with "
                               "month-over-month vs the prior equal period. Cards showing '—' await the China-team "
                               "formulas for 复购率 / 留存率 and the 新客/老客 split (老客·新客营业额, 新客数, 转化率).")),
                    _bp("China-team operating view — 营业额, 成单数/成单人数, 成单率, 客单价 and customer metrics on the 充值成功 basis.",
                        "中国团队运营视角 — 以「充值成功」为口径的营业额、成单数/成单人数、成单率、客单价及客户指标。"),
                    ui.output_ui("operating_overview_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💎 Net Contribution", "💎 净贡献",
                         _help("Net Contribution = successful GMV − COGS (结算价 converted to RMB) − coupon spend. "
                               "已退款 GMV is shown separately and excluded. True bottom-line per the selected filters.")),
                    _bp("The true bottom line: successful GMV minus supplier cost (COGS) minus coupon spend.",
                        "真实利润口径：成功GMV 减去供应商成本（COGS）再减去优惠券支出。"),
                    ui.output_ui("net_contribution_kpi"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🚨 Anomaly Detection & Alerts", "🚨 异常检测与预警",
                         _help("Cards are generated by comparing the last 7 days vs the prior 4-week baseline.")),
                    _bp("Auto-detected signals from the last 7 days vs the prior 4-week baseline.",
                        "基于过去7天与前4周基线的自动检测信号，忽略日期范围，始终锚定最新数据。"),
                    ui.output_ui("alerts_panel"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Key Performance Indicators (KPIs)", "📊 核心绩效指标 (KPIs)"),
                    ui.output_ui("overview_metrics"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⚡ Period-over-Period (PoP) Top Movers", "⚡ 环比 Top 变动榜"),
                    _bp("Markets and operators with the largest revenue change versus the previous equally-long period.",
                        "与前等长周期相比收入变化最大的市场与运营商。"),
                    ui.output_ui("top_movers_strip"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Revenue & Order Volume Trend", "📈 收入与订单量趋势"),
                    ui.output_ui("overview_sales_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🥧 Revenue (GMV) by Customer Segment", "🥧 各客户分类收入 (GMV)"),
                    ui.output_ui("overview_sales_segment"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🌐 Revenue Contribution by Region", "🌐 各地区收入贡献",
                         _help("Revenue split across geographic regions.")),
                    _bp("Regional revenue breakdown to identify concentration and diversification across continents.",
                        "区域收入分布，快速识别集中度及洲际多元化机会。"),
                    ui.output_ui("overview_region_donut"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🏆 Top 5 Markets by Revenue (GMV)", "🏆 收入前 5 大市场 (GMV)"),
                    _bp("Quick-glance ranking of your highest-value markets.",
                        "高价值市场排名速览，完整排名请查看「市场洞察」页。"),
                    ui.output_ui("overview_top5_countries"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🌏 Key Countries — Last 3 Months Revenue", "🌏 重点国家 — 近3个月营业额",
                         _help("Grouped bars: GMV (充值成功) for each key country over the latest 3 months, "
                               "independent of the country filter. Edit the key-country list in the sidebar.")),
                    _bp("Momentum of your priority markets over the last three months (充值成功 basis).",
                        "重点市场近3个月的营业额走势（充值成功口径），不受国家筛选影响。"),
                    ui.output_ui("key_country_3m_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Segment Performance Summary", "📋 分部业绩汇总"),
                    ui.output_data_frame("segment_summary_table"),
                    class_="data-table"
                ),
                _remarks_accordion("executive_overview"),
            ),
            ui.nav_panel(
                _bnav("Performance Comparison", "业绩对比"),
                ui.div(
                    _bh3("🆚 Period-over-Period (PoP) Comparison", "🆚 环比对比分析"),
                    _bp("Pick any two date windows to compare side-by-side. Sidebar filters still apply.",
                        "选择任意两个时间段并排对比。侧边栏过滤条件仍然有效。"),
                    ui.div(
                        ui.div(
                            ui.tags.label("Period A (current)", style="font-weight:700; color:#5B6CFF; margin-bottom:6px; display:block;"),
                            ui.input_date_range(
                                "compare_a", None,
                                start=compare_a_default_start, end=compare_a_default_end,
                                min=min_date, max=max_date, format="yyyy-mm-dd"
                            ) if compare_a_default_start else ui.p("No data"),
                            style="flex: 1 1 45%; min-width: 280px;"
                        ),
                        ui.div(
                            ui.tags.label("Period B (baseline)", style="font-weight:700; color:#94A3B8; margin-bottom:6px; display:block;"),
                            ui.input_date_range(
                                "compare_b", None,
                                start=compare_b_default_start, end=compare_b_default_end,
                                min=min_date, max=max_date, format="yyyy-mm-dd"
                            ) if compare_b_default_start else ui.p("No data"),
                            style="flex: 1 1 45%; min-width: 280px;"
                        ),
                        ui.div(
                            ui.input_action_button(
                                "compare_swap", "↔ Swap A ↔ B",
                                style=("background: white; color: #5B6CFF; "
                                       "border: 2px solid #5B6CFF; padding: 8px 16px; "
                                       "border-radius: 8px; font-weight: 600; cursor: pointer; "
                                       "margin-top: 24px; align-self: flex-end;")
                            ),
                            style="flex: 0 0 auto;"
                        ),
                        style="display: flex; gap: 16px; align-items: flex-start; flex-wrap: wrap;"
                    ),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 KPI Variance — Period A vs Period B", "📊 指标差异 — 时段A vs 时段B"),
                    _bp("Side-by-side KPI cards: Revenue (GMV), Orders, Active Customers, and AOV for each period.",
                        "并排KPI卡片：收入(GMV)、订单量、活跃客户数、AOV。"),
                    ui.output_ui("compare_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Revenue Trend Overlay — Period A vs Period B", "📈 收入趋势叠加 — 时段A vs 时段B"),
                    _bp("Periods aligned to Day 1 for trajectory comparison. Hover for the actual calendar date.",
                        "两段时间对齐至第1天，便于轨迹比较。悬停可查看实际日期。"),
                    ui.output_ui("compare_trend_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🏃 Top Revenue Movers by Market, Operator & Denomination", "🏃 按市场/运营商/面值排名的收入变动"),
                    _bp("Largest absolute revenue delta between Period A and B. Positive = growth driver; negative = revenue at risk.",
                        "时段A与B之间绝对收入差最大的市场/运营商/面值。正值=增长驱动；负值=收入风险。"),
                    ui.output_ui("compare_movers_tables"),
                    class_="chart-container"
                ),
                _remarks_accordion("performance_comparison"),
            ),
            ui.nav_panel(
                _bnav("Revenue & Orders", "收入与订单"),
                ui.div(
                    _bh3("📊 Revenue & Orders KPIs", "📊 收入与订单核心指标"),
                    _bp("Key performance indicators for the selected period. GMV = Gross Merchandise Value.",
                        "所选周期核心绩效指标。GMV = 商品交易总额。AOV = 客单价。"),
                    ui.output_ui("revenue_orders_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💰 Revenue (GMV) by Customer Segment", "💰 各客户分类收入 (GMV)"),
                    _bp("Revenue split between B2B (Agent) and B2C (Master) customer segments.",
                        "B2B（代理渠道）与 B2C（主渠道）客户分类的收入分布。"),
                    ui.output_ui("sales_segment_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Order Volume by Customer Segment", "📦 各客户分类订单量"),
                    _bp("Number of unique orders placed by B2B vs B2C customers.",
                        "B2B 与 B2C 客户的独立订单数量对比。"),
                    ui.output_ui("orders_segment_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💎 Average Order Value (AOV) by Customer Segment", "💎 各客户分类客单价 (AOV)",
                         _help("AOV = Total Revenue ÷ Total Orders for each segment.")),
                    _bp("Higher AOV signals stronger per-transaction value; guide pricing strategy and promotions.",
                        "高 AOV 代表每笔交易价值更强，用于指导定价策略和分部促销活动。"),
                    ui.output_ui("aov_by_segment_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Revenue & Order Volume by Market (GMV)", "📋 各市场收入与订单量 (GMV)"),
                    _bp("Detailed breakdown by market and customer segment.",
                        "按市场和客户分类的详细拆解，完整市场排名请查看「市场洞察」。"),
                    ui.output_data_frame("sales_by_country_table"),
                    class_="data-table"
                ),
                # ══ Order Status / Quality section ════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(239,68,68,0.10),transparent);'
                    'border-left:4px solid #EF4444;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:18px 0;">'
                    '<span style="font-size:1.5em;">🚦</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Order Status &amp; Quality</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '订单状态与质量分析</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Success / refund / cancellation analysis — always shows ALL statuses, '
                    'regardless of the sidebar Order Status filter</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🚦 Order Status KPIs", "🚦 订单状态核心指标",
                         _help("Computed on ALL orders in the selected period/segment/market — "
                               "the sidebar Order Status filter does not apply here.")),
                    _bp("Success rate is a core service-quality metric; refunds erode realised revenue and damage customer trust.",
                        "成功率是核心服务质量指标；退款侵蚀实际收入并损害客户信任。"),
                    ui.output_ui("order_status_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Order Count by Status × Segment", "📊 各状态 × 客户分类订单量"),
                    _bp("Compare how B2B and B2C orders distribute across success, refund, and cancellation.",
                        "对比 B2B 与 B2C 订单在成功、退款、取消之间的分布。"),
                    ui.output_ui("order_status_breakdown_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📉 Monthly Refund Rate Trend", "📉 月度退款率趋势",
                         _help("Refunded orders ÷ total orders per month, per segment. "
                               "A rising line signals supplier or product quality issues.")),
                    _bp("Watch for refund-rate spikes — they usually trace back to a specific supplier or operator outage.",
                        "关注退款率飙升——通常可追溯到特定供应商或运营商故障。"),
                    ui.output_ui("refund_trend_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⚠ Refund Rate by Operator (Top 10)", "⚠ 各运营商退款率排名 (前10)",
                         _help("Operators with at least 200 orders, ranked by refund rate. "
                               "High refund rate = supplier quality problem.")),
                    _bp("Use this ranking in supplier reviews — operators with persistent high refund rates need escalation or rerouting.",
                        "用于供应商考核——退款率持续偏高的运营商需要升级处理或切换通道。"),
                    ui.output_ui("refund_by_operator_chart"),
                    class_="chart-container"
                ),
                _remarks_accordion("revenue_orders"),
            ),
            ui.nav_panel(
                _bnav("Market Intelligence", "市场洞察"),
                ui.div(
                    ui.div(
                        ui.tags.span(
                            ui.tags.span("🔍 Market Comparison Filter", class_="lang-en"),
                            ui.tags.span("🔍 市场对比筛选", class_="lang-zh"),
                            style="font-weight:600; color:#5B6CFF; font-size:0.95em;"
                        ),
                        ui.input_selectize(
                            "mi_compare_countries", None,
                            choices=_raw_country_choices,
                            multiple=True,
                            options={"placeholder": "Select specific markets to compare…",
                                     "plugins": ["remove_button"]}
                        ),
                        ui.tags.small(
                            ui.tags.span("When markets are selected here, all charts on this page scope to those markets only.", class_="lang-en"),
                            ui.tags.span("选择市场后，本页所有图表将只显示所选市场数据。", class_="lang-zh"),
                            style="color:#64748B; font-size:0.8em;"
                        ),
                        style=("background:#EEF0FF; border:1px solid #C7D2FE; border-radius:10px; "
                               "padding:12px 16px; margin-bottom:12px;")
                    ),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🗺️ Global Revenue Distribution (World Map)", "🗺️ 全球收入分布（世界地图）",
                         _help("Choropleth map shaded by total revenue (GMV).")),
                    ui.output_ui("country_world_map"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🚀 Revenue Momentum: Top Risers vs 📉 Top Decliners", "🚀 收入动能：增长最快 vs 📉 下滑最大"),
                    _bp("Markets with the largest revenue movement vs an equally-long prior period.",
                        "与前等长周期相比收入变化最大的市场，下滑代表留存或定价风险。"),
                    ui.output_ui("country_growth_table"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🌍 Top Markets by Revenue (GMV)", "🌍 按收入排名前15市场 (GMV)"),
                    _bp("Top 15 markets ranked by total Gross Merchandise Value for the selected period.",
                        "所选周期内按 GMV 排名的前15个市场。"),
                    ui.output_ui("country_sales_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Top Markets by Order Volume", "📦 按订单量排名前15市场"),
                    _bp("Top 15 markets by order count. High volume with low AOV signals upsell potential.",
                        "高订单量但低 AOV 的市场是增值销售机会。"),
                    ui.output_ui("country_orders_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💎 Average Order Value (AOV) by Market", "💎 各市场客单价 (AOV)",
                         _help("AOV = Revenue ÷ Orders per market.")),
                    _bp("Markets sorted by AOV. Pair with order volume to identify upsell vs. penetration opportunities.",
                        "按 AOV 降序排列。结合订单量可识别增值销售与市场渗透机会。"),
                    ui.output_ui("country_aov_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💎 Market Opportunity Matrix (Volume × AOV)", "💎 市场机会矩阵（订单量 × AOV）",
                         _help("Each bubble is a market. X = Order Volume, Y = AOV, size = GMV.")),
                    _bp("Bottom-right: high volume/low AOV — upsell opportunity. Top-left: low volume/high AOV — penetration.",
                        "右下：高量低价，增值机会；左上：低量高价，渗透机会；右上：核心市场。"),
                    ui.output_ui("country_potential_scatter"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🧭 Market Expansion Radar — Strategic Quadrant Classification", "🧭 市场拓展雷达 — 战略四象限",
                         _help("Markets classified by Order Volume and AOV vs median.")),
                    _bp("Classifies every market into four strategic quadrants based on volume and AOV.",
                        "核心市场(高量高价)、增值机会(高量低价)、成长市场(低量高价)、长尾(低量低价)。"),
                    ui.output_ui("country_expansion_radar"),
                    ui.output_ui("country_expansion_quadrant_tables"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📅 Monthly Revenue Heatmap by Market (Top 15)", "📅 各市场月度收入热力图（前15）",
                         _help("Each cell shows revenue for a market × month. Use to spot seasonal patterns.")),
                    ui.output_ui("country_month_heatmap"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Order Volume by Market and Customer Segment", "📊 各市场订单量（按客户分类）"),
                    _bp("Stacked bar: B2B vs B2C order split per market — reveals channel mix by geography.",
                        "堆叠柱状图：每个市场的 B2B vs B2C 订单拆分，揭示各市场渠道结构。"),
                    ui.output_ui("country_orders_by_segment_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("📋 Market KPI Scorecard", "📋 市场 KPI 评分卡", style="margin: 0;"),
                        ui.download_button(
                            "download_country_summary", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background: #5B6CFF !important; color: white !important; "
                                   "border: none !important; padding: 6px 14px !important; "
                                   "font-size: 0.85em !important; width: auto !important; "
                                   "margin: 0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    ui.p("Comprehensive market-level scorecard: Revenue (GMV), Order Volume, AOV, Gross Margin, "
                         "Customer Segment split, and Period-over-Period Growth.",
                         style="color:#64748B; font-size:0.88em; margin-top:8px;"),
                    ui.output_data_frame("country_summary_table"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("💲 Avg Recharge Denomination by Market", "💲 各市场平均充值面值",
                         _help("Average recharge denomination (face value) per market. "
                               "High avg = customers prefer large top-ups. "
                               "Low avg = frequent small top-ups. "
                               "Use to plan product mix per market.")),
                    _bp("Markets with high avg denomination are prime candidates for large-bundle product launches.",
                        "平均面值高的市场是推出大额充值套餐产品的优先候选市场。"),
                    ui.output_ui("denomination_aov_by_market"),
                    class_="chart-container"
                ),
                # ══ Destination & Beneficiary Analysis ════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(14,165,233,0.10),transparent);'
                    'border-left:4px solid #0EA5E9;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:18px 0 14px;">'
                    '<span style="font-size:1.5em;">📞</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Recharge Destination &amp; Beneficiary Analysis</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '充值目的地与受益号码分析</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Where the recharges actually land (区号 calling codes + 充值号码 recharge numbers)</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🌍 Top Recharge Destinations (by calling code)", "🌍 充值目的地排名（按区号）",
                         _help("The 区号 column gives the destination calling code of every recharge — "
                               "the market the top-up actually lands in.")),
                    _bp("The truest market view: where the phones being recharged actually are.",
                        "最真实的市场视图：被充值的手机号实际所在的市场。"),
                    ui.output_ui("destination_market_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🔀 Billing vs Destination Mismatch", "🔀 下单市场 vs 充值目的地错配",
                         _help("Orders where the billing/order country differs from the destination calling-code "
                               "country = cross-border gifting / remittance-style usage.")),
                    _bp("High mismatch share = diaspora/remittance demand — a marketing segment of its own.",
                        "错配占比高 = 侨汇/跨境代充需求，可作为独立营销客群。"),
                    ui.output_ui("destination_mismatch_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📱 Beneficiary Numbers — Reach & Stickiness", "📱 受益号码 — 触达与黏性",
                         _help("Unique recharge numbers (充值号码) = actual end-beneficiaries. "
                               "Numbers-per-user > 3 suggests reseller behaviour in B2C.")),
                    _bp("Orders count transactions; unique numbers count people reached. The gap reveals repeat top-ups and resellers.",
                        "订单数是交易量，唯一号码数是触达人数。两者差距揭示复充行为与代充客户。"),
                    ui.output_ui("beneficiary_analysis"),
                    class_="chart-container"
                ),
                _remarks_accordion("market_intelligence"),
            ),
            ui.nav_panel(
                _bnav("Operational Intelligence", "运营智能"),
                ui.div(
                    _bh3("📊 Operational KPIs", "📊 运营核心指标"),
                    _bp("Key operational metrics: Avg Daily Revenue, Avg Daily Orders, Peak Revenue Day, Peak Hour.",
                        "日均收入、日均订单数、最高收入日及高峰时段等运营核心指标。"),
                    ui.output_ui("ops_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Revenue Velocity — Revenue & Order Volume Trend", "📈 收入速度 — 收入与订单量趋势",
                         _help("Dual-axis chart: bars = order volume, line = revenue.")),
                    ui.output_ui("daily_sales_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📉 Day-over-Day Revenue Change (%)", "📉 日环比收入变化 (%)",
                         _help("Green = increased; Red = declined vs prior day.")),
                    _bp("Large negative bars may indicate supplier downtime, payment failures, or market disruptions.",
                        "大幅负值可能表明供应商宕机、支付失败或市场特定中断。"),
                    ui.output_ui("daily_delta_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📅 Order Activity Heatmap (Day of Week × Hour of Day)", "📅 订单活跃度热力图（星期 × 小时）",
                         _help("Each cell = orders at that day/hour. Use to plan staffing and maintenance.")),
                    _bp("Identify peak trading hours and low-activity windows for promotions and maintenance.",
                        "识别高峰交易时段及低活跃窗口，用于安排促销活动和系统维护。"),
                    ui.output_ui("weekday_sales_chart"),
                    class_="chart-container"
                ),
                _remarks_accordion("operational_intelligence"),
            ),
            ui.nav_panel(
                _bnav("Supplier & Operator Performance", "供应商绩效"),
                ui.div(
                    _bh3("🤝 Operator Performance Snapshot", "🤝 供应商绩效快照",
                         _help("Key metrics anchored to the current filter selection.")),
                    _bp("KPI snapshot for the period. Use as anchor metrics when negotiating volume discounts and SLA terms.",
                        "当期 KPI 快照，可用作与各供应商谈判折扣、返利及 SLA 条款的锚点。"),
                    ui.output_ui("supplier_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⚠️ Supplier Concentration Risk", "⚠️ 供应商集中度风险",
                         _help("Top 3 operators >80% GMV = high supplier concentration risk.")),
                    _bp("High concentration (>80% from top 3) signals vendor dependency. Target diversification.",
                        "高集中度（前3供应商占 GMV >80%）表明供应商依赖风险，应推进多元化布局。"),
                    ui.output_ui("supplier_concentration_card"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💰 Gross Margin by Operator (Revenue − Cost of Goods)", "💰 各运营商毛利润（收入 − 结算成本）",
                         _help("Gross Margin = Revenue − Settlement Price. Thin margins are renegotiation targets.")),
                    _bp("Thin margins indicate pricing pressure or unfavorable settlement terms.",
                        "毛利润偏低表明定价压力或不利结算条款，应优先重新谈判合同。"),
                    ui.output_ui("supplier_margin_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Gross Margin % Trend by Operator", "📊 各运营商毛利率趋势",
                         _help("Margin % trend. Decline = margin compression, signal to renegotiate.")),
                    _bp("A downward trend signals deteriorating supplier terms requiring renegotiation.",
                        "下降趋势表明供应商条款恶化，需重新谈判。"),
                    ui.output_ui("supplier_margin_pct_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🥧 Revenue Concentration — Pareto Analysis", "🥧 收入集中度 — 帕累托分析",
                         _help("Bars = GMV per operator. Red line = cumulative share.")),
                    _bp("If 3 operators drive 80% of GMV, they are your highest-leverage vendor relationships.",
                        "若前3家供应商贡献80% GMV，则属于高集中风险，同时也是最具谈判杠杆的关系。"),
                    ui.output_ui("supplier_pareto"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Operator Revenue Trend", "📈 运营商收入趋势"),
                    _bp("Monthly revenue per operator. Identify declining (churn risk) or growing (upsell) operators.",
                        "各运营商月度收入走势，识别流失风险或增值机会。"),
                    ui.output_ui("supplier_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🚀 Top Operators by Revenue (GMV)", "🚀 按收入排名运营商 (GMV)"),
                    ui.output_ui("operator_sales_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Top Operators by Order Volume", "📦 按订单量排名运营商"),
                    ui.output_ui("operator_orders_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("📋 Operator Performance Scorecard (Sortable)", "📋 运营商绩效评分卡（可排序）", style="margin: 0;"),
                        ui.download_button(
                            "download_supplier_scorecard", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background: #5B6CFF !important; color: white !important; "
                                   "border: none !important; padding: 6px 14px !important; "
                                   "font-size: 0.85em !important; width: auto !important; "
                                   "margin: 0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    ui.p("Sort by Gross Margin, GMV, AOV, or Period-over-Period Growth to prepare negotiation briefs. "
                         "Download to Excel with filters embedded in the filename.",
                         style="color:#64748B; margin-top:8px;"),
                    ui.output_data_frame("supplier_scorecard"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("💹 Gross Margin by Product Category", "💹 各产品类别毛利润",
                         _help("Revenue vs cost (settlement price) breakdown by product category. "
                               "Requires settlement_price data. "
                               "Margin % shown above each bar.")),
                    _bp("Compare margin rates across product categories to identify which categories drive the most profit.",
                        "比较各产品类别的毛利率，识别利润贡献最高的类别。"),
                    ui.output_ui("margin_by_category_chart"),
                    class_="chart-container"
                ),
                # ══ Fulfillment & Routing Health ══════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(245,158,11,0.10),transparent);'
                    'border-left:4px solid #F59E0B;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:18px 0 14px;">'
                    '<span style="font-size:1.5em;">🔌</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Fulfillment &amp; Routing Health</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '履约与路由健康度</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Supplier order-id coverage (接口商订单号), PIN delivery, payment gateway mix</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🩺 Fulfillment KPIs", "🩺 履约核心指标",
                         _help("Routing coverage = orders carrying a supplier-side order id (接口商订单号). "
                               "Successful orders without one are a reconciliation risk.")),
                    _bp("Orders marked successful but missing the supplier order id cannot be reconciled against supplier statements.",
                        "标记成功却缺少接口商订单号的订单无法与供应商账单对账。"),
                    ui.output_ui("fulfillment_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⚠ Successful Orders Missing Supplier Order ID", "⚠ 缺少接口商订单号的成功订单",
                         _help("By operator — these orders were charged as successful but have no supplier-side "
                               "reference, so they can't be matched in reconciliation.")),
                    _bp("Escalate operators with persistent routing gaps — every order here is unverifiable spend.",
                        "对持续存在路由缺口的运营商进行升级处理——这里的每一单都是无法核验的支出。"),
                    ui.output_ui("routing_gap_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("💱 Settlement Currency Audit", "💱 结算币种核对表", style="margin: 0;",
                             ),
                        ui.download_button(
                            "download_settlement_audit", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background:#5B6CFF !important; color:white !important; "
                                   "border:none !important; padding:6px 14px !important; "
                                   "font-size:0.85em !important; width:auto !important; margin:0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    _bp("Settlement prices arrive in mixed currencies (local for MY/ID/KG/SA/MM/VN, per-product for "
                        "MX/LK, USD elsewhere). This table shows the currency applied per market and the resulting "
                        "margin — rows flagged ⚠ have implausible margins and may need a rule adjustment.",
                        "结算价币种混合（马来西亚/印尼/吉尔吉斯斯坦/沙特/缅甸/越南为当地货币，墨西哥/斯里兰卡按产品判定，"
                        "其余为美元）。此表显示每个市场应用的币种及毛利率——带⚠的行毛利异常，可能需要调整规则。"),
                    ui.output_data_frame("settlement_audit_table"),
                    class_="data-table"
                ),
                ui.tags.hr(style="border-color:rgba(91,108,255,0.25); margin:24px 0 16px;"),
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(79,70,229,0.10),transparent);'
                    'border-left:4px solid #4F46E5;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:4px 0 14px;">'
                    '<span style="font-size:1.5em;">🇮🇶</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Iraq Pinstore — Supplier Purchase Planning</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '伊拉克 Pinstore — 供应商采购计划</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Weekly PIN demand &amp; stock-purchase estimation for the Pinstore supplier (Iraq).</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🇮🇶 Iraq Pinstore — Weekly Purchase Planner", "🇮🇶 伊拉克 Pinstore — 周采购计划",
                         _help("Covers AsiaCell PIN, Zain PIN, Korek PIN orders from Iraq. "
                               "B2C (Master): product name ends with 'PIN'. "
                               "B2B (Agent): product_info ends with 'PIN'. "
                               "Supplier: Pinstore (manual weekly purchase). Iraq has two suppliers: DT & Pinstore.")),
                    _bp("Estimate how many PINs to purchase this week and this month based on historical order trends.",
                        "根据历史订单趋势估算本周及本月需要向 Pinstore 采购的PIN数量。"),
                    ui.output_ui("iraq_pinstore_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Iraq PIN Weekly Order Trend (Last 12 Weeks)", "📊 伊拉克PIN订单周趋势（近12周）",
                         _help("Weekly order volume per PIN SKU. Red dashed line = 4-week rolling average total.")),
                    _bp("Track each PIN SKU's weekly demand. Seasonal spikes indicate upcoming high-demand periods.",
                        "追踪每个PIN SKU的每周需求量，季节性峰值提示即将到来的高需求期。"),
                    ui.output_ui("iraq_pinstore_trend_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🔥 Iraq Pinstore — Denomination × Operator Heatmap", "🔥 伊拉克 Pinstore — 面值 × 运营商热力图",
                         _help("Weekly order volume per operator × denomination combination (last 12 weeks). "
                               "Dark cells = high demand. Use to spot which denominations drive the most volume per operator.")),
                    _bp("Identify hot denominations per operator to prioritise purchase allocation.",
                        "识别每个运营商的热门面值，优先安排采购资金。"),
                    ui.output_ui("iraq_pinstore_denom_heatmap"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🛒 Iraq Pinstore — Stock Purchase Planner", "🛒 伊拉克 Pinstore — 备货采购计划",
                         _help("Pieces to buy per operator × denomination for the chosen stock horizon. "
                               "Pieces = recent daily velocity (last 28 days) × days × 1.10 safety buffer, "
                               "rounded up. Pick 1 or 2 weeks, or enter a custom number of days.")),
                    _bp("Pick how many days of stock you want to hold and read the pieces to purchase per "
                        "denomination per operator. Buffer: +10%. Detailed weekly/monthly estimates remain in the Excel download.",
                        "选择备货天数，直接读取每个运营商每个面值需采购的张数。安全缓冲+10%。详细的周/月估算仍可在Excel中下载。"),
                    ui.div(
                        ui.div(
                            ui.input_radio_buttons(
                                "pinstore_horizon", None,
                                choices={"7": "📅 1 Week (7d)", "14": "📅 2 Weeks (14d)",
                                         "custom": "✏️ Custom"},
                                selected="7", inline=True),
                            ui.panel_conditional(
                                "input.pinstore_horizon === 'custom'",
                                ui.input_numeric("pinstore_days", "Days of stock:",
                                                 value=10, min=1, max=60, width="160px"),
                            ),
                            style="display:flex; gap:16px; align-items:center; flex-wrap:wrap;"
                        ),
                        ui.download_button(
                            "download_iraq_pinstore_plan",
                            "⬇ Detailed Plan (Excel)",
                            class_="refresh-btn",
                            style=("background:#5B6CFF!important; color:white!important; "
                                   "border:none!important; padding:6px 14px!important; "
                                   "font-size:0.85em!important; width:auto!important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center; "
                              "margin-bottom:8px; flex-wrap:wrap; gap:10px;"
                    ),
                    ui.output_ui("pinstore_budget_note"),
                    ui.output_data_frame("pinstore_purchase_matrix"),
                    class_="data-table"
                ),
                _remarks_accordion("supplier_operator_performance"),
            ),
            ui.nav_panel(
                _bnav("Product & Denomination Analysis", "产品与面值"),
                ui.div(
                    ui.div(
                        ui.tags.span(
                            ui.tags.span("🏷️ Product Category Filter", class_="lang-en"),
                            ui.tags.span("🏷️ 产品类别筛选", class_="lang-zh"),
                            style="font-weight:600; color:#5B6CFF; font-size:0.95em;"
                        ),
                        ui.output_ui("product_type_filter_ui"),
                        ui.tags.small(
                            ui.tags.span("Filter all product charts on this page by product category.", class_="lang-en"),
                            ui.tags.span("按产品类别筛选本页所有图表。", class_="lang-zh"),
                            style="color:#64748B; font-size:0.8em;"
                        ),
                        style=("background:#EEF0FF; border:1px solid #C7D2FE; border-radius:10px; "
                               "padding:12px 16px; margin-bottom:12px;")
                    ),
                    ui.div(
                        ui.tags.span(
                            ui.tags.span("🏢 Operator Filter", class_="lang-en"),
                            ui.tags.span("🏢 运营商筛选", class_="lang-zh"),
                            style="font-weight:600; color:#5B6CFF; font-size:0.95em;"
                        ),
                        ui.output_ui("product_operator_filter_ui"),
                        ui.tags.small(
                            ui.tags.span("Leave empty to view all operators, or pick one/several to scope every chart on this page.", class_="lang-en"),
                            ui.tags.span("留空查看全部运营商，或选择一个/多个，以筛选本页所有图表。", class_="lang-zh"),
                            style="color:#64748B; font-size:0.8em;"
                        ),
                        style=("background:#EEF0FF; border:1px solid #C7D2FE; border-radius:10px; "
                               "padding:12px 16px; margin-bottom:12px;")
                    ),
                    class_="chart-container"
                ),
                # ══ Category Overview ═════════════════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(79,70,229,0.10),transparent);'
                    'border-left:4px solid #4F46E5;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:4px 0 14px;">'
                    '<span style="font-size:1.5em;">🗂️</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Product Category Overview (B2C)</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '产品类别总览 (B2C)</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'How each product line (airtime / data / e-wallet / bills) contributes to the business</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🗂️ Category KPIs", "🗂️ 类别核心指标"),
                    _bp("Top-line view of the product portfolio — which line drives revenue and which drives traffic.",
                        "产品组合的总览：哪个产品线贡献收入、哪个产品线带来流量。"),
                    ui.output_ui("category_overview_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Revenue & Orders by Product Category", "📊 各产品类别收入与订单量",
                         _help("Bars = revenue (GMV); line = order count. Categories come from the B2C catalogue "
                               "(充话费 airtime, 买流量 data, Touch'n Go, e-wallet, bills...).")),
                    _bp("Compare monetisation vs traffic per category — high-orders/low-revenue lines are engagement drivers, "
                        "high-revenue lines are monetisation engines.",
                        "对比各类别的变现与流量：订单多收入低的类别是引流款，收入高的类别是变现引擎。"),
                    ui.output_ui("category_revenue_orders_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Monthly Revenue Trend by Category (Top 6)", "📈 各类别月度收入趋势（前6）"),
                    _bp("Track how each product line grows or declines over time.",
                        "跟踪各产品线随时间的增长或下滑。"),
                    ui.output_ui("category_monthly_trend_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🌳 Product Revenue Mix (Treemap)", "🌳 产品收入结构（树图）",
                         _help("Hierarchical view sized by GMV. Larger = higher revenue contribution.")),
                    _bp("Visualise your product portfolio. Use to identify concentration risk and diversification opportunities.",
                        "一目了然地可视化产品组合，识别产品集中度风险及多元化机会。"),
                    ui.output_ui("product_treemap"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Top 5 Products — Revenue Trend", "📈 前5产品收入趋势",
                         _help("Month-over-month revenue for top 5 products. Declining = lifecycle maturity.")),
                    _bp("Track product revenue trajectories. Declining products may need promotion or indicate substitution.",
                        "追踪产品收入走势，下降产品可能需要促销支持或表明市场替代。"),
                    ui.output_ui("product_revenue_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Top Products by Revenue (GMV)", "📦 按收入排名产品 (GMV)"),
                    ui.output_ui("product_sales_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Top Products by Customer Segment", "📊 按客户分类的产品排名"),
                    _bp("Revenue per product split by B2B and B2C. Reveals channel-product affinity.",
                        "各产品按 B2B 和 B2C 分类的收入贡献，揭示渠道-产品亲和性。"),
                    ui.output_ui("product_segment_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💵 Recharge Denomination Band Revenue Contribution (%)", "💵 充值面值档位收入贡献率 (%)",
                         _help("Revenue by denomination band: Low (<10), Mid (10-50), High (>50) in base currency. "
                               "Airtime & Bill Payment only — denomination is the face value / bill amount.")),
                    _bp("Which face-value tier (Low/Mid/High) drives the most GMV? Filter to 'Airtime' or 'Bill' category for clean results.",
                        "哪个面值档位（低/中/高）贡献最多 GMV？筛选到'话费'或'账单'类别可获得更清晰的分析结果。"),
                    ui.output_ui("denomination_contribution_chart"),
                    class_="chart-container"
                ),
                # ── Data Package Volume Analysis ─────────────────────────
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(16,185,129,0.1),transparent);'
                    'border-left:4px solid #10B981;border-radius:0 8px 8px 0;'
                    'padding:10px 16px;margin:24px 0 16px;">'
                    '<span style="font-size:1.3em;">📶</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1em;color:#1E293B;">'
                    'Data Package Volume Analysis</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1em;color:#1E293B;">'
                    '数据流量套餐分析</div>'
                    '<div style="font-size:0.78em;color:#64748B;margin-top:1px;">'
                    'Orders & revenue by data size (MB/GB). Parsed from product names.</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("📶 Data Package Orders & Revenue by Volume", "📶 数据流量套餐订单量与收入（按流量大小）",
                         _help("Parses data volume (e.g. 500MB, 1GB, 2GB) from product names. "
                               "Packages must contain 'MB', 'GB', or 'TB' in the product name. "
                               "Filter to Data category using the product type filter above for cleaner results.")),
                    _bp("Understand which data package sizes drive the most orders and revenue. "
                        "High-volume small packs = price-sensitive market; large packs = high-value segment.",
                        "了解哪些流量套餐规格带来最多订单和收入。小包量大=价格敏感市场；大包量=高价值客群。"),
                    ui.output_ui("data_package_volume_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Data Package Revenue by Size Tier", "📊 数据流量套餐按大小档位收入分析",
                         _help("Groups data packages into tiers: Micro (<500MB), Small (500MB-2GB), "
                               "Mid (2-5GB), Large (5-20GB), Mega (20GB+). "
                               "Reveals which tier drives the most GMV.")),
                    _bp("Tier analysis guides inventory investment — focus on highest-GMV tiers for volume rebate negotiations.",
                        "档位分析指导库存投入方向，聚焦GMV最高档位开展量返谈判。"),
                    ui.output_ui("data_package_tier_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Data Package Orders by Operator × Volume Size", "📦 运营商 × 流量套餐规格订单分布",
                         _help("Stacked bar: each bar = one operator, segments = data package volume sizes. "
                               "Shows which operators sell which package sizes most.")),
                    _bp("Understand each operator's product mix by data volume — identify if they skew towards micro packs or large packs.",
                        "了解各运营商按流量大小的产品结构分布，识别其主打小流量包还是大流量包。"),
                    ui.output_ui("data_package_operator_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("📋 Data Package Sales Matrix — Operator × Package Size", "📋 流量套餐销售矩阵 — 运营商 × 套餐规格", style="margin: 0;"),
                        ui.download_button(
                            "download_data_package_matrix", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background:#5B6CFF !important; color:white !important; "
                                   "border:none !important; padding:6px 14px !important; "
                                   "font-size:0.85em !important; width:auto !important; margin:0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    _bp("Every data product's sales per operator per package size — the exact view for negotiating "
                        "package-level pricing with each operator.",
                        "每个运营商每个流量套餐规格的销量——与运营商谈套餐级价格的精确依据。"),
                    ui.output_data_frame("data_package_matrix_table"),
                    class_="data-table"
                ),
                # ── End of Data Package section ──────────────────────────
                # ══ Airtime / Top-up Denominations ════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(16,185,129,0.10),transparent);'
                    'border-left:4px solid #10B981;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:18px 0 14px;">'
                    '<span style="font-size:1.5em;">📱</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Airtime / Top-up Denomination Sales</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '话费充值面值销售分析</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Sales per denomination for airtime/top-up products (充话费 / 后付费 / PIN码话费)</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("💵 Airtime Sales by Denomination", "💵 话费各面值销量",
                         _help("Orders and revenue per denomination for airtime/top-up categories. "
                               "Labels use the SKU name (e.g. RM 50, 100000 Rp) when available.")),
                    _bp("Which face values customers actually buy — guides which denominations to stock and promote.",
                        "客户实际购买的面值分布——指导面值备货与促销重点。"),
                    ui.output_ui("airtime_denomination_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📡 Airtime Denomination × Operator", "📡 话费面值 × 运营商",
                         _help("Top denominations split by operator (brand). Shows which operator dominates each face value.")),
                    _bp("Identify operator ownership of each denomination — input for operator-level rebate talks.",
                        "识别各面值由哪个运营商主导——运营商级返点谈判依据。"),
                    ui.output_ui("airtime_denom_operator_chart"),
                    class_="chart-container"
                ),
                # ══ Peak Purchase Hours ═══════════════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(139,92,246,0.10),transparent);'
                    'border-left:4px solid #8B5CF6;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:18px 0 14px;">'
                    '<span style="font-size:1.5em;">⏰</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Peak Purchase Hours</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '购买高峰时段</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Which hour customers buy each denomination / data package, per operator (MYT, UTC+8)</div>'
                    '</div></div>'
                ),
                ui.div(
                    ui.div(
                        ui.div(
                            ui.tags.span(ui.tags.span("Operator", class_="lang-en"),
                                         ui.tags.span("运营商", class_="lang-zh"),
                                         style="font-weight:600;font-size:0.85em;color:#475569;"),
                            ui.output_ui("hourly_operator_selector_ui"),
                            style="flex:1; min-width:200px;"),
                        ui.div(
                            ui.tags.span(ui.tags.span("View", class_="lang-en"),
                                         ui.tags.span("视图", class_="lang-zh"),
                                         style="font-weight:600;font-size:0.85em;color:#475569;"),
                            ui.input_radio_buttons(
                                "hourly_view", None,
                                choices={"airtime": "💵 Airtime denominations",
                                         "data": "📶 Data packages"},
                                selected="airtime", inline=True),
                            style="flex:1; min-width:240px;"),
                        style="display:flex; gap:20px; flex-wrap:wrap; align-items:flex-start; margin-bottom:10px;"
                    ),
                    _bh3("⏰ Orders by Hour × Denomination / Package", "⏰ 各小时 × 面值/套餐订单量",
                         _help("Heatmap of order count by hour of day (0–23, MYT) for the selected operator. "
                               "Darker = more orders. Use it to time promotions and supplier top-ups.")),
                    _bp("Schedule campaigns and ensure stock/credit is loaded before each product's daily peak hour.",
                        "在每个产品的每日高峰时段前安排活动并确保库存/额度到位。"),
                    ui.output_ui("hourly_purchase_heatmap"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Peak Hour by Denomination / Package", "📋 各面值/套餐高峰时段"),
                    _bp("The single busiest hour for each item and how concentrated demand is in that hour.",
                        "每个商品最繁忙的单一时段，以及该时段需求的集中程度。"),
                    ui.output_data_frame("hourly_peak_table"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("🔢 Denomination × Operator Order Matrix", "🔢 面值 × 运营商订单矩阵",
                         _help("Heatmap of order volume per operator × denomination. Darker = more orders.")),
                    _bp("Operator-denomination ownership in specific markets — key input for inventory planning.",
                        "各市场运营商-面值归属分析，是库存规划和合同谈判的关键输入。"),
                    ui.output_ui("denomination_heatmap"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("💰 Revenue by Denomination × Operator", "💰 各运营商面值收入分布",
                         _help("Grouped bar: for each of the top 15 denominations, bars are grouped by operator. "
                               "Shows which operator drives revenue for each denomination.")),
                    _bp("Identify which operator owns each denomination in terms of GMV — key insight for supplier contract negotiations.",
                        "识别每个面值的GMV由哪个运营商主导，是供应商合同谈判的关键输入。"),
                    ui.output_ui("denomination_operator_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🔝 Top Recharge Denominations by Order Volume (All Operators)", "🔝 按订单量排名的充值面值（全运营商）"),
                    _bp("High-volume denominations are key to negotiating volume rebates.",
                        "高销量面值是谈判量返的关键杠杆。"),
                    ui.output_ui("top_denominations_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("📋 Denomination Performance Scorecard", "📋 面值绩效评分卡", style="margin: 0;"),
                        ui.download_button(
                            "download_denomination_scorecard", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background: #5B6CFF !important; color: white !important; "
                                   "border: none !important; padding: 6px 14px !important; "
                                   "font-size: 0.85em !important; width: auto !important; "
                                   "margin: 0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    ui.p("Sortable by Order Volume / Revenue (GMV) / Gross Margin — drill into "
                         "denomination-level profitability per operator.",
                         style="color:#64748B; font-size:0.88em; margin-top:8px;"),
                    ui.output_data_frame("denomination_scorecard"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("📋 Product Summary", "📋 产品汇总"),
                    ui.output_data_frame("product_summary_table"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("📡 Revenue by Product Category × Operator", "📡 产品类别 × 运营商收入分析",
                         _help("Revenue (GMV) split by product category (Data/Airtime/Bill) per operator. "
                               "Identifies which operators are strongest in each product line.")),
                    _bp("Understand each operator's product mix — which operators dominate Data vs Airtime vs Bill Payment.",
                        "了解各运营商的产品结构：哪个运营商在数据流量、话费充值、账单支付中各占优势。"),
                    ui.output_ui("operator_category_revenue_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📦 Order Volume by Product Category × Operator", "📦 产品类别 × 运营商订单量分析",
                         _help("Order volume split by product category per operator. "
                               "Reveals high-frequency operators vs high-value operators per category.")),
                    _bp("Compare order volume vs revenue per category to identify high-volume/low-value vs low-volume/high-value operators.",
                        "对比各类别订单量与收入，识别高频低值 vs 低频高值运营商。"),
                    ui.output_ui("operator_category_volume_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Operator × Product Category Pivot Table", "📋 运营商 × 产品类别汇总表",
                         _help("Full pivot: each row = operator, columns = product categories. "
                               "Shows Revenue (GMV), Orders, and AOV per cell. "
                               "Toggle between Revenue view and Orders view.")),
                    _bp("Comprehensive cross-reference of every operator by product type. Download as Excel for detailed analysis.",
                        "每个运营商按产品类别的完整交叉分析表。可下载为Excel进行详细分析。"),
                    ui.div(
                        ui.input_radio_buttons(
                            "op_cat_metric", None,
                            choices={"revenue": "💰 Revenue (GMV)", "orders": "📦 Orders", "aov": "💎 AOV"},
                            selected="revenue", inline=True,
                        ),
                        ui.download_button(
                            "download_op_category_pivot", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background:#5B6CFF !important; color:white !important; "
                                   "border:none !important; padding:6px 14px !important; "
                                   "font-size:0.85em !important; width:auto !important;")
                        ),
                        style="display:flex; gap:16px; align-items:center; margin-bottom:8px;"
                    ),
                    ui.output_data_frame("operator_category_pivot_table"),
                    class_="data-table"
                ),
                _remarks_accordion("product_denomination_analysis"),
            ),
            ui.nav_panel(
                _bnav("Customer Analytics", "客户分析"),
                # ══ B2B Agent Analytics section header ═══════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(91,108,255,0.12),transparent);'
                    'border-left:4px solid #5B6CFF;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:4px 0 18px;">'
                    '<span style="font-size:1.5em;">🏢</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'B2B Agent Analytics</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'B2B 代理商分析</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Agent performance · concentration risk · revenue contribution</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("🏢 B2B Performance Snapshot", "🏢 B2B 代理商绩效快照",
                         _help("Key B2B metrics for the selected period. "
                               "Active Agents = unique B2B user IDs with ≥1 order. "
                               "Top-3 Concentration = % of B2B GMV from top 3 agents.")),
                    _bp("Monitor B2B health: growing agent count = healthy acquisition; "
                        "Top-3 >70% = concentration risk.",
                        "监控B2B健康度：代理商数量增长=获客健康；前3占比>70%=集中度风险。"),
                    ui.output_ui("b2b_agent_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Top 20 B2B Agents by Revenue (GMV)", "📊 按收入排名前20代理商 (GMV)",
                         _help("Top 20 B2B agents by revenue in the selected period. "
                               "% shown is each agent's share of total B2B GMV.")),
                    _bp("High concentration in few agents = revenue dependency risk. Target inactive top agents for re-engagement.",
                        "高度集中在少数代理商=收入依赖风险，优先对不活跃的核心代理商开展再激活工作。"),
                    ui.output_ui("b2b_agent_revenue_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 B2B Agent Performance Table (Top 50)", "📋 B2B 代理商绩效表（前50）",
                         _help("Detailed B2B table: orders, revenue, AOV, revenue share, cumulative share. "
                               "Cumulative share shows how many agents drive the majority of B2B GMV.")),
                    _bp("Sorted by revenue. Cumulative share identifies concentration risk in your agent network.",
                        "按收入排序，累计占比识别代理商网络中的集中度风险。"),
                    ui.output_data_frame("agent_performance_table"),
                    class_="data-table"
                ),
                # ══ B2C Customer Analytics section header ════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(16,185,129,0.12),transparent);'
                    'border-left:4px solid #10B981;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:32px 0 18px;">'
                    '<span style="font-size:1.5em;">👥</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'B2C Customer Analytics</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'B2C 客户分析</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'Customer behaviour · churn risk · retention cohorts · acquisition analysis</div>'
                    '</div></div>'
                ),
                ui.div(
                    _bh3("👥 Customer KPIs (B2C)", "👥 客户核心指标（B2C）",
                         _help("Active Customers = unique user IDs with at least one order in the period. "
                               "ARPU = Average Revenue Per User (GMV ÷ Active Customers). "
                               "Repeat Purchase Rate = % of customers with 2+ orders. B2C segment only.")),
                    _bp("Core B2C customer health metrics: Active Customers, Repeat Purchase Rate, ARPU, Avg Orders per Customer.",
                        "B2C核心客户健康指标：活跃客户数、复购率、ARPU、客均订单数。"),
                    ui.output_ui("user_metrics"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⚠️ Customer Churn Risk Analysis (B2C)", "⚠️ 客户流失风险分析（B2C）",
                         _help("Based on days since each B2C customer's last order (all historical data). "
                               "Active = last order ≤30 days ago. "
                               "At Risk = last order 31-90 days ago — prime re-engagement window. "
                               "Lapsed = last order 91+ days ago — recovery campaign needed. "
                               "Revenue at risk = historical GMV from At-Risk customers.")),
                    _bp("Identify customers at different churn stages. "
                        "Focus marketing spend on At-Risk customers before they lapse.",
                        "识别不同流失阶段的客户，在高危客户完全流失前优先开展再激活营销。"),
                    ui.output_ui("b2c_churn_risk_panel"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⏱️ Registration → First Purchase Funnel (B2C)", "⏱️ 注册到首购漏斗（B2C）",
                         _help("Shows how quickly registered B2C customers make their first purchase. "
                               "Same Day = first order on the day of registration. "
                               "Within 7 Days, 8–30 Days, 31–90 Days = conversion windows. "
                               "No Purchase = registered users with no order on record.")),
                    _bp("Measure how fast new registrations convert. A long tail means acquisition → purchase friction needs attention.",
                        "衡量新注册用户首购转化速度。长尾说明注册到购买存在摩擦，需要优化引导流程。"),
                    ui.output_ui("b2c_registration_funnel"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🌐 IP Geographic Origin Analysis (B2C)", "🌐 IP来源地分析（B2C）",
                         _help("Compares the country of the order (from order data) vs. the country inferred from the customer's IP address. "
                               "Mismatches may indicate VPN use, cross-border shopping, or fraud signals. "
                               "Requires ip_country column in the data.")),
                    _bp("Identify geographic mismatches between order origin and IP location. High mismatch rates may signal VPN or fraud activity.",
                        "识别订单来源国家与IP归属地的差异。高错配率可能表明VPN使用或潜在欺诈活动。"),
                    ui.output_ui("b2c_ip_analysis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🔄 New vs. Returning Customers (B2C)", "🔄 新客 vs 老客（B2C）",
                         _help("New customers = first-ever order in the selected period. "
                               "Returning customers = had at least one prior order. "
                               "A healthy business typically sees >50% returning customers.")),
                    _bp("Customer loyalty indicator: a higher returning-customer share signals strong retention.",
                        "客户忠诚度指标：回购客户占比越高，说明留存能力越强。"),
                    ui.output_ui("new_vs_returning_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Monthly Customer Acquisition Rate (B2C)", "📈 每月新客户获取量（B2C）",
                         _help("Number of B2C customers placing their first-ever order in each month. "
                               "A consistent upward trend indicates healthy top-of-funnel growth.")),
                    _bp("Track how many new B2C customers are acquired each month. A flattening trend signals acquisition funnel issues.",
                        "跟踪每月B2C新客户获取量。趋势趋平或下滑意味着获客漏斗出现问题。"),
                    ui.output_ui("new_customer_acquisition_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 User Source Analysis (B2C)", "📊 渠道来源分析（B2C）",
                         _help("Breakdown of B2C customers by their acquisition source (用户来源). "
                               "Identify which channels bring the most customers and highest-value buyers.")),
                    _bp("Understand which acquisition channels (user source) drive volume vs. value for B2C customers.",
                        "了解哪些获客渠道（用户来源）为B2C客户带来量和价值的差异。"),
                    ui.output_ui("user_source_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🔗 Channel Performance (会员来源) — B2C", "🔗 渠道来源绩效（会员来源）— B2C",
                         _help("Normalized channel (会员来源) from the 用户列表, joined to orders by user — "
                               "the standard 渠道来源 dimension. Revenue per acquisition channel.")),
                    _bp("Revenue by normalized acquisition channel (会员来源) — the China-team 渠道来源 mapping.",
                        "按统一后的获客渠道（会员来源）划分的营业额 — 标准「渠道来源」口径。"),
                    ui.output_ui("channel_analysis_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Channel ROI Scorecard (会员来源)", "📋 渠道来源 ROI 评分卡",
                         _help("Per channel: GMV, orders, customers, new customers, coupon spend, "
                               "ROI (GMV ÷ coupon spend) and CAC (coupon spend ÷ new customers). B2C only.")),
                    _bp("Which acquisition channel returns the most per coupon-yuan spent (ROI), and what each new customer costs (CAC).",
                        "哪个获客渠道每投入1元优惠券带来的回报最高（ROI），以及每个新客的获取成本（CAC）。"),
                    ui.output_data_frame("channel_scorecard"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("📚 Customer Retention & CLV by Acquisition Cohort (B2C)", "📚 获客批次留存率与CLV（B2C）",
                         _help("An acquisition cohort is the group of customers whose first order was in a given month. "
                               "Rows = cohorts (acquisition month). Columns = months since first order. "
                               "Retention % shows what proportion of the cohort is still active.")),
                    _bp("B2C only. Cohort = month of first order. Switch between Retention Rate (%) and Cumulative CLV.",
                        "仅限B2C。批次 = 首次下单月份。可切换留存率(%)和累计CLV视图。"),
                    ui.output_ui("cohort_kpis"),
                    ui.input_radio_buttons(
                        "cohort_metric", None,
                        choices=["Retention %", "Cumulative LTV"],
                        selected="Retention %",
                        inline=True,
                    ),
                    ui.output_ui("cohort_heatmap"),
                    ui.output_ui("cohort_ltv_curves"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📊 Order Frequency Distribution (B2C)", "📊 下单频次分布（B2C）",
                         _help("Distribution of how many orders each B2C customer has placed. "
                               "A high proportion of 1-order customers indicates churn risk.")),
                    _bp("Understand B2C customer purchase behaviour: how many buy once vs. repeatedly?",
                        "了解B2C客户购买行为：一次性购买 vs 多次复购的分布。"),
                    ui.output_ui("user_order_freq_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Avg Orders per Customer by Segment", "📈 各客户分类客均订单数"),
                    _bp("Compares purchase frequency between B2B and B2C segments.",
                        "比较B2B与B2C客户分类的购买频次差异。"),
                    ui.output_ui("user_segment_order_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📋 Customer Summary (B2C)", "📋 客户汇总（B2C）"),
                    ui.output_data_frame("user_summary_table"),
                    class_="data-table"
                ),
                _remarks_accordion("customer_analytics"),
            ),
            # ── Marketing & Promotions Tab (B2C) ──────────────────────────
            ui.nav_panel(
                _bnav("Marketing & Promotions", "营销与促销"),
                ui.div(
                    _bh3("🎟️ Promotion KPIs (B2C)", "🎟️ 营销核心指标 (B2C)",
                         _help("Coupon usage, spend and effectiveness computed from "
                               "是否使用优惠券 / 优惠券名称 / 优惠券金额 / 是否新人优惠 / 是否角标产品.")),
                    _bp("How much you spend on promotions and what it buys — the marketing efficiency view.",
                        "促销投入与产出一览——营销效率视图。"),
                    ui.output_ui("marketing_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Monthly Coupon Spend vs Coupon-Order Revenue", "📈 月度优惠券支出 vs 券单收入",
                         _help("Bars = coupon discount spend (优惠券金额); line = GMV of orders that used a coupon. "
                               "A widening gap means promotions pay for themselves.")),
                    _bp("Promotion ROI over time — if coupon spend rises faster than coupon-order revenue, campaigns are losing efficiency.",
                        "促销ROI随时间变化——若券支出增速超过券单收入，说明活动效率在下降。"),
                    ui.output_ui("coupon_roi_trend_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("🏷️ Campaign Performance (Top Coupons)", "🏷️ 活动绩效（优惠券排名）", style="margin: 0;"),
                        ui.download_button(
                            "download_campaign_table", "⬇ Excel",
                            class_="refresh-btn",
                            style=("background:#5B6CFF !important; color:white !important; "
                                   "border:none !important; padding:6px 14px !important; "
                                   "font-size:0.85em !important; width:auto !important; margin:0 !important;")
                        ),
                        style="display:flex; justify-content:space-between; align-items:center;"
                    ),
                    _bp("Per-campaign orders, discount spend, revenue and average discount — find your best and worst coupons.",
                        "每个活动的订单、券支出、收入与平均折扣——找出最优与最差的优惠券。"),
                    ui.output_data_frame("campaign_performance_table"),
                    class_="data-table"
                ),
                ui.div(
                    _bh3("⚖️ Coupon vs Non-Coupon Customers", "⚖️ 用券 vs 未用券客户对比",
                         _help("AOV and repeat-purchase rate for customers who used coupons vs those who didn't.")),
                    _bp("The key question: do coupon customers come back? If repeat rate is no better than organic, coupons are buying one-off orders.",
                        "关键问题：用券客户会回购吗？若回购率不优于自然客户，优惠券只是买了一次性订单。"),
                    ui.output_ui("coupon_vs_noncoupon_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🆕 New-User Promo Orders by Month", "🆕 新人优惠订单月度趋势",
                         _help("Orders flagged 是否新人优惠 = 是. Tracks acquisition-promo volume over time.")),
                    _bp("Measures how much of your new-customer intake is promo-driven.",
                        "衡量新客获取中促销驱动的比例。"),
                    ui.output_ui("new_user_promo_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("⭐ Featured (Badge) Product Performance", "⭐ 角标产品绩效",
                         _help("Products flagged 是否角标产品 = 是 (highlighted in the app UI). "
                               "Compares revenue share and AOV vs non-featured products.")),
                    _bp("Merchandising effectiveness — does giving a product a badge actually move sales?",
                        "运营位效果——给产品加角标真的能带动销售吗？"),
                    ui.output_ui("badge_product_chart"),
                    class_="chart-container"
                ),
                _remarks_accordion("marketing_promotions"),
            ),
            # ── Sales Explorer Tab (ad-hoc time-window query) ─────────────
            ui.nav_panel(
                _bnav("⏱ Sales Explorer", "⏱ 时段销售查询"),
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(79,70,229,0.10),transparent);'
                    'border-left:4px solid #4F46E5;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:4px 0 14px;">'
                    '<span style="font-size:1.5em;">⏱</span>'
                    '<div>'
                    '<div class="lang-en" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    'Sales Explorer — query sales &amp; volume for any time window</div>'
                    '<div class="lang-zh" style="font-weight:700;font-size:1.08em;color:#1E293B;">'
                    '时段销售查询 — 任意时间窗口的销售与销量</div>'
                    '<div style="font-size:0.8em;color:#64748B;margin-top:2px;">'
                    'e.g. "what did Iraq sell last night, 20:00–06:00?" · self-contained filters · '
                    'compared against the previous equivalent window</div>'
                    '</div></div>'
                ),
                # ---- Filter card ----
                ui.div(
                    ui.div(
                        ui.div(_bl("Region", "地区"), ui.input_select(
                            "q_region", None, choices=region_choices, selected="All"),
                            style="flex:1; min-width:150px;"),
                        ui.div(_bl("Market (Country)", "市场（国家）"), ui.input_selectize(
                            "q_country", None, choices=_raw_country_choices, multiple=True,
                            options={"placeholder": "All countries — type to filter…"}),
                            style="flex:2; min-width:240px;"),
                        ui.div(_bl("Segment", "客户分类"), ui.input_select(
                            "q_segment", None,
                            choices={"All": "All", "B2B": "B2B", "B2C": "B2C"}, selected="All"),
                            style="flex:1; min-width:120px;"),
                        ui.div(_bl("Order Status", "订单状态"), ui.input_select(
                            "q_status", None, choices=ORDER_STATUS_CHOICES, selected="Successful"),
                            style="flex:1; min-width:160px;"),
                        style="display:flex; gap:14px; flex-wrap:wrap; margin-bottom:12px;"
                    ),
                    ui.div(
                        ui.div(_bl("From date", "起始日期"), ui.input_date(
                            "q_date_from", None, value=max_date,
                            min=min_date, max=max_date, format="yyyy-mm-dd"),
                            style="flex:1; min-width:150px;"),
                        ui.div(_bl("To date", "结束日期"), ui.input_date(
                            "q_date_to", None, value=max_date,
                            min=min_date, max=max_date, format="yyyy-mm-dd"),
                            style="flex:1; min-width:150px;"),
                        ui.div(_bl("Time window (MYT)", "时段（MYT）"), ui.input_radio_buttons(
                            "q_preset", None,
                            choices={"all": "🕓 Whole day", "night": "🌙 Night 20–06",
                                     "morning": "🌅 Morning 06–12", "biz": "🏢 Business 09–18",
                                     "custom": "✏ Custom"},
                            selected="all", inline=True),
                            style="flex:2; min-width:340px;"),
                        style="display:flex; gap:14px; flex-wrap:wrap; margin-bottom:12px; align-items:flex-start;"
                    ),
                    ui.panel_conditional(
                        "input.q_preset === 'custom'",
                        ui.div(
                            ui.div(_bl("From hour", "起始小时"), ui.input_select(
                                "q_hour_from", None,
                                choices={str(h): f"{h:02d}:00" for h in range(24)}, selected="0"),
                                style="flex:1; min-width:120px;"),
                            ui.div(_bl("To hour", "结束小时"), ui.input_select(
                                "q_hour_to", None,
                                choices={**{str(h): f"{h:02d}:00" for h in range(24)}, "24": "24:00"},
                                selected="24"),
                                style="flex:1; min-width:120px;"),
                            ui.tags.div(
                                ui.tags.span("Tip: set From > To for an overnight span (e.g. 20 → 06). "
                                             "Hours are MYT (UTC+8).",
                                             class_="lang-en"),
                                ui.tags.span("提示：起始>结束表示跨夜时段（如20→06）。时间为马来西亚时间(UTC+8)。",
                                             class_="lang-zh"),
                                style="flex:2; min-width:260px; color:#64748B; font-size:0.8em; align-self:center;"),
                            style="display:flex; gap:14px; flex-wrap:wrap; margin-bottom:12px;"
                        ),
                    ),
                    ui.div(
                        ui.div(_bl("Days of week", "星期"), ui.input_checkbox_group(
                            "q_dow", None,
                            choices={"0": "Mon", "1": "Tue", "2": "Wed", "3": "Thu",
                                     "4": "Fri", "5": "Sat", "6": "Sun"},
                            selected=["0", "1", "2", "3", "4", "5", "6"], inline=True),
                            style="flex:2; min-width:300px;"),
                        ui.div(_bl("Product type", "产品类型"), ui.input_radio_buttons(
                            "q_product_dim", None,
                            choices={"all": "All products", "data": "📶 Data packages",
                                     "airtime": "💵 Denominations (airtime)"},
                            selected="all", inline=True),
                            style="flex:2; min-width:300px;"),
                        style="display:flex; gap:14px; flex-wrap:wrap; margin-bottom:12px; align-items:flex-start;"
                    ),
                    ui.div(
                        ui.div(_bl("Operator", "运营商"), ui.output_ui("q_operator_ui"),
                               style="flex:1; min-width:240px;"),
                        ui.div(_bl("Specific package / denomination", "指定套餐 / 面值"),
                               ui.output_ui("q_product_value_ui"),
                               style="flex:1; min-width:240px;"),
                        style="display:flex; gap:14px; flex-wrap:wrap;"
                    ),
                    class_="chart-container"
                ),
                ui.div(
                    ui.output_ui("explorer_caption"),
                    _bh3("📊 Sales & Volume — Selected Window", "📊 所选时段销售与销量",
                         _help("Headline metrics for the filtered window, each compared against the "
                               "immediately-preceding equivalent window (same length, same hour band).")),
                    ui.output_ui("explorer_kpis"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🕐 Orders & Revenue by Hour (MYT)", "🕐 各小时订单与收入（MYT）"),
                    _bp("Order volume (bars) and GMV (line) by hour of day; the selected window is shaded.",
                        "各小时订单量（柱）与收入（线）；所选时段以阴影标示。"),
                    ui.output_ui("explorer_hourly_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("📈 Daily Trend Across the Date Range", "📈 日期区间内每日趋势"),
                    _bp("Orders and GMV per day within the window — compare several nights at a glance.",
                        "窗口内每日订单与收入，便于多晚对比。"),
                    ui.output_ui("explorer_daily_trend"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.div(
                        _bh3("📋 Breakdown", "📋 明细拆解", style="margin:0;"),
                        ui.div(
                            ui.input_select(
                                "q_groupby", None,
                                choices={"Operator": "By Operator", "Product": "By Product/Package",
                                         "Denomination": "By Denomination", "Country": "By Country",
                                         "Day": "By Day", "Hour": "By Hour", "DOW": "By Day-of-week"},
                                selected="Operator", width="200px"),
                            ui.download_button("download_explorer_xlsx", "⬇ Excel",
                                               class_="refresh-btn",
                                               style=("background:#5B6CFF !important; color:white !important; "
                                                      "border:none !important; padding:6px 14px !important; "
                                                      "font-size:0.85em !important; width:auto !important; margin:0 !important;")),
                            ui.download_button("download_explorer_csv", "⬇ CSV",
                                               class_="refresh-btn",
                                               style=("background:#0EA5E9 !important; color:white !important; "
                                                      "border:none !important; padding:6px 14px !important; "
                                                      "font-size:0.85em !important; width:auto !important; margin:0 !important;")),
                            style="display:flex; gap:10px; align-items:center;"
                        ),
                        style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;"
                    ),
                    _bp("Pivot the matched orders by any dimension — orders, GMV, margin, AOV and share.",
                        "按任意维度透视匹配订单——订单、收入、毛利、客单价与占比。"),
                    ui.output_data_frame("explorer_breakdown_table"),
                    class_="data-table"
                ),
                _remarks_accordion("sales_explorer"),
            ),
            # ── AI Predictions Tab ────────────────────────────────────────
            ui.nav_panel(
                _bnav("🤖 AI Predictions", "🤖 AI预测"),
                # ══ Revenue Forecasting ═══════════════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(16,185,129,0.12),transparent);'
                    'border-left:4px solid #10B981;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:4px 0 18px;">'
                    '<span style="font-size:1.5em;">📈</span>'
                    '<div><div style="font-weight:700;font-size:1.1em;color:#0F172A;">Revenue Forecasting</div>'
                    '<div style="font-size:0.85em;color:#64748B;">Multi-model weekly revenue prediction with confidence bands</div>'
                    '</div></div>'
                ),
                ui.div(
                    ui.div(
                        ui.input_radio_buttons(
                            "forecast_horizon", "Forecast Horizon:",
                            choices={"4": "4 Weeks", "8": "8 Weeks", "12": "12 Weeks"},
                            selected="8", inline=True,
                        ),
                        ui.input_action_button("run_revenue_forecast", "Generate Forecast",
                                               class_="btn btn-success btn-sm ms-3"),
                        style="display:flex; align-items:center; flex-wrap:wrap; gap:12px; margin-bottom:12px;"
                    ),
                    ui.output_ui("revenue_forecast_chart"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.output_ui("revenue_forecast_metrics"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.output_data_frame("revenue_forecast_table"),
                    class_="data-table"
                ),
                # ══ Customer Churn Prediction ═════════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(239,68,68,0.12),transparent);'
                    'border-left:4px solid #EF4444;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:24px 0 18px;">'
                    '<span style="font-size:1.5em;">🔮</span>'
                    '<div><div style="font-weight:700;font-size:1.1em;color:#0F172A;">Customer Churn Prediction (B2C)</div>'
                    '<div style="font-size:0.85em;color:#64748B;">Identify at-risk customers using ML classification</div>'
                    '</div></div>'
                ),
                ui.div(
                    ui.div(
                        ui.input_action_button("run_churn_model", "Run Churn Model",
                                               class_="btn btn-danger btn-sm"),
                        style="margin-bottom:12px;"
                    ),
                    ui.output_ui("churn_model_metrics"),
                    class_="chart-container"
                ),
                ui.div(
                    ui.output_ui("churn_feature_importance"),
                    class_="chart-container"
                ),
                ui.div(
                    _bh3("🎯 At-Risk Customers (Top 50)", "🎯 高流失风险客户（Top 50）",
                         _help("Customers ranked by predicted churn probability. "
                               "High Risk = >60% probability of churn. Prioritise for re-engagement campaigns.")),
                    ui.output_data_frame("churn_risk_table"),
                    class_="data-table"
                ),
                # ══ Product Demand Forecasting ════════════════════════════
                ui.HTML(
                    '<div style="display:flex;align-items:center;gap:12px;'
                    'background:linear-gradient(90deg,rgba(245,158,11,0.12),transparent);'
                    'border-left:4px solid #F59E0B;border-radius:0 8px 8px 0;'
                    'padding:12px 18px;margin:24px 0 18px;">'
                    '<span style="font-size:1.5em;">📦</span>'
                    '<div><div style="font-weight:700;font-size:1.1em;color:#0F172A;">Product Demand Forecasting</div>'
                    '<div style="font-size:0.85em;color:#64748B;">Weekly order volume forecast per operator × product (top 50 by volume)</div>'
                    '</div></div>'
                ),
                ui.div(
                    ui.div(
                        ui.input_action_button("run_demand_forecast", "Generate Demand Forecast",
                                               class_="btn btn-warning btn-sm text-dark"),
                        style="margin-bottom:12px;"
                    ),
                    ui.output_data_frame("demand_forecast_table"),
                    class_="data-table"
                ),
            ),
            ui.nav_panel(
                _bnav("📖 Guideline", "📖 使用指南"),
                *_guideline_children(),
            ),
        ),
        style="padding: 20px;"
    )
)



def server(input, output, session):
    import datetime as _dt
    import io as _io
    import re as _re_local

    # ---- Per-session fresh data load -----------------------------------
    # IMPORTANT: re-read the parquet here (not at module level) so each
    # new browser session sees disk-level changes (e.g. after Reload from
    # source) WITHOUT needing a Python restart. Cost: ~0.5s per session.
    session_data = load_data()
    if 'order_time' in session_data.columns and not session_data['order_time'].isna().all():
        session_min_date = session_data['order_time'].min().date()
        session_max_date = session_data['order_time'].max().date()
    else:
        session_min_date = min_date
        session_max_date = max_date

    # Reactive state for the data + meta
    data_rv = reactive.Value(session_data)
    min_date_rv = reactive.Value(session_min_date)
    max_date_rv = reactive.Value(session_max_date)
    import_message_rv = reactive.Value("Idle. Upload one or both files and click Process.")
    import_summary_rv = reactive.Value(db_utils.import_status())
    # Guard flag: True when a Quick-Period or Month-picker handler is the one
    # programmatically updating the date inputs. The date observer uses this
    # to know whether to clear the other date controls (user edit) or skip
    # (programmatic update -> avoid infinite loop).
    _programmatic_range_update = reactive.Value(False)

    # --- Applied filter state ------------------------------------------
    # The dashboard renders from these *applied* values. The user changes
    # the inputs freely; the Enter button copies the current input values
    # into the applied state, which is what triggers chart recompute.
    applied_segment = reactive.Value("All")
    applied_order_status = reactive.Value("Successful")
    applied_region = reactive.Value("All")
    applied_country = reactive.Value("All")
    applied_currency = reactive.Value("RMB")
    applied_trend_period = reactive.Value("Daily")
    applied_date_from = reactive.Value(session_min_date)
    applied_date_to = reactive.Value(session_max_date)
    applied_status_rv = reactive.Value("Showing all data (initial view)")

    # If the disk parquet has moved past what the module-level `data`
    # captured at startup, push the new dates into the widgets so the
    # date picker isn't pinned to a stale max_date.
    if (session_min_date is not None and session_max_date is not None and
            (session_min_date != min_date or session_max_date != max_date)):
        _programmatic_range_update.set(True)
        ui.update_date("date_from", value=session_min_date,
                       min=session_min_date, max=session_max_date, session=session)
        ui.update_date("date_to", value=session_max_date,
                       min=session_min_date, max=session_max_date, session=session)
        new_months = ["—"] + sorted(
            session_data['order_time'].dropna().dt.to_period('M').astype(str).unique().tolist()
        )
        ui.update_select("from_month", choices=new_months, selected="—", session=session)
        ui.update_select("to_month",   choices=new_months, selected="—", session=session)
        new_segs = ["All"] + sorted(session_data['segment'].dropna().astype(str).unique().tolist())
        new_ctrs = ["All"] + _clean_country_choices(session_data['country'])
        present = set(session_data['region'].dropna().astype(str).unique().tolist()) if 'region' in session_data.columns else set()
        new_regs = ["All"] + [r for r in T.REGION_ORDER if r in present]
        ui.update_select("segment", choices=new_segs, session=session)
        ui.update_select("region",  choices=new_regs, session=session)
        ui.update_selectize("country", choices=new_ctrs, session=session)

    @reactive.Effect
    @reactive.event(input.apply_btn, ignore_init=True)
    def apply_filters_action():
        """Copy the live inputs into the applied state. Charts re-render."""
        applied_segment.set(input.segment() or "All")
        applied_order_status.set(input.order_status_f() or "Successful")
        applied_region.set(input.region() or "All")
        applied_country.set(input.country() or "All")
        applied_currency.set(input.currency() or "RMB")
        applied_trend_period.set(input.trend_period() or "Daily")
        applied_date_from.set(input.date_from())
        applied_date_to.set(input.date_to())
        applied_status_rv.set(
            f"Applied at {_dt.datetime.now().strftime('%H:%M:%S')}"
        )

    @render.text
    def apply_status():
        return applied_status_rv()

    # ── Language-reactive sidebar labels ──────────────────────────────────────
    _LABELS = {
        "en": {
            "segment":      "Customer Segment",
            "order_status": "Order Status",
            "region":       "Region / Continent",
            "country":      "Market (Country)",
            "currency":     "Reporting Currency",
            "trend_period": "Reporting Period",
            "date_range":   "Date Range",
        },
        "zh": {
            "segment":      "客户分类",
            "order_status": "订单状态",
            "region":       "地区 / 洲",
            "country":      "市场（国家）",
            "currency":     "报告货币",
            "trend_period": "报告周期",
            "date_range":   "日期范围",
        },
    }

    def _L(key):
        lang = input.ui_lang() if hasattr(input, "ui_lang") else "en"
        return _LABELS.get(lang, _LABELS["en"]).get(key, key)

    def _is_zh():
        try:
            return (input.ui_lang() or "en") == "zh"
        except Exception:
            return False

    def _tt(text):
        """Translate a chart title / axis label / legend name when the UI
        language is Chinese. Reading input.ui_lang() makes every chart that
        calls this re-render on language switch."""
        if not _is_zh():
            return text
        return translate_chart_text(text)

    def _tdf(df):
        """Translate a display DataFrame's column headers for Chinese mode."""
        if df is None or not hasattr(df, "columns") or not _is_zh():
            return df
        out = df.copy()
        out.columns = [translate_chart_text(str(c)) for c in out.columns]
        return out

    @render.ui
    @safe_render
    def label_segment():
        return ui.h4(_L("segment"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_order_status():
        return ui.h4(_L("order_status"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_region():
        return ui.h4(_L("region"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_country():
        return ui.h4(_L("country"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_currency():
        return ui.h4(_L("currency"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_trend_period():
        return ui.h4(_L("trend_period"), style="margin-top:0;")

    @render.ui
    @safe_render
    def label_date_range():
        return ui.h4(_L("date_range"), style="margin-top:0;")

    # ── Key Countries management ───────────────────────────────────────────────
    _key_countries_msg = reactive.Value("")

    @reactive.Effect
    @reactive.event(input.save_key_countries)
    def _save_key_countries_handler():
        raw = input.key_countries_text() or ""
        lst = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        _save_key_countries(lst)
        _key_countries_msg.set(f"✓ Saved {len(lst)} countries")

    @render.text
    def key_countries_saved_msg():
        return _key_countries_msg()

    # ── Language switch: push lang attribute to <body> via JS ─────────────────
    # NOTE: session.send_custom_message is a coroutine and MUST be awaited —
    # a plain (sync) effect silently drops the message, which is why the
    # body[data-lang] attribute was never set and Chinese never appeared.
    @reactive.effect
    async def _apply_lang_body():
        lang = input.ui_lang()
        await session.send_custom_message("setDashLang", lang)

    # ── Market Intelligence page-level country comparison ─────────────────────
    @reactive.Calc
    def mi_filtered_data():
        df = filtered_data()
        compare = list(input.mi_compare_countries() or [])
        if compare:
            df = df[df['country'].astype(str).isin(compare)]
        return df

    # ── Product type page-level filter ────────────────────────────────────────
    # Stores the last *applied* selection (None = never clicked Apply = show all)
    _product_filter_applied = reactive.Value(None)

    @render.ui
    @safe_render
    def product_type_filter_ui():
        df = filtered_data()
        if 'product_category' in df.columns:
            cats = sorted(df['product_category'].dropna().astype(str).unique().tolist())
        else:
            cats = []
        if not cats:
            return ui.p("No product categories in current data.", style="color:#64748B; font-size:0.85em;")
        return ui.tags.div(
            ui.input_checkbox_group(
                "product_type_filter", None,
                choices={c: c for c in cats},
                selected=cats,
                inline=True,
            ),
            ui.input_action_button(
                "apply_product_filter", "Apply Filter",
                class_="btn btn-sm btn-primary mt-2",
                style="width:100%;",
            ),
        )

    @render.ui
    @safe_render
    def product_operator_filter_ui():
        """Operator selector for the Product & Denomination tab.
        Empty selection = all operators (the default)."""
        df = filtered_data()
        if 'operator' not in df.columns or df.empty:
            return ui.input_selectize("product_operator", None, choices=[], multiple=True,
                                      options={"placeholder": "All operators"})
        ops = (df['operator'].astype(str).replace({'': None}).dropna()
               .value_counts().head(60).index.tolist())
        return ui.input_selectize(
            "product_operator", None, choices=ops, multiple=True,
            options={"placeholder": "All operators — type to filter…"})

    def _apply_product_operator(df):
        """Scope a product-tab frame to the operator(s) chosen in the tab filter.
        Empty selection = all operators (returns df unchanged)."""
        if df is None:
            return df
        try:
            ops = list(input.product_operator() or [])
        except Exception:
            ops = []
        if ops and 'operator' in df.columns:
            df = df[df['operator'].astype(str).isin(ops)]
        return df

    @reactive.Effect
    @reactive.event(input.apply_product_filter)
    def _on_apply_product_filter():
        try:
            _product_filter_applied.set(list(input.product_type_filter() or []))
        except Exception:
            pass

    @reactive.Calc
    def product_type_filtered_data():
        df = _apply_product_operator(filtered_data())
        # Use last applied selection; fall back to raw input on initial load
        applied = _product_filter_applied()
        if applied is None:
            try:
                selected_types = list(input.product_type_filter() or [])
            except Exception:
                return df
        else:
            selected_types = applied
        if not selected_types:
            return df  # nothing selected = show all
        if 'product_category' in df.columns:
            all_cats = df['product_category'].dropna().astype(str).unique().tolist()
            if set(selected_types) != set(all_cats):
                df = df[df['product_category'].astype(str).isin(selected_types)]
        return df

    @render.ui
    @safe_render
    def staleness_banner():
        """Show a warning at the top when the source xlsx files are newer
        than the rolling database (i.e. user has edited source but not
        clicked Reload from source yet)."""
        s = db_utils.source_freshness()
        if not s["any_stale"]:
            return ui.HTML("")
        parts = []
        if s["agent_stale"]:
            parts.append(
                f"Agent Data.xlsx edited {s['source_agent_mtime'].strftime('%Y-%m-%d %H:%M')} "
                f"(rolling DB: {s['db_agent_mtime'].strftime('%Y-%m-%d %H:%M')})"
            )
        if s["master_stale"]:
            parts.append(
                f"Master Data.xlsx edited {s['source_master_mtime'].strftime('%Y-%m-%d %H:%M')} "
                f"(rolling DB: {s['db_master_mtime'].strftime('%Y-%m-%d %H:%M')})"
            )
        return ui.tags.div(
            ui.tags.div(
                ui.tags.span("⚠", style="font-size: 1.3em; margin-right: 10px; vertical-align: middle;"),
                ui.tags.span("Source xlsx is newer than the rolling database — dashboard is showing OLD data.",
                             style="font-weight: 700; color: #92400E;"),
                style="margin-bottom: 6px;"
            ),
            ui.tags.div(
                *[ui.tags.div("• " + p, style="margin-left: 28px;") for p in parts],
                style="color: #78350F; font-size: 0.88em;"
            ),
            ui.tags.div(
                ui.tags.span("→ Click ", style="color: #78350F; font-size: 0.88em;"),
                ui.tags.span("🔄 Reload from source xlsx", style="font-weight: 700; color: #92400E;"),
                ui.tags.span(" in the sidebar to apply your changes (takes 5–10 minutes).",
                             style="color: #78350F; font-size: 0.88em;"),
                style="margin-top: 8px; margin-left: 28px;"
            ),
            style=("background: linear-gradient(135deg, #FEF3C7 0%, #FED7AA 100%);"
                   "border: 1px solid #F59E0B; border-left: 5px solid #D97706;"
                   "padding: 14px 18px; margin: 10px; border-radius: 10px;"
                   "box-shadow: 0 2px 6px rgba(217, 119, 6, 0.15);")
        )

    # ------------------------------------------------------------------
    # Export helpers
    # ------------------------------------------------------------------
    def _safe_filename_part(s):
        s = "" if s is None else str(s)
        s = _re_local.sub(r"[^A-Za-z0-9_-]+", "_", s).strip("_")
        return s or "All"

    def _make_filename(prefix: str, ext: str) -> str:
        """Build a descriptive filename from the applied filters.

        e.g. supplier_scorecard_B2C_Iraq_2026-04-27_to_2026-05-10.xlsx
        """
        parts = [prefix]
        seg = applied_segment()
        reg = applied_region()
        ctr = applied_country()
        dfrom = applied_date_from()
        dto   = applied_date_to()
        if seg and seg != "All": parts.append(_safe_filename_part(seg))
        if reg and reg != "All": parts.append(_safe_filename_part(reg))
        if ctr and ctr != "All": parts.append(_safe_filename_part(ctr))
        if dfrom and dto:
            parts.append(f"{dfrom}_to_{dto}")
        elif dfrom:
            parts.append(str(dfrom))
        return f"{'_'.join(parts)}.{ext}"

    def _xlsx_bytes(df, sheet_name="Data") -> bytes:
        """Encode a DataFrame as xlsx bytes using xlsxwriter (fast)."""
        buf = _io.BytesIO()
        if df is None or df.empty:
            df = pd.DataFrame({"info": ["No data for the current filter selection"]})
        sheet_name = _re_local.sub(r"[\\/*\[\]:?]", "_", str(sheet_name))[:31] or "Data"
        with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
            df.to_excel(writer, index=False, sheet_name=sheet_name)
        return buf.getvalue()

    def _csv_bytes(df) -> bytes:
        """Encode a DataFrame as CSV with UTF-8 BOM (so Excel handles Chinese)."""
        if df is None or df.empty:
            df = pd.DataFrame({"info": ["No data for the current filter selection"]})
        return df.to_csv(index=False).encode("utf-8-sig")

    @render.download(filename=lambda: _make_filename("filtered_data", "csv"))
    def download_filtered_csv():
        yield _csv_bytes(filtered_data())

    @render.download(filename=lambda: _make_filename("filtered_data", "xlsx"))
    def download_filtered_xlsx():
        df = filtered_data()
        # Excel can't handle a single sheet > ~1.05M rows. Clip with a notice.
        if df is not None and len(df) > 1_000_000:
            df = df.head(1_000_000).copy()
            # Add a footer note via a second sheet
            buf = _io.BytesIO()
            note = pd.DataFrame({"note": [
                f"Source row count exceeded 1,000,000. First 1,000,000 rows exported.",
                "Use the CSV download for the complete view."
            ]})
            with pd.ExcelWriter(buf, engine="xlsxwriter") as writer:
                df.to_excel(writer, index=False, sheet_name="Data")
                note.to_excel(writer, index=False, sheet_name="Notes")
            yield buf.getvalue()
        else:
            yield _xlsx_bytes(df, sheet_name="Filtered_Data")

    def _refresh_filter_choices(new_data):
        """Re-populate sidebar dropdowns from the latest dataset, and reset
        the applied state so the dashboard renders the freshly-loaded data."""
        new_segs = ["All"] + sorted(new_data['segment'].dropna().astype(str).unique().tolist())
        new_ctrs = ["All"] + _clean_country_choices(new_data['country'])
        present = set(new_data['region'].dropna().astype(str).unique().tolist()) if 'region' in new_data.columns else set()
        new_regs = ["All"] + [r for r in T.REGION_ORDER if r in present]
        ui.update_select("segment", choices=new_segs, session=session)
        ui.update_select("region", choices=new_regs, session=session)
        ui.update_selectize("country", choices=new_ctrs, session=session)

        # Reset applied filter state to defaults — Enter is no longer needed
        # to see the just-imported rows.
        applied_segment.set("All")
        applied_region.set("All")
        applied_country.set("All")

        if 'order_time' in new_data.columns and not new_data['order_time'].isna().all():
            new_min = new_data['order_time'].min().date()
            new_max = new_data['order_time'].max().date()
            min_date_rv.set(new_min)
            max_date_rv.set(new_max)
            _programmatic_range_update.set(True)
            ui.update_date("date_from", value=new_min, min=new_min, max=new_max, session=session)
            ui.update_date("date_to",   value=new_max, min=new_min, max=new_max, session=session)
            applied_date_from.set(new_min)
            applied_date_to.set(new_max)
            new_months = ["—"] + sorted(
                new_data['order_time'].dropna().dt.to_period('M').astype(str).unique().tolist()
            )
            ui.update_select("from_month", choices=new_months, selected="—", session=session)
            ui.update_select("to_month", choices=new_months, selected="—", session=session)
        applied_status_rv.set(
            f"Reset after import at {_dt.datetime.now().strftime('%H:%M:%S')} — showing all data"
        )

    # ------------------------------------------------------------------
    # Import Data section
    # ------------------------------------------------------------------
    @reactive.Effect
    @reactive.event(input.import_btn)
    def handle_import():
        try:
            agent_files = input.agent_upload()
            master_files = input.master_upload()
            if not agent_files and not master_files:
                import_message_rv.set(
                    "⚠ Please choose at least one file (Agent or Master) before clicking Process."
                )
                return

            results = []
            archive_lines = []
            import_message_rv.set("⏳ Reading uploaded file(s) and updating the rolling parquet stores... usually well under a minute.")

            if agent_files:
                info = agent_files[0]
                apath = Path(info['datapath'])
                original_name = info.get('name') or apath.name
                archived = db_utils.archive_upload(apath, db_utils.AGENT_ARCHIVE_DIR, original_name)
                renamed = (archived.name != original_name)
                archive_lines.append(
                    f"📁 Agent → {archived.name}"
                    + (f"  (renamed from '{original_name}' to avoid overwriting an existing file)"
                       if renamed else "")
                )
                df = db_utils._read_data_file(apath)
                r = db_utils.append_agent(df)
                r['filename'] = original_name
                results.append(r)
            if master_files:
                info = master_files[0]
                mpath = Path(info['datapath'])
                original_name = info.get('name') or mpath.name
                archived = db_utils.archive_upload(mpath, db_utils.MASTER_ARCHIVE_DIR, original_name)
                renamed = (archived.name != original_name)
                archive_lines.append(
                    f"📁 Master → {archived.name}"
                    + (f"  (renamed from '{original_name}' to avoid overwriting an existing file)"
                       if renamed else "")
                )
                df = db_utils._read_data_file(mpath)
                r = db_utils.append_master(df)
                r['filename'] = original_name
                results.append(r)

            new_data = load_data()
            data_rv.set(new_data)
            _refresh_filter_choices(new_data)
            import_summary_rv.set(db_utils.import_status())

            lines = []
            for r in results:
                lines.append(
                    f"✅ {r['filename']}: +{r['added']:,} new rows, "
                    f"{r['duplicates']:,} duplicates skipped, "
                    f"total now {r['total_rows']:,} rows ({r['elapsed_seconds']}s)"
                )
                if r.get('date_min'):
                    lines.append(f"   📅 Batch covers {r['date_min']} → {r['date_max']}")
                if r.get('missing_expected'):
                    lines.append(
                        f"   ❌ Missing expected columns: {', '.join(r['missing_expected'])} — "
                        f"check that you uploaded the right file."
                    )
                if r.get('unknown_columns'):
                    lines.append(
                        f"   🆕 New columns detected: {', '.join(r['unknown_columns'])} — "
                        f"stored in the database but not yet used by the dashboard."
                    )
            if archive_lines:
                lines.extend([""] + archive_lines)
            import_message_rv.set("\n".join(lines))
        except Exception as exc:
            import_message_rv.set(f"❌ Import failed: {exc}")

    # ------------------------------------------------------------------
    # Quick refresh from disk (re-read parquet, <1s)
    # ------------------------------------------------------------------
    @reactive.Effect
    @reactive.event(input.refresh_disk_btn, ignore_init=True)
    def handle_refresh_disk():
        try:
            t0 = _dt.datetime.now()
            new_data = load_data()
            data_rv.set(new_data)
            _refresh_filter_choices(new_data)
            import_summary_rv.set(db_utils.import_status())
            elapsed = (_dt.datetime.now() - t0).total_seconds()
            max_dt = new_data['order_time'].max() if 'order_time' in new_data.columns else None
            max_dt_str = max_dt.strftime('%Y-%m-%d %H:%M') if max_dt is not None else "—"
            import_message_rv.set(
                f"✅ Refreshed from disk at {_dt.datetime.now().strftime('%H:%M:%S')}\n"
                f"   {len(new_data):,} rows loaded ({elapsed:.1f}s)\n"
                f"   Latest order_time: {max_dt_str}"
            )
        except Exception as exc:
            import_message_rv.set(f"❌ Refresh from disk failed: {exc}")

    # ------------------------------------------------------------------
    # Reload from source xlsx (Master Data.xlsx + Agent Data.xlsx)
    # ------------------------------------------------------------------
    @reactive.Effect
    @reactive.event(input.reload_source_btn, ignore_init=True)
    def handle_reload_source():
        progress_lines = []

        def _say(msg):
            progress_lines.append(msg)
            # Note: Shiny doesn't push interim status mid-handler reliably,
            # so the user sees the full log after completion.

        try:
            import_message_rv.set(
                "⏳ Reloading from source xlsx files (Master Data.xlsx + Agent Data.xlsx) ...\n"
                "This typically takes 5–10 minutes. Do NOT close the browser tab.\n"
                "The dashboard will refresh automatically when done."
            )
            t0 = _dt.datetime.now()
            result = db_utils.rebuild_from_source(progress_callback=_say)

            # Re-load the data into the live dashboard
            new_data = load_data()
            data_rv.set(new_data)
            _refresh_filter_choices(new_data)
            import_summary_rv.set(db_utils.import_status())

            elapsed = (_dt.datetime.now() - t0).total_seconds()
            summary_lines = [
                f"✅ Source xlsx reloaded successfully at {_dt.datetime.now().strftime('%H:%M:%S')}",
                "",
                f"📥 Agent  ({db_utils.SOURCE_AGENT.name}): {result['agent_rows']:,} rows",
                f"📥 Master ({db_utils.SOURCE_MASTER.name}): {result['master_rows']:,} rows",
                f"⏱  Total: {elapsed:.0f}s",
                "",
                "Step log:",
            ] + [f"  • {ln}" for ln in progress_lines]
            try:
                import pyarrow.parquet as _pq
                available = set(_pq.ParquetFile(db_utils.CACHE_PARQUET).schema_arrow.names)
                unused = sorted(available - set(DASHBOARD_COLUMNS) - {'segment'})
                if unused:
                    summary_lines += ["", f"ℹ Cache columns not yet used by the dashboard: {', '.join(unused)}"]
            except Exception:
                pass
            import_message_rv.set("\n".join(summary_lines))
        except FileNotFoundError as exc:
            import_message_rv.set(
                f"❌ Reload failed — source file not found:\n{exc}\n\n"
                f"Expected files:\n"
                f"  • {db_utils.SOURCE_AGENT}\n"
                f"  • {db_utils.SOURCE_MASTER}"
            )
        except Exception as exc:
            import_message_rv.set(f"❌ Reload failed: {exc}")

    @reactive.Effect
    @reactive.event(input.export_excel_btn, ignore_init=True)
    def handle_export_excel():
        try:
            import_message_rv.set(
                "⏳ Writing Excel backup files from the rolling parquet stores...\n"
                "This can take a few minutes for 1M+ rows."
            )
            r = db_utils.export_excel_backup()
            import_message_rv.set(
                f"✅ Excel backups written at {_dt.datetime.now().strftime('%H:%M:%S')}\n"
                f"   Agent_Database.xlsx: {r['agent_rows']:,} rows\n"
                f"   Master_Database.xlsx: {r['master_rows']:,} rows\n"
                f"   ⏱ {r['elapsed_sec']}s"
            )
        except Exception as exc:
            import_message_rv.set(f"❌ Excel export failed: {exc}")

    @render.ui
    @safe_render
    def import_status_ui():
        msg = import_message_rv()
        s = import_summary_rv()
        lines = str(msg).split("\n")
        # Combined status panel for the sidebar
        return ui.div(
            *[ui.div(ln, style="margin-bottom: 4px;") for ln in lines],
            ui.tags.hr(style="border-color: rgba(255,255,255,0.2); margin: 8px 0;"),
            ui.div(
                ui.div(f"Agent rows: {s['agent_rows']:,}", style="color: rgba(255,255,255,0.85);"),
                ui.div(f"Master rows: {s['master_rows']:,}", style="color: rgba(255,255,255,0.85);"),
                ui.div(f"Cache: {'✓' if s['cache_exists'] else '✗'}", style="color: rgba(255,255,255,0.85);"),
            ),
        )

    # ------------------------------------------------------------------
    # Month picker -> updates the Custom Range. As soon as both From Month
    # and To Month are picked, the Custom Range below snaps to span them.
    # The Quick Period dropdown is reset so it doesn't appear stuck on a
    # stale value.
    # ------------------------------------------------------------------
    @reactive.Effect
    @reactive.event(input.from_month, input.to_month)
    def update_range_from_months():
        from datetime import date
        from calendar import monthrange
        fm = input.from_month()
        tm = input.to_month()
        if not fm or not tm or fm == "—" or tm == "—":
            return
        try:
            fy, fmm = map(int, fm.split("-"))
            ty, tmm = map(int, tm.split("-"))
            if (fy, fmm) > (ty, tmm):
                fy, fmm, ty, tmm = ty, tmm, fy, fmm
            start = date(fy, fmm, 1)
            end = date(ty, tmm, monthrange(ty, tmm)[1])
            with reactive.isolate():
                min_d = min_date_rv()
                max_d = max_date_rv()
            if min_d:
                start = max(start, min_d)
            if max_d:
                end = min(end, max_d)
            # Reset Quick Period so the UI stays consistent
            with reactive.isolate():
                if input.quick_period() and input.quick_period() != "—":
                    ui.update_select("quick_period", selected="—", session=session)
            _programmatic_range_update.set(True)
            ui.update_date("date_from", value=start, session=session)
            ui.update_date("date_to",   value=end,   session=session)
        except Exception:
            pass

    # When the user edits the From/To dates directly, reset the higher-level
    # selectors so the UI doesn't show a stale "Today" / "From Month=2024-01"
    # tag while the actual filter says something else.
    @reactive.Effect
    @reactive.event(input.date_from, input.date_to)
    def date_range_user_edit():
        with reactive.isolate():
            if _programmatic_range_update():
                _programmatic_range_update.set(False)
                return
            qp = input.quick_period()
            fm = input.from_month()
            tm = input.to_month()
        if qp and qp != "—":
            ui.update_select("quick_period", selected="—", session=session)
        if fm and fm != "—":
            ui.update_select("from_month", selected="—", session=session)
        if tm and tm != "—":
            ui.update_select("to_month", selected="—", session=session)

    @reactive.Effect
    @reactive.event(input.quick_period)
    def update_range_from_quick_period():
        """Quick Period dropdown -> Custom Range. Resets the month picker."""
        from datetime import timedelta
        qp = input.quick_period()
        if not qp or qp == "—":
            return
        with reactive.isolate():
            max_d = max_date_rv()
            min_d = min_date_rv()
        if max_d is None:
            return

        if qp == "Today":
            start = end = max_d
        elif qp == "Yesterday":
            start = end = max_d - timedelta(days=1)
        elif qp == "Past 7 Days":
            end = max_d
            start = max_d - timedelta(days=7)
        elif qp == "This Month":
            end = max_d
            start = max_d.replace(day=1)
        elif qp == "This Year":
            end = max_d
            start = max_d.replace(month=1, day=1)
        elif qp == "All Time":
            start = min_d if min_d else max_d
            end = max_d
        else:
            return

        # Clear the month picker so it doesn't visually conflict.
        ui.update_select("from_month", selected="—", session=session)
        ui.update_select("to_month", selected="—", session=session)
        _programmatic_range_update.set(True)
        ui.update_date("date_from", value=start, session=session)
        ui.update_date("date_to",   value=end,   session=session)
    
    @reactive.Calc
    def filtered_base_calc():
        """Segment/region/country/date filters — WITHOUT the order-status
        filter, so the Order Status analytics section can still see
        refunded/cancelled orders. Core metrics drop 电子钱包 / Touch'n Go."""
        df = _apply_global_exclusions(data_rv().copy())
        segment = applied_segment()
        region = applied_region() if 'region' in df.columns else None
        country = applied_country()
        date_from = applied_date_from()
        date_to   = applied_date_to()

        if segment and segment != "All":
            df = df[df['segment'] == segment]
        if region and region != "All" and 'region' in df.columns:
            df = df[df['region'] == region]
        df = _filter_by_country(df, country)
        if date_from and date_to and 'order_time' in df.columns:
            start = pd.to_datetime(date_from, errors='coerce')
            end   = pd.to_datetime(date_to,   errors='coerce')
            if pd.notna(start) and pd.notna(end):
                if start > end:
                    start, end = end, start
                start = start.date()
                end   = end.date()
                df = df[(df['order_time'].dt.date >= start) &
                        (df['order_time'].dt.date <= end)]
        return df

    @reactive.Calc
    def filtered_data_calc():
        return filter_by_order_status(filtered_base_calc(), applied_order_status())

    def filtered_data():
        return filtered_data_calc()
    
    @reactive.Calc
    def previous_period_base():
        df = _apply_global_exclusions(data_rv().copy())
        segment = applied_segment()
        region = applied_region() if 'region' in df.columns else None
        country = applied_country()
        date_from = applied_date_from()
        date_to   = applied_date_to()

        if segment and segment != "All":
            df = df[df['segment'] == segment]
        if region and region != "All" and 'region' in df.columns:
            df = df[df['region'] == region]
        df = _filter_by_country(df, country)
        if date_from and date_to and 'order_time' in df.columns:
            start = pd.to_datetime(date_from, errors='coerce')
            end   = pd.to_datetime(date_to,   errors='coerce')
            if pd.notna(start) and pd.notna(end):
                if start > end:
                    start, end = end, start
                period_length = end - start
                prev_end = start
                prev_start = prev_end - period_length
                start = prev_start.date()
                end   = prev_end.date()
                df = df[(df['order_time'].dt.date >= start) &
                        (df['order_time'].dt.date < end)]
        return df

    @reactive.Calc
    def previous_period_data():
        return filter_by_order_status(previous_period_base(), applied_order_status())

    def _resolve_currency(currency, country, as_of=None):
        """Return the currency descriptor dict given the choice + country.

        For Local Currency: looks up the country in fx_rates.COUNTRY_CURRENCY.
        If the country is 'All' or unknown, falls back to RMB and flags it.
        """
        if currency == "RMB":
            return {"symbol": "¥", "rate": 1.0, "label": "RMB",
                    "is_local": False, "fallback": False}
        if currency == "USD":
            return {"symbol": "$", "rate": 1.0 / exchange_rate, "label": "USD",
                    "is_local": False, "fallback": False}
        if currency == "Local Currency":
            info = fx_rates.lookup(country, as_of) if (country and country != "All") else None
            if info:
                sym, code, rate = info
                # Trailing space so values render as "RM 12,345" not "RM12,345"
                return {"symbol": f"{sym} ", "rate": float(rate), "label": code,
                        "is_local": True, "fallback": False, "fx_as_of": fx_rates.RATES_AS_OF}
            # Fallback: country=All or country has no entry
            return {"symbol": "¥", "rate": 1.0, "label": "RMB",
                    "is_local": False, "fallback": True}
        # Unknown — default to RMB
        return {"symbol": "¥", "rate": 1.0, "label": "RMB",
                "is_local": False, "fallback": False}

    @reactive.Calc
    def currency_converter():
        dto = applied_date_to()
        as_of = None
        if dto:
            try:
                as_of = pd.to_datetime(dto, errors='coerce').strftime('%Y-%m')
            except Exception:
                as_of = None
        return _resolve_currency(applied_currency(), applied_country(), as_of)

    @render.ui
    @safe_render
    def currency_status_badge():
        """Small badge below the Currency radio buttons showing the active
        currency. Especially useful when 'Local Currency' is selected so the
        user knows exactly which local FX is being applied (or that it fell
        back to RMB because Country = All)."""
        c = currency_converter()
        # Only show when Local is chosen so we don't crowd the sidebar
        if applied_currency() != "Local Currency":
            return ui.HTML("")
        if c["fallback"]:
            return ui.tags.div(
                "⚠ No country selected — showing RMB. "
                "Pick a Country (e.g. Malaysia) to see local-currency values.",
                style=("background: rgba(245, 158, 11, 0.25);"
                       "border-left: 3px solid #F59E0B;"
                       "padding: 6px 10px; border-radius: 4px;"
                       "font-size: 0.75em; color: white; margin-top: 6px;")
            )
        as_of = c.get("fx_as_of")
        as_of_txt = f" · rates as of {as_of}" if as_of else ""
        return ui.tags.div(
            f"Showing in {c['label']} ({c['symbol'].strip()}){as_of_txt}",
            style=("background: rgba(16, 185, 129, 0.30);"
                   "border-left: 3px solid #10B981;"
                   "padding: 6px 10px; border-radius: 4px;"
                   "font-size: 0.78em; color: white; font-weight: 600; margin-top: 6px;")
        )

    @render.ui
    @safe_render
    def sidebar_freshness_badge():
        df = data_rv()
        if 'order_time' not in df.columns or df.empty:
            return ui.HTML('')
        latest = df['order_time'].dropna().max()
        if pd.isna(latest):
            return ui.HTML('')
        days_ago = (pd.Timestamp.now() - latest).days
        color = '#10B981' if days_ago <= 1 else ('#F59E0B' if days_ago <= 3 else '#EF4444')
        dot_label = 'Fresh' if days_ago <= 1 else (f'{days_ago}d old' if days_ago <= 7 else f'{days_ago}d old ⚠')
        built = db_utils.cache_mtime()
        built_line = (f'<span style="color:rgba(255,255,255,0.65);">cache built '
                      f'{built.strftime("%d %b %H:%M")}</span><br>') if built else ''
        warn_line = ''
        if days_ago >= 2:
            warn_line = ('<span style="color:#FCA5A5;">⚠ Upload the latest daily files '
                         'in the Import tab</span><br>')
        return ui.HTML(
            f'<div style="background:rgba(0,0,0,0.18); border-radius:6px; padding:5px 10px; '
            f'font-size:0.77em; color:rgba(255,255,255,0.9); margin-bottom:8px; text-align:center;">'
            f'📅 Data as of <b>{latest.strftime("%d %b %Y")}</b><br>'
            f'{built_line}{warn_line}'
            f'<span style="color:{color}; font-weight:600;">● {dot_label}</span>'
            f'</div>'
        )

    def _bl(en: str, zh: str):
        """Bilingual inline label — responds to body[data-lang] CSS toggle."""
        return ui.HTML(f'<span class="lang-en">{en}</span><span class="lang-zh">{zh}</span>')

    def _kpi_card(icon, icon_class, label, value, delta_pct, sub_text, tooltip):
        """Build a single KPI card with consistent styling and delta colour."""
        delta_str = T.format_pct(delta_pct) if delta_pct is not None else "—"
        delta_color = T.delta_color(delta_pct)
        delta_arrow = "▲" if delta_pct and delta_pct > 0 else ("▼" if delta_pct and delta_pct < 0 else "▬")
        return ui.tags.div(
            ui.tags.div(icon, class_=f"metric-icon {icon_class}"),
            ui.tags.h4(label),
            ui.tags.p(value),
            ui.tags.small(
                f"{delta_arrow} {delta_str} vs prev period" if delta_pct is not None else "—",
                style=f"color: {delta_color}; font-weight: 600;"
            ),
            ui.tags.div(
                ui.tags.small(sub_text, style="color: #64748B;"),
                title=tooltip
            ),
            class_="metric-card",
            style="flex: 1 1 23%; min-width: 220px; max-width: 23%;"
        )

    # ------------------------------------------------------------------
    # Phase 1 — "Knowing what to act on"
    #
    # Smart alerts: slipping / surging / new operators + countries, plus a
    # "what changed this week" digest. These respect segment + region +
    # country filters but always anchor on the LATEST data (ignore the
    # applied date range) — exec wants to know what's happening *now*.
    # ------------------------------------------------------------------
    @reactive.Calc
    def alerts_data():
        df = data_rv()
        if 'order_time' not in df.columns or df.empty:
            return None

        # Apply non-date filters
        seg = applied_segment()
        reg = applied_region()
        ctr = applied_country()
        if seg and seg != "All":
            df = df[df['segment'] == seg]
        if 'region' in df.columns and reg and reg != "All":
            df = df[df['region'] == reg]
        df = _filter_by_country(df, ctr)
        if df.empty:
            return None

        currency = currency_converter()
        rate = currency['rate']
        sym = currency['symbol']

        max_date = df['order_time'].max().normalize()
        recent_start   = max_date - pd.Timedelta(days=7)
        prev_start     = max_date - pd.Timedelta(days=14)
        baseline_start = max_date - pd.Timedelta(days=35)
        long_start     = max_date - pd.Timedelta(days=90)

        recent   = df[df['order_time'] >= recent_start]
        prev_wk  = df[(df['order_time'] >= prev_start) & (df['order_time'] < recent_start)]
        baseline = df[(df['order_time'] >= baseline_start) & (df['order_time'] < recent_start)]
        longwin  = df[df['order_time'] >= long_start]

        def _movers(level: str):
            if level not in df.columns:
                return pd.DataFrame()
            r = recent.groupby(level, observed=True)['sales'].sum().mul(rate)
            b = baseline.groupby(level, observed=True)['sales'].sum().mul(rate) / 4.0  # weekly average
            idx = sorted(set(r.index.astype(str)) | set(b.index.astype(str)))
            out = pd.DataFrame({
                'entity':   idx,
                'recent':   [float(r.get(e, 0.0)) for e in idx],
                'baseline': [float(b.get(e, 0.0)) for e in idx],
            })
            out['delta'] = out['recent'] - out['baseline']
            base_safe = out['baseline'].replace(0, np.nan)
            out['pct'] = (out['delta'] / base_safe) * 100.0
            return out

        op_m = _movers('operator')
        co_m = _movers('country')

        # Significance thresholds: baseline weekly volume must be material.
        def _slip(d, min_base=500.0):
            if d.empty: return d
            d2 = d.dropna(subset=['pct'])
            d2 = d2[(d2['baseline'] >= min_base) & (d2['pct'] <= -20)]
            return d2.nsmallest(5, 'pct')

        def _surge(d, min_base=500.0):
            if d.empty: return d
            d2 = d.dropna(subset=['pct'])
            d2 = d2[(d2['baseline'] >= min_base) & (d2['pct'] >= 30)]
            return d2.nlargest(5, 'pct')

        slip_ops, slip_cos   = _slip(op_m),  _slip(co_m)
        surge_ops, surge_cos = _surge(op_m), _surge(co_m)

        # New entrants: in last 7 days but not in the prior 90 days
        def _new(level):
            if level not in df.columns:
                return []
            prior = set(longwin[longwin['order_time'] < recent_start][level]
                        .dropna().astype(str).str.strip().unique())
            now = set(recent[level].dropna().astype(str).str.strip().unique())
            return sorted([x for x in (now - prior) if x and x.lower() not in {"nan", "none"}])

        new_ops = _new('operator')
        new_cos = _new('country')

        # What changed this week vs prior 7 days
        rec_total  = float(recent['sales'].sum() * rate)
        prev_total = float(prev_wk['sales'].sum() * rate)
        week_pct = ((rec_total - prev_total) / prev_total * 100.0) if prev_total > 0 else None

        # Segment breakdown of weekly change
        seg_lines = []
        if 'segment' in df.columns:
            for s, group in recent.groupby('segment', observed=True):
                rs = float(group['sales'].sum() * rate)
                ps = float(prev_wk[prev_wk['segment'] == s]['sales'].sum() * rate)
                if ps > 0:
                    seg_lines.append((s, rs, ((rs - ps) / ps) * 100.0))

        # Top country contribution to / drag on the week
        country_changes = co_m.copy()
        if not country_changes.empty:
            country_changes = country_changes.dropna(subset=['delta'])
            top_driver = country_changes.nlargest(1, 'delta')
            top_drag   = country_changes.nsmallest(1, 'delta')
        else:
            top_driver = top_drag = pd.DataFrame()

        return {
            'symbol': sym, 'rate': rate,
            'reference_date': max_date.date(),
            'rec_total': rec_total, 'prev_total': prev_total, 'week_pct': week_pct,
            'seg_lines': seg_lines,
            'top_driver': top_driver, 'top_drag': top_drag,
            'slip_ops': slip_ops, 'slip_cos': slip_cos,
            'surge_ops': surge_ops, 'surge_cos': surge_cos,
            'new_ops': new_ops, 'new_cos': new_cos,
        }

    def _alert_card(entity, recent_val, baseline_val, pct, sym, color):
        delta_arrow = "▼" if pct is not None and pct < 0 else ("▲" if pct is not None else "•")
        pct_txt = T.format_pct(pct) if pct is not None else ""
        return ui.tags.div(
            ui.tags.div(entity, style="font-weight: 700; color: #0F172A; "
                                     "font-size: 0.95em; line-height: 1.2; "
                                     "margin-bottom: 6px; word-break: break-word;"),
            ui.tags.div(
                ui.tags.span(f"{delta_arrow} {pct_txt}", style=f"color:{color}; font-weight:600;"),
                style="font-size: 0.95em; margin-bottom: 4px;"
            ),
            ui.tags.div(
                f"{T.format_number(recent_val, sym)}  ·  baseline {T.format_number(baseline_val, sym)}/wk",
                style="font-size: 0.78em; color: #64748B;"
            ),
            style=("flex: 0 0 200px; padding: 12px 14px; border-radius: 10px;"
                   "background: white; border: 1px solid #E2E8F0;"
                   f"border-left: 4px solid {color};"
                   "box-shadow: 0 1px 3px rgba(15,23,42,0.04);")
        )

    def _new_entity_card(entity, label, color):
        return ui.tags.div(
            ui.tags.div(entity,
                        style="font-weight: 700; color: #0F172A; font-size: 0.9em;"
                              "word-break: break-word; line-height: 1.2;"),
            ui.tags.div(label, style="font-size: 0.72em; color: #64748B; margin-top: 4px;"),
            style=("flex: 0 0 180px; padding: 10px 14px; border-radius: 10px;"
                   "background: white; border: 1px solid #E2E8F0;"
                   f"border-left: 4px solid {color};"
                   "box-shadow: 0 1px 3px rgba(15,23,42,0.04);")
        )

    def _alert_row(title, icon, frame, color, sym, empty_text):
        if frame is None or frame.empty:
            return ui.div(
                ui.tags.h5(f"{icon} {title}",
                           style="margin: 14px 0 8px 0; font-size: 0.95em; color: #0F172A;"),
                ui.tags.div(empty_text,
                            style="color: #94A3B8; font-size: 0.85em; font-style: italic;"),
            )
        cards = [
            _alert_card(row['entity'], row['recent'], row['baseline'], row.get('pct'), sym, color)
            for _, row in frame.iterrows()
        ]
        return ui.div(
            ui.tags.h5(f"{icon} {title}",
                       style="margin: 14px 0 8px 0; font-size: 0.95em; color: #0F172A;"),
            ui.tags.div(*cards, style="display:flex; gap:10px; flex-wrap:wrap;")
        )

    @render.ui
    @safe_render
    def alerts_panel():
        a = alerts_data()
        if a is None:
            return ui.div(
                ui.p("No data available for alerts.", style="color:#64748B;"),
                class_="chart-container"
            )
        sym = a['symbol']

        # "What changed this week" digest -----------------------------------
        bits = [f"Reference week ending <b>{a['reference_date']}</b>: "
                f"total sales <b>{T.format_number(a['rec_total'], sym)}</b>"]
        if a['week_pct'] is not None:
            wp = a['week_pct']
            color = T.SUCCESS if wp >= 0 else T.DANGER
            bits.append(f"<span style='color:{color}; font-weight:700;'>"
                        f"{('+' if wp>=0 else '')}{wp:.1f}% vs prior 7 days</span>")
        for s, _v, pct in (a['seg_lines'] or []):
            color = T.SUCCESS if pct >= 0 else T.DANGER
            bits.append(f"{s} <span style='color:{color}; font-weight:600;'>"
                        f"{('+' if pct>=0 else '')}{pct:.1f}%</span>")
        if not a['top_driver'].empty:
            r = a['top_driver'].iloc[0]
            bits.append(f"<b>{r['entity']}</b> drove "
                        f"<span style='color:{T.SUCCESS}; font-weight:600;'>"
                        f"+{T.format_number(r['delta'], sym)}</span>")
        if not a['top_drag'].empty:
            r = a['top_drag'].iloc[0]
            if r['delta'] < 0:
                bits.append(f"<b>{r['entity']}</b> slowed "
                            f"<span style='color:{T.DANGER}; font-weight:600;'>"
                            f"{T.format_number(r['delta'], sym)}</span>")

        digest = " · ".join(bits)

        # New entrants row --------------------------------------------------
        new_op_cards = [_new_entity_card(o, "new operator", T.INFO) for o in a['new_ops'][:8]]
        new_co_cards = [_new_entity_card(c, "new country / market", T.WARNING) for c in a['new_cos'][:8]]
        new_section = []
        if new_op_cards or new_co_cards:
            new_section = [ui.tags.h5("✨ New entrants in the last 7 days",
                                       style="margin: 14px 0 8px 0; font-size: 0.95em; color: #0F172A;"),
                           ui.tags.div(*(new_op_cards + new_co_cards),
                                       style="display:flex; gap:10px; flex-wrap:wrap;")]

        return ui.div(
            ui.tags.div(
                ui.HTML(digest),
                style=("background: linear-gradient(135deg, #EEF2FF 0%, #F5F3FF 100%);"
                       "padding: 14px 18px; border-radius: 10px;"
                       "border-left: 4px solid #5B6CFF; margin-bottom: 6px;"
                       "color: #1E293B; font-size: 0.95em; line-height: 1.55;")
            ),
            _alert_row("Slipping operators", "🚨", a['slip_ops'], T.DANGER, sym,
                       "No operators dropping >20% from their 4-week baseline. ✓"),
            _alert_row("Slipping countries / markets", "🚨", a['slip_cos'], T.DANGER, sym,
                       "No countries dropping >20% from their 4-week baseline. ✓"),
            _alert_row("Surging operators", "🚀", a['surge_ops'], T.SUCCESS, sym,
                       "No operators up >30% from baseline."),
            _alert_row("Surging countries", "🚀", a['surge_cos'], T.SUCCESS, sym,
                       "No countries up >30% from baseline."),
            *new_section,
        )

    @render.ui
    @safe_render
    def overview_metrics():
        df = filtered_data()
        prev_df = previous_period_data()
        currency = currency_converter()
        rate = currency['rate']
        symbol = currency['symbol']

        total_sales = df['sales'].sum() * rate if 'sales' in df.columns else 0
        total_orders = df['order_id'].nunique() if 'order_id' in df.columns else len(df)
        total_users = df['user_id'].nunique() if 'user_id' in df.columns else 0
        total_countries = df['country'].nunique() if 'country' in df.columns else 0
        avg_order_value = total_sales / total_orders if total_orders > 0 else 0

        prev_sales = prev_df['sales'].sum() * rate if 'sales' in prev_df.columns else 0
        prev_orders = prev_df['order_id'].nunique() if 'order_id' in prev_df.columns else len(prev_df)
        prev_users = prev_df['user_id'].nunique() if 'user_id' in prev_df.columns else 0

        sales_d  = ((total_sales  - prev_sales)  / prev_sales  * 100) if prev_sales  > 0 else None
        orders_d = ((total_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else None
        users_d  = ((total_users  - prev_users)  / prev_users  * 100) if prev_users  > 0 else None

        lang = input.ui_lang() if hasattr(input, 'ui_lang') else 'en'
        return ui.tags.div(
            _kpi_card(
                "💰", "sales-icon",
                ui.HTML('<span class="lang-en">Total Revenue (GMV)</span><span class="lang-zh">营业额 (GMV)</span>'),
                T.format_full(total_sales, symbol),
                sales_d,
                f"AOV: {T.format_full(avg_order_value, symbol)}",
                f"Total revenue in {currency['label']}; vs equal prior period."
            ),
            _kpi_card(
                "📦", "orders-icon",
                ui.HTML('<span class="lang-en">Total Orders</span><span class="lang-zh">订单总量</span>'),
                f"{total_orders:,}",
                orders_d,
                f"{total_countries:,} {'markets' if lang == 'en' else '个市场'}",
                "Distinct orders in selected period."
            ),
            _kpi_card(
                "👥", "users-icon",
                ui.HTML('<span class="lang-en">Active Customers</span><span class="lang-zh">活跃客户数</span>'),
                f"{total_users:,}",
                users_d,
                f"{(total_orders/total_users):.2f} {'orders/customer' if lang == 'en' else '订单/客户'}" if total_users > 0 else "—",
                "Unique B2C user IDs in selected period."
            ),
            _kpi_card(
                "🌍", "countries-icon",
                ui.HTML('<span class="lang-en">Market Reach</span><span class="lang-zh">市场覆盖</span>'),
                f"{total_countries:,} {'markets' if lang == 'en' else '个市场'}",
                None,
                f"{T.format_full(total_sales/total_countries, symbol)} {'avg/market' if lang == 'en' else '均值/市场'}" if total_countries > 0 else "—",
                "Geographic spread of orders for the selected period."
            ),
            style="display: flex; flex-wrap: nowrap; justify-content: space-between; gap: 12px; overflow-x: auto;"
        )

    @render.ui
    @safe_render
    def operating_overview_kpis():
        """Bitsbang-style operating KPI strip implementing 全球共用计算取数公式及标准:
        充值成功 basis, exclude 电子钱包 + Touch'n Go, 新客=注册月==订单月 (B2C),
        with MoM vs the prior equal period. Cards needing the 用户列表 (Users table)
        — 新客数 / 转化率 — are approximated (≈) or shown as needing data."""
        def _excl_global(d):
            # Global rule: exclude 电子钱包 (e-wallet) and Touch'n Go (TNG) from core metrics.
            if d is None or len(d) == 0 or 'product_category' not in d.columns:
                return d
            cat = d['product_category'].astype(str)
            keep = ~(cat.str.contains('电子钱包', na=False)
                     | cat.str.contains('e-?wallet', case=False, na=False, regex=True)
                     | cat.str.contains('Touch', case=False, na=False))
            return d[keep]

        base = _excl_global(filtered_base_calc())     # all statuses, current period + sidebar filters
        prev_base = _excl_global(previous_period_base())
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']

        cur_succ = filter_by_order_status(base, "Successful")
        prev_succ = filter_by_order_status(prev_base, "Successful")

        def _orders(d):
            if d is None or len(d) == 0:
                return 0
            return int(d['order_id'].nunique()) if 'order_id' in d.columns else len(d)

        def _gmv(d):
            if d is None or len(d) == 0 or 'sales' not in d.columns:
                return 0.0
            return float(d['sales'].sum() * rate)

        def _users(d):
            if d is None or len(d) == 0 or 'user_id' not in d.columns:
                return 0
            return int(d['user_id'].nunique())

        def _uset(d):
            if d is None or len(d) == 0 or 'user_id' not in d.columns:
                return set()
            return set(d['user_id'].dropna().astype(str).unique())

        def _b2c(d):
            if d is None or len(d) == 0 or 'segment' not in d.columns:
                return d
            return d[d['segment'].astype(str).str.upper() == 'B2C']

        def _new_uset(d):
            """新客成功用户 = 注册月份 == 订单月份 (monthly rule, B2C). None if no register_time."""
            d = _b2c(d)
            if d is None or len(d) == 0 or 'register_time' not in d.columns \
                    or 'order_time' not in d.columns or 'user_id' not in d.columns:
                return None
            dd = d.dropna(subset=['register_time', 'order_time', 'user_id'])
            if dd.empty:
                return set()
            regm = pd.to_datetime(dd['register_time'], errors='coerce').dt.to_period('M')
            ordm = pd.to_datetime(dd['order_time'], errors='coerce').dt.to_period('M')
            return set(dd.loc[regm == ordm, 'user_id'].astype(str).unique())

        def _mom(cur, prev):
            return ((cur - prev) / prev * 100) if (prev and prev > 0) else None

        # ── headline (充值成功 basis) ──
        gmv, gmv_p = _gmv(cur_succ), _gmv(prev_succ)
        succ_orders, succ_orders_p = _orders(cur_succ), _orders(prev_succ)
        total_orders, total_orders_p = _orders(base), _orders(prev_base)
        succ_users, succ_users_p = _users(cur_succ), _users(prev_succ)
        succ_rate = (succ_orders / total_orders * 100) if total_orders > 0 else None
        succ_rate_p = (succ_orders_p / total_orders_p * 100) if total_orders_p > 0 else None
        aov = (gmv / succ_orders) if succ_orders > 0 else 0.0
        aov_p = (gmv_p / succ_orders_p) if succ_orders_p > 0 else 0.0

        # ── new/old (B2C, 注册月 vs 订单月) + 复购率 + 留存率 (order-based sets) ──
        cur_new = _new_uset(cur_succ)
        prev_new = _new_uset(prev_succ)
        has_reg = cur_new is not None
        cur_uset, prev_uset = _uset(cur_succ), _uset(prev_succ)
        repurchase = (len(cur_uset & prev_uset) / len(cur_uset) * 100) if cur_uset else None
        new_gmv = old_gmv = new_gmv_p = old_gmv_p = retention = None
        new_ordered = new_ordered_p = None
        if has_reg:
            b2c_succ, b2c_succ_p = _b2c(cur_succ), _b2c(prev_succ)
            new_gmv = float(b2c_succ[b2c_succ['user_id'].astype(str).isin(cur_new)]['sales'].sum() * rate) \
                if ('sales' in b2c_succ.columns and len(b2c_succ)) else 0.0
            old_gmv = max(_gmv(b2c_succ) - new_gmv, 0.0)
            new_gmv_p = float(b2c_succ_p[b2c_succ_p['user_id'].astype(str).isin(prev_new)]['sales'].sum() * rate) \
                if (b2c_succ_p is not None and 'sales' in b2c_succ_p.columns and len(b2c_succ_p)) else 0.0
            old_gmv_p = max(_gmv(b2c_succ_p) - new_gmv_p, 0.0)
            retention = (len(prev_new & cur_uset) / len(prev_new) * 100) if prev_new else None
            new_ordered = len(cur_new)
            new_ordered_p = len(prev_new) if prev_new is not None else 0

        def _card(icon, cls, en, zh, value, delta, sub, tip):
            return _kpi_card(
                icon, cls,
                ui.HTML(f'<span class="lang-en">{en}</span><span class="lang-zh">{zh}</span>'),
                value, delta, ui.HTML(sub) if isinstance(sub, str) and '<span' in sub else sub, tip)

        def _pending(icon, cls, en, zh, sub, tip):
            return _kpi_card(
                icon, cls,
                ui.HTML(f'<span class="lang-en">{en}</span><span class="lang-zh">{zh}</span>'),
                "—", None, ui.HTML(sub), tip)

        oldnew_sub = ('<span class="lang-en">B2C · reg-month vs order-month</span>'
                      '<span class="lang-zh">B2C · 注册月 vs 订单月</span>')
        need_reg = ('<span class="lang-en">needs register_time (B2C)</span>'
                    '<span class="lang-zh">需注册时间 (B2C)</span>')
        need_userlist = ('<span class="lang-en">needs 用户列表 (Users)</span>'
                         '<span class="lang-zh">需用户列表</span>')

        # ── exact 新客数 / 转化率 from the 用户列表 ──
        df_from, df_to = applied_date_from(), applied_date_to()
        country_sel = applied_country()
        new_ids, ul_ok = _new_customer_ids(df_from, df_to, country_sel)
        pfrom = pto = None
        if df_from and df_to:
            _s = pd.to_datetime(df_from, errors='coerce')
            _e = pd.to_datetime(df_to, errors='coerce')
            if pd.notna(_s) and pd.notna(_e):
                if _s > _e:
                    _s, _e = _e, _s
                pto, pfrom = _s, _s - (_e - _s)
        new_ids_prev, _ = _new_customer_ids(pfrom, pto, country_sel)

        def _nset(d):
            if d is None or len(d) == 0 or 'user_id' not in d.columns:
                return set()
            return set(d['user_id'].dropna().astype(str).str.replace(r'\.0$', '', regex=True).unique())
        succ_ids, succ_ids_p = _nset(cur_succ), _nset(prev_succ)

        if ul_ok:
            nc, nc_p = len(new_ids), len(new_ids_prev)
            conv = (len(new_ids & succ_ids) / nc * 100) if nc else None
            conv_p = (len(new_ids_prev & succ_ids_p) / nc_p * 100) if nc_p else None
            newcust_card = _card("🌟", "sales-icon", "New Customers", "新客数",
                f"{nc:,}", _mom(nc, nc_p),
                '<span class="lang-en">registered in period · 用户列表</span><span class="lang-zh">本期注册 · 用户列表</span>',
                "新客数 = COUNT(DISTINCT 用户ID) WHERE 注册时间∈周期 (用户列表; 汇总=仅微信端, 微信剔除国家为空).")
            conv_card = (_card("📈", "orders-icon", "Conversion Rate", "转化率",
                f"{conv:.1f}%", _mom(conv, conv_p),
                '<span class="lang-en">new ∩ success / new</span><span class="lang-zh">当月新客∩当月成功 / 当月新客</span>',
                "转化率 = |当月新客 ∩ 当月成功订单用户| / |当月新客| (用户列表 ∩ 订单表).")
                if conv is not None else
                _pending("📈", "orders-icon", "Conversion Rate", "转化率",
                '<span class="lang-en">no new users in scope</span><span class="lang-zh">本期范围内无新客</span>',
                "No new registrations in the selected period / country scope."))
        elif has_reg:
            newcust_card = _card("🌟", "sales-icon", "New Customers*", "新客数*",
                (f"≈ {new_ordered:,}" if new_ordered is not None else "-"),
                _mom(new_ordered, new_ordered_p),
                '<span class="lang-en">≈ ordered-new · 用户列表 not found</span><span class="lang-zh">≈ 成单新客 · 未找到用户列表</span>',
                "Approx (用户列表 not found in database/ or the Report folder): distinct B2C 成单 new customers (注册月=订单月).")
            conv_card = _pending("📈", "orders-icon", "Conversion Rate", "转化率", need_userlist,
                "转化率 needs the 用户列表 — drop 用户列表*.csv into database/ or the Report Raw Data folder.")
        else:
            newcust_card = _pending("🌟", "sales-icon", "New Customers", "新客数", need_userlist,
                "新客数 must come from the 用户列表 (registration table).")
            conv_card = _pending("📈", "orders-icon", "Conversion Rate", "转化率", need_userlist,
                "转化率 needs the 用户列表 (registration table).")

        return ui.tags.div(
            _card("💰", "sales-icon", "Revenue (GMV)", "营业额 (GMV)",
                  T.format_full(gmv, sym), _mom(gmv, gmv_p),
                  '<span class="lang-en">充值成功 · excl e-wallet/TNG</span><span class="lang-zh">充值成功 · 剔除电子钱包/TNG</span>',
                  "营业额 = SUM(实际支付) WHERE 订单状态='充值成功' (剔除电子钱包/Touch'n Go)."),
            (_card("👴", "sales-icon", "Returning-customer GMV", "老客营业额",
                   T.format_full(old_gmv, sym), _mom(old_gmv, old_gmv_p), oldnew_sub,
                   "老客营业额 = 充值成功 GMV，注册月 < 订单月 (B2C).")
             if has_reg else
             _pending("👴", "sales-icon", "Returning-customer GMV", "老客营业额", need_reg,
                      "Requires B2C register_time (注册时间).")),
            (_card("🆕", "sales-icon", "New-customer GMV", "新客营业额",
                   T.format_full(new_gmv, sym), _mom(new_gmv, new_gmv_p), oldnew_sub,
                   "新客营业额 = 充值成功 GMV，注册月 = 订单月 (B2C).")
             if has_reg else
             _pending("🆕", "sales-icon", "New-customer GMV", "新客营业额", need_reg,
                      "Requires B2C register_time (注册时间).")),
            _card("📦", "orders-icon", "Successful Orders", "成单数",
                  f"{succ_orders:,}", _mom(succ_orders, succ_orders_p),
                  '<span class="lang-en">充值成功 orders</span><span class="lang-zh">充值成功订单</span>',
                  "成单数 = count of 充值成功 orders."),
            _card("🧑", "users-icon", "Successful Users", "成单人数",
                  f"{succ_users:,}", _mom(succ_users, succ_users_p),
                  '<span class="lang-en">unique buyers</span><span class="lang-zh">去重买家</span>',
                  "成单人数 = 充值成功 去重用户数."),
            _card("✅", "users-icon", "Success Rate", "成单率",
                  (f"{succ_rate:.1f}%" if succ_rate is not None else "-"),
                  (_mom(succ_rate, succ_rate_p) if (succ_rate is not None and succ_rate_p) else None),
                  '<span class="lang-en">success ÷ all orders</span><span class="lang-zh">成功 ÷ 全量订单</span>',
                  "成单率 = 成功订单数 ÷ 全量订单数(含成功/失败)."),
            _card("💎", "countries-icon", "AOV", "客单价",
                  T.format_full(aov, sym), _mom(aov, aov_p),
                  '<span class="lang-en">GMV ÷ successful orders</span><span class="lang-zh">GMV ÷ 成单数</span>',
                  "客单价 = 营业额(GMV) ÷ 成单数."),
            _card("🔁", "orders-icon", "Repurchase Rate", "复购率",
                  (f"{repurchase:.1f}%" if repurchase is not None else "-"), None,
                  '<span class="lang-en">this-mo ∩ last-mo / this-mo</span><span class="lang-zh">本月∩上月成单 / 本月成单</span>',
                  "复购率 = |上月成功用户 ∩ 本月成功用户| / |本月成功用户|."),
            (_card("📌", "users-icon", "Retention Rate", "留存率",
                   (f"{retention:.1f}%" if retention is not None else "-"), None,
                   '<span class="lang-en">last-mo new ∩ this-mo / last-mo new</span><span class="lang-zh">上月新客∩本月成单 / 上月新客</span>',
                   "留存率 = |上月新客成功用户 ∩ 本月成功用户| / |上月新客成功用户|.")
             if has_reg else
             _pending("📌", "users-icon", "Retention Rate", "留存率", need_reg,
                      "Requires B2C register_time to identify 上月新客.")),
            newcust_card,
            conv_card,
            style="display: flex; flex-wrap: wrap; justify-content: flex-start; gap: 12px;"
        )

    @render.ui
    @safe_render
    def net_contribution_kpi():
        """Net Contribution (净贡献) = 成功GMV − COGS(结算价→RMB) − 券支出, with
        已退款GMV shown as context (excluded from Net). MoM vs prior equal period."""
        base = filtered_base_calc()            # already excludes 电子钱包/TNG
        prev_base = previous_period_base()
        currency = currency_converter(); rate, sym = currency['rate'], currency['symbol']

        def _net(b):
            if b is None or len(b) == 0:
                return 0.0, 0.0, 0.0, 0.0, 0.0
            succ = filter_by_order_status(b, "Successful")
            refunded = filter_by_order_status(b, "Refunded")
            gmv = float(succ['sales'].sum() * rate) if 'sales' in succ.columns else 0.0
            scol = 'settlement_rmb' if 'settlement_rmb' in succ.columns else 'settlement_price'
            cogs = float(pd.to_numeric(succ[scol], errors='coerce').sum() * rate) if scol in succ.columns else 0.0
            coupon = float(pd.to_numeric(succ['coupon_amount'], errors='coerce').sum() * rate) if 'coupon_amount' in succ.columns else 0.0
            refunded_gmv = float(refunded['sales'].sum() * rate) if (refunded is not None and 'sales' in refunded.columns) else 0.0
            return gmv - cogs - coupon, gmv, cogs, coupon, refunded_gmv

        net, gmv, cogs, coupon, refunded_gmv = _net(base)
        net_p = _net(prev_base)[0]
        delta = ((net - net_p) / net_p * 100) if net_p and net_p > 0 else None
        margin_pct = (net / gmv * 100) if gmv else 0.0

        sub = (f'<span class="lang-en">GMV {T.format_number(gmv, sym)} − COGS {T.format_number(cogs, sym)} '
               f'− coupon {T.format_number(coupon, sym)}</span>'
               f'<span class="lang-zh">成功GMV {T.format_number(gmv, sym)} − COGS {T.format_number(cogs, sym)} '
               f'− 券 {T.format_number(coupon, sym)}</span>')
        tip = ("Net Contribution = 成功GMV − COGS(结算价→RMB) − 券支出. "
               "已退款GMV shown separately (excluded). Supplier settlement refund on 已退款 unconfirmed (review B2).")
        return ui.tags.div(
            _kpi_card("💎", "sales-icon",
                      ui.HTML('<span class="lang-en">Net Contribution</span><span class="lang-zh">净贡献</span>'),
                      T.format_full(net, sym), delta, ui.HTML(sub), tip),
            _kpi_card("📊", "countries-icon",
                      ui.HTML('<span class="lang-en">Net Margin %</span><span class="lang-zh">净贡献率</span>'),
                      f"{margin_pct:.1f}%", None,
                      ui.HTML('<span class="lang-en">Net ÷ 成功GMV</span><span class="lang-zh">净贡献 ÷ 成功GMV</span>'),
                      "Net Contribution as a share of successful GMV."),
            _kpi_card("↩", "orders-icon",
                      ui.HTML('<span class="lang-en">Refunded GMV</span><span class="lang-zh">已退款GMV</span>'),
                      T.format_full(refunded_gmv, sym), None,
                      ui.HTML('<span class="lang-en">booked but returned (excluded)</span><span class="lang-zh">已退款（不计入净贡献）</span>'),
                      "GMV of 已退款 orders — booked but refunded; excluded from Net Contribution."),
            style="display: flex; flex-wrap: wrap; gap: 12px;"
        )

    @render.ui
    @safe_render
    def top_movers_strip():
        """Three side-by-side mini-cards: top riser, top decliner, top product."""
        df = filtered_data()
        prev = previous_period_data()
        if 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        sym = currency['symbol']

        def _mover_card(title, icon, name, value, change, color):
            change_str = T.format_pct(change) if change is not None else "—"
            return ui.tags.div(
                ui.tags.div(icon, style="font-size: 1.4em; margin-bottom: 6px;"),
                ui.tags.div(title, style="font-size: 0.78em; color:#64748B; text-transform: uppercase; letter-spacing:0.5px; font-weight:600;"),
                ui.tags.div(name, style="font-size: 1.15em; font-weight: 700; color:#0F172A; margin-top:4px; line-height: 1.2;"),
                ui.tags.div(
                    ui.tags.span(value, style="color:#475569; font-size:0.9em;"),
                    ui.tags.span(f" · {change_str}", style=f"color:{color}; font-weight:600;") if change is not None else "",
                    style="margin-top:6px;"
                ),
                style=("flex:1 1 22%; min-width:220px; padding:18px; border-radius:12px;"
                       "background:white; border:1px solid #E2E8F0;"
                       "box-shadow: 0 1px 3px rgba(15,23,42,0.04);"
                       f"border-left: 4px solid {color};"),
            )

        # Country: best riser & worst decliner (current vs previous period)
        if 'country' in df.columns:
            cur_c = df.groupby('country', observed=True)['sales'].sum() * currency['rate']
            prv_c = prev.groupby('country', observed=True)['sales'].sum() * currency['rate']
            # Convert CategoricalIndex to plain string to avoid int16 buffer dtype mismatch
            cur_c.index = cur_c.index.astype(str)
            prv_c.index = prv_c.index.astype(str)
            gc = pd.concat([cur_c.rename('cur'), prv_c.rename('prv')], axis=1).fillna(0)
            # Significance floor: ≥500 prior-period revenue (matches alerts_data min_base)
            # so a 2→6-order market can't outrank a real mover on % alone.
            gc = gc[(gc['prv'] >= max(500.0, gc['prv'].quantile(0.5)))]
            if not gc.empty:
                gc['pct'] = (gc['cur'] - gc['prv']) / gc['prv'] * 100
                gc = gc.dropna(subset=['pct'])
                top_riser    = gc.nlargest(1,  'pct')
                top_decliner = gc.nsmallest(1, 'pct')
            else:
                top_riser = top_decliner = pd.DataFrame()
        else:
            top_riser = top_decliner = pd.DataFrame()

        # Product: top product by current sales
        if 'product' in df.columns:
            top_p = df.groupby('product', observed=True)['sales'].sum().mul(currency['rate']).nlargest(1)
            top_p_name  = top_p.index[0] if len(top_p) else "—"
            top_p_value = top_p.iloc[0] if len(top_p) else 0
        else:
            top_p_name = "—"; top_p_value = 0

        # Operator: top operator by current sales
        if 'operator' in df.columns:
            top_o = df.groupby('operator', observed=True)['sales'].sum().mul(currency['rate']).nlargest(1)
            top_o_name  = top_o.index[0] if len(top_o) else "—"
            top_o_value = top_o.iloc[0] if len(top_o) else 0
        else:
            top_o_name = "—"; top_o_value = 0

        cards = []
        if not top_riser.empty:
            r = top_riser.iloc[0]
            cards.append(_mover_card("Fastest growing market", "🚀", top_riser.index[0],
                                     T.format_number(r['cur'], sym), r['pct'], T.SUCCESS))
        if not top_decliner.empty:
            r = top_decliner.iloc[0]
            cards.append(_mover_card("Biggest decliner", "📉", top_decliner.index[0],
                                     T.format_number(r['cur'], sym), r['pct'], T.DANGER))
        cards.append(_mover_card("Top product", "🏆", str(top_p_name),
                                 T.format_number(top_p_value, sym), None, T.PRIMARY))
        cards.append(_mover_card("Top operator", "🤝", str(top_o_name),
                                 T.format_number(top_o_value, sym), None, T.SECONDARY))

        return ui.tags.div(*cards,
                           style="display:flex; gap:12px; flex-wrap:wrap;")

    @render.ui
    @safe_render
    def overview_sales_trend():
        df = filtered_data()
        if 'order_time' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        symbol = currency['symbol']
        period = applied_trend_period() or "Monthly"
        period_freq = {"Daily": None, "Weekly": "W", "Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}
        if period == "Daily":
            grouped = df.groupby(df['order_time'].dt.date)
        else:
            grouped = df.groupby(df['order_time'].dt.to_period(period_freq[period]).dt.start_time)
        sales_trend = grouped['sales'].sum().mul(currency['rate']).reset_index()
        sales_trend.columns = ['order_time', 'sales']

        filter_summary = []
        seg = applied_segment()
        ctr = applied_country()
        reg = applied_region()
        if seg and seg != "All":
            filter_summary.append(f"Segment: {seg}")
        if reg and reg != "All":
            filter_summary.append(f"Region: {reg}")
        if ctr and ctr != "All":
            filter_summary.append(f"Country: {ctr}")
        filter_note = " · ".join(filter_summary) if filter_summary else "All segments · All regions · All countries"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=sales_trend['order_time'], y=sales_trend['sales'],
            mode='lines+markers', name=_tt('Sales'),
            line=dict(color=T.PRIMARY, width=2.5, shape='spline'),
            marker=dict(size=6, color=T.PRIMARY, line=dict(width=1.5, color='white')),
            fill='tozeroy', fillcolor='rgba(91,108,255,0.10)',
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Sales: ' + symbol + '%{y:,.2f}<extra></extra>',
        ))
        # 3.2 Targets vs-plan: dashed plan line from database/targets.csv (per-month revenue target)
        targets = _load_targets()
        if targets:
            months = pd.to_datetime(sales_trend['order_time']).dt.to_period('M').astype(str)
            tvals = [(targets.get(('revenue', m)) or targets.get(('gmv', m))) for m in months]
            tvals_disp = [(v * currency['rate']) if v is not None else None for v in tvals]
            if any(v is not None for v in tvals_disp):
                fig.add_trace(go.Scatter(
                    x=sales_trend['order_time'], y=tvals_disp,
                    mode='lines', name=_tt('Target'),
                    line=dict(color=T.WARNING, width=2, dash='dash'),
                    connectgaps=False,
                    hovertemplate='<b>%{x|%Y-%m}</b><br>Target: ' + symbol + '%{y:,.0f}<extra></extra>',
                ))
        T.apply_theme(fig, title=_tt(f"{period} Sales Trend"),
                      xaxis_title=None, yaxis_title=_tt(f"Sales ({symbol})"),
                      hovermode='x unified', margin=dict(l=10, r=10, t=70, b=10),
                      annotations=[dict(text=filter_note, xref='paper', yref='paper',
                                        x=0, y=1.08, showarrow=False,
                                        font=dict(size=11, color=T.NEUTRAL))])
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def overview_sales_segment():
        df = filtered_data()
        if 'segment' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        seg = df.groupby('segment', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        fig = go.Figure(go.Pie(
            labels=seg['segment'], values=seg['sales'],
            hole=0.55,
            marker=dict(colors=T.PALETTE, line=dict(color='white', width=2)),
            textinfo='label+percent', textfont=dict(size=13),
            hovertemplate='<b>%{label}</b><br>Sales: ' + currency['symbol'] + '%{value:,.0f}<br>%{percent}<extra></extra>',
        ))
        total = seg['sales'].sum()
        fig.add_annotation(text=f"<b>Total</b><br>{T.format_number(total, currency['symbol'])}",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#0F172A"))
        T.apply_theme(fig, title=_tt(f"Sales mix · {currency['label']}"),
                      showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def segment_summary_table():
        df = filtered_data()
        if 'segment' in df.columns:
            currency = currency_converter()
            rate = currency['rate']
            grp = df.groupby('segment', observed=True)
            summary = pd.DataFrame({
                'Total Sales':  grp['sales'].sum() * rate,
                'Avg Sales':    grp['sales'].mean() * rate,
                'Transactions': grp['sales'].count(),
                'Total Orders': grp['order_id'].nunique(),
                'Unique Users': grp['user_id'].nunique(),
            }).reset_index().rename(columns={'segment': 'Segment'})
            summary['Avg Order Value'] = summary['Total Sales'] / summary['Total Orders']
            summary['Orders per User'] = summary['Total Orders'] / summary['Unique Users']
            
            # Add share percentages
            total_sales_all = summary['Total Sales'].sum()
            total_orders_all = summary['Total Orders'].sum()
            summary['Sales Share %'] = (summary['Total Sales'] / total_sales_all * 100).round(1)
            summary['Orders Share %'] = (summary['Total Orders'] / total_orders_all * 100).round(1)
            
            # Rename segments for clarity
            segment_labels = {'B2B': 'Business-to-Business (B2B)', 'B2C': 'Business-to-Consumer (B2C)'}
            summary['Segment'] = summary['Segment'].map(segment_labels).fillna(summary['Segment'])
            
            out = summary[['Segment', 'Total Sales', 'Sales Share %', 'Avg Order Value',
                           'Total Orders', 'Orders Share %', 'Unique Users', 'Orders per User']].copy()
            for col in ['Total Sales', 'Avg Order Value', 'Avg Sales']:
                if col in out.columns:
                    out[col] = out[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
            for col in ['Sales Share %', 'Orders Share %']:
                if col in out.columns:
                    out[col] = out[col].apply(lambda x: f"{x:.1f}%")
            for col in ['Total Orders', 'Unique Users']:
                if col in out.columns:
                    out[col] = out[col].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
            for col in ['Orders per User']:
                if col in out.columns:
                    out[col] = out[col].apply(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
            return render.DataGrid(_tdf(out), filters=False)
        return render.DataGrid(pd.DataFrame())

    # ── New: Executive Overview additions ─────────────────────────────────────

    @render.ui
    @safe_render
    def overview_region_donut():
        df = filtered_data()
        if 'region' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        reg = df.groupby('region', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        reg = reg[reg['sales'] > 0].sort_values('sales', ascending=False)
        if reg.empty:
            return _no_data()
        total = reg['sales'].sum()
        fig = go.Figure(go.Pie(
            labels=reg['region'], values=reg['sales'],
            hole=0.55,
            marker=dict(colors=T.PALETTE, line=dict(color='white', width=2)),
            textinfo='label+percent', textfont=dict(size=12),
            hovertemplate='<b>%{label}</b><br>Revenue: ' + currency['symbol'] +
                          '%{value:,.0f}<br>Share: %{percent}<extra></extra>',
        ))
        fig.add_annotation(text=f"<b>By Region</b><br>{T.format_number(total, currency['symbol'])}",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=13, color="#0F172A"))
        T.apply_theme(fig, title=_tt(f"Revenue Contribution by Region · {currency['label']}"),
                      showlegend=True, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def overview_top5_countries():
        df = filtered_data()
        if 'country' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        top5 = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).nlargest(5).reset_index()
        top5 = top5.sort_values('sales')
        fig = go.Figure(go.Bar(
            x=top5['sales'], y=top5['country'], orientation='h',
            marker=dict(color=T.PALETTE[:5], line=dict(color='white', width=1)),
            text=[T.format_number(v, currency['symbol']) for v in top5['sales']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Revenue (GMV): ' + currency['symbol'] + '%{x:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Top 5 Markets by Revenue (GMV) · {currency['label']}"),
                      xaxis_title=_tt(f"Revenue ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=280)
        return ui.HTML(T.fig_to_html(fig))

    # ── New: Revenue & Orders tab additions ───────────────────────────────────

    @render.ui
    @safe_render
    def revenue_orders_kpis():
        df = filtered_data()
        prev_df = previous_period_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']

        total_sales = float(df['sales'].sum() * rate) if 'sales' in df.columns else 0
        total_orders = int(df['order_id'].nunique()) if 'order_id' in df.columns else len(df)
        total_users = int(df['user_id'].nunique()) if 'user_id' in df.columns else 0
        aov = total_sales / total_orders if total_orders > 0 else 0
        arpu = total_sales / total_users if total_users > 0 else 0

        prev_sales = float(prev_df['sales'].sum() * rate) if 'sales' in prev_df.columns else 0
        prev_orders = int(prev_df['order_id'].nunique()) if 'order_id' in prev_df.columns else 0
        sales_d  = ((total_sales  - prev_sales)  / prev_sales  * 100) if prev_sales  > 0 else None
        orders_d = ((total_orders - prev_orders) / prev_orders * 100) if prev_orders > 0 else None

        return ui.tags.div(
            _kpi_card("💰", "sales-icon", _bl("Total Revenue (GMV)", "营业额 (GMV)"),
                      T.format_full(total_sales, sym), sales_d,
                      f"vs previous period",
                      f"Gross Merchandise Value in {currency['label']} for the selected period."),
            _kpi_card("📦", "orders-icon", _bl("Total Order Volume", "订单总量"),
                      f"{total_orders:,}", orders_d,
                      "Unique order IDs",
                      "Distinct orders placed in the selected period."),
            _kpi_card("💎", "users-icon", _bl("Avg Order Value (AOV)", "客单价 (AOV)"),
                      T.format_full(aov, sym), None,
                      "GMV ÷ Order Volume",
                      "Average revenue per transaction."),
            _kpi_card("👤", "countries-icon", _bl("Avg Revenue / Customer (ARPU)", "客均收入 (ARPU)"),
                      T.format_full(arpu, sym), None,
                      "GMV ÷ Active Customers (B2C)",
                      "Average revenue per active B2C customer."),
            style="display: flex; flex-wrap: wrap; gap: 12px;"
        )

    @render.ui
    @safe_render
    def aov_by_segment_chart():
        df = filtered_data()
        if 'segment' not in df.columns or 'sales' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = df.groupby('segment', observed=True)
        agg = pd.DataFrame({'sales': grp['sales'].sum(),
                            'orders': grp['order_id'].nunique()}).reset_index()
        agg['aov'] = (agg['sales'] * rate) / agg['orders'].replace(0, np.nan)
        agg = agg.dropna(subset=['aov']).sort_values('aov', ascending=True)
        fig = go.Figure(go.Bar(
            x=agg['aov'], y=agg['segment'], orientation='h',
            marker=dict(color=T.PALETTE[:len(agg)], line=dict(color='white', width=1)),
            text=[T.format_number(v, sym) for v in agg['aov']],
            textposition='outside', textfont=dict(size=12, color="#334155"),
            hovertemplate='<b>%{y}</b><br>AOV: ' + sym + '%{x:,.2f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Average Order Value (AOV) by Customer Segment · {currency['label']}"),
                      xaxis_title=_tt(f"AOV ({sym})"), yaxis_title=None,
                      showlegend=False, margin=dict(l=10, r=80, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def sales_country_chart():
        df = filtered_data()
        if 'country' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        cs = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).nlargest(10).reset_index()
        cs = cs.sort_values('sales')
        fig = go.Figure(go.Bar(
            x=cs['sales'], y=cs['country'], orientation='h',
            marker=dict(color=cs['sales'], colorscale=T.SCALE_SEQUENTIAL, showscale=False,
                        line=dict(color='white', width=1)),
            text=[T.format_number(v, currency['symbol']) for v in cs['sales']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Sales: ' + currency['symbol'] + '%{x:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Top 10 countries by sales · {currency['label']}"),
                      xaxis_title=_tt(f"Sales ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def sales_segment_chart():
        df = filtered_data()
        if 'segment' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        seg = df.groupby('segment', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        fig = go.Figure(go.Bar(
            x=seg['segment'], y=seg['sales'],
            marker=dict(color=T.PALETTE[:len(seg)], line=dict(color='white', width=1)),
            text=[T.format_number(v, currency['symbol']) for v in seg['sales']],
            textposition='outside', textfont=dict(size=12, color="#334155"),
            hovertemplate='<b>%{x}</b><br>Sales: ' + currency['symbol'] + '%{y:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Sales by segment · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Sales ({currency['symbol']})"),
                      showlegend=False)
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def sales_by_country_table():
        df = filtered_data()
        if {'country', 'segment', 'sales'}.issubset(df.columns):
            currency = currency_converter()
            rate = currency['rate']
            sales_table = df.groupby(['country', 'segment'], observed=True)['sales'].sum().mul(rate).unstack(fill_value=0)
            sales_table.columns = [str(c) for c in sales_table.columns]
            sales_table['Total'] = sales_table.sum(axis=1)
            sales_table = sales_table.sort_values('Total', ascending=False).reset_index()
            num_cols = [c for c in sales_table.columns if c != 'country']
            for c in num_cols:
                sales_table[c] = pd.to_numeric(sales_table[c], errors='coerce').apply(
                    lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
            return render.DataGrid(_tdf(sales_table), filters=True)
        return render.DataGrid(pd.DataFrame())

    # ── Order Status & Quality (uses pre-status-filter data) ─────────────────

    @reactive.Calc
    def _status_frame():
        """Filtered data WITHOUT the order-status filter, with a clean
        status-group column. None when order_status is unavailable."""
        df = filtered_base_calc()
        if 'order_status' not in df.columns or df.empty:
            return None
        d = df.copy()
        s = d['order_status'].astype(str).str.strip()
        group = pd.Series("Other", index=d.index)
        for name, values in ORDER_STATUS_GROUPS.items():
            group = group.mask(s.isin(values), name)
        d['status_group'] = group
        return d

    @render.ui
    @safe_render
    def order_status_kpis():
        d = _status_frame()
        if d is None:
            return ui.HTML(
                '<div style="color:#64748B;padding:20px;">Order status data not available — '
                'click <b>Rebuild Data Pipeline</b> in the sidebar to load the new 订单状态 column.</div>'
            )
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        total = d['order_id'].nunique() if 'order_id' in d.columns else len(d)
        if total == 0:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No orders in the current selection.</div>')

        def _count(grp_name):
            sub = d[d['status_group'] == grp_name]
            return sub['order_id'].nunique() if 'order_id' in sub.columns else len(sub)

        n_success = _count("Successful")
        n_refund  = _count("Refunded")
        n_cancel  = _count("Cancelled")
        n_pending = _count("Pending")
        refund_gmv = float(d.loc[d['status_group'] == "Refunded", 'sales'].sum() * rate) if 'sales' in d.columns else 0.0
        success_rate = n_success / total * 100
        refund_rate  = n_refund / total * 100

        return ui.tags.div(
            _kpi_card("✅", "sales-icon", _bl("Success Rate", "成功率"),
                      f"{success_rate:.2f}%", None,
                      f"{T.format_int(n_success)} of {T.format_int(total)} orders",
                      "Orders with status 充值成功 ÷ all orders in the selection."),
            _kpi_card("↩", "orders-icon", _bl("Refund Rate", "退款率"),
                      f"{refund_rate:.2f}%", None,
                      f"{T.format_int(n_refund)} refunds · {T.format_number(refund_gmv, sym)} GMV",
                      "已退款 orders. Refunded GMV is revenue you booked but did not keep."),
            _kpi_card("✖", "users-icon", _bl("Cancelled Orders", "已取消订单"),
                      T.format_int(n_cancel), None,
                      f"{(n_cancel / total * 100):.2f}% of orders",
                      "已取消 orders (B2C checkout abandonments / failures)."),
            _kpi_card("⏳", "countries-icon", _bl("Pending / In-progress", "待处理订单"),
                      T.format_int(n_pending), None,
                      "等待支付 · 待付款 · 等待处理 · 充值中",
                      "Orders not yet in a final state at export time."),
            class_="metrics-grid"
        )

    @render.ui
    @safe_render
    def order_status_breakdown_chart():
        d = _status_frame()
        if d is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Order status data not available.</div>')
        if 'segment' not in d.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Segment column not available.</div>')
        grp = d.groupby(['status_group', 'segment'], observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = orders_s.reset_index(name=_tt('orders'))
        agg = agg[agg['orders'] > 0]
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No orders in the current selection.</div>')
        status_order = ["Successful", "Refunded", "Cancelled", "Pending", "Other"]
        colors = {"Successful": T.SUCCESS, "Refunded": T.DANGER, "Cancelled": "#F59E0B",
                  "Pending": "#94A3B8", "Other": "#CBD5E1"}
        fig = go.Figure()
        for st in status_order:
            sub = agg[agg['status_group'] == st]
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub['segment'].astype(str), y=sub['orders'],
                name=st,
                marker=dict(color=colors.get(st, T.PRIMARY), line=dict(color='white', width=1)),
                hovertemplate='<b>%{x}</b><br>' + st + ': %{y:,} orders<extra></extra>',
            ))
        fig.update_layout(barmode='stack')
        T.apply_theme(fig, title=_tt("Order Count by Status × Segment"),
                      xaxis_title=None, yaxis_title=_tt("Orders"), height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def refund_trend_chart():
        d = _status_frame()
        if d is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Order status data not available.</div>')
        if 'order_time' not in d.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Order time column not available.</div>')
        d = d.dropna(subset=['order_time']).copy()
        if d.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No dated orders in the current selection.</div>')
        d['month'] = d['order_time'].dt.to_period('M').dt.start_time
        segs = sorted(d['segment'].dropna().astype(str).unique().tolist()) if 'segment' in d.columns else ['All']
        fig = go.Figure()
        palette = T.PALETTE
        for i, seg in enumerate(segs):
            sub = d[d['segment'].astype(str) == seg] if 'segment' in d.columns else d
            ref = sub[sub['status_group'] == 'Refunded']
            if 'order_id' in sub.columns:
                total_s  = sub.groupby('month', observed=True)['order_id'].nunique()
                refund_s = ref.groupby('month', observed=True)['order_id'].nunique()
            else:
                total_s  = sub.groupby('month', observed=True).size()
                refund_s = ref.groupby('month', observed=True).size()
            refund_s = refund_s.reindex(total_s.index, fill_value=0)
            rates = (refund_s / total_s.replace(0, np.nan) * 100).dropna()
            if rates.empty:
                continue
            fig.add_trace(go.Scatter(
                x=rates.index, y=rates.values,
                mode='lines+markers', name=seg,
                line=dict(width=2.5, color=palette[i % len(palette)], shape='spline'),
                marker=dict(size=7, line=dict(color='white', width=1)),
                hovertemplate='<b>' + seg + '</b><br>%{x|%b %Y}: %{y:.2f}%<extra></extra>',
            ))
        if not fig.data:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Not enough data to compute monthly refund rates.</div>')
        T.apply_theme(fig, title=_tt("Monthly Refund Rate by Segment"),
                      xaxis_title=None, yaxis_title=_tt("Refund rate (%)"),
                      hovermode='x unified', height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def refund_by_operator_chart():
        d = _status_frame()
        if d is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Order status data not available.</div>')
        if 'operator' not in d.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Operator column not available.</div>')
        d = d.copy()
        d['operator'] = d['operator'].astype(str)
        ref = d[d['status_group'] == 'Refunded']
        if 'order_id' in d.columns:
            total_s  = d.groupby('operator', observed=True)['order_id'].nunique()
            refund_s = ref.groupby('operator', observed=True)['order_id'].nunique()
        else:
            total_s  = d.groupby('operator', observed=True).size()
            refund_s = ref.groupby('operator', observed=True).size()
        refund_s = refund_s.reindex(total_s.index, fill_value=0)
        agg = pd.DataFrame({'orders': total_s, 'refunds': refund_s}).reset_index()
        agg = agg[agg['orders'] >= 200]
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No operator has ≥200 orders in the current selection — widen the date range.</div>')
        agg['refund_rate'] = agg['refunds'] / agg['orders'] * 100
        agg = agg.nlargest(10, 'refund_rate').sort_values('refund_rate')
        fig = go.Figure(go.Bar(
            x=agg['refund_rate'], y=agg['operator'], orientation='h',
            marker=dict(color=agg['refund_rate'], colorscale='Reds',
                        showscale=False, line=dict(color='white', width=1)),
            text=[f"{v:.1f}%" for v in agg['refund_rate']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            customdata=np.stack([agg['refunds'], agg['orders']], axis=-1),
            hovertemplate='<b>%{y}</b><br>Refund rate: %{x:.2f}%<br>'
                          'Refunds: %{customdata[0]:,} of %{customdata[1]:,} orders<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Refund Rate by Operator (≥200 orders, Top 10)"),
                      xaxis_title=_tt("Refund rate (%)"), yaxis_title=None,
                      margin=dict(l=10, r=70, t=50, b=10), height=420)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def orders_country_chart():
        df = filtered_data()
        if 'country' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        co = df.groupby('country', observed=True)['order_id'].nunique().nlargest(10).reset_index()
        co = co.sort_values('order_id')
        fig = go.Figure(go.Bar(
            x=co['order_id'], y=co['country'], orientation='h',
            marker=dict(color=co['order_id'], colorscale=T.SCALE_SEQUENTIAL, showscale=False),
            text=[T.format_int(v) for v in co['order_id']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Top 10 countries by orders"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def orders_segment_chart():
        df = filtered_data()
        if 'segment' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        so = df.groupby('segment', observed=True)['order_id'].nunique().reset_index()
        fig = go.Figure(go.Bar(
            x=so['segment'], y=so['order_id'],
            marker=dict(color=T.PALETTE[:len(so)], line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in so['order_id']],
            textposition='outside', textfont=dict(size=12, color="#334155"),
            hovertemplate='<b>%{x}</b><br>Orders: %{y:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Orders by segment"),
                      xaxis_title=None, yaxis_title=_tt("Orders"), showlegend=False)
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def orders_by_country_table():
        df = filtered_data()
        if {'country', 'segment', 'order_id'}.issubset(df.columns):
            orders_table = df.groupby(['country', 'segment'])['order_id'].nunique().unstack(fill_value=0)
            orders_table['Total'] = orders_table.sum(axis=1)
            orders_table = orders_table.sort_values('Total', ascending=False)
            return orders_table.reset_index()
        return pd.DataFrame()

    # ------------------------------------------------------------------
    # Country growth + potential (period-over-period)
    # ------------------------------------------------------------------
    @render.ui
    @safe_render
    def country_growth_table():
        df = mi_filtered_data()
        _compare = list(input.mi_compare_countries() or [])
        prev = previous_period_data()
        if _compare:
            prev = prev[prev['country'].astype(str).isin(_compare)]
        if 'country' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        cur = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate'])
        prv = prev.groupby('country', observed=True)['sales'].sum().mul(currency['rate'])
        # Convert CategoricalIndex to plain string before concat to avoid int16 buffer dtype mismatch
        cur.index = cur.index.astype(str)
        prv.index = prv.index.astype(str)
        # Combine into a single frame
        gdf = pd.concat([cur.rename('current'), prv.rename('previous')], axis=1).fillna(0).reset_index()
        gdf['country'] = gdf['country'].astype(str)
        gdf = gdf[(gdf['current'] > 0) | (gdf['previous'] > 0)]
        # Coerce to plain float to avoid object-dtype contamination from category levels
        gdf['current']  = pd.to_numeric(gdf['current'],  errors='coerce')
        gdf['previous'] = pd.to_numeric(gdf['previous'], errors='coerce')
        # Only consider countries with meaningful prior volume to avoid 0 -> any = ∞
        prev_q25 = float(gdf['previous'].quantile(0.25)) if len(gdf) else 0.0
        meaningful = gdf['previous'] >= max(100.0, prev_q25)
        # Use np.nan (not pd.NA) so the column stays float64 and supports nlargest/nsmallest
        prev_safe = gdf['previous'].replace(0, np.nan)
        gdf['growth_pct'] = ((gdf['current'] - gdf['previous']) / prev_safe) * 100.0
        gdf['growth_pct'] = pd.to_numeric(gdf['growth_pct'], errors='coerce')
        gdf_meaningful = gdf[meaningful].dropna(subset=['growth_pct'])
        risers = gdf_meaningful.nlargest(10, 'growth_pct')
        decliners = gdf_meaningful.nsmallest(10, 'growth_pct')
        # New markets (prev = 0, current > threshold)
        new_markets = gdf[(gdf['previous'] == 0) & (gdf['current'] > 100)].nlargest(5, 'current')

        def _pill(value, color):
            return ui.tags.span(
                value,
                style=f"display:inline-block; padding:3px 10px; border-radius:999px;"
                      f"background:{color}15; color:{color}; font-weight:600; font-size:0.85em;"
            )

        def _row_table(title, frame, color, icon, value_label):
            if frame.empty:
                return ui.div(
                    ui.tags.h5(f"{icon} {title}"),
                    ui.p("No qualifying countries in this period.", style="color:#64748B; font-size:0.85em;"),
                    style="flex: 1 1 33%; min-width: 280px;"
                )
            rows = []
            for _, r in frame.iterrows():
                v = T.format_pct(r.get('growth_pct')) if 'growth_pct' in frame.columns else T.format_number(r['current'], currency['symbol'])
                rows.append(ui.tags.tr(
                    ui.tags.td(r['country'], style="padding:7px 10px; font-weight:500; color:#0F172A;"),
                    ui.tags.td(T.format_number(r['current'], currency['symbol']),
                               style="padding:7px 10px; color:#475569; text-align:right; font-variant-numeric: tabular-nums;"),
                    ui.tags.td(_pill(v, color),
                               style="padding:7px 10px; text-align:right;"),
                ))
            return ui.div(
                ui.tags.h5(f"{icon} {title}", style="color:#0F172A; margin-bottom:8px;"),
                ui.tags.table(
                    ui.tags.thead(ui.tags.tr(
                        ui.tags.th("Country", style="text-align:left; padding:8px 10px; font-size:0.78em; color:#64748B; text-transform:uppercase; letter-spacing:0.5px;"),
                        ui.tags.th("Current", style="text-align:right; padding:8px 10px; font-size:0.78em; color:#64748B; text-transform:uppercase; letter-spacing:0.5px;"),
                        ui.tags.th(value_label, style="text-align:right; padding:8px 10px; font-size:0.78em; color:#64748B; text-transform:uppercase; letter-spacing:0.5px;"),
                    )),
                    ui.tags.tbody(*rows),
                    style="width:100%; border-collapse:collapse; background:#FAFAFA; border-radius:8px; overflow:hidden;"
                ),
                style="flex: 1 1 33%; min-width: 280px;"
            )

        return ui.div(
            _row_table("Top 10 risers", risers, T.SUCCESS, "🚀", "Growth"),
            _row_table("Top 10 decliners", decliners, T.DANGER, "📉", "Change"),
            _row_table("New markets", new_markets, T.INFO, "✨", "Sales"),
            style="display:flex; gap:16px; flex-wrap:wrap;"
        )

    @render.ui
    @safe_render
    def country_potential_scatter():
        df = mi_filtered_data()
        if not {'country', 'sales', 'order_id'}.issubset(df.columns):
            return _no_data()
        currency = currency_converter()
        grp = df.groupby('country', observed=True)
        agg = pd.DataFrame({'sales': grp['sales'].sum(),
                            'orders': grp['order_id'].nunique()}).reset_index()
        agg = agg[(agg['sales'] > 0) & (agg['orders'] > 0)]
        if agg.empty:
            return _no_data()
        agg['sales'] = agg['sales'] * currency['rate']
        agg['aov'] = agg['sales'] / agg['orders']
        agg = agg.nlargest(40, 'sales')  # focus on countries that actually move the needle
        median_orders = agg['orders'].median()
        median_aov    = agg['aov'].median()
        fig = go.Figure(go.Scatter(
            x=agg['orders'], y=agg['aov'],
            mode='markers+text',
            marker=dict(
                size=(agg['sales'] / agg['sales'].max() * 60 + 8),
                color=agg['sales'], colorscale=T.SCALE_SEQUENTIAL,
                showscale=True,
                colorbar=dict(title=dict(text=f"Sales ({currency['symbol']})", font=dict(size=11)), thickness=12, len=0.6),
                line=dict(color='white', width=1.5),
                opacity=0.85,
            ),
            text=agg['country'],
            textposition='top center', textfont=dict(size=10, color="#334155"),
            hovertemplate=('<b>%{text}</b><br>'
                          'Orders: %{x:,}<br>'
                          'AOV: ' + currency['symbol'] + '%{y:,.2f}<br>'
                          'Total Sales: ' + currency['symbol'] + '%{marker.color:,.0f}<extra></extra>'),
        ))
        # Quadrant guide lines
        fig.add_hline(y=median_aov, line_dash="dot", line_color="#94A3B8", opacity=0.6,
                      annotation_text=f"Median AOV {currency['symbol']}{median_aov:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(size=10, color="#64748B"))
        fig.add_vline(x=median_orders, line_dash="dot", line_color="#94A3B8", opacity=0.6,
                      annotation_text=f"Median orders {median_orders:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(size=10, color="#64748B"))
        T.apply_theme(fig, title=_tt("Country potential matrix · top 40 countries by sales"),
                      xaxis_title=_tt("Orders"), yaxis_title=_tt(f"Avg order value ({currency['symbol']})"),
                      xaxis_type="log", yaxis_type="log",
                      margin=dict(l=10, r=10, t=50, b=10), height=540)
        return ui.HTML(T.fig_to_html(fig))

    # ------------------------------------------------------------------
    # Phase 1.2 — Country Expansion Radar
    # Classifies each country into a 2x2 quadrant based on Orders × AOV
    # versus the median across all visible countries. Each quadrant has an
    # explicit business label and a top-5 list.
    # ------------------------------------------------------------------
    @reactive.Calc
    def expansion_radar_data():
        df = mi_filtered_data()
        if not {'country', 'sales', 'order_id'}.issubset(df.columns):
            return None
        currency = currency_converter()
        grp = df.groupby('country', observed=True)
        agg = pd.DataFrame({'sales': grp['sales'].sum(),
                            'orders': grp['order_id'].nunique()}).reset_index()
        agg = agg[(agg['sales'] > 0) & (agg['orders'] > 0)]
        if agg.empty:
            return None
        agg['sales'] = agg['sales'] * currency['rate']
        agg['aov'] = agg['sales'] / agg['orders']
        # Focus on countries that matter — top 60 by sales
        agg = agg.nlargest(60, 'sales').reset_index(drop=True)
        median_orders = float(agg['orders'].median())
        median_aov    = float(agg['aov'].median())

        def _quadrant(row):
            high_orders = row['orders'] >= median_orders
            high_aov    = row['aov']    >= median_aov
            if high_orders and high_aov:
                return "Stronghold"
            if high_orders and not high_aov:
                return "Upsell target"
            if (not high_orders) and high_aov:
                return "Expansion target"
            return "Long tail"

        agg['quadrant'] = agg.apply(_quadrant, axis=1)
        return {
            'frame': agg,
            'median_orders': median_orders,
            'median_aov': median_aov,
            'currency': currency,
        }

    QUAD_COLORS = {
        "Stronghold":       "#10B981",   # green
        "Upsell target":    "#F59E0B",   # amber
        "Expansion target": "#5B6CFF",   # primary blue
        "Long tail":        "#94A3B8",   # slate
    }

    @render.ui
    @safe_render
    def country_expansion_radar():
        data = expansion_radar_data()
        if data is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No country data in current selection.</div>')
        agg = data['frame']
        currency = data['currency']
        sym = currency['symbol']
        median_orders = data['median_orders']
        median_aov    = data['median_aov']

        fig = go.Figure()
        for quad, color in QUAD_COLORS.items():
            d = agg[agg['quadrant'] == quad]
            if d.empty:
                continue
            fig.add_trace(go.Scatter(
                x=d['orders'], y=d['aov'],
                mode='markers+text',
                name=quad,
                marker=dict(
                    size=(d['sales'] / agg['sales'].max() * 55 + 10),
                    color=color,
                    line=dict(color='white', width=1.5),
                    opacity=0.88,
                ),
                text=d['country'],
                textposition='top center',
                textfont=dict(size=9, color="#334155"),
                customdata=d['sales'],
                hovertemplate=('<b>%{text}</b><br>'
                              'Quadrant: ' + quad + '<br>'
                              'Orders: %{x:,}<br>'
                              'AOV: ' + sym + '%{y:,.2f}<br>'
                              'Total sales: ' + sym + '%{customdata:,.0f}<extra></extra>'),
            ))
        # Quadrant guide lines
        fig.add_hline(y=median_aov, line_dash="dot", line_color="#94A3B8", opacity=0.6,
                      annotation_text=f"Median AOV {sym}{median_aov:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(size=10, color="#64748B"))
        fig.add_vline(x=median_orders, line_dash="dot", line_color="#94A3B8", opacity=0.6,
                      annotation_text=f"Median orders {median_orders:,.0f}",
                      annotation_position="top right",
                      annotation_font=dict(size=10, color="#64748B"))
        # Quadrant labels (top-right of each quadrant region)
        for quad, color in QUAD_COLORS.items():
            d = agg[agg['quadrant'] == quad]
            if d.empty: continue
            quad_label = {
                "Stronghold":       "STRONGHOLDS · defend share",
                "Upsell target":    "UPSELL TARGETS · push higher denoms",
                "Expansion target": "EXPANSION TARGETS · invest in marketing",
                "Long tail":        "LONG TAIL · deprioritise",
            }[quad]
            fig.add_annotation(
                xref="x", yref="y",
                x=(agg['orders'].max() if "Upsell" in quad or "Stronghold" in quad else median_orders * 0.5),
                y=(agg['aov'].max() if "Stronghold" in quad or "Expansion" in quad else median_aov * 0.5),
                text=f"<i>{quad_label}</i>",
                showarrow=False,
                font=dict(size=10, color=color),
                opacity=0.55,
                xanchor='right' if "Upsell" in quad or "Stronghold" in quad else 'left',
                yanchor='top' if "Stronghold" in quad or "Expansion" in quad else 'bottom',
            )
        T.apply_theme(fig, title=_tt("Country expansion radar · classified by Orders × AOV"),
                      xaxis_title=_tt("Orders"), yaxis_title=_tt(f"Avg order value ({sym})"),
                      xaxis_type="log", yaxis_type="log",
                      margin=dict(l=10, r=10, t=50, b=10), height=560,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.18, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def country_expansion_quadrant_tables():
        data = expansion_radar_data()
        if data is None:
            return _no_data()
        agg = data['frame']
        sym = data['currency']['symbol']
        QUAD_DESC = [
            ("Stronghold",       "🏰", "Strongholds — defend share, deepen relationships"),
            ("Upsell target",    "📈", "Upsell targets — high volume but low AOV; push higher denominations"),
            ("Expansion target", "🚀", "Expansion targets — high AOV but low volume; invest in marketing"),
            ("Long tail",        "🪶", "Long tail — deprioritise unless growing fast"),
        ]
        sections = []
        for quad, icon, desc in QUAD_DESC:
            d = agg[agg['quadrant'] == quad].nlargest(5, 'sales')
            color = QUAD_COLORS[quad]
            if d.empty:
                rows = [ui.tags.tr(ui.tags.td("—", colspan=4,
                                              style="padding:10px; color:#94A3B8; text-align:center;"))]
            else:
                rows = []
                for _, r in d.iterrows():
                    rows.append(ui.tags.tr(
                        ui.tags.td(r['country'],
                                   style="padding:7px 10px; font-weight:500;"),
                        ui.tags.td(T.format_int(r['orders']),
                                   style="padding:7px 10px; text-align:right; font-variant-numeric:tabular-nums;"),
                        ui.tags.td(T.format_number(r['aov'], sym),
                                   style="padding:7px 10px; text-align:right; font-variant-numeric:tabular-nums;"),
                        ui.tags.td(T.format_number(r['sales'], sym),
                                   style="padding:7px 10px; text-align:right; font-variant-numeric:tabular-nums; color:#475569;"),
                    ))
            sections.append(ui.div(
                ui.tags.h5(
                    ui.tags.span(icon, style="margin-right:6px;"),
                    quad,
                    style=f"color:{color}; border-bottom:2px solid {color}; padding-bottom:6px; margin:0 0 8px 0;"
                ),
                ui.tags.p(desc, style="font-size:0.78em; color:#64748B; margin:0 0 10px 0;"),
                ui.tags.table(
                    ui.tags.thead(ui.tags.tr(
                        ui.tags.th("Country",  style="text-align:left; padding:6px 10px; font-size:0.74em; color:#64748B; text-transform:uppercase;"),
                        ui.tags.th("Orders",   style="text-align:right; padding:6px 10px; font-size:0.74em; color:#64748B; text-transform:uppercase;"),
                        ui.tags.th("AOV",      style="text-align:right; padding:6px 10px; font-size:0.74em; color:#64748B; text-transform:uppercase;"),
                        ui.tags.th("Sales",    style="text-align:right; padding:6px 10px; font-size:0.74em; color:#64748B; text-transform:uppercase;"),
                    )),
                    ui.tags.tbody(*rows),
                    style="width:100%; border-collapse:collapse; background:#FAFAFA; border-radius:8px; overflow:hidden;"
                ),
                style="flex: 1 1 45%; min-width: 320px; margin-bottom: 16px;"
            ))
        return ui.div(*sections, style="display:flex; gap:16px; flex-wrap:wrap;")

    # ------------------------------------------------------------------
    # Phase 2 — Compare tab
    #   period_a_data / period_b_data: filtered DataFrames for the two date
    #   windows. Sidebar segment/region/country filters DO apply; the only
    #   thing the Compare tab overrides is the date range.
    # ------------------------------------------------------------------
    def _filter_by_compare_range(df, date_range):
        if not date_range or len(date_range) != 2 or 'order_time' not in df.columns:
            return df.iloc[0:0]
        start = pd.to_datetime(date_range[0], errors='coerce')
        end   = pd.to_datetime(date_range[1], errors='coerce')
        if pd.isna(start) or pd.isna(end):
            return df.iloc[0:0]
        if start > end:
            start, end = end, start
        return df[(df['order_time'].dt.date >= start.date()) &
                  (df['order_time'].dt.date <= end.date())]

    def _filter_by_sidebar(df):
        seg = applied_segment()
        reg = applied_region()
        ctr = applied_country()
        if seg and seg != "All":
            df = df[df['segment'] == seg]
        if 'region' in df.columns and reg and reg != "All":
            df = df[df['region'] == reg]
        df = _filter_by_country(df, ctr)
        return filter_by_order_status(df, applied_order_status())

    @reactive.Calc
    def period_a_data():
        df = _filter_by_sidebar(data_rv())
        return _filter_by_compare_range(df, input.compare_a())

    @reactive.Calc
    def period_b_data():
        df = _filter_by_sidebar(data_rv())
        return _filter_by_compare_range(df, input.compare_b())

    @reactive.Effect
    @reactive.event(input.compare_swap, ignore_init=True)
    def swap_compare_periods():
        a = input.compare_a()
        b = input.compare_b()
        if a and b and len(a) == 2 and len(b) == 2:
            ui.update_date_range("compare_a", start=b[0], end=b[1], session=session)
            ui.update_date_range("compare_b", start=a[0], end=a[1], session=session)

    def _compare_kpi_card(label, a_val, b_val, sym, value_formatter=None, lower_is_better=False):
        if value_formatter is None:
            value_formatter = lambda v: T.format_number(v, sym)
        delta_abs = (a_val or 0) - (b_val or 0)
        delta_pct = ((a_val - b_val) / b_val * 100.0) if b_val else None
        if delta_pct is None:
            color, arrow = T.NEUTRAL, "•"
        else:
            up = delta_pct > 0
            if lower_is_better:
                color = T.SUCCESS if not up else T.DANGER
            else:
                color = T.SUCCESS if up else (T.DANGER if delta_pct < 0 else T.NEUTRAL)
            arrow = "▲" if up else ("▼" if delta_pct < 0 else "▬")
        delta_pct_str = T.format_pct(delta_pct) if delta_pct is not None else "—"
        delta_abs_str = value_formatter(delta_abs)
        return ui.tags.div(
            ui.tags.div(label,
                        style="font-size: 0.78em; color: #64748B; text-transform: uppercase; "
                              "letter-spacing: 0.5px; font-weight: 600; margin-bottom: 8px;"),
            ui.tags.div(
                ui.tags.div(
                    ui.tags.div("Period A", style="font-size:0.72em; color:#5B6CFF; font-weight:600;"),
                    ui.tags.div(value_formatter(a_val),
                                style="font-size: 1.3em; font-weight: 700; color: #0F172A;"),
                    style="flex: 1 1 50%;"
                ),
                ui.tags.div(
                    ui.tags.div("Period B", style="font-size:0.72em; color:#94A3B8; font-weight:600;"),
                    ui.tags.div(value_formatter(b_val),
                                style="font-size: 1.1em; color: #64748B;"),
                    style="flex: 1 1 50%;"
                ),
                style="display:flex; gap:8px; margin-bottom: 8px;"
            ),
            ui.tags.div(
                ui.tags.span(f"{arrow} {delta_pct_str}",
                             style=f"color:{color}; font-weight:700; font-size:0.95em; margin-right:8px;"),
                ui.tags.span(f"({'+' if delta_abs >= 0 else ''}{delta_abs_str})",
                             style="color:#64748B; font-size:0.85em;"),
            ),
            style=("flex: 1 1 22%; min-width: 200px; padding: 16px; border-radius: 12px;"
                   "background: white; border: 1px solid #E2E8F0;"
                   "box-shadow: 0 1px 3px rgba(15,23,42,0.04);"
                   "border-top: 3px solid #5B6CFF;")
        )

    @render.ui
    @safe_render
    def compare_kpis():
        a = period_a_data()
        b = period_b_data()
        currency = currency_converter()
        rate = currency['rate']
        sym = currency['symbol']

        def _aggs(df):
            if df.empty:
                return dict(sales=0, orders=0, users=0, aov=0, margin=0, margin_pct=0)
            sales  = float(df['sales'].sum() * rate) if 'sales' in df.columns else 0
            orders = int(df['order_id'].nunique()) if 'order_id' in df.columns else len(df)
            users  = int(df['user_id'].dropna().nunique()) if 'user_id' in df.columns else 0
            aov    = sales / orders if orders > 0 else 0
            _sc = _settle_col(df)
            cost   = float(df[_sc].sum() * rate) if _sc in df.columns else 0
            margin = sales - cost
            margin_pct = (margin / sales * 100) if sales > 0 else 0
            return dict(sales=sales, orders=orders, users=users, aov=aov,
                        margin=margin, margin_pct=margin_pct)

        A = _aggs(a)
        B = _aggs(b)

        return ui.tags.div(
            _compare_kpi_card("Sales", A['sales'], B['sales'], sym),
            _compare_kpi_card("Orders", A['orders'], B['orders'], sym, value_formatter=T.format_int),
            _compare_kpi_card("Users", A['users'], B['users'], sym, value_formatter=T.format_int),
            _compare_kpi_card("AOV", A['aov'], B['aov'], sym),
            _compare_kpi_card("Margin", A['margin'], B['margin'], sym),
            _compare_kpi_card("Margin %", A['margin_pct'], B['margin_pct'], "",
                              value_formatter=lambda v: T.format_pct(v)),
            style="display: flex; flex-wrap: wrap; gap: 12px;"
        )

    @render.ui
    @safe_render
    def compare_trend_chart():
        a = period_a_data()
        b = period_b_data()
        if a.empty and b.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No data in selected periods.</div>')
        currency = currency_converter()
        rate = currency['rate']
        sym = currency['symbol']

        def _series(df, label):
            if df.empty or 'order_time' not in df.columns:
                return pd.DataFrame(columns=['day_offset', 'sales', 'date', 'label'])
            g = df.groupby(df['order_time'].dt.date)['sales'].sum().mul(rate).reset_index()
            g.columns = ['date', 'sales']
            g['date'] = pd.to_datetime(g['date'])
            g = g.sort_values('date').reset_index(drop=True)
            g['day_offset'] = (g['date'] - g['date'].min()).dt.days
            g['label'] = label
            return g

        sa = _series(a, "Period A")
        sb = _series(b, "Period B")

        fig = go.Figure()
        if not sa.empty:
            fig.add_trace(go.Scatter(
                x=sa['day_offset'], y=sa['sales'], name=_tt("Period A"),
                mode='lines+markers',
                line=dict(color=T.PRIMARY, width=2.5, shape='spline'),
                marker=dict(size=6, color=T.PRIMARY, line=dict(color='white', width=1.5)),
                customdata=sa['date'].dt.strftime('%Y-%m-%d'),
                hovertemplate='<b>Period A</b><br>Day %{x}<br>Date %{customdata}<br>Sales: ' + sym + '%{y:,.0f}<extra></extra>',
            ))
        if not sb.empty:
            fig.add_trace(go.Scatter(
                x=sb['day_offset'], y=sb['sales'], name=_tt("Period B"),
                mode='lines+markers',
                line=dict(color="#94A3B8", width=2.0, shape='spline', dash='dot'),
                marker=dict(size=5, color="#94A3B8", line=dict(color='white', width=1.5)),
                customdata=sb['date'].dt.strftime('%Y-%m-%d'),
                hovertemplate='<b>Period B</b><br>Day %{x}<br>Date %{customdata}<br>Sales: ' + sym + '%{y:,.0f}<extra></extra>',
            ))
        T.apply_theme(fig, title=_tt("Daily sales · aligned by day-of-period"),
                      xaxis_title=_tt("Day within period (0 = first day)"),
                      yaxis_title=_tt(f"Sales ({sym})"),
                      hovermode='x unified',
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    def _compare_movers(level, top_n=10):
        a = period_a_data()
        b = period_b_data()
        if level not in data_rv().columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate = currency['rate']
        ra = (a.groupby(level, observed=True)['sales'].sum() * rate) if not a.empty else pd.Series(dtype=float)
        rb = (b.groupby(level, observed=True)['sales'].sum() * rate) if not b.empty else pd.Series(dtype=float)
        idx = sorted(set(ra.index.astype(str)) | set(rb.index.astype(str)))
        out = pd.DataFrame({
            'entity':   idx,
            'period_a': [float(ra.get(e, 0.0)) for e in idx],
            'period_b': [float(rb.get(e, 0.0)) for e in idx],
        })
        out['delta_abs'] = out['period_a'] - out['period_b']
        base_safe = out['period_b'].replace(0, np.nan)
        out['delta_pct'] = (out['delta_abs'] / base_safe) * 100.0
        return out

    def _mover_table(level_name, level_col, top_n=10):
        d = _compare_movers(level_col, top_n=top_n)
        if d.empty:
            return ui.div(
                ui.tags.h5(level_name, style="color:#0F172A; margin-bottom:8px;"),
                ui.p("No data.", style="color:#94A3B8; font-style:italic;"),
                style="flex: 1 1 31%; min-width: 280px;"
            )
        sym = currency_converter()['symbol']
        rising  = d.nlargest(top_n // 2, 'delta_abs')
        falling = d.nsmallest(top_n // 2, 'delta_abs')

        def _rows(frame, label_color):
            rows = []
            for _, r in frame.iterrows():
                delta = r['delta_abs']
                color = T.SUCCESS if delta > 0 else (T.DANGER if delta < 0 else T.NEUTRAL)
                pct = r['delta_pct']
                pct_str = T.format_pct(pct) if pct is not None and not pd.isna(pct) else ""
                rows.append(ui.tags.tr(
                    ui.tags.td(r['entity'], style="padding:6px 10px; font-weight:500; color:#0F172A;"),
                    ui.tags.td(T.format_number(r['period_a'], sym),
                               style="padding:6px 10px; text-align:right; font-variant-numeric:tabular-nums; color:#475569;"),
                    ui.tags.td(
                        ui.tags.span(f"{'+' if delta >= 0 else ''}{T.format_number(delta, sym)}",
                                     style=f"color:{color}; font-weight:600;"),
                        ui.tags.span(f" ({pct_str})", style="color:#64748B; font-size:0.85em; margin-left:4px;") if pct_str else "",
                        style="padding:6px 10px; text-align:right; font-variant-numeric:tabular-nums;"
                    ),
                ))
            return rows

        return ui.div(
            ui.tags.h5(level_name, style="color:#0F172A; margin-bottom:8px;"),
            ui.tags.div("▲ Risers", style="font-size:0.78em; color:" + T.SUCCESS + "; font-weight:600; margin-top:4px; margin-bottom:4px;"),
            ui.tags.table(ui.tags.tbody(*_rows(rising, T.SUCCESS)),
                          style="width:100%; border-collapse:collapse; font-size:0.88em; background:#FAFAFA; border-radius:6px;"),
            ui.tags.div("▼ Decliners", style="font-size:0.78em; color:" + T.DANGER + "; font-weight:600; margin-top:10px; margin-bottom:4px;"),
            ui.tags.table(ui.tags.tbody(*_rows(falling, T.DANGER)),
                          style="width:100%; border-collapse:collapse; font-size:0.88em; background:#FAFAFA; border-radius:6px;"),
            style="flex: 1 1 31%; min-width: 280px;"
        )

    @render.ui
    @safe_render
    def compare_movers_tables():
        return ui.div(
            _mover_table("🌍 Countries", "country", top_n=10),
            _mover_table("🤝 Operators", "operator", top_n=10),
            _mover_table("🔢 Denominations", "denomination", top_n=10),
            style="display:flex; gap:16px; flex-wrap:wrap;"
        )

    @render.ui
    @safe_render
    def country_month_heatmap():
        df = mi_filtered_data()
        if not {'country', 'sales', 'order_time'}.issubset(df.columns):
            return _no_data()
        currency = currency_converter()
        d = df.copy()
        d['month'] = d['order_time'].dt.to_period('M').astype(str)
        sales = d.groupby(['country', 'month'], observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        top_countries = sales.groupby('country', observed=True)['sales'].sum().nlargest(15).index
        sales = sales[sales['country'].isin(top_countries)]
        pivot = sales.pivot(index='country', columns='month', values='sales').fillna(0)
        # Sort countries by overall total
        pivot = pivot.loc[pivot.sum(axis=1).sort_values(ascending=False).index]
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=T.SCALE_SEQUENTIAL, showscale=True,
            colorbar=dict(title=dict(text=f"Sales ({currency['symbol']})", font=dict(size=11)), thickness=12, len=0.7),
            hovertemplate='%{y} · %{x}<br>Sales: ' + currency['symbol'] + '%{z:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Monthly sales heatmap · top 15 countries · {currency['label']}"),
                      xaxis_title=None, yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def country_sales_chart():
        df = mi_filtered_data()
        if 'country' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        cs = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        cs = cs.sort_values('sales', ascending=True).tail(15)
        fig = charts.topn_hbar(
            values=cs['sales'], labels=cs['country'],
            title=_tt(f"Top 15 countries by sales · {currency['label']}"),
            xaxis_title=_tt(f"Sales ({currency['symbol']})"),
            hover_label='Sales: ' + currency['symbol'] + '%{x:,.0f}',
            value_text=[T.format_number(v, currency['symbol']) for v in cs['sales']])
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def country_world_map():
        """Choropleth of total sales by country for the selected period."""
        df = mi_filtered_data()
        if 'country' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        cs = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        cs['iso3'] = cs['country'].map(T.to_iso3)
        cs = cs.dropna(subset=['iso3'])
        if cs.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No mappable countries in current selection.</div>')
        fig = go.Figure(go.Choropleth(
            locations=cs['iso3'], z=cs['sales'], locationmode='ISO-3',
            text=cs['country'],
            colorscale=T.SCALE_SEQUENTIAL,
            colorbar=dict(title=dict(text=f"Sales ({currency['symbol']})", font=dict(size=11)),
                          thickness=12, len=0.7),
            hovertemplate='<b>%{text}</b><br>Sales: ' + currency['symbol'] + '%{z:,.0f}<extra></extra>',
            marker_line_color='white', marker_line_width=0.5,
        ))
        T.apply_theme(fig, title=_tt(f"Sales by country · world map ({currency['label']})"),
                      margin=dict(l=0, r=0, t=50, b=0), height=520,
                      geo=dict(showframe=False, showcoastlines=False, projection_type='natural earth',
                               bgcolor='rgba(0,0,0,0)', landcolor='#F1F5F9', showcountries=True,
                               countrycolor='#E2E8F0'))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def country_orders_by_segment_chart():
        df = mi_filtered_data()
        if not {'country', 'segment', 'order_id'}.issubset(df.columns):
            return _no_data()
        co = df.groupby(['country', 'segment'], observed=True)['order_id'].nunique().reset_index()
        top_c = co.groupby('country', observed=True)['order_id'].sum().nlargest(10).index
        co = co[co['country'].isin(top_c)]
        fig = px.bar(co, x='country', y='order_id', color='segment',
                     barmode='stack', color_discrete_sequence=T.PALETTE)
        fig.update_traces(marker_line_color='white', marker_line_width=1.0,
                          hovertemplate='<b>%{x}</b><br>%{fullData.name}: %{y:,}<extra></extra>')
        T.apply_theme(fig, title=_tt("Top 10 countries · orders by segment"),
                      xaxis_title=None, yaxis_title=_tt("Orders"), barmode='stack')
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def country_orders_chart():
        df = mi_filtered_data()
        if 'country' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        co = df.groupby('country', observed=True)['order_id'].nunique().nlargest(15).reset_index()
        co = co.sort_values('order_id')
        fig = charts.topn_hbar(
            values=co['order_id'], labels=co['country'],
            title=_tt("Top 15 countries by orders"), xaxis_title=_tt("Orders"),
            hover_label='Orders: %{x:,}',
            value_text=[T.format_int(v) for v in co['order_id']])
        return ui.HTML(T.fig_to_html(fig))

    # ── New: Market Intelligence additions ───────────────────────────────────

    @render.ui
    @safe_render
    def country_aov_chart():
        df = mi_filtered_data()
        if 'country' not in df.columns or 'sales' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = df.groupby('country', observed=True)
        agg = pd.DataFrame({'sales': grp['sales'].sum(),
                            'orders': grp['order_id'].nunique()}).reset_index()
        agg['aov'] = (agg['sales'] * rate) / agg['orders'].replace(0, np.nan)
        agg = agg.dropna(subset=['aov']).nlargest(15, 'aov').sort_values('aov', ascending=True)
        if agg.empty:
            return _no_data()
        fig = charts.topn_hbar(
            values=agg['aov'], labels=agg['country'], color_line=True,
            title=_tt(f"Average Order Value (AOV) by Market · Top 15 · {currency['label']}"),
            xaxis_title=_tt(f"AOV ({sym})"),
            hover_label='AOV: ' + sym + '%{x:,.2f}',
            value_text=[T.format_number(v, sym) for v in agg['aov']])
        return ui.HTML(T.fig_to_html(fig))

    # ── New: Operational Intelligence additions ───────────────────────────────

    @render.ui
    @safe_render
    def ops_kpis():
        df = filtered_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        if 'order_time' not in df.columns or 'sales' not in df.columns:
            return _no_data()

        df2 = df.copy()
        df2['date'] = df2['order_time'].dt.date
        df2['hour'] = df2['order_time'].dt.hour
        _dgrp = df2.groupby('date')
        daily = pd.DataFrame({'sales': _dgrp['sales'].sum(),
                              'orders': _dgrp['order_id'].nunique()}).reset_index()
        daily['sales'] = daily['sales'] * rate
        n_days = len(daily)
        avg_daily_rev = daily['sales'].mean() if n_days > 0 else 0
        avg_daily_ord = daily['orders'].mean() if n_days > 0 else 0
        peak_day = str(daily.loc[daily['sales'].idxmax(), 'date']) if n_days > 0 else "—"
        hourly = df2.groupby('hour')['order_id'].nunique()
        peak_hour = int(hourly.idxmax()) if not hourly.empty else 0

        return ui.tags.div(
            _kpi_card("📅", "sales-icon", _bl("Avg Daily Revenue (GMV)", "日均收入 (GMV)"),
                      T.format_full(avg_daily_rev, sym), None,
                      f"Over {n_days} active days",
                      "Average daily Gross Merchandise Value for the selected period."),
            _kpi_card("📦", "orders-icon", _bl("Avg Daily Order Volume", "日均订单量"),
                      f"{avg_daily_ord:,.1f}", None,
                      "Orders per trading day",
                      "Average number of orders placed per day in the selected period."),
            _kpi_card("🏆", "users-icon", _bl("Peak Revenue Day", "最高收入日"),
                      str(peak_day), None,
                      "Highest single-day GMV",
                      "The calendar date with the highest single-day revenue."),
            _kpi_card("⏰", "countries-icon", _bl("Peak Order Hour", "高峰下单时段"),
                      f"{peak_hour:02d}:00 – {peak_hour+1:02d}:00", None,
                      "Hour with most orders (UTC+8 MYT)",
                      "The hour of the day with the highest order volume."),
            style="display: flex; flex-wrap: wrap; gap: 12px;"
        )

    @render.ui
    @safe_render
    def daily_delta_chart():
        df = filtered_data()
        if 'order_time' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        df2 = df.copy()
        df2['date'] = df2['order_time'].dt.date
        daily = df2.groupby('date')['sales'].sum().mul(rate).reset_index()
        daily = daily.sort_values('date')
        daily['pct_change'] = daily['sales'].pct_change() * 100
        daily = daily.dropna(subset=['pct_change'])
        if daily.empty:
            return ui.HTML('<div style="color:#64748B; padding:20px;">Insufficient data for day-over-day comparison.</div>')
        colors = [T.SUCCESS if v >= 0 else T.DANGER for v in daily['pct_change']]
        fig = go.Figure(go.Bar(
            x=daily['date'], y=daily['pct_change'],
            marker=dict(color=colors, line=dict(width=0)),
            hovertemplate='<b>%{x}</b><br>Day-over-Day Change: %{y:.1f}%<extra></extra>',
        ))
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color="#94A3B8")
        T.apply_theme(fig, title=_tt("Day-over-Day Revenue Change (%)"),
                      xaxis_title=None, yaxis_title=_tt("Change (%)"),
                      showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def daily_sales_trend():
        df = filtered_data()
        if 'order_time' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        period = applied_trend_period() or "Daily"
        period_freq = {"Daily": None, "Weekly": "W", "Monthly": "M", "Quarterly": "Q", "Yearly": "Y"}
        if period == "Daily":
            grouped = df.groupby(df['order_time'].dt.date)
        else:
            grouped = df.groupby(df['order_time'].dt.to_period(period_freq[period]).dt.start_time)
        daily = pd.DataFrame({'sales': grouped['sales'].sum(),
                              'orders': grouped['order_id'].nunique()}).reset_index()
        daily['sales'] = daily['sales'] * currency['rate']
        # Dual axis chart
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=daily['order_time'], y=daily['orders'], name=_tt('Orders'),
            marker=dict(color='rgba(139,92,246,0.55)', line=dict(width=0)),
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Orders: %{y:,}<extra></extra>',
            yaxis='y',
        ))
        fig.add_trace(go.Scatter(
            x=daily['order_time'], y=daily['sales'], name=_tt('Sales'),
            mode='lines+markers',
            line=dict(color=T.PRIMARY, width=2.5, shape='spline'),
            marker=dict(size=5, color=T.PRIMARY, line=dict(color='white', width=1)),
            hovertemplate='<b>%{x|%Y-%m-%d}</b><br>Sales: ' + currency['symbol'] + '%{y:,.0f}<extra></extra>',
            yaxis='y2',
        ))
        T.apply_theme(fig, title=_tt(f"{period} sales (line) vs orders (bars)"),
                      xaxis_title=None, yaxis_title=_tt("Orders"),
                      yaxis2=dict(title=_tt(f"Sales ({currency['symbol']})"), overlaying='y',
                                  side='right', showgrid=False),
                      hovermode='x unified', margin=dict(l=10, r=60, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def weekday_sales_chart():
        df = filtered_data()
        if 'order_time' not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        df = df.assign(weekday=df['order_time'].dt.day_name(), hour=df['order_time'].dt.hour)
        heatmap = df.groupby(['weekday', 'hour'], observed=True)['order_id'].nunique().reset_index()
        weekday_order = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
        # Build a 7x24 matrix
        pivot = heatmap.pivot(index='weekday', columns='hour', values='order_id').reindex(weekday_order)
        pivot = pivot.reindex(columns=range(24), fill_value=0)
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=[f"{h:02d}:00" for h in pivot.columns], y=pivot.index,
            colorscale=T.SCALE_SEQUENTIAL, showscale=True,
            colorbar=dict(title=dict(text="Orders", font=dict(size=11)), thickness=12, len=0.7),
            hovertemplate='%{y} · %{x}<br>Orders: %{z:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("When customers buy · weekday × hour"),
                      xaxis_title=_tt("Hour of day"), yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    # ── Iraq Pinstore Inventory Planner ────────────────────────────────────────

    @reactive.Calc
    def _iraq_pinstore_base():
        """Iraq Pinstore PIN orders. Uses full session data (data_rv) for accurate projections."""
        df = data_rv()
        if df is None or df.empty:
            return None
        if 'country' not in df.columns:
            return None
        iraq = df[df['country'].astype(str).str.strip().str.lower() == 'iraq'].copy()
        if iraq.empty:
            return None
        pin_mask = pd.Series(False, index=iraq.index)
        if 'product' in iraq.columns:
            pin_mask = pin_mask | iraq['product'].astype(str).str.strip().str.upper().str.endswith('PIN')
        if 'product_info' in iraq.columns:
            pin_mask = pin_mask | iraq['product_info'].astype(str).str.strip().str.upper().str.endswith('PIN')
        df_pin = iraq[pin_mask].copy()
        if df_pin.empty:
            return None
        # Unified SKU name: prefer product (B2C), fallback to product_info (B2B)
        if 'product' in df_pin.columns and 'product_info' in df_pin.columns:
            b2c_mask = df_pin['product'].astype(str).str.strip().str.upper().str.endswith('PIN')
            df_pin['pin_product'] = df_pin['product'].astype(str).str.strip()
            df_pin.loc[~b2c_mask, 'pin_product'] = (
                df_pin.loc[~b2c_mask, 'product_info'].astype(str).str.strip()
            )
        elif 'product' in df_pin.columns:
            df_pin['pin_product'] = df_pin['product'].astype(str).str.strip()
        elif 'product_info' in df_pin.columns:
            df_pin['pin_product'] = df_pin['product_info'].astype(str).str.strip()
        else:
            df_pin['pin_product'] = 'Unknown PIN'
        if 'order_time' in df_pin.columns:
            df_pin['week_start'] = df_pin['order_time'].dt.to_period('W').dt.start_time
        return df_pin

    @render.ui
    @safe_render
    def iraq_pinstore_kpis():
        df = _iraq_pinstore_base()
        if df is None:
            return ui.p(
                "No Iraq Pinstore PIN orders found. "
                "Ensure Iraq orders with products ending in 'PIN' (e.g. AsiaCell PIN) exist in the database.",
                style="color:#64748B; padding:12px 0;"
            )
        if 'week_start' not in df.columns:
            return ui.p("Order date column unavailable — cannot calculate weekly estimates.",
                        style="color:#64748B; padding:12px 0;")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        today = pd.Timestamp.now().normalize()
        c4  = today - pd.Timedelta(weeks=4)
        c12 = today - pd.Timedelta(weeks=12)
        r4  = df[df['week_start'] >= c4]
        r12 = df[df['week_start'] >= c12]
        if r4.empty:
            r4 = df
        if r12.empty:
            r12 = df
        ord_col = 'order_id' if 'order_id' in df.columns else None
        w4  = (r4.groupby('week_start')[ord_col].nunique() if ord_col else r4.groupby('week_start').size())
        w12 = (r12.groupby('week_start')[ord_col].nunique() if ord_col else r12.groupby('week_start').size())
        avg4  = float(w4.mean())  if not w4.empty  else 0.0
        avg12 = float(w12.mean()) if not w12.empty else 0.0
        next_wk  = avg4 * 1.15
        monthly  = avg4 * 4.33 * 1.10
        rev4     = r4['sales'].sum() * rate if 'sales' in r4.columns else 0.0
        wkly_rev = rev4 / max(len(w4), 1)
        return ui.tags.div(
            _kpi_card("📦", "orders-icon", _bl("Avg Weekly Orders (4-wk)", "周均订单量（近4周）"),
                      f"{avg4:,.0f}", None,
                      f"12-wk avg: {avg12:,.0f}",
                      "Rolling 4-week average of Iraq Pinstore PIN orders per week."),
            _kpi_card("🛒", "sales-icon", _bl("Next Week Purchase Est.", "下周采购建议量"),
                      f"{next_wk:,.0f}", None,
                      "+15% safety buffer on 4-wk avg",
                      "Recommended qty to purchase next week = 4-wk rolling avg × 1.15."),
            _kpi_card("📅", "countries-icon", _bl("Monthly Purchase Est.", "月度采购建议量"),
                      f"{monthly:,.0f}", None,
                      "+10% buffer · 4.33 wks/month",
                      "Monthly projection = 4-wk avg × 4.33 weeks/month × 1.10."),
            _kpi_card("💰", "supplier-icon", _bl("Avg Weekly Revenue", "周均收入"),
                      T.format_full(wkly_rev, sym), None,
                      "Iraq Pinstore orders · last 4 weeks",
                      "Average weekly GMV from Iraq Pinstore PIN orders over the last 4 weeks."),
            style="display:flex; flex-wrap:wrap; gap:12px;"
        )

    @render.ui
    @safe_render
    def iraq_pinstore_trend_chart():
        df = _iraq_pinstore_base()
        if df is None or 'week_start' not in df.columns:
            return ui.HTML('<div style="color:#64748B;padding:16px;">No Iraq PIN data available.</div>')
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(weeks=12)
        recent = df[df['week_start'] >= cutoff].copy()
        if recent.empty:
            recent = df.copy()
        ord_col = 'order_id' if 'order_id' in recent.columns else None
        if ord_col:
            agg = (recent.groupby(['week_start', 'pin_product'], observed=True)[ord_col]
                   .nunique().reset_index(name=_tt('orders')))
        else:
            agg = (recent.groupby(['week_start', 'pin_product'], observed=True)
                   .size().reset_index(name=_tt('orders')))
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:16px;">No data to chart.</div>')
        fig = px.bar(agg, x='week_start', y='orders', color='pin_product',
                     barmode='group', color_discrete_sequence=T.PALETTE)
        fig.update_traces(
            marker=dict(line=dict(color='white', width=1)),
            hovertemplate='<b>%{fullData.name}</b><br>Week of %{x|%d %b %Y}<br>Orders: %{y:,}<extra></extra>'
        )
        total_wk = agg.groupby('week_start')['orders'].sum().reset_index().sort_values('week_start')
        total_wk['rolling4'] = total_wk['orders'].rolling(4, min_periods=1).mean()
        fig.add_trace(go.Scatter(
            x=total_wk['week_start'], y=total_wk['rolling4'],
            name=_tt('4-wk Rolling Avg'),
            mode='lines+markers',
            line=dict(color='#EF4444', width=2.5, dash='dash'),
            marker=dict(size=6, symbol='circle', line=dict(color='white', width=1.5)),
            hovertemplate='<b>4-wk Rolling Avg</b><br>Week of %{x|%d %b %Y}<br>Avg: %{y:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt("Iraq Pinstore — Weekly PIN Order Volume by SKU (Last 12 Weeks)"),
                      xaxis_title=_tt("Week Starting"), yaxis_title=_tt("Orders"),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="left", x=0),
                      height=420)
        return ui.HTML(T.fig_to_html(fig))

    def _iraq_pinstore_plan_data():
        """Returns purchase plan broken down by Operator × Denomination."""
        df = _iraq_pinstore_base()
        if df is None or 'pin_product' not in df.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        today    = pd.Timestamp.now().normalize()
        c4, c8, c12 = (today - pd.Timedelta(weeks=w) for w in (4, 8, 12))
        ord_col  = 'order_id' if 'order_id' in df.columns else None
        has_denom = 'denomination' in df.columns

        def _wk_avg(sub, cutoff):
            if 'week_start' not in sub.columns:
                return 0.0
            recent = sub[sub['week_start'] >= cutoff]
            if recent.empty:
                return 0.0
            wk = (recent.groupby('week_start')[ord_col].nunique() if ord_col
                  else recent.groupby('week_start').size())
            return float(wk.mean()) if not wk.empty else 0.0

        rows = []
        numeric = []
        group_keys = ['pin_product', 'denomination'] if has_denom else ['pin_product']
        for keys, sub in df.groupby(group_keys, observed=True):
            if has_denom:
                sku, denom = keys
            else:
                sku, denom = keys, None
            a4, a8, a12 = _wk_avg(sub, c4), _wk_avg(sub, c8), _wk_avg(sub, c12)
            nw = a4 * 1.15
            mo = a4 * 4.33 * 1.10
            r4_sub = sub[sub['week_start'] >= c4] if 'week_start' in sub.columns else sub.iloc[0:0]
            if 'sales' in sub.columns and not r4_sub.empty:
                total_rev4 = r4_sub['sales'].sum() * rate
                total_ord4 = r4_sub[ord_col].nunique() if ord_col else len(r4_sub)
                rpo = total_rev4 / max(total_ord4, 1)
            else:
                rpo = 0.0
            # Strip " PIN" suffix for a cleaner operator display name
            op_name = str(sku).strip()
            if op_name.upper().endswith(' PIN'):
                op_name = op_name[:-4].strip()
            row = {'Operator': op_name}
            if has_denom:
                try:
                    row['Denomination'] = f"{float(str(denom).replace(',', '')):,.0f}"
                except Exception:
                    row['Denomination'] = str(denom)
            row.update({
                'Avg Wkly (4w)':       f"{a4:.1f}",
                'Avg Wkly (8w)':       f"{a8:.1f}",
                'Avg Wkly (12w)':      f"{a12:.1f}",
                'Next Wk Rec. (+15%)': f"{nw:.0f}",
                'Monthly Est. (+10%)': f"{mo:.0f}",
                f'Unit Cost ({sym})':      f"{rpo:.4f}",
                f'Est. Wkly Cost ({sym})': f"{rpo * a4:,.2f}",
                f'Est. Mo. Cost ({sym})':  f"{rpo * a4 * 4.33:,.2f}",
            })
            rows.append(row)
            numeric.append({'a4': a4, 'a8': a8, 'a12': a12, 'nw': nw, 'mo': mo,
                            'wc': rpo * a4, 'mc': rpo * a4 * 4.33})
        if not rows:
            return pd.DataFrame()
        out = pd.DataFrame(rows)
        nr  = numeric
        total = {'Operator': '📊 GRAND TOTAL'}
        if has_denom:
            total['Denomination'] = ''
        total.update({
            'Avg Wkly (4w)':       f"{sum(r['a4'] for r in nr):,.1f}",
            'Avg Wkly (8w)':       f"{sum(r['a8'] for r in nr):,.1f}",
            'Avg Wkly (12w)':      f"{sum(r['a12'] for r in nr):,.1f}",
            'Next Wk Rec. (+15%)': f"{sum(r['nw'] for r in nr):,.0f}",
            'Monthly Est. (+10%)': f"{sum(r['mo'] for r in nr):,.0f}",
            f'Unit Cost ({sym})':      '',
            f'Est. Wkly Cost ({sym})': f"{sum(r['wc'] for r in nr):,.2f}",
            f'Est. Mo. Cost ({sym})':  f"{sum(r['mc'] for r in nr):,.2f}",
        })
        return pd.concat([out, pd.DataFrame([total])], ignore_index=True)

    @render.ui
    @safe_render
    def iraq_pinstore_denom_heatmap():
        df = _iraq_pinstore_base()
        if df is None or 'week_start' not in df.columns or 'denomination' not in df.columns:
            return ui.HTML('<div style="color:#64748B;padding:12px;">Denomination data not available.</div>')
        cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(weeks=12)
        recent = df[df['week_start'] >= cutoff].copy()
        if recent.empty:
            recent = df.copy()
        ord_col = 'order_id' if 'order_id' in recent.columns else None
        # Clean operator name for display
        def _clean_op(s):
            s = str(s).strip()
            return s[:-4].strip() if s.upper().endswith(' PIN') else s
        recent['op_denom'] = (recent['pin_product'].apply(_clean_op)
                              + ' — ' + recent['denomination'].astype(str))
        if ord_col:
            agg = (recent.groupby(['week_start', 'op_denom'], observed=True)[ord_col]
                   .nunique().reset_index(name=_tt('orders')))
        else:
            agg = (recent.groupby(['week_start', 'op_denom'], observed=True)
                   .size().reset_index(name=_tt('orders')))
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:12px;">No data.</div>')
        pivot = agg.pivot(index='op_denom', columns='week_start', values='orders').fillna(0)
        pivot.columns = [c.strftime('%b %d') for c in pivot.columns]
        fig = go.Figure(go.Heatmap(
            z=pivot.values,
            x=list(pivot.columns),
            y=list(pivot.index),
            colorscale=T.SCALE_SEQUENTIAL,
            showscale=True,
            colorbar=dict(title=dict(text="Orders", font=dict(size=11)), thickness=12, len=0.7),
            hovertemplate='<b>%{y}</b><br>Week of %{x}<br>Orders: %{z:,}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt("Iraq Pinstore — Weekly Orders per Operator × Denomination (Last 12 Weeks)"),
                      xaxis_title=_tt("Week"), yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10),
                      height=max(300, len(pivot) * 36 + 90))
        return ui.HTML(T.fig_to_html(fig))

    def _pinstore_days():
        """Stock horizon (days) from the radio + custom numeric input."""
        try:
            h = input.pinstore_horizon() or "7"
        except Exception:
            return 7
        if h == "custom":
            try:
                d = int(input.pinstore_days() or 7)
            except Exception:
                d = 7
            return max(1, min(60, d))
        return int(h)

    def _pinstore_matrix_data():
        """Pieces to purchase per operator (rows) × denomination (cols) for the
        chosen number of days of stock. Returns (matrix_df, budget_rmb)."""
        df = _iraq_pinstore_base()
        if df is None or 'pin_product' not in df.columns or 'denomination' not in df.columns:
            return pd.DataFrame(), 0.0
        if 'order_time' not in df.columns:
            return pd.DataFrame(), 0.0
        days = _pinstore_days()
        ord_col = 'order_id' if 'order_id' in df.columns else None

        d = df.copy()
        d['op'] = d['pin_product'].astype(str).str.replace(r'\s*PIN$', '', regex=True).str.strip()
        max_dt = d['order_time'].max()
        recent = d[d['order_time'] >= max_dt - pd.Timedelta(days=28)]
        window_days = 28
        if recent.empty:
            recent = d
            span = (d['order_time'].max() - d['order_time'].min()).days
            window_days = max(span, 1)

        grp = recent.groupby(['op', 'denomination'], observed=True)
        cnt = (grp[ord_col].nunique() if ord_col else grp.size()).reset_index(name='orders')
        if cnt.empty:
            return pd.DataFrame(), 0.0
        cnt['pieces'] = np.ceil(cnt['orders'] / window_days * days * 1.10).astype(int)

        # Budget: pieces × median settlement_rmb per (op, denom)
        budget = 0.0
        sc = _settle_col(recent)
        if sc in recent.columns:
            med = grp[sc].median().reset_index(name='unit_cost')
            cnt = cnt.merge(med, on=['op', 'denomination'], how='left')
            budget = float((cnt['pieces'] * cnt['unit_cost'].fillna(0)).sum())

        # Pivot to operator × denomination matrix
        cnt['denom_label'] = cnt['denomination'].map(_clean_denom_label)
        cnt['denom_label'] = cnt['denom_label'].where(
            cnt['denom_label'].astype(str).str.strip() != "", cnt['denomination'].astype(str))
        pivot = cnt.pivot_table(index='op', columns='denomination', values='pieces',
                                aggfunc='sum', observed=True).fillna(0)
        # numeric denomination ordering for columns
        col_order = sorted(pivot.columns, key=_denom_sort_key)
        pivot = pivot.reindex(columns=col_order)
        label_map = {c: (_clean_denom_label(c) or str(c)) for c in pivot.columns}
        pivot.columns = [label_map[c] for c in pivot.columns]
        pivot = pivot.astype(int)
        pivot['TOTAL'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('TOTAL', ascending=False)
        total_row = pivot.sum(axis=0)
        total_row.name = '📊 TOTAL'
        out = pd.concat([pivot, pd.DataFrame([total_row])])
        out = out.reset_index().rename(columns={'index': 'Operator', 'op': 'Operator'})
        return out, budget

    @render.ui
    @safe_render
    def pinstore_budget_note():
        out, budget = _pinstore_matrix_data()
        if out.empty:
            return ui.HTML('')
        days = _pinstore_days()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        total_pieces = int(out.loc[out['Operator'] == '📊 TOTAL', 'TOTAL'].iloc[0]) \
            if 'TOTAL' in out.columns and (out['Operator'] == '📊 TOTAL').any() else 0
        budget_disp = budget * rate
        return ui.HTML(
            f'<div style="background:#EEF2FF;border-left:4px solid #4F46E5;padding:10px 14px;'
            f'border-radius:8px;margin-bottom:10px;font-size:0.9em;color:#3730A3;">'
            f'🛒 <b>{days}-day stock plan</b>: purchase <b>{total_pieces:,} pieces</b> total · '
            f'estimated cost <b>{T.format_number(budget_disp, sym)}</b> '
            f'(recent 28-day velocity × {days}d × 1.10 buffer)</div>')

    @render.data_frame
    @safe_grid
    def pinstore_purchase_matrix():
        out, _budget = _pinstore_matrix_data()
        if out.empty:
            return render.DataGrid(pd.DataFrame(
                {'Status': ['No Iraq Pinstore PIN data found in the current selection.']}))
        return render.DataGrid(_tdf(out), filters=False, width="100%")

    @render.download(filename=lambda: f"Iraq_Pinstore_Purchase_Plan_{pd.Timestamp.now().strftime('%Y-%m-%d')}.xlsx")
    def download_iraq_pinstore_plan():
        yield _xlsx_bytes(_iraq_pinstore_plan_data())

    # ── New: Supplier & Operator Performance additions ────────────────────────

    @render.ui
    @safe_render
    def supplier_concentration_card():
        df = filtered_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        operator_col = 'operator' if 'operator' in df.columns else None
        if operator_col is None or 'sales' not in df.columns:
            return _no_data()
        op_sales = df.groupby(operator_col, observed=True)['sales'].sum().mul(rate).sort_values(ascending=False)
        if op_sales.empty:
            return _no_data()
        total = op_sales.sum()
        top1_pct = op_sales.iloc[0] / total * 100 if total > 0 else 0
        top3_pct = op_sales.head(3).sum() / total * 100 if total > 0 else 0
        n_ops = len(op_sales)

        if top3_pct >= 80:
            risk_color, risk_label = T.DANGER, "HIGH RISK"
        elif top3_pct >= 60:
            risk_color, risk_label = T.WARNING, "MODERATE"
        else:
            risk_color, risk_label = T.SUCCESS, "LOW RISK"

        top1_name = op_sales.index[0] if len(op_sales) > 0 else "—"
        return ui.tags.div(
            _kpi_card("⚠️", "sales-icon", "Supplier Concentration Risk",
                      risk_label, None,
                      f"Top operator ({top1_name}): {top1_pct:.1f}% of GMV",
                      f"Revenue concentration risk: {top3_pct:.1f}% of GMV from top 3 of {n_ops} operators. "
                      "High >80%, Moderate 60-80%, Low <60%."),
            _kpi_card("🏆", "orders-icon", f"Top 3 Operator Share",
                      f"{top3_pct:.1f}%", None,
                      f"of total GMV from {n_ops} operators",
                      "If top 3 operators account for >80% of GMV, consider supplier diversification."),
            style="display: flex; flex-wrap: wrap; gap: 12px;"
        )

    @render.ui
    @safe_render
    def supplier_margin_pct_trend():
        df = filtered_data()
        if 'operator' not in df.columns or 'order_time' not in df.columns:
            return _no_data()
        if _settle_col(df) not in df.columns or 'sales' not in df.columns:
            return ui.HTML('<div style="color:#64748B; padding:20px;">Settlement price data not available for margin % trend.</div>')
        currency = currency_converter()
        rate = currency['rate']
        d = df.copy()
        d['month'] = d['order_time'].dt.to_period('M').dt.start_time
        _mgrp = d.groupby(['month', 'operator'], observed=True)
        agg = pd.DataFrame({'sales': _mgrp['sales'].sum(),
                            'settle': _mgrp[_settle_col(d)].sum()}).reset_index()
        agg['sales'] = agg['sales'] * rate
        agg['settle'] = agg['settle'] * rate
        agg['margin_pct'] = ((agg['sales'] - agg['settle']) / agg['sales'].replace(0, np.nan) * 100).round(2)
        agg = agg.dropna(subset=['margin_pct'])
        if agg.empty:
            return _no_data()
        top_ops = agg.groupby('operator', observed=True)['sales'].sum().nlargest(6).index.tolist()
        agg = agg[agg['operator'].isin(top_ops)]
        fig = px.line(agg, x='month', y='margin_pct', color='operator',
                      markers=True, color_discrete_sequence=T.PALETTE)
        fig.update_traces(line=dict(width=2.5, shape='spline'),
                          marker=dict(size=7, line=dict(color='white', width=1)),
                          hovertemplate='<b>%{fullData.name}</b><br>%{x|%b %Y}: %{y:.1f}% Gross Margin<extra></extra>')
        fig.add_hline(y=0, line_width=1, line_dash="dot", line_color=T.DANGER,
                      annotation_text="Break-even", annotation_position="right")
        T.apply_theme(fig, title=_tt("Gross Margin % Trend by Operator (Top 6)"),
                      xaxis_title=None, yaxis_title=_tt("Gross Margin (%)"),
                      hovermode='x unified', height=420,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def operator_sales_chart():
        df = filtered_data()
        operator_col = 'operator' if 'operator' in df.columns else 'country'
        if operator_col not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        os_ = df.groupby(operator_col, observed=True)['sales'].sum().mul(currency['rate']).nlargest(10).reset_index()
        os_ = os_.sort_values('sales')
        fig = go.Figure(go.Bar(
            x=os_['sales'], y=os_[operator_col], orientation='h',
            marker=dict(color=os_['sales'], colorscale=T.SCALE_SEQUENTIAL, showscale=False),
            text=[T.format_number(v, currency['symbol']) for v in os_['sales']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Sales: ' + currency['symbol'] + '%{x:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Top 10 operators by sales · {currency['label']}"),
                      xaxis_title=_tt(f"Sales ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def operator_orders_chart():
        df = filtered_data()
        operator_col = 'operator' if 'operator' in df.columns else 'country'
        if operator_col not in df.columns or 'order_id' not in df.columns:
            return _no_data()
        oo = df.groupby(operator_col, observed=True)['order_id'].nunique().nlargest(10).reset_index()
        oo = oo.sort_values('order_id')
        fig = go.Figure(go.Bar(
            x=oo['order_id'], y=oo[operator_col], orientation='h',
            marker=dict(color=oo['order_id'], colorscale=T.SCALE_SEQUENTIAL, showscale=False),
            text=[T.format_int(v) for v in oo['order_id']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Top 10 operators by orders"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    # ------------------------------------------------------------------
    # Supplier Insights (operator-level negotiation data)
    # ------------------------------------------------------------------
    @render.ui
    @safe_render
    def supplier_kpis():
        df = filtered_data()
        if 'operator' not in df.columns:
            return ui.p("Operator data not available.", style="color:#64748B;")
        currency = currency_converter()
        rate = currency['rate']
        sym = currency['symbol']

        total_sales = df['sales'].sum() * rate if 'sales' in df.columns else 0
        total_settle = (df[_settle_col(df)].sum() * rate) if _settle_col(df) in df.columns else 0
        margin = total_sales - total_settle if total_settle > 0 else None
        margin_pct = (margin / total_sales * 100) if margin is not None and total_sales > 0 else None
        n_ops = df['operator'].dropna().astype(str).replace('', pd.NA).dropna().nunique()
        # Platform-wide supplier count (configured constant — operator column is more granular)
        n_suppliers_all = _KNOWN_SUPPLIER_COUNT
        # Concentration: share of top 3 operators
        op_sales = df.groupby('operator', observed=True)['sales'].sum().sort_values(ascending=False)
        top3_share = (op_sales.head(3).sum() / op_sales.sum() * 100) if op_sales.sum() > 0 else 0

        return ui.tags.div(
            _kpi_card("🏢", "supplier-icon", _bl("Total Suppliers", "供应商总数"),
                      str(_KNOWN_SUPPLIER_COUNT), None,
                      f"{T.format_int(n_ops)} active in current filter",
                      "Total distinct supplier companies on the platform (fixed at 16)."),
            _kpi_card("🤝", "users-icon", _bl("Active Operators", "活跃运营商"),
                      T.format_int(n_ops), None,
                      "Operators with sales in selected period",
                      "Operators with at least one order in the selected period."),
            _kpi_card("💰", "sales-icon", _bl("Gross Margin", "毛利润"),
                      T.format_full(margin, sym) if margin is not None else "N/A", None,
                      T.format_pct(margin_pct) + " of sales" if margin_pct is not None else "Settlement price missing",
                      "Total sales − total settlement price (the cost paid to operators)."),
            _kpi_card("🥧", "orders-icon", _bl("Top-3 Concentration", "前3集中度"),
                      T.format_pct(top3_share), None,
                      "Share of sales from top 3 operators",
                      "Revenue concentration risk — higher means dependency on fewer suppliers."),
            _kpi_card("📦", "countries-icon", _bl("Operator AOV", "运营商 AOV"),
                      T.format_full(total_sales / max(df['order_id'].nunique(), 1), sym), None,
                      "Across all operators",
                      "Average order value across all operators in the selected period."),
            style="display: flex; flex-wrap: nowrap; justify-content: space-between; gap: 12px; overflow-x: auto;"
        )

    @render.ui
    @safe_render
    def supplier_margin_chart():
        df = filtered_data()
        if 'operator' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        _ogrp = df.groupby('operator', observed=True)
        agg = pd.DataFrame({
            'sales':  _ogrp['sales'].sum(),
            'settle': _ogrp[_settle_col(df)].sum() if _settle_col(df) in df.columns else _ogrp['sales'].sum(),
        }).reset_index()
        agg = agg[(agg['sales'] > 0)].nlargest(15, 'sales')
        agg['sales'] = agg['sales'] * currency['rate']
        agg['settle'] = agg['settle'] * currency['rate']
        agg['margin'] = agg['sales'] - agg['settle']
        agg['margin_pct'] = (agg['margin'] / agg['sales'] * 100).fillna(0)
        agg = agg.sort_values('sales')

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['settle'], y=agg['operator'], orientation='h',
            name=_tt('Cost (settlement)'),
            marker=dict(color='rgba(148,163,184,0.55)', line=dict(color='white', width=1)),
            hovertemplate='<b>%{y}</b><br>Cost: ' + currency['symbol'] + '%{x:,.0f}<extra></extra>',
        ))
        fig.add_trace(go.Bar(
            x=agg['margin'], y=agg['operator'], orientation='h',
            name=_tt('Margin'),
            marker=dict(color=T.SUCCESS, line=dict(color='white', width=1)),
            text=[T.format_pct(p) for p in agg['margin_pct']],
            textposition='outside', textfont=dict(size=11, color="#0F172A"),
            hovertemplate='<b>%{y}</b><br>Margin: ' + currency['symbol'] + '%{x:,.0f}<br>Margin %: %{text}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Top 15 operators · cost vs margin · {currency['label']}"),
                      barmode='stack',
                      xaxis_title=_tt(f"Sales ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=520,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def supplier_pareto():
        df = filtered_data()
        if 'operator' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        op = df.groupby('operator', observed=True)['sales'].sum().mul(currency['rate'])
        op = op[op > 0].sort_values(ascending=False).head(20).reset_index()
        op.columns = ['operator', 'sales']
        op['cum_share'] = (op['sales'].cumsum() / op['sales'].sum()) * 100

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=op['operator'], y=op['sales'],
            name=_tt('Sales'),
            marker=dict(color=op['sales'], colorscale=T.SCALE_SEQUENTIAL, showscale=False,
                        line=dict(color='white', width=1)),
            hovertemplate='<b>%{x}</b><br>Sales: ' + currency['symbol'] + '%{y:,.0f}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=op['operator'], y=op['cum_share'],
            name=_tt('Cumulative %'), mode='lines+markers', yaxis='y2',
            line=dict(color=T.DANGER, width=2.5, shape='spline'),
            marker=dict(size=6, color=T.DANGER, line=dict(color='white', width=1.5)),
            hovertemplate='<b>%{x}</b><br>Cumulative: %{y:.1f}%<extra></extra>',
        ))
        fig.add_hline(y=80, line_dash="dot", line_color="#94A3B8", yref="y2",
                      annotation_text="80%", annotation_position="bottom right",
                      annotation_font=dict(size=10, color="#64748B"))
        T.apply_theme(fig, title=_tt(f"Pareto · top 20 operators · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Sales ({currency['symbol']})"),
                      yaxis2=dict(title=_tt("Cumulative %"), overlaying='y', side='right',
                                  range=[0, 105], showgrid=False, ticksuffix="%"),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=60, t=60, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def supplier_trend():
        df = filtered_data()
        if not {'operator', 'sales', 'order_time'}.issubset(df.columns):
            return _no_data()
        currency = currency_converter()
        d = df.copy()
        d['month'] = d['order_time'].dt.to_period('M').dt.start_time
        # Limit to top-7 operators by total sales for readability
        top_ops = d.groupby('operator', observed=True)['sales'].sum().nlargest(7).index
        d = d[d['operator'].isin(top_ops)]
        s = (d.groupby(['month', 'operator'], observed=True)['sales'].sum()
                 .mul(currency['rate']).reset_index())
        fig = px.line(s, x='month', y='sales', color='operator',
                      color_discrete_sequence=T.PALETTE, markers=True)
        fig.update_traces(line=dict(width=2), marker=dict(size=6, line=dict(color='white', width=1)),
                          hovertemplate='<b>%{fullData.name}</b><br>%{x|%Y-%m}: ' + currency['symbol'] + '%{y:,.0f}<extra></extra>')
        T.apply_theme(fig, title=_tt(f"Operator volume trend · top 7 · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Sales ({currency['symbol']})"),
                      hovermode='x unified', height=420,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    def _supplier_scorecard_data():
        df = filtered_data()
        prev = previous_period_data()
        if 'operator' not in df.columns or 'sales' not in df.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate = currency['rate']

        _cgrp = df.groupby('operator', observed=True)
        cur = pd.DataFrame({
            'sales':  _cgrp['sales'].sum(),
            'orders': _cgrp['order_id'].nunique(),
            'settle': _cgrp[_settle_col(df)].sum() if _settle_col(df) in df.columns else _cgrp['sales'].sum(),
        }).reset_index()
        prv = prev.groupby('operator', observed=True)['sales'].sum().rename('prev_sales')
        m = cur.merge(prv, on='operator', how='left').fillna({'prev_sales': 0})

        # Use float math (np.nan instead of pd.NA) so .round(2) doesn't blow up.
        m['sales']     = pd.to_numeric(m['sales'], errors='coerce') * rate
        m['settle']    = pd.to_numeric(m['settle'], errors='coerce') * rate
        m['prev_sales'] = pd.to_numeric(m['prev_sales'], errors='coerce') * rate
        m['margin']    = m['sales'] - m['settle']
        sales_safe     = m['sales'].replace(0, np.nan)
        orders_safe    = m['orders'].replace(0, np.nan)
        prev_safe      = m['prev_sales'].replace(0, np.nan)
        m['margin_pct'] = (m['margin'] / sales_safe * 100).round(2)
        m['aov']        = (m['sales'] / orders_safe).round(2)
        m['growth_pct'] = ((m['sales'] - m['prev_sales']) / prev_safe * 100).round(2)
        total_sales = m['sales'].sum()
        m['share_pct'] = ((m['sales'] / total_sales * 100).round(2)
                          if total_sales > 0 else 0.0)
        m = m.rename(columns={
            'operator': 'Operator',
            'sales':    f'Sales ({currency["symbol"]})',
            'orders':   'Orders',
            'aov':      f'AOV ({currency["symbol"]})',
            'margin':   f'Margin ({currency["symbol"]})',
            'margin_pct': 'Margin %',
            'growth_pct': 'Growth %',
            'share_pct':  'Share %',
        }).drop(columns=['settle', 'prev_sales'])
        # Round only numeric columns — Operator names are text, and any
        # remaining NaNs survive without crashing.
        sales_col = f'Sales ({currency["symbol"]})'
        m = m.sort_values(sales_col, ascending=False).copy()
        currency_cols = [c for c in m.columns if currency["symbol"] in c]
        for col in currency_cols:
            m[col] = m[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        for col in ['Margin %', 'Growth %', 'Share %']:
            if col in m.columns:
                m[col] = m[col].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        int_cols = [c for c in m.select_dtypes(include=[np.number]).columns]
        for col in int_cols:
            m[col] = m[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        return m

    @render.data_frame
    @safe_grid
    def supplier_scorecard():
        return _supplier_scorecard_data()

    @render.download(filename=lambda: _make_filename("supplier_scorecard", "xlsx"))
    def download_supplier_scorecard():
        df = _supplier_scorecard_data()
        yield _xlsx_bytes(df)

    # ── Margin by Product Category ─────────────────────────────────────────────

    @render.ui
    @safe_render
    def margin_by_category_chart():
        df = filtered_data()
        if 'product_category' not in df.columns or 'sales' not in df.columns:
            return ui.HTML(
                '<div style="color:#64748B; padding:12px;">'
                'Gross margin by category requires <b>product_category</b> column.</div>'
            )
        if _settle_col(df) not in df.columns:
            return ui.HTML(
                '<div style="color:#64748B; padding:12px;">'
                'Settlement price data is not available — cannot calculate gross margin. '
                'Ensure settlement_price column is present in the source data.</div>'
            )
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        ord_col = 'order_id' if 'order_id' in df.columns else None
        _pgrp = df.groupby('product_category', observed=True)
        agg = pd.DataFrame({
            'revenue': _pgrp['sales'].sum(),
            'cost':    _pgrp[_settle_col(df)].sum(),
            'orders':  _pgrp[ord_col].nunique() if ord_col else _pgrp['sales'].count(),
        }).reset_index()
        agg['revenue'] = agg['revenue'] * rate
        agg['cost']    = agg['cost'] * rate
        agg['margin']  = agg['revenue'] - agg['cost']
        rev_safe       = agg['revenue'].replace(0, np.nan)
        agg['margin_pct'] = (agg['margin'] / rev_safe * 100).round(1)
        agg = agg[agg['revenue'] > 0].sort_values('revenue', ascending=False)
        if agg.empty:
            return ui.HTML('<div style="color:#64748B; padding:12px;">No product category data available.</div>')
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['product_category'], y=agg['cost'],
            name=_tt('Cost (Settlement)'),
            marker=dict(color='rgba(148,163,184,0.55)', line=dict(color='white', width=1)),
            hovertemplate='<b>%{x}</b><br>Cost: ' + sym + '%{y:,.0f}<extra></extra>',
        ))
        fig.add_trace(go.Bar(
            x=agg['product_category'], y=agg['margin'],
            name=_tt('Gross Margin'),
            marker=dict(color=T.SUCCESS, line=dict(color='white', width=1)),
            text=[f"{p:.1f}%" for p in agg['margin_pct']],
            textposition='outside',
            textfont=dict(size=12, color='#0F172A'),
            hovertemplate='<b>%{x}</b><br>Margin: ' + sym + '%{y:,.0f}<br>Margin %%: %{text}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt(f"Gross Margin by Product Category · {currency['label']}"),
                      barmode='stack',
                      xaxis_title=_tt('Product Category'),
                      yaxis_title=_tt(f'Revenue ({sym})'),
                      legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                      height=420)
        return ui.HTML(T.fig_to_html(fig))

    # ── Fulfillment & routing health (接口商订单号 / pin码 / useepay) ────────

    @render.ui
    @safe_render
    def fulfillment_kpis():
        df = filtered_base_calc()   # all statuses — gaps matter most on 'successful'
        if 'interface_order_id' not in df.columns:
            return _no_data("Supplier order-id data (接口商订单号) not loaded — click 'Refresh Cache' in the sidebar.")
        d = df.copy()
        iface = d['interface_order_id'].astype('string').str.strip()
        _null_like = {"", "--", "-", "nan", "none", "null", "n/a"}
        has_iface = iface.notna() & ~iface.str.lower().isin(_null_like)
        total = len(d)
        coverage = has_iface.mean() * 100 if total else 0
        succ_mask = (d['order_status'].astype(str).str.strip() == '充值成功') if 'order_status' in d.columns \
            else pd.Series(True, index=d.index)
        gap = d[succ_mask & ~has_iface]
        gap_orders = gap['order_id'].nunique() if 'order_id' in gap.columns else len(gap)
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        gap_gmv = float(gap['sales'].sum() * rate) if 'sales' in gap.columns else 0.0
        pin_share = None
        if 'pin_code' in d.columns:
            pin_share = d['pin_code'].notna().mean() * 100
        gateway_share = None
        if 'useepay_order_id' in d.columns and 'segment' in d.columns:
            b2c = d[d['segment'].astype(str) == 'B2C']
            if len(b2c):
                gateway_share = b2c['useepay_order_id'].notna().mean() * 100
        return ui.tags.div(
            _kpi_card("🔌", "orders-icon", _bl("Supplier Order-ID Coverage", "接口商订单号覆盖率"),
                      f"{coverage:.2f}%", None,
                      f"of {T.format_int(total)} orders carry a supplier reference",
                      "Orders with a supplier-side order id — required for reconciliation."),
            _kpi_card("⚠", "countries-icon", _bl("Unreconcilable Successful Orders", "无法对账的成功订单"),
                      T.format_int(gap_orders), None,
                      f"{T.format_number(gap_gmv, sym)} GMV at risk",
                      "Marked 充值成功 but missing 接口商订单号 — cannot be matched to supplier statements."),
            _kpi_card("🔢", "users-icon", _bl("PIN Delivery Share", "PIN码交付占比"),
                      f"{pin_share:.1f}%" if pin_share is not None else "—", None,
                      "Orders fulfilled by PIN code",
                      "Share of orders delivered as PIN codes rather than direct top-up."),
            _kpi_card("💳", "sales-icon", _bl("Useepay Gateway Share (B2C)", "Useepay支付占比 (B2C)"),
                      f"{gateway_share:.1f}%" if gateway_share is not None else "—", None,
                      "B2C orders carrying a useepay order id",
                      "Payment-gateway mix — share of B2C orders processed through Useepay."),
            class_="metrics-grid"
        )

    @render.ui
    @safe_render
    def routing_gap_chart():
        df = filtered_base_calc()
        if 'interface_order_id' not in df.columns or 'operator' not in df.columns:
            return _no_data("Needs 接口商订单号 and operator columns.")
        d = df.copy()
        iface = d['interface_order_id'].astype('string').str.strip()
        _null_like = {"", "--", "-", "nan", "none", "null", "n/a"}
        has_iface = iface.notna() & ~iface.str.lower().isin(_null_like)
        succ = (d['order_status'].astype(str).str.strip() == '充值成功') if 'order_status' in d.columns \
            else pd.Series(True, index=d.index)
        d['gap'] = ~has_iface
        d = d[succ].copy()
        d['operator'] = d['operator'].astype(str)
        grp = d.groupby('operator', observed=True)
        total_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        gap_d = d[d['gap']]
        gap_s = (gap_d.groupby('operator', observed=True)['order_id'].nunique()
                 if 'order_id' in d.columns else gap_d.groupby('operator', observed=True).size())
        gap_s = gap_s.reindex(total_s.index, fill_value=0)
        agg = pd.DataFrame({'orders': total_s, 'gaps': gap_s}).reset_index()
        agg = agg[agg['gaps'] > 0]
        if agg.empty:
            return ui.HTML('<div style="color:#10B981;padding:16px;">✔ Every successful order in the '
                           'current selection carries a supplier order id — no routing gaps.</div>')
        agg['gap_rate'] = agg['gaps'] / agg['orders'].replace(0, np.nan) * 100
        agg = agg.nlargest(12, 'gaps').sort_values('gaps')
        fig = go.Figure(go.Bar(
            x=agg['gaps'], y=agg['operator'], orientation='h',
            marker=dict(color=agg['gap_rate'], colorscale='Reds', showscale=False,
                        line=dict(color='white', width=1)),
            text=[f"{int(g):,} ({r:.1f}%)" for g, r in zip(agg['gaps'], agg['gap_rate'])],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Missing supplier id: %{x:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Successful Orders Missing Supplier Order ID — by Operator"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=110, t=50, b=10),
                      height=max(360, 30 * len(agg) + 110))
        return ui.HTML(T.fig_to_html(fig))

    # ── Settlement currency audit ─────────────────────────────────────────────

    def _settlement_audit_data():
        df = filtered_data()
        if 'settlement_rmb' not in df.columns or 'country' not in df.columns:
            return pd.DataFrame()
        d = df[df['settlement_rmb'].notna() & df['sales'].notna() & (df['sales'] > 0)].copy()
        if d.empty:
            return pd.DataFrame()
        d['country'] = d['country'].astype(str)
        d['settlement_currency'] = d['settlement_currency'].astype(str)
        grp = d.groupby(['country', 'settlement_currency'], observed=True)
        agg = pd.DataFrame({
            'orders':      grp['order_id'].nunique() if 'order_id' in d.columns else grp.size(),
            'sales_sum':   grp['sales'].sum(),
            'settle_sum':  grp['settlement_rmb'].sum(),
            'med_sales':   grp['sales'].median(),
            'med_settle_raw': grp['settlement_price'].median() if 'settlement_price' in d.columns else grp['settlement_rmb'].median(),
            'med_settle_rmb': grp['settlement_rmb'].median(),
        }).reset_index()
        agg = agg[agg['orders'] >= 50]
        if agg.empty:
            return pd.DataFrame()
        agg['margin_pct'] = (agg['sales_sum'] - agg['settle_sum']) / agg['sales_sum'] * 100
        agg['flag'] = np.where((agg['margin_pct'] < 0) | (agg['margin_pct'] > 60), '⚠', '')
        agg = agg.sort_values('orders', ascending=False)
        out = pd.DataFrame({
            'Country':                 agg['country'],
            'Settlement Currency':     agg['settlement_currency'],
            'Orders':                  agg['orders'].apply(lambda x: f"{int(x):,}"),
            'Median Sales (RMB)':      agg['med_sales'].apply(lambda x: f"{x:,.2f}"),
            'Median Settlement (raw)': agg['med_settle_raw'].apply(lambda x: f"{x:,.2f}"),
            'Median Settlement (RMB)': agg['med_settle_rmb'].apply(lambda x: f"{x:,.2f}"),
            'Margin %':                agg['margin_pct'].apply(lambda x: f"{x:,.1f}%"),
            'Check':                   agg['flag'],
        })
        return out

    @render.data_frame
    @safe_grid
    def settlement_audit_table():
        out = _settlement_audit_data()
        if out.empty:
            return render.DataGrid(pd.DataFrame(
                {'Status': ['Settlement data not available — click Refresh Cache in the sidebar.']}))
        return render.DataGrid(_tdf(out.head(80)), filters=True)

    @render.download(filename=lambda: _make_filename("settlement_currency_audit", "xlsx"))
    def download_settlement_audit():
        yield _xlsx_bytes(_settlement_audit_data())

    def _country_summary_data():
        df = mi_filtered_data()
        if 'country' not in df.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate = currency['rate']
        _cgrp = df.groupby('country', observed=True)
        _parts = {
            'Total Sales':     _cgrp['sales'].sum(),
            'Avg Transaction': _cgrp['sales'].mean(),
            'Total Orders':    _cgrp['order_id'].nunique(),
            'Unique Users':    _cgrp['user_id'].nunique(),
        }
        if _settle_col(df) in df.columns:
            _parts['Total Cost'] = _cgrp[_settle_col(df)].sum()
        summary = pd.DataFrame(_parts).reset_index().rename(columns={'country': 'Country'})
        summary['Total Sales']     = summary['Total Sales'] * rate
        summary['Avg Transaction'] = summary['Avg Transaction'] * rate
        summary['Avg Order Value'] = summary['Total Sales'] / summary['Total Orders'].replace(0, np.nan)
        summary['Orders per User'] = summary['Total Orders'] / summary['Unique Users'].replace(0, np.nan)
        total = summary['Total Sales'].sum()
        summary['Pct of Total Sales'] = (summary['Total Sales'] / total * 100).round(2) if total > 0 else 0
        if 'Total Cost' in summary.columns:
            summary['Total Cost']   = summary['Total Cost'] * rate
            summary['Gross Margin'] = summary['Total Sales'] - summary['Total Cost']
            rev_safe = summary['Total Sales'].replace(0, np.nan)
            summary['Margin %'] = (summary['Gross Margin'] / rev_safe * 100).round(1)
            cols = ['Country', 'Total Sales', 'Pct of Total Sales', 'Total Orders',
                    'Avg Order Value', 'Unique Users', 'Margin %']
        else:
            cols = ['Country', 'Total Sales', 'Pct of Total Sales', 'Total Orders',
                    'Avg Order Value', 'Unique Users']
        out = summary[cols].sort_values('Total Sales', ascending=False).copy()
        for col in ['Total Sales', 'Avg Order Value', 'Avg Transaction']:
            if col in out.columns:
                out[col] = out[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        out['Total Orders'] = out['Total Orders'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
        out['Unique Users'] = out['Unique Users'].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
        out['Pct of Total Sales'] = out['Pct of Total Sales'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        if 'Margin %' in out.columns:
            out['Margin %'] = out['Margin %'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        return out

    # ── Denomination AOV by Market ─────────────────────────────────────────────

    @render.ui
    @safe_render
    def denomination_aov_by_market():
        df = mi_filtered_data()
        if 'country' not in df.columns or 'denomination' not in df.columns:
            return ui.HTML(
                '<div style="color:#64748B; padding:12px;">'
                'Denomination and country columns are required for this chart.</div>'
            )
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        d = df.copy()
        d['denomination'] = pd.to_numeric(d['denomination'], errors='coerce')
        d = d.dropna(subset=['denomination'])
        if d.empty:
            return ui.HTML('<div style="color:#64748B; padding:12px;">No denomination data available.</div>')
        _dgrp = d.groupby('country', observed=True)
        agg = pd.DataFrame({
            'avg_denom': _dgrp['denomination'].mean(),
            'orders':    _dgrp['order_id'].nunique() if 'order_id' in d.columns else _dgrp['denomination'].count(),
            'revenue':   _dgrp['sales'].sum() if 'sales' in d.columns else _dgrp['denomination'].sum(),
        }).reset_index()
        agg['avg_denom'] = agg['avg_denom'] * rate
        agg = agg[agg['orders'] >= 10].nlargest(20, 'orders').sort_values('avg_denom', ascending=True)
        if agg.empty:
            return ui.HTML('<div style="color:#64748B; padding:12px;">Insufficient data (min 10 orders per market).</div>')
        fig = go.Figure(go.Bar(
            x=agg['avg_denom'], y=agg['country'],
            orientation='h',
            marker=dict(
                color=agg['avg_denom'],
                colorscale=T.SCALE_SEQUENTIAL,
                showscale=True,
                colorbar=dict(title=dict(text=f"Avg Denom ({sym})", font=dict(size=11)),
                              thickness=12, len=0.7),
                line=dict(color='white', width=1),
            ),
            text=[f"{sym}{v:,.1f}" for v in agg['avg_denom']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Avg Denomination: ' + sym + '%{x:,.1f}<br>Orders: %{customdata:,}<extra></extra>',
            customdata=agg['orders'],
        ))
        T.apply_theme(fig,
                      title=_tt(f"Avg Recharge Denomination by Market · {currency['label']} (min 10 orders)"),
                      xaxis_title=_tt(f"Avg Denomination ({sym})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def country_summary_table():
        return _tdf(_country_summary_data())

    @render.download(filename=lambda: _make_filename("country_summary", "xlsx"))
    def download_country_summary():
        yield _xlsx_bytes(_country_summary_data())

    # ── Destination & beneficiary analysis (区号 / 充值号码) ─────────────────

    @reactive.Calc
    def _destination_frame():
        df = filtered_data()
        if 'area_code' not in df.columns:
            return None
        d = df[df['area_code'].notna()].copy()
        if d.empty:
            return None
        d['dest_country'] = d['area_code'].map(T.calling_code_to_country)
        return d

    @render.ui
    @safe_render
    def destination_market_chart():
        d = _destination_frame()
        if d is None:
            return _no_data("Destination calling-code data (区号) not loaded — click 'Refresh Cache' in the sidebar.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = d.groupby('dest_country', observed=True)
        rev_s = grp['sales'].sum() * rate if 'sales' in d.columns else grp.size()
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = pd.DataFrame({'revenue': rev_s, 'orders': ord_s}).reset_index()
        agg = agg.nlargest(15, 'orders').sort_values('orders')
        fig = go.Figure(go.Bar(
            x=agg['orders'], y=agg['dest_country'], orientation='h',
            marker=dict(color=agg['orders'], colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in agg['orders']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            customdata=agg['revenue'],
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<br>Revenue: ' + sym +
                          '%{customdata:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Top 15 Recharge Destinations (by calling code)"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def destination_mismatch_chart():
        d = _destination_frame()
        if d is None:
            return _no_data("Destination calling-code data (区号) not available.")
        if 'country' not in d.columns:
            return _no_data("Billing country column not available.")
        d2 = d[d['country'].notna()].copy()
        _alias = {"United States": "USA", "Democratic Republic of the Congo": "DR Congo",
                  "Russia": "Russia/Kazakhstan", "Kazakhstan": "Russia/Kazakhstan",
                  "Canada": "USA/Canada"}
        d2['billing'] = d2['country'].astype(str).str.strip().replace(_alias)
        # Compare on country names where the calling-code map produced one
        known = ~d2['dest_country'].str.startswith('+', na=True)
        d2 = d2[known & (d2['dest_country'] != 'Unknown')]
        if d2.empty:
            return _no_data("No rows with a recognised destination country.")
        # Containment match tolerates combined labels like 'USA/Canada'
        d2['mismatch'] = [not (b in dc or dc in b)
                          for b, dc in zip(d2['billing'], d2['dest_country'])]
        mismatch_rate = d2['mismatch'].mean() * 100
        pairs = (d2[d2['mismatch']]
                 .groupby(['billing', 'dest_country'], observed=True).size()
                 .reset_index(name=_tt('orders'))
                 .nlargest(12, 'orders'))
        if pairs.empty:
            return ui.HTML(
                f'<div style="color:#10B981;padding:16px;">✔ No billing/destination mismatches — '
                f'all recharges land in the order market. (checked {len(d2):,} orders)</div>')
        pairs['label'] = pairs['billing'] + ' → ' + pairs['dest_country']
        pairs = pairs.sort_values('orders')
        fig = go.Figure(go.Bar(
            x=pairs['orders'], y=pairs['label'], orientation='h',
            marker=dict(color=T.INFO, line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in pairs['orders']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt(f"Cross-Border Recharges — order market → destination "
                                f"(mismatch rate {mismatch_rate:.1f}%)"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10),
                      height=max(380, 30 * len(pairs) + 110))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def beneficiary_analysis():
        df = filtered_data()
        if 'recharge_number' not in df.columns:
            return _no_data("Recharge-number data (充值号码) not loaded — click 'Refresh Cache' in the sidebar.")
        d = df[df['recharge_number'].notna()].copy()
        if d.empty:
            return _no_data("No recharge numbers in the current selection.")
        total_orders = d['order_id'].nunique() if 'order_id' in d.columns else len(d)
        uniq_numbers = d['recharge_number'].nunique()
        per_number = (d.groupby('recharge_number', observed=True)['order_id'].nunique()
                      if 'order_id' in d.columns
                      else d.groupby('recharge_number', observed=True).size())
        repeat_share = float((per_number > 1).mean() * 100)
        # B2C reseller signal: numbers recharged per user
        reseller_html = ""
        if 'user_id' in d.columns and 'segment' in d.columns:
            b2c = d[d['segment'].astype(str) == 'B2C']
            if not b2c.empty:
                npu = b2c.groupby('user_id', observed=True)['recharge_number'].nunique()
                many = int((npu >= 4).sum())
                reseller_html = (
                    f"{T.format_int(many)} B2C users recharge ≥4 different numbers — likely resellers"
                )
        buckets = pd.cut(per_number, bins=[0, 1, 2, 5, 10, float('inf')],
                         labels=['1 order', '2 orders', '3–5', '6–10', '>10']).astype(str)
        counts = buckets.value_counts().reindex(['1 order', '2 orders', '3–5', '6–10', '>10'],
                                                fill_value=0)
        fig = go.Figure(go.Bar(
            x=counts.index, y=counts.values,
            marker=dict(color=counts.values, colorscale=T.SCALE_SEQUENTIAL, showscale=False,
                        line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in counts.values], textposition='outside',
            hovertemplate='<b>%{x}</b><br>Numbers: %{y:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Recharges per Beneficiary Number"),
                      xaxis_title=_tt("Top-ups received"), yaxis_title=_tt("Unique numbers"),
                      height=360, margin=dict(l=10, r=10, t=50, b=10))
        kpis = ui.tags.div(
            _kpi_card("📱", "orders-icon", _bl("Unique Numbers Reached", "触达唯一号码数"),
                      T.format_int(uniq_numbers), None,
                      f"from {T.format_int(total_orders)} orders",
                      "Distinct phone numbers that received a recharge."),
            _kpi_card("🔁", "sales-icon", _bl("Numbers Recharged Again", "复充号码占比"),
                      f"{repeat_share:.1f}%", None,
                      "Share of numbers topped up more than once",
                      "End-beneficiary stickiness — repeat top-ups to the same number."),
            _kpi_card("🏪", "users-icon", _bl("Reseller Signal (B2C)", "代充信号 (B2C)"),
                      reseller_html.split(' ')[0] if reseller_html else "—", None,
                      reseller_html or "user_id/segment not available",
                      "B2C accounts recharging 4+ different numbers behave like resellers."),
            class_="metrics-grid"
        )
        return ui.tags.div(kpis, ui.HTML(T.fig_to_html(fig)))

    # ------------------------------------------------------------------
    # Mexico Focus tab — Telcel + operator comparison
    # Mexico-scoped. IGNORES applied_country (always Mexico) but respects
    # segment, currency, and date range.
    # ------------------------------------------------------------------
    def _mexico_label(value):
        """Display label for an operator, with NaN -> 'Other / Unspecified'."""
        s = ("" if value is None else str(value)).strip()
        if not s or s.lower() in {"nan", "none", "<na>"}:
            return "Other / Unspecified"
        return s

    # ── New: Product & Denomination Analysis additions ────────────────────────

    @render.ui
    @safe_render
    def product_revenue_trend():
        df = product_type_filtered_data()
        if 'product' not in df.columns or 'order_time' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        top5_products = df.groupby('product', observed=True)['sales'].sum().nlargest(5).index.tolist()
        d = df[df['product'].isin(top5_products)].copy()
        d['month'] = d['order_time'].dt.to_period('M').dt.start_time
        agg = d.groupby(['month', 'product'], observed=True)['sales'].sum().mul(rate).reset_index()
        if agg.empty:
            return _no_data()
        fig = px.line(agg, x='month', y='sales', color='product',
                      markers=True, color_discrete_sequence=T.PALETTE)
        fig.update_traces(line=dict(width=2.5, shape='spline'),
                          marker=dict(size=7, line=dict(color='white', width=1)),
                          hovertemplate='<b>%{fullData.name}</b><br>%{x|%b %Y}: ' +
                                        sym + '%{y:,.0f}<extra></extra>')
        T.apply_theme(fig, title=_tt(f"Top 5 Products — Monthly Revenue (GMV) Trend · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Revenue ({sym})"),
                      hovermode='x unified', height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.22, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def denomination_contribution_chart():
        df = product_type_filtered_data()
        if 'denomination' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        d = df.copy()
        d['denom_num'] = pd.to_numeric(d['denomination'].astype(str).str.extract(r'(\d+\.?\d*)')[0], errors='coerce')
        d = d.dropna(subset=['denom_num'])
        if d.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No numeric denomination data available.</div>')
        d['band'] = pd.cut(d['denom_num'], bins=[0, 10, 50, float('inf')],
                           labels=['Low (<10)', 'Mid (10–50)', 'High (>50)'])
        band_sales = d.groupby('band', observed=True)['sales'].sum().mul(rate)
        band_sales = band_sales[band_sales > 0]
        if band_sales.empty:
            return _no_data()
        total = band_sales.sum()
        fig = go.Figure(go.Pie(
            labels=band_sales.index.astype(str).tolist(),
            values=band_sales.values.tolist(),
            hole=0.55,
            marker=dict(colors=[T.SUCCESS, T.PRIMARY, T.DANGER], line=dict(color='white', width=2)),
            textinfo='label+percent', textfont=dict(size=12),
            hovertemplate='<b>%{label}</b><br>Revenue: ' + sym + '%{value:,.0f}<br>%{percent}<extra></extra>',
        ))
        fig.add_annotation(text=f"<b>By Band</b><br>{T.format_number(total, sym)}",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=13, color="#0F172A"))
        T.apply_theme(fig, title=_tt(f"Revenue Contribution by Denomination Band · {currency['label']}"),
                      showlegend=True, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5))
        return ui.HTML(T.fig_to_html(fig))

    # ── Data Package Volume Analysis ───────────────────────────────────────────

    def _parse_data_volume(name):
        """Parse a data-package SKU label like '50GB，28天' / '3.5G，30天' /
        '500MB' into (mb_float, label_str, days_int).

        - mb_float : data volume in MB (for tier binning + primary sort)
        - label_str: volume WITH validity period, e.g. '50GB · 28天'
        - days_int : validity in days for secondary sort (天/日→n, 周→n×7,
                     月/个月→n×30); None when no period token is present.
        """
        import re as _re_v
        s = str(name)

        # --- validity period (after the volume; tolerate a 有效期 prefix) ---
        days = None
        period_label = None
        pm = _re_v.search(r'(\d+)\s*(个月|月|周|天|日)', s)
        if pm:
            n = int(pm.group(1))
            unit = pm.group(2)
            mult = {'天': 1, '日': 1, '周': 7, '月': 30, '个月': 30}.get(unit, 1)
            days = n * mult
            period_label = f"{n}{unit}"

        def _with_period(vol_label):
            return f"{vol_label} · {period_label}" if period_label else vol_label

        if ('无限' in s) or ('不限量' in s) or ('unlimited' in s.lower()):
            # 1TB sentinel volume — sorts last among volumes
            return 1024.0 * 1024, _with_period('Unlimited (无限)'), days
        for pat, factor in [
            (r'(\d+(?:\.\d+)?)\s*TB', 1024 * 1024),
            (r'(\d+(?:\.\d+)?)\s*G[B]?(?![a-z])', 1024),   # GB or bare G ('3.5G')
            (r'(\d+(?:\.\d+)?)\s*MB', 1),
        ]:
            m = _re_v.search(pat, s, _re_v.IGNORECASE)
            if m:
                mb = float(m.group(1)) * factor
                vol = m.group(0).strip().upper()
                if vol.endswith('G') and not vol.endswith('GB'):
                    vol += 'B'
                return mb, _with_period(vol), days
        return None, None, None

    def _data_package_df():
        df = product_type_filtered_data()
        if 'product' not in df.columns and 'sku_name' not in df.columns:
            return pd.DataFrame()
        # Prefer filtering to Data category if available
        if 'product_category' in df.columns:
            mask = df['product_category'].astype(str).str.lower().str.contains(
                r'data|流量|数据', na=False
            )
            ddf = df[mask].copy() if mask.any() else df.copy()
        else:
            ddf = df.copy()
        # Parse volume from the SKU label first ('50GB，28天'), product name fallback
        src = None
        if 'sku_name' in ddf.columns:
            src = ddf['sku_name'].astype('string')
        if 'product' in ddf.columns:
            p = ddf['product'].astype('string')
            src = p if src is None else src.fillna(p)
        vols = src.apply(_parse_data_volume)
        ddf['vol_mb']    = [v[0] for v in vols]
        ddf['vol_label'] = [v[1] for v in vols]
        # Undated packages sort last within a volume (large sentinel)
        ddf['vol_days']  = [v[2] if v[2] is not None else 9999 for v in vols]
        ddf = ddf.dropna(subset=['vol_mb'])
        return ddf.reset_index(drop=True)

    @render.ui
    @safe_render
    def data_package_volume_chart():
        ddf = _data_package_df()
        if ddf.empty:
            return ui.HTML(
                '<div style="color:#64748B;padding:14px;">'
                'No data package volume data found. Ensure product names contain size indicators '
                'like <b>500MB</b>, <b>1GB</b>, <b>2GB</b>, etc. '
                'Filter to Data category using the product type filter above.</div>'
            )
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = ddf.groupby(['vol_label', 'vol_mb', 'vol_days'], observed=True)
        orders_s  = grp['order_id'].nunique() if 'order_id' in ddf.columns else grp.size()
        revenue_s = grp['sales'].sum()        if 'sales'    in ddf.columns else pd.Series(0.0, index=orders_s.index)
        agg = (pd.DataFrame({'orders': orders_s, 'revenue': revenue_s})
               .reset_index().sort_values(['vol_mb', 'vol_days']))
        agg['revenue'] = agg['revenue'] * rate
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:14px;">No data to chart.</div>')
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['vol_label'], y=agg['orders'],
            name=_tt('Orders'),
            yaxis='y',
            marker=dict(color=T.PRIMARY, line=dict(color='white', width=1)),
            hovertemplate='<b>%{x}</b><br>Orders: %{y:,}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=agg['vol_label'], y=agg['revenue'],
            name=_tt(f'Revenue ({sym})'),
            mode='lines+markers',
            yaxis='y2',
            line=dict(color=T.SUCCESS, width=2.5),
            marker=dict(size=8, line=dict(color='white', width=1.5)),
            hovertemplate='<b>%{x}</b><br>Revenue: ' + sym + '%{y:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt("Data Package — Orders & Revenue by Package Size"),
                      xaxis_title=_tt("Package Size"), yaxis_title=_tt("Orders"),
                      yaxis2=dict(title=_tt(f"Revenue ({sym})"), overlaying='y', side='right',
                                  showgrid=False),
                      legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='left', x=0),
                      height=420)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def data_package_tier_chart():
        ddf = _data_package_df()
        if ddf.empty:
            return _no_data()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        # Tier boundaries in MB
        bins   = [0, 500, 2*1024, 5*1024, 20*1024, float('inf')]
        labels = ['Micro (<500MB)', 'Small (500MB–2GB)', 'Mid (2–5GB)', 'Large (5–20GB)', 'Mega (>20GB)']
        ddf['tier'] = pd.cut(ddf['vol_mb'], bins=bins, labels=labels)
        tier_order  = [str(l) for l in labels]
        ddf['tier'] = ddf['tier'].astype(str)      # Categorical → str avoids MultiIndex bug
        grp = ddf.groupby('tier', observed=True)
        orders_s  = grp['order_id'].nunique() if 'order_id' in ddf.columns else grp.size()
        revenue_s = grp['sales'].sum()        if 'sales'    in ddf.columns else pd.Series(0.0, index=orders_s.index)
        agg = pd.DataFrame({'orders': orders_s, 'revenue': revenue_s}).reset_index()
        agg['tier'] = pd.Categorical(agg['tier'], categories=tier_order, ordered=True)
        agg = agg.sort_values('tier')
        agg['revenue'] = agg['revenue'] * rate
        agg = agg[agg['revenue'] > 0]
        if agg.empty:
            return _no_data()
        total_rev = agg['revenue'].sum()
        agg['rev_pct'] = (agg['revenue'] / total_rev * 100).round(1)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['tier'].astype(str), y=agg['revenue'],
            name=_tt(f'Revenue ({sym})'),
            marker=dict(color=agg['revenue'], colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[f"{p:.1f}%" for p in agg['rev_pct']],
            textposition='outside',
            textfont=dict(size=11, color='#0F172A'),
            hovertemplate='<b>%{x}</b><br>Revenue: ' + sym + '%{y:,.0f}<br>Share: %{text}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt(f"Data Package Revenue by Size Tier · {currency['label']}"),
                      xaxis_title=_tt("Size Tier"), yaxis_title=_tt(f"Revenue ({sym})"),
                      height=380)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def data_package_operator_chart():
        ddf = _data_package_df()
        if ddf.empty or 'operator' not in ddf.columns:
            return ui.HTML('<div style="color:#64748B;padding:14px;">No data package × operator data available. Ensure product names contain size indicators like 500MB, 1GB, etc.</div>')
        grp = ddf.groupby(['operator', 'vol_label', 'vol_mb', 'vol_days'], observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in ddf.columns else grp.size()
        agg = orders_s.reset_index(name='orders')
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:14px;">No data to display.</div>')
        top_ops = agg.groupby('operator', observed=True)['orders'].sum().nlargest(15).index.tolist()
        agg = agg[agg['operator'].isin(top_ops)].copy()
        agg['operator'] = agg['operator'].astype(str)
        # Determine vol size order by ascending vol_mb, then validity period
        vol_order_df = (agg.groupby(['vol_label', 'vol_mb', 'vol_days'], observed=True)['orders']
                           .sum().reset_index().sort_values(['vol_mb', 'vol_days']))
        seen_v: set = set()
        vol_order = [x for x in vol_order_df['vol_label'].tolist() if not (x in seen_v or seen_v.add(x))]
        op_order = agg.groupby('operator', observed=True)['orders'].sum().sort_values(ascending=False).index.tolist()
        agg['operator'] = pd.Categorical(agg['operator'], categories=op_order, ordered=True)
        fig = go.Figure()
        colors = (T.PALETTE * (len(vol_order) // len(T.PALETTE) + 1))
        for i, vol in enumerate(vol_order):
            sub = agg[agg['vol_label'] == vol].sort_values('operator')
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub['operator'].astype(str), y=sub['orders'],
                name=vol,
                marker=dict(color=colors[i], line=dict(color='white', width=1)),
                hovertemplate='<b>%{x}</b><br>' + str(vol) + ': %{y:,} orders<extra></extra>',
            ))
        fig.update_layout(barmode='stack')
        T.apply_theme(fig,
                      title=_tt("Data Package Orders by Operator × Volume Size"),
                      xaxis_title=_tt("Operator"), yaxis_title=_tt("Orders"),
                      height=440,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="left", x=0),
                      margin=dict(l=10, r=10, t=50, b=140))
        fig.update_xaxes(tickangle=-35)
        return ui.HTML(T.fig_to_html(fig))

    # ── Data Package Matrix: operator × package size ─────────────────────────

    def _data_package_matrix_data():
        ddf = _data_package_df()
        if ddf.empty or 'operator' not in ddf.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        d = ddf.copy()
        d['operator'] = d['operator'].astype(str)
        grp = d.groupby(['operator', 'vol_label', 'vol_mb', 'vol_days'], observed=True)
        rev_s = grp['sales'].sum() if 'sales' in d.columns else grp.size()
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = pd.DataFrame({'revenue': rev_s, 'orders': ord_s}).reset_index()
        if agg.empty:
            return pd.DataFrame()
        top_ops = (agg.groupby('operator', observed=True)['revenue'].sum()
                      .nlargest(15).index.tolist())
        top_pkgs_df = (agg.groupby(['vol_label', 'vol_mb', 'vol_days'], observed=True)['orders']
                          .sum().reset_index().nlargest(20, 'orders')
                          .sort_values(['vol_mb', 'vol_days']))
        pkg_order = top_pkgs_df['vol_label'].tolist()
        agg = agg[agg['operator'].isin(top_ops) & agg['vol_label'].isin(pkg_order)]
        agg['revenue'] = agg['revenue'] * rate
        pivot = agg.pivot_table(index='operator', columns='vol_label',
                                values='revenue', aggfunc='sum', observed=True)
        pivot = pivot.reindex(columns=[c for c in pkg_order if c in pivot.columns])
        pivot['Total'] = pivot.sum(axis=1)
        pivot = pivot.sort_values('Total', ascending=False).reset_index()
        out = pivot.rename(columns={'operator': 'Operator'})
        for c in out.columns:
            if c != 'Operator':
                out[c] = out[c].apply(lambda x: f"{x:,.0f}" if pd.notna(x) and x > 0 else "—")
        return out

    @render.data_frame
    @safe_grid
    def data_package_matrix_table():
        out = _data_package_matrix_data()
        if out.empty:
            return render.DataGrid(pd.DataFrame(
                {'Status': ['No data package sales in the current selection.']}))
        return render.DataGrid(_tdf(out), filters=False, width="100%")

    @render.download(filename=lambda: _make_filename("data_package_matrix", "xlsx"))
    def download_data_package_matrix():
        yield _xlsx_bytes(_data_package_matrix_data())

    # ── Category Overview (B2C product lines) ────────────────────────────────

    @reactive.Calc
    def _category_frame():
        df = _apply_product_operator(filtered_data())
        if 'product_category' not in df.columns:
            return None
        d = df[df['product_category'].notna()
               & (df['product_category'].astype(str).str.strip() != "")].copy()
        if d.empty:
            return None
        d['product_category'] = d['product_category'].astype(str)
        return d

    @render.ui
    @safe_render
    def category_overview_kpis():
        d = _category_frame()
        if d is None:
            return _no_data("Product category data is only present in B2C (Master) rows — "
                            "select All or B2C in the Customer Segment filter.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = d.groupby('product_category', observed=True)
        rev_s = grp['sales'].sum() * rate
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        total_rev = rev_s.sum()
        top_cat = rev_s.idxmax() if not rev_s.empty else "—"
        top_share = (rev_s.max() / total_rev * 100) if total_rev > 0 else 0
        top_orders_cat = ord_s.idxmax() if not ord_s.empty else "—"
        return ui.tags.div(
            _kpi_card("🗂️", "orders-icon", _bl("Product Categories", "产品类别数"),
                      f"{len(rev_s):,}", None,
                      "Active categories in selection",
                      "Distinct B2C product categories with at least one order."),
            _kpi_card("👑", "sales-icon", _bl("Top Category by Revenue", "收入最高类别"),
                      str(top_cat), None,
                      f"{T.format_number(rev_s.max(), sym)} · {top_share:.1f}% of GMV",
                      "Category contributing the most revenue."),
            _kpi_card("🚶", "users-icon", _bl("Top Category by Orders", "订单最多类别"),
                      str(top_orders_cat), None,
                      f"{T.format_int(ord_s.max())} orders",
                      "Category with the highest order count — the traffic driver."),
            _kpi_card("💰", "countries-icon", _bl("Category GMV (B2C)", "类别总收入 (B2C)"),
                      T.format_number(total_rev, sym), None,
                      f"across {len(rev_s)} categories",
                      "Total revenue across all categorised B2C orders."),
            class_="metrics-grid"
        )

    @render.ui
    @safe_render
    def category_revenue_orders_chart():
        d = _category_frame()
        if d is None:
            return _no_data("Product category data is only present in B2C rows.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = d.groupby('product_category', observed=True)
        rev_s = grp['sales'].sum() * rate
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = pd.DataFrame({'revenue': rev_s, 'orders': ord_s}).reset_index()
        agg = agg.sort_values('revenue', ascending=False).head(12)
        total_rev = agg['revenue'].sum()
        agg['share'] = agg['revenue'] / total_rev * 100 if total_rev > 0 else 0
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['product_category'], y=agg['revenue'],
            name=_tt('Revenue'), yaxis='y',
            marker=dict(color=T.PRIMARY, line=dict(color='white', width=1)),
            text=[f"{s:.1f}%" for s in agg['share']],
            textposition='outside', textfont=dict(size=11, color='#0F172A'),
            hovertemplate='<b>%{x}</b><br>Revenue: ' + sym + '%{y:,.0f}<br>Share: %{text}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=agg['product_category'], y=agg['orders'],
            name=_tt('Orders'), yaxis='y2', mode='lines+markers',
            line=dict(color=T.WARNING, width=2.5),
            marker=dict(size=8, line=dict(color='white', width=1.5)),
            hovertemplate='<b>%{x}</b><br>Orders: %{y:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Revenue & Orders by Product Category · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Revenue ({sym})"),
                      yaxis2=dict(title=_tt("Orders"), overlaying='y', side='right', showgrid=False),
                      height=430,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=60, t=60, b=80))
        fig.update_xaxes(tickangle=-25)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def category_monthly_trend_chart():
        d = _category_frame()
        if d is None:
            return _no_data("Product category data is only present in B2C rows.")
        if 'order_time' not in d.columns:
            return _no_data("Order time column not available.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        d = d.dropna(subset=['order_time']).copy()
        top_cats = (d.groupby('product_category', observed=True)['sales']
                      .sum().nlargest(6).index.tolist())
        d = d[d['product_category'].isin(top_cats)]
        d['month'] = d['order_time'].dt.to_period('M').dt.start_time
        agg = (d.groupby(['month', 'product_category'], observed=True)['sales']
                 .sum().mul(rate).reset_index())
        if agg.empty:
            return _no_data()
        fig = px.line(agg, x='month', y='sales', color='product_category',
                      markers=True, color_discrete_sequence=T.PALETTE)
        fig.update_traces(line=dict(width=2.5, shape='spline'),
                          marker=dict(size=7, line=dict(color='white', width=1)),
                          hovertemplate='<b>%{fullData.name}</b><br>%{x|%b %Y}: ' +
                                        sym + '%{y:,.0f}<extra></extra>')
        T.apply_theme(fig, title=_tt(f"Monthly Revenue by Category (Top 6) · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Revenue ({sym})"),
                      hovermode='x unified', height=420,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    # ── Airtime / Top-up denomination analysis ───────────────────────────────

    @reactive.Calc
    def _airtime_frame():
        """B2C airtime/top-up rows with a display label for each denomination
        (SKU name like 'RM 50' preferred, formatted number fallback)."""
        df = _apply_product_operator(filtered_data())
        if 'product_category' not in df.columns:
            return None
        mask = df['product_category'].astype(str).str.contains(
            r'话费|后付费|PIN码|airtime|topup|top-up', case=False, na=False)
        d = df[mask].copy()
        if d.empty:
            return None
        if 'sku_name' in d.columns:
            label = d['sku_name'].astype('string').str.strip()
        else:
            label = pd.Series(pd.NA, index=d.index, dtype='string')
        fallback = d['denomination'].map(_clean_denom_label).astype('string') if 'denomination' in d.columns \
            else pd.Series(pd.NA, index=d.index, dtype='string')
        d['denom_label'] = label.where(label.notna() & (label != ""), fallback)
        d = d[d['denom_label'].notna() & (d['denom_label'] != "")]
        if d.empty:
            return None
        return d

    @render.ui
    @safe_render
    def airtime_denomination_chart():
        d = _airtime_frame()
        if d is None:
            return _no_data("No airtime/top-up orders in the current selection "
                            "(needs B2C rows with category 充话费 / 后付费 / PIN码话费).")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = d.groupby('denom_label', observed=True)
        rev_s = grp['sales'].sum() * rate
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = pd.DataFrame({'revenue': rev_s, 'orders': ord_s}).reset_index()
        agg = agg.nlargest(20, 'orders')
        agg = agg.sort_values('orders', ascending=True)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['orders'], y=agg['denom_label'], orientation='h',
            name=_tt('Orders'),
            marker=dict(color=T.PRIMARY, line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in agg['orders']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            customdata=agg['revenue'],
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<br>Revenue: ' + sym +
                          '%{customdata:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Airtime Orders by Denomination (Top 20) · {currency['label']}"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10),
                      height=max(420, 26 * len(agg) + 110))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def airtime_denom_operator_chart():
        d = _airtime_frame()
        if d is None:
            return _no_data("No airtime/top-up orders in the current selection.")
        if 'operator' not in d.columns:
            return _no_data("Operator column not available.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        d = d.copy()
        d['operator'] = d['operator'].astype(str)
        grp = d.groupby(['denom_label', 'operator'], observed=True)
        rev_s = grp['sales'].sum() * rate
        ord_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        agg = pd.DataFrame({'revenue': rev_s, 'orders': ord_s}).reset_index()
        top_denoms = (agg.groupby('denom_label', observed=True)['orders']
                         .sum().nlargest(12).index.tolist())
        top_ops = (agg.groupby('operator', observed=True)['orders']
                      .sum().nlargest(8).index.tolist())
        agg = agg[agg['denom_label'].isin(top_denoms) & agg['operator'].isin(top_ops)]
        if agg.empty:
            return _no_data()
        denom_order = (agg.groupby('denom_label', observed=True)['orders']
                          .sum().sort_values(ascending=False).index.tolist())
        fig = go.Figure()
        colors = (T.PALETTE * (len(top_ops) // len(T.PALETTE) + 1))
        for i, op in enumerate(top_ops):
            sub = agg[agg['operator'] == op].set_index('denom_label').reindex(denom_order)
            fig.add_trace(go.Bar(
                x=denom_order, y=sub['orders'],
                name=str(op),
                marker=dict(color=colors[i], line=dict(color='white', width=1)),
                hovertemplate='<b>%{x}</b><br>' + str(op) + ': %{y:,} orders<extra></extra>',
            ))
        fig.update_layout(barmode='stack')
        T.apply_theme(fig, title=_tt("Airtime Top Denominations × Operator (orders)"),
                      xaxis_title=_tt("Denomination"), yaxis_title=_tt("Orders"),
                      height=440,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0),
                      margin=dict(l=10, r=10, t=50, b=120))
        fig.update_xaxes(tickangle=-30)
        return ui.HTML(T.fig_to_html(fig))

    # ── Peak purchase hours (hour × denomination/package per operator) ────────

    def _hourly_frame():
        """Returns (df, label_col) for the selected hourly view, with an 'hour'
        column. label_col holds the denomination or package-size label.
        None when the data/columns are unavailable."""
        try:
            view = input.hourly_view() or "airtime"
        except Exception:
            view = "airtime"
        if view == "data":
            d = _data_package_df()
            if d.empty or 'order_time' not in d.columns:
                return None, None
            d = d.copy()
            d['hour'] = d['order_time'].dt.hour
            d = d.rename(columns={'vol_label': 'item_label'})
            return d, 'item_label'
        # airtime
        d = _airtime_frame()
        if d is None or 'order_time' not in d.columns:
            return None, None
        d = d.copy()
        d['hour'] = d['order_time'].dt.hour
        d = d.rename(columns={'denom_label': 'item_label'})
        return d, 'item_label'

    @render.ui
    @safe_render
    def hourly_operator_selector_ui():
        d, _lbl = _hourly_frame()
        if d is None or 'operator' not in d.columns:
            return ui.input_select("hourly_operator", None,
                                   choices={"__all__": "All operators"}, selected="__all__")
        ops = (d.assign(operator=d['operator'].astype(str))
                .groupby('operator', observed=True).size().sort_values(ascending=False))
        choices = {"__all__": "All operators"}
        for op in ops.head(30).index.tolist():
            choices[op] = op
        return ui.input_select("hourly_operator", None, choices=choices, selected="__all__")

    def _hourly_agg():
        d, lbl = _hourly_frame()
        if d is None or lbl not in d.columns:
            return None, None
        try:
            op_sel = input.hourly_operator() or "__all__"
        except Exception:
            op_sel = "__all__"
        if op_sel != "__all__" and 'operator' in d.columns:
            d = d[d['operator'].astype(str) == op_sel]
        d = d[d[lbl].notna() & (d[lbl].astype(str).str.strip() != "")]
        if d.empty:
            return None, op_sel
        ord_col = 'order_id'
        if ord_col in d.columns:
            agg = (d.groupby([lbl, 'hour'], observed=True)[ord_col]
                   .nunique().reset_index(name='orders'))
        else:
            agg = (d.groupby([lbl, 'hour'], observed=True)
                   .size().reset_index(name='orders'))
        return agg, op_sel

    @render.ui
    @safe_render
    def hourly_purchase_heatmap():
        agg, op_sel = _hourly_agg()
        if agg is None or agg.empty:
            return _no_data("No hourly data for this selection — try 'All operators' or the other view.")
        top_items = (agg.groupby(agg.columns[0], observed=True)['orders']
                     .sum().nlargest(12).index.tolist())
        agg = agg[agg[agg.columns[0]].isin(top_items)]
        lbl = agg.columns[0]
        pivot = (agg.pivot_table(index=lbl, columns='hour', values='orders',
                                 aggfunc='sum', observed=True)
                 .reindex(columns=range(24), fill_value=0).fillna(0))
        # order rows by total volume (heaviest at top)
        pivot = pivot.loc[pivot.sum(axis=1).sort_values().index]
        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=[f"{h:02d}" for h in pivot.columns],
            y=[str(i) for i in pivot.index],
            colorscale=T.SCALE_SEQUENTIAL, showscale=True,
            colorbar=dict(title=dict(text=_tt("Orders"), font=dict(size=11)),
                          thickness=12, len=0.75),
            hovertemplate='<b>%{y}</b><br>Hour %{x}:00<br>Orders: %{z:,}<extra></extra>',
        ))
        op_txt = "" if op_sel in (None, "__all__") else f" · {op_sel}"
        T.apply_theme(fig, title=_tt("Orders by Hour × Denomination / Package") + op_txt,
                      xaxis_title=_tt("Hour of day (MYT)"), yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=40),
                      height=max(320, 30 * len(pivot) + 110))
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def hourly_peak_table():
        agg, op_sel = _hourly_agg()
        if agg is None or agg.empty:
            return render.DataGrid(pd.DataFrame(
                {'Status': ['No hourly data for this selection.']}))
        lbl = agg.columns[0]
        rows = []
        for item, sub in agg.groupby(lbl, observed=True):
            total = sub['orders'].sum()
            if total <= 0:
                continue
            peak = sub.loc[sub['orders'].idxmax()]
            rows.append({
                'Item': str(item),
                'Total Orders': int(total),
                'Peak Hour': f"{int(peak['hour']):02d}:00–{int(peak['hour'])+1:02d}:00",
                'Orders @ Peak': int(peak['orders']),
                'Peak Share': peak['orders'] / total * 100,
            })
        if not rows:
            return render.DataGrid(pd.DataFrame({'Status': ['No hourly data.']}))
        out = pd.DataFrame(rows).sort_values('Total Orders', ascending=False).head(20)
        out['Total Orders'] = out['Total Orders'].apply(lambda x: f"{x:,}")
        out['Orders @ Peak'] = out['Orders @ Peak'].apply(lambda x: f"{x:,}")
        out['Peak Share'] = out['Peak Share'].apply(lambda x: f"{x:.1f}%")
        return render.DataGrid(_tdf(out), filters=False, width="100%")

    @render.ui
    @safe_render
    def product_sales_chart():
        df = product_type_filtered_data()
        if 'product' not in df.columns or 'sales' not in df.columns:
            return _no_data()
        currency = currency_converter()
        ps = df.groupby('product', observed=True)['sales'].sum().mul(currency['rate']).nlargest(10).reset_index()
        ps = ps.sort_values('sales')
        fig = go.Figure(go.Bar(
            x=ps['sales'], y=ps['product'], orientation='h',
            marker=dict(color=ps['sales'], colorscale=T.SCALE_SEQUENTIAL, showscale=False),
            text=[T.format_number(v, currency['symbol']) for v in ps['sales']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Sales: ' + currency['symbol'] + '%{x:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Top 10 products by sales · {currency['label']}"),
                      xaxis_title=_tt(f"Sales ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def product_treemap():
        """Treemap: products grouped by segment, sized by sales."""
        df = product_type_filtered_data()
        if not {'segment', 'product', 'sales'}.issubset(df.columns):
            return _no_data()
        currency = currency_converter()
        ps = df.groupby(['segment', 'product'], observed=True)['sales'].sum().mul(currency['rate']).reset_index()
        ps = ps[ps['sales'] > 0]
        # Limit to top-30 products to keep treemap readable
        top_p = ps.nlargest(30, 'sales')
        fig = px.treemap(
            top_p, path=[px.Constant("All"), 'segment', 'product'], values='sales',
            color='sales', color_continuous_scale=T.SCALE_SEQUENTIAL,
        )
        fig.update_traces(
            hovertemplate='<b>%{label}</b><br>Sales: ' + currency['symbol'] + '%{value:,.0f}<br>Share: %{percentParent:.1%} of %{parent}<extra></extra>',
            textinfo='label+value',
            texttemplate='<b>%{label}</b><br>' + currency['symbol'] + '%{value:,.0f}',
            marker=dict(line=dict(color='white', width=2)),
        )
        T.apply_theme(fig, title=_tt(f"Product mix by segment (top 30) · {currency['label']}"),
                      margin=dict(l=10, r=10, t=50, b=10), height=520,
                      coloraxis_colorbar=dict(title=dict(text="Sales", font=dict(size=11)), thickness=12, len=0.7))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def product_segment_chart():
        df = product_type_filtered_data()
        if not {'segment', 'product', 'sales'}.issubset(df.columns):
            return _no_data()
        currency = currency_converter()
        ps = (df.groupby(['segment', 'product'], observed=True)['sales']
                .sum().mul(currency['rate'])
                .groupby(level=0, group_keys=False).nlargest(5).reset_index())
        fig = px.bar(ps, x='sales', y='product', color='segment', orientation='h',
                     color_discrete_sequence=T.PALETTE)
        fig.update_traces(marker_line_color='white', marker_line_width=1.0,
                          hovertemplate='<b>%{y}</b><br>%{fullData.name}: ' + currency['symbol'] + '%{x:,.0f}<extra></extra>')
        T.apply_theme(fig, title=_tt(f"Top 5 products per segment · {currency['label']}"),
                      xaxis_title=_tt(f"Sales ({currency['symbol']})"), yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    # ------------------------------------------------------------------
    # Denomination analysis (e.g. Iraq, past 2 weeks, by operator × denomination)
    # ------------------------------------------------------------------
    def _clean_denom_label(value):
        """'2000.0' -> '2000', '0' -> '', other strings kept as-is."""
        s = str(value).strip()
        if not s or s.lower() in {"nan", "none", "nat", "<na>"}:
            return ""
        try:
            f = float(s.replace(",", ""))
            if f == 0:
                return ""
            if f == int(f):
                return f"{int(f):,}"
            return f"{f:,.2f}"
        except (TypeError, ValueError):
            return s

    def _denom_frame():
        """Filtered data with a clean 'denomination' label column, NaNs dropped."""
        df = product_type_filtered_data()
        if 'denomination' not in df.columns:
            return None
        d = df.copy()
        cleaned = d['denomination'].map(_clean_denom_label)
        # Fall back to the raw string when cleaning produces an empty label
        raw = d['denomination'].astype(str).str.strip()
        d['denomination'] = cleaned.where(cleaned != "", raw)
        d = d[d['denomination'].notna() & (d['denomination'] != "") & (d['denomination'] != "nan") & (d['denomination'] != "<NA>")]
        if d.empty:
            return None
        return d

    def _denom_sort_key(value):
        """Order denominations numerically if the label parses to a number."""
        s = str(value).replace(",", "")
        try:
            return (0, float(s), str(value))
        except ValueError:
            # Fall back to extracting any number from the string
            m = _re.search(r"-?\d+(?:\.\d+)?", s)
            if m:
                try:
                    return (0, float(m.group()), str(value))
                except ValueError:
                    pass
            return (1, 0.0, str(value))

    @render.ui
    @safe_render
    def denomination_heatmap():
        d = _denom_frame()
        if d is None or 'operator' not in d.columns or 'order_id' not in d.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No denomination data in current selection.</div>')

        agg = (d.groupby(['operator', 'denomination'], observed=True)['order_id']
                .nunique().reset_index(name=_tt('orders')))
        agg = agg[agg['orders'] > 0]
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No denomination data in current selection.</div>')

        # Limit to top 15 operators × top 25 denominations by total volume
        top_ops    = agg.groupby('operator', observed=True)['orders'].sum().nlargest(15).index.tolist()
        top_denoms = agg.groupby('denomination', observed=True)['orders'].sum().nlargest(25).index.tolist()
        agg = agg[agg['operator'].isin(top_ops) & agg['denomination'].isin(top_denoms)]

        denom_order = sorted(top_denoms, key=_denom_sort_key)
        op_order    = (agg.groupby('operator', observed=True)['orders'].sum()
                          .sort_values(ascending=True).index.tolist())  # heaviest at top

        pivot = agg.pivot(index='operator', columns='denomination', values='orders')
        pivot = pivot.reindex(index=op_order, columns=denom_order).fillna(0)

        fig = go.Figure(go.Heatmap(
            z=pivot.values, x=pivot.columns, y=pivot.index,
            colorscale=T.SCALE_SEQUENTIAL, showscale=True,
            zmin=0,
            colorbar=dict(title=dict(text="Orders", font=dict(size=11)),
                          thickness=12, len=0.75),
            hovertemplate='<b>Operator:</b> %{y}<br><b>Denomination:</b> %{x}<br><b>Orders:</b> %{z:,}<extra></extra>',
        ))
        # Cell labels only when the data set is small enough to keep them legible
        if pivot.size <= 200:
            fig.update_traces(text=pivot.values.astype(int),
                              texttemplate='%{text:,}',
                              textfont=dict(size=10, color="#0F172A"))
        height = max(360, 28 * max(1, len(op_order)) + 100)
        T.apply_theme(fig, title=_tt("Orders by Operator × Denomination"),
                      xaxis_title=_tt("Denomination"), yaxis_title=None,
                      margin=dict(l=10, r=10, t=50, b=60), height=height,
                      xaxis=dict(tickangle=-30, automargin=True))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def denomination_operator_chart():
        d = _denom_frame()
        if d is None or 'operator' not in d.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No denomination × operator data available.</div>')
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        grp = d.groupby(['denomination', 'operator'], observed=True)
        orders_s  = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        revenue_s = grp['sales'].sum()        if 'sales'    in d.columns else pd.Series(0.0, index=orders_s.index)
        agg = pd.DataFrame({'orders': orders_s, 'revenue': revenue_s}).reset_index()
        agg['revenue'] = agg['revenue'] * rate
        if agg.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No data.</div>')
        top_denoms = (agg.groupby('denomination', observed=True)['orders']
                         .sum().nlargest(15).index.tolist())
        top_denoms_sorted = sorted(top_denoms, key=_denom_sort_key)
        top_ops = (agg.groupby('operator', observed=True)['orders']
                      .sum().nlargest(10).index.tolist())
        agg = agg[agg['denomination'].isin(top_denoms) & agg['operator'].isin(top_ops)].copy()
        agg['denomination'] = agg['denomination'].astype(str)
        denom_str_order = [str(x) for x in top_denoms_sorted]
        agg['denomination'] = pd.Categorical(agg['denomination'], categories=denom_str_order, ordered=True)
        fig = go.Figure()
        colors = (T.PALETTE * (len(top_ops) // len(T.PALETTE) + 1))
        for i, op in enumerate(top_ops):
            sub = agg[agg['operator'].astype(str) == str(op)].sort_values('denomination')
            if sub.empty:
                continue
            fig.add_trace(go.Bar(
                x=sub['denomination'].astype(str), y=sub['revenue'],
                name=str(op),
                marker=dict(color=colors[i], line=dict(color='white', width=0.8)),
                hovertemplate='<b>%{x}</b><br>' + str(op) + ': ' + sym + '%{y:,.0f}<extra></extra>',
            ))
        fig.update_layout(barmode='group')
        T.apply_theme(fig,
                      title=_tt(f"Revenue by Denomination × Operator (Top 15 denominations) · {currency['label']}"),
                      xaxis_title=_tt("Denomination"), yaxis_title=_tt(f"Revenue ({sym})"),
                      height=460,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.32, xanchor="left", x=0),
                      margin=dict(l=10, r=10, t=50, b=130))
        fig.update_xaxes(tickangle=-35)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def top_denominations_chart():
        d = _denom_frame()
        if d is None or 'order_id' not in d.columns:
            return _no_data()
        currency = currency_converter()
        grp = d.groupby('denomination', observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        sales_s  = grp['sales'].sum()        if 'sales'    in d.columns else pd.Series(0.0, index=orders_s.index)
        agg = pd.DataFrame({'orders': orders_s, 'sales': sales_s}).reset_index()
        agg = agg[agg['orders'] > 0]
        if agg.empty:
            return _no_data()
        agg['sales'] = agg['sales'] * currency['rate']
        agg = agg.nlargest(20, 'orders').sort_values('orders')

        fig = go.Figure(go.Bar(
            x=agg['orders'], y=agg['denomination'], orientation='h',
            marker=dict(color=agg['orders'], colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in agg['orders']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            customdata=agg['sales'],
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<br>Sales: ' + currency['symbol'] + '%{customdata:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Top 20 denominations by orders"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    def _denomination_scorecard_data():
        d = _denom_frame()
        if d is None or 'operator' not in d.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate = currency['rate']
        # If product name is missing (Agent rows), fall back to product_info
        if 'product' in d.columns and 'product_info' in d.columns:
            d['product'] = d['product'].astype(str).where(
                d['product'].astype(str).str.strip().replace({"nan": "", "None": "", "<NA>": ""}) != "",
                d['product_info']
            )
        prod_col = 'product' if 'product' in d.columns else ('product_info' if 'product_info' in d.columns else None)

        group_cols = ['operator', 'denomination']
        if prod_col:
            group_cols.append(prod_col)

        grp = d.groupby(group_cols, observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        sales_s  = grp['sales'].sum()
        _parts   = {'orders': orders_s, 'sales': sales_s}
        if _settle_col(d) in d.columns:
            _parts['cost'] = grp[_settle_col(d)].sum()
        summary = pd.DataFrame(_parts).reset_index()
        if 'cost' not in summary.columns:
            summary['cost'] = np.nan
        summary['sales'] = (summary['sales'] * rate).round(2)
        summary['cost']  = (summary['cost']  * rate).round(2)
        summary['margin'] = (summary['sales'] - summary['cost']).round(2)
        summary['margin_pct'] = ((summary['margin'] / summary['sales'].replace(0, np.nan)) * 100).round(2)
        summary['avg_sale'] = (summary['sales'] / summary['orders'].replace(0, np.nan)).round(2)

        sym = currency['symbol']
        rename_map = {
            'operator':   'Operator',
            'denomination': 'Denomination',
            'orders':     'Orders',
            'sales':      f'Sales ({sym})',
            'cost':       f'Cost ({sym})',
            'margin':     f'Margin ({sym})',
            'margin_pct': 'Margin %',
            'avg_sale':   f'Avg sale ({sym})',
        }
        if prod_col:
            rename_map[prod_col] = 'Product'
        summary = summary.rename(columns=rename_map)
        col_order = ['Operator', 'Denomination']
        if prod_col:
            col_order.append('Product')
        col_order += ['Orders', f'Sales ({sym})', f'Avg sale ({sym})',
                      f'Cost ({sym})', f'Margin ({sym})', 'Margin %']
        summary = summary[[c for c in col_order if c in summary.columns]].sort_values('Orders', ascending=False).copy()
        for col in [f'Sales ({sym})', f'Cost ({sym})', f'Margin ({sym})', f'Avg sale ({sym})']:
            if col in summary.columns:
                summary[col] = summary[col].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        if 'Margin %' in summary.columns:
            summary['Margin %'] = summary['Margin %'].apply(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        if 'Orders' in summary.columns:
            summary['Orders'] = summary['Orders'].apply(lambda x: f"{int(x):,}")
        return summary

    @render.data_frame
    @safe_grid
    def denomination_scorecard():
        # Cap on-screen rows for grid responsiveness; the Excel download keeps all.
        return _tdf(_denomination_scorecard_data().head(500))

    @render.download(filename=lambda: _make_filename("denomination_scorecard", "xlsx"))
    def download_denomination_scorecard():
        yield _xlsx_bytes(_denomination_scorecard_data())

    @render.data_frame
    @safe_grid
    def product_summary_table():
        df = product_type_filtered_data()
        if 'product' in df.columns and 'sales' in df.columns:
            currency = currency_converter()
            rate = currency['rate']
            grp = df.groupby('product', observed=True)
            sales_s   = grp['sales'].sum()
            mean_s    = grp['sales'].mean()
            count_s   = grp['sales'].count()
            orders_s  = grp['order_id'].nunique() if 'order_id' in df.columns else count_s
            summary = pd.DataFrame({
                'Product':      sales_s.index,
                'Total Sales':  sales_s.values * rate,
                'Avg Sale':     mean_s.values  * rate,
                'Transactions': count_s.values,
                'Total Orders': orders_s.values,
            })
            summary['Pct of Total'] = (summary['Total Sales'] / summary['Total Sales'].sum() * 100)
            out = summary[['Product', 'Total Sales', 'Pct of Total', 'Total Orders', 'Avg Sale']].sort_values('Total Sales', ascending=False).copy()
            out['Total Sales'] = out['Total Sales'].apply(lambda x: f"{x:,.2f}")
            out['Avg Sale'] = out['Avg Sale'].apply(lambda x: f"{x:,.2f}")
            out['Total Orders'] = out['Total Orders'].apply(lambda x: f"{int(x):,}")
            out['Pct of Total'] = out['Pct of Total'].apply(lambda x: f"{x:.2f}%")
            return _tdf(out)
        return pd.DataFrame()

    # ── Operator × Product Category breakdown ────────────────────────────────

    @reactive.Calc
    def _operator_category_data():
        """Aggregated operator × product_category frame (revenue + orders)."""
        df = product_type_filtered_data()
        if not {'operator', 'product_category', 'sales'}.issubset(df.columns):
            return None
        # product_category only exists in B2C (Master) data; B2B rows have NaN
        df = df[df['product_category'].notna() & (df['product_category'].astype(str).str.strip().replace({"<NA>": "", "nan": ""}) != "")]
        if df.empty:
            return None
        currency = currency_converter()
        rate = currency['rate']
        grp = df.groupby(['operator', 'product_category'], observed=True)
        revenue_s = grp['sales'].sum()
        orders_s  = grp['order_id'].nunique() if 'order_id' in df.columns else grp.size()
        agg = pd.DataFrame({'revenue': revenue_s, 'orders': orders_s}).reset_index()
        agg['revenue'] = agg['revenue'] * rate
        agg['aov'] = (agg['revenue'] / agg['orders'].replace(0, np.nan)).round(2)
        agg['operator'] = agg['operator'].astype(str)
        agg['product_category'] = agg['product_category'].astype(str)
        return agg, currency

    @render.ui
    @safe_render
    def operator_category_revenue_chart():
        result = _operator_category_data()
        if result is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Operator or product category data not available.</div>')
        agg, currency = result
        sym = currency['symbol']
        # Top 15 operators by total revenue
        top_ops = agg.groupby('operator', observed=True)['revenue'].sum().nlargest(15).index.tolist()
        d = agg[agg['operator'].isin(top_ops)].copy()
        # Sort operators by total revenue descending
        op_order = d.groupby('operator', observed=True)['revenue'].sum().sort_values(ascending=True).index.tolist()
        d['operator'] = pd.Categorical(d['operator'], categories=op_order, ordered=True)
        cats = sorted(d['product_category'].unique().tolist())

        from plotly.subplots import make_subplots
        fig = go.Figure()
        for i, cat in enumerate(cats):
            sub = d[d['product_category'] == cat].sort_values('operator')
            fig.add_trace(go.Bar(
                y=sub['operator'].astype(str), x=sub['revenue'],
                name=cat, orientation='h',
                marker=dict(color=T.PALETTE[i % len(T.PALETTE)], opacity=0.85,
                            line=dict(color='white', width=1)),
                text=[T.format_full(v, sym) for v in sub['revenue']],
                textposition='inside', insidetextanchor='middle',
                textfont=dict(size=9, color='white'),
                hovertemplate=(f'<b>%{{y}}</b><br>Category: {cat}<br>'
                               f'Revenue: {sym}%{{x:,.2f}}<extra></extra>'),
            ))
        height = max(380, 30 * len(top_ops) + 120)
        T.apply_theme(fig, title=_tt(f"Revenue (GMV) by Operator × Product Category · {currency['label']}"),
                      xaxis_title=_tt(f"Revenue ({sym})"), yaxis_title=None,
                      barmode='stack', height=height,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def operator_category_volume_chart():
        result = _operator_category_data()
        if result is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Operator or product category data not available.</div>')
        agg, currency = result
        top_ops = agg.groupby('operator', observed=True)['orders'].sum().nlargest(15).index.tolist()
        d = agg[agg['operator'].isin(top_ops)].copy()
        op_order = d.groupby('operator', observed=True)['orders'].sum().sort_values(ascending=True).index.tolist()
        d['operator'] = pd.Categorical(d['operator'], categories=op_order, ordered=True)
        cats = sorted(d['product_category'].unique().tolist())

        fig = go.Figure()
        for i, cat in enumerate(cats):
            sub = d[d['product_category'] == cat].sort_values('operator')
            fig.add_trace(go.Bar(
                y=sub['operator'].astype(str), x=sub['orders'],
                name=cat, orientation='h',
                marker=dict(color=T.PALETTE[i % len(T.PALETTE)], opacity=0.85,
                            line=dict(color='white', width=1)),
                text=[T.format_int(v) for v in sub['orders']],
                textposition='inside', insidetextanchor='middle',
                textfont=dict(size=9, color='white'),
                hovertemplate=(f'<b>%{{y}}</b><br>Category: {cat}<br>'
                               f'Orders: %{{x:,}}<extra></extra>'),
            ))
        height = max(380, 30 * len(top_ops) + 120)
        T.apply_theme(fig, title=_tt("Order Volume by Operator × Product Category"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      barmode='stack', height=height,
                      legend=dict(orientation="h", yanchor="bottom", y=-0.12, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    def _op_category_pivot_raw():
        """Returns (DataFrame, currency) for the full pivot. Used by table and download."""
        result = _operator_category_data()
        if result is None:
            return None, None
        agg, currency = result
        metric = getattr(input, 'op_cat_metric', lambda: 'revenue')()
        col = 'revenue' if metric == 'revenue' else ('aov' if metric == 'aov' else 'orders')
        pivot = (agg.pivot_table(index='operator', columns='product_category',
                                  values=col, aggfunc='sum')
                    .reset_index())
        pivot.columns = [str(c) for c in pivot.columns]
        cat_cols = [c for c in pivot.columns if c != 'operator']
        pivot['Total'] = pivot[cat_cols].sum(axis=1, numeric_only=True)
        pivot = pivot.sort_values('Total', ascending=False)
        return pivot, currency

    @render.data_frame
    @safe_grid
    def operator_category_pivot_table():
        raw = _op_category_pivot_raw()
        if raw is None or raw[0] is None or raw[1] is None:
            return render.DataGrid(pd.DataFrame({'Status': ['Product category data requires B2C data. Filter to B2C segment to view.']}))
        pivot, currency = raw
        metric = getattr(input, 'op_cat_metric', lambda: 'revenue')()
        sym = currency['symbol']
        cat_cols = [c for c in pivot.columns if c not in ('operator', 'Total')]
        out = pivot.copy()
        if metric == 'revenue':
            for c in cat_cols + ['Total']:
                out[c] = pd.to_numeric(out[c], errors='coerce').apply(
                    lambda x: f"{sym}{x:,.2f}" if pd.notna(x) else "—")
        elif metric == 'aov':
            for c in cat_cols + ['Total']:
                out[c] = pd.to_numeric(out[c], errors='coerce').apply(
                    lambda x: f"{sym}{x:,.2f}" if pd.notna(x) else "—")
        else:
            for c in cat_cols + ['Total']:
                out[c] = pd.to_numeric(out[c], errors='coerce').apply(
                    lambda x: f"{int(x):,}" if pd.notna(x) else "—")
        # Cap on-screen rows; the Excel download keeps the full pivot.
        return render.DataGrid(_tdf(out.head(200)), filters=True)

    @render.download(filename=lambda: _make_filename("operator_category_pivot", "xlsx"))
    def download_op_category_pivot():
        pivot, _ = _op_category_pivot_raw()
        if pivot is None:
            yield _xlsx_bytes(pd.DataFrame())
        else:
            yield _xlsx_bytes(pivot)

    # ── New: Customer Analytics additions ─────────────────────────────────────

    @render.ui
    @safe_render
    def key_country_3m_trend():
        df = _apply_global_exclusions(data_rv())
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        df = filter_by_order_status(df, "Successful")
        if df is None or df.empty or 'order_time' not in df.columns or 'country' not in df.columns:
            return _no_data()
        currency = currency_converter(); rate, sym = currency['rate'], currency['symbol']
        kc = _load_key_countries()
        d = df[df['country'].astype(str).isin(kc)].copy()
        if d.empty:
            return _no_data("No key-country data in the current selection.")
        d['ym'] = pd.to_datetime(d['order_time'], errors='coerce').dt.to_period('M').astype(str)
        months = sorted([m for m in d['ym'].dropna().unique() if m and m != 'NaT'])[-3:]
        d = d[d['ym'].isin(months)]
        if d.empty:
            return _no_data()
        piv = d.groupby(['country', 'ym'], observed=True)['sales'].sum().mul(rate).reset_index()
        countries = (piv.groupby('country')['sales'].sum()
                     .sort_values(ascending=False).index.tolist())
        pal = getattr(T, 'PALETTE', None)
        fig = go.Figure()
        for i, m in enumerate(months):
            sub = piv[piv['ym'] == m].set_index('country')['sales']
            fig.add_trace(go.Bar(name=m, x=countries,
                                  y=[float(sub.get(c, 0)) for c in countries],
                                  marker=dict(color=(pal[i % len(pal)] if pal else None))))
        fig.update_layout(barmode='group')
        T.apply_theme(fig, title=_tt("Key Countries — Last 3 Months Revenue (重点国家)"),
                      xaxis_title=None, yaxis_title=_tt(f"Revenue ({sym})"), height=430,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=10, t=60, b=90))
        fig.update_xaxes(tickangle=-25)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def channel_analysis_chart():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        d = _with_channel(df)
        if d is None or 'channel' not in d.columns or d['channel'].isna().all():
            return _no_data("渠道来源 (会员来源) requires the 用户列表 — file not found.")
        currency = currency_converter(); rate, sym = currency['rate'], currency['symbol']
        d = d.dropna(subset=['channel'])
        g = d.groupby('channel', observed=True)
        agg = pd.DataFrame({
            'gmv': g['sales'].sum() * rate,
            'orders': g['order_id'].nunique() if 'order_id' in d.columns else g.size(),
        }).reset_index().sort_values('gmv', ascending=True).tail(12)
        total = float(agg['gmv'].sum())
        fig = go.Figure(go.Bar(
            x=agg['gmv'], y=agg['channel'], orientation='h',
            marker=dict(color=agg['gmv'], colorscale=T.SCALE_SEQUENTIAL, showscale=False,
                        line=dict(color='white', width=1)),
            text=[f"{T.format_number(v, sym)} · {v/total*100:.0f}%" if total else T.format_number(v, sym)
                  for v in agg['gmv']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>GMV: ' + sym + '%{x:,.0f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Revenue by Channel (会员来源, B2C)"),
                      xaxis_title=_tt(f"Revenue ({sym})"), yaxis_title=None, height=440,
                      margin=dict(l=10, r=120, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def channel_scorecard():
        """3.3 Channel ROI/CAC — per 会员来源: GMV, orders, customers, new customers,
        coupon spend, ROI (GMV÷spend), CAC (spend÷new)."""
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        d = _with_channel(df)
        if d is None or 'channel' not in d.columns or d['channel'].isna().all():
            return render.DataGrid(pd.DataFrame({'Status': ['渠道来源 ROI requires the 用户列表 — not found.']}))
        currency = currency_converter(); rate, sym = currency['rate'], currency['symbol']
        d = d.dropna(subset=['channel']).copy()
        d['_coupon'] = pd.to_numeric(d['coupon_amount'], errors='coerce') if 'coupon_amount' in d.columns else 0.0
        g = d.groupby('channel', observed=True)
        gmv = g['sales'].sum() * rate
        orders = g['order_id'].nunique() if 'order_id' in d.columns else g.size()
        customers = g['user_id'].nunique() if 'user_id' in d.columns else 0
        coupon = g['_coupon'].sum() * rate
        new_by_ch = pd.Series(dtype=float)
        if {'register_time', 'order_time', 'user_id'}.issubset(d.columns):
            dd = d.dropna(subset=['register_time', 'order_time', 'user_id'])
            if not dd.empty:
                regm = pd.to_datetime(dd['register_time'], errors='coerce').dt.to_period('M')
                ordm = pd.to_datetime(dd['order_time'], errors='coerce').dt.to_period('M')
                nd = dd[regm.values == ordm.values]
                new_by_ch = nd.groupby('channel', observed=True)['user_id'].nunique()
        agg = pd.DataFrame({'gmv': gmv, 'orders': orders, 'customers': customers, 'coupon': coupon})
        agg['new'] = new_by_ch.reindex(agg.index).fillna(0)
        agg = agg.sort_values('gmv', ascending=False)
        agg['roi'] = agg['gmv'] / agg['coupon'].replace(0, np.nan)
        agg['cac'] = agg['coupon'] / agg['new'].replace(0, np.nan)
        out = pd.DataFrame({'Channel (会员来源)': agg.index})
        out[f'GMV ({sym})']          = agg['gmv'].apply(lambda x: f"{x:,.0f}").values
        out['Orders']                = agg['orders'].apply(lambda x: f"{int(x):,}").values
        out['Customers']             = agg['customers'].apply(lambda x: f"{int(x):,}").values
        out['New Customers']         = agg['new'].apply(lambda x: f"{int(x):,}").values
        out[f'Coupon Spend ({sym})'] = agg['coupon'].apply(lambda x: f"{x:,.0f}").values
        out['ROI (GMV÷Spend)']       = agg['roi'].apply(lambda x: f"{x:,.0f}×" if pd.notna(x) else "—").values
        out[f'CAC ({sym}/new)']      = agg['cac'].apply(lambda x: f"{x:,.1f}" if pd.notna(x) else "—").values
        return render.DataGrid(_tdf(out), filters=True)

    @render.ui
    @safe_render
    def new_vs_returning_chart():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'] == 'B2C']
        if 'user_id' not in df.columns or 'order_id' not in df.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Customer data not available (B2C only).</div>')
        currency = currency_converter()
        # China-team standard: 新客 = 注册月 == 订单月; 老客 = 注册月 < 订单月 (B2C).
        if {'register_time', 'order_time'}.issubset(df.columns):
            g = df.dropna(subset=['register_time', 'order_time', 'user_id']).copy()
            if g.empty:
                return _no_data()
            regm = pd.to_datetime(g['register_time'], errors='coerce').dt.to_period('M')
            ordm = pd.to_datetime(g['order_time'], errors='coerce').dt.to_period('M')
            g['_is_new'] = (regm == ordm)
            user_is_new = g.groupby('user_id', observed=True)['_is_new'].max()
            new_count = int(user_is_new.sum())
            returning_count = int((~user_is_new).sum())
            labels = ['New 新客 (注册月=订单月)', 'Returning 老客 (注册月<订单月)']
        else:   # fallback when register_time is unavailable
            user_orders = df.groupby('user_id', observed=True)['order_id'].nunique()
            if user_orders.empty:
                return _no_data()
            new_count = int((user_orders == 1).sum())
            returning_count = int((user_orders > 1).sum())
            labels = ['New Customers (1 order)', 'Returning Customers (2+ orders)']
        total = new_count + returning_count
        values = [new_count, returning_count]
        fig = go.Figure(go.Pie(
            labels=labels, values=values, hole=0.55,
            marker=dict(colors=[T.INFO, T.SUCCESS], line=dict(color='white', width=2)),
            textinfo='label+percent', textfont=dict(size=12),
            hovertemplate='<b>%{label}</b><br>Customers: %{value:,}<br>%{percent}<extra></extra>',
        ))
        ret_pct = returning_count / total * 100 if total > 0 else 0
        fig.add_annotation(text=f"<b>老客 Returning</b><br>{ret_pct:.1f}%",
                           x=0.5, y=0.5, showarrow=False, font=dict(size=14, color="#0F172A"))
        T.apply_theme(fig, title=_tt("New vs. Returning Customers (B2C)"),
                      showlegend=True, margin=dict(l=10, r=10, t=50, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=-0.1, xanchor="center", x=0.5))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def new_customer_acquisition_chart():
        df_all = data_rv()
        if 'user_id' not in df_all.columns or 'order_time' not in df_all.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Customer acquisition data not available (B2C only).</div>')
        b2c = df_all[df_all.get('segment', pd.Series()) == 'B2C'] if 'segment' in df_all.columns else df_all
        if b2c.empty:
            b2c = df_all
        first_order = b2c.groupby('user_id', observed=True)['order_time'].min().reset_index()
        first_order['month'] = first_order['order_time'].dt.to_period('M').dt.start_time
        monthly_new = first_order.groupby('month').size().reset_index(name=_tt('new_customers'))
        monthly_new = monthly_new.sort_values('month')
        if monthly_new.empty:
            return _no_data()
        fig = go.Figure(go.Bar(
            x=monthly_new['month'], y=monthly_new['new_customers'],
            marker=dict(color=T.PRIMARY, opacity=0.8, line=dict(color='white', width=1)),
            hovertemplate='<b>%{x|%b %Y}</b><br>New Customers: %{y:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Monthly Customer Acquisition Rate — New Customers by First-Order Month (B2C, Full History)"),
                      xaxis_title=None, yaxis_title=_tt("New Customers"),
                      showlegend=False, margin=dict(l=10, r=10, t=50, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def user_source_chart():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'] == 'B2C']
        src_col = next((c for c in df.columns if c.lower() in ('user_source', '用户来源', 'source', 'channel')), None)
        if src_col is None or 'user_id' not in df.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">'
                           'User source (用户来源) column not found in current data.</div>')
        df2 = df.dropna(subset=[src_col])
        if df2.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No user source data available.</div>')
        currency = currency_converter()
        grp = df2.groupby(src_col, observed=True)
        customers_s = grp['user_id'].nunique()  if 'user_id'  in df2.columns else grp.size()
        orders_s    = grp['order_id'].nunique() if 'order_id' in df2.columns else grp.size()
        revenue_s   = grp['sales'].sum()        if 'sales'    in df2.columns else pd.Series(0.0, index=customers_s.index)
        agg = pd.DataFrame({'customers': customers_s, 'orders': orders_s, 'revenue': revenue_s}).reset_index()
        agg['revenue'] *= currency['rate']
        agg = agg.sort_values('revenue', ascending=False).head(15)
        sym = currency['symbol']

        from plotly.subplots import make_subplots
        fig = make_subplots(
            rows=1, cols=2,
            subplot_titles=(_tt("Revenue (GMV) by User Source"), _tt("Customer Count by User Source")),
            horizontal_spacing=0.12,
        )
        fig.add_trace(go.Bar(
            x=agg[src_col], y=agg['revenue'],
            marker=dict(color=T.PRIMARY, opacity=0.85),
            text=[T.format_number(v, sym) for v in agg['revenue']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Revenue: ' + sym + '%{y:,.2f}<extra></extra>',
            name=_tt("Revenue"),
        ), row=1, col=1)
        fig.add_trace(go.Bar(
            x=agg[src_col], y=agg['customers'],
            marker=dict(color=T.SUCCESS, opacity=0.85),
            text=[T.format_int(v) for v in agg['customers']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Customers: %{y:,}<extra></extra>',
            name=_tt("Customers"),
        ), row=1, col=2)
        T.apply_theme(fig, title=_tt("User Source (用户来源) Analysis — Revenue & Customer Count (B2C)"),
                      showlegend=False, margin=dict(l=10, r=10, t=70, b=80))
        fig.update_xaxes(tickangle=-35)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def user_metrics():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'] == 'B2C']
        if not {'user_id', 'order_id'}.issubset(df.columns):
            return ui.p("User behaviour metrics are unavailable (B2C only).")
        user_orders = df.groupby('user_id', observed=True)['order_id'].nunique().reset_index()
        user_orders.columns = ['user_id', 'order_count']
        if user_orders.empty:
            return ui.p("No user data in the current selection.")
        avg_orders = user_orders['order_count'].mean()
        repeat_users = (user_orders['order_count'] > 1).sum()
        total_users = len(user_orders)
        single_purchase = (user_orders['order_count'] == 1).sum()

        # China-team standard 复购率 / 留存率 (vs prior equal period, B2C 充值成功 basis)
        prev = previous_period_data()
        if 'segment' in prev.columns:
            prev = prev[prev['segment'] == 'B2C']
        cur_uids = set(df['user_id'].dropna().astype(str).unique())
        prev_uids = set(prev['user_id'].dropna().astype(str).unique()) if 'user_id' in prev.columns else set()
        repurchase_std = (len(cur_uids & prev_uids) / len(cur_uids) * 100) if cur_uids else None
        prev_new = _reg_new_user_set(prev)
        retention_std = (len(prev_new & cur_uids) / len(prev_new) * 100) if prev_new else None

        return ui.tags.div(
            _kpi_card("👥", "users-icon", _bl("Active Customers (B2C)", "活跃客户数 (B2C)"),
                      f"{total_users:,}", None,
                      f"{T.format_int(repeat_users)} repeat · {T.format_int(single_purchase)} one-time",
                      "Unique B2C user IDs in the selected period."),
            _kpi_card("📌", "users-icon", _bl("Retention Rate", "留存率"),
                      (T.format_pct(retention_std, 1) if retention_std is not None else "—"), None,
                      _bl("prev-period new ∩ this-period", "上月新客∩本月成单 / 上月新客"),
                      "留存率 = |上月新客成功用户 ∩ 本月成功用户| / |上月新客成功用户| (vs prior equal period)."),
            _kpi_card("🔄", "orders-icon", _bl("Avg Orders / Customer", "客均订单数"),
                      f"{avg_orders:.2f}", None,
                      "Lifetime in current selection",
                      "Mean number of orders per active B2C customer."),
            _kpi_card("🔁", "sales-icon", _bl("Repeat Purchase Rate", "复购率"),
                      (T.format_pct(repurchase_std, 1) if repurchase_std is not None else "—"), None,
                      _bl("this ∩ prev / this period", "本月∩上月成单 / 本月成单"),
                      "复购率 = |上月成功用户 ∩ 本月成功用户| / |本月成功用户| (vs prior equal period)."),
            style="display: flex; flex-wrap: nowrap; justify-content: space-between; gap: 12px; overflow-x: auto;"
        )

    @render.ui
    @safe_render
    def user_order_freq_chart():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'] == 'B2C']
        if not {'user_id', 'order_id'}.issubset(df.columns):
            return _no_data()
        uo = df.groupby('user_id', observed=True)['order_id'].nunique()
        # Bucket: 1, 2-3, 4-5, 6-10, 11-20, 21+
        bins = [0, 1, 3, 5, 10, 20, 10**9]
        labels = ['1', '2–3', '4–5', '6–10', '11–20', '21+']
        buckets = pd.cut(uo, bins=bins, labels=labels, right=True).astype(str)
        counts = buckets.value_counts().reindex([str(l) for l in labels], fill_value=0)
        fig = go.Figure(go.Bar(
            x=counts.index, y=counts.values,
            marker=dict(color=counts.values, colorscale=T.SCALE_SEQUENTIAL, showscale=False),
            text=[T.format_int(v) for v in counts.values], textposition='outside',
            hovertemplate='<b>%{x} orders</b><br>Users: %{y:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("User order-frequency distribution"),
                      xaxis_title=_tt("Orders per user"), yaxis_title=_tt("Users"),
                      showlegend=False)
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def user_segment_order_chart():
        df = filtered_data()
        if not {'segment', 'user_id', 'order_id'}.issubset(df.columns):
            return _no_data()
        # Keep all segments for comparison context, but highlight B2C
        us = (df.groupby(['segment', 'user_id'], observed=True)['order_id']
                .nunique().groupby(level=0, observed=True).mean().reset_index())
        us.columns = ['segment', 'avg_orders']
        fig = go.Figure(go.Bar(
            x=us['segment'], y=us['avg_orders'],
            marker=dict(color=T.PALETTE[:len(us)], line=dict(color='white', width=1)),
            text=[f"{v:.2f}" for v in us['avg_orders']],
            textposition='outside', textfont=dict(size=12, color="#334155"),
            hovertemplate='<b>%{x}</b><br>Avg orders: %{y:.2f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Average orders per user · by segment"),
                      xaxis_title=None, yaxis_title=_tt("Avg orders per user"),
                      showlegend=False)
        return ui.HTML(T.fig_to_html(fig))

    # ------------------------------------------------------------------
    # Phase 3 — Customer Cohort & LTV (B2C only — Agent rows have no user_id)
    # Cohort = month of a user's first order. Tracks retention (% of cohort
    # still active) and cumulative LTV (avg cumulative revenue per cohort
    # user) by months-since-acquisition.
    # Respects segment / region / country sidebar filters; ignores date
    # range — cohort analysis needs the full history to be meaningful.
    # ------------------------------------------------------------------
    @reactive.Calc
    def cohort_data():
        df = data_rv()
        df = _filter_by_sidebar(df)
        # Cohorts require user identity — limit to B2C rows that have user_id
        if 'user_id' not in df.columns or 'order_time' not in df.columns:
            return None
        df = df[df['segment'] == 'B2C'] if 'segment' in df.columns else df
        df = df.dropna(subset=['user_id', 'order_time']).copy()
        if df.empty:
            return None

        df['order_month'] = df['order_time'].dt.to_period('M')
        first_order = df.groupby('user_id', observed=True)['order_month'].min().rename('cohort')
        df = df.merge(first_order, on='user_id', how='left')

        def _delta_months(p1, p2):
            try:
                return (p1.year - p2.year) * 12 + (p1.month - p2.month)
            except Exception:
                return None

        df['months_since'] = [
            _delta_months(om, c) for om, c in zip(df['order_month'], df['cohort'])
        ]
        df = df.dropna(subset=['months_since'])
        if df.empty:
            return None
        df['months_since'] = df['months_since'].astype(int)
        df['cohort_str'] = df['cohort'].astype(str)

        cohort_sizes = first_order.astype(str).value_counts().sort_index()

        # Retention: count of unique users active in each (cohort × month)
        ret = df.groupby(['cohort_str', 'months_since'], observed=True)['user_id'].nunique().unstack(fill_value=0)
        ret_pct = ret.div(cohort_sizes.reindex(ret.index), axis=0) * 100.0

        # LTV: cumulative revenue per user
        currency = currency_converter()
        if 'sales' in df.columns:
            rev = (df.groupby(['cohort_str', 'months_since'], observed=True)['sales'].sum()
                       .unstack(fill_value=0) * currency['rate'])
            ltv = rev.cumsum(axis=1).div(cohort_sizes.reindex(rev.index), axis=0)
        else:
            ltv = pd.DataFrame(index=ret_pct.index)

        # Limit to last 18 cohorts for readability
        wanted = list(ret_pct.index)[-18:]
        ret_pct = ret_pct.loc[wanted]
        ltv = ltv.loc[wanted]
        cohort_sizes = cohort_sizes.reindex(wanted)

        # Trim columns to a sensible window (0..18)
        max_col = min(18, max(ret_pct.columns.max() if len(ret_pct.columns) else 0,
                              ltv.columns.max()      if len(ltv.columns) else 0))
        cols = list(range(0, max_col + 1))
        ret_pct = ret_pct.reindex(columns=cols, fill_value=0)
        ltv     = ltv.reindex(columns=cols, fill_value=np.nan)

        return {
            'retention_pct': ret_pct,
            'ltv': ltv,
            'cohort_sizes': cohort_sizes,
            'symbol': currency['symbol'],
            'label':  currency['label'],
        }

    @render.ui
    @safe_render
    def cohort_heatmap():
        d = cohort_data()
        if d is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No B2C user data with timestamps in current selection.</div>')
        metric = input.cohort_metric() if hasattr(input, 'cohort_metric') else "Retention %"
        if metric == "Cumulative LTV":
            mat = d['ltv'].copy()
            title = f"Cumulative LTV per cohort user · {d['label']}"
            ctxt  = f"LTV ({d['symbol']})"
            hover_fmt = d['symbol'] + '%{z:,.2f}'
        else:
            mat = d['retention_pct'].copy()
            title = "Retention % per cohort"
            ctxt  = "% retained"
            hover_fmt = '%{z:.1f}%'
        if mat.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">Cohort matrix is empty.</div>')
        # Mask the first column (cohort always 100% retained / starting LTV)
        mat_for_color = mat.copy()
        if metric == "Retention %":
            mat_for_color.iloc[:, 0] = np.nan  # don't let the 100% column dominate the colorscale

        # Small-sample guard (A7): flag cohorts with < min_n customers (noisy tail).
        sizes = d['cohort_sizes']
        min_n = max(30, int((sizes.max() if len(sizes) else 0) * 0.05))
        ylabels = [f"{c}  (n={sizes.get(c, 0):,.0f})" + (" ⚠" if (sizes.get(c, 0) or 0) < min_n else "")
                   for c in mat.index]
        fig = go.Figure(go.Heatmap(
            z=mat_for_color.values, x=mat.columns.astype(str),
            y=ylabels,
            colorscale=T.SCALE_SEQUENTIAL, showscale=True,
            colorbar=dict(title=dict(text=ctxt, font=dict(size=11)), thickness=12, len=0.7),
            hovertemplate=('<b>Cohort:</b> %{y}<br>'
                          '<b>Months since first order:</b> %{x}<br>'
                          '<b>' + ctxt + ':</b> ' + hover_fmt + '<extra></extra>'),
        ))
        # Inline labels when matrix is small
        if mat.size <= 240:
            txt = mat.copy()
            if metric == "Retention %":
                txt = txt.round(0).astype(int).astype(str) + "%"
            else:
                txt = txt.map(lambda v: T.format_number(v, d['symbol']) if pd.notna(v) else "—")
            fig.update_traces(text=txt.values, texttemplate='%{text}',
                              textfont=dict(size=9, color="#0F172A"))

        T.apply_theme(fig, title=title,
                      xaxis_title=_tt("Months since first order"),
                      yaxis_title=_tt("Cohort (month of first order)"),
                      margin=dict(l=10, r=10, t=66, b=10),
                      height=max(380, 24 * len(mat) + 100))
        fig.add_annotation(
            text=f"⚠ = cohort with fewer than {min_n:,} customers (small sample — interpret with caution)",
            xref="paper", yref="paper", x=0, y=1.05, showarrow=False,
            font=dict(size=10, color="#94A3B8"), align="left")
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def cohort_ltv_curves():
        d = cohort_data()
        if d is None:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No B2C user data with timestamps in current selection.</div>')
        ltv = d['ltv']
        if ltv.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">LTV data not available (sales column required).</div>')
        sym = d['symbol']
        # Plot last 6 cohorts overlaid + an average curve
        last_cohorts = list(ltv.index)[-6:]
        fig = go.Figure()
        for i, c in enumerate(last_cohorts):
            row = ltv.loc[c].dropna()
            fig.add_trace(go.Scatter(
                x=row.index.astype(int), y=row.values,
                name=str(c), mode='lines+markers',
                line=dict(width=2, color=T.PALETTE[i % len(T.PALETTE)]),
                marker=dict(size=5, line=dict(color='white', width=1)),
                hovertemplate='<b>' + str(c) + '</b><br>Month %{x}<br>LTV: ' + sym + '%{y:,.2f}<extra></extra>',
            ))
        # Average curve
        avg = ltv.mean(axis=0, skipna=True)
        fig.add_trace(go.Scatter(
            x=avg.index.astype(int), y=avg.values,
            name=_tt('Average'), mode='lines',
            line=dict(color="#0F172A", width=3, dash='dot'),
            hovertemplate='<b>Average</b><br>Month %{x}<br>LTV: ' + sym + '%{y:,.2f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Cumulative LTV curves · last 6 cohorts vs average ({d['label']})"),
                      xaxis_title=_tt("Months since first order"),
                      yaxis_title=_tt(f"Cumulative LTV / user ({sym})"),
                      hovermode='x unified',
                      legend=dict(orientation="h", yanchor="bottom", y=-0.25, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def cohort_kpis():
        d = cohort_data()
        if d is None:
            return _no_data("Cohort KPIs require B2C orders with user_id and order_time in the current selection.")
        ltv = d['ltv']
        sym = d['symbol']

        def _avg_at(month_n):
            if month_n not in ltv.columns:
                return None
            # Only average across cohorts old enough to have month_n of data
            col = ltv[month_n].dropna()
            if col.empty:
                return None
            return float(col.mean())

        ltv_30  = _avg_at(1)    # ~30 days after first order
        ltv_90  = _avg_at(3)    # ~3 months
        ltv_365 = _avg_at(12)   # ~12 months

        return ui.tags.div(
            _kpi_card("📅", "users-icon", "30-day LTV",
                      T.format_number(ltv_30, sym) if ltv_30 is not None else "—",
                      None, "Average cumulative revenue per user in their first month",
                      "30-day LTV — mean across all cohorts with ≥1 month of history."),
            _kpi_card("🗓", "users-icon", "90-day LTV",
                      T.format_number(ltv_90, sym) if ltv_90 is not None else "—",
                      None, "By month 3",
                      "90-day LTV — mean across all cohorts with ≥3 months of history."),
            _kpi_card("📆", "users-icon", "1-year LTV",
                      T.format_number(ltv_365, sym) if ltv_365 is not None else "—",
                      None, "By month 12",
                      "1-year LTV — mean across all cohorts with ≥12 months of history."),
            _kpi_card("👥", "users-icon", "Cohorts tracked",
                      T.format_int(len(d['cohort_sizes'])),
                      None, f"{T.format_int(d['cohort_sizes'].sum())} unique B2C users",
                      "Number of monthly acquisition cohorts shown in the heatmap."),
            style="display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px;"
        )

    @render.data_frame
    @safe_grid
    def user_summary_table():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'] == 'B2C']
        if not {'user_id', 'order_id', 'sales'}.issubset(df.columns):
            return render.DataGrid(pd.DataFrame())
        currency = currency_converter()
        src_col = next((c for c in df.columns if c.lower() in ('user_source', '用户来源', 'source', 'channel')), None)
        grp_col = src_col if src_col else 'segment'
        if grp_col not in df.columns:
            df['segment'] = 'B2C'
            grp_col = 'segment'
        _ugrp = df.groupby([grp_col, 'user_id'], observed=True)
        user_df = pd.DataFrame({
            'orders':  _ugrp['order_id'].nunique(),
            'revenue': _ugrp['sales'].sum(),
        }).reset_index()
        user_df['revenue'] *= currency['rate']
        _sgrp = user_df.groupby(grp_col, observed=True)
        summary = pd.DataFrame({
            'Total_Customers':          _sgrp['user_id'].nunique(),
            'Avg_Orders':               _sgrp['orders'].mean(),
            'Total_Revenue':            _sgrp['revenue'].sum(),
            'Avg_Revenue_per_Customer': _sgrp['revenue'].mean(),
        }).reset_index()
        repeaters = user_df[user_df['orders'] > 1].groupby(grp_col, observed=True)['user_id'].nunique()
        summary['Repeat_Purchase_Pct'] = (repeaters.reindex(summary[grp_col].values).values
                                           / summary['Total_Customers'] * 100)
        summary.rename(columns={grp_col: 'Source / Group'}, inplace=True)
        num_cols = ['Total_Revenue', 'Avg_Revenue_per_Customer']
        pct_cols = ['Repeat_Purchase_Pct']
        for c in num_cols:
            summary[c] = summary[c].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        for c in pct_cols:
            summary[c] = summary[c].map(lambda x: f"{x:.2f}%" if pd.notna(x) else "—")
        summary['Total_Customers'] = summary['Total_Customers'].map(lambda x: f"{x:,}")
        summary['Avg_Orders'] = summary['Avg_Orders'].map(lambda x: f"{x:.2f}" if pd.notna(x) else "—")
        summary.columns = ['Source / Group', 'Total Customers', 'Avg Orders', 'Total Revenue', 'Avg Revenue/Customer', 'Repeat Purchase %']
        return render.DataGrid(_tdf(summary), filters=True)

    # ── B2B Agent Analytics ───────────────────────────────────────────────────

    @render.ui
    @safe_render
    def b2b_agent_kpis():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2B']
        if not {'order_id', 'sales'}.issubset(df.columns) or df.empty:
            return ui.p("No B2B orders found in the selected period.", style="color:#64748B;")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        # Use agent_name if available (after cache rebuild), else fall back to user_id or order count
        agent_id_col = next((c for c in ('agent_name', 'user_id') if c in df.columns and df[c].notna().any()), None)
        total_agents = df[agent_id_col].nunique() if agent_id_col else df['order_id'].nunique()
        total_rev    = df['sales'].sum() * rate
        total_orders = df['order_id'].nunique()
        avg_rev      = total_rev / max(total_agents, 1)
        aov          = total_rev / max(total_orders, 1)
        grp_col      = agent_id_col or 'order_id'
        agent_rev    = df.groupby(grp_col, observed=True)['sales'].sum().mul(rate).sort_values(ascending=False)
        top3_share   = (agent_rev.head(3).sum() / agent_rev.sum() * 100) if agent_rev.sum() > 0 else 0.0
        risk_color   = T.DANGER if top3_share >= 70 else (T.WARNING if top3_share >= 50 else T.SUCCESS)
        agents_label = (
            "Unique agent accounts (agent_name) in the selected period."
            if agent_id_col == 'agent_name' else
            "Showing order-based count — click 'Rebuild Data Pipeline' in sidebar to load agent names."
        )
        return ui.tags.div(
            _kpi_card("🏢", "supplier-icon", _bl("Active Agents", "活跃代理商数"),
                      f"{total_agents:,}", None,
                      "B2B accounts with ≥1 order in period",
                      agents_label),
            _kpi_card("💰", "sales-icon", _bl("Total B2B Revenue", "B2B总收入"),
                      T.format_full(total_rev, sym), None,
                      f"Avg per agent: {T.format_full(avg_rev, sym)}",
                      "Total GMV from B2B (agent) channel in the selected period."),
            _kpi_card("📦", "orders-icon", _bl("Total B2B Orders", "B2B订单总量"),
                      f"{total_orders:,}", None,
                      f"AOV: {T.format_full(aov, sym)}",
                      "Total order count from B2B agents. AOV = GMV ÷ orders."),
            _kpi_card("⚠️", "countries-icon", _bl("Top-3 Agent Concentration", "前3代理商集中度"),
                      f"{top3_share:.1f}%", None,
                      "of B2B GMV from top 3 agents",
                      "Concentration risk: ≥70% = high, 50-70% = moderate, <50% = healthy diversification."),
            style="display:flex; flex-wrap:wrap; gap:12px;"
        )

    @render.ui
    @safe_render
    def b2b_agent_revenue_chart():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2B']
        if 'sales' not in df.columns or df.empty:
            return ui.HTML('<div style="color:#64748B;padding:12px;">No B2B data available.</div>')
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        label_col = next((c for c in ('agent_name', 'user_id') if c in df.columns and df[c].notna().any()), 'order_id')
        agg = (df.groupby(label_col, observed=True)['sales'].sum()
               .mul(rate).nlargest(20).reset_index())
        agg.columns = ['Agent', 'Revenue']
        agg = agg.sort_values('Revenue', ascending=True)
        total = agg['Revenue'].sum()
        agg['share'] = (agg['Revenue'] / total * 100).round(1) if total > 0 else 0.0
        fig = go.Figure(go.Bar(
            x=agg['Revenue'], y=agg['Agent'].astype(str),
            orientation='h',
            marker=dict(color=agg['Revenue'], colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[f"{sym}{v:,.0f}  ({s:.1f}%)" for v, s in zip(agg['Revenue'], agg['share'])],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate='<b>%{y}</b><br>Revenue: ' + sym + '%{x:,.0f}<br>Share: %{customdata:.1f}%<extra></extra>',
            customdata=agg['share'],
        ))
        T.apply_theme(fig,
                      title=_tt(f"Top 20 B2B Agents by Revenue · {currency['label']}"),
                      xaxis_title=_tt(f"Revenue ({sym})"), yaxis_title=None,
                      margin=dict(l=10, r=180, t=50, b=10), height=520)
        return ui.HTML(T.fig_to_html(fig))

    # ── B2C Churn Risk Analysis ───────────────────────────────────────────────

    @render.ui
    @safe_render
    def b2c_churn_risk_panel():
        df = data_rv()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        if not {'user_id', 'order_time'}.issubset(df.columns) or df.empty:
            return ui.p("B2C churn analysis requires user_id and order_time columns.",
                        style="color:#64748B;")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        today = pd.Timestamp.now().normalize()
        last_ord = df.groupby('user_id', observed=True)['order_time'].max().reset_index()
        last_ord.columns = ['user_id', 'last_order']
        last_ord['days_ago'] = (today - last_ord['last_order']).dt.days
        active   = int((last_ord['days_ago'] <= 30).sum())
        at_risk  = int(((last_ord['days_ago'] > 30) & (last_ord['days_ago'] <= 90)).sum())
        lapsed   = int((last_ord['days_ago'] > 90).sum())
        total    = len(last_ord)
        # Revenue at risk (historical GMV of at-risk customers)
        if 'sales' in df.columns:
            at_risk_ids = last_ord[(last_ord['days_ago'] > 30) & (last_ord['days_ago'] <= 90)]['user_id']
            rev_at_risk = df[df['user_id'].isin(at_risk_ids)]['sales'].sum() * rate
        else:
            rev_at_risk = 0.0
        def _pct(n): return f"{n/total*100:.1f}% of customers" if total > 0 else "—"
        return ui.tags.div(
            _kpi_card("✅", "sales-icon", _bl("Active (≤30 days)", "活跃（30天内有购买）"),
                      f"{active:,}", None,
                      _pct(active),
                      "B2C customers who placed at least one order in the last 30 days."),
            _kpi_card("⚠️", "orders-icon", _bl("At Risk (31–90 days)", "高危（31–90天无购买）"),
                      f"{at_risk:,}", None,
                      f"{_pct(at_risk)} · {T.format_full(rev_at_risk, sym)} GMV at risk",
                      "Last order 31-90 days ago. Prime re-engagement window before they lapse."),
            _kpi_card("🚨", "countries-icon", _bl("Lapsed (90+ days)", "流失（90天以上无购买）"),
                      f"{lapsed:,}", None,
                      _pct(lapsed),
                      "Last order over 90 days ago. Recovery campaign or win-back offer needed."),
            _kpi_card("👥", "users-icon", _bl("Total B2C Customers", "B2C客户总数"),
                      f"{total:,}", None,
                      "All-time across full data history",
                      "Total unique B2C customers ever recorded in the system."),
            style="display:flex; flex-wrap:wrap; gap:12px;"
        )

    # ── B2C Registration Funnel ───────────────────────────────────────────────

    @render.ui
    @safe_render
    def b2c_registration_funnel():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        if not {'user_id', 'order_time', 'register_time'}.issubset(df.columns) or df.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">'
                           'Registration funnel requires register_time (注册时间) in the B2C data.</div>')
        df2 = df.dropna(subset=['register_time', 'order_time'])
        if df2.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No registration time data available.</div>')
        first_reg  = df2.groupby('user_id', observed=True)['register_time'].min()
        first_ord  = df2.groupby('user_id', observed=True)['order_time'].min()
        ttf = pd.DataFrame({'register_time': first_reg, 'first_order': first_ord})
        ttf = ttf.dropna()
        ttf['days'] = (ttf['first_order'] - ttf['register_time']).dt.days.clip(lower=0)

        def _bucket(d):
            if d == 0:   return 'Same Day'
            if d <= 7:   return 'Within 7 Days'
            if d <= 30:  return '8–30 Days'
            if d <= 90:  return '31–90 Days'
            return '91+ Days'

        ttf['bucket'] = ttf['days'].map(_bucket)
        order = ['Same Day', 'Within 7 Days', '8–30 Days', '31–90 Days', '91+ Days']
        counts = ttf['bucket'].value_counts().reindex(order, fill_value=0)
        total_conv = counts.sum()
        fig = go.Figure(go.Bar(
            x=counts.values,
            y=counts.index,
            orientation='h',
            marker=dict(
                color=[T.SUCCESS, T.PRIMARY, T.WARNING, '#F97316', T.DANGER],
                line=dict(color='white', width=1),
            ),
            text=[f"{v:,}  ({v/total_conv*100:.1f}%)" if total_conv > 0 else f"{v:,}" for v in counts.values],
            textposition='outside',
            textfont=dict(size=11),
            hovertemplate='<b>%{y}</b><br>Customers: %{x:,}<extra></extra>',
        ))
        T.apply_theme(fig,
                      title=_tt("Time from Registration to First Purchase (B2C)"),
                      xaxis_title=_tt("Number of Customers"), yaxis_title=None,
                      margin=dict(l=10, r=160, t=50, b=10), height=320,
                      yaxis=dict(autorange='reversed'))
        return ui.HTML(T.fig_to_html(fig))

    # ── B2C IP Geographic Origin Analysis ─────────────────────────────────────

    @render.ui
    @safe_render
    def b2c_ip_analysis():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2C']
        if 'ip_country' not in df.columns or 'country' not in df.columns:
            return ui.HTML('<div style="color:#64748B;padding:20px;">'
                           'IP analysis requires ip_country (ip国家) in the B2C data.</div>')
        df2 = df.dropna(subset=['country', 'ip_country'])
        if df2.empty:
            return ui.HTML('<div style="color:#64748B;padding:20px;">No IP country data available.</div>')
        # Mismatch: order country ≠ ip country
        df2 = df2.copy()
        df2['mismatch'] = df2['country'].astype(str).str.strip() != df2['ip_country'].astype(str).str.strip()
        total = len(df2)
        mismatches = int(df2['mismatch'].sum())
        mismatch_pct = mismatches / total * 100 if total > 0 else 0.0
        # Top IP countries
        top_ip = df2['ip_country'].value_counts().head(15).reset_index()
        top_ip.columns = ['IP Country', 'Orders']
        top_ip = top_ip.sort_values('Orders', ascending=True)
        mismatch_color = T.DANGER if mismatch_pct > 20 else (T.WARNING if mismatch_pct > 5 else T.SUCCESS)
        mismatch_badge = (
            f'<div style="background:{mismatch_color};color:white;display:inline-block;'
            f'padding:6px 14px;border-radius:6px;font-size:13px;font-weight:600;margin-bottom:12px;">'
            f'Country–IP Mismatch: {mismatches:,} orders ({mismatch_pct:.1f}%)'
            f'</div>'
        )
        bar_fig = go.Figure(go.Bar(
            x=top_ip['Orders'], y=top_ip['IP Country'],
            orientation='h',
            marker=dict(color=top_ip['Orders'], colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[T.format_int(v) for v in top_ip['Orders']],
            textposition='outside', textfont=dict(size=11, color="#334155"),
            hovertemplate='<b>%{y}</b><br>Orders: %{x:,}<extra></extra>',
        ))
        T.apply_theme(bar_fig, title=_tt("Top 15 IP Countries (B2C Order Origin)"),
                      xaxis_title=_tt("Orders"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=420)
        # NOTE: the world choropleth map ("Global IP Origin Distribution") was
        # removed — low decision value vs. its visual weight. The country–IP
        # mismatch badge + Top-15 IP countries bar below preserve the useful
        # fraud / VPN signal (see Dashboard_Review_Findings A8).
        return ui.tags.div(
            ui.HTML(mismatch_badge),
            ui.HTML(T.fig_to_html(bar_fig)),
        )

    # ── B2B Agent Performance ─────────────────────────────────────────────────

    @render.data_frame
    @safe_grid
    def agent_performance_table():
        df = filtered_data()
        if 'segment' in df.columns:
            df = df[df['segment'].astype(str).str.upper() == 'B2B']
        if not {'order_id', 'sales'}.issubset(df.columns):
            return render.DataGrid(pd.DataFrame({'Status': ['B2B agent data not available.']}))
        if df.empty:
            return render.DataGrid(pd.DataFrame({'Status': ['No B2B orders found in the selected period.']}))
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        has_name = 'agent_name' in df.columns and df['agent_name'].notna().any()
        has_uid  = 'user_id' in df.columns and df['user_id'].notna().any()
        if has_name and has_uid:
            id_cols = ['agent_name', 'user_id']
        elif has_name:
            id_cols = ['agent_name']
        elif has_uid:
            id_cols = ['user_id']
        else:
            id_cols = ['order_id']
        grp = df.groupby(id_cols, observed=True)
        orders_s  = grp['order_id'].nunique()
        revenue_s = grp['sales'].sum()
        scol = 'settlement_rmb' if 'settlement_rmb' in df.columns else (
            'settlement_price' if 'settlement_price' in df.columns else None)
        agg = pd.DataFrame({'orders': orders_s, 'revenue': revenue_s}).reset_index()
        agg['revenue'] = agg['revenue'] * rate
        if scol:   # 3.4 customer/agent-level profitability — join margin (revenue − COGS)
            cost_df = grp[scol].sum(min_count=1).reset_index().rename(columns={scol: '_cost'})
            agg = agg.merge(cost_df, on=id_cols, how='left')
            agg['margin'] = agg['revenue'] - pd.to_numeric(agg['_cost'], errors='coerce') * rate
            agg['margin_pct'] = agg['margin'] / agg['revenue'].replace(0, np.nan) * 100
        agg['aov'] = agg['revenue'] / agg['orders'].replace(0, np.nan)
        agg = agg.sort_values('revenue', ascending=False).head(50)
        total_rev = agg['revenue'].sum()
        agg['share_pct'] = (agg['revenue'] / total_rev * 100).round(2) if total_rev > 0 else 0.0
        agg['cum_pct']   = agg['share_pct'].cumsum().round(2)

        # Build the display frame with explicit, ordered columns (robust to id_cols).
        id_label = {'agent_name': 'Agent Name', 'user_id': 'Agent ID', 'order_id': 'Order ID'}
        out = pd.DataFrame()
        for c in id_cols:
            out[id_label.get(c, c)] = agg[c]
        out['Orders'] = agg['orders'].apply(lambda x: f"{int(x):,}")
        out[f'Revenue ({sym})'] = agg['revenue'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        if 'margin' in agg.columns:
            out[f'Gross Margin ({sym})'] = agg['margin'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
            out['Margin %'] = agg['margin_pct'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        out[f'AOV ({sym})'] = agg['aov'].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        out['Revenue Share %'] = agg['share_pct'].apply(lambda x: f"{x:.2f}%")
        out['Cum. Share %'] = agg['cum_pct'].apply(lambda x: f"{x:.2f}%")
        return render.DataGrid(_tdf(out), filters=True)

    # ── Marketing & Promotions (B2C coupons / promos / merchandising) ────────

    @reactive.Calc
    def _promo_frame():
        """B2C rows with normalised promo flags. None when coupon data absent."""
        df = filtered_data()
        if 'coupon_used' not in df.columns:
            return None
        d = df[df['segment'] == 'B2C'].copy() if 'segment' in df.columns else df.copy()
        if d.empty:
            return None
        d['coupon_used'] = d['coupon_used'].astype('string')
        return d

    @render.ui
    @safe_render
    def marketing_kpis():
        d = _promo_frame()
        if d is None:
            return _no_data("Coupon data (是否使用优惠券) not loaded — click 'Refresh Cache' in the sidebar.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        total_orders = d['order_id'].nunique() if 'order_id' in d.columns else len(d)
        cp = d[d['coupon_used'] == '是']
        cp_orders = cp['order_id'].nunique() if 'order_id' in cp.columns else len(cp)
        usage_rate = cp_orders / total_orders * 100 if total_orders else 0
        coupon_spend = float(cp['coupon_amount'].sum() * rate) if 'coupon_amount' in cp.columns else 0.0
        coupon_gmv = float(cp['sales'].sum() * rate) if 'sales' in cp.columns else 0.0
        roi = coupon_gmv / coupon_spend if coupon_spend > 0 else None
        nup = d[d['new_user_promo'] == '是'] if 'new_user_promo' in d.columns else d.iloc[0:0]
        nup_orders = nup['order_id'].nunique() if 'order_id' in nup.columns else len(nup)
        badge_share = None
        if 'badge_product' in d.columns and 'sales' in d.columns:
            tot = d['sales'].sum()
            if tot and tot > 0:
                badge_share = float(d.loc[d['badge_product'] == '是', 'sales'].sum()) / float(tot) * 100
        return ui.tags.div(
            _kpi_card("🎟️", "orders-icon", _bl("Coupon Usage Rate", "优惠券使用率"),
                      f"{usage_rate:.2f}%", None,
                      f"{T.format_int(cp_orders)} of {T.format_int(total_orders)} B2C orders",
                      "Share of B2C orders that used a coupon in the selected period."),
            _kpi_card("💸", "countries-icon", _bl("Coupon Spend", "优惠券支出"),
                      T.format_number(coupon_spend, sym), None,
                      f"GMV per {sym.strip() or '¥'}1 coupon: {roi:.1f}" if roi else "—",
                      "Total discount value given out (优惠券金额)."),
            _kpi_card("💰", "sales-icon", _bl("Coupon-Order GMV", "券单收入"),
                      T.format_number(coupon_gmv, sym), None,
                      "Revenue of orders that used a coupon",
                      "GMV generated by coupon orders — compare against coupon spend for ROI."),
            _kpi_card("🆕", "users-icon", _bl("New-User Promo Orders", "新人优惠订单"),
                      T.format_int(nup_orders), None,
                      (f"Badge-product GMV share: {badge_share:.1f}%" if badge_share is not None else "—"),
                      "Orders flagged 是否新人优惠 = 是 (acquisition promotions)."),
            class_="metrics-grid"
        )

    @render.ui
    @safe_render
    def coupon_roi_trend_chart():
        d = _promo_frame()
        if d is None:
            return _no_data("Coupon data not available.")
        if 'order_time' not in d.columns:
            return _no_data("Order time column not available.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        cp = d[d['coupon_used'] == '是'].dropna(subset=['order_time']).copy()
        if cp.empty:
            return _no_data("No coupon orders in the current selection.")
        cp['month'] = cp['order_time'].dt.to_period('M').dt.start_time
        grp = cp.groupby('month', observed=True)
        spend_s = grp['coupon_amount'].sum() * rate if 'coupon_amount' in cp.columns else grp.size() * 0
        gmv_s   = grp['sales'].sum() * rate if 'sales' in cp.columns else grp.size() * 0
        orders_s = grp['order_id'].nunique() if 'order_id' in cp.columns else grp.size()
        agg = pd.DataFrame({'spend': spend_s, 'gmv': gmv_s, 'orders': orders_s}).reset_index()
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=agg['month'], y=agg['spend'], name=_tt('Coupon spend'),
            marker=dict(color=T.DANGER, opacity=0.75),
            hovertemplate='<b>%{x|%b %Y}</b><br>Coupon spend: ' + sym + '%{y:,.0f}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=agg['month'], y=agg['gmv'], name=_tt('Coupon-order GMV'),
            mode='lines+markers', line=dict(color=T.SUCCESS, width=2.5, shape='spline'),
            marker=dict(size=7, line=dict(color='white', width=1)),
            customdata=agg['orders'],
            hovertemplate='<b>%{x|%b %Y}</b><br>GMV: ' + sym + '%{y:,.0f}<br>Orders: %{customdata:,}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt(f"Coupon Spend vs Coupon-Order Revenue · {currency['label']}"),
                      xaxis_title=None, yaxis_title=_tt(f"Amount ({sym})"),
                      hovermode='x unified', height=420,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0))
        return ui.HTML(T.fig_to_html(fig))

    def _campaign_table_data():
        d = _promo_frame()
        if d is None or 'coupon_name' not in d.columns:
            return pd.DataFrame()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        cp = d[(d['coupon_used'] == '是') & d['coupon_name'].notna()].copy()
        if cp.empty:
            return pd.DataFrame()
        cp['coupon_name'] = cp['coupon_name'].astype(str)
        grp = cp.groupby('coupon_name', observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in cp.columns else grp.size()
        spend_s  = grp['coupon_amount'].sum() * rate if 'coupon_amount' in cp.columns else orders_s * 0
        gmv_s    = grp['sales'].sum() * rate if 'sales' in cp.columns else orders_s * 0
        users_s  = grp['user_id'].nunique() if 'user_id' in cp.columns else orders_s
        agg = pd.DataFrame({'orders': orders_s, 'spend': spend_s,
                            'gmv': gmv_s, 'customers': users_s}).reset_index()
        agg['avg_discount'] = agg['spend'] / agg['orders'].replace(0, np.nan)
        agg['gmv_per_unit'] = agg['gmv'] / agg['spend'].replace(0, np.nan)
        agg = agg.sort_values('spend', ascending=False)
        out = agg.rename(columns={
            'coupon_name': 'Campaign / Coupon',
            'orders': 'Orders',
            'customers': 'Customers',
            'spend': f'Coupon Spend ({sym})',
            'gmv': f'Order GMV ({sym})',
            'avg_discount': f'Avg Discount ({sym})',
            'gmv_per_unit': 'GMV per 1 Spend',
        })
        for c in out.columns:
            if c.startswith(('Coupon Spend', 'Order GMV', 'Avg Discount')):
                out[c] = out[c].apply(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        out['GMV per 1 Spend'] = out['GMV per 1 Spend'].apply(lambda x: f"{x:,.1f}×" if pd.notna(x) else "—")
        out['Orders'] = out['Orders'].apply(lambda x: f"{int(x):,}")
        out['Customers'] = out['Customers'].apply(lambda x: f"{int(x):,}")
        return out

    @render.data_frame
    @safe_grid
    def campaign_performance_table():
        out = _campaign_table_data()
        if out.empty:
            return render.DataGrid(pd.DataFrame({'Status': ['No coupon campaigns in the current selection.']}))
        return render.DataGrid(_tdf(out.head(100)), filters=True)

    @render.download(filename=lambda: _make_filename("campaign_performance", "xlsx"))
    def download_campaign_table():
        yield _xlsx_bytes(_campaign_table_data())

    @render.ui
    @safe_render
    def coupon_vs_noncoupon_chart():
        d = _promo_frame()
        if d is None:
            return _no_data("Coupon data not available.")
        if not {'user_id', 'order_id', 'sales'}.issubset(d.columns):
            return _no_data("Needs user_id / order_id / sales columns.")
        # Customer-level: a 'coupon customer' used a coupon at least once.
        cu = d.groupby('user_id', observed=True)['coupon_used'] \
              .apply(lambda s: (s == '是').any())
        orders_per_user = d.groupby('user_id', observed=True)['order_id'].nunique()
        rev_per_user = d.groupby('user_id', observed=True)['sales'].sum()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        rows = []
        for flag, label in [(True, 'Coupon users'), (False, 'Non-coupon users')]:
            ids = cu[cu == flag].index
            if len(ids) == 0:
                continue
            opu = orders_per_user.loc[ids]
            rows.append({
                'group': label,
                'customers': len(ids),
                'aov': float(rev_per_user.loc[ids].sum() * rate) / max(int(opu.sum()), 1),
                'repeat_rate': float((opu > 1).mean() * 100),
            })
        if not rows:
            return _no_data()
        agg = pd.DataFrame(rows)
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=1, cols=2, subplot_titles=(_tt("Avg Order Value"), _tt("Repeat-Purchase Rate (%)")),
                            horizontal_spacing=0.15)
        colors = [T.PRIMARY, "#94A3B8"]
        fig.add_trace(go.Bar(
            x=agg['group'], y=agg['aov'], marker=dict(color=colors),
            text=[f"{sym}{v:,.2f}" for v in agg['aov']], textposition='outside',
            hovertemplate='<b>%{x}</b><br>AOV: ' + sym + '%{y:,.2f}<extra></extra>',
            showlegend=False), row=1, col=1)
        fig.add_trace(go.Bar(
            x=agg['group'], y=agg['repeat_rate'], marker=dict(color=colors),
            text=[f"{v:.1f}%" for v in agg['repeat_rate']], textposition='outside',
            customdata=agg['customers'],
            hovertemplate='<b>%{x}</b><br>Repeat rate: %{y:.1f}%<br>Customers: %{customdata:,}<extra></extra>',
            showlegend=False), row=1, col=2)
        T.apply_theme(fig, title=_tt("Coupon vs Non-Coupon Customers — Value & Loyalty"),
                      showlegend=False, height=400, margin=dict(l=10, r=10, t=70, b=30))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def new_user_promo_chart():
        d = _promo_frame()
        if d is None or 'new_user_promo' not in d.columns:
            return _no_data("New-user promo flag (是否新人优惠) not available.")
        if 'order_time' not in d.columns:
            return _no_data("Order time column not available.")
        d2 = d.dropna(subset=['order_time']).copy()
        d2['month'] = d2['order_time'].dt.to_period('M').dt.start_time
        promo = d2[d2['new_user_promo'] == '是']
        if promo.empty:
            return _no_data("No new-user promo orders in the current selection.")
        if 'order_id' in d2.columns:
            total_s = d2.groupby('month', observed=True)['order_id'].nunique()
            promo_s = promo.groupby('month', observed=True)['order_id'].nunique()
        else:
            total_s = d2.groupby('month', observed=True).size()
            promo_s = promo.groupby('month', observed=True).size()
        promo_s = promo_s.reindex(total_s.index, fill_value=0)
        share = (promo_s / total_s.replace(0, np.nan) * 100)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=promo_s.index, y=promo_s.values, name=_tt('New-user promo orders'),
            marker=dict(color=T.INFO, opacity=0.8),
            hovertemplate='<b>%{x|%b %Y}</b><br>Promo orders: %{y:,}<extra></extra>',
        ))
        fig.add_trace(go.Scatter(
            x=share.index, y=share.values, name=_tt('Share of all orders (%)'),
            yaxis='y2', mode='lines+markers',
            line=dict(color=T.ACCENT, width=2.5),
            marker=dict(size=7, line=dict(color='white', width=1)),
            hovertemplate='<b>%{x|%b %Y}</b><br>Share: %{y:.2f}%<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("New-User Promo Orders by Month"),
                      xaxis_title=None, yaxis_title=_tt("Orders"),
                      yaxis2=dict(title=_tt("Share (%)"), overlaying='y', side='right',
                                  showgrid=False, ticksuffix="%"),
                      height=400,
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=60, t=60, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def badge_product_chart():
        d = _promo_frame()
        if d is None or 'badge_product' not in d.columns:
            return _no_data("Badge-product flag (是否角标产品) not available.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        rows = []
        for flag, label in [('是', 'Featured (badge)'), ('否', 'Not featured')]:
            sub = d[d['badge_product'] == flag]
            if sub.empty:
                continue
            orders = sub['order_id'].nunique() if 'order_id' in sub.columns else len(sub)
            rev = float(sub['sales'].sum() * rate) if 'sales' in sub.columns else 0.0
            rows.append({'group': label, 'orders': orders, 'revenue': rev,
                         'aov': rev / max(orders, 1)})
        if not rows:
            return _no_data("No badge-product data in the current selection.")
        agg = pd.DataFrame(rows)
        from plotly.subplots import make_subplots
        fig = make_subplots(rows=1, cols=2, subplot_titles=(_tt("Revenue"), _tt("Avg Order Value")),
                            horizontal_spacing=0.15)
        colors = [T.WARNING, "#94A3B8"]
        fig.add_trace(go.Bar(
            x=agg['group'], y=agg['revenue'], marker=dict(color=colors),
            text=[T.format_number(v, sym) for v in agg['revenue']], textposition='outside',
            customdata=agg['orders'],
            hovertemplate='<b>%{x}</b><br>Revenue: ' + sym + '%{y:,.0f}<br>Orders: %{customdata:,}<extra></extra>',
            showlegend=False), row=1, col=1)
        fig.add_trace(go.Bar(
            x=agg['group'], y=agg['aov'], marker=dict(color=colors),
            text=[f"{sym}{v:,.2f}" for v in agg['aov']], textposition='outside',
            hovertemplate='<b>%{x}</b><br>AOV: ' + sym + '%{y:,.2f}<extra></extra>',
            showlegend=False), row=1, col=2)
        T.apply_theme(fig, title=_tt("Featured (Badge) vs Non-Featured Products"),
                      showlegend=False, height=400, margin=dict(l=10, r=10, t=70, b=30))
        return ui.HTML(T.fig_to_html(fig))

    # ══════════════════════════════════════════════════════════════════════════
    # Sales Explorer — ad-hoc time-window / country / operator / product query
    # ══════════════════════════════════════════════════════════════════════════

    _PRESET_BANDS = {"all": (0, 24), "night": (20, 6), "morning": (6, 12), "biz": (9, 18)}

    def _q_hour_band():
        """(from, to) hour band from the preset / custom selects. to may be 24."""
        try:
            preset = input.q_preset() or "all"
        except Exception:
            preset = "all"
        if preset in _PRESET_BANDS:
            return _PRESET_BANDS[preset]
        try:
            hf = int(input.q_hour_from() or 0)
            ht = int(input.q_hour_to() or 24)
        except Exception:
            hf, ht = 0, 24
        return hf, ht

    def _hour_mask(hours, hf, ht):
        """Boolean mask for an hour Series given a band; supports midnight wrap."""
        if hf == ht:
            return hours.notna() & True            # whole day (defensive)
        if hf < ht:
            return (hours >= hf) & (hours < ht)
        # wrap past midnight, e.g. 20 -> 06
        return (hours >= hf) | (hours < ht)

    def _add_prod_label(df):
        """Add prod_label (+ vol_mb for data) to a (already small) filtered frame."""
        d = df
        # volume (data packages) — parse unique source strings once, map back
        src = None
        if 'sku_name' in d.columns:
            src = d['sku_name'].astype('string')
        if 'product' in d.columns:
            p = d['product'].astype('string')
            src = p if src is None else src.fillna(p)
        if src is not None:
            uniq = pd.unique(src.dropna())
            vmap = {u: _parse_data_volume(u) for u in uniq}
            d['vol_mb'] = src.map(lambda x: (vmap.get(x) or (None, None, None))[0] if pd.notna(x) else None)
            d['vol_label'] = src.map(lambda x: (vmap.get(x) or (None, None, None))[1] if pd.notna(x) else None)
        else:
            d['vol_mb'] = np.nan
            d['vol_label'] = pd.NA
        # generic product label: product -> product_info -> operator
        lbl = pd.Series(pd.NA, index=d.index, dtype='object')
        for c in ('product', 'product_info', 'operator'):
            if c in d.columns:
                v = d[c].astype('object').where(d[c].notna(), None)
                lbl = lbl.where(lbl.notna(), v)
        d['prod_label'] = pd.Series(lbl, index=d.index).fillna('Unknown').astype(str)
        return d

    def _explorer_filter(df, d_from, d_to, apply_status=True):
        if df is None or df.empty or 'order_time' not in df.columns:
            return df.iloc[0:0] if df is not None else pd.DataFrame()
        d = df
        # region
        try:
            region = input.q_region() or "All"
        except Exception:
            region = "All"
        if region and region != "All" and 'country' in d.columns:
            d = d[d['country'].astype(str).map(T.to_region) == region]
        # countries (multi)
        try:
            countries = list(input.q_country() or [])
        except Exception:
            countries = []
        if countries and 'country' in d.columns:
            d = d[d['country'].astype(str).isin(countries)]
        # segment
        try:
            seg = input.q_segment() or "All"
        except Exception:
            seg = "All"
        if seg and seg != "All" and 'segment' in d.columns:
            d = d[d['segment'].astype(str) == seg]
        # order status
        if apply_status:
            try:
                status = input.q_status() or "Successful"
            except Exception:
                status = "Successful"
            d = filter_by_order_status(d, status)
        # date range
        if d_from and d_to:
            dd = d['order_time'].dt.date
            lo, hi = (d_from, d_to) if d_from <= d_to else (d_to, d_from)
            d = d[(dd >= lo) & (dd <= hi)]
        # day-of-week
        try:
            dows = [int(x) for x in (input.q_dow() or [])]
        except Exception:
            dows = list(range(7))
        if dows and len(dows) < 7:
            d = d[d['order_time'].dt.dayofweek.isin(dows)]
        # hour band
        hf, ht = _q_hour_band()
        if not (hf == 0 and ht == 24):
            d = d[_hour_mask(d['order_time'].dt.hour, hf, ht)]
        # operator (multi)
        try:
            ops = list(input.q_operator() or [])
        except Exception:
            ops = []
        if ops and 'operator' in d.columns:
            d = d[d['operator'].astype(str).isin(ops)]
        if d.empty:
            return d.copy()
        d = _add_prod_label(d.copy())
        # product dimension + value
        try:
            dim = input.q_product_dim() or "all"
        except Exception:
            dim = "all"
        if dim == "data":
            d = d[d['vol_mb'].notna()]
            if not d.empty:
                d['prod_label'] = d['vol_label'].astype(str)
        elif dim == "airtime":
            if 'product_category' in d.columns:
                m = d['product_category'].astype(str).str.contains(
                    r'话费|后付费|PIN码|airtime|topup|top-up', case=False, na=False)
                d = d[m]
            if not d.empty:
                if 'sku_name' in d.columns:
                    lab = d['sku_name'].astype('string').str.strip()
                else:
                    lab = pd.Series(pd.NA, index=d.index, dtype='string')
                fb = (d['denomination'].map(_clean_denom_label).astype('string')
                      if 'denomination' in d.columns else pd.Series(pd.NA, index=d.index, dtype='string'))
                d['prod_label'] = lab.where(lab.notna() & (lab != ''), fb).fillna('Unknown').astype(str)
        try:
            pvals = list(input.q_product_value() or [])
        except Exception:
            pvals = []
        if pvals and not d.empty:
            d = d[d['prod_label'].isin(pvals)]
        return d

    @reactive.Calc
    def _explorer_dates():
        try:
            d_from = input.q_date_from()
            d_to = input.q_date_to()
        except Exception:
            d_from = d_to = session_max_date
        if d_from and d_to and d_from > d_to:
            d_from, d_to = d_to, d_from
        return d_from, d_to

    @reactive.Calc
    def _explorer_frame():
        d_from, d_to = _explorer_dates()
        return _explorer_filter(data_rv(), d_from, d_to, apply_status=True)

    @reactive.Calc
    def _explorer_frame_allstatus():
        d_from, d_to = _explorer_dates()
        return _explorer_filter(data_rv(), d_from, d_to, apply_status=False)

    @reactive.Calc
    def _explorer_prev_frame():
        d_from, d_to = _explorer_dates()
        if not (d_from and d_to):
            return pd.DataFrame()
        span = (d_to - d_from).days + 1
        prev_to = d_from - _dt.timedelta(days=1)
        prev_from = prev_to - _dt.timedelta(days=span - 1)
        return _explorer_filter(data_rv(), prev_from, prev_to, apply_status=True)

    # ---- dynamic choice builders ----
    @render.ui
    @safe_render
    def q_operator_ui():
        d_from, d_to = _explorer_dates()
        # operator choices from the slice WITHOUT the operator/product filters:
        df = data_rv()
        try:
            region = input.q_region() or "All"
            countries = list(input.q_country() or [])
            seg = input.q_segment() or "All"
        except Exception:
            region, countries, seg = "All", [], "All"
        d = df
        if region != "All" and 'country' in d.columns:
            d = d[d['country'].astype(str).map(T.to_region) == region]
        if countries and 'country' in d.columns:
            d = d[d['country'].astype(str).isin(countries)]
        if seg != "All" and 'segment' in d.columns:
            d = d[d['segment'].astype(str) == seg]
        if 'operator' not in d.columns or d.empty:
            return ui.input_selectize("q_operator", None, choices=[], multiple=True,
                                      options={"placeholder": "All operators"})
        ops = (d['operator'].astype(str).replace({'': None}).dropna()
               .value_counts().head(60).index.tolist())
        return ui.input_selectize("q_operator", None, choices=ops, multiple=True,
                                  options={"placeholder": "All operators — type to filter…"})

    @render.ui
    @safe_render
    def q_product_value_ui():
        try:
            dim = input.q_product_dim() or "all"
        except Exception:
            dim = "all"
        if dim == "all":
            return ui.tags.div(
                ui.tags.small("Choose a product type above to pick specific packages / denominations.",
                              style="color:#94A3B8;"),
                ui.input_selectize("q_product_value", None, choices=[], multiple=True),
                style="opacity:0.6;")
        d = _explorer_frame()
        if d is None or d.empty or 'prod_label' not in d.columns:
            return ui.input_selectize("q_product_value", None, choices=[], multiple=True,
                                      options={"placeholder": "All"})
        if dim == "data" and 'vol_mb' in d.columns:
            order = (d.dropna(subset=['vol_mb'])
                     .drop_duplicates('prod_label').sort_values('vol_mb')['prod_label'].tolist())
        else:
            order = sorted(d['prod_label'].dropna().unique().tolist(), key=_denom_sort_key)
        return ui.input_selectize("q_product_value", None, choices=order, multiple=True,
                                  options={"placeholder": "All — type to filter…"})

    # ---- helpers for metrics ----
    def _explorer_metrics(d, rate):
        if d is None or d.empty:
            return dict(gmv=0.0, orders=0, benef=0, margin=0.0, margin_pct=None,
                        aov=0.0, gb=0.0)
        gmv = float(d['sales'].sum() * rate) if 'sales' in d.columns else 0.0
        orders = int(d['order_id'].nunique()) if 'order_id' in d.columns else len(d)
        benef = int(d['recharge_number'].nunique()) if 'recharge_number' in d.columns else 0
        sc = _settle_col(d)
        cost = float(d[sc].sum() * rate) if sc in d.columns else 0.0
        margin = gmv - cost
        margin_pct = (margin / gmv * 100) if gmv > 0 else None
        aov = gmv / orders if orders > 0 else 0.0
        gb = float(d['vol_mb'].sum() / 1024.0) if 'vol_mb' in d.columns and d['vol_mb'].notna().any() else 0.0
        return dict(gmv=gmv, orders=orders, benef=benef, margin=margin,
                    margin_pct=margin_pct, aov=aov, gb=gb)

    def _pct_delta(cur, prev):
        if prev is None or prev == 0 or prev != prev:
            return None
        return (cur - prev) / prev * 100

    @render.ui
    @safe_render
    def explorer_caption():
        d_from, d_to = _explorer_dates()
        hf, ht = _q_hour_band()
        try:
            countries = list(input.q_country() or [])
            seg = input.q_segment() or "All"
            status = input.q_status() or "Successful"
        except Exception:
            countries, seg, status = [], "All", "Successful"
        cty = ", ".join(countries) if countries else "All markets"
        band = "whole day" if (hf == 0 and ht == 24) else f"{hf:02d}:00→{(ht % 24):02d}:00"
        dr = f"{d_from}" if d_from == d_to else f"{d_from} → {d_to}"
        currency = currency_converter()
        return ui.HTML(
            f'<div style="color:#475569;font-size:0.9em;margin-bottom:6px;">'
            f'<b>{cty}</b> · {dr} · <b>{band}</b> (MYT) · {seg} · {status} · '
            f'values in {currency["label"]}. Deltas compare the previous equivalent window.</div>')

    @render.ui
    @safe_render
    def explorer_kpis():
        cur = _explorer_frame()
        if cur is None or cur.empty:
            return _no_data("No orders match this query. Widen the date range, hours, or filters.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        m = _explorer_metrics(cur, rate)
        pm = _explorer_metrics(_explorer_prev_frame(), rate)
        allst = _explorer_frame_allstatus()
        # success / refund within window (status-agnostic)
        succ = ref = 0
        if allst is not None and not allst.empty and 'order_status' in allst.columns:
            s = allst['order_status'].astype(str).str.strip()
            succ = int(allst.loc[s.isin(ORDER_STATUS_GROUPS['Successful']), 'order_id'].nunique()
                       if 'order_id' in allst.columns else s.isin(ORDER_STATUS_GROUPS['Successful']).sum())
            ref = int(allst.loc[s.isin(ORDER_STATUS_GROUPS['Refunded']), 'order_id'].nunique()
                      if 'order_id' in allst.columns else s.isin(ORDER_STATUS_GROUPS['Refunded']).sum())
        succ_rate = (succ / (succ + ref) * 100) if (succ + ref) > 0 else None
        # peak hour
        peak = "—"
        if 'order_time' in cur.columns and len(cur):
            hc = cur.groupby(cur['order_time'].dt.hour).size()
            if not hc.empty:
                ph = int(hc.idxmax())
                peak = f"{ph:02d}:00–{(ph + 1) % 24:02d}:00"
        cards = [
            _kpi_card("💰", "sales-icon", _bl("Total Revenue (GMV)", "营业额 (GMV)"),
                      T.format_number(m['gmv'], sym), _pct_delta(m['gmv'], pm['gmv']),
                      "Sum of sales in the window", "GMV for the filtered window; delta vs previous equivalent window."),
            _kpi_card("📦", "orders-icon", _bl("Orders", "订单量"),
                      T.format_int(m['orders']), _pct_delta(m['orders'], pm['orders']),
                      "Unique orders", "Distinct order count in the window."),
            _kpi_card("📱", "users-icon", _bl("Beneficiary Numbers", "受益号码数"),
                      T.format_int(m['benef']) if m['benef'] else "—",
                      _pct_delta(m['benef'], pm['benef']) if m['benef'] else None,
                      "Unique recharge numbers", "Distinct phone numbers recharged."),
            _kpi_card("💵", "countries-icon", _bl("AOV", "客单价"),
                      T.format_number(m['aov'], sym), _pct_delta(m['aov'], pm['aov']),
                      "Avg order value", "GMV ÷ orders."),
            _kpi_card("📈", "sales-icon", _bl("Gross Margin", "毛利"),
                      T.format_number(m['margin'], sym), _pct_delta(m['margin'], pm['margin']),
                      (f"Margin {m['margin_pct']:.1f}%" if m['margin_pct'] is not None else "—"),
                      "Revenue − settlement cost (currency-converted)."),
            _kpi_card("📶", "orders-icon", _bl("Data Volume (GB)", "数据流量 (GB)"),
                      f"{m['gb']:,.1f}" if m['gb'] else "—",
                      _pct_delta(m['gb'], pm['gb']) if m['gb'] else None,
                      "Total GB sold (data packages)", "Sum of data-package volume in GB."),
            _kpi_card("✅", "users-icon", _bl("Success Rate", "成功率"),
                      f"{succ_rate:.1f}%" if succ_rate is not None else "—", None,
                      f"{T.format_int(succ)} ok · {T.format_int(ref)} refunded",
                      "Successful vs refunded orders in the window (ignores the status filter)."),
            _kpi_card("🕐", "countries-icon", _bl("Peak Hour", "高峰时段"),
                      peak, None, "Busiest hour (MYT)", "Hour with the most orders in the window."),
        ]
        return ui.tags.div(*cards, style="display:flex; flex-wrap:wrap; gap:12px;")

    @render.ui
    @safe_render
    def explorer_hourly_chart():
        cur = _explorer_frame()
        if cur is None or cur.empty or 'order_time' not in cur.columns:
            return _no_data("No orders to chart for this query.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        g = cur.assign(hour=cur['order_time'].dt.hour).groupby('hour')
        orders_s = g['order_id'].nunique() if 'order_id' in cur.columns else g.size()
        gmv_s = (g['sales'].sum() * rate) if 'sales' in cur.columns else orders_s * 0
        idx = list(range(24))
        orders_s = orders_s.reindex(idx, fill_value=0)
        gmv_s = gmv_s.reindex(idx, fill_value=0)
        hf, ht = _q_hour_band()
        in_band = [bool(_hour_mask(pd.Series([h]), hf, ht).iloc[0]) for h in idx]
        bar_colors = [T.PRIMARY if b else "#CBD5E1" for b in in_band]
        fig = go.Figure()
        fig.add_trace(go.Bar(x=[f"{h:02d}" for h in idx], y=orders_s.values, name=_tt("Orders"),
                             marker=dict(color=bar_colors), yaxis='y',
                             hovertemplate='%{x}:00<br>Orders: %{y:,}<extra></extra>'))
        fig.add_trace(go.Scatter(x=[f"{h:02d}" for h in idx], y=gmv_s.values, name=_tt("Revenue"),
                                 mode='lines+markers', yaxis='y2',
                                 line=dict(color=T.WARNING, width=2.5),
                                 hovertemplate='%{x}:00<br>GMV: ' + sym + '%{y:,.0f}<extra></extra>'))
        T.apply_theme(fig, title=_tt("Orders & Revenue by Hour (MYT)"),
                      xaxis_title=_tt("Hour of day (MYT)"), yaxis_title=_tt("Orders"),
                      yaxis2=dict(title=_tt("Revenue") + f" ({sym})", overlaying='y', side='right', showgrid=False),
                      height=380, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=60, t=60, b=10))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def explorer_daily_trend():
        cur = _explorer_frame()
        if cur is None or cur.empty or 'order_time' not in cur.columns:
            return _no_data("No orders to chart for this query.")
        d_from, d_to = _explorer_dates()
        if d_from == d_to:
            return _no_data("Single-day window — pick a wider date range to see the daily trend.")
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        g = cur.assign(day=cur['order_time'].dt.date).groupby('day')
        orders_s = g['order_id'].nunique() if 'order_id' in cur.columns else g.size()
        gmv_s = (g['sales'].sum() * rate) if 'sales' in cur.columns else orders_s * 0
        days = sorted(orders_s.index)
        fig = go.Figure()
        fig.add_trace(go.Bar(x=days, y=orders_s.reindex(days).values, name=_tt("Orders"),
                             marker=dict(color=T.PRIMARY, opacity=0.75), yaxis='y',
                             hovertemplate='%{x}<br>Orders: %{y:,}<extra></extra>'))
        fig.add_trace(go.Scatter(x=days, y=gmv_s.reindex(days).values, name=_tt("Revenue"),
                                 mode='lines+markers', yaxis='y2', line=dict(color=T.SUCCESS, width=2.5),
                                 hovertemplate='%{x}<br>GMV: ' + sym + '%{y:,.0f}<extra></extra>'))
        T.apply_theme(fig, title=_tt("Daily Orders & Revenue"),
                      xaxis_title=None, yaxis_title=_tt("Orders"),
                      yaxis2=dict(title=_tt("Revenue") + f" ({sym})", overlaying='y', side='right', showgrid=False),
                      height=360, legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
                      margin=dict(l=10, r=60, t=60, b=10))
        return ui.HTML(T.fig_to_html(fig))

    def _explorer_breakdown_df():
        cur = _explorer_frame()
        if cur is None or cur.empty:
            return pd.DataFrame()
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        try:
            gb = input.q_groupby() or "Operator"
        except Exception:
            gb = "Operator"
        d = cur.copy()
        if gb == "Operator":
            key = d['operator'].astype(str) if 'operator' in d.columns else pd.Series('—', index=d.index)
        elif gb in ("Product", "Denomination"):
            key = d['prod_label'].astype(str)
        elif gb == "Country":
            key = d['country'].astype(str) if 'country' in d.columns else pd.Series('—', index=d.index)
        elif gb == "Day":
            key = d['order_time'].dt.date.astype(str)
        elif gb == "Hour":
            key = d['order_time'].dt.hour.map(lambda h: f"{int(h):02d}:00")
        elif gb == "DOW":
            _names = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
            key = d['order_time'].dt.dayofweek.map(lambda i: _names[int(i)])
        else:
            key = d['operator'].astype(str) if 'operator' in d.columns else pd.Series('—', index=d.index)
        d['_k'] = key
        sc = _settle_col(d)
        grp = d.groupby('_k', observed=True)
        orders_s = grp['order_id'].nunique() if 'order_id' in d.columns else grp.size()
        gmv_s = grp['sales'].sum() * rate if 'sales' in d.columns else orders_s * 0
        cost_s = grp[sc].sum() * rate if sc in d.columns else orders_s * 0
        gbv_s = grp['vol_mb'].sum() / 1024.0 if 'vol_mb' in d.columns else orders_s * 0
        agg = pd.DataFrame({'orders': orders_s, 'gmv': gmv_s, 'cost': cost_s, 'gbv': gbv_s}).reset_index()
        agg['margin'] = agg['gmv'] - agg['cost']
        agg['margin_pct'] = (agg['margin'] / agg['gmv'].replace(0, np.nan) * 100)
        agg['aov'] = agg['gmv'] / agg['orders'].replace(0, np.nan)
        tot_gmv = agg['gmv'].sum()
        agg['share'] = agg['gmv'] / tot_gmv * 100 if tot_gmv > 0 else 0
        agg = agg.sort_values('gmv', ascending=False)
        show_gb = bool(agg['gbv'].sum() > 0)
        out = pd.DataFrame({
            gb: agg['_k'],
            'Orders': agg['orders'].map(lambda x: f"{int(x):,}"),
            f'GMV ({sym})': agg['gmv'].map(lambda x: f"{x:,.2f}"),
        })
        if show_gb:
            out[f'Data Vol (GB)'] = agg['gbv'].map(lambda x: f"{x:,.1f}")
        out[f'Cost ({sym})'] = agg['cost'].map(lambda x: f"{x:,.2f}")
        out[f'Margin ({sym})'] = agg['margin'].map(lambda x: f"{x:,.2f}")
        out['Margin %'] = agg['margin_pct'].map(lambda x: f"{x:.1f}%" if pd.notna(x) else "—")
        out[f'AOV ({sym})'] = agg['aov'].map(lambda x: f"{x:,.2f}" if pd.notna(x) else "—")
        out['Share %'] = agg['share'].map(lambda x: f"{x:.1f}%")
        # totals row
        tot = {gb: 'TOTAL', 'Orders': f"{int(agg['orders'].sum()):,}",
               f'GMV ({sym})': f"{agg['gmv'].sum():,.2f}"}
        if show_gb:
            tot['Data Vol (GB)'] = f"{agg['gbv'].sum():,.1f}"
        tot[f'Cost ({sym})'] = f"{agg['cost'].sum():,.2f}"
        tot[f'Margin ({sym})'] = f"{agg['margin'].sum():,.2f}"
        _tm = agg['margin'].sum() / tot_gmv * 100 if tot_gmv > 0 else 0
        tot['Margin %'] = f"{_tm:.1f}%"
        tot[f'AOV ({sym})'] = f"{(tot_gmv / agg['orders'].sum()):,.2f}" if agg['orders'].sum() > 0 else "—"
        tot['Share %'] = "100.0%"
        return pd.concat([out, pd.DataFrame([tot])], ignore_index=True)

    @render.data_frame
    @safe_grid
    def explorer_breakdown_table():
        out = _explorer_breakdown_df()
        if out.empty:
            return render.DataGrid(pd.DataFrame({'Status': ['No orders match this query.']}))
        return render.DataGrid(_tdf(out.head(300)), filters=True, width="100%")

    @render.download(filename=lambda: _make_filename("sales_explorer", "xlsx"))
    def download_explorer_xlsx():
        yield _xlsx_bytes(_explorer_breakdown_df())

    @render.download(filename=lambda: _make_filename("sales_explorer", "csv"))
    def download_explorer_csv():
        yield _csv_bytes(_explorer_breakdown_df())

    # ── AI Predictions: Revenue Forecasting ──────────────────────────────────

    _revenue_forecast_result = reactive.Value(None)
    _churn_model_result      = reactive.Value(None)
    _demand_forecast_result  = reactive.Value(None)

    @reactive.Effect
    @reactive.event(input.run_revenue_forecast)
    def _compute_revenue_forecast():
        if ml_predictions is None:
            _revenue_forecast_result.set({'error': f"Machine-learning module unavailable: {ML_IMPORT_ERROR}"})
            return
        df = filter_by_order_status(data_rv(), "Successful")
        try:
            horizon = int(input.forecast_horizon())
        except Exception:
            horizon = 8
        try:
            result = ml_predictions.forecast_revenue(df, horizon_weeks=horizon)
            _revenue_forecast_result.set(result)
        except Exception as exc:
            _revenue_forecast_result.set({'error': str(exc)})

    @render.ui
    @safe_render
    def revenue_forecast_chart():
        result = _revenue_forecast_result()
        if result is None:
            return ui.HTML(
                '<div style="color:#64748B;padding:24px;text-align:center;">'
                'Click <b>Generate Forecast</b> above to run the revenue model on full historical data.</div>'
            )
        if isinstance(result, dict) and 'error' in result:
            return ui.HTML(f'<div style="color:#B91C1C;background:#FEF2F2;padding:16px;'
                           f'border-radius:8px;">⚠ {result["error"]}</div>')
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        hist = result['history']
        pred = result['predictions']
        fig  = go.Figure()
        fig.add_trace(go.Scatter(
            x=hist['week_start'], y=hist['Actual Revenue'] * rate,
            name=_tt('Actual Revenue'), mode='lines',
            line=dict(color=T.PRIMARY, width=2),
            hovertemplate=f'<b>%{{x|%b %d}}</b><br>Actual: {sym}%{{y:,.0f}}<extra></extra>',
        ))
        model_colors = [T.SUCCESS, T.WARNING, '#8B5CF6', '#F97316']
        model_names  = [c for c in pred.columns if c != 'week_start']
        for i, name in enumerate(model_names):
            fig.add_trace(go.Scatter(
                x=pred['week_start'], y=pred[name] * rate,
                name=name, mode='lines+markers',
                line=dict(color=model_colors[i % len(model_colors)], width=2, dash='dot'),
                marker=dict(size=6),
                hovertemplate=f'<b>{name}</b><br>%{{x|%b %d}}<br>Forecast: {sym}%{{y:,.0f}}<extra></extra>',
            ))
        # Shade from last history point to first forecast
        if not hist.empty and not pred.empty:
            fig.add_vrect(
                x0=pred['week_start'].min(), x1=pred['week_start'].max(),
                fillcolor='rgba(16,185,129,0.05)', layer='below', line_width=0,
            )
        best = result['best_model']
        T.apply_theme(fig,
                      title=_tt(f"Revenue Forecast — Next {result['horizon_weeks']} Weeks · {currency['label']} (Best: {best})"),
                      xaxis_title=_tt("Week"), yaxis_title=_tt(f"Revenue ({sym})"),
                      hovermode='x unified', height=420,
                      legend=dict(orientation='h', yanchor='bottom', y=-0.25, xanchor='left', x=0))
        return ui.HTML(T.fig_to_html(fig))

    @render.ui
    @safe_render
    def revenue_forecast_metrics():
        result = _revenue_forecast_result()
        if result is None or (isinstance(result, dict) and 'error' in result):
            return ui.HTML('')
        currency = currency_converter()
        sym = currency['symbol']
        best = result['best_model']
        m = result['metrics'].get(best, {})
        q = result.get('quality', {})
        mape = m.get('mape', float('nan'))
        rmse = m.get('rmse', float('nan'))
        mae  = m.get('mae', float('nan'))
        base_mape = q.get('baseline_mape', float('nan'))
        beats = q.get('beats_baseline', False)

        def _fmt(v): return f"{v:,.0f}" if not np.isnan(v) else "—"

        # Honest quality banner
        if beats:
            banner = ui.HTML(
                f'<div style="background:#ECFDF5;border-left:4px solid #10B981;'
                f'padding:10px 14px;border-radius:8px;margin-bottom:12px;font-size:0.9em;color:#065F46;">'
                f'✔ {q.get("note", "")}</div>')
        else:
            banner = ui.HTML(
                f'<div style="background:#FFFBEB;border-left:4px solid #F59E0B;'
                f'padding:10px 14px;border-radius:8px;margin-bottom:12px;font-size:0.9em;color:#92400E;">'
                f'⚠ {q.get("note", "")}</div>')

        cards = ui.tags.div(
            _kpi_card("🎯", "sales-icon", "Best Model",
                      best[:22], None,
                      q.get('validation', 'walk-forward validation'),
                      "Lowest daily MAPE under walk-forward validation. "
                      "'Seasonal Baseline' means no ML model beat a simple same-weekday average."),
            _kpi_card("📏", "orders-icon", "Daily MAPE",
                      f"{mape:.1f}%" if not np.isnan(mape) else "—", None,
                      f"Baseline: {base_mape:.1f}%" if not np.isnan(base_mape) else "—",
                      "Mean Absolute Percentage Error on out-of-sample days. Lower = better. "
                      "Compared against the seasonal-naive baseline."),
            _kpi_card("📉", "users-icon", f"RMSE ({sym})",
                      _fmt(rmse * currency['rate']), None,
                      "Daily root-mean-squared error",
                      "Penalises large misses; in the reporting currency."),
            _kpi_card("📊", "countries-icon", f"MAE ({sym})",
                      _fmt(mae * currency['rate']), None,
                      "Daily mean absolute error",
                      "Average absolute daily deviation between predicted and actual."),
            style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:8px;"
        )
        return ui.tags.div(banner, cards)

    @render.data_frame
    @safe_grid
    def revenue_forecast_table():
        result = _revenue_forecast_result()
        if result is None:
            return render.DataGrid(pd.DataFrame({'Status': ['Click "Generate Forecast" to run the model.']}))
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        pred = result['predictions'].copy()
        pred['week_start'] = pred['week_start'].dt.strftime('%Y-%m-%d')
        for col in pred.columns:
            if col != 'week_start':
                pred[col] = (pred[col] * rate).apply(lambda x: f"{sym}{x:,.0f}" if pd.notna(x) else "—")
        pred.columns = [c if c == 'week_start' else c for c in pred.columns]
        pred = pred.rename(columns={'week_start': 'Week Starting'})
        return render.DataGrid(_tdf(pred))

    # ── AI Predictions: Customer Churn ────────────────────────────────────────

    @reactive.Effect
    @reactive.event(input.run_churn_model)
    def _compute_churn_model():
        if ml_predictions is None:
            _churn_model_result.set({'error': f"Machine-learning module unavailable: {ML_IMPORT_ERROR}"})
            return
        df = filter_by_order_status(data_rv(), "Successful")
        try:
            result = ml_predictions.predict_churn(df, churn_days=60)
            _churn_model_result.set(result)
        except Exception as exc:
            _churn_model_result.set({'error': str(exc)})

    @render.ui
    @safe_render
    def churn_model_metrics():
        result = _churn_model_result()
        if result is None:
            return ui.HTML(
                '<div style="color:#64748B;padding:24px;text-align:center;">'
                'Click <b>Run Churn Model</b> above. Requires B2C data with user_id, order_time, and sales.</div>'
            )
        if isinstance(result, dict) and 'error' in result:
            return ui.HTML(f'<div style="color:#B91C1C;background:#FEF2F2;padding:16px;'
                           f'border-radius:8px;">⚠ {result["error"]}</div>')
        metrics  = result['metrics']
        best     = result['best_model']
        roc_data = result['roc_curves']
        m = metrics[best]
        # ROC curve figure
        fig = go.Figure()
        colors = [T.SUCCESS, T.PRIMARY, T.WARNING]
        for (name, (fpr, tpr)), col in zip(roc_data.items(), colors):
            auc = metrics[name]['auc']
            fig.add_trace(go.Scatter(
                x=fpr, y=tpr, mode='lines', name=_tt(f"{name} (AUC={auc:.3f})"),
                line=dict(color=col, width=2),
            ))
        fig.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1], mode='lines', name=_tt('Random'),
            line=dict(color='#94A3B8', width=1, dash='dash'), showlegend=True,
        ))
        T.apply_theme(fig, title=_tt("ROC Curves — Model Comparison"),
                      xaxis_title=_tt("False Positive Rate"), yaxis_title=_tt("True Positive Rate"),
                      height=360,
                      legend=dict(orientation='h', yanchor='bottom', y=-0.3, xanchor='left', x=0))
        total = result['total_customers']
        churned = result['churned_count']
        return ui.tags.div(
            ui.tags.div(
                _kpi_card("🏆", "sales-icon", "Best Model",
                          best[:22], None,
                          f"AUC: {m['auc']:.3f}",
                          "Classifier with highest AUC-ROC on held-out test customers."),
                _kpi_card("📊", "orders-icon", "AUC-ROC",
                          f"{m['auc']:.3f}" if not np.isnan(m['auc']) else "—", None,
                          "Area under the ROC curve (1.0 = perfect)",
                          "Higher AUC = better discrimination between churned and active customers."),
                _kpi_card("🎯", "users-icon", "F1 Score",
                          f"{m['f1']:.3f}", None,
                          f"Precision: {m['precision']:.2f} | Recall: {m['recall']:.2f}",
                          "Harmonic mean of precision and recall. Balances false positives and missed churners."),
                _kpi_card("👥", "countries-icon", "B2C Customers",
                          f"{total:,}", None,
                          f"{churned:,} churned ({churned/total*100:.1f}%)" if total > 0 else "—",
                          f"Churn defined as no order in the last 60 days."),
                style="display:flex; flex-wrap:wrap; gap:12px; margin-bottom:16px;"
            ),
            ui.HTML(T.fig_to_html(fig)),
        )

    @render.ui
    @safe_render
    def churn_feature_importance():
        result = _churn_model_result()
        if result is None or (isinstance(result, dict) and 'error' in result):
            return ui.HTML('')
        fi = result['feature_importance']
        if fi.empty:
            return ui.HTML('')
        fi_sorted = fi.sort_values(ascending=True)
        label_map = {
            'recency_days':    'Days Since Last Order',
            'frequency':       'Order Frequency',
            'monetary':        'Total Revenue (GMV)',
            'avg_order_value': 'Avg Order Value',
            'tenure_days':     'Customer Tenure (days)',
            'days_since_reg':  'Days Since Registration',
        }
        labels = [label_map.get(i, i) for i in fi_sorted.index]
        fig = go.Figure(go.Bar(
            x=fi_sorted.values, y=labels, orientation='h',
            marker=dict(color=fi_sorted.values, colorscale=T.SCALE_SEQUENTIAL,
                        showscale=False, line=dict(color='white', width=1)),
            text=[f"{v:.3f}" for v in fi_sorted.values],
            textposition='outside', textfont=dict(size=11),
            hovertemplate='<b>%{y}</b><br>Importance: %{x:.4f}<extra></extra>',
        ))
        T.apply_theme(fig, title=_tt("Random Forest — Feature Importance (Churn Prediction)"),
                      xaxis_title=_tt("Importance Score"), yaxis_title=None,
                      margin=dict(l=10, r=80, t=50, b=10), height=320)
        return ui.HTML(T.fig_to_html(fig))

    @render.data_frame
    @safe_grid
    def churn_risk_table():
        result = _churn_model_result()
        if result is None:
            return render.DataGrid(pd.DataFrame({'Status': ['Click "Run Churn Model" to generate predictions.']}))
        currency = currency_converter()
        rate, sym = currency['rate'], currency['symbol']
        src = result['at_risk'].head(50).copy()

        def _money(s):
            return (s * rate).apply(lambda x: f"{sym}{x:,.2f}" if pd.notna(x) else "—")
        def _int(s):
            return s.apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
        def _id(s):
            return s.apply(lambda x: str(int(x)) if pd.notna(x) and str(x).replace('.', '', 1).isdigit()
                           else (str(x) if pd.notna(x) else "—"))

        # Select + format by NAME so extra model feature columns don't break the
        # positional rename (Round-7 at_risk has 9 cols, not 7).
        out = pd.DataFrame({
            'Customer ID':            _id(src['user_id']),
            'Days Since Last Order':  src['recency_days'].apply(lambda x: f"{int(x):,} days" if pd.notna(x) else "—"),
            'Total Orders':           _int(src['frequency']),
            'Orders (90d)':           _int(src['recent_3m_orders']) if 'recent_3m_orders' in src.columns else "—",
            f'Total GMV ({sym})':     _money(src['monetary']),
            f'Avg Order ({sym})':     _money(src['avg_order_value']),
            f'Revenue 30d ({sym})':   _money(src['revenue_30d']) if 'revenue_30d' in src.columns else "—",
            'Churn Probability':      src['churn_probability'].apply(lambda x: f"{x:.1f}%" if pd.notna(x) else "—"),
            'Risk Tier':              src['risk_tier'].astype(str),
        })
        return render.DataGrid(_tdf(out), filters=True)

    # ── AI Predictions: Product Demand Forecasting ────────────────────────────

    @reactive.Effect
    @reactive.event(input.run_demand_forecast)
    def _compute_demand_forecast():
        if ml_predictions is None:
            _demand_forecast_result.set({'error': f"Machine-learning module unavailable: {ML_IMPORT_ERROR}"})
            return
        df = filter_by_order_status(data_rv(), "Successful")
        try:
            result = ml_predictions.forecast_demand(df, horizon_weeks=4)
            if result is None:
                _demand_forecast_result.set({'error': (
                    'Insufficient data for demand forecasting. '
                    'Need at least 2 weeks of order history with operator and product columns.'
                )})
            else:
                _demand_forecast_result.set(result)
        except Exception as exc:
            _demand_forecast_result.set({'error': str(exc)})

    @render.data_frame
    @safe_grid
    def demand_forecast_table():
        result = _demand_forecast_result()
        if result is None:
            return render.DataGrid(pd.DataFrame({'Status': ['Click "Generate Demand Forecast" to run the model.']}))
        if isinstance(result, dict) and 'error' in result:
            return render.DataGrid(pd.DataFrame({'Error': [result['error']]}))
        forecast = result['forecast'].copy()
        num_cols = [c for c in forecast.columns if 'Wk' in c or 'Avg' in c]
        for c in num_cols:
            forecast[c] = forecast[c].apply(lambda x: f"{int(x):,}" if pd.notna(x) else "—")
        return render.DataGrid(_tdf(forecast), filters=True)

    # ── Analyst Remarks: save handlers for each tab ───────────────────────────

    _remark_msg_executive_overview        = reactive.Value("")
    _remark_msg_performance_comparison    = reactive.Value("")
    _remark_msg_revenue_orders            = reactive.Value("")
    _remark_msg_market_intelligence       = reactive.Value("")
    _remark_msg_operational_intelligence  = reactive.Value("")
    _remark_msg_supplier_operator         = reactive.Value("")
    _remark_msg_product_denomination      = reactive.Value("")
    _remark_msg_customer_analytics        = reactive.Value("")

    @reactive.Effect
    @reactive.event(input.save_remark_executive_overview)
    def _save_remark_executive_overview():
        remarks_utils.save_remark("executive_overview", input.remark_executive_overview())
        _remark_msg_executive_overview.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_executive_overview():
        return _remark_msg_executive_overview()

    @reactive.Effect
    @reactive.event(input.save_remark_performance_comparison)
    def _save_remark_performance_comparison():
        remarks_utils.save_remark("performance_comparison", input.remark_performance_comparison())
        _remark_msg_performance_comparison.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_performance_comparison():
        return _remark_msg_performance_comparison()

    @reactive.Effect
    @reactive.event(input.save_remark_revenue_orders)
    def _save_remark_revenue_orders():
        remarks_utils.save_remark("revenue_orders", input.remark_revenue_orders())
        _remark_msg_revenue_orders.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_revenue_orders():
        return _remark_msg_revenue_orders()

    @reactive.Effect
    @reactive.event(input.save_remark_market_intelligence)
    def _save_remark_market_intelligence():
        remarks_utils.save_remark("market_intelligence", input.remark_market_intelligence())
        _remark_msg_market_intelligence.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_market_intelligence():
        return _remark_msg_market_intelligence()

    @reactive.Effect
    @reactive.event(input.save_remark_operational_intelligence)
    def _save_remark_operational_intelligence():
        remarks_utils.save_remark("operational_intelligence", input.remark_operational_intelligence())
        _remark_msg_operational_intelligence.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_operational_intelligence():
        return _remark_msg_operational_intelligence()

    @reactive.Effect
    @reactive.event(input.save_remark_supplier_operator_performance)
    def _save_remark_supplier_operator_performance():
        remarks_utils.save_remark("supplier_operator_performance", input.remark_supplier_operator_performance())
        _remark_msg_supplier_operator.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_supplier_operator_performance():
        return _remark_msg_supplier_operator()

    @reactive.Effect
    @reactive.event(input.save_remark_product_denomination_analysis)
    def _save_remark_product_denomination_analysis():
        remarks_utils.save_remark("product_denomination_analysis", input.remark_product_denomination_analysis())
        _remark_msg_product_denomination.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_product_denomination_analysis():
        return _remark_msg_product_denomination()

    @reactive.Effect
    @reactive.event(input.save_remark_customer_analytics)
    def _save_remark_customer_analytics():
        remarks_utils.save_remark("customer_analytics", input.remark_customer_analytics())
        _remark_msg_customer_analytics.set(f"✓ Saved · {_dt.datetime.now().strftime('%Y-%m-%d %H:%M')}")

    @render.text
    def remark_saved_msg_customer_analytics():
        return _remark_msg_customer_analytics()

    # ── PDF Report download handler ──────────────────────────────────────────

    @render.download(
        filename=lambda: f"revenue_intelligence_report_{_dt.datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    )
    def download_pdf():
        from pdf_export import build_pdf

        currency = currency_converter()
        sym = currency['symbol']
        df = filtered_data()

        # Build filters summary string
        parts = []
        seg = applied_segment()
        reg = applied_region()
        ctr = applied_country()
        dfrom, dto = applied_date_from(), applied_date_to()
        if seg and seg != "All":
            parts.append(f"Segment: {seg}")
        if reg and reg != "All":
            parts.append(f"Region: {reg}")
        if ctr and ctr != "All":
            parts.append(f"Market: {ctr}")
        filters_str = " | ".join(parts) if parts else "All Segments · All Regions · All Markets"
        date_str = f"{dfrom} to {dto}" if dfrom and dto else "All dates"

        # Helper to safely call render functions
        def _safe_fig(fn_name):
            try:
                result = getattr(output, fn_name)
            except Exception:
                return None
            return None  # Plotly figs can't be retrieved from render.ui; collect from filtered_data below

        # Build chart figures directly for PDF (independent of output rendering)
        def _top5_fig():
            if 'country' not in df.columns or 'sales' not in df.columns:
                return None
            top5 = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).nlargest(5).reset_index().sort_values('sales')
            import plotly.graph_objects as _go
            return _go.Figure(_go.Bar(x=top5['sales'], y=top5['country'], orientation='h',
                                      marker=dict(color=T.PALETTE[:5])))

        def _region_fig():
            if 'region' not in df.columns or 'sales' not in df.columns:
                return None
            reg_s = df.groupby('region', observed=True)['sales'].sum().mul(currency['rate']).reset_index()
            reg_s = reg_s[reg_s['sales'] > 0]
            if reg_s.empty:
                return None
            import plotly.graph_objects as _go
            return _go.Figure(_go.Pie(labels=reg_s['region'], values=reg_s['sales'], hole=0.5,
                                       marker=dict(colors=T.PALETTE)))

        def _trend_fig():
            if 'order_time' not in df.columns or 'sales' not in df.columns:
                return None
            monthly = df.groupby(df['order_time'].dt.to_period('M').dt.start_time)['sales'].sum().mul(currency['rate']).reset_index()
            monthly.columns = ['month', 'sales']
            import plotly.graph_objects as _go
            return _go.Figure(_go.Scatter(x=monthly['month'], y=monthly['sales'], mode='lines+markers',
                                           line=dict(color=T.PRIMARY, width=2)))

        def _country_sales_fig():
            if 'country' not in df.columns or 'sales' not in df.columns:
                return None
            cs = df.groupby('country', observed=True)['sales'].sum().mul(currency['rate']).nlargest(15).reset_index().sort_values('sales')
            import plotly.graph_objects as _go
            return _go.Figure(_go.Bar(x=cs['sales'], y=cs['country'], orientation='h',
                                       marker=dict(color=cs['sales'], colorscale=T.SCALE_SEQUENTIAL)))

        def _operator_sales_fig():
            if 'operator' not in df.columns or 'sales' not in df.columns:
                return None
            op = df.groupby('operator', observed=True)['sales'].sum().mul(currency['rate']).nlargest(10).reset_index().sort_values('sales')
            import plotly.graph_objects as _go
            return _go.Figure(_go.Bar(x=op['sales'], y=op['operator'], orientation='h',
                                       marker=dict(color=op['sales'], colorscale=T.SCALE_SEQUENTIAL)))

        # KPI computations
        total_sales = float(df['sales'].sum() * currency['rate']) if 'sales' in df.columns else 0
        total_orders = int(df['order_id'].nunique()) if 'order_id' in df.columns else 0
        total_users = int(df['user_id'].nunique()) if 'user_id' in df.columns else 0
        total_countries = int(df['country'].nunique()) if 'country' in df.columns else 0
        aov = total_sales / total_orders if total_orders > 0 else 0

        # Operator concentration
        op_conc = ""
        if 'operator' in df.columns and 'sales' in df.columns:
            op_s = df.groupby('operator', observed=True)['sales'].sum().mul(currency['rate']).sort_values(ascending=False)
            if len(op_s) > 0:
                top3_pct = op_s.head(3).sum() / op_s.sum() * 100 if op_s.sum() > 0 else 0
                op_conc = f"Top 3 operators: {top3_pct:.1f}% of GMV"

        tab_data = [
            {
                "tab": "Executive Overview",
                "kpis": [
                    ("Total Revenue (GMV)", T.format_number(total_sales, sym), None),
                    ("Order Volume", T.format_int(total_orders), None),
                    ("Active Customers", T.format_int(total_users), None),
                    ("Markets", str(total_countries), None),
                ],
                "figures": [_trend_fig(), _region_fig(), _top5_fig()],
                "tables": [],
                "remark": remarks_utils.get_remark("executive_overview"),
            },
            {
                "tab": "Market Intelligence",
                "kpis": [
                    ("Total Revenue (GMV)", T.format_number(total_sales, sym), None),
                    ("Markets Active", str(total_countries), None),
                    ("AOV", T.format_number(aov, sym), None),
                ],
                "figures": [_country_sales_fig()],
                "tables": [],
                "remark": remarks_utils.get_remark("market_intelligence"),
            },
            {
                "tab": "Supplier & Operator Performance",
                "kpis": [
                    ("Total Revenue (GMV)", T.format_number(total_sales, sym), None),
                    ("Concentration", op_conc, None),
                ],
                "figures": [_operator_sales_fig()],
                "tables": [],
                "remark": remarks_utils.get_remark("supplier_operator_performance"),
            },
        ]

        # Add remaining tabs with remark-only pages
        for tab_id, tab_name in [
            ("performance_comparison", "Performance Comparison"),
            ("revenue_orders", "Revenue & Orders"),
            ("operational_intelligence", "Operational Intelligence"),
            ("product_denomination_analysis", "Product & Denomination Analysis"),
            ("customer_analytics", "Customer Analytics"),
        ]:
            tab_data.append({
                "tab": tab_name,
                "kpis": [],
                "figures": [],
                "tables": [],
                "remark": remarks_utils.get_remark(tab_id),
            })

        pdf_bytes = build_pdf(
            tab_data,
            filters_summary=filters_str,
            date_range=date_str,
        )
        yield pdf_bytes


def _static_assets_dir() -> Path:
    """Path to the static asset directory. Copies plotly.min.js out of the
    plotly package on first run so we can serve it locally (no CDN fetch)."""
    here = Path(__file__).resolve().parent
    static_dir = here / "static"
    static_dir.mkdir(exist_ok=True)
    plotly_target = static_dir / "plotly.min.js"
    if not plotly_target.exists():
        try:
            import plotly
            plotly_src = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"
            if plotly_src.exists():
                import shutil
                shutil.copy(plotly_src, plotly_target)
                print(f"[startup] copied plotly.min.js to {plotly_target} "
                      f"({plotly_target.stat().st_size/1024/1024:.1f} MB)", flush=True)
        except Exception as exc:
            print(f"[startup] could not bundle plotly.min.js: {exc}", flush=True)
    return static_dir


app = App(app_ui, server, static_assets={"/static": _static_assets_dir()})


if __name__ == '__main__':
    app.run()
