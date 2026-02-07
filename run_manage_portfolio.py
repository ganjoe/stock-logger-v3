#!/usr/bin/env python3
"""
Wrapper script to run the Stop-Loss Manager from the root directory.
Delegates to py_manage_portfolio.manage_stoploss.main()
"""
import sys
import os

# Ensure the root directory is in PYTHONPATH so we can import the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py_manage_portfolio.manage_stoploss import main

if __name__ == "__main__":
    main()
