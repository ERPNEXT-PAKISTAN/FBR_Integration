import frappe
from frappe.utils import cint

from fbr_integration.fbr_tax_calculation import get_fbr_invoice_doc


def _assert_can_read_invoice(doc):
	doctype = getattr(doc, "doctype", None) or "Sales Invoice"
	if frappe.session.user != "Administrator" and not frappe.has_permission(
		doctype, "read", doc=doc
	):
		frappe.throw(
			f"You do not have permission to read this {doctype}.",
			frappe.PermissionError,
			title="Not Permitted",
		)


@frappe.whitelist()
def send_to_fbr_si(name: str):
	from fbr_integration.fbr_api import send_to_fbr_si as _send

	return _send(name)


@frappe.whitelist()
def get_pos_fbr_status(name: str):
	"""POS summary payload: FBR number, status, QR/barcode after each POS submit."""
	doc = get_fbr_invoice_doc(name)
	_assert_can_read_invoice(doc)

	fbr_no = (getattr(doc, "custom_fbr_invoice_no", None) or "").strip()
	status = (getattr(doc, "custom_fbr_invoice_status", None) or "").strip()
	status_code = (getattr(doc, "custom_fbr_invoice_status_code", None) or "").strip()
	error = (getattr(doc, "custom_fbr_invoice_error", None) or "").strip()

	qr_data_url = ""
	barcode_data_url = ""
	if fbr_no:
		try:
			from fbr_integration.print_barcodes import get_qr_and_barcode_data_uri

			data = get_qr_and_barcode_data_uri(fbr_no)
			qr_data_url = data.get("qr") or ""
			barcode_data_url = data.get("barcode") or ""
		except Exception:
			frappe.log_error(title="FBR POS QR failed", message=frappe.get_traceback())

	return {
		"ok": bool(fbr_no),
		"sales_invoice": doc.name,
		"doctype": doc.doctype,
		"is_pos": cint(getattr(doc, "is_pos", 0)),
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"posting_date": str(doc.posting_date or ""),
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"fbr_invoice_no": fbr_no,
		"fbr_status": status,
		"fbr_status_code": status_code,
		"fbr_error": error,
		"qr_data_url": qr_data_url,
		"barcode_data_url": barcode_data_url,
	}


@frappe.whitelist()
def get_fbr_codes(name: str):
	"""Returns QR + Barcode data urls using custom_fbr_invoice_no."""
	doc = get_fbr_invoice_doc(name)
	_assert_can_read_invoice(doc)

	fbr_no = (getattr(doc, "custom_fbr_invoice_no", None) or "").strip()
	if not fbr_no:
		return {
			"ok": False,
			"message": "FBR Invoice No not found",
			"qr_data_url": "",
			"barcode_data_url": "",
		}

	try:
		from fbr_integration.print_barcodes import get_qr_and_barcode_data_uri

		data = get_qr_and_barcode_data_uri(fbr_no)
		return {
			"ok": True,
			"qr_data_url": data.get("qr") or "",
			"barcode_data_url": data.get("barcode") or "",
		}
	except Exception as e:
		frappe.log_error(title="FBR QR/Barcode generation failed", message=frappe.get_traceback())
		return {
			"ok": False,
			"message": f"QR/Barcode generator failed: {e}",
			"qr_data_url": "",
			"barcode_data_url": "",
		}
