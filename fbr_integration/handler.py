import frappe

@frappe.whitelist()
def send_to_fbr_si(name: str):
    from fbr_integration.fbr_api import send_to_fbr_si as _send
    return _send(name)

# ---------------------------------------------------------
# QR/Barcode generator (if you are using the backend QR)
# ---------------------------------------------------------
@frappe.whitelist()
def get_fbr_codes(name: str):
    """
    Returns QR + Barcode data urls for Sales Invoice using custom_fbr_invoice_no.
    """
    doc = frappe.get_doc("Sales Invoice", name)
    fbr_no = (getattr(doc, "custom_fbr_invoice_no", None) or "").strip()

    if not fbr_no:
        return {"ok": False, "message": "FBR Invoice No not found", "qr_data_url": "", "barcode_data_url": ""}

    from fbr.barcode_service import get_qr_and_barcode_data_urls
    data = get_qr_and_barcode_data_urls(fbr_no)
    data["ok"] = True
    return data