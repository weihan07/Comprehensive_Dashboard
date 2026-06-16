# Sales Dashboard — Weakness & Gap Review (漏洞 / 缺点)

**Reviewed:** 2026-06-13 · **Scope:** the full dashboard, data pipeline, and ML
engine, from four management perspectives. Severity: 🔴 critical · 🟡 medium ·
🟢 minor. Items marked **[FIXED Round 7]** were addressed in this round.

---

## 1 · Data Analyst Manager — model & metric integrity

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| A1 | 🔴 | **[FIXED Round 7]** Settlement price was mixed-currency but margin math treated it all as RMB → Indonesia/Vietnam/Kyrgyzstan showed nonsensical margins and total gross margin was −12.6 billion. | Per-row `settlement_rmb` conversion engine + Settlement Currency Audit table now live. Verify the audit table against supplier statements monthly. |
| A2 | 🔴 | **[FIXED Round 7]** Churn model AUC = 1.000 (label leakage: churn defined from recency while recency was a feature). | Rebuilt as a leak-free temporal split (features before cutoff, label after). Honest AUC now ≈0.79–0.81. |
| A3 | 🔴 | **[FIXED Round 7]** Revenue forecast R² was −1 to −635 (only ~15 weekly training rows; MLP diverged). | Rebuilt on daily grain with walk-forward validation + seasonal-naïve baseline; daily MAPE ≈5%. Forecast now falls back to baseline honestly when ML can't beat it. |
| A4 | 🔴 | **[FIXED Round 7]** Demand forecast returned nothing (NA groupby keys silently dropped every group). | NA-safe per-segment label coalescing; now returns 60 groups across B2B+B2C. |
| A5 | 🟡 | **FX rates are hardcoded mid-2025 values** with no effective-dating. Cross-currency revenue trends and any "Local Currency" view drift as real rates move; historical months are revalued at today's rate. | Move `fx_rates` to a dated rate table (rate per month); convert each order at its order-month rate. |
| A6 | 🟡 | **PoP "Top Movers" has no significance / minimum-volume guard.** A market going 2→6 orders shows as "+200%" beside a real mover. | Add a minimum-base-volume floor and/or rank by absolute change, not just %. |
| A7 | 🟡 | **Cohort retention/LTV tail months are tiny-sample noise** shown with the same visual weight as mature cohorts. | Grey out or annotate cohorts with <N customers; add a sample-size column. |
| A8 | 🟡 | **IP country vs billing/destination country is never cross-checked.** A fraud/risk signal (order from IP that doesn't match the market) is sitting unused. | Add an IP-vs-market mismatch flag in the Customer/Market tabs. |
| A9 | 🟢 | **Mean vs median inconsistency** across tabs (some KPIs use mean AOV, audit uses median). | Standardise: report both, or pick median for skewed money fields consistently. |
| A10 | 🟢 | **No data dictionary surfaced in-app**; column meanings live only in code/PDF. | Link the documentation PDF from an "ℹ️ About the data" panel. |

---

## 2 · Operations Manager — reliability & process

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| O1 | 🔴 | **Single-machine, manual start, no auto-restart.** If the box reboots or the process dies, the dashboard is simply down until someone runs the command. | Run as a Windows service / scheduled task with auto-restart; or host on an internal server. |
| O2 | 🔴 | **Windows App Control intermittently blocks scikit-learn DLLs** → AI tab dies (now degrades gracefully, but the capability is still lost on those runs). | Whitelist the `sales_env` interpreter in App Control policy, or run ML in a separate approved environment. |
| O3 | 🟡 | **Daily import is fully manual** (download export → upload → process). Easy to forget; freshness only flagged passively by the sidebar badge. | Watch-folder auto-import: drop the daily file in a folder, a scheduled job ingests it. |
| O4 | 🟡 | **No active alerting.** Refund spikes, routing gaps, and stale data are visible only if someone opens the relevant tab. | Scheduled job emails/Slacks a daily exception digest (refund rate > X%, routing gap > N, data > 2 days old). |
| O5 | 🟡 | **No authentication / access control.** Anyone who can reach the port sees all revenue, margin and customer data. | Put behind SSO / a reverse proxy with auth; restrict to the office network/VPN. |
| O6 | 🟡 | **Backups are manual** (the Excel-backup button) and live on the same disk as the source. | Scheduled nightly copy of `./database` to off-machine / cloud storage. |
| O7 | 🟢 | **No cache-integrity check** — if a rebuild half-fails, the cache could silently diverge from the rolling stores. | Nightly check: rolling-store row counts vs cache row counts, alert on mismatch. |

---

## 3 · Business Manager — decision usefulness

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| B1 | 🔴 | **No single "Net Revenue" KPI.** GMV is shown, refunds are shown separately, coupon cost is in another tab — but `GMV − refunds − coupon spend − COGS` (true contribution) is never one number. | Add a Net Contribution KPI to Executive Overview. |
| B2 | 🟡 | **Margin ignores refund recovery.** When an order is 已退款, is the supplier settlement refunded back to us? Margin currently treats settled cost as sunk. | Confirm supplier refund behaviour; net refunded settlement out of cost. |
| B3 | 🟡 | **No targets / budget overlay.** Every trend is absolute; there's no "vs plan" line, so "good month?" needs outside context. | Add a monthly target table and plot target lines on the revenue trend. |
| B4 | 🟡 | **Supplier concentration threshold is a static 80%/3-operator rule** regardless of category or market. | Make thresholds configurable; show concentration per category (a single-source data SKU is riskier than airtime). |
| B5 | 🟡 | **FX staleness (A5) flows into reported margins** for local-currency settlement markets — margin % can drift purely from rate movement. | Same fix as A5 (dated FX); show "margins at <rate-date> rates". |
| B6 | 🟢 | **No customer-level profitability**, only revenue. High-revenue resellers on thin-margin SKUs may be low-profit. | Join margin to the B2B agent / B2C cohort views. |

---

## 4 · Marketing Manager — campaign & growth insight

| # | Sev | Finding | Recommendation |
|---|-----|---------|----------------|
| M1 | 🟡 | **Coupon attribution is "any coupon ever used"**, not first-touch or within-campaign-window. Repeat-rate comparison (coupon vs non-coupon) is therefore biased. | Attribute by the order that used the coupon; compare next-90-day behaviour from that point. |
| M2 | 🟡 | **No CAC or channel ROI.** `user_source` (channel) and coupon spend exist but are never combined into cost-per-acquired-customer or revenue-per-channel-dollar. | Build a channel scorecard: new customers, coupon spend, 90-day revenue, ROI per `user_source`. |
| M3 | 🟡 | **Badge-product comparison has selection bias** — badged products are chosen because they're already popular, so "badged sells more" is partly circular. | Compare pre/post badging for the same SKU, or use a matched control group. |
| M4 | 🟡 | **No registration → first-purchase funnel by channel.** Activation rate per acquisition source is invisible. | Add a funnel: registrations → first order → repeat, split by `user_source`. |
| M5 | 🟢 | **Campaign metadata is missing upstream** — no campaign start/end dates, no UTM/source on the coupon. Limits attribution precision. | Request campaign dates + source tags in the Master export (see Data Asks). |

---

## 5 · Database & Upload — 12 improvement suggestions (advisory)

These were requested explicitly; none are implemented yet — listed by priority.

1. **File-hash duplicate-upload guard** — refuse / warn when the same file (by content hash) is uploaded twice; today only order-id dedup catches it.
2. **Row-level validation quarantine** — on import, divert rows with negative/zero sales, unknown status, or unparseable dates to a quarantine sheet instead of silently absorbing them.
3. **Restatement / backfill detection** — when an incoming row changes a value for an existing order id (not just adds new ids), log the before/after so price/status corrections are auditable.
4. **Import audit log** — append-only log of who uploaded which file, when, rows added/skipped — for traceability.
5. **Watch-folder auto-import** — scheduled ingestion from a drop folder (also O3).
6. **Nightly cache-integrity check** — rolling-store vs cache row-count reconciliation with an alert (also O7).
7. **Scheduled off-machine backup** of `./database` (also O6).
8. **Parquet month-partitioning** — partition the cache by order-month so loads/filters scale as history grows beyond ~1–2M rows.
9. **FX rate table with effective dates** — convert at order-date rates, not one global snapshot (also A5/B5).
10. **Supplier dimension table** — map operator → supplier company → contract/currency, so settlement currency, margin targets and concentration are driven by data, not the hardcoded rules in `_apply_settlement_currency`.
11. **Upstream data asks** — populate 取消原因 (cancel reason, currently empty); add campaign start/end + source tags; confirm whether settlement is refunded on 已退款.
12. **Unify recon-system and dashboard ingestion** — both read the same daily exports; a single shared ingestion pipeline (one parser, two consumers) removes drift between reconciliation and reporting.

---

## Round 7 summary

**Fixed this round:** A1 settlement currency · A2 churn leakage · A3 revenue forecast ·
A4 demand forecast. Plus: per-row Settlement Currency Audit, honest ML quality
banners, hourly peak-purchase module, simplified Iraq Pinstore stock planner.

**Highest-value remaining:** O1/O2 (reliability — make it always-on and ML-stable),
B1 (net-revenue KPI), A5/#9 (dated FX), O4 (alerting).
