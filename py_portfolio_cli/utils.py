"""
CLI Utility Functions.
Pure helpers with no dependencies on the service layer.
"""
import os
from typing import Optional


def clear_terminal():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def parse_input_decimal(val_str: str) -> float:
    """Robust parsing of user input for decimal numbers (handles ',' and '.')."""
    if not val_str: return 0.0
    val_str = val_str.strip()
    if '.' in val_str and ',' in val_str:
        dot_idx = val_str.rfind('.')
        comma_idx = val_str.rfind(',')
        clean = val_str.replace(',', '') if dot_idx > comma_idx else val_str.replace('.', '').replace(',', '.')
    elif ',' in val_str:
        clean = val_str.replace(',', '.')
    else:
        clean = val_str
    try:
        return float(clean)
    except ValueError:
        return 0.0


def prompt_stop_loss(symbol: str, direction: str, avg_entry: float, 
                      current_stop: float = None) -> Optional[tuple]:
    """
    Prompt for stop loss with simple UI validation.
    Returns: (stop_price, stop_type, limit_price) or "REMOVE" or None
    """
    prompt_text = f"  Enter Stop Trigger price"
    if current_stop:
        prompt_text += f" [current: {current_stop}]"
    prompt_text += " (or 'remove' / 'skip'): "
    
    while True:
        user_input = input(prompt_text).strip().lower()
        if user_input in ['remove', 'r']:
            return "REMOVE"
        if user_input in ['skip', 's', '']:
            return None
        
        try:
            stop_trigger = parse_input_decimal(user_input)
            if stop_trigger <= 0:
                print("  ⚠ Invalid price.")
                continue

            # 2. Choose Type
            print("  Order Typ: [1] STP (Market), [2] STP LMT (Limit)")
            t_choice = input("  Auswahl [1]: ").strip() or "1"
            stop_type = "STP LMT" if t_choice == "2" else "STP"
            
            limit_price = None
            if stop_type == "STP LMT":
                # Prefill with 1 cent difference based on direction
                # LONG position -> SELL stop -> Limit below Trigger
                # SHORT position -> BUY stop -> Limit above Trigger
                default_limit = stop_trigger - 0.01 if direction == "LONG" else stop_trigger + 0.01
                
                lmt_input = input(f"  Enter Limit Price for {symbol} [{default_limit:.2f}]: ").strip()
                if not lmt_input:
                    limit_price = default_limit
                else:
                    limit_price = parse_input_decimal(lmt_input)
                
                if limit_price <= 0:
                    print("  ⚠ Invalid limit price.")
                    continue

            # Simple validation warning
            if direction == "LONG" and stop_trigger > avg_entry:
                print(f"  ⚠️  Trigger ist ÜBER Entry ({avg_entry:.2f}) für LONG.")
                if input("  Trotzdem speichern? [y/N]: ").strip().lower() != 'y':
                    continue
            elif direction == "SHORT" and stop_trigger < avg_entry:
                print(f"  ⚠️  Trigger ist UNTER Entry ({avg_entry:.2f}) für SHORT.")
                if input("  Trotzdem speichern? [y/N]: ").strip().lower() != 'y':
                    continue
                    
            return (stop_trigger, stop_type, limit_price)
        except ValueError:
            print("  ⚠ Invalid input.")
