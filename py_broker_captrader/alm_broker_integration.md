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

## Standalone Architecture: py_broker_captrader

Das Modul `py_broker_captrader` ist als **eigenständiges Paket** konzipiert. Es definiert seine eigenen Schnittstellen und Datenstrukturen, um ohne Abhängigkeit vom restlichen Projekt (z.B. `py_manage_portfolio`) in beliebigen Python-Umgebungen eingesetzt werden zu können.

### Schnittstellen-Definitionen (interface.py)

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-BRK-INT-010 | Architecture | Standalone Interfaces | Das Modul definiert abstrakte Basisklassen (`BrokerReader`, `BrokerOrderManager`, `BrokerConnection`) direkt in `interface.py`. | interface.py |
| F-BRK-INT-020 | DTO | Independence | Alle Datenstrukturen (`BrokerPosition`, `AccountMetrics`, `BrokerOrderRequest`) sind im Paket definiert und haben keine externen Projekt-Abhängigkeiten. | interface.py |

---

## Anforderungen: Broker Client API

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-BRK-010 | Architecture | DataSource Implementation | Die Klasse `BrokerDataSource` implementiert die im Paket definierten Interfaces. | BrokerDataSource |
| F-BRK-020 | Connection | Gateway Configuration | Verbindung zum TWS/IB Gateway über konfigurierbaren Host:Port (Standard: 127.0.0.1:7497). | BrokerDataSource |
| F-BRK-030 | Connection | Connection Status | Prüfung der Verbindung über `is_connected()` und sauberes Trennen via `disconnect()`. | BrokerDataSource |
| F-BRK-040 | Account | Multi-Account Support | Das Modul unterstützt mehrere Accounts über den `account_id` Parameter im Konstruktor. | BrokerDataSource |
| F-BRK-050 | Positions | Live Position Query | Methode `get_positions() -> List[BrokerPosition]` liefert offene Positionen live vom Broker. | BrokerDataSource.get_positions |
| F-BRK-060 | Orders | Stop Loss Query | Methode `get_stop_losses() -> Dict[str, BrokerStopOrder]` liefert aktive Stop-Orders als Risk-Daten. | BrokerDataSource.get_stop_losses |
| F-BRK-070 | Account | Account Summary | Methode `get_account_metrics() -> AccountMetrics` liefert NetLiquidation (Equity) und AvailableFunds (Cash). | BrokerDataSource.get_account_metrics |
| F-BRK-080 | Status | Order Mapping | IBKR-Order-Status (e.g. `PendingSubmit`, `Inactive`) werden auf eine einheitliche `OrderStatus` Enum gemappt. | BrokerDataSource.get_open_orders |
| F-BRK-090 | Risk | Trailing Stop Support | Unterstützung für `TRAIL` und `TRAIL LIMIT` Orders zur dynamischen Stop-Loss Ermittlung. | BrokerDataSource._get_active_stops |
| F-BRK-100 | Connection | Master Client 0 | Das System nutzt standardmäßig Client ID 0 zur vollen Synchronisation inkl. TWS-Orders. | BrokerDataSource.__init__ |
| F-BRK-110 | Risk | Stop-Limit Support | Unterstützung für STP LMT Orders inkl. Trigger- und Limit-Preis Management. | BrokerDataSource.place_order |
| F-BRK-120 | Orders | Order Modification | Unterstützung zur Änderung bestehender Orders (Qty, Price) via `update_order`. | BrokerDataSource.update_order |

---

## Anforderungen: Order Management

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-API-060 | API | Open Order Retrieval | Abruf aller aktiven Orders via `get_open_orders(symbol=None) -> List[BrokerOpenOrder]`. | BrokerDataSource.get_open_orders |
| F-API-100 | API | Order Parameters | `BrokerOrderRequest` enthält Symbol, Aktion (BUY/SELL), Menge, Typ (LMT, STP, etc.) und Time-In-Force. | BrokerOrderRequest |
| F-API-110 | API | Order Placement | Platzieren von Orders via `place_order(request)`. Liefert die Broker-Order-ID zurück. | BrokerDataSource.place_order |
| F-API-120 | API | Order Cancellation | Stornieren von Orders via `cancel_order(order_id)`. | BrokerDataSource.cancel_order |

---

## Technische Details & Error Handling

| ID | Category | Title | Description | Covered By |
|----|----------|-------|-------------|------------|
| F-TECH-010 | Lib | ib_insync | Das Modul nutzt die `ib_insync` Bibliothek für die asynchrone Kommunikation mit dem Gateway. | - |
| F-TECH-020 | Error | Exception Handling | API-Fehler werden gefangen und als aussagekräftige Log-Meldungen ausgegeben; Methoden liefern im Fehlerfall `None` oder `False`. | - |
| F-TECH-030 | Port | Default Port | Für Live/Real-Trading wird Port 7497 genutzt, für Paper-Trading Port 7498 oder 4002. | - |

---

## Status

- [x] Architektur entkoppelt (Standalone Modul)
- [x] Unit/Integration Tests bestanden
- [x] Dokumentation aktualisiert

