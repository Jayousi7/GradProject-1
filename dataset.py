import os
import pandas as pd
import numpy as np
import torch
import random
from torch.utils.data import Dataset, DataLoader

class TimeSeriesDataset(Dataset):
    def __init__(self, features, targets, raw_returns, company_names=None):
        self.features = torch.tensor(features, dtype=torch.float32)
        self.targets = torch.tensor(targets, dtype=torch.float32)
        self.raw_returns = torch.tensor(raw_returns, dtype=torch.float32)
        # Store company names to group predictions later if needed
        self.company_names = company_names if company_names is not None else [""] * len(features)
        
    def __len__(self):
        return len(self.features)
    
    def __getitem__(self, idx):
        return self.features[idx], self.targets[idx], self.raw_returns[idx], self.company_names[idx]

def create_sliding_windows(features, targets, raw_returns, company_name, window_size=5):
    num_samples = len(features) - window_size + 1
    if num_samples <= 0:
        return np.empty((0, features.shape[1], window_size)), np.empty((0,)), np.empty((0,)), []
        
    w_features = []
    w_targets = []
    w_raw_returns = []
    w_company_names = []
    
    for i in range(num_samples):
        window_f = features[i:i+window_size]
        w_features.append(window_f.T)
        w_targets.append(targets[i+window_size-1])
        w_raw_returns.append(raw_returns[i+window_size-1])
        w_company_names.append(company_name)
        
    return np.array(w_features), np.array(w_targets), np.array(w_raw_returns), w_company_names

def prepare_data(data_dir="Jordan", window_size=5, seed=42):
    csv_files = []
    for root, dirs, files in os.walk(data_dir):
        for file in files:
            if file.endswith('.csv'):
                rel_dir = os.path.relpath(root, data_dir)
                if rel_dir == '.':
                    csv_files.append(file)
                else:
                    csv_files.append(os.path.join(rel_dir, file).replace('\\', '/'))
                    
    all_train_f, all_train_t, all_train_r, all_train_c = [], [], [], []
    all_eval_f,  all_eval_t,  all_eval_r,  all_eval_c  = [], [], [], []
    all_test_f,  all_test_t,  all_test_r,  all_test_c  = [], [], [], []
    
    continuous_cols = ['Return', 'RSI', 'MACD', 'Spread', 'VROC']
    features_cols = continuous_cols + ['is_market_open']
    
    for f in csv_files:
        path = os.path.join(data_dir, f)
        df = pd.read_csv(path)
        
        # 1. Sort Chronologically to prevent target index shift leakage
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date').reset_index(drop=True)
        
        # 2. Target Shift
        df['next_day_return_value'] = df['Return'].shift(-1)
        df = df.iloc[:-1].copy()
        df['is_market_open'] = 1 - df['is_closed']
        
        # 3. Chronological Indices
        n_samples = len(df)
        train_end = int(n_samples * 0.7)
        eval_end = int(n_samples * 0.85)
        
        # 4. Z-Score Normalization strictly on Train Split
        train_df = df.iloc[:train_end]
        train_mean = train_df[continuous_cols].mean()
        train_std = train_df[continuous_cols].std()
        
        # Avoid division by zero
        train_std = train_std.replace(0, 1.0)
        
        df[continuous_cols] = (df[continuous_cols] - train_mean) / train_std
        
        comp_name = os.path.basename(f).replace('.csv', '')
        
        def extract_slice(start_idx, end_idx):
            if start_idx >= end_idx:
                return None, None, None, None
            slice_df = df.iloc[start_idx:end_idx]
            features = slice_df[features_cols].values
            target = slice_df['next_day_return_value'].values
            raw_ret = slice_df['next_day_return_value'].values
            
            # create_sliding_windows inherently requires `window_size` points to output 1 prediction.
            # Passing consecutive slice blocks independently creates a natural Purge zone!
            w_f, w_t, w_r, w_c = create_sliding_windows(features, target, raw_ret, comp_name, window_size)
            return w_f, w_t, w_r, w_c

        # Train Slice
        tr_f, tr_t, tr_r, tr_c = extract_slice(0, train_end)
        if tr_f is not None and len(tr_f) > 0:
            all_train_f.append(tr_f)
            all_train_t.append(tr_t)
            all_train_r.append(tr_r)
            all_train_c.extend(tr_c)
            
        # Eval Slice
        ev_f, ev_t, ev_r, ev_c = extract_slice(train_end, eval_end)
        if ev_f is not None and len(ev_f) > 0:
            all_eval_f.append(ev_f)
            all_eval_t.append(ev_t)
            all_eval_r.append(ev_r)
            all_eval_c.extend(ev_c)
            
        # Test Slice
        te_f, te_t, te_r, te_c = extract_slice(eval_end, n_samples)
        if te_f is not None and len(te_f) > 0:
            all_test_f.append(te_f)
            all_test_t.append(te_t)
            all_test_r.append(te_r)
            all_test_c.extend(te_c)

    def build_dataset(f_list, t_list, r_list, c_list):
        if not f_list:
            return None
        return TimeSeriesDataset(np.concatenate(f_list), np.concatenate(t_list), np.concatenate(r_list), c_list)
        
    train_dataset = build_dataset(all_train_f, all_train_t, all_train_r, all_train_c)
    eval_dataset = build_dataset(all_eval_f, all_eval_t, all_eval_r, all_eval_c)
    test_dataset = build_dataset(all_test_f, all_test_t, all_test_r, all_test_c)
    
    print(f"--- Chronological Data Split ---")
    print(f"Total Companies processed: {len(csv_files)}")
    print(f"Train samples: {len(train_dataset) if train_dataset else 0}")
    print(f"Eval samples: {len(eval_dataset) if eval_dataset else 0}")
    print(f"Test samples: {len(test_dataset) if test_dataset else 0}")
    print("-----------------------------------")
    
    return train_dataset, eval_dataset, test_dataset

def get_dataloaders(data_dir="Jordan", window_size=5, batch_size=32, seed=42):
    train_ds, eval_ds, test_ds = prepare_data(data_dir, window_size, seed)
    
    train_loader = DataLoader(train_ds, batch_size=batch_size, shuffle=True)
    # We do NOT shuffle eval and test so we can plot time series correctly in evaluate
    eval_loader = DataLoader(eval_ds, batch_size=batch_size, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=batch_size, shuffle=False)
    
    return train_loader, eval_loader, test_loader

if __name__ == "__main__":
    tl, el, tel = get_dataloaders()
    for b_f, b_t, b_r, b_c in tl:
        print("Train Features shape:", b_f.shape)
        print("Train Target shape:", b_t.shape)
        print("Train Company names:", b_c[:5])
        break
