import os
import sys
import pandas as pd
import numpy as np

# Set stdout to UTF-8
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

combined_path = os.path.join(PROJECT_ROOT, "bulletin_staging", "combined_bulletins.csv")

if not os.path.exists(combined_path):
    print(f"ERROR: Combined bulletins not found at '{combined_path}'! Run combine_bulletins.py first.")
    sys.exit(1)

# Load combined bulletins
print("Loading combined bulletins...")
df_bull = pd.read_csv(combined_path)
df_bull['trade_date'] = pd.to_datetime(df_bull['trade_date']).dt.strftime('%Y-%m-%d')
print(f"Loaded bulletins: {len(df_bull)} rows.")

# File patterns for closing prices (under bulletin_staging/raw_csv/)
price_files = {
    2010: "bulletin_staging/raw_csv/2010/prices_2010_0.csv",
    2011: "bulletin_staging/raw_csv/2011/Prices_2011_0.csv",
    2012: "bulletin_staging/raw_csv/2012/prices 2012_0_0.csv",
    2013: "bulletin_staging/raw_csv/2013/Prices 2013_1_0.csv",
    2014: "bulletin_staging/raw_csv/2014/Prices_2014_0.csv",
    2015: "bulletin_staging/raw_csv/2015/Prices_2015_0.csv",
    2016: "bulletin_staging/raw_csv/2016/Prices_2016_0.csv",
    2017: "bulletin_staging/raw_csv/2017/Prices_2017.csv",
    2018: "bulletin_staging/raw_csv/2018/closing_prices_2018.csv",
    2019: "bulletin_staging/raw_csv/2019/closing_prices_2019.csv",
    2020: "bulletin_staging/raw_csv/2020/closing_prices_2020.csv",
    2021: "bulletin_staging/raw_csv/2021/closing_prices_2021_0.csv",
    2022: "bulletin_staging/raw_csv/2022/closing_prices_2022_0.csv",
    2023: "bulletin_staging/raw_csv/2023/closing_prices_2023_0.csv",
    2024: "bulletin_staging/raw_csv/2024/closing_prices_2024.csv",
    2025: "bulletin_staging/raw_csv/2025/closing_prices_2025.csv",
    2026: "bulletin_staging/raw_csv/2026/closing_prices_2026.csv",
}

audit_summary = []

for year in sorted(price_files.keys()):
    rel_path = price_files[year]
    csv_path = os.path.join(PROJECT_ROOT, rel_path)
    
    print(f"\n--- Auditing Year {year} ---")
    if not os.path.exists(csv_path):
        print(f"  Prices CSV file not found at: {csv_path}")
        continue
        
    df_price = pd.read_csv(csv_path)
    
    # Extract Bulletin unique dates and firms for this year
    # Note: Year 2026 is only in prices, not in bulletins
    bulletin_year_dates = set(df_bull[pd.to_datetime(df_bull['trade_date']).dt.year == year]['trade_date'].unique())
    bulletin_year_firms = set(df_bull[pd.to_datetime(df_bull['trade_date']).dt.year == year]['code'].dropna().unique())
    
    # Parse dates and firms from Prices CSV
    price_year_dates = []
    price_year_firms = []
    
    if year <= 2017:
        # Dates are in Row 0 starting from Col 2 (for 2010, 2011) or Col 3 (for 2012-2017)
        start_col = 2 if year in [2010, 2011] else 3
        
        # Get raw date strings from Row 0
        raw_dates = list(df_price.iloc[0, start_col:].values)
        # Parse them standardly as day-first (since they are in DD-MM-YYYY or D-M-YYYY)
        parsed_dates = pd.to_datetime(raw_dates, dayfirst=True, errors='coerce')
        price_year_dates = list(parsed_dates.dropna().strftime('%Y-%m-%d'))
        
        # Firms are in Row 3 onwards
        code_col_idx = 1 if year in [2016, 2017] else 0
        raw_codes = df_price.iloc[3:, code_col_idx].dropna()
        # Convert codes to integers
        price_year_firms = list(pd.to_numeric(raw_codes, errors='coerce').dropna().astype(int).unique())
    else:
        # For years 2018-2026: columns 3 onwards are standard YYYY-MM-DD dates
        raw_dates = list(df_price.columns[3:])
        # Direct parsing
        parsed_dates = pd.to_datetime(raw_dates, errors='coerce')
        price_year_dates = list(parsed_dates.dropna().strftime('%Y-%m-%d'))
        
        # Firms are in 'Code' column (which is Column 1)
        if 'Code' in df_price.columns:
            raw_codes = df_price['Code'].dropna()
        elif 'code' in df_price.columns:
            raw_codes = df_price['code'].dropna()
        else:
            raw_codes = df_price.iloc[:, 1].dropna()
            
        price_year_firms = list(pd.to_numeric(raw_codes, errors='coerce').dropna().astype(int).unique())
        
    price_dates_set = set(price_year_dates)
    price_firms_set = set(price_year_firms)
    
    print(f"  Bulletins: Dates={len(bulletin_year_dates)}, Firms={len(bulletin_year_firms)}")
    print(f"  Prices:    Dates={len(price_dates_set)}, Firms={len(price_firms_set)}")
    
    # 1. Compare Dates
    only_in_bulletins_dates = bulletin_year_dates - price_dates_set
    only_in_prices_dates = price_dates_set - bulletin_year_dates
    common_dates = bulletin_year_dates & price_dates_set
    
    print(f"  [Date Comparison]:")
    print(f"    Common Dates:                  {len(common_dates)}")
    if only_in_bulletins_dates:
        print(f"    Only in Bulletins ({len(only_in_bulletins_dates)}): {sorted(list(only_in_bulletins_dates))[:5]} ...")
    if only_in_prices_dates:
        print(f"    Only in Prices ({len(only_in_prices_dates)}):    {sorted(list(only_in_prices_dates))[:5]} ...")
        
    # 2. Compare Firms
    only_in_bulletins_firms = bulletin_year_firms - price_firms_set
    only_in_prices_firms = price_firms_set - bulletin_year_firms
    common_firms = bulletin_year_firms & price_firms_set
    
    print(f"  [Firm Comparison]:")
    print(f"    Common Firms (Codes):          {len(common_firms)}")
    if only_in_bulletins_firms:
        print(f"    Only in Bulletins ({len(only_in_bulletins_firms)}): {sorted(list(only_in_bulletins_firms))[:5]} ...")
    if only_in_prices_firms:
        print(f"    Only in Prices ({len(only_in_prices_firms)}):    {sorted(list(only_in_prices_firms))[:5]} ...")
        
    audit_summary.append({
        "year": year,
        "bull_dates": len(bulletin_year_dates),
        "price_dates": len(price_dates_set),
        "common_dates": len(common_dates),
        "only_bull_dates": len(only_in_bulletins_dates),
        "only_price_dates": len(only_in_prices_dates),
        "bull_firms": len(bulletin_year_firms),
        "price_firms": len(price_firms_set),
        "common_firms": len(common_firms),
        "only_bull_firms": len(only_in_bulletins_firms),
        "only_price_firms": len(only_in_prices_firms),
    })

print("\n" + "="*80)
print("                           SUMMARY OF MAPPING OVER YEARS")
print("="*80)
summary_df = pd.DataFrame(audit_summary)
print(summary_df.to_string(index=False))
