"""
Dashboard Formatter for CLI Portfolio Display.
Renders the Minervini-style position table with color coding.
"""
from typing import Optional, List
from py_manage_portfolio.service import PortfolioService
from py_manage_portfolio.models import Position, PortfolioSummary

# ANSI Color Constants
C_RESET  = "\033[0m"
C_BOLD   = "\033[1m"
C_RED    = "\033[91m"
C_GREEN  = "\033[92m"
C_YELLOW = "\033[93m"


# Session Persistence (reset on script restart)
SESSION_SORT_BY = "7"

def render_dashboard(service: PortfolioService, sort_by: Optional[str] = None):
    """
    Renders the Minervini Dashboard table to stdout.
    
    Args:
        service: The PortfolioService instance to read data from.
        sort_by: Optional column index (1-12) to sort by. If None, uses session default.
    """
    global SESSION_SORT_BY
    if sort_by:
        SESSION_SORT_BY = sort_by
    effective_sort = SESSION_SORT_BY
    
    positions = service.get_open_positions(update_prices=False)
    summary = service.get_summary()
    settings = service.get_risk_settings()
    max_equity_risk = settings.get("max_equity_risk", 1.25)

    # Sorting Logic
    sort_map = {
        "1": lambda p: p.symbol,
        "2": lambda p: p.quantity,
        "3": lambda p: p.entry_price,
        "4": lambda p: p.days_held or 0,
        "5": lambda p: p.pos_pct or 0.0,
        "6": lambda p: p.current_price or 0.0,
        "7": lambda p: p.unrealized_pct or 0.0,
        "8": lambda p: p.stop_loss or 0.0,
        "9": lambda p: p.dist_pct or 0.0,
        "10": lambda p: p.risk_pct or 0.0,
        "11": lambda p: p.r_multiple or 0.0,
        "12": lambda p: " ".join(p.status_flags) if p.status_flags else ""
    }
    
    key_func = sort_map.get(effective_sort, sort_map["7"])
    # Most columns sort descending (e.g. highest gain first), 
    # except Sym, Days (maybe?), Status.
    # Let's do descending for most numeric ones.
    reverse = effective_sort not in ["1", "4", "12"]
    positions.sort(key=key_func, reverse=reverse)

    mode_label = f"{service.context.upper()} TRADING"
    print(f"\n--- Minervini Dashboard [{mode_label}] ---")
    
    # Header with numbers for sorting
    h_sym   = "[1]Sym"
    h_qty   = "[2]Qty"
    h_avg   = "[3]AvgPx"
    h_days  = "[4]Day"
    h_pos   = "[5]Pos%"
    h_price = "[6]Price"
    h_gain  = "[7]Gain%"
    h_stop  = "[8]Stop"
    h_dist  = "[9]Dist%"
    h_risk  = "[10]Risk%"
    h_r     = "[11]R"
    h_stat  = "[12]Status"

    header = (f"{C_BOLD}{h_sym:<8} {h_qty:>6} {h_avg:>9} {h_days:>4} {h_pos:>7} {h_price:>9} "
              f"{h_gain:>8} {h_stop:>9} {h_dist:>8} {h_risk:>8} {h_r:>6} {h_stat:<8}{C_RESET}")
    print(header)
    print("-" * len(header))
    
    for p in positions:
        # Price & Formatting
        price_str = f"{p.current_price:>9.2f}" if p.current_price else f"{'---':>9}"
        
        # Gain% Coloring
        gain_val = p.unrealized_pct or 0.0
        gain_color = C_GREEN if gain_val >= 0 else C_RED
        gain_str = f"{gain_color}{gain_val:>7.1f}%{C_RESET}" if p.unrealized_pct is not None else f"{'---':>8}"
        
        # Risk% Coloring
        risk_equity_val = p.risk_pct or 0.0
        risk_color = C_RED if risk_equity_val > max_equity_risk else ""
        risk_str = f"{risk_color}{risk_equity_val:>7.2f}%{C_RESET}"
        
        # R-Multiple
        r_color = C_GREEN if (p.r_multiple or 0) >= 0 else C_RED
        r_str = f"{r_color}{(p.r_multiple or 0):>6.1f}{C_RESET}"
        
        dist_str = f"{p.dist_pct:>7.1f}%" if p.dist_pct is not None else f"{'---':>8}"
        stop_val = p.stop_loss or 0
        stop_str = f"{stop_val:>9.2f}" if stop_val > 0 else f"{C_RED}{'0.00':>9}{C_RESET}"
        
        status_str = " ".join(p.status_flags) if p.status_flags else "-"
        dir_label = "(L)" if p.direction == "LONG" else "(S)"
        sym_text = f"{p.symbol}{dir_label}"
        sym_display = (sym_text[:7] + '..') if len(sym_text) > 8 else sym_text
        
        days_held = p.days_held if p.days_held is not None else 0
        pos_pct = p.pos_pct if p.pos_pct is not None else 0.0
        
        line = (f"{sym_display:<8} {p.quantity:>6.0f} {p.entry_price:>9.2f} {days_held:>4} {pos_pct:>6.1f}% {price_str} {gain_str} "
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
