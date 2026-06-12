import os
import glob
import pandas as pd
import numpy as np
import yfinance as yf

# Define directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

EGYPT_DIR = os.path.join(SCRIPT_DIR, "Egypt")
KUWAIT_DIR = os.path.join(SCRIPT_DIR, "Kuwait")
QATAR_DIR = os.path.join(SCRIPT_DIR, "Qatar")
JORDAN_DIR = os.path.join(SCRIPT_DIR, "Jordan")
SAUDI_DIR = os.path.join(SCRIPT_DIR, "Saudi")

# Create folders
for d in [EGYPT_DIR, KUWAIT_DIR, QATAR_DIR, JORDAN_DIR, SAUDI_DIR]:
    os.makedirs(d, exist_ok=True)

# Helper function to compute RSI_14
def compute_rsi(close, window=14):
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    
    avg_gain = gain.rolling(window=window, min_periods=1).mean()
    avg_loss = loss.rolling(window=window, min_periods=1).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    
    rsi = rsi.fillna(100.0)
    rsi.loc[avg_gain == 0] = 0.0
    rsi.loc[(avg_gain == 0) & (avg_loss == 0)] = 50.0
    return rsi

# Helper function to compute MACD
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

def process_yfinance_market(file_name, market_folder, date_col='Date', ticker_col='Ticker', company_col='Company'):
    file_path = os.path.join(SCRIPT_DIR, file_name)
    print(f"\n==================================================")
    print(f"[*] Processing Market File: {file_name}")
    print(f"==================================================")
    
    df_orig = pd.read_csv(file_path)
    ticker_to_company = df_orig.set_index(ticker_col)[company_col].to_dict()
    tickers = sorted(df_orig[ticker_col].unique())
    
    combined_ticker_dfs = []
    
    for idx, ticker in enumerate(tickers):
        print(f"[{idx+1}/{len(tickers)}] Fetching '{ticker}' ({ticker_to_company[ticker]}) from Yahoo Finance...")
        
        # Download price history starting 20 days before 2025 (Dec 11, 2024 to Apr 1, 2025)
        # We fetch up to Apr 2 to ensure Apr 1 (inclusive) is fully covered.
        df_yf = pd.DataFrame()
        try:
            df_yf = yf.download(ticker, start='2024-12-10', end='2025-04-02', progress=False)
        except Exception as e:
            print(f"  [-] Error downloading from yfinance: {e}")
        
        # Check if we got valid data
        if not df_yf.empty and len(df_yf) > 10:
            # Flatten multi-index columns if present (sometimes happens with yfinance download)
            if isinstance(df_yf.columns, pd.MultiIndex):
                df_yf.columns = df_yf.columns.get_level_values(0)
            
            # Record originally open dates (dates returned by yfinance where Volume > 0)
            originally_open_dates = set(df_yf[df_yf['Volume'] > 0].index.strftime('%Y-%m-%d'))
            
            # Reindex to contiguous daily calendar range
            min_date = '2024-12-10'
            max_date = '2025-04-01'
            all_days = pd.date_range(start=min_date, end=max_date, freq='D')
            
            df_yf = df_yf.reindex(all_days)
            df_yf.index.name = 'Date_dt'
            df_yf = df_yf.ffill()
            df_yf = df_yf.reset_index()
            
            df_yf['Date'] = df_yf['Date_dt'].dt.strftime('%Y-%m-%d')
            
            # Compute technical indicators on the contiguous daily range
            close = df_yf['Close']
            high = df_yf['High']
            low = df_yf['Low']
            volume = df_yf['Volume']
            
            log_ret = np.log(close / close.shift(1))
            log_ret = log_ret.fillna(0.0).replace([np.inf, -np.inf], 0.0)
            
            rsi = compute_rsi(close, window=14)
            macd = compute_macd_line(close)
            spread = (high - low) / close
            spread = spread.fillna(0.0).replace([np.inf, -np.inf], 0.0)
            vroc = compute_vroc(volume, n=5)
            
            df_yf['Ticker'] = ticker
            df_yf['Company'] = ticker_to_company[ticker]
            df_yf['Return'] = log_ret
            df_yf['RSI'] = rsi
            df_yf['MACD'] = macd
            df_yf['Spread'] = spread
            df_yf['VROC'] = vroc
            
            # Determine Is_Market_Open and is_closed
            df_yf['Is_Market_Open'] = df_yf['Date'].apply(lambda d: 1 if d in originally_open_dates else 0)
            df_yf['is_closed'] = 1 - df_yf['Is_Market_Open']
            
            # Clean overrides
            df_yf.loc[df_yf['is_closed'] == 1, 'Return'] = 0.0
            
            # Trim to Jan 1, 2025 to Apr 1, 2025
            df_final = df_yf[(df_yf['Date'] >= '2025-01-01') & (df_yf['Date'] <= '2025-04-01')].copy()
            
            # Reorder columns
            cols = ['Date', 'Ticker', 'Company', 'Return', 'RSI', 'MACD', 'Spread', 'VROC', 'Is_Market_Open', 'is_closed']
            df_final = df_final[cols]
            
            # Convert integer flags to nullable Int64
            df_final['Is_Market_Open'] = df_final['Is_Market_Open'].astype('Int64')
            df_final['is_closed'] = df_final['is_closed'].astype('Int64')
            
        else:
            print(f"  [!] yfinance returned empty or failed for {ticker}. Falling back to original CSV...")
            # Fallback to original CSV
            df_ticker_orig = df_orig[df_orig[ticker_col] == ticker].copy()
            df_ticker_orig['Date_dt'] = pd.to_datetime(df_ticker_orig[date_col])
            df_ticker_orig = df_ticker_orig.sort_values(by='Date_dt').reset_index(drop=True)
            
            originally_open_dates = set(df_ticker_orig[df_ticker_orig['Is_Market_Open'] == 1][date_col])
            
            target_days = pd.date_range(start='2025-01-01', end='2025-04-01', freq='D')
            
            df_final = df_ticker_orig.set_index('Date_dt').reindex(target_days).ffill().reset_index()
            df_final['Date'] = df_final['index'].dt.strftime('%Y-%m-%d')
            df_final = df_final.drop(columns=['index'])
            
            df_final['Ticker'] = ticker
            df_final['Company'] = ticker_to_company[ticker]
            
            df_final['Is_Market_Open'] = df_final['Date'].apply(lambda d: 1 if d in originally_open_dates else 0)
            df_final['is_closed'] = 1 - df_final['Is_Market_Open']
            
            # Override closed returns
            df_final.loc[df_final['is_closed'] == 1, 'Return'] = 0.0
            
            cols = ['Date', 'Ticker', 'Company', 'Return', 'RSI', 'MACD', 'Spread', 'VROC', 'Is_Market_Open', 'is_closed']
            df_final = df_final[cols]
            
            df_final['Is_Market_Open'] = df_final['Is_Market_Open'].astype('Int64')
            df_final['is_closed'] = df_final['is_closed'].astype('Int64')
        
        # Save individual firm CSV
        firm_csv_path = os.path.join(market_folder, f"{ticker}.csv")
        df_final.to_csv(firm_csv_path, index=False, encoding='utf-8')
        print(f"  [+] Saved {firm_csv_path} (Shape: {df_final.shape})")
        
        combined_ticker_dfs.append(df_final)
        
    # Overwrite the original master CSV file with the updated combined dataset
    if combined_ticker_dfs:
        df_master = pd.concat(combined_ticker_dfs, ignore_index=True)
        df_master = df_master.sort_values(by=['Date', 'Ticker']).reset_index(drop=True)
        df_master.to_csv(file_path, index=False, encoding='utf-8')
        print(f"[+++] Overwrote original master CSV: {file_path} (Shape: {df_master.shape})")

def process_jordan():
    print(f"\n==================================================")
    print(f"[*] Processing Jordan Market (Local File)")
    print(f"==================================================")
    
    file_path = os.path.join(PROJECT_ROOT, "data", "sample_2025_jan_march.csv")
    df_orig = pd.read_csv(file_path)
    df_orig['trade_date_dt'] = pd.to_datetime(df_orig['trade_date'])
    
    tickers = sorted(df_orig['symbol'].unique())
    combined_ticker_dfs = []
    
    for idx, ticker in enumerate(tickers):
        print(f"[{idx+1}/{len(tickers)}] Processing Jordan '{ticker}'...")
        
        df_ticker_orig = df_orig[df_orig['symbol'] == ticker].copy()
        df_ticker_orig = df_ticker_orig.sort_values(by='trade_date_dt').reset_index(drop=True)
        
        # Capture originally open trade dates
        originally_open_dates = set(df_ticker_orig[df_ticker_orig['is_closed'] == 0]['trade_date'])
        
        # Reindex to range '2024-12-18' (Jordan's min) to '2025-04-01'
        min_date = '2024-12-18'
        max_date = '2025-04-01'
        all_days = pd.date_range(start=min_date, end=max_date, freq='D')
        
        df_ticker_full = df_ticker_orig.set_index('trade_date_dt').reindex(all_days)
        df_ticker_full.index.name = 'trade_date_dt'
        df_ticker_full = df_ticker_full.ffill()
        df_ticker_full = df_ticker_full.reset_index()
        
        df_ticker_full['trade_date'] = df_ticker_full['trade_date_dt'].dt.strftime('%Y-%m-%d')
        df_ticker_full = df_ticker_full.drop(columns=['trade_date_dt'])
        
        # Re-enforce symbol and metadata
        df_ticker_full['symbol'] = ticker
        df_ticker_full['name'] = df_ticker_orig['name'].iloc[0]
        
        # Re-compute returns based on contiguous prices
        close = df_ticker_full['close_price']
        log_ret = np.log(close / close.shift(1))
        log_ret = log_ret.fillna(0.0).replace([np.inf, -np.inf], 0.0)
        df_ticker_full['return_value'] = log_ret
        
        # Set is_closed flag
        df_ticker_full['is_closed'] = df_ticker_full['trade_date'].apply(lambda d: 0 if d in originally_open_dates else 1)
        
        # Clean overrides
        df_ticker_full.loc[df_ticker_full['is_closed'] == 1, 'return_value'] = 0.0
        
        # Trim to target range '2025-01-01' to '2025-04-01'
        df_final = df_ticker_full[(df_ticker_full['trade_date'] >= '2025-01-01') & (df_ticker_full['trade_date'] <= '2025-04-01')].copy()
        
        # Enforce types
        df_final['code'] = df_final['code'].astype('Int64')
        df_final['market'] = df_final['market'].astype('Int64')
        df_final['qty'] = df_final['qty'].astype('Int64')
        df_final['no_of_trades'] = df_final['no_of_trades'].astype('Int64')
        df_final['is_closed'] = df_final['is_closed'].astype('Int64')
        
        # Save individual firm CSV
        firm_csv_path = os.path.join(JORDAN_DIR, f"{ticker}.csv")
        df_final.to_csv(firm_csv_path, index=False, encoding='utf-8')
        print(f"  [+] Saved {firm_csv_path} (Shape: {df_final.shape})")

if __name__ == "__main__":
    process_yfinance_market("Egypt.csv", EGYPT_DIR)
    process_yfinance_market("Kuwait.csv", KUWAIT_DIR)
    process_yfinance_market("Qatar.csv", QATAR_DIR)
    process_yfinance_market("Saudi_Arabia.csv", SAUDI_DIR)
    process_jordan()
    print("\n[+++] All markets processed successfully!")
