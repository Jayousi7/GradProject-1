# Amman Stock Exchange (ASE) Data Pipeline Architecture Reference

This document outlines the restructured, portable phase-based architecture of the Amman Stock Exchange (ASE) data collection and feature engineering pipeline.

---

## 📂 Restructured Directory Layout

The codebase is structured sequentially by data engineering phases to establish clear separation of concerns, improve legibility, and allow modular maintenance:

```text
├── .gitignore                          # Rules for Git (excludes large CSVs, venv, log files)
├── requirements.txt                    # Python dependencies
├── run_pipeline.bat                    # Master Windows automation runner (Scraping -> Unification -> Features)
├── pipeline_architecture.md            # [This File] Architecture and schema reference
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
├── legacy_pipeline/                    # Archive of legacy/deprecated scripts (column numbers removed)
│   ├── ase_data_pipeline_methodology.md
│   ├── ase_data_pipeline_methodology.docx
│   ├── download_and_process.py
│   ├── generate_combined.py            # Renamed from generate_combined_16col.py
│   └── generate_methodology_docx.py
│
├── bulletin_staging/                   # Raw inputs staging folder
│   ├── raw/                            # Yearly subfolders containing original bulletins (.xls, .xlsx, .txt)
│   ├── raw_csv/                        # Converted yearly CSVs
│   └── combined_bulletins.csv          # Output of Phase 2
│
├── regional_markets/                   # Downstream regional market outputs & separation scripts
│   ├── Egypt.csv                       # Market input template
│   ├── Kuwait.csv                      # Market input template
│   ├── Qatar.csv                       # Market input template
│   ├── Saudi_Arabia.csv                # Market input template
│   ├── process_ase.py                  # Downstream filtering/processing for ASE firms
│   ├── process_markets.py              # Download historical data for other regional markets
│   ├── process_mena.py                 # Combine all MENA country data into final datasets
│   ├── Egypt/                          # [Git Ignored] Local processed Egypt folder
│   ├── Kuwait/                         # [Git Ignored] Local processed Kuwait folder
│   ├── Qatar/                          # [Git Ignored] Local processed Qatar folder
│   ├── Saudi/                          # [Git Ignored] Local processed Saudi folder
│   ├── Jordan/                         # [Git Ignored] Local processed Jordan folder
│   ├── ASE/                            # [Git Ignored] Saved files per ASE firm (CSV/Parquet)
│   └── MENA/                           # [Git Ignored] Unified MENA dataset and country outputs
│
└── data/                               # Central output folder for unified datasets
    ├── combined_historical.csv         # Raw scraped 2026 daily logs
    ├── combined_historical_unified.csv # Unified master chronological ledger (2010-2026)
    ├── combined_historical_with_features.csv # Final feature-engineered dataset
    └── firms/                          # Subfolders for each ticker (e.g. APOT) containing individual datasets
```

---

## 🛠️ Data Pipeline Stages

### 1. Ingestion & Conversion (Phase 1)
*   **Module**: `01_conversion/convert_to_csv.py`
*   **Inputs**: `bulletin_staging/raw/<year>/`
*   **Outputs**: `bulletin_staging/raw_csv/<year>/`, `bulletin_staging/raw_csv_structure_report.txt`
*   **Operation**: Standardizes legacy binary Spreadsheets (`.xls`), zipped XMLs (`.xlsx`), and legacy TSVs. Uses cp1256 (Windows Arabic) encoding to parse Arabic company names without corruption, writing standard UTF-8-BOM CSVs.

### 2. Bulletins Consolidation & QA (Phase 2)
*   **Module**: `02_consolidation/combine_bulletins.py` and `audit_days_and_firms.py`
*   **Inputs**: `bulletin_staging/raw_csv/`
*   **Outputs**: `bulletin_staging/combined_bulletins.csv` / `.parquet`
*   **Operation**: Aggregates the 16 yearly normalized CSV files. It programmatically fixes the **2023–2025 "Swapped Days" corruption** where trading session days <= 12 had month and day fields swapped. Standardizes different column structures across years into a unified 16-column layout. Runs assertions to ensure zero data loss and check for chronological integrity.

### 3. Daily Web Scraping (Phase 3)
*   **Module**: `03_daily_scraping/download_and_process.py`
*   **Inputs**: Live ASE Web Server
*   **Outputs**: `data/combined_historical.csv` / `.parquet`, `data/firms/<ticker>/<ticker>_historical.csv`
*   **Operation**: Fetches live price history spreadsheet updates for the 13 equities directly from official ASE servers. Computes moving averages (SMAs, EMAs), MACD, and basic return statistics on the daily sheet.

### 4. Multi-Era Schema Binding (Phase 4)
*   **Module**: `04_unification/unify_multi_era_data.py`
*   **Inputs**: `bulletin_staging/combined_bulletins.csv`, `data/combined_historical.csv`
*   **Outputs**: `data/combined_historical_unified.csv` / `.parquet`, `data/firms/<ticker>/<ticker>_historical_unified.csv`
*   **Operation**: Connects bulletins (2010–2025) and daily scraped data (2026–Present). 
    *   *Metadata Lookup*: Since 2026 live sheets omit metadata (names, company codes, markets), the script extracts the most frequent historical values (mode) for each ticker from the bulletins to auto-populate the 2026 rows.
    *   *Symbol Unification*: Pre-2016 `LIPO` rows are automatically mapped under the modern symbol `ATCO` to create a single contiguous series.
    *   *Market-Closed Day Imputation*: Reindexes to include all calendar days, forward-filling values from the last active trading session, setting returns to zero, and flags closed days.

### 5. Advanced Feature Engineering (Phase 5)
*   **Module**: `05_feature_engineering/generate_features.py`
*   **Inputs**: `data/combined_historical_unified.csv`
*   **Outputs**: `data/combined_historical_with_features.csv` / `.parquet`
*   **Operation**: Generates 8 primary indicators: Stochastic %K & %D, Relative Strength Index (RSI_14), MACD Line & MACD Signal, Normalized Intraday Spread, Volume Rate of Change (VROC_5d), and Bollinger Band Width.

---

## 📊 Output Schema References

### Unified Master Schema (18 Core + 8 Engineered Columns)
The master unified outputs under `data/combined_historical_with_features.csv` contain **26 columns**:
1.  `trade_date` (Date)
2.  `name` (Arabic Company Name)
3.  `code` (Numeric Company Code)
4.  `symbol` (Ticker)
5.  `market` (Market Tier ID)
6.  `volume` (Transaction Financial Volume in JOD)
7.  `qty` (Total shares transacted)
8.  `no_of_trades` (Trade count)
9.  `high` (Maximum transaction price)
10. `low` (Minimum transaction price)
11. `open` (Opening session price; unrecorded daily rows set to `NaN`)
12. `close_price` (Closing session price)
13. `best_ask_price` (Set to `NaN` post-2026)
14. `best_ask_qty` (Set to `NaN` post-2026)
15. `best_bid_price` (Set to `NaN` post-2026)
16. `best_bid_qty` (Set to `NaN` post-2026)
17. `return_value` (Daily log return of closing prices)
18. `is_closed` (Binary flag: 1 for closed calendar sessions, 0 for active)
19. `vroc_5d` (5-day Volume Rate of Change)
20. `rsi_14` (14-day Relative Strength Index)
21. `stochastic_k` (Stochastic Oscillator %K)
22. `stochastic_d` (Stochastic Oscillator %D)
23. `macd_line` (MACD Line)
24. `macd_signal` (MACD Signal)
25. `normalized_spread` (High-Low spread normalized by close price)
26. `bollinger_width` (Bollinger Band Width)

---

### Final Clean Dataset Schema (14 Standard Columns)
For downstream modeling, separation scripts (like `regional_markets/process_ase.py` and `regional_markets/process_mena.py`), and regional aggregates, the data is standardized into the following **14 columns**:

| Column Name | Type | Description |
| :--- | :--- | :--- |
| **`date`** | `object` | Chronological session date (`YYYY-MM-DD`). |
| **`ticker`** | `object` | Unique symbol identifying the equity (e.g. `APOT`). |
| **`company_name`** | `object` | Descriptive company name. |
| **`open`** | `float64` | Opening session price (properly handled/imputed). |
| **`high`** | `float64` | Maximum session price. |
| **`low`** | `float64` | Minimum session price. |
| **`close_price`** | `float64` | Closing session price. |
| **`volume`** | `float64` | Sessions transacted volume (0.0 on closed days). |
| **`return_value`** | `float64` | Log returns of the closing prices (0.0 on closed days). |
| **`rsi_14`** | `float64` | 14-day Welles Wilder's Relative Strength Index. |
| **`macd_line`** | `float64` | MACD Line value. |
| **`normalized_spread`**| `float64` | High-Low Spread normalized by open: `(high - low) / open`. |
| **`vroc_5d`** | `float64` | 5-day Volume Rate of Change. |
| **`is_market_open`** | `Int64` | Binary status flag (1 for active trading, 0 for closed days). |
