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
                     current_stop: float = None) -> Optional[float]:
    """Prompt for stop loss with simple UI validation."""
    prompt_text = f"  Enter Stop Loss price"
    if current_stop:
        prompt_text += f" [current: {current_stop}]"
    prompt_text += " (or 'skip'): "
    
    while True:
        user_input = input(prompt_text).strip()
        if user_input.lower() in ['skip', 's', '']:
            return None
        
        try:
            stop_loss = parse_input_decimal(user_input)
            
            # Simple validation warning
            if direction == "LONG" and stop_loss > avg_entry:
                print(f"  ⚠️  Stop ist ÜBER Entry ({avg_entry:.2f}) für LONG.")
                if input("  Trotzdem speichern? [y/N]: ").strip().lower() != 'y':
                    continue
            elif direction == "SHORT" and stop_loss < avg_entry:
                print(f"  ⚠️  Stop ist UNTER Entry ({avg_entry:.2f}) für SHORT.")
                if input("  Trotzdem speichern? [y/N]: ").strip().lower() != 'y':
                    continue
                    
            return stop_loss
        except ValueError:
            print("  ⚠ Invalid input.")
