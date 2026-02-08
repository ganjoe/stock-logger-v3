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

import os
import json
from typing import Optional

# Reuse existing modules
from .service import PortfolioService
from .models import PortfolioPosition

RISK_DATA_FILE = "manual_risk_data.json"

def parse_input_decimal(val_str: str) -> float:
    """Robust parsing of user input for decimal numbers."""
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

def prompt_stop_loss(symbol: str, direction: str, avg_entry: float, current_stop: float = None) -> Optional[float]:
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

def show_menu():
    """Display main menu and return choice."""
    print("\n" + "=" * 60)
    print("📊 STOP-LOSS MANAGER")
    print("=" * 60)
    print("  [1] Neue Stop-Loss Werte eingeben (nur fehlende)")
    print("  [2] Bestehende Einträge bearbeiten")
    print("  [3] Alle Einträge anzeigen")
    print("  [4] Eintrag löschen")
    print("  [5] Marktdaten aktualisieren (DataFetcher)")
    print("  [q] Beenden")
    print("-" * 60)
    return input("Auswahl: ").strip().lower()


def action_add_new(service: PortfolioService):
    """Add stop loss for positions that don't have one yet."""
    print("\n--- Neue Stop-Loss Werte ---")
    positions = service.get_open_positions()
    updated = False
    
    for p in positions:
        if "Missing" not in p.status_flags:
            continue
        
        print(f"\n▶ {p.symbol} ({p.direction} {p.quantity:.2f} @ {p.entry_price:.2f} {p.currency})")
        new_stop = prompt_stop_loss(p.symbol, p.direction, p.entry_price)
        
        if new_stop is not None:
            if service.update_stop_loss(p.symbol, new_stop):
                print(f"  └─ StopLoss gespeichert: {new_stop}")
                updated = True
    
    if not updated:
        print("\nKeine neuen Einträge vorgenommen.")

def action_edit(service: PortfolioService):
    """Edit existing stop loss entries."""
    print("\n--- Bestehende Einträge bearbeiten ---")
    positions = [p for p in service.get_open_positions() if "Missing" not in p.status_flags]
    
    if not positions:
        print("Keine bestehenden Einträge zum Bearbeiten gefunden.")
        return
    
    for i, p in enumerate(positions, 1):
        print(f"  [{i}] {p.symbol:<10} | Stop: {p.stop_loss:>8.2f} | Entry: {p.entry_price:>8.2f}")
    print("  [0] Zurück")
    
    choice = input("\nWähle [1-{}]: ".format(len(positions))).strip()
    try:
        idx = int(choice)
        if idx == 0: return
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            new_stop = prompt_stop_loss(target.symbol, target.direction, target.entry_price, target.stop_loss)
            if new_stop is not None:
                service.update_stop_loss(target.symbol, new_stop)
                print("  ✓ Aktualisiert.")
    except ValueError:
        print("Ungültige Eingabe.")

def action_list():
    """Shows overview of all open positions with stop-loss status and metrics."""
    service = PortfolioService(project_root=".")
    positions = service.get_open_positions(update_prices=False)
    summary = service.get_summary()

    C_RESET, C_BOLD, C_RED, C_GREEN, C_YELLOW = "\033[0m", "\033[1m", "\033[91m", "\033[92m", "\033[93m"

    print("\n--- Übersicht aller offenen Positionen ---")
    print(f"{C_BOLD}{'Symbol':<9} {'Qty':>5} {'Entry':>7} {'Invest':>8} {'Market':>8} {'Unreal.':>9} {'Unr%':>6} {'R':>5} {'Stop':>7} {'Risk':>5} {'Status':<9}{C_RESET}")
    print("-" * 105)
    
    for p in positions:
        mkt_str = f"{p.current_price:>8.1f}" if p.current_price is not None else f"{'---':>8}"
        invest_str = f"{p.market_value:>8.0f}" if p.market_value is not None else f"{'---':>8}"
        unreal_pl_str, unreal_pct_str = f"{'---':>9}", f"{'---':>6}"
        
        if p.unrealized_pl is not None:
            pnl_color = C_GREEN if p.unrealized_pl >= 0 else C_RED
            unreal_pl_str = f"{pnl_color}{p.unrealized_pl:>9.1f}{C_RESET}"
            pct_color = C_GREEN if (p.unrealized_pct or 0) >= 0 else C_RED
            unreal_pct_str = f"{pct_color}{(p.unrealized_pct or 0):>5.1f}%{C_RESET}"
            
        r_str = f"{C_GREEN if (p.r_multiple or 0) >= 0 else C_RED}{(p.r_multiple or 0):>5.1f}{C_RESET}" if p.r_multiple is not None else f"{'---':>5}"
        stop_str = f"{p.stop_loss:>7.1f}" if p.stop_loss else f"{'---':>7}"
        risk_str = f"{p.initial_risk:>5.0f}" if p.initial_risk else f"{'---':>5}"
        
        status_val = p.status_flags[0] if p.status_flags else "Missing"
        status_str = f"{C_GREEN if status_val=='OK' else C_YELLOW if status_val=='Trail' else C_RED}{'✓ OK' if status_val=='OK' else '⚠️ Trail' if status_val=='Trail' else '❌ Miss':<9}{C_RESET}"
            
        sym_display = (p.symbol[:9] + '..') if len(p.symbol) > 9 else p.symbol
        print(f"{sym_display:<9} {p.quantity:>5.0f} {p.entry_price:>7.1f} {invest_str} {mkt_str} {unreal_pl_str} {unreal_pct_str} {r_str} {stop_str} {risk_str} {status_str}")
    
    print("-" * 105)
    pl_sum_color = C_GREEN if summary.total_unrealized_pl >= 0 else C_RED
    print(f"{C_BOLD}SUMMEN:{C_RESET}   Invest: {summary.total_invested:>.0f} | Unreal. P&L: {pl_sum_color}{summary.total_unrealized_pl:>.1f}{C_RESET} | Risk: {summary.total_risk:>.0f}")
    print(f"{C_BOLD}JOURNAL:{C_RESET}  Buying Power: {summary.buying_power:>.2f} | Invested: {summary.total_invested:>.2f} | Equity: {summary.equity:>.2f}")
    print(f"Gesamt: {summary.position_count} Ops | {C_GREEN}✓ {summary.count_ok}{C_RESET} | {C_YELLOW}⚠️ {summary.count_trail}{C_RESET} | {C_RED}❌ {summary.count_missing}{C_RESET}")

def action_delete(service: PortfolioService):
    """Delete stop loss entries via service."""
    print("\n--- Eintrag löschen ---")
    positions = [p for p in service.get_open_positions() if "Missing" not in p.status_flags]
    if not positions:
        print("Keine Einträge zum Löschen vorhanden.")
        return
    for i, p in enumerate(positions, 1):
        print(f"  [{i}] {p.symbol}")
    print("  [0] Zurück")
    choice = input("\nWähle [1-{}]: ".format(len(positions))).strip()
    try:
        idx = int(choice)
        if idx == 0: return
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            if input(f"Wirklich Stop für '{target.symbol}' löschen? [y/N]: ").strip().lower() == 'y':
                service.delete_stop_loss(target.symbol)
                print("  ✓ Gelöscht.")
    except ValueError: print("Ungültige Eingabe.")

def action_update_prices(service: PortfolioService):
    """Force update market prices via service orchestrator."""
    print("\n--- Marktdaten aktualisieren ---")
    service.get_open_positions(update_prices=True)
    print("✓ Marktdaten erfolgreich aktualisiert.")

def main():
    service = PortfolioService(project_root=".")
    while True:
        choice = show_menu()
        if choice == '1': action_add_new(service)
        elif choice == '2': action_edit(service)
        elif choice == '3': action_list()
        elif choice == '4': action_delete(service)
        elif choice == '5': action_update_prices(service)
        elif choice in ['q', 'quit', 'exit']:
            print("\nAuf Wiedersehen!")
            break
        else: print("Ungültige Auswahl.")

if __name__ == "__main__":
    main()
