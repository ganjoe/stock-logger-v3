#!/usr/bin/env python3
"""
Wrapper script to run the Portfolio Manager CLI.
Delegates to py_portfolio_cli.main()
"""
import sys
import os

# Ensure the root directory is in PYTHONPATH so we can import the package
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from py_portfolio_cli.main import main

if __name__ == "__main__":
    main()
