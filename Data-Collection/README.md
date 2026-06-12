# Amman Stock Exchange (ASE) & MENA Markets Ingestion, ETL & Downstream Separation Pipeline

This repository hosts a multi-stage financial data engineering pipeline designed to ingest, clean, unify, and analyze transaction records for Jordan equities listed on the Amman Stock Exchange (ASE) along with other regional MENA markets (Saudi Arabia, Kuwait, Qatar, and Egypt).

The pipeline integrates bulk historical bulletins (2010–2025) with live daily automated updates from exchange servers (2026–Present) into a contiguous, contiguous timeline, with additional downstream scripts to generate standardized regional indices.

---

## 🔗 Google Drive Data Repositories
The processed datasets, including feature-engineered matrices and regional separation index files, are hosted on Google Drive:
*   [ASE & MENA Processed Datasets (Staging/Features)](https://drive.google.com/drive/folders/1dnKvzroe4-FZ2d9QeD7Frd0kQGvyE1z0?usp=sharing)
*   [MENA Downstream separation files](https://drive.google.com/drive/folders/1cFYB3oyoWtwZUpu7qgroWbOEBL1fCc8p?usp=drive_link)

---

## 📂 Directory Structure

The repository is structured logically by data engineering phases to separate concerns and ensure portability:

```text
├── .gitignore                          # Rules for Git (excludes local virtual env, logs, and generated files)
├── requirements.txt                    # Python dependencies
├── run_pipeline.bat                    # Master Windows automation runner (Scraping -> Unification -> Features)
├── pipeline_architecture.md            # Detailed processing phase details and master schemas reference
├── downloaded_files.json               # Registry tracking downloaded yearly source bulletins
│
├── 01_conversion/                      # PHASE 1: Raw Spreadsheet Ingestion
│   └── convert_to_csv.py               # Checks magic bytes and converts raw .xls/.xlsx to standard CSV
│
├── 02_consolidation/                   # PHASE 2: Ingestion & QA of Bulletins (2010–2025)
│   ├── combine_bulletins.py            # Combines yearly files and applies critical date corrections
│   └── audit_days_and_firms.py         # Diagnostic audit of dates and tickers against prices
│
├── 03_daily_scraping/                  # PHASE 3: Daily ASE Live Updates
│   └── download_and_process.py         # Scrapes company IDs, downloads live logs, and generates temp indicators
│
├── 04_unification/                     # PHASE 4: Multi-Era Schema Binding
│   └── unify_multi_era_data.py         # Merges bulletins with 2026 daily logs into a contiguous daily timeline
│
├── 05_feature_engineering/             # PHASE 5: Advanced Technical Features
│   └── generate_features.py            # Calculates RSI, MACD, VROC, stochastic oscillators, and spreads
│
├── legacy_pipeline/                    # Archive of legacy/deprecated scripts
│   ├── ase_data_pipeline_methodology.md
│   ├── ase_data_pipeline_methodology.docx
│   ├── download_and_process.py
│   ├── generate_combined.py
│   └── generate_methodology_docx.py
│
├── bulletin_staging/                   # Raw bulletins and spreadsheet conversion area (git-ignored raw data)
│   ├── raw/                            # Raw yearly source bulletins (.xls, .xlsx, .txt)
│   ├── raw_csv/                        # Standardized CP1256/UTF-8-sig CSV files per year
│   ├── raw_csv_structure_report.txt    # Audit report of column layouts across bulletins
│   └── combined_bulletins.csv          # Output of bulletins consolidation (Phase 2)
│
├── regional_markets/                   # Separation and aggregation scripts for regional indices
│   ├── Egypt.csv                       # Baseline regional index template
│   ├── Kuwait.csv                      # Baseline regional index template
│   ├── Qatar.csv                       # Baseline regional index template
│   ├── Saudi_Arabia.csv                # Baseline regional index template
│   ├── process_ase.py                  # Partitions the master ASE dataset into standard 14-column per-firm CSVs
│   ├── process_markets.py              # Downloads prices for Egypt, Kuwait, Qatar, and Saudi Arabia from yfinance
│   ├── process_mena.py                 # Compiles historical country datasets and index under MENA/
│   ├── Egypt/                          # [Git Ignored] Processed data for Egypt
│   ├── Kuwait/                         # [Git Ignored] Processed data for Kuwait
│   ├── Qatar/                          # [Git Ignored] Processed data for Qatar
│   ├── Saudi/                          # [Git Ignored] Processed data for Saudi
│   ├── Jordan/                         # [Git Ignored] Processed data for Jordan
│   ├── ASE/                            # [Git Ignored] Partitioned firm datasets for Jordan
│   └── MENA/                           # [Git Ignored] Consolidated index and aggregated datasets for MENA region
│
└── data/                               # Central output folder for unified datasets
    ├── combined_historical.csv         # Raw scraped 2026 daily logs
    ├── combined_historical_unified.csv # Unified master chronological ledger (2010-2026)
    ├── combined_historical_with_features.csv # Final feature-engineered dataset
    ├── sample_2025_jan_march.csv       # Q1 2025 baseline sample
    └── firms/                          # Subfolders for each ticker (e.g. APOT) containing individual datasets
```

---

## 📈 Final Files, Data Counts & Timestamps

Below is a detailed inventory of the final processed output files produced by the pipeline:

*   **Master Feature Dataset ([data/combined_historical_with_features.csv](file:///c:/Users/VICTUS/Desktop/Docs/ASE_collection/Data-Collection/data/combined_historical_with_features.csv))**: **78,050 rows** (26 columns) covering the contiguous daily timeframe from **2010-01-03** to **2026-06-11**.
*   **Jordan Partitions ([regional_markets/ASE/&lt;Ticker&gt;/&lt;Ticker&gt;.csv](file:///c:/Users/VICTUS/Desktop/Docs/ASE_collection/Data-Collection/regional_markets/ASE))**: **4,018 rows** per ticker (covering **2015-01-01** to **2025-12-31**).
*   **MENA Master Index ([regional_markets/MENA/MENA.csv](file:///c:/Users/VICTUS/Desktop/Docs/ASE_collection/Data-Collection/regional_markets/MENA/MENA.csv))**: **274,448 rows** (14 columns) covering exactly **4,036 contiguous days** per ticker from **2014-12-14** to **2025-12-31**.
*   **Country Aggregates (Egypt, Kuwait, Qatar, Saudi Arabia)**: Detailing row counts and date coverages:
    *   **Egypt**: `regional_markets/MENA/Egypt/csv/Egypt_combined.csv` (**60,540 rows** | 15 tickers | Range: `2014-12-14` to `2025-12-31`)
    *   **Kuwait**: `regional_markets/MENA/Kuwait/csv/Kuwait_combined.csv` (**52,468 rows** | 13 tickers | Range: `2014-12-14` to `2025-12-31`)
    *   **Qatar**: `regional_markets/MENA/Qatar/csv/Qatar_combined.csv` (**60,540 rows** | 15 tickers | Range: `2014-12-14` to `2025-12-31`)
    *   **Saudi Arabia**: `regional_markets/MENA/Saudi/csv/Saudi_combined.csv` (**100,900 rows** | 25 tickers | Range: `2014-12-14` to `2025-12-31`)

---

## 📊 Final 14-Column Schema Specification

All downstream separation files created under `regional_markets/ASE/` and `regional_markets/MENA/` are normalized into the following 14-column layout:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| **`date`** | `object` | Chronological session date (`YYYY-MM-DD`). |
| **`ticker`** | `object` | Unique equity ticker symbol (e.g., `APOT`, `COMI.CA`, `1120.SR`). |
| **`company_name`** | `object` | Descriptive name of the corporation. |
| **`open`** | `float64` | Opening session price. |
| **`high`** | `float64` | Maximum transaction price. |
| **`low`** | `float64` | Minimum transaction price. |
| **`close_price`** | `float64` | Closing session price. |
| **`volume`** | `float64` | Transactions volume in JOD (set to `0.0` on market-closed days). |
| **`return_value`** | `float64` | Log return of the closing price (set to `0.0` on market-closed days). |
| **`rsi_14`** | `float64` | 14-day Welles Wilder's Relative Strength Index (RSI). |
| **`macd_line`** | `float64` | Moving Average Convergence Divergence (MACD) Line value. |
| **`normalized_spread`**| `float64` | Intraday price volatility spread normalized by open: `(high - low) / open`. |
| **`vroc_5d`** | `float64` | 5-day Volume Rate of Change. |
| **`is_market_open`** | `Int64` | Binary status flag (`1` for active trading, `0` for closed days/weekends). |
