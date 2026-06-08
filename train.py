import torch
from torch import nn
from torch.optim import AdamW
import numpy as np
import json
import os
import itertools
import sys
from sklearn.metrics import accuracy_score, f1_score

class Logger(object):
    def __init__(self, filename):
        self.terminal = sys.stdout
        self.log = open(filename, "w", encoding="utf-8")

    def write(self, message):
        self.terminal.write(message)
        self.log.write(message)
        self.log.flush()

    def flush(self):
        self.terminal.flush()
        self.log.flush()
        
    def close(self):
        self.log.close()

from dataset import get_dataloaders
from network import TimeSeriesClassifier
from evaluate import evaluate_model

class StockTanhLoss(nn.Module):
    def forward(self, logits, targets):
        allocations = torch.tanh(logits)
        step_returns = allocations * targets
        batch_roi = torch.mean(step_returns)
        return -batch_roi

def train_model(results_dir, epochs=30, batch_size=32, lr=1e-3, weight_decay=1e-3, window_size=5, hidden_dim=32):
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"[{results_dir}] Initializing DataLoaders...")
    train_loader, eval_loader, _ = get_dataloaders(window_size=window_size, batch_size=batch_size)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    model = TimeSeriesClassifier(hidden_dim=hidden_dim).to(device)
    criterion = StockTanhLoss()
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    
    history = {
        'train_loss': [], 'val_loss': [],
        'train_roi': [], 'val_roi': []
    }
    
    best_val_roi = -float('inf')
    best_model_path = os.path.join(results_dir, "best_model.pth")
    
    print(f"[{results_dir}] Starting training loop for {epochs} epochs...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        train_roi = 0.0
        
        for batch_idx, (features, targets, _, _) in enumerate(train_loader):
            features, targets = features.to(device), targets.to(device)
            
            optimizer.zero_grad()
            logits = model(features).squeeze(-1)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * features.size(0)
            train_roi += (-loss.item()) * features.size(0)
            
        train_loss /= len(train_loader.dataset)
        train_roi /= len(train_loader.dataset)
        
        model.eval()
        val_loss = 0.0
        val_roi = 0.0
        
        with torch.no_grad():
            for features, targets, _, _ in eval_loader:
                features, targets = features.to(device), targets.to(device)
                logits = model(features).squeeze(-1)
                
                loss = criterion(logits, targets)
                val_loss += loss.item() * features.size(0)
                val_roi += (-loss.item()) * features.size(0)
                
        val_loss /= len(eval_loader.dataset)
        val_roi /= len(eval_loader.dataset)
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_roi'].append(train_roi)
        history['val_roi'].append(val_roi)
        
        if val_roi > best_val_roi:
            best_val_roi = val_roi
            torch.save(model.state_dict(), best_model_path)
            
        if (epoch + 1) % 10 == 0 or epoch == epochs - 1:
            print(f"[{results_dir}] Epoch [{epoch+1}/{epochs}] | Val ROI: {val_roi:.6f} | Best Val ROI: {best_val_roi:.6f}")

    with open(os.path.join(results_dir, "training_history.json"), "w") as f:
        json.dump(history, f)
        
    return best_val_roi

def run_grid_search():
    learning_rates = [1e-3, 1e-4]
    weight_decays = [1e-3, 1e-4]
    window_sizes = [30, 60]
    epochs_list = [30, 50]
    hidden_dims = [128, 64]
    
    best_overall_roi = -float('inf')
    best_run_id = None
    best_config_dir = None
    
    run_id = 1
    
    for lr, wd, ws, ep, hd in itertools.product(learning_rates, weight_decays, window_sizes, epochs_list, hidden_dims):
        results_dir = os.path.join("results", f"run_{run_id}")
        os.makedirs(results_dir, exist_ok=True)
        
        log_file_path = os.path.join(results_dir, "run.log")
        logger = Logger(log_file_path)
        old_stdout = sys.stdout
        sys.stdout = logger
        
        try:
            config = {
                "run_id": run_id,
                "learning_rate": lr,
                "weight_decay": wd,
                "window_size": ws,
                "epochs": ep,
                "hidden_dim": hd
            }
            with open(os.path.join(results_dir, "config.json"), "w") as f:
                json.dump(config, f, indent=4)
                
            print(f"\n{'='*50}\nEvaluating Config Run {run_id}\n{config}\n{'='*50}")
            
            best_val_roi = train_model(
                results_dir=results_dir, 
                epochs=ep, 
                batch_size=32, 
                lr=lr, 
                weight_decay=wd, 
                window_size=ws,
                hidden_dim=hd
            )
            
            print(f"Evaluating run_{run_id} on test set and generating plots...")
            evaluate_model(results_dir=results_dir, window_size=ws, hidden_dim=hd)
            
            if best_val_roi > best_overall_roi:
                best_overall_roi = best_val_roi
                best_run_id = run_id
                best_config_dir = results_dir
        finally:
            sys.stdout = old_stdout
            logger.close()
            
        run_id += 1
                    
    summary = (
        f"\n{'='*50}\n"
        f"GRID SEARCH COMPLETE\n"
        f"{'='*50}\n"
        f"Best Configuration Run: {best_run_id}\n"
        f"Best Validation Mean ROI Step: {best_overall_roi:.6f}\n"
        f"Results can be found in: {best_config_dir}\n"
    )
    print(summary)
    
    if best_config_dir:
        final_log_path = os.path.join("results", "best_model_summary.log")
        with open(final_log_path, "w", encoding="utf-8") as f:
            f.write(summary)

if __name__ == "__main__":
    run_grid_search()
