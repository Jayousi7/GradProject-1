import os
import sys
import pandas as pd

# Reconfigure stdout to UTF-8 to prevent console encoding issues
sys.stdout.reconfigure(encoding='utf-8')

# Dynamically resolve directories relative to the script location
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)

raw_dir = os.path.join(PROJECT_ROOT, "bulletin_staging", "raw")
out_dir = os.path.join(PROJECT_ROOT, "bulletin_staging", "raw_csv")
report_path = os.path.join(PROJECT_ROOT, "bulletin_staging", "raw_csv_structure_report.txt")

if not os.path.exists(out_dir):
    os.makedirs(out_dir)

if not os.path.exists(raw_dir):
    print(f"Error: Raw bulletins directory not found at '{raw_dir}'. Make sure bulletin_staging/raw exists.")
    sys.exit(1)

years = sorted([d for d in os.listdir(raw_dir) if os.path.isdir(os.path.join(raw_dir, d)) and d.isdigit()])

print("Phase 0: Starting Raw-to-CSV Conversion...")
conversion_report = []

for year in years:
    year_raw_dir = os.path.join(raw_dir, year)
    year_out_dir = os.path.join(out_dir, year)
    
    if not os.path.exists(year_out_dir):
        os.makedirs(year_out_dir)
        
    files = os.listdir(year_raw_dir)
    print(f"\nProcessing Year {year}...")
    
    for f in files:
        raw_path = os.path.join(year_raw_dir, f)
        if os.path.isdir(raw_path):
            continue
            
        base_name, _ = os.path.splitext(f)
        out_csv_name = f"{base_name}.csv"
        out_csv_path = os.path.join(year_out_dir, out_csv_name)
        
        print(f"  Converting '{f}' -> '{out_csv_name}'...")
        
        # Read the file header signature to determine format
        is_excel = False
        try:
            with open(raw_path, 'rb') as test_f:
                head_bytes = test_f.read(8)
                # OLE2 signature for .xls or Zip signature for .xlsx
                if head_bytes.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1') or head_bytes.startswith(b'PK\x03\x04'):
                    is_excel = True
        except Exception:
            pass
            
        df = None
        if not is_excel:
            # It's a text TSV file (2010, 2012, 2015, 2016 data/bulletin files)
            # Read TSV with CP1256 encoding for Arabic names
            df = pd.read_csv(raw_path, sep='\t', encoding='cp1256')
        else:
            # Excel file
            try:
                xl = pd.ExcelFile(raw_path)
                # Find the first non-empty sheet
                data_sheet = None
                for sh in xl.sheet_names:
                    temp_df = xl.parse(sh)
                    if temp_df.shape[0] > 0 or temp_df.shape[1] > 0:
                        data_sheet = sh
                        break
                if data_sheet is None:
                    data_sheet = xl.sheet_names[0]
                df = xl.parse(data_sheet)
            except Exception as e:
                print(f"    Error reading Excel: {e}")
                continue
                
        if df is not None:
            # Write to CSV in standard UTF-8-sig so Excel opens Arabic correctly
            df.to_csv(out_csv_path, index=False, encoding='utf-8-sig')
            shape = df.shape
            print(f"    Successfully converted. Shape: {shape}")
            
            conversion_report.append({
                "year": year,
                "original_file": f,
                "csv_file": out_csv_name,
                "shape": shape,
                "columns": list(df.columns),
                "head": df.head(3).to_dict(orient='records')
            })

# Save detailed structure report to a text file
with open(report_path, "w", encoding="utf-8") as rf:
    rf.write("========================================================================\n")
    rf.write("          RAW-TO-CSV CONVERSION AND COLUMN ANALYSIS REPORT              \n")
    rf.write("========================================================================\n\n")
    
    for item in conversion_report:
        rf.write(f"Year: {item['year']}\n")
        rf.write(f"Original File: {item['original_file']}\n")
        rf.write(f"Converted CSV: {item['csv_file']}\n")
        rf.write(f"Shape: {item['shape']}\n")
        rf.write(f"Columns: {item['columns']}\n")
        rf.write("Sample Data (First 3 Rows):\n")
        for i, row in enumerate(item['head']):
            # Clean none/nan representation for clean printing
            clean_row = {k: ("NaN" if pd.isna(v) else v) for k, v in row.items()}
            # Print only first 8 columns to keep it tidy in the report file
            subset_row = {k: clean_row[k] for k in list(clean_row.keys())[:8]}
            rf.write(f"  Row {i+1}: {subset_row} ...\n")
        rf.write("\n" + "-"*80 + "\n\n")

print(f"\nAll files successfully converted. Structure report saved to '{report_path}'.")
