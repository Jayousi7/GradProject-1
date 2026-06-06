import torch
from torch import nn
from torch.optim import AdamW
import numpy as np
import json
import os
from sklearn.metrics import accuracy_score, f1_score

from dataset import get_dataloaders
from network import TimeSeriesClassifier
from evaluate import evaluate_model

def train_model(results_dir, epochs=30, batch_size=32, lr=1e-3, weight_decay=1e-3, window_size=5):
    os.makedirs(results_dir, exist_ok=True)
    
    print(f"[{results_dir}] Initializing DataLoaders...")
    train_loader, eval_loader, _ = get_dataloaders(window_size=window_size, batch_size=batch_size)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    
    train_targets = train_loader.dataset.targets
    up_days = train_targets.sum().item()
    down_days = len(train_targets) - up_days
    ratio = down_days / up_days if up_days > 0 else 1.0
    pos_weight_tensor = torch.tensor([ratio], device=device)
    
    model = TimeSeriesClassifier().to(device)
    criterion = nn.BCEWithLogitsLoss(pos_weight=pos_weight_tensor)
    optimizer = AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    
    history = {
        'train_loss': [], 'val_loss': [],
        'train_acc': [], 'val_acc': [],
        'train_f1': [], 'val_f1': []
    }
    
    best_val_f1 = -1
    best_model_path = os.path.join(results_dir, "best_model.pth")
    
    print(f"[{results_dir}] Starting training loop for {epochs} epochs...")
    for epoch in range(epochs):
        model.train()
        train_loss = 0.0
        train_preds_all = []
        train_targets_all = []
        
        for batch_idx, (features, targets, _, _) in enumerate(train_loader):
            features, targets = features.to(device), targets.to(device)
            
            optimizer.zero_grad()
            logits = model(features).squeeze(-1)
            loss = criterion(logits, targets)
            loss.backward()
            optimizer.step()
            
            train_loss += loss.item() * features.size(0)
            
            preds = (logits > 0).cpu().numpy().astype(int)
            train_preds_all.extend(preds)
            train_targets_all.extend(targets.cpu().numpy().astype(int))
            
        train_loss /= len(train_loader.dataset)
        train_acc = accuracy_score(train_targets_all, train_preds_all)
        train_f1 = f1_score(train_targets_all, train_preds_all, zero_division=0)
        
        model.eval()
        val_loss = 0.0
        val_preds_all = []
        val_targets_all = []
        
        with torch.no_grad():
            for features, targets, _, _ in eval_loader:
                features, targets = features.to(device), targets.to(device)
                logits = model(features).squeeze(-1)
                
                loss = criterion(logits, targets)
                val_loss += loss.item() * features.size(0)
                
                preds = (logits > 0).cpu().numpy().astype(int)
                val_preds_all.extend(preds)
                val_targets_all.extend(targets.cpu().numpy().astype(int))
                
        val_loss /= len(eval_loader.dataset)
        val_acc = accuracy_score(val_targets_all, val_preds_all)
        val_f1 = f1_score(val_targets_all, val_preds_all, zero_division=0)
        
        history['train_loss'].append(train_loss)
        history['val_loss'].append(val_loss)
        history['train_acc'].append(train_acc)
        history['val_acc'].append(val_acc)
        history['train_f1'].append(train_f1)
        history['val_f1'].append(val_f1)
        
        if val_f1 > best_val_f1:
            best_val_f1 = val_f1
            torch.save(model.state_dict(), best_model_path)
            
        if (epoch + 1) % 10 == 0 or epoch == epochs - 1:
            print(f"[{results_dir}] Epoch [{epoch+1}/{epochs}] | Val F1: {val_f1:.4f} | Best Val F1: {best_val_f1:.4f}")

    with open(os.path.join(results_dir, "training_history.json"), "w") as f:
        json.dump(history, f)
        
    return best_val_f1

def run_grid_search():
    learning_rates = [1e-3, 1e-4]
    weight_decays = [1e-3, 1e-4]
    window_sizes = [5, 10]
    epochs_list = [30, 50]
    
    best_overall_f1 = -1
    best_run_id = None
    best_config_dir = None
    
    run_id = 1
    
    for lr in learning_rates:
        for wd in weight_decays:
            for ws in window_sizes:
                for ep in epochs_list:
                    results_dir = os.path.join("results", f"run_{run_id}")
                    os.makedirs(results_dir, exist_ok=True)
                    
                    config = {
                        "run_id": run_id,
                        "learning_rate": lr,
                        "weight_decay": wd,
                        "window_size": ws,
                        "epochs": ep
                    }
                    with open(os.path.join(results_dir, "config.json"), "w") as f:
                        json.dump(config, f, indent=4)
                        
                    print(f"\n{'='*50}\nEvaluating Config Run {run_id}\n{config}\n{'='*50}")
                    
                    best_val_f1 = train_model(
                        results_dir=results_dir, 
                        epochs=ep, 
                        batch_size=32, 
                        lr=lr, 
                        weight_decay=wd, 
                        window_size=ws
                    )
                    
                    print(f"Evaluating run_{run_id} on test set and generating plots...")
                    evaluate_model(results_dir=results_dir, window_size=ws)
                    
                    if best_val_f1 > best_overall_f1:
                        best_overall_f1 = best_val_f1
                        best_run_id = run_id
                        best_config_dir = results_dir
                        
                    run_id += 1
                    
    print("\n" + "="*50)
    print("GRID SEARCH COMPLETE")
    print("="*50)
    print(f"Best Configuration Run: {best_run_id}")
    print(f"Best Validation F1 Score: {best_overall_f1:.4f}")
    print(f"Results can be found in: {best_config_dir}")

if __name__ == "__main__":
    run_grid_search()
