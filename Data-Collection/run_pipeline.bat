@echo off
:: Change directory to the folder containing this batch script (project root)
cd /d "%~dp0"

echo =====================================================================
echo          ASE DATA COLLECTION ^& ETL AUTOMATION PIPELINE RUN           
echo =====================================================================
echo.
echo Date and Time: %date% %time%
echo.

echo [1/3] Step 1: Downloading daily ASE lists (Phase 3 scraper)...
python 03_daily_scraping/download_and_process.py > daily_run.log 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [-] Error during Phase 3 Daily Scraping! Check daily_run.log
    exit /b %errorlevel%
)

echo [2/3] Step 2: Unifying historical bulletins with daily run (Phase 4)...
python 04_unification/unify_multi_era_data.py >> daily_run.log 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [-] Error during Phase 4 Data Unification! Check daily_run.log
    exit /b %errorlevel%
)

echo [3/3] Step 3: Computing technical indicators and feature engineering (Phase 5)...
python 05_feature_engineering/generate_features.py >> daily_run.log 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [-] Error during Phase 5 Feature Engineering! Check daily_run.log
    exit /b %errorlevel%
)

echo.
echo =====================================================================
echo       [SUCCESS] Automation completed successfully with zero loss      
echo =====================================================================
echo Details and logs saved to: %~dp0daily_run.log
echo.
