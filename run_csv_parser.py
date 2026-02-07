#!/usr/bin/env python3
"""
Run CSV Parser - Import CapTrader CSV into trades.xml

Usage:
    python run_csv_parser.py [csv_file]
    
If no file is provided, auto-discovers the newest *.csv file.
"""

from py_csv_parser.csv_parser import main

if __name__ == "__main__":
    main()
