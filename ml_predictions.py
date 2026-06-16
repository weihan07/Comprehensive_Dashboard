"""
ml_predictions.py — AI/ML prediction engine for the Sales Dashboard.

Three prediction modules (Round 7 accuracy rebuild):
  1. forecast_revenue()  — DAILY-grain multi-model revenue forecasting with a
                           seasonal-naive baseline and walk-forward validation.
                           If no model beats the baseline, the baseline is used
                           and the UI says so (no fake accuracy).
  2. predict_churn()     — LEAK-FREE temporal churn model: features are built
                           strictly BEFORE a cutoff date, the label is observed
                           strictly AFTER it. (The previous design leaked the
                           label through recency_days -> AUC 1.0.)
  3. forecast_demand()   — per-operator x product weekly demand. Fixed the
                           NA-group bug (operator missing on B2C, product
                           missing on B2B made pandas drop every group).

Dependencies: scikit-learn (1.9+), numpy, pandas.
"""

from __future__ import annotations

import warnings
import numpy as np
import pandas as pd

with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from sklearn.ensemble import (
        GradientBoostingRegressor, RandomForestRegressor,
        GradientBoostingClassifier, RandomForestClassifier, ExtraTreesClassifier,
    )
    from sklearn.linear_model import LogisticRegression, Ridge
    from sklearn.preprocessing import StandardScaler
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import (
        mean_absolute_error, mean_squared_error, r2_score,
        roc_auc_score, precision_score, recall_score, f1_score,
        roc_curve,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_rmse(y_true, y_pred) -> float:
    return float(np.sqrt(mean_squared_error(y_true, y_pred)))


def _safe_mae(y_true, y_pred) -> float:
    return float(mean_absolute_error(y_true, y_pred))


def _safe_r2(y_true, y_pred) -> float:
    try:
        return float(r2_score(y_true, y_pred))
    except Exception:
        return float("nan")


def _safe_mape(y_true, y_pred) -> float:
    """MAPE in %, ignoring near-zero actuals."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    mask = np.abs(y_true) > 1e-9
    if mask.sum() == 0:
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


# ---------------------------------------------------------------------------
# 1 — Revenue Forecasting (daily grain + seasonal baseline + walk-forward CV)
# ---------------------------------------------------------------------------

_DAILY_FEATURES = [
    "t", "lag1", "lag7", "lag14", "roll7", "roll28",
    "dow_sin", "dow_cos", "is_weekend", "month_sin", "month_cos",
]


def _daily_feature_row(t, hist, day):
    """Feature vector for one day given the revenue history list `hist`."""
    n = len(hist)
    lag1 = hist[-1] if n >= 1 else 0.0
    lag7 = hist[-7] if n >= 7 else lag1
    lag14 = hist[-14] if n >= 14 else lag7
    roll7 = float(np.mean(hist[-7:])) if n >= 7 else lag1
    roll28 = float(np.mean(hist[-28:])) if n >= 28 else roll7
    dow = day.dayofweek
    return [
        t, np.log1p(lag1), np.log1p(lag7), np.log1p(lag14),
        np.log1p(roll7), np.log1p(roll28),
        np.sin(2 * np.pi * dow / 7), np.cos(2 * np.pi * dow / 7),
        1.0 if dow >= 5 else 0.0,
        np.sin(2 * np.pi * day.month / 12), np.cos(2 * np.pi * day.month / 12),
    ]


def _seasonal_baseline(values, dows, target_dow, upto):
    """Mean revenue of the same weekday over the 4 weeks before index `upto`."""
    same = [values[i] for i in range(max(0, upto - 28), upto) if dows[i] == target_dow]
    if not same:
        same = values[max(0, upto - 7):upto] or [0.0]
    return float(np.mean(same[-4:]))


def forecast_revenue(df: pd.DataFrame, horizon_weeks: int = 8) -> dict | None:
    """
    Daily-grain revenue forecast with honest validation.

    - Trains GradientBoosting / RandomForest / Ridge on log1p(daily revenue)
      with lag, rolling and calendar features.
    - Walk-forward validation: the last 3 x 14-day windows are predicted
      out-of-sample; MAPE/RMSE/MAE/R2 reported per model PLUS a
      seasonal-naive baseline (same-weekday mean of the prior 4 weeks).
    - The Ensemble forecast uses the ML models only when they beat the
      baseline; otherwise it IS the baseline (and `quality` says so).

    Returns dict(history, predictions, metrics, best_model,
                 feature_importance, horizon_weeks, quality) or None.
    History/predictions are aggregated to weeks for display.
    """
    if "order_time" not in df.columns or "sales" not in df.columns:
        return None

    df = df.dropna(subset=["order_time", "sales"]).copy()
    df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce")
    df = df.dropna(subset=["order_time"])
    if df.empty:
        return None

    daily = df.groupby(df["order_time"].dt.normalize())["sales"].sum()
    daily = daily.reindex(
        pd.date_range(daily.index.min(), daily.index.max(), freq="D"), fill_value=0.0
    )
    # The last export day is almost always partial — drop it.
    if len(daily) > 1:
        daily = daily.iloc[:-1]
    # Drop leading dead days
    nz = np.nonzero(daily.values > 0)[0]
    if len(nz) == 0:
        return None
    daily = daily.iloc[nz[0]:]

    if len(daily) < 42:
        return None

    days = daily.index
    values = daily.values.astype(float)
    dows = [d.dayofweek for d in days]

    # --- feature matrix (log space target) ---
    rows, targets = [], []
    for i in range(28, len(daily)):
        rows.append(_daily_feature_row(i, list(values[:i]), days[i]))
        targets.append(np.log1p(values[i]))
    X = np.asarray(rows)
    y = np.asarray(targets)
    offset = 28  # X[k] predicts day index k + offset

    def make_models():
        return {
            "Gradient Boosting": GradientBoostingRegressor(
                n_estimators=300, max_depth=3, learning_rate=0.05,
                subsample=0.9, random_state=42),
            "Random Forest": RandomForestRegressor(
                n_estimators=300, min_samples_leaf=2, random_state=42, n_jobs=-1),
            "Ridge": Pipeline([
                ("scaler", StandardScaler()),
                ("ridge", Ridge(alpha=1.0)),
            ]),
        }

    # --- walk-forward validation: last 3 windows of 14 days ---
    n = len(X)
    test_len = 14
    folds = []
    for k in range(3, 0, -1):
        te_end = n - (k - 1) * test_len
        te_start = te_end - test_len
        if te_start > 30:
            folds.append((te_start, te_end))
    if not folds:
        folds = [(max(1, n - test_len), n)]

    oof = {name: ([], []) for name in make_models()}   # (true, pred) in revenue space
    base_true, base_pred = [], []
    for te_start, te_end in folds:
        models = make_models()
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            for name, m in models.items():
                m.fit(X[:te_start], y[:te_start])
        for i in range(te_start, te_end):
            actual = float(np.expm1(y[i]))
            day_idx = i + offset
            for name, m in models.items():
                p = float(np.expm1(m.predict(X[i:i + 1])[0]))
                oof[name][0].append(actual)
                oof[name][1].append(max(0.0, p))
            base_true.append(actual)
            base_pred.append(_seasonal_baseline(list(values), dows, dows[day_idx], day_idx))

    metrics = {}
    for name, (t_, p_) in oof.items():
        metrics[name] = {
            "rmse": _safe_rmse(t_, p_), "mae": _safe_mae(t_, p_),
            "r2": _safe_r2(t_, p_), "mape": _safe_mape(t_, p_),
        }
    metrics["Seasonal Baseline"] = {
        "rmse": _safe_rmse(base_true, base_pred), "mae": _safe_mae(base_true, base_pred),
        "r2": _safe_r2(base_true, base_pred), "mape": _safe_mape(base_true, base_pred),
    }

    ml_names = list(make_models().keys())
    best_model = min(ml_names, key=lambda k: metrics[k]["mape"]
                     if not np.isnan(metrics[k]["mape"]) else 1e9)
    baseline_mape = metrics["Seasonal Baseline"]["mape"]
    best_mape = metrics[best_model]["mape"]
    beats = bool(not np.isnan(best_mape) and best_mape < baseline_mape)
    if not beats:
        best_model = "Seasonal Baseline"

    # --- final fit on ALL data ---
    final_models = make_models()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        for m in final_models.values():
            m.fit(X, y)

    rf = final_models.get("Random Forest")
    fi = (pd.Series(rf.feature_importances_, index=_DAILY_FEATURES)
          .sort_values(ascending=False)
          if hasattr(rf, "feature_importances_") else pd.Series(dtype=float))

    # --- recursive daily forecast (each model keeps its own history path) ---
    horizon_days = horizon_weeks * 7 + 7
    model_hist = {name: list(values) for name in final_models}
    ens_hist = list(values)
    fut_dows = list(dows)
    future = []
    for i in range(1, horizon_days + 1):
        day = days[-1] + pd.Timedelta(days=i)
        t_val = len(values) + i - 1
        row = {"date": day}
        preds = {}
        for name, m in final_models.items():
            x = np.asarray([_daily_feature_row(t_val, model_hist[name], day)])
            p = max(0.0, float(np.expm1(m.predict(x)[0])))
            model_hist[name].append(p)
            preds[name] = p
        b = _seasonal_baseline(ens_hist, fut_dows, day.dayofweek, len(ens_hist))
        preds["Seasonal Baseline"] = b
        ens = float(np.mean([preds[nm] for nm in ml_names])) if beats else b
        ens_hist.append(ens)
        fut_dows.append(day.dayofweek)
        preds["Ensemble"] = ens
        row.update(preds)
        future.append(row)

    fut = pd.DataFrame(future)
    fut["week_start"] = fut["date"].dt.to_period("W").dt.start_time
    counts = fut.groupby("week_start")["date"].count()
    full_weeks = counts[counts == 7].index[:horizon_weeks]
    pred_cols = ml_names + ["Seasonal Baseline", "Ensemble"]
    pred_df = (fut[fut["week_start"].isin(full_weeks)]
               .groupby("week_start")[pred_cols].sum().reset_index())

    hist = daily.reset_index()
    hist.columns = ["date", "revenue"]
    hist["week_start"] = hist["date"].dt.to_period("W").dt.start_time
    hcounts = hist.groupby("week_start")["date"].count()
    hfull = hcounts[hcounts == 7].index
    history_df = (hist[hist["week_start"].isin(hfull)]
                  .groupby("week_start")["revenue"].sum().reset_index()
                  .rename(columns={"revenue": "Actual Revenue"}))

    note = (f"Best model ({best_model}) beats the seasonal baseline: "
            f"{best_mape:.1f}% vs {baseline_mape:.1f}% daily MAPE."
            if beats else
            f"No ML model beat the seasonal baseline ({baseline_mape:.1f}% daily MAPE) - "
            f"the forecast shown IS the baseline. More history will improve this.")

    return {
        "history": history_df,
        "predictions": pred_df,
        "metrics": metrics,
        "best_model": best_model,
        "feature_importance": fi,
        "horizon_weeks": horizon_weeks,
        "quality": {
            "best_mape": best_mape,
            "baseline_mape": baseline_mape,
            "beats_baseline": beats,
            "validation": f"walk-forward, {len(folds)}x{test_len}-day windows",
            "note": note,
        },
    }


# ---------------------------------------------------------------------------
# 2 — Customer Churn Prediction (temporal, leak-free)
# ---------------------------------------------------------------------------

_CHURN_FEATURES = [
    "recency_days", "frequency", "monetary", "avg_order_value",
    "tenure_days", "days_since_reg", "recent_3m_orders", "revenue_30d",
    "interval_mean", "interval_std",
]


def _churn_features(df: pd.DataFrame, ref_date: pd.Timestamp) -> pd.DataFrame:
    """Per-customer features using ONLY orders at or before `ref_date`."""
    past = df[df["order_time"] <= ref_date]
    if past.empty:
        return pd.DataFrame()
    c3m = ref_date - pd.Timedelta(days=90)
    c30 = ref_date - pd.Timedelta(days=30)

    cust = past.groupby("user_id", observed=True).agg(
        last_order=("order_time", "max"),
        first_order=("order_time", "min"),
        frequency=("order_time", "count"),
        monetary=("sales", "sum"),
        avg_order_value=("sales", "mean"),
    ).reset_index()
    cust["recency_days"] = (ref_date - cust["last_order"]).dt.days.clip(lower=0)
    cust["tenure_days"] = (cust["last_order"] - cust["first_order"]).dt.days.clip(lower=0)

    recent_3m = (past[past["order_time"] >= c3m]
                 .groupby("user_id", observed=True).size()
                 .rename("recent_3m_orders").reset_index())
    revenue_30d = (past[past["order_time"] >= c30]
                   .groupby("user_id", observed=True)["sales"].sum()
                   .rename("revenue_30d").reset_index())
    cust = (cust.merge(recent_3m, on="user_id", how="left")
                .merge(revenue_30d, on="user_id", how="left"))
    cust["recent_3m_orders"] = cust["recent_3m_orders"].fillna(0)
    cust["revenue_30d"] = cust["revenue_30d"].fillna(0)

    # Purchase-interval stats (cadence) — only meaningful for repeat buyers
    try:
        ints = (past.groupby("user_id", observed=True)["order_time"]
                .apply(lambda s: s.sort_values().diff().dt.days.dropna()))
        if not ints.empty:
            stats = ints.groupby(level=0).agg(["mean", "std"])
            stats.columns = ["interval_mean", "interval_std"]
            cust = cust.merge(stats.reset_index(), on="user_id", how="left")
    except Exception:
        pass
    if "interval_mean" not in cust.columns:
        cust["interval_mean"] = np.nan
    if "interval_std" not in cust.columns:
        cust["interval_std"] = np.nan
    cust["interval_mean"] = cust["interval_mean"].fillna(cust["tenure_days"].clip(lower=1))
    cust["interval_std"] = cust["interval_std"].fillna(0)

    if "register_time" in past.columns:
        reg = (past.dropna(subset=["register_time"])
               .groupby("user_id", observed=True)["register_time"].min().reset_index())
        reg["register_time"] = pd.to_datetime(reg["register_time"], errors="coerce")
        cust = cust.merge(reg, on="user_id", how="left")
        cust["days_since_reg"] = ((ref_date - cust["register_time"])
                                  .dt.days.clip(lower=0).fillna(cust["tenure_days"]))
    else:
        cust["days_since_reg"] = cust["tenure_days"]
    return cust


def predict_churn(df: pd.DataFrame, churn_days: int = 60) -> dict | None:
    """
    Leak-free temporal churn model.

    Design: cutoff = latest order date - churn_days. Features are computed
    from orders <= cutoff only; the label is "placed NO order in the
    churn_days window after the cutoff". The previous design defined churn
    from recency while feeding recency as a feature -> AUC 1.0 (leakage).

    Validation: 5-fold stratified CV (out-of-fold probabilities) on the
    cutoff dataset; Youden's J threshold. The at-risk table re-scores every
    customer on features as of TODAY (the true current state).
    """
    needed = {"user_id", "order_time", "sales"}
    if not needed.issubset(df.columns):
        return None

    df = df.dropna(subset=["user_id", "order_time", "sales"]).copy()
    df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce")
    df = df.dropna(subset=["order_time"])
    if "segment" in df.columns:
        df = df[df["segment"].astype(str).str.upper() == "B2C"]
    if df.empty or df["user_id"].nunique() < 30:
        return None

    today = df["order_time"].max()
    cutoff = today - pd.Timedelta(days=churn_days)

    train = _churn_features(df, cutoff)
    if train.empty or len(train) < 40:
        return None
    future_buyers = set(df.loc[df["order_time"] > cutoff, "user_id"].unique())
    train["churn"] = (~train["user_id"].isin(future_buyers)).astype(int)

    X = train[_CHURN_FEATURES].fillna(0).values
    y = train["churn"].values
    if y.sum() < 5 or (1 - y).sum() < 5:
        return None

    clfs = {
        "Logistic Regression": Pipeline([
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=1000, random_state=42,
                                       class_weight="balanced")),
        ]),
        "Random Forest": RandomForestClassifier(
            n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1),
        "Gradient Boosting": GradientBoostingClassifier(
            n_estimators=150, random_state=42, max_depth=3, learning_rate=0.05),
        "Extra Trees": ExtraTreesClassifier(
            n_estimators=200, random_state=42, class_weight="balanced", n_jobs=-1),
    }

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
    fitted, metrics, roc_curves = {}, {}, {}
    for name, clf in clfs.items():
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            try:
                proba_oof = cross_val_predict(clf, X, y, cv=cv,
                                              method="predict_proba")[:, 1]
            except Exception:
                proba_oof = np.full(len(y), 0.5)
            clf.fit(X, y)
        fitted[name] = clf
        try:
            fpr_c, tpr_c, thrs = roc_curve(y, proba_oof)
            best_thr = float(thrs[np.argmax(tpr_c - fpr_c)])
        except Exception:
            best_thr = 0.5
        pred = (proba_oof >= best_thr).astype(int)
        try:
            auc = float(roc_auc_score(y, proba_oof))
        except Exception:
            auc = float("nan")
        metrics[name] = {
            "auc": auc,
            "precision": float(precision_score(y, pred, zero_division=0)),
            "recall": float(recall_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0)),
            "threshold": best_thr,
        }
        try:
            fpr2, tpr2, _ = roc_curve(y, proba_oof)
            roc_curves[name] = (fpr2.tolist(), tpr2.tolist())
        except Exception:
            roc_curves[name] = ([0, 1], [0, 1])

    best_model = max(metrics, key=lambda k: metrics[k]["auc"]
                     if not np.isnan(metrics[k]["auc"]) else 0)

    rf = fitted.get("Random Forest")
    fi = (pd.Series(rf.feature_importances_, index=_CHURN_FEATURES)
          .sort_values(ascending=False)
          if hasattr(rf, "feature_importances_") else pd.Series(dtype=float))

    # Score everyone on TODAY's features (current state, not the cutoff snapshot)
    current = _churn_features(df, today)
    Xc = current[_CHURN_FEATURES].fillna(0).values
    proba_now = fitted[best_model].predict_proba(Xc)[:, 1]
    at_risk = current[["user_id", "recency_days", "frequency", "monetary",
                       "avg_order_value", "recent_3m_orders", "revenue_30d"]].copy()
    at_risk["churn_probability"] = (proba_now * 100).round(1)
    at_risk["risk_tier"] = pd.cut(
        proba_now, bins=[0, 0.3, 0.6, 1.001],
        labels=["Low Risk", "Medium Risk", "High Risk"])
    at_risk = at_risk.sort_values("churn_probability", ascending=False)

    return {
        "at_risk": at_risk,
        "metrics": metrics,
        "best_model": best_model,
        "feature_importance": fi,
        "roc_curves": roc_curves,
        "churn_days": churn_days,
        "total_customers": len(train),
        "churned_count": int(y.sum()),
        "validation_cutoff": str(cutoff.date()),
    }


# ---------------------------------------------------------------------------
# 3 — Product Demand Forecasting
# ---------------------------------------------------------------------------

def forecast_demand(df: pd.DataFrame, horizon_weeks: int = 4) -> dict | None:
    """
    Forecast next ``horizon_weeks`` weeks of order volume per operator x product.

    Round-7 fixes:
      - NA-safe grouping: operator (missing on B2C in raw data) and product
        (missing on B2B) are coalesced per segment and filled with 'Unknown' -
        previously pandas dropped every NA-keyed group, returning None.
      - The trailing partial week is excluded from history.
      - Output limited to the top 60 groups by volume, with a WoW % column.

    Per-group model: >=8 weeks history -> linear trend + 90% CI;
    otherwise 4-week moving average + 20% band.
    """
    if "order_time" not in df.columns:
        return None

    df = df.dropna(subset=["order_time"]).copy()
    df["order_time"] = pd.to_datetime(df["order_time"], errors="coerce")
    df = df.dropna(subset=["order_time"])
    if df.shape[0] < 10:
        return None

    # NA-safe labels: product (B2C) -> product_info (B2B) -> denomination -> Unknown
    lbl = pd.Series([None] * len(df), index=df.index, dtype="object")
    for c in ("product", "product_info", "denomination"):
        if c in df.columns:
            v = df[c].astype("object")
            v = v.where(pd.notna(v), None)
            lbl = lbl.where(pd.notna(lbl), v)
    df["product_group"] = (pd.Series(lbl, index=df.index)
                           .fillna("Unknown").astype(str).str.strip().str[:40])
    if "operator" in df.columns:
        op = df["operator"].astype("object")
        df["op_group"] = pd.Series(op.where(pd.notna(op), "Unknown"),
                                   index=df.index).astype(str).str.strip()
    else:
        df["op_group"] = "Unknown"

    df["week"] = df["order_time"].dt.to_period("W")
    all_weeks = sorted(df["week"].unique())
    # Drop the trailing partial week (daily uploads make it incomplete)
    if len(all_weeks) >= 3:
        last_week = all_weeks[-1]
        if df["order_time"].max() < last_week.end_time - pd.Timedelta(hours=12):
            all_weeks = all_weeks[:-1]
            df = df[df["week"].isin(all_weeks)]
    if len(all_weeks) < 2:
        return None

    weekly_grp = (df.groupby(["op_group", "product_group", "week"], observed=True)
                  .size().reset_index(name="orders"))
    if weekly_grp.empty:
        return None

    # Top 60 groups by total volume
    totals = (weekly_grp.groupby(["op_group", "product_group"], observed=True)["orders"]
              .sum().sort_values(ascending=False))
    n_groups_total = len(totals)
    keep = set(totals.head(60).index)

    rows = []
    for (operator, product_group), grp in weekly_grp.groupby(
            ["op_group", "product_group"], observed=True):
        if (operator, product_group) not in keep:
            continue
        s = grp.sort_values("week").set_index("week")["orders"]
        s = s.reindex(all_weeks, fill_value=0)
        vals = s.values.astype(float)
        vals = vals[-12:] if len(vals) > 12 else vals
        avg4 = float(np.mean(vals[-4:])) if len(vals) >= 4 else float(np.mean(vals))
        wow = ((vals[-1] - vals[-2]) / vals[-2] * 100) if len(vals) >= 2 and vals[-2] > 0 else np.nan

        if len(vals) >= 8:
            t = np.arange(len(vals))
            try:
                coef = np.polyfit(t, vals, 1)
            except Exception:
                coef = np.array([0.0, avg4])
            slope = coef[0]
            trend = "up" if slope > avg4 * 0.02 else ("down" if slope < -avg4 * 0.02 else "flat")
            preds = [max(0.0, float(np.polyval(coef, len(vals) + i)))
                     for i in range(horizon_weeks)]
            resid = float(np.std(vals - np.polyval(coef, t))) if len(vals) > 2 else avg4 * 0.15
        else:
            trend = "flat"
            preds = [avg4] * horizon_weeks
            resid = avg4 * 0.20

        row = {
            "Operator": str(operator),
            "Product Group": str(product_group),
            "Avg 4-Wk": round(avg4, 1),
            "WoW %": ("-" if np.isnan(wow) else f"{wow:+.0f}%"),
            "Trend": trend,
        }
        for i, p in enumerate(preds, 1):
            row[f"Wk {i} Forecast"] = round(p, 0)
            row[f"Wk {i} Low"] = round(max(0.0, p - 1.64 * resid), 0)
            row[f"Wk {i} High"] = round(p + 1.64 * resid, 0)
        rows.append(row)

    if not rows:
        return None
    out = pd.DataFrame(rows).sort_values("Avg 4-Wk", ascending=False).reset_index(drop=True)
    return {
        "forecast": out,
        "horizon_weeks": horizon_weeks,
        "n_groups_total": n_groups_total,
        "n_groups_shown": len(out),
    }
