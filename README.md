# Comprehensive Dashboard — Global Mobile Recharge Revenue Intelligence

A 10-tab business-intelligence web app (Shiny for Python) for a global mobile-recharge
platform, covering revenue (GMV), order quality, markets, suppliers/operators, products &
denominations, customers, marketing, AI forecasts, and an ad-hoc Sales Explorer. Bilingual
(English / 中文).

> **Note:** the real order data (`database/`) and the Python virtualenv (`sales_env/`) are
> intentionally **not** committed — the data contains customer PII (phone numbers, IPs, user IDs)
> and the venv is large/machine-specific. See **Data** below.

## Tabs

Executive Overview · Performance Comparison · Revenue & Orders · Market Intelligence ·
Operational Intelligence · Supplier & Operator Performance · Product & Denomination Analysis ·
Customer Analytics · Marketing & Promotions · ⏱ Sales Explorer · 🤖 AI Predictions

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
| `db_utils.py` | Storage layer — rolling parquet stores, dedup/append, cache rebuild, import validation |
| `ml_predictions.py` | Revenue forecast, churn prediction, demand forecast |
| `theme.py` | Palette, Plotly theme, number formatting, country/region/currency maps |
| `translations.py` | EN ↔ 中文 dictionaries (headings + chart-phrase translator) |
| `country_mapping.py` · `fx_rates.py` | Country-name translation · currency conversion table |
| `pdf_export.py` · `generate_doc_pdf.py` | Per-tab report export · system documentation PDF |
| `remarks_utils.py` | Per-tab analyst remarks storage |
