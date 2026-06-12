# Amman Stock Exchange (ASE) Dataset Documentation

This directory contains the cleaned, processed, and contiguous daily historical stock market dataset for **13 major companies** listed on the **Amman Stock Exchange (ASE)** in Jordan. The dataset spans over 11 years (from 2015 to 2025) and is organized by company ticker.

---

## 1. Region and Market Context

* **Exchange:** Amman Stock Exchange (ASE) - بورصة عمان
* **Location:** Amman, Jordan
* **Country:** Jordan (الأردن)
* **Currency:** Jordanian Dinar (JOD)
* **Trading Days:** Typically Sunday through Thursday (Friday and Saturday are weekends, and the market is closed on national and religious holidays).

---

## 2. Firms Mentioned in the Dataset

The dataset covers **13 leading firms** across various sectors of the Jordanian economy (financial, industrial, energy, utilities, and education). 

| Ticker | Company Name (Arabic) | Company Name (English) | Core Sector / Business Description |
| :--- | :--- | :--- | :--- |
| **APOT** | البوتاس العربية | Arab Potash Company | One of the world's largest potash producers and fertilizer exporters. |
| **ARBK** | البنك العربي | Arab Bank | One of the largest financial institutions in the Middle East. |
| **ATCO** | انجاز للتنمية والمشاريع المتعددة | Injaz for Development & Multi Projects | Multi-sector development, real estate, and investment projects. |
| **DADI** | دار الدواء للتنمية والاستثمار | Dar Al Dawa Development & Investment | A leading manufacturer of generic pharmaceuticals and health products. |
| **IREL** | كهرباء محافظة اربد | Irbid District Electricity Company (IDECO) | The main power distribution company for northern Jordan. |
| **JOEP** | الكهرباء الاردنية | Jordan Electric Power Company (JEPCO) | The main power distribution company for central Jordan. |
| **JOPH** | مناجم الفوسفات الاردنية | Jordan Phosphate Mines Company | A global mining giant specializing in phosphate rock and phosphate fertilizers. |
| **JOPT** | مصفاة البترول الأردنية /جوبترول | Jordan Petroleum Refinery Co. (JoPetrol) | The sole petroleum refiner in Jordan, including downstream fuel distribution. |
| **JTEL** | الاتصالات الأردنية | Jordan Telecom Group (Orange Jordan) | The primary telecommunications provider, operating under the Orange brand. |
| **MANE** | آفاق للطاقة | Afaq for Energy Company | A holding company focusing on energy investments and fuel distribution (Manaseer Group). |
| **PEDC** | البتراء للتعليم | Petra Education Company | Owner and operator of the University of Petra (جامعة البتراء). |
| **RMCC** | الباطون الجاهز والتوريدات الانشائية | Ready Mix Concrete & Construction Supplies | Major supplier of building materials and ready-mix concrete in Jordan. |
| **UBSI** | بنك الإتحاد | Bank al Etihad (Union Bank) | A prominent corporate and retail banking group in Jordan. |

---

## 3. Columns and Data Values

Each company file (e.g., `ASE/ARBK/ARBK.csv`) contains daily data with the following schema:

| Column Name | Data Type | Description & Calculations | Example Value |
| :--- | :--- | :--- | :--- |
| **`Date`** | String | The calendar date of the record. Format: `YYYY-MM-DD`. | `2015-01-04` |
| **`Ticker`** | String | The unique stock symbol identifier of the company. | `ARBK` |
| **`Company`** | String | The official name of the company in Arabic script. | `البنك العربي` |
| **`Return`** | Float | Daily log returns of the closing price: $\ln(Close_t / Close_{t-1})$. Closed days are set to `0.0`. | `-0.011331` |
| **`RSI`** | Float | 14-day Welles Wilder Relative Strength Index (momentum indicator, ranges from `0` to `100`). | `69.767442` |
| **`MACD`** | Float | Moving Average Convergence Divergence line: $12\text{-day EMA} - 26\text{-day EMA}$ of Close. | `0.043773` |
| **`Spread`** | Float | Normalized intraday price spread, calculated as: $\frac{\text{High} - \text{Low}}{\text{Close}}$ | `0.011396` |
| **`VROC`** | Float | Volume Rate of Change over a 5-day lookback: $\frac{Volume_t - Volume_{t-5}}{Volume_{t-5}}$ | `-0.792059` |
| **`Is_Market_Open`** | Integer | Binary flag: `1` if the market was open and trading occurred; `0` if the market was closed. | `1` |
| **`is_closed`** | Integer | Binary flag: `1` if the market was closed (weekends, holidays); `0` if open ($1 - Is\_Market\_Open$). | `0` |

---

## 4. Timestamps & Temporal Integrity

* **Contiguous Daily Coverage:** The data is represented as a contiguous daily calendar series.
* **Leakage Prevention:** 
  - Technical indicators (RSI, MACD, Spread, VROC) are computed on the sequence of open trading days.
  - The calculated values are forward-filled (`ffill`) onto closed days (weekends/holidays) so that indicators reflect the last known trading information.
  - On days when the market is closed (`is_closed = 1`), the daily **`Return`** is explicitly overridden to `0.0` to prevent forward data leakage.
  - If a firm was listed after the starting date, all price data and indicators are set to `0.0` prior to its listing/IPO date to prevent data leakage.

---

## 5. Dataset Split & Structure

The dataset in the workspace is structured and split as follows:

```
WORKSPACE/
├── combined_historical_with_features.csv  <- Master raw historical Jordan file (2010-01-03 to 2025-04-01)
├── sample_2025_jan_march.csv              <- Raw subset containing Q1 2025 Jordan data
├── Jordan/                                <- Sliced evaluation split for Jordan (2025-01-01 to 2025-04-01)
│   ├── APOT.csv                           <- Individual files with a wide feature set 
│   ├── ARBK.csv                              (e.g., stochastics, Bollinger Bands, ask/bid data)
│   └── ... 
└── ASE/                                   <- Long-term processed daily dataset (2015-01-01 to 2025-12-31)
    ├── README.md                          <- This documentation file
    ├── APOT/
    │   ├── APOT.csv                       <- Long-term CSV dataset (4,018 rows)
    │   └── APOT.parquet                   <- Column-oriented Parquet format
    ├── ARBK/
    │   ├── ARBK.csv
    │   └── ARBK.parquet
    └── ...
```

### Key Splits:
1. **Long-Term Training & Backtesting Dataset (`ASE/`)**:
   - **Date Range:** **2015-01-01 to 2025-12-31** (4,018 calendar days per ticker).
   - **Features:** Cleaned and structured to 10 core columns (`Date`, `Ticker`, `Company`, `Return`, `RSI`, `MACD`, `Spread`, `VROC`, `Is_Market_Open`, `is_closed`).
   - **Formats:** Available in both CSV (UTF-8) and compressed, high-performance Parquet format.
2. **Evaluation & Recent Test Dataset (`Jordan/`)**:
   - **Date Range:** **2025-01-01 to 2025-04-01** (91 calendar days per ticker).
   - **Features:** Retains 26 technical and market depth features (including `stochastic_k`, `stochastic_d`, `bollinger_width`, `macd_signal`, and bid-ask queue data like `best_ask_price`, `best_bid_price`, etc.).
