import os
import glob
import shutil
import pandas as pd
import numpy as np
import yfinance as yf

# Define directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

EGYPT_DIR = os.path.join(SCRIPT_DIR, "Egypt")
KUWAIT_DIR = os.path.join(SCRIPT_DIR, "Kuwait")
QATAR_DIR = os.path.join(SCRIPT_DIR, "Qatar")
SAUDI_DIR = os.path.join(SCRIPT_DIR, "Saudi")
MENA_DIR = os.path.join(SCRIPT_DIR, "MENA")

# Clean and re-create MENA folder to ensure a clean directory structure
if os.path.exists(MENA_DIR):
    print("[*] Cleaning existing MENA folder...")
    shutil.rmtree(MENA_DIR)
os.makedirs(MENA_DIR, exist_ok=True)

# Helper function to compute Welles Wilder's RSI_14
def compute_rsi(close, window=14):
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    
    # Welles Wilder's smoothing (EMA with alpha = 1 / window)
    avg_gain = gain.ewm(alpha=1.0/window, adjust=False, min_periods=window).mean()
    avg_loss = loss.ewm(alpha=1.0/window, adjust=False, min_periods=window).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    # Handle division by zero or NaN values
    rsi = rsi.fillna(50.0)
    rsi.loc[avg_gain == 0] = 0.0
    rsi.loc[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return rsi

# Helper function to compute MACD line
def compute_macd_line(close):
    ema_12 = close.ewm(span=12, adjust=False, min_periods=1).mean()
    ema_26 = close.ewm(span=26, adjust=False, min_periods=1).mean()
    return ema_12 - ema_26

# Helper function to compute VROC_5d
def compute_vroc(volume, n=5):
    vol_shift = volume.shift(n)
    with np.errstate(divide='ignore', invalid='ignore'):
        vroc = (volume - vol_shift) / vol_shift
    return vroc.fillna(0.0).replace([np.inf, -np.inf], 0.0)

# Helper function to compute intraday normalized spread
def compute_normalized_spread(high, low, open_price):
    with np.errstate(divide='ignore', invalid='ignore'):
        spread = (high - low) / open_price
    return spread.fillna(0.0).replace([np.inf, -np.inf], 0.0)

def main():
    folders = [EGYPT_DIR, KUWAIT_DIR, QATAR_DIR, SAUDI_DIR]
    ticker_to_company = {}
    ticker_to_country = {}
    
    # Scan directories to discover tickers, company names, and countries
    print("[*] Scanning regional folders for tickers and company names...")
    for folder in folders:
        folder_name = os.path.basename(folder) # Egypt, Kuwait, Qatar, Saudi
        csv_files = glob.glob(os.path.join(folder, "*.csv"))
        for f in csv_files:
            filename = os.path.basename(f)
            ticker = filename[:-4] # Strip .csv
            
            # Read first few rows of CSV to extract company name
            try:
                df = pd.read_csv(f, nrows=5)
                company = None
                for col in ['Company', 'name', 'company', 'Company Name', 'company_name']:
                    if col in df.columns:
                        company = df[col].iloc[0]
                        break
                if not company:
                    company = ticker
                ticker_to_company[ticker] = company
                ticker_to_country[ticker] = folder_name
            except Exception as e:
                print(f"  [!] Error reading {filename}: {e}")
                ticker_to_company[ticker] = ticker
                ticker_to_country[ticker] = folder_name

    print(f"[+] Found {len(ticker_to_company)} tickers to process.")
    
    # Lists for reports and combining
    success_tickers = []
    failed_tickers = []
    data_issues_report = []
    
    combined_all_firms = []
    combined_by_country = {
        "Egypt": [],
        "Kuwait": [],
        "Qatar": [],
        "Saudi": []
    }

    # Dates definitions
    download_start = '2014-11-01'
    download_end = '2026-01-05' # extra buffer
    target_start = '2014-12-14'
    target_end = '2025-12-31'
    
    all_target_days = pd.date_range(start=target_start, end=target_end, freq='D')
    expected_rows = len(all_target_days) # 4036 days
    print(f"[*] Target range: {target_start} to {target_end} ({expected_rows} contiguous days)")

    for idx, (ticker, company_name) in enumerate(sorted(ticker_to_company.items())):
        country = ticker_to_country[ticker]
        print(f"\n[{idx+1}/{len(ticker_to_company)}] Fetching historical data for {ticker} ({company_name}) [{country}]...")
        
        try:
            # Download from Yahoo Finance
            df_yf = yf.download(ticker, start=download_start, end=download_end, progress=False)
        except Exception as e:
            print(f"  [-] Failed to download from yfinance: {e}")
            failed_tickers.append(ticker)
            data_issues_report.append(f"{ticker}: yfinance download exception: {e}")
            continue

        if df_yf.empty or len(df_yf) < 5:
            print(f"  [-] yfinance returned empty or insufficient data.")
            failed_tickers.append(ticker)
            data_issues_report.append(f"{ticker}: Empty or insufficient data returned from yfinance")
            continue

        # Flatten multi-index columns if present
        if isinstance(df_yf.columns, pd.MultiIndex):
            df_yf.columns = df_yf.columns.get_level_values(0)

        # Drop rows where major fields are all NaN
        df_yf = df_yf.dropna(subset=['Close', 'High', 'Low', 'Open'], how='all')

        if len(df_yf) < 5:
            print(f"  [-] yfinance data had only NaNs.")
            failed_tickers.append(ticker)
            data_issues_report.append(f"{ticker}: Data contained only NaN price values")
            continue

        # Record originally open dates (dates returned by yfinance)
        originally_open_dates = set(df_yf.index.strftime('%Y-%m-%d'))
        
        # Log if listing date starts late or ends early
        first_available_date = df_yf.index.min().strftime('%Y-%m-%d')
        last_available_date = df_yf.index.max().strftime('%Y-%m-%d')
        
        issues = []
        if first_available_date > target_start:
            issues.append(f"Starts late (listed) on {first_available_date}")
        if last_available_date < target_end:
            issues.append(f"Ends early on {last_available_date}")

        # Compute technical indicators on trading-days-only sequence
        close = df_yf['Close']
        high = df_yf['High']
        low = df_yf['Low']
        open_price = df_yf['Open']
        volume_raw = df_yf['Volume']

        # Log returns
        df_yf['return_value'] = np.log(close / close.shift(1))
        df_yf['return_value'] = df_yf['return_value'].fillna(0.0).replace([np.inf, -np.inf], 0.0)
        
        # Technical indicators
        df_yf['rsi_14'] = compute_rsi(close, window=14)
        df_yf['macd_line'] = compute_macd_line(close)
        df_yf['normalized_spread'] = compute_normalized_spread(high, low, open_price)
        df_yf['vroc_5d'] = compute_vroc(volume_raw, n=5)

        # Reindex to continuous calendar range from download_start to target_end
        full_range = pd.date_range(start=download_start, end=target_end, freq='D')
        df_daily = df_yf.reindex(full_range)
        df_daily.index.name = 'date_dt'

        # Set binary flag
        df_daily['is_market_open'] = df_daily.index.strftime('%Y-%m-%d').isin(originally_open_dates).astype(int)

        # Forward-fill prices and calculated indicators
        cols_to_ffill = ['Open', 'High', 'Low', 'Close', 'rsi_14', 'macd_line', 'normalized_spread', 'vroc_5d']
        df_daily[cols_to_ffill] = df_daily[cols_to_ffill].ffill()

        # Backward fill any remaining NaNs at the beginning of the series, then fill with 0.0 if any are left
        # Note: These will be overwritten for pre-IPO dates to prevent data leakage.
        df_daily[cols_to_ffill] = df_daily[cols_to_ffill].bfill().fillna(0.0)

        # Construct and clean volume
        df_daily['volume'] = df_daily['Volume'].fillna(0.0)
        
        # Set overrides on non-trading days
        # Volume set to 0.0, return set to 0.0
        df_daily.loc[df_daily['is_market_open'] == 0, 'volume'] = 0.0
        df_daily.loc[df_daily['is_market_open'] == 0, 'return_value'] = 0.0

        # CRITICAL DATA LEAKAGE FIX:
        # If the day is before the first available listing/trading date on yfinance, 
        # set ALL indicators, prices, volume, and returns to 0.0 and is_market_open to 0.
        pre_ipo_mask = df_daily.index.strftime('%Y-%m-%d') < first_available_date
        df_daily.loc[pre_ipo_mask, cols_to_ffill] = 0.0
        df_daily.loc[pre_ipo_mask, 'volume'] = 0.0
        df_daily.loc[pre_ipo_mask, 'return_value'] = 0.0
        df_daily.loc[pre_ipo_mask, 'is_market_open'] = 0

        # Reset index and build final schema
        df_daily = df_daily.reset_index()
        df_daily['date'] = df_daily['date_dt'].dt.strftime('%Y-%m-%d')
        df_daily['ticker'] = ticker
        df_daily['company_name'] = company_name
        df_daily['open'] = df_daily['Open']
        df_daily['high'] = df_daily['High']
        df_daily['low'] = df_daily['Low']
        df_daily['close_price'] = df_daily['Close']

        # Slice to the target period (2014-12-14 to 2025-12-31)
        df_final = df_daily[(df_daily['date'] >= target_start) & (df_daily['date'] <= target_end)].copy()

        # Ensure correct column order
        cols_order = [
            'date', 'ticker', 'company_name', 
            'open', 'high', 'low', 'close_price', 'volume',
            'return_value', 'rsi_14', 'macd_line', 
            'normalized_spread', 'vroc_5d', 'is_market_open'
        ]
        df_final = df_final[cols_order]

        # Convert is_market_open to Int64 type
        df_final['is_market_open'] = df_final['is_market_open'].astype('Int64')

        # Check for unexpected trading gaps (e.g. market closed for > 10 days) after IPO
        post_ipo_df = df_final[df_final['date'] >= first_available_date]
        if len(post_ipo_df) > 0:
            closed_streaks = post_ipo_df['is_market_open'].eq(0).astype(int).groupby(post_ipo_df['is_market_open'].eq(1).cumsum()).sum()
            max_closed_gap = closed_streaks.max()
            if max_closed_gap > 10:
                issues.append(f"Has post-listing gap of {max_closed_gap} consecutive days")

        if issues:
            data_issues_report.append(f"{ticker}: " + " | ".join(issues))
            print(f"  [WARN] Data issues: {', '.join(issues)}")

        # Create target directories
        country_csv_dir = os.path.join(MENA_DIR, country, "csv")
        country_parquet_dir = os.path.join(MENA_DIR, country, "parquet")
        os.makedirs(country_csv_dir, exist_ok=True)
        os.makedirs(country_parquet_dir, exist_ok=True)

        # Save individual CSV file
        csv_file_path = os.path.join(country_csv_dir, f"{ticker}.csv")
        df_final.to_csv(csv_file_path, index=False, encoding='utf-8')
        
        # Save individual Parquet file
        parquet_file_path = os.path.join(country_parquet_dir, f"{ticker}.parquet")
        df_final.to_parquet(parquet_file_path, index=False, engine='pyarrow')
        
        print(f"  [+] Saved CSV & Parquet to {country} (Rows: {len(df_final)})")
        
        success_tickers.append(ticker)
        combined_all_firms.append(df_final)
        combined_by_country[country].append(df_final)

    # Save combined country files
    for country, dfs in combined_by_country.items():
        if dfs:
            print(f"\n[*] Concatenating data for {country}...")
            df_country_master = pd.concat(dfs, ignore_index=True)
            df_country_master = df_country_master.sort_values(by=['date', 'ticker']).reset_index(drop=True)
            
            # Save combined CSV for this country
            c_csv_path = os.path.join(MENA_DIR, country, "csv", f"{country}_combined.csv")
            df_country_master.to_csv(c_csv_path, index=False, encoding='utf-8')
            
            # Save combined Parquet for this country
            c_parquet_path = os.path.join(MENA_DIR, country, "parquet", f"{country}_combined.parquet")
            df_country_master.to_parquet(c_parquet_path, index=False, engine='pyarrow')
            print(f"  [+] Saved combined {country} files: {len(df_country_master)} rows.")

    # Save overall master files
    if combined_all_firms:
        print("\n[*] Concatenating all firms data into a single master file...")
        df_master = pd.concat(combined_all_firms, ignore_index=True)
        # Sort by date and ticker
        df_master = df_master.sort_values(by=['date', 'ticker']).reset_index(drop=True)
        
        master_csv_path = os.path.join(MENA_DIR, "MENA.csv")
        df_master.to_csv(master_csv_path, index=False, encoding='utf-8')
        
        master_parquet_path = os.path.join(MENA_DIR, "MENA.parquet")
        df_master.to_parquet(master_parquet_path, index=False, engine='pyarrow')
        print(f"[+++] Saved master files to {master_csv_path} and {master_parquet_path} (Shape: {df_master.shape})")
    
    # Save missing days/data issue report
    report_path = os.path.join(MENA_DIR, "missing_days_report.txt")
    with open(report_path, "w", encoding='utf-8') as rf:
        rf.write("==================================================\n")
        rf.write("MENA Stock Data Retrieval - Data Quality Report\n")
        rf.write("==================================================\n\n")
        rf.write(f"Total Tickers Attempted: {len(ticker_to_company)}\n")
        rf.write(f"Successful Downloads: {len(success_tickers)}\n")
        rf.write(f"Failed Downloads: {len(failed_tickers)}\n\n")
        
        if failed_tickers:
            rf.write("FAILED TICKERS:\n")
            for ft in failed_tickers:
                rf.write(f" - {ft}\n")
            rf.write("\n")
            
        rf.write("DATA QUALITY ISSUES (LATE START, EARLY END, OR LARGE GAPS):\n")
        if data_issues_report:
            for issue in data_issues_report:
                rf.write(f" - {issue}\n")
        else:
            rf.write(" None found. All tickers have complete coverage.\n")
            
    print(f"[+++] Saved data quality report to {report_path}")

if __name__ == "__main__":
    main()
