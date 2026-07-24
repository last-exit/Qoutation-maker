"""Builds share links for WhatsApp and Email. Never sends anything itself — the caller
must explicitly open the link (e.g. via webbrowser.open) in response to a user click."""
from urllib.parse import quote


def _item_summary_text(items, max_items=5):
    lines = []
    for item in items[:max_items]:
        qty = item.get("qty", 1)
        desc = str(item.get("description", "")).split("\n")[0][:60]
        lines.append(f"- {desc} (x{qty})")
    if len(items) > max_items:
        lines.append(f"...and {len(items) - max_items} more item(s)")
    return "\n".join(lines)


def build_whatsapp_link(client_name, quote_ref, grand_total, items, phone=None):
    message = (
        f"Quotation for {client_name} (Ref: {quote_ref})\n\n"
        f"{_item_summary_text(items)}\n\n"
        f"Grand Total: AED {grand_total:,.2f}\n\n"
        f"Please find the attached quotation for your review."
    )
    encoded = quote(message)
    if phone:
        digits = "".join(ch for ch in phone if ch.isdigit())
        return f"https://wa.me/{digits}?text={encoded}"
    return f"https://wa.me/?text={encoded}"


def build_mailto_link(client_name, quote_ref, grand_total, items, pdf_path=None, to_email=None):
    subject = quote(f"Quotation {quote_ref} - {client_name}")
    body_lines = [
        f"Dear {client_name},",
        "",
        "Please find below a summary of the attached quotation:",
        "",
        _item_summary_text(items),
        "",
        f"Grand Total: AED {grand_total:,.2f}",
        "",
    ]
    if pdf_path:
        body_lines += [f"(Please attach the generated file manually: {pdf_path})", ""]
    body_lines += ["Best regards,"]
    body = quote("\n".join(body_lines))
    recipient = to_email or ""
    return f"mailto:{recipient}?subject={subject}&body={body}"
