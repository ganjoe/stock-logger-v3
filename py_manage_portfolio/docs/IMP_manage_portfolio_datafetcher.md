
# Implementation Plan: DataFetcher Error Matrix Logging (IMP_datafetcher_error_matrix.md)

## Context
The DataFetcher module currently logs errors sequentially in a simple CSV format. The requirement is to implement a **Matrix-Based Error Log** (`log_ticker_failed.csv`) where rows represent fetch attempts for a ticker, and columns represent the status/error per provider. This allows for better analysis of provider reliability. The log must be appended to (`F-DF-200`) and include entries for any partial or total failure (`F-DF-190`).

## 1. System Skeleton (Shared Context)

### 1.1 Data Structures
We need a structure to hold the results of a fetch attempt across multiple providers before flushing to disk.

```python
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime

@dataclass
class ProviderResult:
    provider_name: str
    status: str # "OK", "ERROR", "SKIPPED"
    error_message: str = ""

@dataclass
class FetchAttempt:
    timestamp: str # ISO Timestamp
    isin: str
    ticker: str
    # Map of Provider Name -> Result
    # e.g. {"YAHOO": ProviderResult("YAHOO", "ERROR", "404"), "ALPHA_VANTAGE": ProviderResult(...)}
    provider_results: Dict[str, ProviderResult] = field(default_factory=dict)
```

### 1.2 Interface Updates
The `ErrorLogger` class needs to support this structured logging.

```python
class ErrorLogger:
    def __init__(self, output_dir: str, configured_providers: List[str]):
        """
        Args:
            output_dir: Directory for log files.
            configured_providers: List of provider names (e.g. ["YAHOO", "TWELVE_DATA"])
                                  to ensure consistent CSV columns.
        """
        pass

    def log_matrix_entry(self, attempt: FetchAttempt) -> None:
        """
        Writes a single matrix row to 'log_ticker_failed.csv'.
        Columns: Timestamp, ISIN, Ticker, [Provider1], [Provider2], ...
        """
        pass
```

## 2. Implementation Work Orders

### Task T-050: Update ErrorLogger for Matrix Logging
**Target File:** `py_datafetcher/error_logger.py`
**Description:** Implement the `log_matrix_entry` method and the logic to handle dynamic provider columns in the CSV.
**Context:** Uses `FetchAttempt` and `ProviderResult`.
**Code Stub:**
```python
import csv
import os
from typing import List
from .data_models import ProviderType # Assuming FetchAttempt structure is defined or passed as dict

class ErrorLogger:
    def __init__(self, output_dir: str, configured_providers: List[str]):
        self.output_dir = output_dir
        self.matrix_filepath = os.path.join(output_dir, "log_ticker_failed.csv")
        self.provider_columns = sorted([p.upper() for p in configured_providers])
        self._ensure_matrix_header()

    def _ensure_matrix_header(self) -> None:
        """
        Ensures the CSV file exists with columns: Timestamp, ISIN, Ticker, ...Providers...
        If file exists but headers mismatch (e.g. new provider added), we might need to recreate or append with caveats.
        For simplicity: If header differs, maybe just append (flexible) or ignore validation for now.
        Let's implement: Check existence, if not write header.
        """
        # TODO: Implement logic
        pass

    def log_matrix_entry(self, isin: str, ticker: str, results: dict) -> None:
        """
        results: Dict[str, str] mapping ProviderName -> "OK" or "ErrorMsg"
        """
        # TODO: Implement logic
        pass
```
**Algo/Logic Steps for `log_matrix_entry`:**
1. Generate ISO timestamp.
2. Prepare a row dictionary: `{'Timestamp': ..., 'ISIN': ..., 'Ticker': ...}`.
3. For each provider in `self.provider_columns`:
   - Look up the result in the `results` argument.
   - If found, insert the value (e.g., "OK", "Timeout").
   - If not found (provider skipped?), insert "SKIPPED".
4. Append this row to the CSV using `csv.DictWriter`.

### Task T-060: Integrate Matrix Logging into Fetcher Orchestrator
**Target File:** `py_datafetcher/fetcher_core.py`
**Description:** Update `update_asset` loop to track results per provider and call `error_logger.log_matrix_entry` at the end of the fetch process if any failure occurred.
**Context:** Modify the loop over `self.providers`.
**Code Stub:**
```python
    def update_asset(self, isin: str, ticker: str, start_date_hint: Optional[date] = None) -> bool:
        # ... existing setup ...
        
        provider_results = {} # Store results: {"YAHOO": "OK", "TWELVE_DATA": "Error 404"}
        has_any_failure = False

        for provider in self.providers:
            p_name = provider.__class__.__name__.replace("Provider", "").upper() # Normalize name
            try:
                # ... attempt fetch ...
                # If success:
                provider_results[p_name] = "OK"
                break 
            except Exception as e:
                provider_results[p_name] = str(e)
                has_any_failure = True
                continue
        
        # After loop
        if has_any_failure and self.error_logger:
            # We call the matrix logger
            self.error_logger.log_matrix_entry(isin, ticker, provider_results)
            
        # ... validation results ...
```
**Logic:**
- Ensure every attempt (even if one succeeds eventually) clearly documents what happened with previous providers.
- Pass the collected `provider_results` map to the logger.

### Task T-070: Update ErrorLogger Instantiation
**Target File:** `py_datafetcher/service.py` (and potentially `datafetcher.py` legacy if used)
**Description:** Pass the list of configured provider names when initializing `ErrorLogger`.
**Code Stub:**
```python
        # Extract provider names from config
        provider_names = [p.name.value for p in self.config.providers]
        self.error_logger = ErrorLogger(self.config.market_data_dir, provider_names)
```

