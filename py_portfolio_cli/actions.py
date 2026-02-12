import time
from py_manage_portfolio.service import PortfolioService

from .utils import clear_terminal, prompt_stop_loss, parse_input_decimal
from .formatter import render_dashboard
from .logger import append_trade_log
from py_manage_portfolio.data_source import OrderManager, OrderRequest, OrderStatus

# --- Order Functions ---

def action_place_order(service: PortfolioService):
    """Interactive order placement via connected broker."""
    ds = service.get_data_source()
    if not ds or not isinstance(ds, OrderManager) or not service.is_broker_connected():
        print("\n❌ Kein Broker verbunden. Order-Platzierung nicht möglich.")
        input("Enter...")
        return

    print("\n--- 🚀 Order Platzieren ---")
    
    # 1. Symbol
    symbol = input(" Symbol (z.B. AAPL): ").strip().upper()
    if not symbol: return

    # 2. Action
    action = input(" Action (BUY/SELL) [BUY]: ").strip().upper() or "BUY"
    if action not in ["BUY", "SELL"]:
        print("Ungültige Action.")
        return

    # 3. Quantity
    try:
        qty_str = input(" Menge (Quantity): ").strip()
        qty = parse_input_decimal(qty_str)
        if qty <= 0: raise ValueError
    except ValueError:
        print("Ungültige Menge.")
        return

    # 4. Order Type
    print(" Order Typen: [1] MKT (Market), [2] LMT (Limit), [3] STP (Stop), [4] STP LMT")
    type_map = {'1': 'MKT', '2': 'LMT', '3': 'STP', '4': 'STP LMT'}
    t_choice = input(" Auswahl [1]: ").strip() or '1'
    order_type = type_map.get(t_choice, 'MKT')

    limit_price = None
    stop_price = None

    # 5. Prices
    if order_type in ['LMT', 'STP LMT']:
        try:
            lmt_str = input(" Limit Preis: ").strip()
            limit_price = parse_input_decimal(lmt_str)
        except ValueError:
            print("Ungültiger Limit Preis.")
            return

    if order_type in ['STP', 'STP LMT']:
        try:
            stp_str = input(" Stop Preis (Aux): ").strip()
            stop_price = parse_input_decimal(stp_str)
        except ValueError:
            print("Ungültiger Stop Preis.")
            return

    # Summary & Confirm
    print("\n📝 Order Übersicht:")
    print(f"  {action} {qty} {symbol} @ {order_type}")
    if limit_price: print(f"  Limit: {limit_price}")
    if stop_price: print(f"  Stop:  {stop_price}")
    
    confirm = input("\n Order wirklich senden? [y/N]: ").strip().lower()
    if confirm == 'y':
        req = OrderRequest(
            symbol=symbol,
            action=action,
            quantity=qty,
            order_type=order_type,
            limit_price=limit_price,
            stop_price=stop_price,
            time_in_force="GTC"
        )
        
        try:
            print(" Sende Order an Broker...")
            order_id = ds.place_order(req)
            if order_id:
                print(f" ✅ Order erfolgreich übermittelt! ID: {order_id}")
                # Log the trade to CSV
                append_trade_log(service, req, order_id)
            else:
                print(" ❌ Order konnte nicht platziert werden (keine ID zurückerhalten).")
        except Exception as e:
            print(f" ❌ Fehler beim Senden: {e}")
    else:
        print(" Abbruch.")
    
    # Removed redundant Enter zum Fortfahren...


def action_show_open_orders(service: PortfolioService):
    """List open orders from broker and allow cancellation."""
    ds = service.get_data_source()
    if not ds or not isinstance(ds, OrderManager) or not service.is_broker_connected():
        print("\n❌ Kein Broker verbunden.")
        input("Enter...")
        return
        
    while True:
        clear_terminal()
        print("\n--- 📋 Order Löschen ---")
        try:
            orders = ds.get_open_orders()
            if not orders:
                print("  Keine offenen Orders.")
                input("\nEnter...")
                return
            
            print(f"{'Nr':<3} {'ID':<10} {'Sym':<6} {'Action':<4} {'Qty':>6} {'Type':<7} {'Lmt/Stp':<10} {'Status':<10}")
            print("-" * 65)
            for i, o in enumerate(orders, 1):
                price_info = ""
                if o.limit_price: price_info += f"L:{o.limit_price} "
                if o.stop_price: price_info += f"S:{o.stop_price}"
                
                print(f"[{i:<1}] {o.order_id:<10} {o.symbol:<6} {o.action:<4} {o.quantity:>6.0f} {o.order_type:<7} {price_info:<10} {o.status.value:<10}")
            
            print("-" * 65)
            print("  Wähle:")
            print("  [Nr]    Selektiere Order (Storno/Ändern)")
            print("  [A]     STORNIERE ALLE")
            print("  [Sym]   Storniere alle für Symbol (z.B. AAPL)")
            print("  [b]     Zurück")
            
            choice = input("\nAuswahl: ").strip().lower()
            
            if choice == 'b':
                return
            
            # 1. Cancel All
            if choice == 'a':
                if input("  ⚠️ Wirklich ALLE offenen Orders stornieren? [y/N]: ").lower() == 'y':
                    print("  Sende Stornierungen...")
                    for o in orders:
                        ds.cancel_order(o.order_id)
                    time.sleep(1)
                continue

            # 2. Try Numeric Selection
            try:
                idx = int(choice)
                if 1 <= idx <= len(orders):
                    target = orders[idx-1]
                    
                    print(f"\n  --- Order {target.order_id} ({target.action} {target.symbol}) ---")
                    print("  [1] ❌ Stornieren (Löschen)")
                    print("  [2] ✏️  Ändern (Preis/Menge)")
                    print("  [0] Zurück")
                    sub_choice = input("  Auswahl: ").strip()
                    
                    if sub_choice == '1':
                        confirm = input(f"  Wirklich stornieren? [y/N]: ").strip().lower()
                        if confirm == 'y':
                            print(f"  Sende Stornierung...")
                            if ds.cancel_order(target.order_id):
                                print("  ✅ Stornierung angefordert.")
                                time.sleep(1)
                            else:
                                print("  ❌ Stornierung fehlgeschlagen.")
                                input("Enter...")
                    
                    elif sub_choice == '2':
                        print(f"\n  --- Order Ändern (leer lassen = unverändert) ---")
                        
                        # Menge
                        qty_str = input(f"  Neue Menge [{target.quantity}]: ").strip()
                        new_qty = float(qty_str) if qty_str else target.quantity
                        
                        # Preise
                        new_lmt = target.limit_price
                        if target.limit_price:
                            lmt_str = input(f"  Neuer Limit-Preis [{target.limit_price}]: ").strip()
                            new_lmt = float(lmt_str) if lmt_str else target.limit_price
                            
                        new_stp = target.stop_price
                        if target.stop_price:
                            stp_str = input(f"  Neuer Stop-Preis [{target.stop_price}]: ").strip()
                            new_stp = float(stp_str) if stp_str else target.stop_price
                            
                        print(f"  Sende Änderung: Qty={new_qty}, Lmt={new_lmt}, Stp={new_stp}...")
                        if ds.modify_order(target.order_id, quantity=new_qty, limit_price=new_lmt, stop_price=new_stp):
                            print("  ✅ Änderung erfolgreich übermittelt.")
                            time.sleep(1)
                        else:
                            print("  ❌ Änderung fehlgeschlagen.")
                            input("Enter...")
                else:
                    print("  Ungültige Nummer.")
                    time.sleep(1)
                continue
            except ValueError:
                pass

            # 3. Check for Symbol Match
            ticker_match = [o for o in orders if o.symbol.lower() == choice]
            if ticker_match:
                if input(f"  ⚠️ Wirklich alle {len(ticker_match)} Orders für {choice.upper()} stornieren? [y/N]: ").lower() == 'y':
                    print(f"  Sende Stornierungen für {choice.upper()}...")
                    for o in ticker_match:
                        ds.cancel_order(o.order_id)
                    time.sleep(1)
            else:
                print("  Ungültige Eingabe oder Symbol nicht gefunden.")
                time.sleep(1)

        except Exception as e:
            print(f"Fehler bei den Orders: {e}")
            input("Enter...")
            return




def action_close_position(service: PortfolioService):
    """Interactive workflow to close an existing position."""
    ds = service.get_data_source()
    if not ds or not isinstance(ds, OrderManager) or not service.is_broker_connected():
        print("\n❌ Kein Broker verbunden.")
        input("Enter...")
        return

    print("\n--- 📉 Position Glattstellen (Close) ---")
    positions = service.get_open_positions()
    
    if not positions:
        print("  Keine offenen Positionen.")
        input("Enter...")
        return
        
    for i, p in enumerate(positions, 1):
        # Determine closing action
        close_action = "SELL" if p.direction == "LONG" else "BUY"
        print(f"  [{i}] {p.symbol:<6} {p.quantity:>6.0f} Stk @ {p.entry_price:.2f}  [Close: {close_action}]")
        
    print("  [0] Abbrechen")
    
    choice = input("\nWelche Position schließen? [1-{}]: ".format(len(positions))).strip()
    try:
        idx = int(choice)
        if idx == 0: return
        
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            close_action = "SELL" if target.direction == "LONG" else "BUY"
            
            print(f"\nClosing: {close_action} {target.quantity} {target.symbol} via MKT Order")
            confirm = input("Ausführen? [y/N]: ").strip().lower()
            
            if confirm == 'y':
                req = OrderRequest(
                    symbol=target.symbol,
                    action=close_action,
                    quantity=target.quantity,
                    order_type="MKT",
                    time_in_force="GTC"
                )
                
                print(" Sende Close-Order...")
                order_id = ds.place_order(req)
                if order_id:
                    print(f" ✅ Order gesendet! ID: {order_id}")
                    # Log
                    append_trade_log(service, req, order_id)
                else:
                    print(" ❌ Fehler beim Senden.")
            else:
                print(" Abgebrochen.")
                
            input("Enter...")
            
    except ValueError:
        print("Ungültige Eingabe.")
    except Exception as e:
        print(f"Fehler: {e}")
        input("Enter...")


# --- Portfolio Actions ---

def action_manage_stops(service: PortfolioService):
    """Interactive stop-loss editor for a selected position."""
    print("\n--- Stop-Loss verwalten ---")
    positions = service.get_open_positions()
    
    for i, p in enumerate(positions, 1):
        stop_val = f"{p.stop_loss:.2f}" if (p.stop_loss or 0) > 0 else "KEIN STOP"
        print(f"  [{i}] {p.symbol:<8} | Entry: {p.entry_price:>8.2f} | Stop: {stop_val}")
    print("  [0] Zurück")
    
    choice = input("\nWähle [1-{}]: ".format(len(positions))).strip()
    try:
        idx = int(choice)
        if idx == 0: return
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            current_stop = target.stop_loss if (target.stop_loss or 0) > 0 else None
            
            print(f"\n▶ {target.symbol} ({target.direction} {target.quantity:.2f} @ {target.entry_price:.2f} {target.currency})")
            
            new_stop = prompt_stop_loss(target.symbol, target.direction, target.entry_price, current_stop)
            
            if new_stop == "REMOVE":
                service.remove_stop_loss(target.symbol)
                render_dashboard(service)
                input("\nEingabe zum Fortfahren...")
            elif new_stop is not None:
                # new_stop is a tuple: (stop_trigger, stop_type, limit_price)
                trigger, s_type, lmt = new_stop
                service.update_stop_loss(target.symbol, trigger, stop_type=s_type, limit_price=lmt)
                print(f"  ✓ {s_type} für {target.symbol} auf {trigger} gesetzt.")
                render_dashboard(service)
                input("\nEingabe zum Fortfahren...")
                
    except ValueError:
        print("Ungültige Eingabe.")


def action_init_paper(service: PortfolioService):
    """Clone live portfolio into simulation."""
    print("\n⚠️  ACHTUNG: Dies überschreibt alle aktuellen Paper-Trades!")
    choice = input("  Live-Portfolio wirklich klonen? [y/N]: ").strip().lower()
    if choice == 'y':
        service.init_from_live()
        print("  ✓ Live-Portfolio erfolgreich in Paper-Umgebung kopiert.")
        render_dashboard(service)
        input("\nEingabe zum Fortfahren...")


def action_edit_paper_position(service: PortfolioService):
    """Sub-menu: Edit/Delete simulation positions (Stop, Qty, Delete)."""
    print("\n--- Simulierte Position bearbeiten ---")
    positions = service.get_open_positions()
    if not positions:
        print("  Keine PP-Positionen vorhanden.")
        return
        
    for i, p in enumerate(positions, 1):
        print(f"  [{i}] {p.symbol:<8} | Qty: {p.quantity:>8.2f} | Stop: {(p.stop_loss or 0):>8.2f}")
    print("  [0] Abbrechen")
    
    choice = input("\nWähle Position [1-{}]: ".format(len(positions))).strip()
    if choice == '0' or not choice: return
    
    try:
        idx = int(choice)
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            print(f"\n▶ {target.symbol} bearbeiten:")
            print("  [1] Ticker löschen")
            print("  [2] Stop-Loss bearbeiten")
            print("  [3] Anzahl (Qty) bearbeiten")
            print("  [0] Zurück")
            
            sub_choice = input("\nAuswahl: ").strip()
            if sub_choice == '1':
                if input(f"  Wirklich {target.symbol} löschen? [y/N]: ").lower() == 'y':
                    try:
                        if hasattr(service, 'delete_position_sim'):
                            service.delete_position_sim(target.symbol)
                        else:
                            service.delete_paper_position(target.symbol)
                        print(f"  ✓ {target.symbol} entfernt.")
                    except AttributeError:
                         print("  ❌ Fehler: Delete-Methode im Service nicht gefunden.")
            elif sub_choice == '2':
                new_stop = prompt_stop_loss(target.symbol, target.direction, target.entry_price, target.stop_loss)
                if new_stop is not None:
                    service.update_stop_loss(target.symbol, new_stop)
                    print(f"  ✓ Stop aktualisiert.")
            elif sub_choice == '3':
                new_qty_in = input(f"  Neue Anzahl (Qty) [aktuell: {target.quantity}]: ").replace(',', '.').strip()
                if new_qty_in:
                    service.update_paper_quantity(target.symbol, float(new_qty_in))
                    print(f"  ✓ Anzahl aktualisiert.")
            
            render_dashboard(service)
            input("\nEingabe zum Fortfahren...")
    except (ValueError, IndexError):
        print("  Ungültige Eingabe.")


def action_edit_paper_metrics(service: PortfolioService):
    """Allows manual editing of paper journal metrics (Equity/Exposure)."""
    equity, _, assets = service._get_journal_metrics()
    
    print("\n--- Portfolio-Metriken anpassen (PAPER) ---")
    print(f"Aktuelle Werte: Equity: {equity:.2f} $ | Exposure: {assets:.2f} $")
    
    try:
        new_eq = input(f"Neue Gesamtequity ($) [{equity:.2f}]: ").replace(',', '.').strip()
        final_eq = float(new_eq) if new_eq else equity
        
        new_exp = input(f"Aktuelles Exposure ($) [{assets:.2f}]: ").replace(',', '.').strip()
        final_exp = float(new_exp) if new_exp else assets
        
        service.update_paper_journal(final_eq, final_exp)
        print("  ✓ Metriken in paper_journal.csv gespeichert.")
        render_dashboard(service)
        input("\nEingabe zum Fortfahren...")
    except ValueError:
        print("  ⚠️ Ungültige Zahleneingabe.")


def action_update_prices(service: PortfolioService):
    """Force update market prices via service orchestrator."""
    print("\n--- Marktdaten aktualisieren ---")
    service.get_open_positions(update_prices=True)
    
    # Save updated snapshot if in live mode
    if service.context == "live" and service.state:
        service.storage.save_portfolio(service.state, "data_portfolio_live_snapshot.json")
        print("✓ Snapshot aktualisiert.")
    
    print("✓ Marktdaten erfolgreich aktualisiert.")
    
    # Show updated dashboard
    clear_terminal()
    render_dashboard(service)
    # Removed redundant Enter zum Fortfahren...


def action_clear_paper(service: PortfolioService):
    """Clear all simulated data after confirmation."""
    print("\n🔥 ACHTUNG: Dies löscht UNWIDERRUFLICH alle simulierten Daten!")
    if input("  Wirklich alles löschen? [y/N]: ").lower() == 'y':
        service.clear_paper_portfolio()
        print("  ✓ Paper-Portfolio geleert.")
        render_dashboard(service)
        input("\nEingabe zum Fortfahren...")


# --- Data Source Switching ---

def action_switch_data_source(service: PortfolioService):
    """Switch between Snapshot and Broker data sources (F-PDS-120)."""
    connected = service.is_broker_connected()
    status = "🟢 Broker (IBKR)" if connected else "📁 Snapshot (Offline)"
    
    print("\n--- Datenquelle wechseln ---")
    print(f"Aktuell: {status}")
    print()
    
    if connected:
        print("  [1] 📁 Disconnect → Snapshot-Modus")
        print("  [0] Zurück")
        choice = input("Auswahl: ").strip()
        if choice == '1':
            service.disconnect_broker()
            print("✓ Disconnected. Snapshot-Modus aktiv.")
    else:
        print("  [1] 🔌 Broker verbinden (CapTrader/IBKR)")
        print("  [0] Zurück")
        choice = input("Auswahl: ").strip()
        if choice == '1':
            _connect_to_broker(service)
    
    input("\nDrücke Enter zum Fortfahren...")


# --- Broker Connection ---

def _connect_to_broker(service: PortfolioService):
    """Helper to connect to IBKR broker."""
    try:
        from py_broker_captrader import BrokerDataSource
    except ImportError:
        print("⚠ py_broker_captrader Modul nicht gefunden.")
        print("  Stelle sicher, dass ib_insync installiert ist: pip install ib_insync")
        return
    
    print("\n--- Broker Verbindung ---")
    print("Voraussetzung: TWS oder IB Gateway muss laufen und eingeloggt sein.")
    print()
    
    host = input("Host [127.0.0.1]: ").strip() or "127.0.0.1"
    port_str = input("Port [4001]: ").strip() or "4001"
    account_id = input("Account ID (leer=auto): ").strip() or None
    
    try:
        port = int(port_str)
    except ValueError:
        print("⚠ Ungültiger Port.")
        return
    
    # Use Master Client ID (0) exclusively as per user request
    client_id = 0
    
    print(f"\nVerbinde zu {host}:{port} (Master Client ID: {client_id})...")
    
    try:
        # Note: BrokerDataSource init now prints "Initialisiere..." and "Abonniere..."
        new_source = BrokerDataSource(
            host=host,
            port=port,
            client_id=client_id,
            account_id=account_id,
            auto_connect=True
        )
        
        if new_source.is_connected():
            service.set_data_source(new_source)
            print("✓ Verbunden mit IBKR!")
            
            # Show available accounts
            accounts = new_source._connection.ib.managedAccounts()
            print(f"  Verfügbare Accounts: {', '.join(accounts)}")
            print(f"  Aktiver Account: {new_source._get_account()}")
            
            # Immediately load live state + save snapshot
            print("  Lade Portfolio-Daten...")
            service.load_portfolio_state()
            if service.state:
                service.storage.save_portfolio(service.state, "data_portfolio_live_snapshot.json")
                pos_count = len(service.state.positions)
                print(f"  ✓ {pos_count} Positionen geladen, Snapshot gespeichert.")
        else:
            print("⚠ Verbindung fehlgeschlagen.")
            
    except ConnectionError as e:
        print(f"\n❌ Verbindungsfehler: {e}")
        print("\n💡 Mögliche Lösungen:")
        print("  1. Prüfen Sie, ob TWS oder IB Gateway wirklich läuft.")
        print(f"  2. Prüfen Sie in TWS/Gateway unter: 'Global Configuration' -> 'API' -> 'Settings':")
        print("     - 'Enable ActiveX and Socket Clients' muss ANGEKREUZT sein.")
        print(f"     - 'Socket Port' muss {port} entsprechen.")
        print("  3. Prüfen Sie, ob 'Trusted IPs' Ihre IP (127.0.0.1) erlauben oder 'Prompt on connection' aktiv ist.")
        print("  4. Stellen Sie sicher, dass keine andere App (z.B. TradingView, Dashboards) Client ID 0 belegt.")
    except Exception as e:
        print(f"\n❌ Unerwarteter Fehler: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
