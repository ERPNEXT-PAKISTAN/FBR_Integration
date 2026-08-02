import frappe


@frappe.whitelist()
def send_to_fbr_si(name: str):
	from fbr_integration.fbr_api import send_to_fbr_si as _send

	return _send(name)


@frappe.whitelist()
def get_fbr_codes(name: str):
	"""
	Returns QR + Barcode data urls for Sales Invoice using custom_fbr_invoice_no.
	"""
	if not name:
		frappe.throw("Sales Invoice name is required.")

	doc = frappe.get_doc("Sales Invoice", name)
	if frappe.session.user != "Administrator" and not frappe.has_permission(
		"Sales Invoice", "read", doc=doc
	):
		frappe.throw(
			"You do not have permission to read this Sales Invoice.",
			frappe.PermissionError,
			title="Not Permitted",
		)

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
