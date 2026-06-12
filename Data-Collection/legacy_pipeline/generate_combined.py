import pandas as pd
import os
import sys
import numpy as np

# Reconfigure stdout to UTF-8 to prevent terminal encoding errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# Define paths relative to project root
BASE_DIR = os.path.join(PROJECT_ROOT, "legacy_pipeline")
BULLETINS_FILE = os.path.join(PROJECT_ROOT, "bulletin_staging", "combined_bulletins.csv")
HISTORICAL_FILE = os.path.join(PROJECT_ROOT, "data", "combined_historical.csv")
FIRMS_DIR = os.path.join(BASE_DIR, "firms")
OUTPUT_MASTER_FILE = os.path.join(BASE_DIR, "combined_historical.csv") # Renamed: column number removed

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

def generate_combined_data():
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
        
        print(f"  Contiguous History (2010-2026) Shape: {df_ticker_full.shape}")
        print(f"  Contiguous History Date range: {df_ticker_full['trade_date'].min()} to {df_ticker_full['trade_date'].max()}")
        
        # Save individual firm historical CSV in 16-column format (column count suffix removed)
        firm_folder = os.path.join(FIRMS_DIR, ticker)
        os.makedirs(firm_folder, exist_ok=True)
        firm_csv = os.path.join(firm_folder, f"{ticker}_historical.csv")
        df_ticker_full.to_csv(firm_csv, index=False, encoding='utf-8')
        print(f"  [+] Saved company file: {firm_csv}")
        
        combined_master_dfs.append(df_ticker_full)
        
    # Create final combined Master CSV in 16-column format
    if combined_master_dfs:
        print("\n>>> CREATING FINAL COMBINED MASTER 16-COLUMN CSV <<<")
        df_master = pd.concat(combined_master_dfs, ignore_index=True)
        
        # Sort by trade_date ascending, then symbol ascending
        df_master = df_master.sort_values(by=['trade_date', 'symbol'], ascending=[True, True]).reset_index(drop=True)
        
        # Save master file (column count suffix removed)
        df_master.to_csv(OUTPUT_MASTER_FILE, index=False, encoding='utf-8')
        print(f"[+++] Consolidated master saved: {OUTPUT_MASTER_FILE}")
        print(f"[+++] Master Shape: {df_master.shape}")
        print(f"[+++] Master Date Range: {df_master['trade_date'].min()} to {df_master['trade_date'].max()}")
        print(f"[+++] Master Unique Symbols: {df_master['symbol'].unique().tolist()}")
    else:
        print("\n[-] Error: No data could be processed or combined.")

if __name__ == "__main__":
    generate_combined_data()
