import pandas as pd
import os
import sys
import numpy as np

# Reconfigure stdout to UTF-8 to prevent terminal encoding errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Define paths relative to the project root
BASE_DIR = os.path.join(PROJECT_ROOT, "data")
BULLETINS_FILE = os.path.join(PROJECT_ROOT, "bulletin_staging", "combined_bulletins.csv")
HISTORICAL_FILE = os.path.join(BASE_DIR, "combined_historical.csv")
FIRMS_DIR = os.path.join(BASE_DIR, "firms")
OUTPUT_MASTER_FILE = os.path.join(BASE_DIR, "combined_historical_unified.csv")

# Tickers to process
TICKERS = ["ARBK", "JOPT", "JOEP", "JOPH", "UBSI", "APOT", "RMCC", "ATCO", "MANE", "PEDC", "DADI", "IREL", "JTEL"]

# Mapping of tickers to historical LIPO symbol if applicable
# ATCO was listed as LIPO prior to 2016. We map LIPO to ATCO to get full contiguous history.
TICKER_MAPPING = {
    "ATCO": ["ATCO", "LIPO"]
}

def load_bulletins():
    """Loads bulletins and returns mapped company codes, names, and markets."""
    if not os.path.exists(BULLETINS_FILE):
        print(f"[-] Error: Bulletins file not found at {BULLETINS_FILE}")
        sys.exit(1)
        
    print(f"[*] Loading combined bulletins from: {BULLETINS_FILE}...")
    df = pd.read_csv(BULLETINS_FILE)
    df['trade_date'] = pd.to_datetime(df['trade_date']).dt.strftime('%Y-%m-%d')
    return df

def unify_multi_era_data():
    df_bull = load_bulletins()
    
    # Check 2026 data
    if not os.path.exists(HISTORICAL_FILE):
        print(f"[-] Error: Combined historical file not found at {HISTORICAL_FILE}")
        sys.exit(1)
        
    print(f"[*] Loading combined 2026 data from: {HISTORICAL_FILE}...")
    df_hist_2026 = pd.read_csv(HISTORICAL_FILE)
    df_hist_2026['date'] = pd.to_datetime(df_hist_2026['date']).dt.strftime('%Y-%m-%d')
    
    # Filter 2026 data to start from 2026-01-01 onwards
    df_hist_2026 = df_hist_2026[
        (df_hist_2026['date'] >= '2026-01-01')
    ].copy()
    
    print(f"[+] Loaded 2026 data: {len(df_hist_2026)} rows from 2026-01-01 onwards.")
    
    # Prepare mapping dictionaries from pre-2026 bulletins
    company_mappings = {}
    
    # 16 standard columns in exact order
    cols_16 = [
        'trade_date', 'name', 'code', 'symbol', 'market', 
        'volume', 'qty', 'no_of_trades', 'high', 'low', 'open', 'close_price',
        'best_ask_price', 'best_ask_qty', 'best_bid_price', 'best_bid_qty'
    ]
    
    combined_master_dfs = []
    
    for ticker in TICKERS:
        print(f"\n>>> PROCESSING TICKER: {ticker} <<<")
        
        # Determine which symbols in bulletins correspond to this ticker
        bulletin_symbols = TICKER_MAPPING.get(ticker, [ticker])
        
        # Extract pre-2026 historical data from bulletins
        df_ticker_bull = df_bull[
            (df_bull['symbol'].isin(bulletin_symbols)) &
            (df_bull['trade_date'] >= '2010-01-01') &
            (df_bull['trade_date'] <= '2025-12-31')
        ].copy()
        
        # If any ticker was mapped (like LIPO to ATCO), rename its symbol to target symbol
        if ticker == "ATCO":
            df_ticker_bull['symbol'] = "ATCO"
            
        print(f"  Bulletins (2010-2025) rows: {len(df_ticker_bull)}")
        
        # Retrieve name, code, market mapping from bulletins
        if not df_ticker_bull.empty:
            # We use the mode (most common value) to be safe and consistent
            name_val = df_ticker_bull['name'].mode()[0]
            code_val = df_ticker_bull['code'].mode()[0]
            market_val = df_ticker_bull['market'].mode()[0]
            company_mappings[ticker] = {
                'name': name_val,
                'code': code_val,
                'market': market_val
            }
            print(f"  Retrieved Metadata | Name: {name_val} | Code: {code_val} | Market: {market_val}")
        else:
            # Fallback if not found in bulletins (should not happen for our tickers)
            print(f"  [-] Warning: No bulletins data found for {ticker} before 2026.")
            company_mappings[ticker] = {
                'name': ticker,
                'code': np.nan,
                'market': np.nan
            }
            
        # Extract 2026 data for this ticker
        df_ticker_2026 = df_hist_2026[df_hist_2026['symbol'] == ticker].copy()
        print(f"  Daily Run 2026 rows: {len(df_ticker_2026)}")
        
        df_ticker_2026_mapped = pd.DataFrame()
        
        if not df_ticker_2026.empty:
            # Map the 7 recorded columns to the 16-column schema
            df_ticker_2026_mapped['trade_date'] = df_ticker_2026['date']
            df_ticker_2026_mapped['name'] = company_mappings[ticker]['name']
            df_ticker_2026_mapped['code'] = company_mappings[ticker]['code']
            df_ticker_2026_mapped['symbol'] = ticker
            df_ticker_2026_mapped['market'] = company_mappings[ticker]['market']
            df_ticker_2026_mapped['volume'] = df_ticker_2026['value_traded']
            df_ticker_2026_mapped['qty'] = df_ticker_2026['no_of_shares']
            df_ticker_2026_mapped['no_of_trades'] = df_ticker_2026['no_of_trades']
            df_ticker_2026_mapped['high'] = df_ticker_2026['high']
            df_ticker_2026_mapped['low'] = df_ticker_2026['low']
            
            # These columns are not recorded in 2026, set to NaN
            df_ticker_2026_mapped['open'] = np.nan
            df_ticker_2026_mapped['close_price'] = df_ticker_2026['close']
            df_ticker_2026_mapped['best_ask_price'] = np.nan
            df_ticker_2026_mapped['best_ask_qty'] = np.nan
            df_ticker_2026_mapped['best_bid_price'] = np.nan
            df_ticker_2026_mapped['best_bid_qty'] = np.nan
            
            # Enforce column order
            df_ticker_2026_mapped = df_ticker_2026_mapped[cols_16]
            
        # Concatenate 2010-2025 and 2026 data
        df_ticker_full = pd.concat([df_ticker_bull[cols_16], df_ticker_2026_mapped], ignore_index=True)
        
        # Sort chronologically ascending
        df_ticker_full = df_ticker_full.sort_values(by='trade_date').reset_index(drop=True)
        
        # --- Market-Closed Days Filling & Return Calculation ---
        # 1. Capture the originally open trade dates for this firm
        originally_open_dates = set(df_ticker_full['trade_date'])
        
        # 2. Reindex to all daily calendar days between the min and max traded dates
        df_ticker_full['trade_date_dt'] = pd.to_datetime(df_ticker_full['trade_date'])
        df_ticker_full = df_ticker_full.sort_values(by='trade_date_dt').reset_index(drop=True)
        
        min_date = df_ticker_full['trade_date_dt'].min()
        max_date = df_ticker_full['trade_date_dt'].max()
        all_days = pd.date_range(start=min_date, end=max_date, freq='D')
        
        df_ticker_full = df_ticker_full.set_index('trade_date_dt')
        df_ticker_full = df_ticker_full.reindex(all_days)
        df_ticker_full.index.name = 'trade_date_dt'
        
        # 3. Forward fill all columns from the last active market day
        df_ticker_full = df_ticker_full.ffill()
        
        # 4. Reset index, restore trade_date, drop temp column, and enforce cols_16
        df_ticker_full = df_ticker_full.reset_index()
        df_ticker_full['trade_date'] = df_ticker_full['trade_date_dt'].dt.strftime('%Y-%m-%d')
        df_ticker_full = df_ticker_full.drop(columns=['trade_date_dt'])
        df_ticker_full = df_ticker_full[cols_16]
        
        # 5. Restore core nullable Int64 types to keep everything clean and compliant
        df_ticker_full['code'] = df_ticker_full['code'].astype('Int64')
        df_ticker_full['market'] = df_ticker_full['market'].astype('Int64')
        df_ticker_full['qty'] = df_ticker_full['qty'].astype('Int64')
        df_ticker_full['no_of_trades'] = df_ticker_full['no_of_trades'].astype('Int64')
        
        # 6. Compute return_value (log return of close price)
        df_ticker_full['return_value'] = np.log(
            df_ticker_full['close_price'] / df_ticker_full['close_price'].shift(1)
        )
        # Handle first row (no shift)
        df_ticker_full['return_value'] = df_ticker_full['return_value'].fillna(0.0)
        # Handle division issues or infinities cleanly
        df_ticker_full['return_value'] = df_ticker_full['return_value'].replace([np.inf, -np.inf], 0.0)
        
        # 7. For any closed days, set return_value to exactly 0.0
        is_closed_day = ~df_ticker_full['trade_date'].isin(originally_open_dates)
        df_ticker_full.loc[is_closed_day, 'return_value'] = 0.0
        
        # 8. Create is_closed flag column (1 for closed, 0 for open)
        df_ticker_full['is_closed'] = 0
        df_ticker_full.loc[is_closed_day, 'is_closed'] = 1
        df_ticker_full['is_closed'] = df_ticker_full['is_closed'].astype('Int64')
        
        # Enforce columns including the 17th return_value and 18th is_closed columns
        cols_18 = cols_16 + ['return_value', 'is_closed']
        df_ticker_full = df_ticker_full[cols_18]
        
        print(f"  Contiguous Daily History (2010-2026) Shape: {df_ticker_full.shape}")
        print(f"  Contiguous Daily History Date range: {df_ticker_full['trade_date'].min()} to {df_ticker_full['trade_date'].max()}")
        
        # Save individual firm historical CSV & Parquet files in 18-column format
        firm_folder = os.path.join(FIRMS_DIR, ticker)
        os.makedirs(firm_folder, exist_ok=True)
        firm_csv = os.path.join(firm_folder, f"{ticker}_historical_unified.csv")
        firm_pq = os.path.join(firm_folder, f"{ticker}_historical_unified.parquet")
        
        df_ticker_full.to_csv(firm_csv, index=False, encoding='utf-8')
        df_ticker_full.to_parquet(firm_pq, index=False)
        print(f"  [+] Saved company files (CSV/Parquet): {firm_csv} | {firm_pq}")
        
        combined_master_dfs.append(df_ticker_full)
        
    # Create final combined Master CSV & Parquet in 18-column format
    if combined_master_dfs:
        print("\n>>> CREATING FINAL COMBINED MASTER 18-COLUMN DATASET <<<")
        df_master = pd.concat(combined_master_dfs, ignore_index=True)
        
        # Sort by trade_date ascending, then symbol ascending
        df_master = df_master.sort_values(by=['trade_date', 'symbol'], ascending=[True, True]).reset_index(drop=True)
        
        # Define target files
        data_dir = os.path.join(PROJECT_ROOT, "data")
        os.makedirs(data_dir, exist_ok=True)
        
        DATA_MASTER_CSV = os.path.join(data_dir, "combined_historical_unified.csv")
        DATA_MASTER_PQ = os.path.join(data_dir, "combined_historical_unified.parquet")
        
        # Save master in data folder
        df_master.to_csv(DATA_MASTER_CSV, index=False, encoding='utf-8')
        df_master.to_parquet(DATA_MASTER_PQ, index=False)
        print(f"[+++] Data folder master saved: {DATA_MASTER_CSV} | {DATA_MASTER_PQ}")
        
        print(f"[+++] Master Shape: {df_master.shape}")
        print(f"[+++] Master Date Range: {df_master['trade_date'].min()} to {df_master['trade_date'].max()}")
        print(f"[+++] Master Unique Symbols: {df_master['symbol'].unique().tolist()}")
    else:
        print("\n[-] Error: No data could be processed or combined.")

if __name__ == "__main__":
    unify_multi_era_data()
