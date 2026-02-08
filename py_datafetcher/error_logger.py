"""
Error Logger Module for DataFetcher.
Implements structured error logging for failed fetches (F-DF-060).
"""
import csv
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, List


@dataclass
class FailedFetch:
    """Represents a single failed fetch attempt."""
    timestamp: str
    ticker: str
    isin: str
    reason: str


class ErrorLogger:
    """
    Logs failed fetch attempts to a structured CSV file for later analysis
    and automated retry workflows.
    """

    def __init__(self, output_dir: str, configured_providers: List[str], filename: str = "fetch_errors.csv"):
        """
        Initializes the ErrorLogger.

        Args:
            output_dir: Directory where the error log file will be stored.
            configured_providers: List of provider names (e.g. ["YAHOO", "ALPHAVANTAGE"])
            filename: Name of the standard sequential CSV file.
        """
        self.output_dir = output_dir
        self.filepath = os.path.join(output_dir, filename)
        self.matrix_filepath = os.path.join(output_dir, "log_ticker_failed.csv")
        self.provider_columns = sorted([p.upper() for p in configured_providers])
        
        self._ensure_header()
        self._ensure_matrix_header()

    def _ensure_header(self) -> None:
        """Creates standard error file with header if it doesn't exist."""
        if not os.path.exists(self.filepath):
            os.makedirs(self.output_dir, exist_ok=True)
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "ISIN", "Ticker", "Reason"])

    def _ensure_matrix_header(self) -> None:
        """Creates matrix failure file with provider columns if it doesn't exist."""
        if not os.path.exists(self.matrix_filepath):
            os.makedirs(self.output_dir, exist_ok=True)
            header = ["Timestamp", "ISIN", "Ticker"] + self.provider_columns
            with open(self.matrix_filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(header)

    def log_failure(self, isin: str, ticker: str, reason: str) -> None:
        """Appends a failure record to the standard sequential CSV log."""
        timestamp = datetime.now().isoformat()
        clean_reason = reason.replace('\n', ' ').replace('\r', ' ').strip()
        with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, isin, ticker, clean_reason])

    def log_matrix_entry(self, isin: str, ticker: str, results: dict) -> None:
        """
        Appends a row to the matrix log.
        results: Dict[str, str] mapping normalized provider name (e.g. 'YAHOO') to status/error.
        """
        timestamp = datetime.now().isoformat()
        row = {
            "Timestamp": timestamp,
            "ISIN": isin,
            "Ticker": ticker
        }
        
        # Fill provider columns
        for p_col in self.provider_columns:
            # Check if result for this provider exists in the current attempt
            row[p_col] = results.get(p_col, "SKIPPED")

        fieldnames = ["Timestamp", "ISIN", "Ticker"] + self.provider_columns
        with open(self.matrix_filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writerow(row)

    def get_failed_fetches(self) -> list[FailedFetch]:
        """Reads and returns all failed fetches from the standard log."""
        results = []
        if not os.path.exists(self.filepath):
            return results
        with open(self.filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                results.append(FailedFetch(
                    timestamp=row.get("Timestamp", ""),
                    isin=row.get("ISIN", ""),
                    ticker=row.get("Ticker", ""),
                    reason=row.get("Reason", "")
                ))
        return results

    def clear_log(self) -> None:
        """Clears both logs by recreating them with headers."""
        self._ensure_header() # This is slightly wrong as it only creates if not exists
        # Correctly overwrite:
        with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(["Timestamp", "ISIN", "Ticker", "Reason"])
        
        header = ["Timestamp", "ISIN", "Ticker"] + self.provider_columns
        with open(self.matrix_filepath, 'w', newline='', encoding='utf-8') as f:
            csv.writer(f).writerow(header)
