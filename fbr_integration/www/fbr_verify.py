"""Public FBR invoice verification page (no legacy signer dependency)."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import cint


def get_context(context):
	context.no_cache = 1
	context.valid = False
	context.message = ""
	context.invoice = None

	invoice_no = (
		frappe.form_dict.get("invoice")
		or frappe.form_dict.get("invoice_no")
		or frappe.form_dict.get("p")
		or ""
	).strip()

	if not invoice_no:
		context.message = _("Provide an FBR Invoice No using ?invoice=")
		return context

	# Prefer Sales Invoice lookup by FBR invoice number
	name = frappe.db.get_value(
		"Sales Invoice",
		{"custom_fbr_invoice_no": invoice_no},
		"name",
	)
	if not name:
		context.message = _("No Sales Invoice found for this FBR Invoice No.")
		return context

	doc = frappe.get_doc("Sales Invoice", name)
	status = (getattr(doc, "custom_fbr_invoice_status", None) or "").strip()
	status_code = (getattr(doc, "custom_fbr_invoice_status_code", None) or "").strip()
	valid = status_code == "00" or status.lower() in {"valid", "success", "accepted"}

	context.valid = bool(valid)
	context.message = _("Valid FBR response") if valid else _("Invoice found, but FBR status is not successful")
	context.invoice = {
		"sales_invoice": doc.name,
		"fbr_invoice_no": getattr(doc, "custom_fbr_invoice_no", "") or "",
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"posting_date": str(doc.posting_date),
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"fbr_status": status,
		"fbr_status_code": status_code,
		"submitted": cint(doc.docstatus) == 1,
	}
	return context
