import os
import re
import sys
import numpy as np
import pandas as pd
import requests

# Reconfigure stdout to UTF-8 to prevent terminal encoding errors on Windows
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

# List of tickers provided by the user
TICKERS = ["JOEP", "JOPH", "ATCO", "APOT", "ARBK", "UBSI", "RMCC", "JOPT", "MANE", "PEDC", "DADI", "IREL", "JTEL"]

# Paths relative to project root
BASE_DIR = os.path.join(PROJECT_ROOT, "legacy_pipeline")
FIRMS_DIR = os.path.join(BASE_DIR, "firms")
COMBINED_FILE = os.path.join(BASE_DIR, "combined_historical.csv")

# Create directories
os.makedirs(FIRMS_DIR, exist_ok=True)

# Headers for HTTP requests to mimic a browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}

def get_company_id(ticker):
    """Scrapes the unique company ID from the ASE historical page for a given ticker."""
    url = f"https://www.ase.com.jo/en/company_historical/{ticker}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code != 200:
            print(f"[-] Error: Could not load historical page for {ticker}. Status code: {res.status_code}")
            return None
        
        # Regex search for the export link e.g. daily-historical-export/619
        match = re.search(r'daily-historical-export/(\d+)', res.text)
        if match:
            company_id = match.group(1)
            print(f"[+] Found Company ID for {ticker}: {company_id}")
            return company_id
        else:
            print(f"[-] Error: Could not find company ID in the page for {ticker}.")
            return None
    except Exception as e:
        print(f"[-] Error querying page for {ticker}: {e}")
        return None

def download_excel(company_id, ticker):
    """Downloads the historical Excel file for the company from ASE."""
    download_url = f"https://ase.com.jo/en/daily-historical-export/{company_id}?_format=xlsx"
    temp_path = os.path.join(SCRIPT_DIR, f"{ticker}_temp.xlsx")
    try:
        print(f"[*] Downloading Excel file for {ticker} from {download_url}...")
        res = requests.get(download_url, headers=HEADERS, timeout=30)
        if res.status_code == 200 and 'spreadsheet' in res.headers.get('Content-Type', ''):
            with open(temp_path, 'wb') as f:
                f.write(res.content)
            print(f"[+] Successfully downloaded Excel for {ticker}.")
            return temp_path
        else:
            print(f"[-] Error: Failed to download Excel for {ticker}. Status code: {res.status_code}, Content-Type: {res.headers.get('Content-Type')}")
            return None
    except Exception as e:
        print(f"[-] Error downloading Excel for {ticker}: {e}")
        return None

def compute_technical_features(df):
    """Computes basic and advanced technical features from OHLCV data."""
    # Ensure sorted by date ascending for sequential indicators
    df = df.sort_values('date').copy()
    
    # 1. Basic Ratio Features
    # Daily Volume Weighted Average Price (VWAP proxy)
    df['vwap_daily'] = np.where(df['no_of_shares'] > 0, df['value_traded'] / df['no_of_shares'], df['close'])
    # Average Share Volume per Trade
    df['avg_shares_per_trade'] = np.where(df['no_of_trades'] > 0, df['no_of_shares'] / df['no_of_trades'], 0.0)
    # Average Financial Value per Trade
    df['avg_value_per_trade'] = np.where(df['no_of_trades'] > 0, df['value_traded'] / df['no_of_trades'], 0.0)
    
    # 2. Return & Volatility Indicators
    # Daily Log Return
    df['daily_return'] = df['close'].pct_change()
    # Historical Volatility (20-day rolling standard deviation of daily return)
    df['volatility_20'] = df['daily_return'].rolling(window=20).std()
    
    # 3. Simple Moving Averages (SMAs)
    df['sma_5'] = df['close'].rolling(window=5).mean()
    df['sma_10'] = df['close'].rolling(window=10).mean()
    df['sma_20'] = df['close'].rolling(window=20).mean()
    df['sma_50'] = df['close'].rolling(window=50).mean()
    df['sma_200'] = df['close'].rolling(window=200).mean()
    
    # 4. Exponential Moving Averages (EMAs)
    df['ema_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['ema_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # 5. MACD (Moving Average Convergence Divergence)
    df['macd'] = df['ema_12'] - df['ema_26']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    df['macd_hist'] = df['macd'] - df['macd_signal']
    
    # 6. Bollinger Bands (20-day SMA +/- 2 Std Dev)
    rolling_std = df['close'].rolling(window=20).std()
    df['bollinger_mid'] = df['sma_20']
    df['bollinger_upper'] = df['sma_20'] + (rolling_std * 2)
    df['bollinger_lower'] = df['sma_20'] - (rolling_std * 2)
    
    # 7. Average True Range (ATR)
    # TR = max(H-L, |H-PrevC|, |L-PrevC|)
    prev_close = df['close'].shift(1)
    tr_high_low = df['high'] - df['low']
    tr_high_pc = (df['high'] - prev_close).abs()
    tr_low_pc = (df['low'] - prev_close).abs()
    
    df['true_range'] = pd.concat([tr_high_low, tr_high_pc, tr_low_pc], axis=1).max(axis=1)
    df['atr_14'] = df['true_range'].rolling(window=14).mean()
    
    # 8. Relative Strength Index (RSI - 14-day)
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    
    # Avoid division by zero
    rs = np.where(loss > 0, gain / loss, 0.0)
    df['rsi_14'] = np.where(loss == 0, 100.0, np.where(gain == 0, 0.0, 100.0 - (100.0 / (1.0 + rs))))
    
    # Sort back by date descending to preserve standard historical view if needed
    df = df.sort_values('date', ascending=False)
    
    return df

def clean_and_process_excel(temp_path, ticker):
    """Parses Excel, cleans format, and computes features."""
    try:
        # Load excel sheet
        df = pd.read_excel(temp_path)
        
        # Verify columns exist
        expected_cols = ['Date', 'High', 'Low', 'Closing', 'Value Traded', 'No. of Trans', 'No. of Shares']
        for col in expected_cols:
            if col not in df.columns:
                print(f"[-] Column '{col}' not found in downloaded sheet for {ticker}!")
                return None
                
        # 1. Clean Column Names to lowercase
        df = df.rename(columns={
            'Date': 'date',
            'High': 'high',
            'Low': 'low',
            'Closing': 'close',
            'Value Traded': 'value_traded',
            'No. of Trans': 'no_of_trades',
            'No. of Shares': 'no_of_shares'
        })
        
        # Keep only required columns in proper order
        df = df[['date', 'high', 'low', 'close', 'value_traded', 'no_of_trades', 'no_of_shares']].copy()
        
        # 2. Clean Dates to universal YYYY-MM-DD
        df['date'] = pd.to_datetime(df['date'], format='%d/%m/%Y', errors='coerce')
        # Drop rows with invalid dates
        df = df.dropna(subset=['date']).copy()
        
        # Sort and remove duplicates if any
        df = df.drop_duplicates(subset=['date']).sort_values('date', ascending=False).reset_index(drop=True)
        
        # 3. Handle Types
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['close'] = df['close'].astype(float)
        df['value_traded'] = df['value_traded'].astype(float)
        df['no_of_trades'] = df['no_of_trades'].astype(int)
        df['no_of_shares'] = df['no_of_shares'].astype(int)
        
        # 4. Generate Advanced Technical Features
        print(f"[*] Constructing technical features for {ticker}...")
        df_featured = compute_technical_features(df)
        
        # Final Format Date string
        df_featured['date'] = df_featured['date'].dt.strftime('%Y-%m-%d')
        
        return df_featured
    except Exception as e:
        print(f"[-] Error cleaning Excel data for {ticker}: {e}")
        return None

def run_workflow():
    print("="*60)
    print("      AMMAN STOCK EXCHANGE AUTOMATED DATA WORKFLOW      ")
    print("="*60)
    
    combined_dfs = []
    
    for ticker in TICKERS:
        print(f"\n>>> PROCESSING TICKER: {ticker} <<<")
        
        # Step 1: Scrape company ID
        company_id = get_company_id(ticker)
        if not company_id:
            print(f"[-] Skipping {ticker} due to missing company ID.")
            continue
            
        # Step 2: Download Excel file
        temp_xlsx = download_excel(company_id, ticker)
        if not temp_xlsx:
            print(f"[-] Skipping {ticker} due to download failure.")
            continue
            
        # Step 3: Clean, Parse and Compute technical features
        df_processed = clean_and_process_excel(temp_xlsx, ticker)
        
        # Clean up temporary Excel file
        try:
            if os.path.exists(temp_xlsx):
                os.remove(temp_xlsx)
        except Exception:
            pass
            
        if df_processed is None or df_processed.empty:
            print(f"[-] Skipping {ticker} due to processing failure.")
            continue
            
        # Step 4: Save individual CSV file in dedicated firm folder (overwriting old)
        firm_folder = os.path.join(FIRMS_DIR, ticker)
        os.makedirs(firm_folder, exist_ok=True)
        firm_csv_path = os.path.join(firm_folder, f"{ticker}_historical.csv")
        
        df_processed.to_csv(firm_csv_path, index=False, encoding='utf-8')
        print(f"[+] Saved updated file: {firm_csv_path} (Shape: {df_processed.shape})")
        
        # Add ticker column for the combined dataset
        df_for_combine = df_processed.copy()
        df_for_combine.insert(0, 'symbol', ticker)
        combined_dfs.append(df_for_combine)
        
    # Step 5: Merge all sheets into the final combined Master CSV
    if combined_dfs:
        print("\n>>> CREATING FINAL COMBINED MASTER CSV <<<")
        df_master = pd.concat(combined_dfs, ignore_index=True)
        # Ensure it is sorted by date descending, then symbol
        df_master['date_dt'] = pd.to_datetime(df_master['date'])
        df_master = df_master.sort_values(by=['date_dt', 'symbol'], ascending=[False, True]).drop(columns=['date_dt'])
        
        df_master.to_csv(COMBINED_FILE, index=False, encoding='utf-8')
        print(f"[+++] Workflow Complete! Saved master file: {COMBINED_FILE}")
        print(f"[+++] Master Shape: {df_master.shape}")
        print(f"[+++] Covered Tickers: {df_master['symbol'].unique().tolist()}")
    else:
        print("\n[-] Error: No data could be processed or combined.")

if __name__ == "__main__":
    run_workflow()
