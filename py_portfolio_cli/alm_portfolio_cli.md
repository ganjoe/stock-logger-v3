# ALM: Portfolio Manager CLI

> **Modul:** `py_portfolio_cli`  
> **Status:** AKTIV

---

## Zweck

Das Modul `py_portfolio_cli` bildet die **Präsentationsschicht** (Terminal UI) des Portfolio Managers.
Es ist vollständig von der Business-Logik (`py_manage_portfolio`) getrennt.

---

## Anforderungen

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-CLI-010 | Menu | Hauptmenü | Anzeige des dreiteiligen Hauptmenüs (Live / Sim / Broker Connect) mit Status-Anzeige (Online/Offline). | menus.show_menu |
| F-CLI-020 | Menu | Live Sub-Menü | Loop mit Dashboard-Anzeige, Trading-Mockup, Wizard, Refresh, Stop-Loss Manager. | menus.show_live_menu |
| F-CLI-030 | Menu | Simulation Sub-Menü | Menü mit Import, Add/Edit, Wizard, Reset. | menus.show_simulation_menu |
| F-CLI-040 | Connection | Broker Toggle | Verbindung zu IBKR herstellen/trennen über interaktive Eingabe (Host, Port, Client ID). | actions._connect_to_broker |
| F-CLI-050 | Menu | Sortierbare Ansicht | Neues Menü-Item in den Portfolio-Untermenüs für eine reine Lese-Ansicht mit Auswahl der Sortierung [1-12]. | menus.show_portfolio_viewer |
| F-CLI-100 | Action | Stop-Loss Manager | Interaktiver Editor: Position wählen, Stop-Loss setzen, mit Validierung. | actions.action_manage_stops |
| F-CLI-110 | Action | Paper Init | Clone des Live-Portfolios in die Simulation mit Bestätigung. | actions.action_init_paper |
| F-CLI-120 | Action | Position bearbeiten | Sub-Menü: Löschen, Stop bearbeiten, Qty bearbeiten einer Sim-Position. | actions.action_edit_paper_position |
| F-CLI-130 | Action | Metriken bearbeiten | Manuelle Anpassung von Equity und Exposure im Paper-Modus. | actions.action_edit_paper_metrics |
| F-CLI-140 | Action | Marktdaten Update | Aktualisierung der Marktpreise und Snapshot-Speicherung. | actions.action_update_prices |
| F-CLI-150 | Action | Paper löschen | Löschen aller simulierten Daten nach Bestätigung. | actions.action_clear_paper |
| F-CLI-160 | Action | Datenquelle wechseln | Umschalten zwischen Offline und Broker Data Source. | actions.action_switch_data_source |
| F-CLI-200 | Wizard | Minervini Sizing | 4-Schritte-Dialog: Portfolio Status → Trade Parameter → Analyse (Trichter) → Speichern. | wizard.run_sizing_wizard |
| F-CLI-210 | Wizard | Schritt 1 | Erfassung von Equity, Exposure, Ziel-Exposure mit Defaults aus Journal. | wizard.wizard_step_1_get_context |
| F-CLI-220 | Wizard | Schritt 2 | Erfassung von Symbol, Entry, Stop, Risk%, MaxSize%, Fee. | wizard.wizard_step_2_get_params |
| F-CLI-300 | Display | Dashboard | Minervini-Dashboard mit farbcodierten Metriken (incl. Qty, AvgPrice, Gain%, Risk%, R-Multiple). | formatter.render_dashboard |
| F-CLI-310 | Utility | Dezimal-Parsing | Robustes Parsing von Benutzereingaben (Komma/Punkt-Handling). | utils.parse_input_decimal |
| F-CLI-320 | Utility | Stop-Loss Prompt | Validierte Eingabe eines Stop-Loss mit Richtungsprüfung (Long/Short). | utils.prompt_stop_loss |
| F-CLI-330 | Interaction | Dashboard-Sortierung | Sitzungs-persistentes Sortieren der Tabellenansicht über numerische Spalten-Indices [1-12]. | formatter.render_dashboard |

---

## Abhängigkeiten

| Abhängigkeit | Verwendung |
|---|---|
| `py_manage_portfolio.service` | PortfolioService (Orchestrierung) |
| `py_manage_portfolio.models` | PortfolioPosition, PortfolioSummary, SizingContext, etc. |
| `py_manage_portfolio.data_source` | ConnectionAware (Typ-Check) |
| `py_manage_portfolio.sizer` | MinerviniSizer (Berechnung) |
| `py_manage_portfolio.broker_adapter` | BrokerAdapter (lazy import) |
| `py_manage_portfolio.offline_data_source` | OfflineDataSource (lazy import) |
