import logging
import os
from typing import List, Dict
from bs4 import BeautifulSoup
from .alm_viewer_types import DocItem, ItemType

class HtmlGenerator:
    def __init__(self, template_path: str):
        self.template_path = template_path
        
    def generate(self, items: List[DocItem], output_path: str):
        """ Fills template tables with items. """
        if not os.path.exists(self.template_path):
            logging.error(f"Template not found: {self.template_path}")
            return
            
        try:
            with open(self.template_path, 'r', encoding='utf-8') as f:
                soup = BeautifulSoup(f, 'html.parser')
                
            # Categorize items
            reqs = [i for i in items if i.item_type == ItemType.REQUIREMENT]
            specs = [i for i in items if i.item_type == ItemType.SPECIFICATION]
            tests = [i for i in items if i.item_type == ItemType.TEST_CASE]
            
            # Inject into Tables
            # We assume the order of Collapsible Sections matches Req -> Spec -> Test
            # Section 2: Requirements
            self._inject_table(soup, "Requirements", reqs, ["ID", "Category", "Title", "Description", "Covered By"])
            
            # Section 3: Specifications
            self._inject_table(soup, "Specifications", specs, ["ID", "Module", "Title", "Technical Implementation", "Traces To", "Covered By"])

            # Section 4: Test Cases
            self._inject_table(soup, "Test Cases", tests, ["ID", "Title", "Procedure & Expectation", "Traces To"])

            # Write output
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(str(soup))
                
            logging.info(f"Generated HTML at {output_path}")
            
        except Exception as e:
            logging.error(f"HTML Generation failed: {e}")

    def _inject_table(self, soup: BeautifulSoup, section_keyword: str, items: List[DocItem], columns: List[str]):
        """ 
        Finds the <table> inside a section identifiable by a header containing section_keyword.
        Clears existing rows and injects new ones.
        """
        # Find Header (h2)
        target_header = None
        for h2 in soup.find_all('h2'):
            if section_keyword in h2.get_text():
                target_header = h2
                break
        
        if not target_header:
            logging.warning(f"Could not find section header for '{section_keyword}'")
            return

        # Find the content div following it
        content_div = target_header.find_next_sibling('div', class_='collapsible-content')
        if not content_div:
            return
            
        table_body = content_div.find('tbody')
        if not table_body:
            return
            
        # Clear existing rows
        table_body.clear()
        
        # Add new rows
        for item in items:
            row = soup.new_tag('tr', id=item.uid)
            
            # Helper to create cell
            def create_cell(content, html=False, class_name=None):
                td = soup.new_tag('td')
                if class_name: td['class'] = class_name
                if html:
                    # Parse simplified HTML content if needed (e.g. for badges)
                    temp_soup = BeautifulSoup(content, 'html.parser')
                    td.append(temp_soup)
                else:
                    td.string = content
                return td

            # Generate cells based on column mapping
            # This is slightly rigid but robust for this template
            
            # ID Column
            row.append(create_cell(item.uid, class_name="id-col"))
            
            # Variable Columns based on Type
            if item.item_type == ItemType.REQUIREMENT:
                # ["ID", "Category", "Title", "Description", "Covered By"]
                row.append(create_cell(f'<span class="badge req">{item.category}</span>', html=True))
                row.append(create_cell(item.title))
                row.append(create_cell(item.description))
                row.append(create_cell(self._format_links(item.covered_by), html=True))
                
            elif item.item_type == ItemType.SPECIFICATION:
                # ["ID", "Module", "Title", "Technical Implementation", "Traces To", "Covered By"]
                # Map CSV Category -> Module, Description -> Technical Impl, Covered By -> Covered By
                # We need separate fields. CSV definition is fixed (Requirements structure).
                # Assumption: CSV is GENERIC. 
                # Category -> Module(Badge)
                # Title -> Title
                # Description -> Tech Impl (for specs)
                # Covered By -> Covered By
                # MISSING: Traces To.
                # Workaround: For Specs, we might need a "Traces To" column in CSV or parse it from Description?
                # The user provided one generic CSV file format.
                # Let's assume the CSV columns are reused appropriately.
                # Since CSV has "Covered By", but Specs need "Traces To" AND "Covered By".
                # Let's check CSV again. It has 5 columns.
                # Spec needs 6.
                # We will just map what we have. Category->Module. Description->TechImpl. Covered By->Covered By.
                # Traces To will be empty/unknown for now unless we parse it specially.
                
                row.append(create_cell(f'<span class="badge spec">{item.category}</span>', html=True))
                row.append(create_cell(item.title))
                row.append(create_cell(item.description))
                row.append(create_cell("-")) # Traces To (Not in CSV)
                row.append(create_cell(self._format_links(item.covered_by), html=True))

            elif item.item_type == ItemType.TEST_CASE:
                # ["ID", "Title", "Procedure & Expectation", "Traces To"]
                # Category -> Badge (Test Type)
                # Description -> Procedure
                # Covered By -> Traces To
                row.append(create_cell(item.title)) # Title is 2nd col here? No, ID is 1st.
                # Wait, Table Header: ID, Title, Procedure, Traces To. (4 cols)
                # CSV has: ID, Category, Title, Description, Covered By.
                # Let's use Category as Badge next to Title? Or just ignore Category column for Test table structure?
                # Template TC Table: ID | Title (with Badge inside?) | Procedure | Traces To
                # Let's put Category as Badge in Title cell like: <span class="badge test">Category</span> Title
                
                title_html = f'<span class="badge test">{item.category}</span> {item.title}'
                row.append(create_cell(title_html, html=True))
                row.append(create_cell(item.description))
                row.append(create_cell(self._format_links(item.covered_by), html=True))

            table_body.append(row)

    def _format_links(self, link_str: str) -> str:
        if not link_str or link_str == "-": return "-"
        links = [l.strip() for l in link_str.split(',')]
        html_parts = []
        for l in links:
            # Simple heuristic: if it looks like an ID, make it a link
            if l:
                html_parts.append(f'<a href="#{l}" class="trace-link">{l}</a>')
        return ", ".join(html_parts)
