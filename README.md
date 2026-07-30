# Comprehensive Dashboard — Global Mobile Recharge Revenue Intelligence

A 10-tab business-intelligence web app (Shiny for Python) for a global mobile-recharge
platform, covering revenue (GMV), order quality, markets, suppliers/operators, products &
denominations, customers, marketing, AI forecasts, and an ad-hoc Sales Explorer. Bilingual
(English / 中文).

> **Note:** the real order data (`database/`) and the Python virtualenv (`sales_env/`) are
> intentionally **not** committed — the data contains customer PII (phone numbers, IPs, user IDs)
> and the venv is large/machine-specific. See **Data** below.

## Tabs

Grouped into 6 top-level nav items (dropdowns):

- **📊 Overview** — verdict line, hero KPIs, Pace-to-Month-End, alerts, movers, trend, geography
- **📈 Performance** — Performance Comparison (incl. Revenue Bridge) · Revenue & Orders
- **🌍 Markets & Products** — Market Intelligence · Product & Denomination Analysis
- **🏭 Operations** — Supplier & Operator Performance (incl. Profit Pool) · Operational Intelligence
- **👥 Customers** — Customer Analytics (incl. sub-national IP failure map) · Marketing & Promotions
- **🧰 Tools** — ⏱ Sales Explorer · 🤖 AI Predictions · 📖 Guideline

## Tech stack

- **Shiny for Python 1.6** (reactive server, bslib layout)
- **pandas + PyArrow** parquet cache (≈1.1M order rows load in ~0.2 s)
- **Plotly** charts · **scikit-learn** (revenue / churn / demand models) · **reportlab** (PDF export)

## Setup

```bash
# 1. create the virtualenv and install dependencies
python -m venv sales_env
sales_env\Scripts\pip install -r requirements.txt

# 2. enable the data-leak guard (one time, per clone) — see Data & Security
git config core.hooksPath githooks

# 3. seed the local database/ folder (it is NOT in the repo) — see Data & Security
```

## Run

```bash
sales_env\Scripts\python.exe -m shiny run sales_dashboard.py --port 8050
```

Then open <http://127.0.0.1:8050>.

### Optional: sub-national IP failure map

The **Customer Analytics → 🗺️ Recharge-Failure Map by State/Province** geolocates B2C customer IPs
offline. It needs one file (not in git):

1. `pip install maxminddb` (already in `requirements.txt`).
2. Download the free, no-account **DB-IP City Lite** DB and unzip it into `database/`:
   `https://download.db-ip.com/free/dbip-city-lite-YYYY-MM.mmdb.gz` → `database/dbip-city-lite.mmdb`.

Without the file the rest of the dashboard runs normally; that one map shows a "database not
installed" hint. No network calls at runtime — raw IPs never leave the machine.

## Updating the data (sidebar → ⚙ Data Management)

All data actions live in the collapsible **⚙ Data Management** block at the bottom of the sidebar.
Heavy rebuilds now run **off the UI thread**, so the dashboard refreshes **automatically** when they
finish — no browser refresh needed (older builds could look "stuck" on old numbers because the long
rebuild froze the session).

| You did this… | Click this | What it does |
|---|---|---|
| Edited `Master Data.xlsx` / `Agent Data.xlsx` by hand | **🔄 Rebuild Data Pipeline** | Re-reads the source workbooks (all `Whole*` + history sheets), rebuilds the rolling stores + cache. 5–25 min. |
| Downloaded new daily CSVs into `Data/…` | **🧹 Clean & Import Daily Files** | Cleans + appends only the new daily files (skips already-imported). Fast. |
| Want `Data/` to be the *sole* source (one-off) | **♻️ Rebuild ALL from Data/** | Full rebuild from the `Data/` history xlsx + every daily CSV. |
| Have a single Agent/Master export to add | **▶ Process & Append** (upload) | Uploads one file, de-dupes on order id, appends. |

The rest of the sidebar (above the Enter button) is **filters** — Segment · Order Status · Region ·
Market · Product Category · Currency · Reporting Period · Date Range. Set them, then press **↵ Enter**
to apply. **⬇ Download / Export** exports the current filtered view (CSV / Excel / PDF).

## Data & Security

**Model: code lives on GitHub, data stays on the local drive only.** The `database/` folder holds
real customer PII (phone numbers, IPs, user IDs) and must **never** be committed or pushed.

**The rules that enforce this:**

- `.gitignore` excludes `database/` and every data extension (`*.parquet`, `*.xlsx`, `*.xls`,
  `*.csv`, `*.db`, `*.sqlite*`), plus local config/secrets (`.env`, `local_config.py`, `secrets.toml`).
- A version-controlled **pre-commit hook** (`githooks/pre-commit`) hard-blocks any commit that stages
  a data file — including the `git add -f` case that `.gitignore` alone does not stop. Git hooks are
  not copied on clone, so each clone must enable it once:

  ```bash
  git config core.hooksPath githooks
  ```

  To verify it works, try `git add -f database/anything.csv && git commit -m test` — the commit
  should be rejected.

**Seeding the local `database/` after a fresh clone** (the folder is intentionally absent). The
dashboard reads `database/sales_cache.parquet` (rebuilt from rolling `Agent_Database.parquet` /
`Master_Database.parquet`). Populate it one of two ways:

- **Import Data tab** — upload the daily Agent (B2B) and Master (B2C) Excel exports; they append
  cumulatively (de-duped on order id). *Recommended for teammates on any machine.*
- **🔄 Rebuild Data Pipeline** / `python init_database.py` — rebuilds from the source
  `Agent Data.xlsx` / `Master Data.xlsx`. ⚠️ This currently reads a **hardcoded path** on the
  original machine
  (`C:\Disk\LiuLian Tech Sdn. Bhd\Report\Recon & Reverse Recon\Raw Data (30 Nov - 23 Mac)\…`).
  Teammates without that exact folder should use the **Import Data tab** instead.

The `database/` files are distributed through the company's internal channel only — **never** via
GitHub.

## Module map

| File | Role |
|------|------|
| `sales_dashboard.py` | Main app — all tabs, ~120 render functions, filter chain, CSS/JS |
| `db_utils.py` | Storage layer — rolling parquet stores, multi-sheet reader, dedup/append, cache rebuild |
| `clean_raw.py` | Raw daily-export cleaner + full rebuild from the `Data/` folders |
| `categories.py` | 6-class product-category taxonomy (raw `product_category` → class) |
| `charts.py` | Reusable Plotly chart builders (DRY factory) |
| `ip_geo.py` | Offline IP → state/province geolocation (DB-IP City Lite) for the failure map |
| `ml_predictions.py` | Revenue forecast, churn prediction, demand forecast |
| `theme.py` | Palette, Plotly theme, number formatting, country/region/currency maps |
| `translations.py` | EN ↔ 中文 dictionaries (headings + chart-phrase translator) |
| `country_mapping.py` · `fx_rates.py` | Country-name translation · currency conversion table |
| `pdf_export.py` · `generate_doc_pdf.py` | Per-tab report export · system documentation PDF |
| `remarks_utils.py` | Per-tab analyst remarks storage |
