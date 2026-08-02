"""Point invoiceRefNo mapping at FBR source invoice field (not ERP name)."""

import frappe

from fbr_integration.fbr_payload_mapping import _source_field_link_name, sync_payload_source_fields


def execute():
	sync_payload_source_fields()

	detail_dt = "FBR Payload Field Mapping Detail"
	if not frappe.db.exists("DocType", detail_dt):
		return

	source_field = _source_field_link_name("Sales Invoice", "custom_fbr_source_invoice_no")
	for name in frappe.get_all(detail_dt, filters={"payload_field": "invoiceRefNo"}, pluck="name"):
		frappe.db.set_value(
			detail_dt,
			name,
			{
				"source_doctype": "Sales Invoice",
				"source_field": source_field,
				"transform": "Text",
				"current_source": "Sales Invoice.custom_fbr_source_invoice_no",
				"description": (
					"FBR official reference field. Empty for Sale Invoice. "
					"For Credit/Debit Note: original FBR Invoice No."
				),
			},
			update_modified=False,
		)

	# Disable legacy non-API fields if present
	for payload_field in ("referencedInvoiceNo", "sourceInvoiceNo"):
		for name in frappe.get_all(detail_dt, filters={"payload_field": payload_field}, pluck="name"):
			frappe.db.set_value(detail_dt, name, "enabled", 0, update_modified=False)
