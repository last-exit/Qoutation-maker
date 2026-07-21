from pathlib import Path
import re
import openpyxl

# We import the exact parser logic from app.py to see where it gets these numbers
import sys
sys.path.append(str(Path(__file__).parent.parent))
from app import QuotationApi

api = QuotationApi()
folder = Path(r"G:\My Drive\BOOM TREE\ALL THE QUOTATIONS")

print("Tracing 'Jungle Gym' items in G Drive folder...")
for file in folder.glob("*"):
    if file.name.startswith("~$") or not file.is_file():
        continue
    file_lower = file.name.lower()
    
    # Process Excel
    if file.suffix.lower() == ".xlsx" and any(x in file_lower for x in ["quotation", "quote", "revised", "option", "production"]):
        items = api.parse_excel_file(file)
        for item in items:
            if "jungle gym" in item['original_description'].lower():
                print(f"EXCEL Match in '{file.name}':")
                print(f"  Description: {repr(item['original_description'])}")
                print(f"  Parsed Rate: {item['historical_rate']}")
                print(f"  Unit: {item['unit']}")
                
    # Process PDF
    elif file.suffix.lower() == ".pdf" and any(x in file_lower for x in ["quotation", "quote", "revised", "option", "production"]):
        items = api.parse_pdf_file(file)
        for item in items:
            if "jungle gym" in item['original_description'].lower():
                print(f"PDF Match in '{file.name}':")
                print(f"  Description: {repr(item['original_description'])}")
                print(f"  Parsed Rate: {item['historical_rate']}")
                print(f"  Unit: {item['unit']}")
