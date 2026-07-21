import fitz
from pathlib import Path

pdf_path = Path(r"G:\My Drive\BOOM TREE\ALL THE QUOTATIONS\Boom Tree - Production & Installation - Maple Bear @ Town Square.pdf")
doc = fitz.open(str(pdf_path))

for page_idx, page in enumerate(doc):
    print(f"\n--- PAGE {page_idx+1} ---")
    lines = [line.strip() for line in page.get_text("text").split('\n') if line.strip()]
    for idx, line in enumerate(lines):
        if "jungle gym" in line.lower() or "platform" in line.lower():
            # Print the line and the next 10 lines
            print(f"Index {idx}: {repr(line)}")
            for j in range(1, 11):
                if idx + j < len(lines):
                    print(f"  +{j}: {repr(lines[idx+j])}")
            print("-" * 30)
