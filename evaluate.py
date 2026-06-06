import torch
import json
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, ConfusionMatrixDisplay, roc_curve, auc
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

def roi_stock_direction(y_pred_logits, percent_changes):
    """
    ROI calculation going 'all in' based on output sign.
    ROI = Prod(1 + sign(y_pred_logits) * percent_changes) - 1
    """
    # sign(x) is 1 for positive, -1 for negative, 0 for 0
    signs = np.sign(y_pred_logits)
    # If logit is exactly 0, sign is 0. 
    step_returns = signs * percent_changes
    cumulative_returns = np.cumprod(1 + step_returns)
    roi = cumulative_returns[-1] - 1 if len(cumulative_returns) > 0 else 0
    return cumulative_returns, roi

def roi_stock_tanh(y_pred_logits, percent_changes):
    """
    ROI calculation scaling investment by tanh(y_pred_logits).
    ROI = Prod(1 + tanh(y_pred_logits) * percent_changes) - 1
    """
    fractions = np.tanh(y_pred_logits)
    step_returns = fractions * percent_changes
    cumulative_returns = np.cumprod(1 + step_returns)
    roi = cumulative_returns[-1] - 1 if len(cumulative_returns) > 0 else 0
    return cumulative_returns, roi

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

def evaluate_model(results_dir, window_size=5):
    plots_dir = os.path.join(results_dir, "plots")
    os.makedirs(plots_dir, exist_ok=True)
    
    _, _, test_loader = get_dataloaders(window_size=window_size, batch_size=32)
    
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = TimeSeriesClassifier().to(device)
    model_path = os.path.join(results_dir, "best_model.pth")
    
    if not os.path.exists(model_path):
        print(f"Warning: {model_path} not found. Skipping evaluation.")
        return
        
    model.load_state_dict(torch.load(model_path, map_location=device, weights_only=True))
    model.eval()
    
    # Get predictions for the test split
    y_true, y_pred_logits, percent_changes, company_names = get_predictions(model, test_loader, device)
    
    print(f"\nEvaluating Model: {results_dir}")
    
    # 1. Standard Classification Metrics
    y_pred, y_probs, cm = calculate_classification_metrics(y_true, y_pred_logits)
    
    # Save global Confusion Matrix
    disp = ConfusionMatrixDisplay(confusion_matrix=cm, display_labels=[0, 1])
    disp.plot(cmap=plt.cm.Blues)
    plt.title('Global Test Confusion Matrix')
    plt.savefig(os.path.join(plots_dir, 'cm_test.png'))
    plt.close()
    
    # 2. Financial ROI Metrics (Per Company)
    unique_companies = np.unique(company_names)
    
    # Plotting ROI
    plt.figure(figsize=(14, 8))
    
    for comp in unique_companies:
        mask = (company_names == comp)
        comp_logits = y_pred_logits[mask]
        comp_percent_changes = percent_changes[mask]
        
        # Calculate ROIs
        cum_ret_dir, roi_dir = roi_stock_direction(comp_logits, comp_percent_changes)
        cum_ret_tanh, roi_tanh = roi_stock_tanh(comp_logits, comp_percent_changes)
        
        # Baseline Buy and Hold
        baseline_cum_ret = np.cumprod(1 + comp_percent_changes)
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
    plt.title('Cumulative ROI on Test Set (Per Company & Algorithm)')
    plt.xlabel('Trade Steps')
    plt.ylabel('Cumulative Return Multiplier')
    plt.legend(loc='center left', bbox_to_anchor=(1, 0.5))
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(os.path.join(plots_dir, 'cumulative_roi_algorithms.png'))
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
        plt.ylabel('BCE Loss')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'loss_curve.png'))
        plt.close()
        
        plt.figure(figsize=(10, 6))
        plt.plot(history['train_f1'], label='Train F1 Score')
        plt.plot(history['val_f1'], label='Validation F1 Score')
        plt.title('Training vs Validation F1 Score')
        plt.xlabel('Epochs')
        plt.ylabel('F1 Score')
        plt.legend()
        plt.grid(True)
        plt.savefig(os.path.join(plots_dir, 'f1_curve.png'))
        plt.close()

if __name__ == "__main__":
    pass
