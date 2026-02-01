import sys
import os
import logging
from py_portfolio.alm_csv_loader import CsvLoader
from py_portfolio.alm_html_gen import HtmlGenerator

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    # Configuration
    # Defaults
    csv_path = "py_portfolio-history/alm_portfolio-history.csv"
    template_path = "ALM/Polarion - Documentation 1.0.html"
    output_path = "alm_documentation.html"
    
    # Simple Argo override (optional)
    if len(sys.argv) > 1:
        csv_path = sys.argv[1]
    
    logging.info(f"Starting ALM Viewer Generator")
    logging.info(f"CSV Source: {csv_path}")
    logging.info(f"Template Source: {template_path}")
    
    # 1. Load Data
    loader = CsvLoader()
    items = loader.load_items(csv_path)
    if not items:
        logging.error("No items loaded. Exiting.")
        return

    # 2. Generate HTML
    gen = HtmlGenerator(template_path)
    gen.generate(items, output_path)
    
    logging.info(f"Success. View report at: file://{os.path.abspath(output_path)}")

if __name__ == "__main__":
    main()
