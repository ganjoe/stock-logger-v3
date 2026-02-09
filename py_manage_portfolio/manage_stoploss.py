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
from .models import PortfolioPosition, PortfolioSummary, SizingContext, TradeParameters, SizingResult
from .sizer import MinerviniSizer

def clear_terminal():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')

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

def show_menu(service: PortfolioService):
    """Display main menu and return choice."""
    clear_terminal()
    action_list(service)  # Always show the list at the top
    
    c_bold, c_yellow, c_reset = "\033[1m", "\033[93m", "\033[0m"
    
    # Show current data source
    source_name = type(service.get_data_source()).__name__
    source_indicator = "📁 Offline" if "Offline" in source_name else "🔌 Broker"
    
    print("\n" + "=" * 60)
    print(f"{c_bold}📊 PORTFOLIOMANAGER{c_reset}  [{source_indicator}]")
    print("=" * 60)
    print("  [1] Stop-Loss bearbeiten (LIVE)")
    print("  [2] Liste aller Positionen (LIVE)")
    print("  [3] Marktdaten aktualisieren (LIVE)")
    print("  [4] 📄 Minervini Wizard (Live)")
    print("  [5] 🧪 Simulation & Paper Portfolio")
    print("-" * 60)
    print("  [D] Datenquelle wechseln")
    print("  [q] Beenden")
    print("-" * 60)
    return input("Auswahl: ").strip().lower()

def show_paper_menu(service: PortfolioService):
    """Display paper trading menu."""
    clear_terminal()
    action_list(service) # Always show the simulated list at the top
    
    c_cyan = "\033[96m"
    c_bold = "\033[1m"
    c_reset = "\033[0m"
    print("\n" + "=" * 60)
    print(f"{c_cyan}{c_bold}📄 TRADE PLANER (PAPER TRADING){c_reset}")
    print("=" * 60)
    print("  [1] Minervini Wizard (Live)  // Start with Live Metrics")
    print("  [2] Minervini Wizard (Paper) // Start with Paper Metrics")
    print("  [3] Live-Portfolio kopieren (Init from Live)")
    print("  [4] Liste simulierte Positionen anzeigen")
    print("  [5] Simulierte Position bearbeiten (Löschen/Stop/Qty)")
    print("  [6] 🔥 Alle simulierten Positionen löschen")
    print("  [7] 💰 Portfolio-Metriken (Equity/Exposure) anpassen")
    print("-" * 60)
    print("  [b] Zurück zum Hauptmenü")
    print("-" * 60)
    return input("Auswahl: ").strip().lower()

def action_manage_stops(service: PortfolioService):
    """Wait for user to select a position to edit stop loss."""
    print("\n--- Stop-Loss verwalten ---")
    positions = service.get_open_positions()
    
    for i, p in enumerate(positions, 1):
        stop_val = f"{p.stop_loss:.2f}" if p.stop_loss > 0 else "KEIN STOP"
        print(f"  [{i}] {p.symbol:<8} | Entry: {p.entry_price:>8.2f} | Stop: {stop_val}")
    print("  [0] Zurück")
    
    choice = input("\nWähle [1-{}]: ".format(len(positions))).strip()
    try:
        idx = int(choice)
        if idx == 0: return
        if 1 <= idx <= len(positions):
            target = positions[idx-1]
            current_stop = target.stop_loss if target.stop_loss > 0 else None
            
            print(f"\n▶ {target.symbol} ({target.direction} {target.quantity:.2f} @ {target.entry_price:.2f} {target.currency})")
            
            new_stop = prompt_stop_loss(target.symbol, target.direction, target.entry_price, current_stop)
            
            if new_stop is not None:
                # new_stop can be 0.0
                service.update_stop_loss(target.symbol, new_stop)
                print(f"  ✓ Stop für {target.symbol} auf {new_stop} gesetzt.")
                action_list(service) 
                input("\nEingabe zum Fortfahren...")
                
    except ValueError:
        print("Ungültige Eingabe.")


def wizard_step_1_get_context(service: PortfolioService, sizer: MinerviniSizer, source: str = "live") -> SizingContext:
    print("\n" + "=" * 50)
    print(" SCHRITT 1: PORTFOLIO STATUS")
    print("=" * 50)
    
    # Get defaults from selected source
    if source == "live":
        # Hacky way to get live metrics if service is paper context:
        # We need a live service instance or just re-read the live journal.
        # Since we are inside the paper loop, service is likely paper context.
        # Let's instantiate a temporary Live Service here.
        temp_live = PortfolioService(project_root=service.project_root, context="live")
        equity, _, total_assets = temp_live._get_journal_metrics()
        print(f" (Lade Daten aus LIVE Journal...)")
    else:
        # Paper metrics: Now correctly synced via auto-update in service
        equity, _, total_assets = service._get_journal_metrics()
        print(f" (Lade Daten aus PAPER Journal...)")

    current_exposure = total_assets 
    defaults = sizer.get_defaults()
    
    # If in Paper Mode, we might want to use paper metrics? 
    # For now, let's use the Journal metrics as base but allow override.
    # Actually, if we are in Paper Planner, we should probably use Paper metrics?
    # The requirement says: "Known values are queried (corresponding to live or paper)."
    # Since this script can be run in context 'paper' or 'live', check service.context?
    # Service context is not exposed directly cleanly, but we can check if service.project_root has paper-risk_data.json?
    # Let's just ask user with defaults from Journal.
    
    print("Bitte aktuelle Kontodaten eingeben:")
    
    eq_in = input(f"Total Equity ($) [{equity:.2f}]: ").replace(',', '.').strip()
    final_equity = float(eq_in) if eq_in else equity
    
    exp_in = input(f"Aktuelles Exposure ($) [{current_exposure:.2f}]: ").replace(',', '.').strip()
    final_exposure = float(exp_in) if exp_in else current_exposure
    
    target_pct_in = input(f"Ziel-Exposure % (z.B. 120 für Margin) [100]: ").replace(',', '.').strip()
    final_target = float(target_pct_in) if target_pct_in else 100.0
    
    ctx = sizer.calculate_wallet_context(final_equity, final_exposure, final_target)
    
    # Persist if in paper mode or using paper source
    if source == "paper":
        service.update_paper_journal(final_equity, final_exposure)

    print("\n" + "-" * 50)
    print(" >> STATUS CHECK:")
    target_val = final_equity * (final_target / 100.0)
    print(f" Ziel-Kapital:    {target_val:,.2f} $ ({final_target:.2f} %)")
    print(f" Bereit invest.:  {final_exposure:,.2f} $ ({(final_exposure/final_equity*100 if final_equity else 0):.2f} %)")
    print("-" * 50)
    print(f" >> VERFÜGBARES BUDGET: {ctx.available_budget:,.2f} $")
    print("=" * 50)
    return ctx

def wizard_step_2_get_params(service: PortfolioService, sizer: MinerviniSizer) -> TradeParameters:
    print("\n" + "=" * 50)
    print(" SCHRITT 2: TRADE PARAMETER")
    print("=" * 50)
    print("Neuen Trade planen:\n")
    
    symbol = input("Ticker Symbol: ").strip().upper()
    if not symbol: return None
    
    # Hint Price
    asset = service.data_fetcher.get_asset(symbol, symbol)
    hint_price = asset.market_price if asset else 0.0
    
    p_in = input(f"Entry Price ($) [{hint_price}]: ").replace(',', '.').strip()
    entry = float(p_in) if p_in else hint_price
    
    s_in = input("Stop Loss ($): ").replace(',', '.').strip()
    stop = float(s_in) if s_in else 0.0
    
    defaults = sizer.get_defaults()
    def_risk = defaults.get("default_risk_pct", 1.0)
    def_max_pos = defaults.get("max_pos_size_pct", 25.0)
    def_fee = defaults.get("default_fee", 2.0)
    
    r_in = input(f"Max Risk an Equity % (Standard {def_risk}): ").replace(',', '.').strip()
    risk = float(r_in) if r_in else def_risk
    
    m_in = input(f"Max Position Size % (Standard {def_max_pos}): ").replace(',', '.').strip()
    max_pos = float(m_in) if m_in else def_max_pos
    
    f_in = input(f"Est. Fee (One-Way $) [{def_fee}]: ").replace(',', '.').strip()
    fee = float(f_in) if f_in else def_fee
    
    return TradeParameters(symbol, entry, stop, risk, max_pos, fee)

def run_sizing_wizard(service: PortfolioService, source: str = "live"):
    sizer = MinerviniSizer(service.project_root)
    
    # Step 1
    ctx = wizard_step_1_get_context(service, sizer, source=source)
    
    # Step 2
    params = wizard_step_2_get_params(service, sizer)
    if not params: return
    
    # Step 3: Analysis
    result = sizer.calculate_sizing(ctx, params)
    
    print("\n" + "=" * 50)
    print(f" SCHRITT 3: ANALYSE & LIMITS ({params.symbol})")
    print("=" * 50)
    
    risk_per_share = abs(params.entry_price - params.stop_loss)
    dist_pct = (risk_per_share / params.entry_price * 100) if params.entry_price else 0
    print(f"Stop Distanz:      -{dist_pct:.2f} %  ({risk_per_share:.2f} $ Risk/Share)")
    print("\nDER TRICHTER (Vergleich der Limits):")
    
    def fmt_limit(name, shares, is_bottleneck):
        marker = " [LIMITIERENDER FAKTOR]" if is_bottleneck else ""
        return f"{name:<25}: Max. {shares:>4} Stk.{marker}"

    print(fmt_limit(f"1. Nach RISIKO ({params.risk_pct}%)", result.limit_risk_shares, result.bottleneck == "RISK"))
    print(fmt_limit(f"2. Nach SIZE CAP ({params.max_position_pct}%)", result.limit_size_shares, result.bottleneck == "SIZE CAP"))
    print(fmt_limit(f"3. Nach BUDGET (Rest)", result.limit_budget_shares, result.bottleneck == "BUDGET"))

    print(f"\n>> VORSCHLAG: {result.suggested_shares} Stück")
    
    if result.warnings:
        print(f"\n⚠️  Warnungen: {', '.join(result.warnings)}")

    print("\nMöchtest du diesen Wert manuell überschreiben?")
    ov_in = input(f"Eingabe 'Stückzahl' oder [ENTER] um {result.suggested_shares} zu akzeptieren: ").strip()
    
    final_shares = int(ov_in) if ov_in else result.suggested_shares
    
    # Re-calculate metrics for final shares if changed?
    # We can just update the result object loosely or display based on calculation.
    invested = final_shares * params.entry_price
    risk_total = (final_shares * risk_per_share) + (2 * params.one_way_fee)
    
    # Step 4: Summary & Commit
    print("\n" + "=" * 50)
    print(f" PLANUNGSERGEBNIS: {params.symbol}")
    print("=" * 50)
    print(" STATUS UPDATE (Simulation):")
    new_exposure = ctx.current_exposure + invested
    new_exp_pct = (new_exposure / ctx.equity * 100) if ctx.equity else 0
    new_budget = ctx.available_budget - invested
    print(f" >> Exposure Neu:     {new_exp_pct:.2f} % (Ziel: {ctx.target_exposure_pct:.2f} %)")
    print(f" >> Budget Rest:      {new_budget:,.2f} $")
    print("-" * 50)
    print(" ORDER SETUP (Broker):")
    print(f" >> ENTRY (Limit):    {params.entry_price:.2f} $")
    print(f" >> STOP LOSS:        {params.stop_loss:.2f} $ (-{dist_pct:.2f} %)")
    print(f" >> STÜCKZAHL:        {final_shares} Stk.")
    print("-" * 50)
    print(" RISIKO & SIZING:")
    invest_pct_final = (invested / ctx.equity * 100) if ctx.equity else 0
    risk_eq_pct_final = (risk_total / ctx.equity * 100) if ctx.equity else 0
    print(f" >> Investition:      {invested:,.2f} $ ({invest_pct_final:.2f} % Exposure)")
    print(f" >> Risiko (Total):   {risk_total:,.2f} $ ({risk_eq_pct_final:.2f} % an Equity)")
    print("-" * 50)
    print(" SZENARIEN (Netto nach Gebühren):")
    print(f" [0R] Break-Even:     {result.price_breakeven:.2f} $") 
    print(f" [2R] Ziel 1:         {result.price_2r:.2f} $")
    print(f" [3R] Ziel 2:         {result.price_3r:.2f} $")
    print("=" * 50)
    
    save = input("💾 Soll dieser Trade in den Planer (Paper) übernommen werden? [y/N]: ").lower()
    if save == 'y':
        # Add to paper
        target_service = service
        if service.context != "paper":
            # If we are in live mode, we need a paper service to save to paper portfolio
            target_service = PortfolioService(project_root=service.project_root, context="paper")

        # Fix: Pass final_shares manual override to service!
        res = target_service.add_paper_position(
            params.symbol, 
            params.entry_price, 
            params.stop_loss, 
            params.risk_pct,
            quantity=final_shares 
        )
        
        if "error" in res:
             print(f"Fehler beim Speichern: {res['error']}")
        else:
             print(f"Gespeichert! (Qty: {res['qty']})")    
    input("\n[Enter] zurück zum Menü...")

def action_init_paper(service: PortfolioService):
    print("\n⚠️  ACHTUNG: Dies überschreibt alle aktuellen Paper-Trades!")
    choice = input("  Live-Portfolio wirklich klonen? [y/N]: ").strip().lower()
    if choice == 'y':
        service.init_from_live()
        print("  ✓ Live-Portfolio erfolgreich in Paper-Umgebung kopiert.")
        action_list(service)
        input("\nEingabe zum Fortfahren...")

def action_edit_paper_position(service: PortfolioService):
    """Specific sub-menu to edit paper positions (Delete, Stop, Qty)."""
    print("\n--- Simulierte Position bearbeiten ---")
    positions = service.get_open_positions()
    if not positions:
        print("  Keine PP-Positionen vorhanden.")
        return
        
    for i, p in enumerate(positions, 1):
        print(f"  [{i}] {p.symbol:<8} | Qty: {p.quantity:>8.2f} | Stop: {p.stop_loss:>8.2f}")
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
                    service.delete_paper_position(target.symbol)
                    print(f"  ✓ {target.symbol} entfernt.")
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
            
            action_list(service)
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
        action_list(service)
        input("\nEingabe zum Fortfahren...")
    except ValueError:
        print("  ⚠️ Ungültige Zahleneingabe.")

def start_paper_mode():
    """Starts the paper trading sub-menu loop."""
    paper_service = PortfolioService(project_root=".", context="paper")
    while True:
        choice = show_paper_menu(paper_service)
        if choice == '1': run_sizing_wizard(paper_service, source="live")
        elif choice == '2': run_sizing_wizard(paper_service, source="paper")
        elif choice == '3': action_init_paper(paper_service)
        elif choice == '4': action_list(paper_service)
        elif choice == '5': action_edit_paper_position(paper_service)
        elif choice == '6': action_clear_paper(paper_service)
        elif choice == '7': action_edit_paper_metrics(paper_service)
        elif choice in ['b', 'back', 'q']:
            break
        else: print("  Ungültige Auswahl.")

def action_clear_paper(service: PortfolioService):
    print("\n🔥 ACHTUNG: Dies löscht UNWIDERRUFLICH alle simulierten Daten!")
    if input("  Wirklich alles löschen? [y/N]: ").lower() == 'y':
        service.clear_paper_portfolio()
        print("  ✓ Paper-Portfolio geleert.")
        action_list(service)
        input("\nEingabe zum Fortfahren...")


def action_list(service: Optional[PortfolioService] = None):
    """Shows Minervini-style overview of open positions."""
    if service is None:
        service = PortfolioService(project_root=".")
    
    positions = service.get_open_positions(update_prices=False)
    summary = service.get_summary()
    settings = service.get_risk_settings()
    max_equity_risk = settings.get("max_equity_risk", 1.25)

    C_RESET, C_BOLD, C_RED, C_GREEN, C_YELLOW = "\033[0m", "\033[1m", "\033[91m", "\033[92m", "\033[93m"

    mode_label = f"{service.context.upper()} TRADING"
    print(f"\n--- Minervini Dashboard [{mode_label}] ---")
    
    # Header: Sym (8), Days (5), Pos% (7), Price (9), Gain% (8), Stop (9), Dist% (8), Risk% (8), R (6), Status (8)
    header = f"{C_BOLD}{'Sym':<8} {'Days':>4} {'Pos%':>7} {'Price':>9} {'Gain%':>8} {'Stop':>9} {'Dist%':>8} {'Risk%':>8} {'R':>6} {'Status':<8}{C_RESET}"
    print(header)
    print("-" * len(header))
    
    for p in positions:
        # Price & Formatting
        price_str = f"{p.current_price:>9.2f}" if p.current_price else f"{'---':>9}"
        
        # Gain% Coloring
        gain_val = p.unrealized_pct or 0.0
        gain_color = C_GREEN if gain_val >= 0 else C_RED
        gain_str = f"{gain_color}{gain_val:>7.1f}%{C_RESET}" if p.unrealized_pct is not None else f"{'---':>8}"
        
        # Risk% Coloring (Minervini warns above threshold)
        risk_equity_val = p.risk_pct or 0.0
        risk_color = C_RED if risk_equity_val > max_equity_risk else ""
        risk_str = f"{risk_color}{risk_equity_val:>7.2f}%{C_RESET}"
        
        # R-Multiple
        r_color = C_GREEN if (p.r_multiple or 0) >= 0 else C_RED
        r_str = f"{r_color}{(p.r_multiple or 0):>6.1f}{C_RESET}"
        
        dist_str = f"{p.dist_pct:>7.1f}%" if p.dist_pct is not None else f"{'---':>8}"
        stop_str = f"{p.stop_loss:>9.2f}" if p.stop_loss > 0 else f"{C_RED}{'0.00':>9}{C_RESET}"
        
        status_str = " ".join(p.status_flags) if p.status_flags else "-"
        sym_display = (p.symbol[:7] + '..') if len(p.symbol) > 8 else p.symbol
        
        line = (f"{sym_display:<8} {p.days_held:>4} {p.pos_pct:>6.1f}% {price_str} {gain_str} "
                f"{stop_str} {dist_str} {risk_str} {r_str}  {status_str:<8}")
        print(line)
    
    print("-" * len(header))
    pl_sum_color = C_GREEN if summary.total_unrealized_pl >= 0 else C_RED
    
    # Compact Summary
    print(f"{C_BOLD}SUMMEN:{C_RESET}  Invest: {summary.total_invested:,.0f} | "
          f"P&L: {pl_sum_color}{summary.total_unrealized_pl:+,.2f}{C_RESET} | "
          f"Equity Risk: {summary.total_risk:,.0f} ({ (summary.total_risk/summary.equity*100 if summary.equity>0 else 0):.2f}%)")
    
    print(f"{C_BOLD}CAPITAL:{C_RESET} Cash: {summary.buying_power:,.2f} | Equity: {summary.equity:,.2f}")
    
    # Diagnostic counts
    counts = f"Positions: {summary.position_count} | Status: {C_GREEN}🟢 {summary.count_ok}{C_RESET} "
    if summary.count_warning > 0: counts += f"| {C_YELLOW}🟡 {summary.count_warning}{C_RESET} "
    if summary.count_danger > 0: counts += f"| {C_RED}🔴 {summary.count_danger}{C_RESET} "
    print(counts)

def action_update_prices(service: PortfolioService):
    """Force update market prices via service orchestrator."""
    print("\n--- Marktdaten aktualisieren ---")
    service.get_open_positions(update_prices=True)
    print("✓ Marktdaten erfolgreich aktualisiert.")
    input("\nDrücke Enter zum Fortfahren...") # Hold after slow update

def action_switch_data_source(service: PortfolioService):
    """Switch between Offline and Broker data sources (F-PDS-120)."""
    from .offline_data_source import OfflineDataSource
    
    current_source = type(service.get_data_source()).__name__
    print("\n--- Datenquelle wechseln ---")
    print(f"Aktuell: {current_source}")
    print()
    print("  [1] 📁 Offline (trades.xml, manual_risk_data.json)")
    print("  [2] 🔌 Broker (CapTrader/IBKR)")
    print("  [0] Zurück")
    
    choice = input("Auswahl: ").strip()
    
    if choice == '1':
        new_source = OfflineDataSource(project_root=service.project_root, context=service.context)
        service.set_data_source(new_source)
        print("✓ Datenquelle gewechselt zu: Offline")
    elif choice == '2':
        _connect_to_broker(service)
    elif choice == '0':
        pass
    else:
        print("Ungültige Auswahl.")
    
    input("\nDrücke Enter zum Fortfahren...")

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
    port_str = input("Port [7497]: ").strip() or "7497"
    account_id = input("Account ID (leer=auto): ").strip() or None
    
    try:
        port = int(port_str)
    except ValueError:
        print("⚠ Ungültiger Port.")
        return
    
    print(f"\nVerbinde zu {host}:{port}...")
    
    try:
        new_source = BrokerDataSource(
            host=host,
            port=port,
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
        else:
            print("⚠ Verbindung fehlgeschlagen.")
            
    except ConnectionError as e:
        print(f"⚠ Verbindungsfehler: {e}")
    except Exception as e:
        print(f"⚠ Fehler: {e}")

def main():
    service_live = PortfolioService(project_root=".", context="live")
    service_paper = PortfolioService(project_root=".", context="paper")
    
    while True:
        choice = show_menu(service_live)
        if choice == '1': action_manage_stops(service_live)
        elif choice == '2': action_list(service_live)
        elif choice == '3': action_update_prices(service_live)
        elif choice == '4': run_sizing_wizard(service_live, source="live") # Changed to Minervini Wizard (Live)
        elif choice == '5': start_paper_mode()
        elif choice == 'd': action_switch_data_source(service_live)
        elif choice in ['q', 'quit', 'exit']:
            print("\nAuf Wiedersehen!")
            break
        else: print("Ungültige Auswahl.")

if __name__ == "__main__":
    main()
