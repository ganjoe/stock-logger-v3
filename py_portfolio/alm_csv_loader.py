import csv
import logging
from typing import List
from .alm_viewer_types import DocItem

class CsvLoader:
    def load_items(self, csv_path: str) -> List[DocItem]:
        """ Reads CSV and returns generic DocItems. """
        items = []
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Map CSV columns to generic DocItem fields
                    # Requirements CSV has columns: ID, Category, Title, Description, Covered By
                    
                    # Safety check for empty rows
                    if not row.get('ID'): continue
                    
                    item = DocItem(
                        uid=row.get('ID', '').strip(),
                        category=row.get('Category', '').strip(),
                        title=row.get('Title', '').strip(),
                        description=row.get('Description', '').strip(),
                        covered_by=row.get('Covered By', '').strip()
                    )
                    items.append(item)
                    
            logging.info(f"Loaded {len(items)} items from {csv_path}")
            return items
            
        except IOError as e:
            logging.error(f"Failed to read CSV file {csv_path}: {e}")
            return []
