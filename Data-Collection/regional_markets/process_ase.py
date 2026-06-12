import os
import pandas as pd
import numpy as np

# Paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
INPUT_CSV = os.path.join(PROJECT_ROOT, "data", "combined_historical_with_features.csv")
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "ASE")

def main():
    print(f"Loading input file: {INPUT_CSV}")
    # Load the master CSV
    df = pd.read_csv(INPUT_CSV)
    print(f"Loaded {len(df)} rows.")

    # 1. Date conversion and filtering (2015-01-01 to 2025-12-31)
    df['Date_parsed'] = pd.to_datetime(df['trade_date'])
    df_filtered = df[(df['Date_parsed'] >= '2015-01-01') & (df['Date_parsed'] <= '2025-12-31')].copy()
    print(f"Filtered to date range 2015-01-01 to 2025-12-31: {len(df_filtered)} rows remaining.")

    if df_filtered.empty:
        print("Error: No data found in the specified date range.")
        return

    # 2. Compute/clean columns
    # Ensure is_closed is numeric
    df_filtered['is_closed'] = pd.to_numeric(df_filtered['is_closed']).fillna(0).astype(int)
    # Compute Is_Market_Open
    df_filtered['Is_Market_Open'] = 1 - df_filtered['is_closed']

    # 3. Rename columns
    # Date,Ticker(symbol),Company(name),Return,RSI,MACD,Spread,VROC,Is_Market_Open,is_closed
    column_mapping = {
        'trade_date': 'Date',
        'symbol': 'Ticker',
        'name': 'Company',
        'return_value': 'Return',
        'rsi_14': 'RSI',
        'macd_line': 'MACD',
        'normalized_spread': 'Spread',
        'vroc_5d': 'VROC',
        'Is_Market_Open': 'Is_Market_Open',
        'is_closed': 'is_closed'
    }
    
    # Select and rename
    df_final = df_filtered[list(column_mapping.keys())].rename(columns=column_mapping)
    
    # 4. Group by Ticker (symbol) and save to firm folders
    tickers = df_final['Ticker'].dropna().unique()
    print(f"Found {len(tickers)} unique firms.")

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    for idx, ticker in enumerate(sorted(tickers)):
        ticker_df = df_final[df_final['Ticker'] == ticker].copy()
        
        # Sort by date
        ticker_df = ticker_df.sort_values(by='Date')
        
        # Define directory for this firm
        firm_dir = os.path.join(OUTPUT_DIR, ticker)
        os.makedirs(firm_dir, exist_ok=True)
        
        # Define file paths
        csv_path = os.path.join(firm_dir, f"{ticker}.csv")
        parquet_path = os.path.join(firm_dir, f"{ticker}.parquet")
        
        # Save files
        ticker_df.to_csv(csv_path, index=False, encoding='utf-8')
        ticker_df.to_parquet(parquet_path, index=False, engine='pyarrow')
        
        print(f"[{idx+1}/{len(tickers)}] Saved {ticker} to {firm_dir} ({len(ticker_df)} rows)")

    print("\nProcessing completed successfully!")

if __name__ == "__main__":
    main()
