import torch
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, roc_curve, auc, accuracy_score, f1_score
import os

from dataset import get_dataloaders
from network import TimeSeriesClassifier

def calculate_classification_metrics(y_true, y_pred_logits):
    """
    Calculate and print standard classification metrics.
    """
    probs = 1.0 / (1.0 + np.exp(-y_pred_logits))
    y_pred = (probs > 0.5).astype(int)
    
    print("\n--- Standard Classification Metrics ---")
    print(classification_report(y_true, y_pred, zero_division=0))
    
    cm = confusion_matrix(y_true, y_pred)
    print("Confusion Matrix:")
    print(cm)
    return y_pred, probs, cm

def roi_stock_direction(y_pred_logits, log_returns):
    """
    ROI calculation going 'all in' based on output sign.
    Cumulative Log Return = sum(sign * log_returns)
    Cumulative Multiplier = exp(Cumulative Log Return)
    """
    signs = np.sign(y_pred_logits)
    step_log_returns = signs * log_returns
    cumulative_log_returns = np.cumsum(step_log_returns)
    cumulative_multipliers = np.exp(cumulative_log_returns)
    roi = cumulative_multipliers[-1] - 1 if len(cumulative_multipliers) > 0 else 0
    return cumulative_multipliers, roi

def roi_stock_tanh(y_pred_logits, log_returns):
    """
    ROI calculation scaling investment by tanh(y_pred_logits).
    Cumulative Log Return = sum(tanh * log_returns)
    Cumulative Multiplier = exp(Cumulative Log Return)
    """
    fractions = np.tanh(y_pred_logits)
    step_log_returns = fractions * log_returns
    cumulative_log_returns = np.cumsum(step_log_returns)
    cumulative_multipliers = np.exp(cumulative_log_returns)
    roi = cumulative_multipliers[-1] - 1 if len(cumulative_multipliers) > 0 else 0
    return cumulative_multipliers, roi

def get_predictions(model, dataloader, device):
    all_logits = []
    all_targets = []
    all_raw_returns = []
    all_company_names = []
    
    with torch.no_grad():
        for features, targets, raw_rets, comp_names in dataloader:
            features = features.to(device)
            logits = model(features).squeeze(-1)
            
            all_logits.extend(logits.cpu().numpy())
            all_targets.extend(targets.numpy())
            all_raw_returns.extend(raw_rets.numpy())
            all_company_names.extend(comp_names)
            
    return np.array(all_targets), np.array(all_logits), np.array(all_raw_returns), np.array(all_company_names)

def evaluate_model(results_dir, window_size=5, hidden_dim=32):
    plots_dir = os.path.join(results_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    _, _, test_loader = get_dataloaders(window_size=window_size, batch_size=32)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = TimeSeriesClassifier(hidden_dim=hidden_dim).to(device)
    model_path = os.path.join(results_dir, "best_model.pth")
    
    if not os.path.exists(model_path):
        print(f"Warning: {model_path} not found. Skipping evaluation.")
        return
        
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    
    # Get predictions for the test split
    y_true, y_pred_logits, percent_changes, company_names = get_predictions(model, test_loader, device)
    
    print(f"\nEvaluating Model: {results_dir}")
    
    # 1. Standard Classification Metrics (Supplementary via Binarization)
    y_true_bin = (y_true > 0).astype(int)
    y_pred, y_probs, cm = calculate_classification_metrics(y_true_bin, y_pred_logits)
    
    test_acc = accuracy_score(y_true_bin, y_pred)
    test_f1 = f1_score(y_true_bin, y_pred, zero_division=0)
    
    # Calculate global Test ROI (Mean Step Multiplier)
    test_roi = np.exp(np.tanh(y_pred_logits) * y_true).mean()
    
    # Extract Train/Val metrics from history and save final metrics JSON
    history_path = os.path.join(results_dir, "training_history.json")
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
            
        best_epoch = np.argmax(history['val_roi'])
        metrics = {
            "train_roi": history['train_roi'][best_epoch],
            "val_roi": history['val_roi'][best_epoch],
            "test_roi": float(test_roi),
            "test_acc_bin": float(test_acc),
            "test_f1_bin": float(test_f1)
        }
    else:
        metrics = {
            "test_roi": float(test_roi),
            "test_acc_bin": float(test_acc),
            "test_f1_bin": float(test_f1)
        }
        
    with open(os.path.join(results_dir, "final_metrics.json"), "w") as f:
        json.dump(metrics, f, indent=4)
    
    # Save global Confusion Matrix
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=[0, 1])
    disp.plot(cmap=plt.cm.Blues)
    plt.title('Global Test Confusion Matrix')
    plt.savefig(os.path.join(plots_dir, 'cm_test.png'))
    plt.close()
    
    # 2. Financial ROI Metrics (Per Company)
    unique_companies = np.unique(company_names)
    
    # Plotting ROI
    for comp in unique_companies:
        plt.figure(figsize=(14, 8))
        mask = (company_names == comp)
        comp_logits = y_pred_logits[mask]
        comp_percent_changes = percent_changes[mask]
        
        # Calculate ROIs
        cum_ret_dir, roi_dir = roi_stock_direction(comp_logits, comp_percent_changes)
        cum_ret_tanh, roi_tanh = roi_stock_tanh(comp_logits, comp_percent_changes)
        
        # Baseline Buy and Hold
        baseline_cum_log_ret = np.cumsum(comp_percent_changes)
        baseline_cum_ret = np.exp(baseline_cum_log_ret)
        baseline_roi = baseline_cum_ret[-1] - 1 if len(baseline_cum_ret) > 0 else 0
        
        print(f"\n--- ROI Metrics for {comp} ---")
        print(f"Stock Direction ROI: {roi_dir:.4f}")
        print(f"Stock Tanh ROI:      {roi_tanh:.4f}")
        print(f"Baseline ROI:        {baseline_roi:.4f}")
        
        # Plot curves for this company
        plt.plot(cum_ret_dir, label=f'{comp} - Stock Direction', linestyle='-')
        plt.plot(cum_ret_tanh, label=f'{comp} - Stock Tanh', linestyle='--')
        plt.plot(baseline_cum_ret, label=f'{comp} - Baseline', linestyle=':', alpha=0.5)

        plt.axhline(y=1.0, color='r', linestyle='-', alpha=0.3, label='Breakeven')
        plt.title(f'Cumulative ROI on Test Set - {comp}')
        plt.xlabel('Trade Steps')
        plt.ylabel('Cumulative Return Multiplier')
        plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(os.path.join(plots_dir, f'cumulative_roi_{comp.replace(".csv", "")}.png'))
        plt.close()
    
    # Training History Plots (if exists)
    history_path = os.path.join(results_dir, "training_history.json")
    if os.path.exists(history_path):
        with open(history_path, "r") as f:
            history = json.load(f)
            
        plt.figure(figsize=(10, 6))
        plt.plot(history['train_loss'], label='Train Loss')
        plt.plot(history['val_loss'], label='Validation Loss')
        plt.title('Training vs Validation Loss')
        plt.xlabel('Epochs')
        plt.ylabel('Stocktanh Loss')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'loss_curve.png'))
        plt.close()
        
        plt.figure(figsize=(10, 6))
        plt.plot(history['train_roi'], label='Train Mean ROI')
        plt.plot(history['val_roi'], label='Validation Mean ROI')
        plt.title('Training vs Validation Mean ROI')
        plt.xlabel('Epochs')
        plt.ylabel('Mean ROI Multiplier')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'roi_curve.png'))
        plt.close()

if __name__ == "__main__":
    pass
