"""Reusable Plotly chart builders (4.3 DRY factory).

Centralises the repeated 'groupby → go.Figure → apply_theme' bar pattern so chart
styling stays consistent and individual render functions shrink. Builders return a
themed ``go.Figure``; the caller does ``ui.HTML(theme.fig_to_html(fig))``.

Titles/axis titles must be pre-translated by the caller (pass ``_tt(...)``), since
translation depends on the active UI language inside the Shiny server scope.
"""
from __future__ import annotations

import plotly.graph_objects as go
import theme as T


def topn_hbar(*, values, labels, title, xaxis_title, hover_label, value_text,
              color_line: bool = False, height: int = 520):
    """Horizontal Top-N bar with the standard sequential-colour styling.

    Parameters
    ----------
    values, labels : ordered ascending so the largest bar sits on top.
    hover_label    : text after the ``<b>%{y}</b><br>`` prefix,
                     e.g. ``'Sales: ¥%{x:,.0f}'``.
    value_text     : pre-formatted outside-bar labels (list aligned to ``values``).
    color_line     : add a thin white bar outline (matches a couple of variants).
    """
    marker = dict(color=values, colorscale=T.SCALE_SEQUENTIAL, showscale=False)
    if color_line:
        marker["line"] = dict(color="white", width=1)
    fig = go.Figure(go.Bar(
        x=values, y=labels, orientation="h", marker=marker,
        text=value_text, textposition="outside",
        textfont=dict(size=11, color="#334155"),
        hovertemplate="<b>%{y}</b><br>" + hover_label + "<extra></extra>",
    ))
    T.apply_theme(fig, title=title, xaxis_title=xaxis_title, yaxis_title=None,
                  margin=dict(l=10, r=80, t=50, b=10), height=height)
    return fig
