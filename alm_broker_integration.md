# ALM: Portfolio Data Source Interface & Broker Integration

> **Rolle:** Senior Requirements Engineer (Brainstorming)  
> **Status:** ENTWURF - Zur Abnahme

---

## Analyse bestehender Anforderungen

### Betroffene Requirements (Änderung erforderlich)

| Original ID | Titel | Änderung |
|-------------|-------|----------|
| F-PM-010 | Transaktionsquelle | trades.xml wird zur Implementierungsdetail des OfflineDataSource |
| F-PM-050 | Risikodaten laden | manual_risk_data.json wird zur Implementierungsdetail |
| F-PM-060 | Risikodaten speichern | Wird abstrakt: set_stop_loss() |
| F-PM-260 | Journal Integration | Abstrakt: get_account_metrics() |
| ICD-PM-FIL-010 | Input Sources | Wird zur Implementierungsdetail des OfflineDataSource |

### Potentiell obsolet bei vollem Broker-Betrieb

| ID | Titel | Grund |
|----|-------|-------|
| F-PM-050 | Risikodaten laden | Broker liefert Stop-Orders direkt |
| F-PM-060 | Risikodaten speichern | Orders werden beim Broker platziert |

---

## Neue Anforderungen: PortfolioDataSource Interface

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-PDS-010 | Architecture | Abstract Interface | Das System muss ein abstraktes Interface `PortfolioDataSource` definieren, das die Datenquelle vom PortfolioService entkoppelt. | - |
| F-PDS-020 | Architecture | Runtime Selection | Die Wahl der Datenquelle (Offline/Broker) erfolgt zur Laufzeit, nicht über Config-Dateien. | - |
| F-PDS-030 | API | Account ID Parameter | Das Interface muss einen optionalen `account_id` Parameter unterstützen für Multi-Account-Szenarien. | - |
| F-PDS-040 | API | Get Positions | Methode `get_positions() -> List[Position]` liefert offene Positionen inkl. Qty, Entry, ISIN. | - |
| F-PDS-050 | API | Get Stop Losses | Methode `get_stop_losses() -> Dict[str, StopOrder]` liefert aktive Stop-Loss-Orders/Daten. | - |
| F-PDS-060 | API | Get Account Metrics | Methode `get_account_metrics() -> AccountMetrics` liefert Equity, Cash, Exposure. | - |
| F-PDS-070 | API | Set Stop Loss | Methode `set_stop_loss(symbol, price) -> bool` setzt/aktualisiert Stop (Order oder JSON je nach Impl.). | - |
| F-PDS-080 | API | Add Position | Methode `add_position(...) -> PositionResult` fügt Position hinzu (nur für Paper/Offline relevant). | - |
| F-PDS-090 | API | Close Position | Methode `close_position(symbol) -> bool` schließt/löscht eine Position. | - |
| F-PDS-100 | Consistency | Identical Processing | Die Verarbeitungslogik im PortfolioService muss für alle DataSource-Implementierungen identisch sein. | - |
| F-PDS-110 | API | Switch DataSource | Der PortfolioService muss eine Methode `set_data_source(source)` haben, um zur Laufzeit die DataSource zu wechseln. | - |
| F-PDS-120 | UX | CLI Menü Datenquelle | Das Hauptmenü in `py_manage_portfolio/manage_stoploss.py` muss einen Menüpunkt "[D] Datenquelle" enthalten, der zwischen Offline und Broker umschalten lässt. | - |
| F-PDS-130 | Default | Offline Default | Beim Start ist immer "Offline" als Datenquelle aktiv. Keine persistente Speicherung der Auswahl. | - |

---

## Neue Anforderungen: OfflineDataSource Implementierung

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-ODS-010 | Implementation | Trades XML | Die OfflineDataSource liest Positionsdaten aus trades.xml (Live) oder paper-trades.xml (Paper). | - |
| F-ODS-020 | Implementation | Risk Data JSON | Die OfflineDataSource liest/schreibt Stop-Loss-Daten aus/in manual_risk_data.json (bzw. paper-). | - |
| F-ODS-030 | Implementation | Journal CSV | Die OfflineDataSource liest Account-Metriken aus journal.csv (bzw. paper_journal.csv). | - |
| F-ODS-040 | Configuration | Context Parameter | Ein `context` Parameter ("live"/"paper") steuert welche Dateien verwendet werden. | - |
| F-ODS-050 | Compatibility | Paper Journal Sync | Bei Änderungen im Paper-Modus wird paper_journal.csv automatisch aktualisiert (bestehende Logik). | - |

---

## Neue Anforderungen: py_broker_captrader Modul

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-BRK-010 | Architecture | DataSource Implementation | Das Modul implementiert PortfolioDataSource für den CapTrader/IBKR-Broker. | - |
| F-BRK-020 | Connection | Gateway Configuration | Verbindung zum TWS/IB Gateway über konfigurierbaren Host:Port (Standard: 127.0.0.1:7497). | - |
| F-BRK-030 | Connection | Connection Retry | Bei Verbindungsfehlern müssen mindestens 3 Wiederholungsversuche mit konfiguriertem Delay erfolgen. | - |
| F-BRK-040 | Account | Multi-Account Support | Das Modul muss mehrere Accounts über den account_id Parameter unterstützen. | - |
| F-BRK-050 | Account | Paper Trading Account | Der Broker unterstützt Paper-Trading-Accounts; diese werden wie Live-Accounts behandelt (gleiche API). | - |
| F-BRK-060 | Positions | Live Position Query | Positionen werden live über die IBKR API abgefragt (nicht aus Cache). | - |
| F-BRK-070 | Orders | Stop Loss Query | Aktive Stop-Orders werden über die IBKR API abgefragt und als Stop-Loss-Daten interpretiert. | - |
| F-BRK-080 | Orders | Stop Loss Placement | set_stop_loss() platziert/modifiziert eine echte Stop-Order beim Broker. | - |
| F-BRK-090 | Account | Account Summary | Equity, Cash und Exposure werden über die IBKR Account Summary API abgefragt. | - |
| F-BRK-100 | Error Handling | Graceful Degradation | Bei API-Fehlern muss eine lesbare Exception mit Fehlercode und -text geworfen werden. | - |
| F-BRK-110 | Security | No Credentials Storage | Keine Broker-Credentials werden im Code gespeichert; Authentifizierung erfolgt über TWS. | - |

---

## Abgenommene Entscheidungen

| Frage | Entscheidung |
|-------|--------------|
| `add_position()` beim Broker | Wirft `NotImplementedError`. Paper-Trading bleibt Offline (Planungstool). |
| Broker Live vs. Paper | Keine Unterscheidung im Code. Nur `account_id` entscheidet (Multi-Account). |
| Marktpreise | Weiterhin über `py_datafetcher`. Broker-Integration als Future Feature. |

---

## Future Features (nicht in dieser Phase)

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-DF-200 | Future | CapTrader Provider | `py_datafetcher/provider_captrader.py` als zusätzliche Online-Datenquelle für Marktpreise via IBKR API. | - |

---

## Status

- [x] Anforderungen abgenommen
- [x] Offene Fragen geklärt
- [ ] ICD für neues Interface erstellen
- [ ] Implementierung starten

