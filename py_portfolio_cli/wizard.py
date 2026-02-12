"""
Minervini Position Sizing Wizard.
Guided 4-step dialog for planning trades.
"""
from datetime import datetime
from typing import Optional
from py_manage_portfolio.service import PortfolioService
from py_riskmanagement import MinerviniSizer, SizingContext, TradeParameters, SizingResult
from py_manage_portfolio.data_source import OrderManager, OrderRequest
from .logger import append_trade_log


def wizard_step_1_get_context(service: PortfolioService, sizer: MinerviniSizer, 
                                source: str = "live") -> SizingContext:
    """
    Step 1: Gathers portfolio status (Equity, Exposure) and calculates available budget.
    Loads defaults from Live or Sim journal, allows user override.
    """
    print("\n" + "=" * 50)
    print(" SCHRITT 1: PORTFOLIO STATUS")
    print("=" * 50)
    
    # Get defaults from the active service
    is_live_broker = source == "live" and service.is_broker_connected()
    
    if is_live_broker:
        print(" (Lade Echtzeit-Daten vom Broker...)")
        # Ensure we have fresh data
        service.load_portfolio_state()
        equity, _, total_assets = service._get_journal_metrics()
    else:
        # Fallback to local journals/snapshots
        equity, _, total_assets = service._get_journal_metrics()
        print(f" (Lade Daten aus {'LIVE' if service.context == 'live' else 'PAPER'} Journal...)")

    current_exposure = total_assets 
    
    if is_live_broker:
        # SKIP manual input if connected to broker
        final_equity = equity
        final_exposure = current_exposure
        print(f" Total Equity ($): {final_equity:,.2f}")
        print(f" Exposure ($):     {final_exposure:,.2f}")
    else:
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


def wizard_step_2_get_params(service: PortfolioService, 
                               sizer: MinerviniSizer) -> Optional[TradeParameters]:
    """
    Step 2: Collects trade parameters (Symbol, Entry, Stop, Risk%, MaxSize%, Fee).
    Returns None if user cancels (empty symbol).
    """
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
    """
    Orchestrates the full 4-step Minervini sizing wizard:
    1. Get Context (Equity/Exposure)
    2. Get Trade Params (Symbol/Entry/Stop)
    3. Calculate & Display Sizing Analysis (The Funnel)
    4. Summary & Save to Simulation
    """
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
    
    # Step 4: Execution & Save
    executed_live = False
    
    # 5. Live Execution (if connected)
    if source == "live" and service.is_broker_connected():
        ds = service.get_data_source()
        if ds and isinstance(ds, OrderManager):
            print("\n" + "=" * 50)
            print(" 🚀 LIVE EXECUTION (Broker)")
            print("=" * 50)
            execute = input(f"Soll dieser Trade JETZT auf {ds.__class__.__name__} ausgeführt werden? [y/N]: ").strip().lower()
            
            if execute == 'y':
                # 1. Entry Order Type
                print("\nEinstiegs-Order Typ: [1] MKT (Market), [2] LMT (Limit), [3] STP (Stop)")
                et_choice = input("Auswahl [1]: ").strip() or "1"
                
                type_map = {"1": "MKT", "2": "LMT", "3": "STP"}
                entry_type = type_map.get(et_choice, "MKT")
                
                # 2. Confirm Entry
                if (entry_type != "MKT") and (params.entry_price <= 0 or params.stop_loss <= 0):
                    print(f" ❌ Ungültige Preise (Entry: {params.entry_price}, Stop: {params.stop_loss}). Abbruch.")
                    return

                print(f"\nSende Entry: BUY {final_shares} {params.symbol} @ {entry_type}" + (f" {params.entry_price:.2f}" if entry_type != "MKT" else ""))
                if input("Bestätigen? [y/N]: ").strip().lower() == 'y':
                    entry_req = OrderRequest(
                        symbol=params.symbol,
                        action="BUY",
                        quantity=final_shares,
                        order_type=entry_type,
                        limit_price=params.entry_price if entry_type == "LMT" else None,
                        stop_price=params.entry_price if entry_type == "STP" else None,
                        time_in_force="GTC" 
                    )
                    
                    print(" Sende Entry Order...")
                    order_id = ds.place_order(entry_req)
                    if order_id:
                        print(f" ✅ Entry-Order gesendet! ID: {order_id}")
                        append_trade_log(service, entry_req, order_id)
                        executed_live = True
                        
                        # 3. Stop Loss (Exit)
                        print("\n" + "-" * 30)
                        print(" EXIT STOP-LOSS SETUP")
                        print("-" * 30)
                        print(f"Trigger Preis: {params.stop_loss:.2f}")
                        print("Stop-Typ: [1] STP (Market), [2] STP LMT (Limit)")
                        st_choice = input("Auswahl [1]: ").strip() or "1"
                        stop_type = "STP LMT" if st_choice == "2" else "STP"
                        
                        lmt_price = None
                        if stop_type == "STP LMT":
                            # Default 1 cent below for LONG positions
                            default_lmt = params.stop_loss - 0.01
                            lmt_in = input(f"Limit Preis [{default_lmt:.2f}]: ").strip()
                            lmt_price = float(lmt_in) if lmt_in else default_lmt
                            
                        print(f"Sende {stop_type} auf {params.stop_loss:.2f}...")
                        # Pass quantity and direction explicitly to ensure sync even for new positions
                        service.update_stop_loss(
                            params.symbol, 
                            params.stop_loss, 
                            stop_type=stop_type, 
                            limit_price=lmt_price,
                            quantity=final_shares,
                            direction="LONG"
                        )
                    else:
                        print(" ❌ Fehler beim Senden der Entry-Order (Broker hat KEINE ID zurückgegeben).")
    
    # 6. Simulation Prompt (only if not executed live)
    if not executed_live:
        save = input("\n💾 Soll dieser Trade in die Simulation übernommen werden? [y/N]: ").lower()
        if save == 'y':
            _save_to_simulation(service, params, final_shares)
    
    input("\n[Enter] zurück zum Menü...")


def _save_to_simulation(service: PortfolioService, params: TradeParameters, final_shares: int):
    """Helper to save a planned trade to the simulation journal."""
    target_service = service
    if service.context != "sim":
        target_service = PortfolioService(project_root=service.project_root, context="sim")

    try:
         success = target_service.add_position_sim(
            symbol=params.symbol, 
            quantity=final_shares,
            price=params.entry_price,
            date=datetime.now().strftime("%Y-%m-%d")
         )
         if success:
              print(f"✓ In Simulation gespeichert.")
    except Exception as e:
         print(f"Fehler beim Speichern der Simulation: {e}")
