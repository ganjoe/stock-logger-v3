"""
Menu Renderers for Portfolio Manager CLI.
Displays main menu, live sub-menu, and simulation sub-menu.
"""
import time
from typing import Optional

from py_manage_portfolio.service import PortfolioService

from .utils import clear_terminal
from .formatter import render_dashboard
from .wizard import run_sizing_wizard
from .actions import (
    action_manage_stops, action_update_prices,
    action_init_paper, action_edit_paper_position,
    action_edit_paper_metrics, action_clear_paper,
    action_switch_data_source,
    action_place_order, action_show_open_orders,
    action_close_position
)


def show_menu(service: PortfolioService) -> str:
    """Display main menu v2.0 (Live/Sim/Connect) and return choice."""
    clear_terminal()
    
    # Header Status
    c_bold = "\033[1m"
    c_green = "\033[92m"
    c_red = "\033[91m"
    c_reset = "\033[0m"
    
    ds = service.get_data_source()
    from py_manage_portfolio.data_source import ConnectionAware
    is_connected = isinstance(ds, ConnectionAware) and ds.is_connected()
        
    status_icon = f"{c_green}🟢 ONLINE{c_reset}" if is_connected else f"{c_red}🔴 OFFLINE{c_reset}"
    source_name = type(ds).__name__
    
    print("\n" + "=" * 60)
    print(f"{c_bold}📊 PORTFOLIO MANAGER 2.0{c_reset}  [{status_icon}]")
    print(f"   Source: {source_name}")
    print("=" * 60)
    
    print("  [1] 📈 Portfolio (Live)")
    print("      (Trading, Wizard, Stops, Display)")
    print()
    print("  [2] 🧪 Portfolio (Simulated)")
    print("      (Planning, Testing, Display)")
    print()
    print("  [3] 🔌 Broker Verbindung (Toggle)")
    print("-" * 60)
    print("  [q] Beenden")
    print("-" * 60)
    return input("Auswahl: ").strip().lower()


def show_live_menu(service: PortfolioService):
    """Sub-menu loop for Live Portfolio."""
    while True:
        clear_terminal()
        render_dashboard(service)
        
        print("\n=== 📈 LIVE PORTFOLIO ===")
        print(" [1] 📤 Trading (Order Entry)")
        print(" [2] 📝 Minervini Wizard (Live -> Order)")
        print(" [3] 🔄 Portfolio & Preise aktualisieren (Sync)")
        print(" [4] 🛑 Stop-Loss Manager")
        print(" [5] 📋 Order Löschen")
        print(" [6] 📊 Portfolio anzeigen (Sortierbar)")
        print(" [7] 📉 Position glattstellen (Close)")
        print("-" * 40)
        print(" [b] Zurück")
        
        choice = input("Auswahl: ").strip().lower()
        if choice == 'b': return
        elif choice == '1':
             action_place_order(service)
             # Force refresh after order
             action_update_prices(service)
        elif choice == '2':
             run_sizing_wizard(service, source="live")
        elif choice == '3':
             action_update_prices(service)
        elif choice == '4':
             action_manage_stops(service)
        elif choice == '5':
             action_show_open_orders(service)
        elif choice == '6':
             show_portfolio_viewer(service)
        elif choice == '7':
             action_close_position(service)
             action_update_prices(service)


def show_simulation_menu(service: PortfolioService):
    """Sub-menu loop for Simulated Portfolio."""
    while True:
        clear_terminal()
        render_dashboard(service)
        
        c_cyan = "\033[96m"
        c_bold = "\033[1m"
        c_reset = "\033[0m"
        print("\n" + "=" * 60)
        print(f"{c_cyan}{c_bold}🧪 PORTFOLIO SIMULATION & PLANUNG{c_reset}")
        print("=" * 60)
        print("  [1] Live-Portfolio importieren (Snapshot Clone)")
        print("  [2] Manuell Position bearbeiten (Add/Edit/Del)")
        print("  [3] Minervini Wizard (Sim -> Save)")
        print("  [4] Simulation zurücksetzen")
        print("  [5] 📊 Portfolio anzeigen (Sortierbar)")
        print("-" * 60)
        print("  [b] Zurück zum Hauptmenü")
        print("-" * 60)
        
        choice = input("Auswahl: ").strip().lower()
        if choice in ['b', 'back']:
            return
            
        if choice == '1': 
             # Import Live
             service.init_from_live()
             input("Import Done. Enter...")
        elif choice == '2':
             # Manual Add/Edit Sub-Menu
             print("\n --- Manuell ---")
             print(" [1] Add Position")
             print(" [2] Edit/Delete Position")
             sc = input(" > ").strip()
             if sc == '1':
                  try:
                      from datetime import datetime
                      print("\n--- Add Position ---")
                      sym = input(" Symbol: ").strip().upper()
                      if sym:
                          qty = float(input(" Quantity: "))
                          price = float(input(" Price: "))
                          service.add_position_sim(sym, qty, price, datetime.now().strftime("%Y-%m-%d"))
                  except Exception as e: print(f"Error: {e}")
             elif sc == '2':
                  from .actions import action_edit_paper_position
                  action_edit_paper_position(service)
             input("Enter...")
        elif choice == '3':
             # Sim Wizard
             run_sizing_wizard(service, source="sim")
        elif choice == '4':
             # Reset
             service.storage.save_portfolio(service.storage._create_empty_state(), "data_portfolio_simulation.json")
             service.load_portfolio_state()
             print("Simulation zurückgesetzt.")
             input("Enter...")
        elif choice == '5':
             show_portfolio_viewer(service)
        else:
            print("  Ungültige Auswahl.")


def show_portfolio_viewer(service: PortfolioService):
    """View-only dashboard with interactive sorting."""
    while True:
        clear_terminal()
        render_dashboard(service) # Uses global SESSION_SORT_BY
        
        print("\n=== 📊 PORTFOLIO ANSICHT (SORTIERBAR) ===")
        print(" Wähle [1-12] zum Sortieren nach Spalte")
        print(" [r] 🔄 Daten aktualisieren (Sync)")
        print(" [b] Zurück zum Hauptmenü")
        print("-" * 40)
        
        choice = input("Sortierung/Aktion: ").strip().lower()
        if choice == 'b':
            return
        if choice == 'r':
            from .actions import action_update_prices
            action_update_prices(service)
        elif choice in [str(i) for i in range(1, 13)]:
            render_dashboard(service, sort_by=choice) # Updates global SESSION_SORT_BY
