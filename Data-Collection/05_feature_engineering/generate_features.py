import pandas as pd
import numpy as np
import os

def calculate_ase_features(df):
    """
    Calculates the 8 requested technical features from the 18-column consolidated ASE dataset,
    and returns a clean DataFrame containing exactly the 18 core columns and 8 engineered columns.
    """
    # Enforce chronological sort by symbol and trade_date
    df = df.sort_values(by=['symbol', 'trade_date']).copy()
    
    # 1. Volume Rate of Change (VROC) - 5-day lookback
    print("[*] Calculating Volume Rate of Change (VROC_5d)...")
    def compute_vroc(volume, n=5):
        vol_shift = volume.shift(n)
        with np.errstate(divide='ignore', invalid='ignore'):
            vroc = (volume - vol_shift) / vol_shift
        return vroc.fillna(0.0).replace([np.inf, -np.inf], 0.0)
    
    df['vroc_5d'] = df.groupby('symbol')['volume'].apply(compute_vroc).reset_index(level=0, drop=True)
    
    # 2. Relative Strength Index (RSI) - 14-day window
    print("[*] Calculating Relative Strength Index (RSI_14)...")
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

    df['rsi_14'] = df.groupby('symbol')['close_price'].apply(compute_rsi).reset_index(level=0, drop=True)
    
    # 3. Stochastic Oscillator (%K and %D) - 14-day window, 3-day SMA of %K
    print("[*] Calculating Stochastic Oscillator (%K and %D)...")
    def compute_stochastic_k(group, n=14):
        close = group['close_price']
        low_n = group['low'].rolling(window=n, min_periods=1).min()
        high_n = group['high'].rolling(window=n, min_periods=1).max()
        denom = high_n - low_n
        k = np.where(denom > 0, ((close - low_n) / denom) * 100, 50.0)
        return pd.Series(k, index=group.index)

    df['stochastic_k'] = df.groupby('symbol', group_keys=False).apply(compute_stochastic_k)
    df['stochastic_d'] = df.groupby('symbol')['stochastic_k'].apply(lambda x: x.rolling(window=3, min_periods=1).mean()).reset_index(level=0, drop=True)
    
    # 4. MACD Line and MACD Signal - EMA 12, EMA 26, Signal EMA 9
    print("[*] Calculating MACD Line and MACD Signal...")
    def compute_macd_line(close):
        ema_12 = close.ewm(span=12, adjust=False, min_periods=1).mean()
        ema_26 = close.ewm(span=26, adjust=False, min_periods=1).mean()
        return ema_12 - ema_26

    df['macd_line'] = df.groupby('symbol')['close_price'].apply(compute_macd_line).reset_index(level=0, drop=True)
    df['macd_signal'] = df.groupby('symbol')['macd_line'].apply(lambda x: x.ewm(span=9, adjust=False, min_periods=1).mean()).reset_index(level=0, drop=True)
    
    # 5. High-Low Spread (Normalized)
    print("[*] Calculating Normalized High-Low Spread...")
    df['normalized_spread'] = (df['high'] - df['low']) / df['close_price']
    df['normalized_spread'] = df['normalized_spread'].fillna(0.0).replace([np.inf, -np.inf], 0.0)
    
    # 6. Bollinger Band Width - 20-day SMA +/- 2 std
    print("[*] Calculating Bollinger Band Width...")
    def compute_bollinger_width(close, window=20):
        sma = close.rolling(window=window, min_periods=1).mean()
        std = close.rolling(window=window, min_periods=1).std().fillna(0.0)
        with np.errstate(divide='ignore', invalid='ignore'):
            width = (4 * std) / sma
        return width.fillna(0.0).replace([np.inf, -np.inf], 0.0)

    df['bollinger_width'] = df.groupby('symbol')['close_price'].apply(compute_bollinger_width).reset_index(level=0, drop=True)
    
    # Standard 18 columns in exact order
    ref_cols_18 = [
        'trade_date', 'name', 'code', 'symbol', 'market', 
        'volume', 'qty', 'no_of_trades', 'high', 'low', 'open', 'close_price',
        'best_ask_price', 'best_ask_qty', 'best_bid_price', 'best_bid_qty', 'return_value', 'is_closed'
    ]
    
    # 8 Technical features
    engineered_cols = [
        'vroc_5d', 'rsi_14', 'stochastic_k', 'stochastic_d', 
        'macd_line', 'macd_signal', 'normalized_spread', 'bollinger_width'
    ]
    
    # Select only the 18 core columns + the 8 engineered columns (total 26 columns)
    final_cols = ref_cols_18 + engineered_cols
    df = df[final_cols]
    
    # Restore nullable Int64 types to keep everything clean and compliant
    df['code'] = df['code'].astype('Int64')
    df['market'] = df['market'].astype('Int64')
    df['qty'] = df['qty'].astype('Int64')
    df['no_of_trades'] = df['no_of_trades'].astype('Int64')
    df['is_closed'] = df['is_closed'].astype('Int64')
    
    return df

if __name__ == "__main__":
    # Dynamically resolve directories relative to the script location
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
    PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

    data_dir = os.path.join(PROJECT_ROOT, "data")
    feature_dir = os.path.join(PROJECT_ROOT, "05_feature_engineering")
    
    data_path = os.path.join(data_dir, "combined_historical_unified.csv")
    
    if os.path.exists(data_path):
        print(f"[*] Reading consolidated master 18-column dataset: {data_path}...")
        df = pd.read_csv(data_path)
        
        # Calculate features (returns 26 columns)
        df_featured = calculate_ase_features(df)
        
        # Sort chronologically by trade_date, then alphabetically by symbol before saving
        df_featured = df_featured.sort_values(by=['trade_date', 'symbol']).reset_index(drop=True)
        
        # Save output in both CSV and Parquet formats under data/ and 05_feature_engineering/
        output_csv_feat = os.path.join(feature_dir, "combined_historical_with_features.csv")
        output_pq_feat = os.path.join(feature_dir, "combined_historical_with_features.parquet")
        
        output_csv_data = os.path.join(data_dir, "combined_historical_with_features.csv")
        output_pq_data = os.path.join(data_dir, "combined_historical_with_features.parquet")
        
        # Save feature-engineered datasets
        df_featured.to_csv(output_csv_feat, index=False)
        df_featured.to_parquet(output_pq_feat, index=False)
        print(f"[+++] Feature engineering complete! Saved to 05_feature_engineering: {output_csv_feat} | {output_pq_feat}")
        
        df_featured.to_csv(output_csv_data, index=False)
        df_featured.to_parquet(output_pq_data, index=False)
        print(f"[+++] Saved to data folder: {output_csv_data} | {output_pq_data}")
        
        # --- Generate Q1 2025 Sample (including 14 days before 2025: Dec 18th, 2024 to March 31st, 2025 inclusive) ---
        print("\n[*] Generating Q1 2025 sample (Dec 18th, 2024 to March 31st, 2025)...")
        df_sample = df_featured[
            (df_featured['trade_date'] >= '2024-12-18') &
            (df_featured['trade_date'] <= '2025-03-31')
        ].copy()
        
        sample_csv_feat = os.path.join(feature_dir, "sample_2025_jan_march.csv")
        sample_pq_feat = os.path.join(feature_dir, "sample_2025_jan_march.parquet")
        
        sample_csv_data = os.path.join(data_dir, "sample_2025_jan_march.csv")
        sample_pq_data = os.path.join(data_dir, "sample_2025_jan_march.parquet")
        
        # Save samples
        df_sample.to_csv(sample_csv_feat, index=False)
        df_sample.to_parquet(sample_pq_feat, index=False)
        print(f"[+++] Q1 2025 sample saved to 05_feature_engineering: {sample_csv_feat} | {sample_pq_feat}")
        
        df_sample.to_csv(sample_csv_data, index=False)
        df_sample.to_parquet(sample_pq_data, index=False)
        print(f"[+++] Q1 2025 sample saved to data folder: {sample_csv_data} | {sample_pq_data}")
        
        print(f"[+++] Dataset shape with engineered features: {df_featured.shape}")
        print(f"[+++] Q1 2025 sample shape: {df_sample.shape}")
        
    else:
        print(f"[-] Error: Could not find consolidated dataset at {data_path}")
