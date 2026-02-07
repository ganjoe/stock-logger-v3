#!/usr/bin/env python3
"""
Interactive Stop-Loss Manager for Open Positions.

This script:
1. Parses trades.xml to determine current open positions.
2. Loads existing risk data from manual_risk_data.json.
3. Provides a menu to: Add, Edit, List, or Delete stop-loss entries.
4. Validates stop-loss values and warns on illogical entries.
5. Saves updated risk data.

Usage:
    python run_manage-portfolio.py [--input trades.xml]
"""

import argparse
import json
import os
from decimal import Decimal
from pathlib import Path

# Reuse existing modules
from py_portfolio_history.xml_parser import XmlInputParser
from py_portfolio_history.types import Transaction

RISK_DATA_FILE = "manual_risk_data.json"


def load_risk_data(filepath: str) -> dict:
    """Load existing risk data from JSON file."""
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_risk_data(filepath: str, data: dict):
    """Save risk data to JSON file."""
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n✅ Risk data saved to {filepath}")


def get_open_positions(transactions: list) -> dict:
    """
    Process transactions to find currently open positions.
    Returns: dict[symbol] -> { 'quantity': Decimal, 'avg_entry': Decimal, 'tranches': [...] }
    """
    positions = {}
    
    for t in sorted(transactions, key=lambda x: x.date):
        if t.type not in ["BUY", "SELL"]:
            continue
            
        symbol = t.symbol
        qty = t.quantity
        side = 1 if t.type == "BUY" else -1
        signed_qty = qty * side
        
        if symbol not in positions:
            positions[symbol] = {
                'quantity': Decimal("0"),
                'tranches': [],
                'currency': t.currency,
                'isin': t.isin
            }
        
        pos = positions[symbol]
        
        # Determine if adding or reducing
        current_side = 1 if pos['quantity'] >= 0 else -1
        if pos['quantity'] == 0:
            current_side = side
            
        if side == current_side:
            # Adding to position
            pos['quantity'] += signed_qty
            pos['tranches'].append({
                'date': t.date.strftime("%Y-%m-%d"),
                'quantity': float(qty),
                'price': float(t.price),
                'id': t.id
            })
        else:
            # Reducing position (LIFO)
            remaining = qty
            while remaining > 0 and pos['tranches']:
                tranche = pos['tranches'][-1]
                match_qty = min(remaining, Decimal(str(tranche['quantity'])))
                remaining -= match_qty
                pos['quantity'] -= match_qty * current_side
                
                if match_qty >= Decimal(str(tranche['quantity'])):
                    pos['tranches'].pop()
                else:
                    tranche['quantity'] = float(Decimal(str(tranche['quantity'])) - match_qty)
            
            # Flip logic
            if remaining > 0:
                pos['quantity'] = remaining * side
                pos['tranches'] = [{
                    'date': t.date.strftime("%Y-%m-%d"),
                    'quantity': float(remaining),
                    'price': float(t.price),
                    'id': t.id
                }]
        
        # Cleanup zero positions
        if pos['quantity'] == 0:
            pos['tranches'] = []
    
    # Filter to only open positions
    open_positions = {
        sym: data for sym, data in positions.items() 
        if data['quantity'] != 0 and data['tranches']
    }
    
    return open_positions


def calculate_avg_entry(tranches: list) -> float:
    """Calculate weighted average entry price from tranches."""
    if not tranches:
        return 0.0
    total_cost = sum(t['quantity'] * t['price'] for t in tranches)
    total_qty = sum(t['quantity'] for t in tranches)
    return total_cost / total_qty if total_qty > 0 else 0.0


def make_position_key(symbol: str, entry_date: str) -> str:
    """Create a unique key for a position based on symbol and earliest entry date."""
    return f"{symbol}_{entry_date}"


def validate_stop_loss(direction: str, avg_entry: float, stop_loss: float) -> tuple:
    """
    Validate if stop loss makes sense for the direction.
    Returns: (is_valid, warning_message)
    """
    if direction == "LONG" and stop_loss > avg_entry:
        return (False, f"⚠️  Stop ({stop_loss:.2f}) ist ÜBER Entry ({avg_entry:.2f}) für LONG. Das ist ein Trailing Stop (garantierter Gewinn).")
    elif direction == "SHORT" and stop_loss < avg_entry:
        return (False, f"⚠️  Stop ({stop_loss:.2f}) ist UNTER Entry ({avg_entry:.2f}) für SHORT. Das ist ein Trailing Stop (garantierter Gewinn).")
    return (True, None)


def calculate_initial_risk(direction: str, avg_entry: float, stop_loss: float, qty: float) -> float:
    """Calculate initial risk based on direction."""
    if direction == "LONG":
        risk_per_unit = avg_entry - stop_loss
    else:
        risk_per_unit = stop_loss - avg_entry
    return abs(risk_per_unit * qty)


def prompt_stop_loss(symbol: str, direction: str, avg_entry: float, qty: float, currency: str, current_stop: float = None) -> tuple:
    """
    Prompt for stop loss with validation.
    Returns: (stop_loss, initial_risk) or (None, None) if skipped.
    """
    prompt_text = f"  Enter Stop Loss price"
    if current_stop:
        prompt_text += f" [current: {current_stop}]"
    prompt_text += " (or 'skip'): "
    
    while True:
        user_input = input(prompt_text).strip()
        
        if user_input.lower() in ['skip', 's', '']:
            return (None, None)
        
        try:
            stop_loss = float(user_input.replace(",", "."))
            
            # Validate
            is_valid, warning = validate_stop_loss(direction, avg_entry, stop_loss)
            
            if not is_valid:
                print(f"  {warning}")
                confirm = input("  Trotzdem speichern? [y/N]: ").strip().lower()
                if confirm != 'y':
                    continue
            
            initial_risk = calculate_initial_risk(direction, avg_entry, stop_loss, qty)
            return (stop_loss, round(initial_risk, 2))
            
        except ValueError:
            print("  ⚠ Invalid input. Please enter a number or 'skip'.")


def show_menu():
    """Display main menu and return choice."""
    print("\n" + "=" * 60)
    print("📊 STOP-LOSS MANAGER")
    print("=" * 60)
    print("  [1] Neue Stop-Loss Werte eingeben (nur fehlende)")
    print("  [2] Bestehende Einträge bearbeiten")
    print("  [3] Alle Einträge anzeigen")
    print("  [4] Eintrag löschen")
    print("  [q] Beenden")
    print("-" * 60)
    return input("Auswahl: ").strip().lower()


def action_add_new(open_positions: dict, risk_data: dict, risk_file: str):
    """Add stop loss for positions that don't have one yet."""
    print("\n--- Neue Stop-Loss Werte ---")
    updated = False
    
    for symbol, pos_data in open_positions.items():
        qty = pos_data['quantity']
        direction = "LONG" if qty > 0 else "SHORT"
        avg_entry = calculate_avg_entry(pos_data['tranches'])
        earliest_date = min(t['date'] for t in pos_data['tranches'])
        currency = pos_data['currency']
        pos_key = make_position_key(symbol, earliest_date)
        
        # Skip if already has data
        if pos_key in risk_data:
            print(f"✓ {symbol}: bereits vorhanden (Stop: {risk_data[pos_key].get('stop_loss', 'N/A')})")
            continue
        
        print(f"\n▶ {symbol} ({direction} {abs(qty):.2f} @ {avg_entry:.2f} {currency})")
        print(f"  Entry Date: {earliest_date}")
        
        stop_loss, initial_risk = prompt_stop_loss(symbol, direction, avg_entry, float(abs(qty)), currency)
        
        if stop_loss is not None:
            risk_data[pos_key] = {
                'symbol': symbol,
                'direction': direction,
                'entry_date': earliest_date,
                'avg_entry': avg_entry,
                'stop_loss': stop_loss,
                'quantity': float(abs(qty)),
                'initial_risk': initial_risk,
                'currency': currency
            }
            print(f"  └─ StopLoss: {stop_loss} | InitialRisk: {initial_risk:.2f} {currency}")
            updated = True
        else:
            print("  └─ Übersprungen.")
    
    if updated:
        save_risk_data(risk_file, risk_data)
    else:
        print("\nKeine Änderungen.")


def action_edit(open_positions: dict, risk_data: dict, risk_file: str):
    """Edit existing stop loss entries."""
    print("\n--- Bestehende Einträge bearbeiten ---")
    
    # Build list of editable entries
    entries = []
    for symbol, pos_data in open_positions.items():
        earliest_date = min(t['date'] for t in pos_data['tranches'])
        pos_key = make_position_key(symbol, earliest_date)
        if pos_key in risk_data:
            entries.append((pos_key, symbol, pos_data))
    
    if not entries:
        print("Keine bestehenden Einträge gefunden.")
        return
    
    # Display list
    print("\nWähle Position zum Bearbeiten:")
    for i, (pos_key, symbol, pos_data) in enumerate(entries, 1):
        entry = risk_data[pos_key]
        direction = entry.get('direction', 'LONG')
        avg_entry = entry.get('avg_entry', 0)
        stop_loss = entry.get('stop_loss', 0)
        
        # Check validity
        is_valid, _ = validate_stop_loss(direction, avg_entry, stop_loss)
        status = "✓" if is_valid else "⚠️"
        
        print(f"  [{i}] {status} {symbol}: Entry {avg_entry:.2f}, Stop {stop_loss} ({direction})")
    
    print("  [0] Zurück")
    
    choice = input("\nWähle [1-{}] oder 0: ".format(len(entries))).strip()
    
    try:
        idx = int(choice)
        if idx == 0:
            return
        if 1 <= idx <= len(entries):
            pos_key, symbol, pos_data = entries[idx - 1]
            entry = risk_data[pos_key]
            
            direction = entry.get('direction', 'LONG')
            avg_entry = entry.get('avg_entry', 0)
            current_stop = entry.get('stop_loss', 0)
            qty = entry.get('quantity', 1)
            currency = entry.get('currency', 'EUR')
            
            print(f"\n▶ {symbol} ({direction} {qty:.2f} @ {avg_entry:.2f} {currency})")
            print(f"  Aktueller Stop: {current_stop}")
            
            stop_loss, initial_risk = prompt_stop_loss(symbol, direction, avg_entry, qty, currency, current_stop)
            
            if stop_loss is not None:
                risk_data[pos_key]['stop_loss'] = stop_loss
                risk_data[pos_key]['initial_risk'] = initial_risk
                print(f"  └─ Neuer StopLoss: {stop_loss} | InitialRisk: {initial_risk:.2f} {currency}")
                save_risk_data(risk_file, risk_data)
            else:
                print("  └─ Keine Änderung.")
    except ValueError:
        print("Ungültige Eingabe.")


def action_list(risk_data: dict, open_positions: dict):
    """List all entries with validation status, including missing ones."""
    print("\n--- Übersicht aller offenen Positionen ---")
    
    print(f"{'Symbol':<10} {'Dir':<6} {'Entry':>10} {'Stop':>10} {'Risk':>10} {'Status':<10}")
    print("-" * 66)
    
    count_ok = 0
    count_trail = 0
    count_missing = 0
    
    # Build comprehensive list
    all_positions = {}
    
    # First, add all open positions
    for symbol, pos_data in open_positions.items():
        earliest_date = min(t['date'] for t in pos_data['tranches'])
        pos_key = make_position_key(symbol, earliest_date)
        qty = pos_data['quantity']
        direction = "LONG" if qty > 0 else "SHORT"
        avg_entry = calculate_avg_entry(pos_data['tranches'])
        currency = pos_data['currency']
        
        all_positions[pos_key] = {
            'symbol': symbol,
            'direction': direction,
            'avg_entry': avg_entry,
            'quantity': float(abs(qty)),
            'currency': currency,
            'has_stop': False,
            'stop_loss': None,
            'initial_risk': None
        }
    
    # Then, overlay with risk data
    for pos_key, entry in risk_data.items():
        if pos_key in all_positions:
            all_positions[pos_key]['has_stop'] = True
            all_positions[pos_key]['stop_loss'] = entry.get('stop_loss', 0)
            all_positions[pos_key]['initial_risk'] = entry.get('initial_risk', 0)
    
    # Display sorted by symbol
    for pos_key in sorted(all_positions.keys()):
        pos = all_positions[pos_key]
        symbol = pos['symbol']
        direction = pos['direction']
        avg_entry = pos['avg_entry']
        
        if pos['has_stop']:
            stop_loss = pos['stop_loss']
            initial_risk = pos['initial_risk']
            
            is_valid, _ = validate_stop_loss(direction, avg_entry, stop_loss)
            if is_valid:
                status = "✓ OK"
                count_ok += 1
            else:
                status = "⚠️ Trail"
                count_trail += 1
            
            print(f"{symbol:<10} {direction:<6} {avg_entry:>10.2f} {stop_loss:>10.2f} {initial_risk:>10.2f} {status:<10}")
        else:
            status = "❌ Missing"
            count_missing += 1
            print(f"{symbol:<10} {direction:<6} {avg_entry:>10.2f} {'---':>10} {'---':>10} {status:<10}")
    
    print("-" * 66)
    print(f"Gesamt: {len(all_positions)} Positionen | ✓ {count_ok} OK | ⚠️ {count_trail} Trail | ❌ {count_missing} Missing")


def action_delete(risk_data: dict, risk_file: str):
    """Delete an entry."""
    print("\n--- Eintrag löschen ---")
    
    if not risk_data:
        print("Keine Einträge vorhanden.")
        return
    
    entries = list(risk_data.items())
    
    for i, (pos_key, entry) in enumerate(entries, 1):
        symbol = entry.get('symbol', pos_key)
        print(f"  [{i}] {symbol} (Entry: {entry.get('entry_date', 'N/A')})")
    print("  [0] Zurück")
    
    choice = input("\nWähle [1-{}] oder 0: ".format(len(entries))).strip()
    
    try:
        idx = int(choice)
        if idx == 0:
            return
        if 1 <= idx <= len(entries):
            pos_key, entry = entries[idx - 1]
            confirm = input(f"Wirklich '{entry.get('symbol', pos_key)}' löschen? [y/N]: ").strip().lower()
            if confirm == 'y':
                del risk_data[pos_key]
                save_risk_data(risk_file, risk_data)
                print("  ✓ Gelöscht.")
            else:
                print("  Abgebrochen.")
    except ValueError:
        print("Ungültige Eingabe.")


def main():
    parser = argparse.ArgumentParser(description="Interactive Stop-Loss Manager")
    parser.add_argument("--input", default="trades.xml", help="Input XML file")
    parser.add_argument("--risk-file", default=RISK_DATA_FILE, help="Risk data JSON file")
    args = parser.parse_args()
    
    # Parse transactions
    xml_parser = XmlInputParser()
    transactions = xml_parser.parse_all(args.input)
    
    if not transactions:
        print("No transactions found.")
        return
    
    # Get open positions
    open_positions = get_open_positions(transactions)
    
    print(f"\n📊 {len(open_positions)} offene Position(en) gefunden.")
    
    # Load existing risk data
    risk_data = load_risk_data(args.risk_file)
    
    while True:
        choice = show_menu()
        
        if choice == '1':
            action_add_new(open_positions, risk_data, args.risk_file)
        elif choice == '2':
            action_edit(open_positions, risk_data, args.risk_file)
        elif choice == '3':
            action_list(risk_data, open_positions)
        elif choice == '4':
            action_delete(risk_data, args.risk_file)
        elif choice in ['q', 'quit', 'exit']:
            print("\nAuf Wiedersehen!")
            break
        else:
            print("Ungültige Auswahl.")


if __name__ == "__main__":
    main()
