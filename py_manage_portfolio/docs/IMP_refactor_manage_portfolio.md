# Umbauplan: py_manage_portfolio vereinfachen

## Ziel-Architektur

`py_manage_portfolio` verwaltet ein **angereichertes Portfolioabbild**:
1. **Speichern/Laden** des Abbilds (JSON Snapshots)
2. **Interface** zum Abruf des Portfolios
3. **Datenquellen**: Broker ODER gespeicherter Snapshot — sonst nichts

## Akuelle Probleme

| # | Problem | Dateien |
|---|---------|---------|
| 1 | `OfflineDataSource` baut Portfolio aus Rohdateien (XML/CSV/JSON) — widerspricht der Vision | `offline_data_source.py` (416 Zeilen) |
| 2 | Zwei Position-Modelle: `Position` (5 Felder, gespeichert) vs. `PortfolioPosition` (21 Felder, UI) | `portfolio_state.py`, `legacy.py` |
| 3 | Anreicherung findet kaum statt — 16 von 21 Feldern bleiben leer | `service.py:101-123` |
| 4 | `data_source.py` Interface zu komplex (5 ABCs, 11 abstrakte Methoden) | `data_source.py` |
| 5 | `price_service.py` redundant wenn Broker Live-Preise liefert | `price_service.py` |
| 6 | `_append_to_legacy_trades` ist toter Code (tree.write auskommentiert) | `service.py:147-169` |

---

## Phase 1: Unified Position Model

**Ziel:** Ein einziges `Position`-Modell das sowohl gespeichert als auch angezeigt wird.

### 1.1 Position erweitern (`models/portfolio_state.py`)

`Position` bekommt alle nützlichen Felder aus `PortfolioPosition`:

```python
@dataclass
class Position:
    # Core (gespeichert)
    symbol: str
    quantity: float
    entry_price: float
    current_price: float = 0.0
    currency: str = "USD"
    isin: Optional[str] = None
    entry_date: Optional[str] = None    # ISO YYYY-MM-DD
    direction: str = "LONG"             # "LONG" or "SHORT"

    # Risk (gespeichert)
    stop_loss: Optional[float] = None
    initial_risk: Optional[float] = None

    # Computed (berechnet, nicht gespeichert)
    # → werden als @property implementiert oder beim Laden berechnet
```

**Betroffene Dateien:**
- `models/portfolio_state.py` — Position erweitern
- `models/legacy.py` — `PortfolioPosition` löschen, `PortfolioSummary` bleibt
- `models/__init__.py` — Exports anpassen

### 1.2 Consumer umverdrahten

Alle Stellen die `PortfolioPosition` verwenden → `Position` nutzen:

| Datei | Änderung |
|-------|----------|
| `service.py` | `get_positions()` gibt `List[Position]` zurück, keine Konvertierung mehr |
| `py_portfolio_cli/formatter.py` | Import `Position` statt `PortfolioPosition` |
| `py_portfolio_cli/test_cli_integration.py` | Import anpassen |
| `tests/integration/test_portfolio_manager_integration.py` | Import anpassen |

### 1.3 PortfolioSummary prüfen

`PortfolioSummary` bleibt als eigene Klasse — wird aus `legacy.py` nach `portfolio_state.py` verschoben.

---

## Phase 2: Anreicherungslogik implementieren

**Ziel:** `service.get_positions()` befüllt tatsächlich die Metriken.

### 2.1 Metriken als Properties auf Position

```python
@property
def market_value(self) -> float:
    return self.quantity * self.current_price

@property
def unrealized_pnl(self) -> float:
    return (self.current_price - self.entry_price) * self.quantity

@property
def unrealized_pct(self) -> float:
    return ((self.current_price - self.entry_price) / self.entry_price * 100) if self.entry_price else 0.0

@property
def r_multiple(self) -> Optional[float]:
    if not self.stop_loss or not self.initial_risk: return None
    return self.unrealized_pnl / self.initial_risk if self.initial_risk else None
```

### 2.2 Portfolio-bezogene Metriken in Service

Felder die den Portfolio-Kontext brauchen (`pos_pct`, `risk_pct`) werden in `get_portfolio_summary()` berechnet — nicht auf Position-Ebene.

---

## Phase 3: OfflineDataSource entfernen

**Ziel:** Keine Rohdaten-Parser mehr. Nur Broker oder Snapshot.

### 3.1 Service-Logik vereinfachen

```
load_portfolio_state():
    if broker_connected:
        state = broker.get_portfolio_state()   # Broker liefert
        storage.save(state, "snapshot.json")    # Snapshot sichern
    else:
        state = storage.load("snapshot.json")   # Letzter Snapshot
```

### 3.2 OfflineDataSource löschen

| Aktion | Datei |
|--------|-------|
| Löschen | `offline_data_source.py` (416 Zeilen) |
| Import entfernen | `service.py:33-34` (Default-Fallback) |
| Import entfernen | `py_portfolio_cli/actions.py:163,176` (Datenquelle wechseln) |
| Import entfernen | `py_portfolio_cli/main.py:89-90` (Disconnect → Offline) |
| Tests anpassen | `py_portfolio_cli/test_cli_integration.py` (Offline Fixtures) |

### 3.3 Disconnect-Verhalten ändern

Aktuell: Broker disconnect → OfflineDataSource erstellen
Neu: Broker disconnect → Snapshot aus JSON laden (schon vorhanden)

---

## Phase 4: data_source.py Interface verschlanken

**Ziel:** Nur das was der Service braucht.

### 4.1 Aktuell (11 abstrakte Methoden in 4 ABCs)

```
PortfolioReader:   get_portfolio_state, get_positions, get_stop_losses, get_account_metrics, get_open_orders
PortfolioWriter:   add_position, close_position
OrderManager:      place_order, cancel_order
ConnectionAware:   is_connected, disconnect
```

### 4.2 Neu (3 Methoden in 2 ABCs)

```
PortfolioReader:   get_portfolio_state() → PortfolioState
ConnectionAware:   is_connected(), disconnect()
```

`get_positions`, `get_stop_losses`, `get_account_metrics` → werden intern vom Broker in `get_portfolio_state()` aufgerufen, nicht vom Service.

`OrderManager` → bleibt im Broker-Modul (wird direkt von der CLI genutzt, nicht über den Service).

`PortfolioWriter` → entfällt (war nur für OfflineDataSource).

### 4.3 Betroffene Dateien

| Datei | Änderung |
|-------|----------|
| `data_source.py` | Auf `PortfolioReader` + `ConnectionAware` reduzieren |
| `py_broker_captrader/broker_data_source.py` | Nur noch `PortfolioReader` + `ConnectionAware` implementieren |
| `py_broker_captrader/interface.py` | Re-Exports anpassen |
| DTOs (`RawPosition`, `StopOrder`, `OpenOrder`, etc.) | Interne Broker-DTOs, nicht mehr im Domain-Interface |

---

## Phase 5: Toter Code & Cleanup

| Aktion | Datei |
|--------|-------|
| Löschen | `_append_to_legacy_trades()` — toter Code | 
| Löschen | `price_service.py` — redundant bei Broker-Preisen |
| Löschen | `models/legacy.py` — nach Migration leer |
| Entfernen | Duplikate Aliase (`get_open_positions` → `get_positions`) |
| Entfernen | `context` paper→sim Mapping (Zeile 38) |

---

## Abhängigkeits-Matrix (alle Consumer)

| Consumer-Datei | Verwendet | Muss angepasst werden |
|----------------|-----------|----------------------|
| `py_portfolio_cli/formatter.py` | `PortfolioPosition`, `PortfolioSummary` | Ja (Phase 1) |
| `py_portfolio_cli/actions.py` | `OfflineDataSource` | Ja (Phase 3) |
| `py_portfolio_cli/main.py` | `OfflineDataSource` | Ja (Phase 3) |
| `py_portfolio_cli/test_cli_integration.py` | `PortfolioPosition`, `PortfolioSummary`, `OfflineDataSource`, `PortfolioReader` | Ja (Phase 1+3+4) |
| `py_broker_captrader/broker_data_source.py` | `PortfolioReader`, `ConnectionAware`, `OrderManager`, alle DTOs | Ja (Phase 4) |
| `py_broker_captrader/interface.py` | Re-exports aus `data_source.py` | Ja (Phase 4) |
| `py_broker_captrader/test_broker_full_integration.py` | `OrderRequest`, `OrderStatus` | Ja (Phase 4) |
| `tests/integration/test_portfolio_manager_integration.py` | `PortfolioPosition`, `PortfolioSummary`, `PortfolioPriceService` | Ja (Phase 1+5) |
| `tests/integration/test_minervini_sizing_wizard.py` | `PortfolioService` nur | Nein |

---

## Reihenfolge & Tests

```
Phase 1 → Tests laufen lassen (Position Model swap)
Phase 2 → Tests laufen lassen (Anreicherung)
Phase 3 → Tests laufen lassen (OfflineDataSource weg)
Phase 4 → Tests laufen lassen (Interface slim)
Phase 5 → Tests laufen lassen (Cleanup)
```

Jede Phase ist einzeln committbar und testbar.

## Ziel-Zustand nach Umbau

```
py_manage_portfolio/
├── __init__.py
├── models/
│   ├── __init__.py          # exports: PortfolioState, Position, PortfolioSummary
│   └── portfolio_state.py   # Unified: Position (angereichert), PortfolioState, PortfolioSummary
├── data_source.py           # Minimal: PortfolioReader (get_portfolio_state) + ConnectionAware
├── service.py               # PortfolioService: Broker → Snapshot Fallback, Metriken
└── storage_manager.py       # JSON save/load
```

Gelöscht: `offline_data_source.py`, `price_service.py`, `models/legacy.py`
