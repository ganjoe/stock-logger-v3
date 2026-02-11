"""
Portfolio Manager CLI — Main Entry Point.
Contains the main event loop and simulation mode loop.
"""
from datetime import datetime

from py_manage_portfolio.service import PortfolioService

from .menus import show_menu, show_live_menu, show_simulation_menu
from .actions import _connect_to_broker





def main():
    """Main CLI entry point."""
    service_live = PortfolioService(project_root=".", context="live")
    
    while True:
        choice = show_menu(service_live)
        
        if choice == '1': 
             # Portfolio (Live)
             try:
                 show_live_menu(service_live)
             except Exception as e:
                 print(f"Error in Live Menu: {e}")
                 input("Enter...")
        elif choice == '2': 
             # Portfolio (Simulated)
             try:
                 sim_service = PortfolioService(project_root=".", context="sim")
                 show_simulation_menu(sim_service)
             except Exception as e:
                 print(f"Error in Sim Mode: {e}")
                 input("Enter...")
        elif choice == '3': 
             # Broker Connection Toggle
             if not service_live.is_broker_connected():
                 print("\nConnecting to Broker...")
                 _connect_to_broker(service_live)
             else:
                 print("\nDisconnecting...")
                 service_live.disconnect_broker()
                 print("Disconnected. Switched to Snapshot View.")
                 input("Enter...")
                  
        elif choice in ['q', 'quit', 'exit']:
            print("\nAuf Wiedersehen!")
            break
        else: print("Ungültige Auswahl.")


if __name__ == "__main__":
    main()
