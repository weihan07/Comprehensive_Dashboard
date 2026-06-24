# Dashboard Comparison & Alignment Plan — Sales Dashboard ⇄ Bitsbang (China-team)

**Prepared:** 2026-06-23 · **Scope:** align our `Sales Dashboard` (Shiny-for-Python BI app)
with the China team's reference dashboard ("bitsbang"), copy its terminology, add its
addon visualizations, restructure the Product & Denomination tab with an operator filter,
add a Guideline tab, and propose removals.

> **Important context correction.** The original request named
> `Code\Indo Product Management`, but that folder is a small Streamlit *price-tracker*
> (Catalog / Compare / Changes / Notes / Export) with none of the features described. Every
> referenced feature — "Product & Denomination Analysis", "🌐 IP Geographic Origin Analysis
> (B2C)", airtime/data/operator analysis — lives in **`Code\Sales Dashboard\sales_dashboard.py`**.
> Confirmed with the user: **the target is the Sales Dashboard.**

---

## A. The two dashboards at a glance

| | **Our Sales Dashboard** | **Bitsbang (reference)** |
|---|---|---|
| Tech | Shiny for Python, Plotly, parquet cache (~1.1M rows) | Static HTML + vanilla JS, hand-rolled SVG (no chart lib) |
| Structure | 11 tabs (`ui.navset_tab` / `ui.nav_panel`) | 1 page, country + source selectors switch sections |
| Language | Bilingual EN / 中文 (CSS `body[data-lang]` toggle) | 中文 only |
| Depth | ~120 render fns, deep operator/denomination/cohort/ML | Lean monthly operating summary |
| Audience | Internal management (multi-perspective) | China ops team (operating KPIs by country/channel) |

**Conclusion:** our dashboard is a *superset* of bitsbang in analytical depth. The gap is
**vocabulary** (the China team reads bitsbang's terms) and a handful of **bitsbang framing
devices** (new-vs-old split everywhere, channel selector, key-country 3-month mini-trends,
refresh + data-updated stamp). So the plan is *align terms + add framing*, not rebuild.

---

## B. Terminology alignment (the core ask: "copy all the terms")

Where each term lives in code:
- **KPI card labels** → inline `_bl("English", "中文")` in `sales_dashboard.py` (e.g. line 4495).
- **Section headings** → inline `_bh3("English", "中文", …)` and `_bnav(...)` / `_bp(...)`.
- **Chart titles / axis / legend / table headers** → English source string in code, translated
  to 中文 at render via `_tt()` → `translations.translate_chart_text()` using `CHART_PHRASES`.
- `translations.py` `ZH` / `EN_LABELS` / `T_UI` dicts are **mostly vestigial** (headings don't
  call them) — alignment happens in the inline strings + `CHART_PHRASES`.

### B1. Headline KPIs / metrics

| Concept | Bitsbang 中文 | Our current 中文 | **Adopt (中文)** | EN to keep |
|---|---|---|---|---|
| Revenue / GMV | **营业额** (GMV) | 总收入 (GMV) | **营业额 (GMV)** | Revenue (GMV) |
| Old-customer revenue | **老客营业额** | — (new) | **老客营业额** | Returning-customer GMV |
| New-customer revenue | **新客营业额** | — (new) | **新客营业额** | New-customer GMV |
| Successful orders | **成单数** | 订单总量 / 订单量 | **成单数** | Successful Orders |
| Successful users | **成单人数** | 活跃客户数 | **成单人数** | Successful Users |
| Success rate | **成单率** | 成功率 | **成单率** | Success Rate |
| AOV | **客单价** | 平均订单价值 (AOV) | **客单价** | AOV |
| Repurchase rate | **复购率** | 复购率 ✓ | **复购率** | Repurchase Rate |
| Retention rate | **留存率** | 客户留存率 | **留存率** | Retention Rate |
| New customers | **新客数** | 新客户获取量 | **新客数** | New Customers |
| Conversion rate | **转化率** | — (new) | **转化率** | Conversion Rate |

### B2. Customer-type, product, channel & grouping terms

| Concept | Bitsbang 中文 | Our current 中文 | **Adopt (中文)** |
|---|---|---|---|
| Returning customers | **老客** | 回购客户 | **老客** |
| New customers | **新客** | 新客户 | **新客** |
| Airtime (category) | **充话费** (short 话费) | 话费 | **充话费** (话费 in axes) |
| Data (category) | **买流量** (short 流量) | 流量 | **买流量** (流量 in axes) |
| Channel / source | **渠道来源** | 来源 | **渠道来源** |
| Source rollup option | **来源汇总** | — | **来源汇总** |
| All-countries rollup | **汇总** | 汇总 ✓ | **汇总** |
| Key countries (≥ threshold) | **重点国家** | — | **重点国家** |
| Other-countries group | **全球** | 全球 ✓ | **全球** |

### B3. Bitsbang section titles to mirror (verbatim, for recognisability)

`本月商品分类占比（按成单数）` · `近3个月：话费 vs 流量 占比（按成单数）` ·
`话费/流量：新客&老客拆分（本月）` · `国家订单分布 TOP5` · `国家支付金额 TOP10` ·
`重点国家&全球：总营业额（近3个月）` (+ the 9 sibling 近3个月 metric variants) ·
`老客 - 话费` / `老客 - 流量` / `新客 - 话费` / `新客 - 流量` ·
`产品订单分布 TOP5（品牌商+SKU/面额）` · `产品支付金额 TOP10（品牌商+SKU/面额）` ·
`指标明细（依次展示 + 和上月对比）`.

**Caveat (gotcha):** `translate_chart_text()` does ordered **longest-substring** replacement.
When changing a metric word, update the **ZH value** in `CHART_PHRASES`; keep the EN key as the
literal that appears in code. Changing 收入→营业额 *globally* is too broad (axis labels read fine
as 收入); restrict 营业额 to the **headline KPI labels and TOP-N revenue titles**, keep 收入 in
generic axis fragments. `复购率` already matches — no change.

---

## C. Visualization coverage: bitsbang → our equivalent

| Bitsbang visual | Our equivalent today | Action |
|---|---|---|
| 11 KPI cards w/ MoM arrows | `_kpi_card` already renders ▲/▼ deltas (line 3908) | **Relabel** to B1 terms; **add** 老客/新客营业额, 成单率, 复购率, 留存率, 转化率 cards |
| Product category donut (按成单数) | Category bar/treemap (by revenue) | Add a **donut by order count** to match |
| 话费 vs 流量 3-month stacked | Category monthly trend (line) | Add **话费/流量 share** stacked view |
| 话费/流量 × 新客&老客 split | Top products by segment (B2B/B2C) | Add **新客/老客** split (not just B2B/B2C) |
| Top5 countries by orders (donut) | Top markets by revenue (bar) | Add **orders donut** variant |
| Top10 countries by revenue (bars) | Top markets by revenue (bars) ✓ | Keep |
| Key-country 3-month grouped trends | Monthly trend lines | Add **grouped 3-month mini-trends** for 重点国家 |
| Product rankings 老客/新客 × 话费/流量 | Top products tables | Restructure in Product tab (see E) |

**Net new from bitsbang:** new-vs-old customer split as a first-class dimension, order-count
donuts, the 话费/流量 share view, and the 重点国家 3-month grouped mini-trends.

---

## D. Addon features (bitsbang) — present vs missing

| Addon | Status in our app | Action |
|---|---|---|
| MoM ▲/▼ colored deltas on KPIs | **Present** (`_kpi_card`) | Reuse; ensure on all new cards |
| 老客/新客 split pervasive | Partial (B2B/B2C only) | **Add** new-vs-returning split |
| Channel / 渠道来源 selector | Missing (`user_source` column exists) | **Add** sidebar/tab channel filter + per-channel view |
| 重点国家 3-month grouped trend | Missing | **Add** grouped mini-trend |
| Refresh button + "数据更新：…" stamp | Staleness banner exists (`staleness_banner`) | **Add** explicit refresh + last-updated label |
| Gradient header / card accents | Present (indigo theme, `theme.py`) | Polish only |

---

## E. Restructure "Product & Denomination Analysis" tab + operator filter

**Current:** one long tab (UI starts line 2207). Has a **Product Category** filter
(`product_type_filter_ui`, server line 3246) but **no operator filter** — operator scoping
only exists in Sales Explorer (`q_operator_ui`, line 9174).

**Target (user ask — "airtime & data, view all operators OR pick one"):**
1. Add a tab-level **Operator filter** beside the category filter, default **"All operators"**,
   reusing the `q_operator_ui` selectize pattern (value-counts top-N, `placeholder="All
   operators"`). New reactive `prod_operator()` threads into every groupby on the tab.
2. Reorganize into 4 clearly-labeled sub-parts (banner dividers already used at lines 2228, 2305):
   - **① Product Category Overview** (充话费 / 买流量 / e-wallet / bills)
   - **② Airtime / 充话费** — denomination bands, top denominations, denomination × operator
   - **③ Data / 买流量** — package size tiers, orders/revenue by volume, operator × size
   - **④ Operator × Denomination matrix** — the heatmap (`denomination_heatmap`, line 7611)
3. Every chart in ②–④ filters by `prod_operator()`; when "All operators" selected, behaves as
   today. Add a small "showing: All operators / <operator>" caption for context.

**Reuse:** master filtered reactive `data_rv()` → existing per-section frames; operator choices
builder identical to `q_operator_ui`; `apply_theme` for styling; `_tt` for titles.

---

## F. New "Guideline" tab (12th `nav_panel`)

Add after AI Predictions (last `nav_panel` block ends ~line 3037, before `def server` at 3038;
insert a new `ui.nav_panel(_bnav("📖 Guideline","📖 使用指南"), …)`).

Content = a static, bilingual catalogue generated from an inventory list, grouped by tab. For
each visualization: **title · chart type · what it shows · the business question it answers**.
Render as styled cards/accordions (reuse `chart-container` + `_bh3`/`_bp`). Append a
**"Proposed removals"** section (see G) with rationale, so the page doubles as documentation +
change log. No data reactivity needed → cheap and safe.

---

## G. Proposed removals (propose-only — awaiting approval)

| # | Item | Where | Rationale | Recommendation |
|---|---|---|---|---|
| R1 | **IP world map** "Global IP Origin Distribution (B2C)" | Customer Analytics, render `b2c_ip_geo*` lines 8598–8663; UI line 2644 | User flagged as non-useful; low decision value, heavy | **Remove map**; keep the **IP-vs-market mismatch** as a compact KPI/flag (review finding A8 calls it a useful unused fraud signal) |
| R2 | Iraq Pinstore modules | ~lines 5718–5893 (`CHART_PHRASES` has Iraq PIN titles) | Reportedly not surfaced in main tabs; niche | **Candidate** — confirm before removing |
| R3 | Redundant Top-N variants | several tabs repeat Top-N revenue/orders bars | Some overlap (e.g. market revenue shown 2–3 ways) | **Candidate** — consolidate, list in Guideline |

Only **R1 (the map)** is explicitly user-approved in concept; R2/R3 listed for your sign-off in
the Guideline tab before deletion.

---

## H. Implementation sequence & risks

1. **Terminology** — edit `CHART_PHRASES` (ZH values) + core inline `_bl`/`_bh3`/`_bnav` KPI &
   heading strings to B1/B2 terms. *Lowest risk, central.*
2. **New KPI cards** — 老客/新客营业额, 成单率, 复购率, 留存率, 转化率 (reuse `_kpi_card`).
3. **Product tab restructure** — operator filter + 4 sub-parts.
4. **Bitsbang framing viz** — new-vs-old splits, order-count donuts, 话费/流量 share, 重点国家
   3-month grouped trends, channel selector, refresh + 数据更新 stamp.
5. **Guideline tab** + **remove IP map (R1)**.

**Risks / gotchas:**
- `sales_dashboard.py` is ~11k lines and the app isn't run-testable in this environment —
  edits must be surgical; verify Python parses (`python -m py_compile`) after each batch.
- `translate_chart_text` longest-substring behaviour — scope 营业额 to headline strings only.
- Reactive invalidation — new `prod_operator()` must compose with `data_rv()` like existing filters.
- Removals (R1) touch both UI (line 2644) and server render (8598+) — remove both ends.

---

## I. Differences vs the China-team standard (`全球共用计算取数公式及标准`)

The new **运营概览** block on Executive Overview now implements this standard. Key
**differences** between the standard and the dashboard's *existing* behaviour:

### Global filters
| # | Rule (standard) | Dashboard before | Status |
|---|---|---|---|
| 1 | Exclude **电子钱包** (e-wallet) from all core metrics | Included everywhere | ✅ **dashboard-wide** (`_apply_global_exclusions` in `filtered_base_calc`/`previous_period_base`; flag `_EXCLUDE_EWALLET_TNG`; header note) |
| 2 | Exclude **Touch'n Go / TNG** | Included | ✅ **dashboard-wide** (same; ≈22% of GMV) |
| 3 | All core metrics on **充值成功** basis | Status selector (defaults Successful) | ✅ 运营概览 forces it; other tabs follow selector |
| 4 | **汇总/全球 exclude Malaysia**; single-country allows it | No view-type concept | 🔴 not implemented — needs a 汇总/重点国家/全球 view selector |
| 5 | **渠道来源** raw → `dim_source_map` → 会员来源; drop rows marked 删除 | Uses raw `user_source` | 🔴 not implemented — needs the mapping table |

### Metric definitions (where the dashboard already had a *different* meaning)
| Metric | Standard | Dashboard's existing chart | Status |
|---|---|---|---|
| **新客/老客** | 注册月 == 订单月 → 新客; 注册月 < 订单月 → 老客 | "🔄 New vs Returning" = *first-ever order in period* | ✅ aligned in 运营概览 **and** the New-vs-Returning chart |
| **客单价** | GMV ÷ **成单数** (successful) | old AOV = GMV ÷ **all** orders | ✅ aligned in 运营概览 (= ÷ successful under default status filter elsewhere) |
| **复购率** | `\|上月成功∩本月成功\| / \|本月成功\|` | "Repeat Purchase" = customers with ≥2 orders in period | ✅ aligned in 运营概览 **and** the Customer-KPIs card |
| **留存率** | `\|上月新客成功∩本月成功\| / \|上月新客成功\|` | cohort-retention heatmap (different construct) | ✅ aligned in 运营概览 **and** the Customer-KPIs card (the cohort heatmap kept as a complementary view) |

### Data gaps — **RESOLVED** with the 用户列表 (`用户列表 20260623…csv`, 649,444 users)
The Users registration table is now loaded (`_load_user_list`) and joined to orders on
`ID` ⇄ `user_id` (99.9% match after `.0` normalisation). Exact metrics now live:
| Metric | Definition implemented | Status |
|---|---|---|
| **新客数** | `COUNT(DISTINCT ID) WHERE 注册时间 ∈ period` from the 用户列表, scoped by country + channel rules | ✅ exact (e.g. 2026-05 汇总 = 11,175) |
| **转化率** | `\|period 新客 ∩ period 成功订单用户\| / \|period 新客\|` (用户列表 ∩ 订单表) | ✅ exact (e.g. 2026-05 汇总 = 48.7%) |
| Channel rules | 汇总 = **WeChat only** (会员来源 ∌ 支付宝); WeChat excludes empty 来源国家; Alipay allowed | ✅ implemented in `_new_customer_ids` |

> Loader looks for `用户列表*.csv` in `database/` first, then the Report Raw Data folder, and
> picks the latest by filename — drop a newer export in either place to refresh.

### Display conventions
| # | Standard | Dashboard | Status |
|---|---|---|---|
| 6 | Signed deltas with absolute, e.g. `+6.8%（+154,307元）` | arrow + % only | 🟡 minor — could add absolute in parentheses |
| 7 | SKU as backtick + full unit (`` `200000 Rp` ``), integer denominations, brand-grouped | denominations shown, not this exact format | 🟢 minor |

**To close the remaining gaps, the dashboard would need:** (a) the **用户列表 (Users registration
table)** export → exact 新客数 & 转化率; (b) the **来源映射表 (dim_source_map)** → 会员来源
normalization; (c) a **汇总 / 重点国家 / 全球** view-type selector → the Malaysia-exclusion rule.
Optionally, align the existing New-vs-Returning / Repeat-Purchase / AOV charts to the standard, and
apply the e-wallet/TNG exclusion dashboard-wide.
