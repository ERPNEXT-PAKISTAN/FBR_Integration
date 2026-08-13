"""Ensure referencedInvoiceNo maps to Sales Invoice name (ERP voucher)."""

import frappe

from fbr_integration.fbr_payload_mapping import (
	_source_field_link_name,
	sync_payload_field_mappings,
	sync_payload_fields,
	sync_payload_source_fields,
)


def execute():
	sync_payload_source_fields()
	sync_payload_fields()
	sync_payload_field_mappings()

	detail_dt = "FBR Payload Field Mapping Detail"
	if not frappe.db.exists("DocType", detail_dt):
		return

	source_field = _source_field_link_name("Sales Invoice", "name")
	for name in frappe.get_all(detail_dt, filters={"payload_field": "referencedInvoiceNo"}, pluck="name"):
		frappe.db.set_value(
			detail_dt,
			name,
			{
				"enabled": 1,
				"source_doctype": "Sales Invoice",
				"source_field": source_field,
				"transform": "Text",
				"current_source": "Sales Invoice.name",
			},
			update_modified=False,
		)
