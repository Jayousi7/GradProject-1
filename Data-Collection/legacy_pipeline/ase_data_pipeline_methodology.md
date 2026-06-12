# Amman Stock Exchange (ASE) Multi-Era Financial Data Ingestion & ETL Pipeline Methodology
### End-to-End Pipeline Documentation: From Raw Excel Bulletins & Live Scraped daily exports to the Unified Consolidated Master File (2010–2026)

This document provides a highly technical, comprehensive walkthrough of the financial data engineering pipeline developed to compile, clean, validate, and unify the multi-era transaction database of the **Amman Stock Exchange (ASE)**. 

The pipeline seamlessly bridges **16 years of historical trading** (from January 3, 2010, to June 1st, 2026) for **8 critical Jordanian equities**, integrating two fundamentally different data sources and schemas into a single, standardized, 16-column chronological ledger: **`combined_historical.csv`**.

---

## 1. End-to-End Architectural Pipeline Overview

The data pipeline runs through a multi-stage ingestion, transformation, validation, and merging architecture implemented across four distinct scripts: `convert_to_csv.py`, `combine_bulletins.py`, `download_and_process.py`, and `generate_combined.py`.

```mermaid
graph TD
    %% Era 1 Input (2010-2025)
    subgraph Era 1: Bulk Ingestion (2010-2025)
        A[Raw Yearly Bulletins .xls / .xlsx / .txt] -->|cp1256 Ingestion| B(Stage 1: Excel-to-CSV Conversion)
        B -->|utf-8-sig CSVs| C{Stage 2: Master Consolidation}
        C -->|1. Date Swapped Fix| D[Date-Normalized DataFrame]
        C -->|2. Column Schema Alignment| D
        C -->|3. Type-Casting & Stripping| D
        D -->|4. Strict Invariant Assertions| E[combined_bulletins.csv 16 Columns]
    end

    %% Era 2 Input (2026-Present)
    subgraph Era 2: Daily Live Automation (2026-Present)
        F[ASE Web Server] -->|Live Scrape & ID Lookup| G(Stage 3: Local daily Scraper)
        G -->|xlsx Download| H[daily Raw Data 7 Columns]
        H -->|Clean & Map| I[generate_combined.py]
    end

    %% Schema Binding & Output
    subgraph Consolidation & Binding (Stage 4)
        E -->|Pre-2026 Bulletins Ingestion| I
        I -->|1. Extract Ticker Metadata Mappings| K[Metadata Dictionaries]
        I -->|2. Ticker Unification: LIPO to ATCO| L[Contiguous Ticker Arrays]
        I -->|3. 7-to-16 Column Schema Mapping| M[Formatted Dataframes]
        K & L & M -->|Chronological Sort| N[combined_historical.csv 16 Columns]
        N -->|Dual Exports| O[Individual Ticker CSVs]
        N -->|Dual Exports| P[Master Consolidated CSV]
    end

    style B fill:#f9f,stroke:#333,stroke-width:2px
    style C fill:#bbf,stroke:#333,stroke-width:2px
    style G fill:#fbf,stroke:#333,stroke-width:2px
    style I fill:#f96,stroke:#333,stroke-width:2px
    style N fill:#9f9,stroke:#333,stroke-width:2px
```

---

## 2. Phase 1: Excel-to-CSV Conversion (`convert_to_csv.py`)

The historical bulletins raw data is published by the ASE in multiple heterogeneous file formats including legacy OLE2 binary spreadsheets (`.xls`), zipped XML spreadsheets (`.xlsx`), and plain text tab-separated values (`.txt` TSV). The script **`convert_to_csv.py`** standardizes this raw layer:

1.  **Format Signature Inspection**: Instead of relying on unreliable file extensions, the script reads the first **8 magic bytes** of the files:
    *   `\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1` identifies OLE2 binary formats (`.xls`).
    *   `PK\x03\x04` identifies zipped OpenXML formats (`.xlsx`).
    *   If no signature matches, the system falls back to text parsing.
2.  **Sheet Selection and Filtering Logic**: Raw spreadsheets contain decorative tabs, blank sheets, and summaries. The script dynamically walks through the sheets, calculates their non-null density, and parses the first tab containing populated tabular data structures.
3.  **Arabic Text Encoding**: Reading legacy text TSV sheets (specifically in 2010, 2012, 2015, and 2016) requires applying explicit **`cp1256` (Windows Arabic)** encoding parameters to prevent string corruption of Arabic company names during parsing.
4.  **Target Output Standard**: The script converts all raw worksheets and outputs them to `bulletin_staging/raw_csv/<year>/` encoded in **`utf-8-sig` (UTF-8 with Byte Order Mark)**. This ensures that Arabic characters render seamlessly across Python libraries, text editors, and Microsoft Excel.

---

## 3. Phase 2: Master Ingestion & QA of Bulletins (`combine_bulletins.py` $\rightarrow$ `combined_bulletins.csv`)

The script **`combine_bulletins.py`** reads the 16 normalized yearly files from Stage 1 to compile the consolidated master database. It performs critical transformations to resolve systemic exchange recording errors:

### A. Date Normalization & The 2023–2025 "Swapped Days" Corruption
In the raw exchange bulletins for the years **2023, 2024, and 2025**, the export engine had a critical date corruption issue. For any trading session where the day of the month was **12 or less** (e.g., March 5th), the system incorrectly swapped the day and month fields (saving it as `2023-05-03` instead of `2023-03-05`). Dates after the 12th of the month were saved correctly in the European `DD-MM-YYYY` layout.

*   **Programmatic Correction (`parse_corrupted_dates`)**: 
    The pipeline resolves this by applying a targeted date parser. When a date falls on a day $\le 12$, it splits the date string, isolates the month and day integers, and programmatically swaps them back:
    $$\text{Corrected Date} = \text{Timestamp}(\text{Year}=Y, \text{Month}=\text{Raw Day}, \text{Day}=\text{Raw Month})$$
*   All other standard historical dates are parsed using the explicit parameter `dayfirst=True` to guarantee standard chronological alignment.

### B. Column Schema Standardization
The raw bulletin columns underwent structural updates over the years. The ETL engine maps these yearly variations into a unified schema:
*   **2012 bulletins**: standardizes variations like `trading_date` and `OPEN_PRICE`.
*   **2021–2022 bulletins**: standardizes variations like `SEC_CODE` $\rightarrow$ `code`, `SEC_NAME1` $\rightarrow$ `name`, `SYMBOL1` $\rightarrow$ `symbol`, `TRADE_QTY` $\rightarrow$ `qty`, and `OPEN_PRICE` $\rightarrow$ `open`.

### C. Strict Null Truncation and Type Casting
*   Text fields (`name`, `symbol`) are stripped of empty padding and normalized to upper case.
*   Numeric fields (`code`, `market`, `qty`, `no_of_trades`) are cast to integers using pandas nullable **`Int64`** type, which prevents decimal/float conversion of missing columns.
*   Prices and volumes are cast to double-precision 64-bit floats (`float64`).

### D. Quality Assurance Assertion Invariants
Before writing `combined_bulletins.csv`, the script validates the output using a defensive testing suite:
1.  **Row Count Check**: Assures that the sum of the processed records matches the sum of the raw files exactly (zero data loss).
2.  **Schema Check**: Assures that the output contains exactly the 16 standardized columns.
3.  **Monotonicity Check**: Validates that dates are strictly increasing.
4.  **Null Check**: Assures that critical indexing columns (`trade_date`, `name`, `code`, `symbol`) contain **exactly zero null records**.

---

## 4. Phase 3: Live Daily Scraping & Local Device Automation (`download_and_process.py` & `run_pipeline.bat`)

To keep the dataset updated, an automated pipeline executes **directly on your local device**:

1.  **Company Export ID Lookup**: The script **`download_and_process.py`** parses the ASE company historical webpage `https://www.ase.com.jo/en/company_historical/{ticker}` and extracts the company ID from the HTML using regular expressions:
    ```regex
    daily-historical-export/(\d+)
    ```
2.  **Spreadsheet Downloader**: Initiates programmatics HTTP requests to download the official live Excel sheet:
    `https://ase.com.jo/en/daily-historical-export/{company_id}?_format=xlsx`
    This query dynamically pulls all daily listings up to the absolute current minute of execution.
3.  **Windows Launcher Pipeline (`run_pipeline.bat`)**: The entire extraction is launched via a local Windows batch script `run_pipeline.bat` which handles directory initialization, downloads raw spreadsheets, standardizes dates, and immediately launches `generate_combined.py` to seamlessly append the new rows.

---

## 5. Phase 4: Multi-Era Schema Binding (`generate_combined.py` $\rightarrow$ `combined_historical.csv`)

This is the crowning stage of the data engineering pipeline. The script **`generate_combined.py`** integrates the rich bulletin data (2010–2025) with the latest 2026 daily logs to generate a standardized, unified chronological dataset.

### A. Metadata Extraction & Cross-Referencing
Since starting from **2026** the daily sheets do not record company metadata (Arabic Names, Numeric Codes, and Market classification), the script dynamically parses the pre-2026 bulletins to extract the most common metadata values for each symbol:
*   *Arabic Name* $\rightarrow$ Mode of `name`
*   *Company Code* $\rightarrow$ Mode of `code`
*   *Market Tier* $\rightarrow$ Mode of `market`

These values are mapped into dictionaries and used to auto-populate the 2026 daily records.

### B. The LIPO to ATCO Ticker Unification
Prior to **2016-01-03**, the company **انجاز للتنمية والمشاريع المتعددة** (Code `141058`) was traded under the symbol **LIPO**. On **2016-01-03**, the ticker was updated to **ATCO**.
To reconstruct a complete history starting from 2010, the pipeline:
1.  Ingests both `LIPO` and `ATCO` records from the bulletins.
2.  Unifies them under the single symbol **`ATCO`**.
3.  Concatenates the pre-2016 `LIPO` series with the post-2016 `ATCO` series, creating a seamless chronological record from 2010.

### C. Technical 7-to-16 Schema Mapping
The 2026 daily logs (containing 7 standard columns) are mapped into the 16-column bulletins layout. Columns that are no longer recorded are set to `NaN`:

| Target 16-Column Name | Source 2026 Column | Population / Lookup Strategy |
| :--- | :--- | :--- |
| **`trade_date`** | `date` | Direct map |
| **`name`** | *None* | Looks up Arabic Name from bulletins mapping |
| **`code`** | *None* | Looks up Numeric Code from bulletins mapping |
| **`symbol`** | `symbol` | Direct map |
| **`market`** | *None* | Looks up Market Tier from bulletins mapping |
| **`volume`** | `value_traded` | Direct map (Local value traded in JOD) |
| **`qty`** | `no_of_shares` | Direct map (Total shares transacted) |
| **`no_of_trades`** | `no_of_trades` | Direct map |
| **`high`** | `high` | Direct map |
| **`low`** | `low` | Direct map |
| **`open`** | *None* | Set to `NaN` (unrecorded in 2026) |
| **`close_price`** | `close` | Direct map |
| **`best_ask_price`** | *None* | Set to `NaN` (unrecorded in 2026) |
| **`best_ask_qty`** | *None* | Set to `NaN` (unrecorded in 2026) |
| **`best_bid_price`** | *None* | Set to `NaN` (unrecorded in 2026) |
| **`best_bid_qty`** | *None* | Set to `NaN` (unrecorded in 2026) |

---

## 6. Output Files and Verification Summary

The pipeline completes by writing the unified outputs, sorted chronologically ascending by Date and Symbol:

1.  **Consolidated Master File**:
    *   Path: `combined_historical.csv`
    *   Shape: `(29247, 16)`
    *   Date Range: `2010-01-03` to `2026-06-01`
2.  **Individual Ticker CSVs** (saved under `firms/<symbol>/`):
    *   **ARBK**: `ARBK_historical.csv`
    *   **JOPT**: `JOPT_historical.csv`
    *   **JOEP**: `JOEP_historical.csv`
    *   **JOPH**: `JOPH_historical.csv`
    *   **UBSI**: `UBSI_historical.csv`
    *   **APOT**: `APOT_historical.csv`
    *   **RMCC**: `RMCC_historical.csv`
    *   **ATCO**: `ATCO_historical.csv`
