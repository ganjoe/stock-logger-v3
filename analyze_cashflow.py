
import csv
import glob
import os

def to_float(val_str):
    if not val_str: return 0.0
    # Remove dots (thousands separator) and replace comma with dot (decimal)
    clean_val = val_str.replace('.', '').replace(',', '.')
    try:
        return float(clean_val)
    except ValueError:
        return 0.0

def process_file(filepath):
    deposits = 0.0
    withdrawals = 0.0
    
    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        rows = list(reader)
        
    current_section = None
    headers = {}
    
    SECTION_DEPOSITS = "Einzahlungen & Auszahlungen"
    
    for row in rows:
        if len(row) < 2: continue
        section_name, row_type = row[0].strip(), row[1].strip()
        
        if row_type == "Header":
            current_section = section_name
            headers = {name.strip(): idx for idx, name in enumerate(row)}
            continue
            
        if current_section == SECTION_DEPOSITS and row_type == "Data":
            # Filter out Total/Gesamt lines if any
            if any("Gesamt" in col for col in row): continue
            
            try:
                # Based on previous interaction, amount is in 'Betrag'
                amount_str = row[headers["Betrag"]]
                amount = to_float(amount_str)
                
                # In CapTrader/IB: 
                # Deposits are positive
                # Withdrawals are negative (usually)
                # But let's check description or sign
                
                if amount > 0:
                    deposits += amount
                else:
                    withdrawals += abs(amount) # Track magnitude separately
                    
            except (KeyError, IndexError):
                continue
                
    return deposits, withdrawals

def main():
    oldcsv_dir = "oldcsv"
    files = glob.glob(os.path.join(oldcsv_dir, "*.csv"))
    
    total_deposits = 0.0
    total_withdrawals = 0.0
    
    print(f"{'File':<40} | {'Deposits':>12} | {'Withdrawals':>12} | {'Net Flow':>12}")
    print("-" * 85)
    
    for file in sorted(files):
        dep, wit = process_file(file)
        net = dep - wit
        total_deposits += dep
        total_withdrawals += wit
        
        filename = os.path.basename(file)
        print(f"{filename:<40} | {dep:12.2f} | {wit:12.2f} | {net:12.2f}")
        
    print("-" * 85)
    print(f"{'TOTAL':<40} | {total_deposits:12.2f} | {total_withdrawals:12.2f} | {(total_deposits - total_withdrawals):12.2f}")

if __name__ == "__main__":
    main()
