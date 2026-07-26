"""Dynamic Excel/Word quotation generation.

Rows are generated to exactly match the item list — no leftover blank template rows,
regardless of whether the draft has 1 item or 100.
"""
import base64
import io
import json
from datetime import datetime, timedelta
from pathlib import Path

import openpyxl
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from PIL import Image as PILImage, ImageOps

from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY_HEX = "1F497D"  # kept as a fallback constant; live styling now reads from COMPANY below

# --- Company branding config -------------------------------------------------------

COMPANY_CONFIG_PATH = Path(__file__).resolve().parent / "company.json"

# Confirmed by the business owner: "Red Cube" is the company running this app; "Boom Tree"
# is one of their clients (their Drive sync folder is just named after that client's
# ongoing job). Edit company.json directly to correct name/colors/logo/PM — no code change
# needed; this dict only seeds the file the first time it's created.
# primary_hex/accent_hex are sampled from the real Red Cube logo (near-black + red) rather
# than an invented palette, so generated documents carry the company's actual brand colors.
_DEFAULT_COMPANY = {
    "name": "RED CUBE",
    "tagline": "Quotation & Cost Estimate",
    "primary_hex": "141313",
    "accent_hex": "DB302F",
    "logo_path": "assets/red_cube_logo.png",
    "pm_name": "",
}


def _load_company_config():
    try:
        if COMPANY_CONFIG_PATH.exists():
            with open(COMPANY_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("name"):
                return {**_DEFAULT_COMPANY, **data}
    except Exception as e:
        print(f"Failed to load company.json, using built-in defaults: {e}")

    try:
        with open(COMPANY_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_COMPANY, f, indent=2)
    except Exception as e:
        print(f"Could not write company.json: {e}")

    return _DEFAULT_COMPANY


COMPANY = _load_company_config()

# --- Terms / validity config ------------------------------------------------------

TERMS_CONFIG_PATH = Path(__file__).resolve().parent / "terms.json"

_DEFAULT_TERMS = {
    "validity_days": 14,
    "payment_terms": [
        "50% advance payment required upon confirmation of order.",
        "Balance 50% payable prior to event build / handover.",
        "Prices are exclusive of any items not explicitly listed above.",
    ],
}


def _load_terms_config():
    """Loads payment terms / default validity period from terms.json so the business can
    edit its own boilerplate without a code change. Seeds the file with defaults on first run."""
    try:
        if TERMS_CONFIG_PATH.exists():
            with open(TERMS_CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data.get("payment_terms"):
                return data
    except Exception as e:
        print(f"Failed to load terms.json, using built-in defaults: {e}")

    try:
        with open(TERMS_CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(_DEFAULT_TERMS, f, indent=2)
    except Exception as e:
        print(f"Could not write terms.json: {e}")

    return _DEFAULT_TERMS


TERMS_CONFIG = _load_terms_config()


def compute_valid_until(quote_date_str, validity_days=None):
    """Returns quote_date + validity_days as YYYY-MM-DD. Falls back to today + configured
    default if quote_date_str can't be parsed."""
    days = int(validity_days if validity_days is not None else TERMS_CONFIG.get("validity_days", 14))
    try:
        base_date = datetime.strptime(quote_date_str, "%Y-%m-%d")
    except Exception:
        base_date = datetime.now()
    return (base_date + timedelta(days=days)).strftime("%Y-%m-%d")


def compute_totals(items, discount_type=None, discount_value=0.0):
    """Subtotal -> discount -> VAT on discounted subtotal -> grand total. Shared by
    Excel/Word generation and the history record so numbers always match the UI."""
    subtotal = sum(float(i.get("qty", 0) or 0) * float(i.get("rate", 0) or 0) for i in items)
    discount_value = float(discount_value or 0)

    if discount_type == "percent":
        discount_amount = subtotal * (discount_value / 100.0)
    elif discount_type == "flat":
        discount_amount = discount_value
    else:
        discount_amount = 0.0

    discount_amount = max(0.0, min(discount_amount, subtotal))
    discounted_subtotal = subtotal - discount_amount
    vat = discounted_subtotal * 0.05
    grand_total = discounted_subtotal + vat

    return {
        "subtotal": round(subtotal, 2),
        "discount_amount": round(discount_amount, 2),
        "discounted_subtotal": round(discounted_subtotal, 2),
        "vat": round(vat, 2),
        "grand_total": round(grand_total, 2),
    }


# --- Image handling ---------------------------------------------------------------

THUMB_BOX = 60  # px — square display size for line-item photos in the generated Excel sheet


def _prepare_thumbnail(img_bytes, box=THUMB_BOX):
    """Normalizes an arbitrary product photo into a clean, undistorted square thumbnail.

    Two real bugs this fixes: (1) forcing an image into a fixed width/height box without
    preserving aspect ratio stretches/squishes any non-square photo, and (2) CMYK or
    palette-mode source images (common from print-oriented exports) render with garish,
    inverted-looking colors if not normalized to RGB first. Both showed up as "weird
    images" in generated quotes.
    """
    pil_img = PILImage.open(io.BytesIO(img_bytes))

    if pil_img.mode == "RGBA":
        # Flatten transparency onto a white background rather than letting Excel show
        # whatever garbage color sits behind an unsupported alpha channel.
        flattened = PILImage.new("RGB", pil_img.size, (255, 255, 255))
        flattened.paste(pil_img, mask=pil_img.split()[-1])
        pil_img = flattened
    elif pil_img.mode != "RGB":
        pil_img = pil_img.convert("RGB")

    # Fit within the box preserving aspect ratio, then letterbox onto a white square —
    # no stretching, no cropping out part of the product.
    padded = ImageOps.pad(pil_img, (box, box), color=(255, 255, 255), centering=(0.5, 0.5))

    stream = io.BytesIO()
    padded.save(stream, format="PNG")
    stream.seek(0)
    return stream


def _load_logo_scaled(max_width=140, max_height=60):
    """Loads COMPANY['logo_path'] if configured and scales it to fit within a bounding box,
    preserving both aspect ratio and transparency (unlike product thumbnails, a logo should
    keep its native shape rather than get letterboxed onto a white square). Returns
    (stream, width, height) or None if no logo is configured / the file is missing.

    logo_path is normally a relative path (e.g. "assets/red_cube_logo.png") so it stays
    portable in company.json regardless of what directory the app is launched from — resolve
    it against this file's own directory rather than trusting the process's current working
    directory, which a desktop app can't guarantee.
    """
    logo_path = COMPANY.get("logo_path", "")
    if not logo_path:
        return None
    path_obj = Path(logo_path)
    if not path_obj.is_absolute():
        path_obj = Path(__file__).resolve().parent / path_obj
    if not path_obj.exists():
        return None
    try:
        pil_img = PILImage.open(str(path_obj))
        ratio = min(max_width / pil_img.width, max_height / pil_img.height, 1.0)
        w, h = max(1, int(pil_img.width * ratio)), max(1, int(pil_img.height * ratio))
        stream = io.BytesIO()
        pil_img.save(stream, format="PNG")
        stream.seek(0)
        return stream, w, h
    except Exception as e:
        print(f"Failed to load company logo '{logo_path}': {e}")
        return None


def _insert_excel_logo(ws, anchor_cell="F1"):
    """Places the configured logo in the top-right corner of the sheet, out of the way of
    the client/date block that templates typically put on the left."""
    result = _load_logo_scaled()
    if not result:
        return
    stream, w, h = result
    try:
        oxl_img = openpyxl.drawing.image.Image(stream)
        oxl_img.width, oxl_img.height = w, h
        ws.add_image(oxl_img, anchor_cell)
    except Exception as e:
        print(f"Failed to insert company logo into Excel: {e}")


# --- Excel generation -----------------------------------------------------------

def create_fallback_template(dest_path):
    """Creates the branding/header block (rows 1-9) from scratch when no template file exists."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Quotation"

    header_fill = PatternFill(start_color=COMPANY["primary_hex"], end_color=COMPANY["primary_hex"], fill_type="solid")
    font_title = Font(name="Georgia", size=18, bold=True, color=COMPANY["primary_hex"])
    font_subtitle = Font(name="Segoe UI", size=10.5, italic=True, color="6B6B6B")
    font_header = Font(name="Segoe UI", size=10, bold=True, color=COMPANY["accent_hex"])
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    font_normal = Font(name="Segoe UI", size=10)
    align_center = Alignment(horizontal="center", vertical="center")

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
    )

    accent_underline = PatternFill(start_color=COMPANY["accent_hex"], end_color=COMPANY["accent_hex"], fill_type="solid")
    for col in range(1, 8):
        ws.cell(row=1, column=col).fill = accent_underline
    ws.row_dimensions[1].height = 4

    ws['A2'] = COMPANY["name"]
    ws['A2'].font = font_title
    ws['A3'] = COMPANY.get("tagline") or "Quotation Sheet"
    ws['A3'].font = font_subtitle

    ws['A5'] = "Client Name:"
    ws['A5'].font = font_bold
    ws['E5'] = "Date:"
    ws['E5'].font = font_bold
    ws['A6'] = "Venue:"
    ws['A6'].font = font_bold

    headers = ["Item #", "Description", "Unit", "Qty", "Rate (AED)", "VAT 5%", "TOTAL (AED)"]
    for col_idx, text in enumerate(headers, start=1):
        cell = ws.cell(row=9, column=col_idx, value=text)
        cell.font = font_header
        cell.fill = header_fill
        cell.alignment = align_center
        cell.border = thin_border
    ws.row_dimensions[9].height = 25

    ws.column_dimensions['A'].width = 8
    ws.column_dimensions['B'].width = 48
    ws.column_dimensions['C'].width = 10
    ws.column_dimensions['D'].width = 10
    ws.column_dimensions['E'].width = 15
    ws.column_dimensions['F'].width = 13
    ws.column_dimensions['G'].width = 16

    _insert_excel_logo(ws, anchor_cell="F1")

    wb.save(dest_path)


def _detect_template_columns(ws, max_scan_row=25):
    col_map = {}
    header_row = None
    for r in range(1, max_scan_row + 1):
        row_vals = [ws.cell(row=r, column=c).value for c in range(1, 15)]
        row_str = [str(v).strip().lower() if v is not None else "" for v in row_vals]
        if any("description" in v or "particulars" in v for v in row_str):
            header_row = r
            for idx, val in enumerate(row_str, start=1):
                if "item #" in val or "item no" in val or "s.no" in val or "sr no" in val:
                    col_map["item_num"] = idx
                elif "description" in val or "particulars" in val:
                    col_map["description"] = idx
                elif "image" in val or "photo" in val:
                    col_map["images"] = idx
                elif "vat" in val:
                    col_map["vat"] = idx
                elif "total" in val:
                    col_map["total"] = idx
                elif "qty" in val or "quantity" in val:
                    col_map["qty"] = idx
                elif "rate" in val or "unit price" in val:
                    col_map["rate"] = idx
                elif "unit" in val:
                    col_map["unit"] = idx
            break

    if "description" not in col_map:
        col_map = {"item_num": 1, "description": 2, "unit": 3, "qty": 4, "rate": 5, "vat": 6, "total": 7}
        header_row = header_row or 9

    return header_row, col_map


def _style_row(ws, row, col_map, thin_border, has_image=False):
    align_left_wrap = Alignment(horizontal="left", vertical="center", wrap_text=True)
    align_center = Alignment(horizontal="center", vertical="center")
    align_right = Alignment(horizontal="right", vertical="center")
    font_normal = Font(name="Segoe UI", size=10)

    for key, col in col_map.items():
        cell = ws.cell(row=row, column=col)
        cell.font = font_normal
        cell.border = thin_border
        if key == "description":
            cell.alignment = align_left_wrap
        elif key in ("rate", "vat", "total"):
            cell.alignment = align_right
            cell.number_format = '#,##0.00'
        else:
            cell.alignment = align_center

    # The real Red Cube template (sample_quotes/Red Cube - Quotation Format.xlsx) uses a flat
    # 20pt row height throughout — forcing every row to 45pt regardless of content made every
    # generated quote look visibly bloated/off compared to the business's actual documents.
    # Only rows that actually carry a photo need the extra height to avoid clipping it.
    ws.row_dimensions[row].height = 46 if has_image else 20


def _apply_print_setup(ws, last_row, last_col, header_row):
    """Forces the sheet onto a single page width when printed or exported to PDF.

    Without this the generated workbook paginates on Excel's defaults, which split the table
    vertically down the middle — the Qty/Rate/VAT/Total columns landed on a separate sheet of
    the PDF, so the first page a client opened showed the line items with no prices on them.
    """
    try:
        ws.page_setup.orientation = 'landscape'
        ws.page_setup.paperSize = ws.PAPERSIZE_A4
        ws.sheet_properties.pageSetUpPr.fitToPage = True
        ws.page_setup.fitToWidth = 1
        ws.page_setup.fitToHeight = 0  # allow as many pages tall as needed, never wider

        ws.print_area = f"A1:{get_column_letter(last_col)}{last_row}"
        # Repeat the column headings on every page of a long quotation.
        ws.print_title_rows = f"{header_row}:{header_row}"

        ws.page_margins.left = ws.page_margins.right = 0.4
        ws.page_margins.top = ws.page_margins.bottom = 0.5
    except Exception as e:
        print(f"Could not apply print setup: {e}")


def generate_excel_dynamic(items, meta, template_path, output_path):
    """Populates a quotation Excel sheet with exactly len(items) rows plus a discount/summary
    block — never leaves stale empty rows from a fixed-size template."""
    wb = openpyxl.load_workbook(str(template_path), data_only=False)
    ws = wb.active

    header_row, col_map = _detect_template_columns(ws)

    thin_border = Border(
        left=Side(style='thin', color='D9D9D9'), right=Side(style='thin', color='D9D9D9'),
        top=Side(style='thin', color='D9D9D9'), bottom=Side(style='thin', color='D9D9D9')
    )
    font_bold = Font(name="Segoe UI", size=10, bold=True)
    font_grand = Font(name="Segoe UI", size=11.5, bold=True, color=COMPANY["primary_hex"])
    align_right = Alignment(horizontal="right", vertical="center")

    # Clear any pre-existing stale rows below the header from an old fixed template.
    if ws.max_row > header_row:
        stale_last_row = ws.max_row
        ws.delete_rows(header_row + 1, stale_last_row - header_row)
        # delete_rows shifts cell VALUES up but leaves the RowDimension height entries behind,
        # so the old template's 55pt rows would otherwise stick to whatever we write next and
        # balloon the summary/terms/signature block onto extra pages. Drop those height entries
        # so any row we don't explicitly size falls back to Excel's compact default.
        for stale_row in range(header_row + 1, stale_last_row + 1):
            if stale_row in ws.row_dimensions:
                del ws.row_dimensions[stale_row]

    # Overwrite the title/subtitle unconditionally rather than trusting whatever static text
    # is baked into the template file — otherwise company.json can say the right name and the
    # actual generated document still shows whatever text someone typed into the template once.
    ws.cell(row=2, column=1, value=COMPANY["name"]).font = Font(name="Georgia", size=16, bold=True, color=COMPANY["primary_hex"])
    ws.cell(row=3, column=1, value=COMPANY.get("tagline") or "Quotation Sheet").font = Font(name="Segoe UI", size=10.5, italic=True, color="6B6B6B")

    quote_date = meta.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
    valid_until = meta.get("valid_until") or compute_valid_until(quote_date)
    font_bold_header = Font(name="Segoe UI", size=10, bold=True)

    if ws.cell(row=5, column=1).value and "client" in str(ws.cell(row=5, column=1).value).lower():
        ws.cell(row=5, column=2, value=meta.get("client_name", ""))
    ws.cell(row=5, column=6, value=quote_date)

    # Write the Venue/Valid Until label + value unconditionally rather than only when the
    # template already has that label — the production template on file turned out to have
    # no "Venue:" field at all, so venue was silently missing from every generated quote.
    ws.cell(row=6, column=1, value="Venue:").font = font_bold_header
    ws.cell(row=6, column=2, value=meta.get("venue", ""))
    ws.cell(row=6, column=5, value="Valid Until:").font = font_bold_header
    ws.cell(row=6, column=6, value=valid_until)

    pm_name = meta.get("pm_name") or COMPANY.get("pm_name", "")
    if pm_name:
        ws.cell(row=7, column=1, value="Prepared By:").font = font_bold_header
        ws.cell(row=7, column=2, value=pm_name)

    quote_ref = meta.get("quote_ref")
    if quote_ref:
        ws.cell(row=7, column=5, value="Quote Ref:").font = font_bold_header
        ws.cell(row=7, column=6, value=quote_ref).font = Font(
            name="Segoe UI", size=10, bold=True, color=COMPANY["accent_hex"])

    desc_col = col_map["description"]
    unit_col = col_map.get("unit")
    qty_col = col_map.get("qty")
    rate_col = col_map.get("rate")
    vat_col = col_map.get("vat")
    tot_col = col_map.get("total")
    img_col = col_map.get("images")

    # The real Red Cube template has no "Images" column at all — without this, any photo a
    # line item carries (from the photo library, a PDF/Excel extraction, or a web search) had
    # nowhere to go in the generated sheet and was silently dropped. Append a trailing Image
    # column rather than inserting one mid-sheet, so none of the existing column letters used
    # by the meta rows above (Date/Venue/Valid Until/Prepared By) shift and break.
    if not img_col and any(item.get('image_base64') for item in items):
        img_col = max(col_map.values()) + 1
        img_col_letter = get_column_letter(img_col)
        header_cell = ws.cell(row=header_row, column=img_col, value="Image")
        ref_header_cell = ws.cell(row=header_row, column=desc_col)
        header_cell.font = ref_header_cell.font.copy()
        header_cell.fill = ref_header_cell.fill.copy()
        header_cell.alignment = Alignment(horizontal="center", vertical="center")
        header_cell.border = ref_header_cell.border.copy()
        ws.column_dimensions[img_col_letter].width = 11

    current_row = header_row + 1
    for idx, item in enumerate(items, 1):
        if "item_num" in col_map:
            ws.cell(row=current_row, column=col_map["item_num"], value=idx)

        ws.cell(row=current_row, column=desc_col, value=item.get('description', ''))
        if unit_col:
            ws.cell(row=current_row, column=unit_col, value=item.get('unit', 'Pcs'))
        if qty_col:
            ws.cell(row=current_row, column=qty_col, value=float(item.get('qty', 0) or 0))
        if rate_col:
            ws.cell(row=current_row, column=rate_col, value=float(item.get('rate', 0) or 0))

        if qty_col and rate_col:
            qty_letter = get_column_letter(qty_col)
            rate_letter = get_column_letter(rate_col)
            if vat_col:
                ws.cell(row=current_row, column=vat_col, value=f"=ROUND({qty_letter}{current_row}*{rate_letter}{current_row}*0.05,2)")
            if tot_col:
                # Matches the real template's own formula (qty*rate*1.05) — the per-row TOTAL
                # column is VAT-inclusive there. Writing plain qty*rate here under-totaled every
                # line item by its VAT amount versus what the business's actual quotes show.
                ws.cell(row=current_row, column=tot_col, value=f"=ROUND({qty_letter}{current_row}*{rate_letter}{current_row}*1.05,2)")

        row_has_image = False
        if item.get('image_base64') and img_col:
            try:
                b64_data = item['image_base64'].split(",")[1]
                img_bytes = base64.b64decode(b64_data)
                tmp_stream = _prepare_thumbnail(img_bytes, THUMB_BOX)
                oxl_img = openpyxl.drawing.image.Image(tmp_stream)
                oxl_img.width = THUMB_BOX
                oxl_img.height = THUMB_BOX
                ws.add_image(oxl_img, f"{get_column_letter(img_col)}{current_row}")
                row_has_image = True
            except Exception as e:
                print(f"Failed to insert image into Excel: {e}")

        _style_row(ws, current_row, col_map, thin_border, has_image=row_has_image)
        current_row += 1

    totals = compute_totals(items, meta.get("discount_type"), meta.get("discount_value", 0))
    label_col = desc_col
    value_col = tot_col or (rate_col + 1 if rate_col else desc_col + 1)

    def write_summary_row(label, value, bold=False, grand=False):
        nonlocal current_row
        cell_label = ws.cell(row=current_row, column=label_col, value=label)
        cell_label.font = font_grand if grand else (font_bold if bold else Font(name="Segoe UI", size=10))
        cell_label.alignment = align_right
        cell_value = ws.cell(row=current_row, column=value_col, value=value)
        cell_value.font = font_grand if grand else (font_bold if bold else Font(name="Segoe UI", size=10))
        cell_value.alignment = align_right
        cell_value.number_format = '#,##0.00'
        current_row += 1

    current_row += 1
    write_summary_row("Subtotal (AED)", totals["subtotal"])
    if totals["discount_amount"] > 0:
        write_summary_row("Discount (AED)", -totals["discount_amount"])
    write_summary_row("VAT 5% (AED)", totals["vat"])
    write_summary_row("Grand Total (AED)", totals["grand_total"], grand=True)

    # --- Terms & payment schedule (configurable via terms.json) ---
    current_row += 2
    ws.cell(row=current_row, column=label_col, value="Terms & Payment Schedule").font = Font(name="Segoe UI", size=10.5, bold=True, color=COMPANY["primary_hex"])
    current_row += 1
    ws.cell(row=current_row, column=label_col, value=f"This quotation is valid until {valid_until}.").font = Font(name="Segoe UI", size=9, italic=True)
    current_row += 1
    for term in TERMS_CONFIG.get("payment_terms", []):
        ws.cell(row=current_row, column=label_col, value=f"• {term}").font = Font(name="Segoe UI", size=9)
        current_row += 1

    # --- Client acceptance / signature block ---
    current_row += 2
    ws.cell(row=current_row, column=label_col, value="Client Acceptance").font = Font(
        name="Segoe UI", size=10.5, bold=True, color=COMPANY["primary_hex"])
    current_row += 1
    ws.cell(
        row=current_row, column=label_col,
        value="By signing below, the client accepts the scope, quantities and pricing above and authorises works to proceed.",
    ).font = Font(name="Segoe UI", size=9, italic=True)
    current_row += 2

    sign_border = Border(bottom=Side(style='thin', color='808080'))
    for left_label, right_label in (("Client Name:", "Authorised Signature:"), ("Date:", "Company Stamp:")):
        ws.cell(row=current_row, column=label_col, value=left_label).font = font_bold
        ws.cell(row=current_row, column=label_col + 1).border = sign_border
        right_col = min(label_col + 3, (tot_col or label_col + 4))
        ws.cell(row=current_row, column=right_col, value=right_label).font = font_bold
        ws.cell(row=current_row, column=right_col + 1).border = sign_border
        current_row += 2

    _insert_excel_logo(ws, anchor_cell="F1")

    # Column A carries both the Item # and the meta labels ("Client Name:", "Prepared By:").
    # At the template's default width those labels are clipped as soon as the value cell
    # beside them is filled, so it gets just enough room to show them in full.
    if ws.column_dimensions['A'].width and ws.column_dimensions['A'].width < 13:
        ws.column_dimensions['A'].width = 13

    _apply_print_setup(ws, last_row=current_row, last_col=max(col_map.values()), header_row=header_row)

    wb.save(str(output_path))
    return totals


# --- Word generation ---------------------------------------------------------------

def _set_cell_shading(cell, hex_color):
    shd = OxmlElement('w:shd')
    shd.set(qn('w:fill'), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)


def generate_word_dynamic(items, meta, output_path):
    """Generates a clean Word (.docx) quotation using python-docx. Tables auto-expand,
    so there is no fixed-row-count problem to begin with."""
    doc = Document()
    primary_rgb = RGBColor(*bytes.fromhex(COMPANY["primary_hex"]))
    accent_rgb = RGBColor(*bytes.fromhex(COMPANY["accent_hex"]))

    logo = _load_logo_scaled(max_width=160, max_height=70)
    if logo:
        logo_stream, _, _ = logo
        logo_para = doc.add_paragraph()
        logo_para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        logo_para.add_run().add_picture(logo_stream, width=Cm(3.2))

    title = doc.add_heading(COMPANY["name"], level=1)
    title.runs[0].font.color.rgb = primary_rgb
    title.runs[0].font.name = "Georgia"
    subtitle = doc.add_paragraph(COMPANY.get("tagline") or "Quotation Sheet")
    subtitle.runs[0].italic = True

    quote_date = meta.get("quote_date", datetime.now().strftime("%Y-%m-%d"))
    valid_until = meta.get("valid_until") or compute_valid_until(quote_date)
    pm_name = meta.get("pm_name") or COMPANY.get("pm_name", "")

    meta_rows = [
        ("Client Name:", meta.get("client_name", "")),
        ("Venue:", meta.get("venue", "")),
        ("Date:", quote_date),
        ("Valid Until:", valid_until),
    ]
    if meta.get("quote_ref"):
        meta_rows.insert(0, ("Quote Ref:", meta["quote_ref"]))
    if pm_name:
        meta_rows.append(("Prepared By:", pm_name))

    meta_table = doc.add_table(rows=len(meta_rows), cols=2)
    meta_table.autofit = True
    for i, (label, value) in enumerate(meta_rows):
        meta_table.cell(i, 0).text = label
        meta_table.cell(i, 0).paragraphs[0].runs[0].bold = True
        meta_table.cell(i, 1).text = str(value)

    doc.add_paragraph("")

    headers = ["#", "Image", "Description", "Unit", "Qty", "Rate (AED)", "Total (AED)"]
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    hdr_cells = table.rows[0].cells
    for i, h in enumerate(headers):
        hdr_cells[i].text = h
        hdr_cells[i].paragraphs[0].runs[0].bold = True
        hdr_cells[i].paragraphs[0].runs[0].font.color.rgb = accent_rgb
        hdr_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
        _set_cell_shading(hdr_cells[i], COMPANY["primary_hex"])

    for idx, item in enumerate(items, 1):
        row_cells = table.add_row().cells
        qty = float(item.get('qty', 0) or 0)
        rate = float(item.get('rate', 0) or 0)
        # VAT-inclusive per-row total, matching the real Excel template's own convention
        # (qty*rate*1.05) so Word and Excel outputs agree with each other and with how the
        # business's actual quotes have always been calculated.
        line_total = round(qty * rate * 1.05, 2)

        if item.get('image_base64'):
            try:
                b64_data = item['image_base64'].split(",")[1]
                img_bytes = base64.b64decode(b64_data)
                thumb_stream = _prepare_thumbnail(img_bytes, THUMB_BOX)
                row_cells[1].paragraphs[0].add_run().add_picture(thumb_stream, width=Cm(1.4))
                row_cells[1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
            except Exception as e:
                print(f"Failed to insert image into Word doc: {e}")

        values = [
            str(idx),
            None,  # image column, handled above
            str(item.get('description', '')).split("\n")[0],
            str(item.get('unit', 'Pcs')),
            f"{qty:g}",
            f"{rate:,.2f}",
            f"{line_total:,.2f}",
        ]
        for i, v in enumerate(values):
            if v is None:
                continue
            row_cells[i].text = v
            if i in (0, 3, 4, 5, 6):
                row_cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER

    totals = compute_totals(items, meta.get("discount_type"), meta.get("discount_value", 0))

    doc.add_paragraph("")
    summary_rows = [("Subtotal (AED)", totals["subtotal"])]
    if totals["discount_amount"] > 0:
        summary_rows.append(("Discount (AED)", -totals["discount_amount"]))
    summary_rows.append(("VAT 5% (AED)", totals["vat"]))
    summary_rows.append(("Grand Total (AED)", totals["grand_total"]))

    summary_table = doc.add_table(rows=len(summary_rows), cols=2)
    for i, (label, value) in enumerate(summary_rows):
        summary_table.cell(i, 0).text = label
        summary_table.cell(i, 1).text = f"{value:,.2f}"
        summary_table.cell(i, 1).paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if label.startswith("Grand"):
            for c in (0, 1):
                summary_table.cell(i, c).paragraphs[0].runs[0].bold = True
                summary_table.cell(i, c).paragraphs[0].runs[0].font.color.rgb = primary_rgb
                summary_table.cell(i, c).paragraphs[0].runs[0].font.size = Pt(12)

    # --- Terms & payment schedule (configurable via terms.json) ---
    doc.add_paragraph("")
    terms_heading = doc.add_paragraph()
    terms_heading_run = terms_heading.add_run("Terms & Payment Schedule")
    terms_heading_run.bold = True

    validity_para = doc.add_paragraph(f"This quotation is valid until {valid_until}.")
    validity_para.runs[0].italic = True

    for term in TERMS_CONFIG.get("payment_terms", []):
        doc.add_paragraph(term, style="List Bullet")

    # --- Client acceptance / signature block ---
    doc.add_paragraph("")
    accept_heading = doc.add_paragraph()
    accept_run = accept_heading.add_run("Client Acceptance")
    accept_run.bold = True
    accept_run.font.color.rgb = primary_rgb

    doc.add_paragraph(
        "By signing below, the client confirms acceptance of the scope, quantities and "
        "pricing set out in this quotation, and authorises works to proceed."
    ).runs[0].font.size = Pt(9)

    sign_table = doc.add_table(rows=2, cols=2)
    sign_table.style = "Table Grid"
    sign_labels = [("Client Name:", "Authorised Signature:"), ("Date:", "Company Stamp:")]
    for r, (left, right) in enumerate(sign_labels):
        for c, label in enumerate((left, right)):
            cell = sign_table.cell(r, c)
            cell.text = label
            cell.paragraphs[0].runs[0].bold = True
            cell.paragraphs[0].runs[0].font.size = Pt(9)
            # Blank ruled line for the handwritten entry.
            cell.add_paragraph("")
            cell.add_paragraph("")

    doc.save(str(output_path))
    return totals
