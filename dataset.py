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
    csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
    
    # Randomly shuffle and split companies
    random.seed(seed)
    random.shuffle(csv_files)
    
    # 9 Train, 2 Eval, 2 Test
    train_comps = csv_files[:9]
    eval_comps = csv_files[9:11]
    test_comps = csv_files[11:13]
    
    print(f"--- Data Split (Seed: {seed}) ---")
    print(f"Train Companies (9): {train_comps}")
    print(f"Eval Companies (2): {eval_comps}")
    print(f"Test Companies (2): {test_comps}")
    print("-----------------------------------")
    
    def load_company_data(comps):
        comp_data = {}
        features_list = []
        for f in comps:
            path = os.path.join(data_dir, f)
            df = pd.read_csv(path)
            
            df['next_day_return_value'] = df['Return'].shift(-1)
            df = df.iloc[:-1].copy()
            df['is_market_open'] = 1 - df['is_closed']
            
            # Apply rolling window normalization to continuous features
            continuous_cols = ['Return', 'RSI', 'MACD', 'Spread', 'VROC']
            rolling_window = window_size
            
            rolling_mean = df[continuous_cols].rolling(window=rolling_window, min_periods=1).mean()
            rolling_std = df[continuous_cols].rolling(window=rolling_window, min_periods=1).std()
            rolling_std = rolling_std.fillna(1.0)
            rolling_std[rolling_std == 0] = 1.0
            
            df[continuous_cols] = (df[continuous_cols] - rolling_mean) / rolling_std
            
            features_cols = continuous_cols + ['is_market_open']
            
            target = df['next_day_return_value'].values
            raw_ret = df['next_day_return_value'].values
            features = df[features_cols].values
            
            comp_data[f] = (features, target, raw_ret)
            features_list.append(features)
        return comp_data, features_list

    train_data_dict, train_features_list = load_company_data(train_comps)
    eval_data_dict, _ = load_company_data(eval_comps)
    test_data_dict, _ = load_company_data(test_comps)
    
    def process_dict_to_dataset(data_dict):
        all_w_f, all_w_t, all_w_r, all_w_c = [], [], [], []
        for comp_name, (features, target, raw_ret) in data_dict.items():
            w_f, w_t, w_r, w_c = create_sliding_windows(features, target, raw_ret, comp_name, window_size)
            if len(w_f) > 0:
                all_w_f.append(w_f)
                all_w_t.append(w_t)
                all_w_r.append(w_r)
                all_w_c.extend(w_c)
                
        if not all_w_f:
            return None
            
        final_f = np.concatenate(all_w_f)
        final_t = np.concatenate(all_w_t)
        final_r = np.concatenate(all_w_r)
        
        return TimeSeriesDataset(final_f, final_t, final_r, all_w_c)
        
    train_dataset = process_dict_to_dataset(train_data_dict)
    eval_dataset = process_dict_to_dataset(eval_data_dict)
    test_dataset = process_dict_to_dataset(test_data_dict)
    
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
