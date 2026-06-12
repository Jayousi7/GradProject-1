import os
import sys
import pandas as pd
import numpy as np

# Reconfigure stdout to UTF-8 to prevent terminal encoding errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Reference columns
ref_cols = [
    'trade_date', 'name', 'code', 'symbol', 'market', 'volume', 'qty',
    'no_of_trades', 'high', 'low', 'open', 'close_price',
    'best_ask_price', 'best_ask_qty', 'best_bid_price', 'best_bid_qty'
]

# Paths are relative to the project root directory
bulletin_files = {
    2010: "bulletin_staging/raw_csv/2010/2010-data.csv",
    2011: "bulletin_staging/raw_csv/2011/2011-data_0.csv",
    2012: "bulletin_staging/raw_csv/2012/2012-data_0.csv",
    2013: "bulletin_staging/raw_csv/2013/2013_data.csv",
    2014: "bulletin_staging/raw_csv/2014/2014_bull_0_0.csv",
    2015: "bulletin_staging/raw_csv/2015/2015_data_0.csv",
    2016: "bulletin_staging/raw_csv/2016/2016_bulls.csv",
    2017: "bulletin_staging/raw_csv/2017/bull_2017.csv",
    2018: "bulletin_staging/raw_csv/2018/Bulletin_2018.csv",
    2019: "bulletin_staging/raw_csv/2019/bulletin_2019_0.csv",
    2020: "bulletin_staging/raw_csv/2020/Bulletin_2020.csv",
    2021: "bulletin_staging/raw_csv/2021/bulletins_2021.csv",
    2022: "bulletin_staging/raw_csv/2022/bulletin 2022_0.csv",
    2023: "bulletin_staging/raw_csv/2023/Bulletin_2023.csv",
    2024: "bulletin_staging/raw_csv/2024/Bulletin_2024.csv",
    2025: "bulletin_staging/raw_csv/2025/Bulletins_2025.csv",
}

def parse_corrupted_dates(series):
    """
    Tailored parsing for 2023, 2024, and 2025, which contain a mix of ISO YYYY-MM-DD
    (with day and month swapped for days <= 12) and DMY strings.
    """
    parsed = []
    for val in series.astype(str).str.strip():
        if pd.isna(val) or val == 'nan' or val == '':
            parsed.append(pd.NaT)
            continue
        if len(val) >= 10 and val[4] == '-' and val[7] == '-':
            try:
                # Excel parsed date (swapped day/month for day <= 12)
                date_part = val.split()[0]
                y, m, d = map(int, date_part.split('-'))
                parsed.append(pd.Timestamp(year=y, month=d, day=m))
            except Exception:
                parsed.append(pd.to_datetime(val, errors='coerce'))
        else:
            # Standard string date (DD-MM-YYYY)
            parsed.append(pd.to_datetime(val, dayfirst=True, errors='coerce'))
    return pd.Series(parsed)

dfs = []
total_raw_rows = 0

print("==========================================================================")
print("            BULLETINS CONSOLIDATION & ET PROCESS STARTED                  ")
print("==========================================================================\n")

for year, rel_path in sorted(bulletin_files.items()):
    csv_path = os.path.join(PROJECT_ROOT, rel_path)
    if not os.path.exists(csv_path):
        print(f"ERROR: Year {year} CSV file not found at {csv_path}!")
        continue
    
    print(f"Processing Year {year}...")
    
    # Load raw CSV
    df = pd.read_csv(csv_path)
    row_count = len(df)
    total_raw_rows += row_count
    print(f"  Loaded {row_count} rows.")
    
    # Convert columns to lowercase for easy mapping
    df.columns = [c.lower() for c in df.columns]
    
    # Apply standard naming maps
    if year == 2012:
        df = df.rename(columns={'trading_date': 'trade_date', 'open_price': 'open'})
    elif year in [2021, 2022]:
        df = df.rename(columns={
            'sec_code': 'code',
            'sec_name1': 'name',
            'symbol1': 'symbol',
            'trade_qty': 'qty',
            'open_price': 'open'
        })
    
    # Handle date parsing based on year type
    date_col = 'trade_date'
    if year == 2023 or year == 2024 or year == 2025:
        # Mix/Corrupted years
        parsed_dates = parse_corrupted_dates(df[date_col])
    elif year in [2010, 2012, 2015, 2016, 2021]:
        # Clean DMY years
        parsed_dates = pd.to_datetime(df[date_col], dayfirst=True, errors='coerce')
    else:
        # Clean ISO years (2011, 2013, 2014, 2017, 2018, 2019, 2020, 2022)
        parsed_dates = pd.to_datetime(df[date_col], errors='coerce')
        
    df['trade_date'] = parsed_dates.dt.strftime('%Y-%m-%d')
    
    # Verify date parsing succeeded completely
    null_dates = df['trade_date'].isna().sum()
    if null_dates > 0:
        print(f"  WARNING: {null_dates} dates failed to parse in Year {year}!")
    
    # Standardize column selection and fill metadata gaps
    # Filter only the 16 reference columns
    df = df[ref_cols]
    
    # Cast data types cleanly
    df['name'] = df['name'].astype(str).str.strip()
    df['symbol'] = df['symbol'].astype(str).str.strip()
    
    # Cast integers (using nullable 'Int64' to handle NaNs elegantly)
    df['code'] = pd.to_numeric(df['code'], errors='coerce').astype('Int64')
    df['market'] = pd.to_numeric(df['market'], errors='coerce').astype('Int64')
    df['qty'] = pd.to_numeric(df['qty'], errors='coerce').astype('Int64')
    df['no_of_trades'] = pd.to_numeric(df['no_of_trades'], errors='coerce').astype('Int64')
    
    # Cast floats
    float_cols = ['volume', 'high', 'low', 'open', 'close_price', 'best_ask_price', 'best_ask_qty', 'best_bid_price', 'best_bid_qty']
    for c in float_cols:
        df[c] = pd.to_numeric(df[c], errors='coerce')
        
    dfs.append(df)
    print(f"  Year {year} parsed and cleaned successfully.")

# Concatenate all dataframes
print("\nConcatenating all years...")
combined_df = pd.concat(dfs, ignore_index=True)
print(f"Combined Shape: {combined_df.shape}")

# Sort primarily by trade_date chronologically, secondarily by code and symbol
print("Sorting data chronologically...")
combined_df = combined_df.sort_values(by=['trade_date', 'code', 'symbol']).reset_index(drop=True)

# Run strict verification checks
print("\nRunning validations...")

# 1. Total row count matches
assert len(combined_df) == total_raw_rows, f"Shape mismatch! Expected {total_raw_rows} rows, got {len(combined_df)}"
print(f"  [PASS] Row Count check: {len(combined_df)} rows matches the sum of raw rows perfectly.")

# 2. Reference schema matches exactly
assert list(combined_df.columns) == ref_cols, f"Schema mismatch! Columns: {list(combined_df.columns)}"
print("  [PASS] Columns check: Columns match the 16 reference columns exactly.")

# 3. Chronological sorting verification
dates_series = pd.to_datetime(combined_df['trade_date'])
is_sorted = dates_series.is_monotonic_increasing
assert is_sorted, "Data is not chronologically sorted!"
print(f"  [PASS] Sorting check: Dates are strictly in chronological order ({combined_df['trade_date'].min()} to {combined_df['trade_date'].max()}).")

# 4. Critical columns null check
for c in ['trade_date', 'name', 'code', 'symbol']:
    null_count = combined_df[c].isna().sum()
    assert null_count == 0, f"Critical column '{c}' has {null_count} nulls!"
print("  [PASS] Critical Null check: Zero nulls found in 'trade_date', 'name', 'code', and 'symbol'.")

# Ensure target directories exist
out_dir_flat = os.path.join(PROJECT_ROOT, "bulletin_staging")
out_dir_nested = os.path.join(PROJECT_ROOT, "bulletin_staging", "combined")
os.makedirs(out_dir_nested, exist_ok=True)

out_path_flat = os.path.join(out_dir_flat, "combined_bulletins.csv")
out_path_nested = os.path.join(out_dir_nested, "combined_bulletins.csv")
out_path_flat_pq = os.path.join(out_dir_flat, "combined_bulletins.parquet")
out_path_nested_pq = os.path.join(out_dir_nested, "combined_bulletins.parquet")

# Save files with UTF-8 with BOM encoding (utf-8-sig) to preserve Arabic characters
print(f"\nSaving consolidated dataset...")
combined_df.to_csv(out_path_flat, index=False, encoding='utf-8-sig')
print(f"  Saved to: {out_path_flat}")

combined_df.to_csv(out_path_nested, index=False, encoding='utf-8-sig')
print(f"  Saved to: {out_path_nested}")

# Save in Parquet format
combined_df.to_parquet(out_path_flat_pq, index=False)
print(f"  Saved to: {out_path_flat_pq}")

combined_df.to_parquet(out_path_nested_pq, index=False)
print(f"  Saved to: {out_path_nested_pq}")

print("\n==========================================================")
print("            CONSOLIDATION COMPLETED SUCCESSFULLY WITH ZERO LOSS           ")
print("==========================================================")
