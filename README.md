# Event-Based Stock Movement Prediction

> **Graduation Project 1 - Initial Results**

This repository contains the initial results and baseline models for **Grad Proj 1**. The core objective of this project is to combine text (news headlines) and numerical data to accurately predict stock market trends.

Currently, this repository holds the foundation for evaluating the numerical trading components. 

## Features
- **Company-Level Dataset Splitting:** Ensures accurate temporal splits of financial data without risking data leakage across multiple distinct companies.
- **Hyperparameter Grid Search:** Automated architecture testing across:
  - Learning Rate: `[1e-3, 1e-4]`
  - Weight Decay: `[1e-3, 1e-4]`
  - Sliding Window Size (Context): `[30, 60]` days
  - Epochs: `[30, 50]`
  - LSTM Hidden Dimension: `[128, 64]`
  Runs are encapsulated cleanly into modular run folders (e.g., `results/run_1`), containing hyperparameter configs, separated ROI plots per company, test metrics JSON, and dedicated `run.log` files capturing all terminal output. A final `best_model_summary.log` is generated at the end.
- **Financial Evaluation Metrics:** Includes modularized evaluation logic comparing standard classification metrics (Precision, Recall, F1) against vectorized algorithms simulating real-world ROI:
  - **Stock Direction Algorithm:** An "all-in" sign-based trading simulation.
  - **Stock Tanh Algorithm:** A fractional investment simulation driven by the model's confidence logic via hyperbolic tangents.
  - **Per-Company ROI Plotting:** Generates individual graphs depicting strategy ROIs over time vs the Buy & Hold baseline for each evaluated company.

## Architecture Details
- **Input Features:** Rolling window Z-score normalization (matching the 30/60 day sequence length) applied to Return Value, RSI, MACD, Normalized Spread, and VROC.
- **Labeling Target & Loss:** The dataset target is now the continuous raw log percent change of the next day's stock price. The model is trained using a custom `StockTanhLoss`, mapping unscaled output logits to fractional allocations `[-1, 1]` via a `tanh` function. The step returns are calculated by multiplying these allocations directly by the target log returns, and the model maximizes the mean step return across the batch.
- **Model Backbone:** 
  - 1D CNN Feature Extractor to parse initial low-level temporal signals.
  - A 2-Layer Bidirectional LSTM projecting into the specific `hidden_dim` hyperparameter, paired with heavy dropout (0.5) to prevent overfitting.
  - A Multi-Layer Perceptron (MLP) prediction head projecting to unscaled logits.

## Quick Start

### 1. Requirements
Ensure you have the required dependencies installed (e.g., PyTorch, scikit-learn, pandas, matplotlib).

### 2. Run the Grid Search
To kick off the automated training and validation processes, execute the core script:
```powershell
python train.py
```
This will automatically evaluate the dataset combinations and output configuration JSONs alongside model weights, metrics, and visual plots directly into the newly generated `results/` folder!

---
*Note: This repository currently focuses on the preliminary numerical tests. Future updates will incorporate the NLP integration for news headline processing.*
