"""
Error Logger Module for DataFetcher.
Implements structured error logging for failed fetches (F-DF-060).
"""
import csv
import os
from datetime import datetime
from dataclasses import dataclass
from typing import Optional


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

    def __init__(self, output_dir: str, filename: str = "fetch_errors.csv"):
        """
        Initializes the ErrorLogger.

        Args:
            output_dir: Directory where the error log file will be stored.
            filename: Name of the CSV file (default: fetch_errors.csv).
        """
        self.output_dir = output_dir
        self.filepath = os.path.join(output_dir, filename)
        self._ensure_header()

    def _ensure_header(self) -> None:
        """Creates file with header if it doesn't exist."""
        if not os.path.exists(self.filepath):
            # Ensure directory exists
            os.makedirs(self.output_dir, exist_ok=True)
            with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(["Timestamp", "ISIN", "Ticker", "Reason"])

    def log_failure(self, isin: str, ticker: str, reason: str) -> None:
        """
        Appends a failure record to the CSV log.

        Args:
            isin: The ISIN of the failed asset.
            ticker: The ticker symbol used for fetching.
            reason: Description of why the fetch failed.
        """
        timestamp = datetime.now().isoformat()
        # Sanitize reason to avoid breaking CSV format
        clean_reason = reason.replace('\n', ' ').replace('\r', ' ').strip()

        with open(self.filepath, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([timestamp, isin, ticker, clean_reason])

    def get_failed_fetches(self) -> list[FailedFetch]:
        """
        Reads and returns all failed fetches from the log file.

        Returns:
            List of FailedFetch objects.
        """
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
        """Clears the error log by recreating the file with only the header."""
        with open(self.filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["Timestamp", "ISIN", "Ticker", "Reason"])
