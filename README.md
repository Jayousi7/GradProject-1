# Event-Based Stock Movement Prediction

> **Graduation Project 1 - Initial Results**

This repository contains the initial results and baseline models for **Grad Proj 1**. The core objective of this project is to combine text (news headlines) and numerical data to accurately predict stock market trends.

Currently, this repository holds the foundation for evaluating the numerical trading components. 

## Features
- **Company-Level Dataset Splitting:** Ensures accurate temporal splits of financial data without risking data leakage across multiple distinct companies.
- **Hyperparameter Grid Search:** Automated architecture testing across learning rate, weight decay, and window size, encapsulated cleanly into modular run folders (`results/run_1`, `results/run_2`).
- **Financial Evaluation Metrics:** Includes modularized evaluation logic comparing standard classification metrics (Precision, Recall, F1) against vectorized algorithms simulating real-world ROI:
  - **Stock Direction Algorithm:** An "all-in" sign-based trading simulation.
  - **Stock Tanh Algorithm:** A fractional investment simulation driven by the model's confidence logic via hyperbolic tangents.
  - **Per-Company ROI Plotting:** Generates clear graphs depicting strategy ROIs over time vs the Buy & Hold baseline.

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
