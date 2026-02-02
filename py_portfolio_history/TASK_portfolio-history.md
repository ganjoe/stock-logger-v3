# Task List

- [x] Analyze `trades.xml` structure <!-- id: 0 -->
- [x] Create implementation plan <!-- id: 1 -->
- [x] Architect System (Senior Architect Workflow) <!-- id: 7 -->
- [x] Implement System Components (Junior Agent Execution) <!-- id: 8 -->
    - [x] T-001: Type Definitions (`alm_types.py`) <!-- id: 9 -->
    - [x] T-002: Market Data Provider (`market_data.py`) <!-- id: 10 -->
    - [x] T-003: XML Parsing (`xml_parser.py`) <!-- id: 11 -->
    - [x] T-004: Trade Logic (`trade_logic.py`) <!-- id: 12 -->
    - [x] T-005: Main Script (`alm_core.py`) <!-- id: 13 -->
- [x] Verify execution and CSV output (`alm_trades-history.csv`) <!-- id: 14 -->
- [x] Update Requirements (Dividends, Flows) <!-- id: 15 -->
- [x] Implement Dividends & Flows (Junior Agent) <!-- id: 16 -->
    - [x] T-001 (Update): Type Definitions (`alm_types.py`) <!-- id: 17 -->
    - [x] T-003 (Update): XML Parsing Dividends (`xml_parser.py`) <!-- id: 18 -->
    - [x] T-004 (Update): Dividend & Flow Logic (`trade_logic.py`) <!-- id: 19 -->
    - [x] T-005 (Update): CSV Output (`alm_core.py`) <!-- id: 20 -->
- [x] Verify Dividends & Flows (`trades-test.xml` -> CSV) <!-- id: 21 -->
- [x] Implement Clean Drawdown (F-CALC-065) <!-- id: 22 -->
    - [x] T-001 (Update): Portfolio State (`alm_types.py`) <!-- id: 23 -->
    - [x] T-004 (Update): Drawdown Logic (`trade_logic.py`) <!-- id: 24 -->
    - [x] Verify Outflow Drawdown Behavior <!-- id: 25 -->
- [x] Reorganize Python files into `py_portfolio` <!-- id: 26 -->
- [x] Implement ALM Viewer (`alm_viewer.py`) <!-- id: 27 -->
    - [x] T-001: Type Definitions (`py_portfolio/alm_viewer_types.py`) <!-- id: 28 -->
    - [x] T-002: CSV Loader (`py_portfolio/alm_csv_loader.py`) <!-- id: 29 -->
    - [x] T-003: HTML Generator (`py_portfolio/alm_html_gen.py`) <!-- id: 30 -->
    - [x] T-004: Entry Point (`alm_viewer.py`) <!-- id: 31 -->
- [x] Implement XML Output Interface (ICD) <!-- id: 32 -->
    - [x] T-001 (Update): Types and State (`alm_types.py`) <!-- id: 33 -->
    - [x] T-002 (Update): Logic and PnL (`trade_logic.py`) <!-- id: 34 -->
    - [x] T-003 (New): XML Generator (`alm_xml_gen.py`) <!-- id: 35 -->
    - [x] T-004 (Update): Core Orchestration (`alm_core.py`) <!-- id: 36 -->
    - [x] Verify XML Output against ICD <!-- id: 37 -->

## Data Fetcher Implementation <!-- id: 38 -->
- [x] Define Interfaces (`icd_datafetcher.csv`, `alm_datafetcher.csv`) <!-- id: 39 -->
- [x] Implement Data Fetcher (`py_datafetcher/`) <!-- id: 40 -->
    - [x] Config Loader & Provider Interfaces <!-- id: 41 -->
    - [x] Yahoo Provider Integration <!-- id: 42 -->
    - [x] Caching Manager & Orchestrator <!-- id: 43 -->
    - [x] CLI Interface (`datafetcher.py`) <!-- id: 44 -->
- [x] Verify Data Fetcher standalone <!-- id: 45 -->

## Portfolio History Implementation <!-- id: 46 -->
- [x] Define Architecture (`IMP_portfolio-history.md`) <!-- id: 47 -->
- [x] Implement Components (`py_portfolio_history/`) <!-- id: 48 -->
    - [x] Domain Models and Decimal Logic <!-- id: 49 -->
    - [x] Market Data Manager (Lazy Fetching) <!-- id: 50 -->
    - [x] XML Parser (`trades.xml`) <!-- id: 51 -->
    - [x] FIFO Engine & Metrics Calculator <!-- id: 52 -->
    - [x] XML Output Generator (`portfolio-history.xml`) <!-- id: 53 -->
- [x] Verify Integration (`portfolio-history.py` with `trades.xml`) <!-- id: 54 -->
