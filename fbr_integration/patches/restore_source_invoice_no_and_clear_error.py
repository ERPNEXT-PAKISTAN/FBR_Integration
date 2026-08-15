import frappe

from fbr_integration.fbr_payload_mapping import (
	_source_field_link_name,
	sync_payload_field_mappings,
	sync_payload_fields,
	sync_payload_source_fields,
)
from fbr_integration.pos_invoice_fields import sync_pos_invoice_fbr_fields


def _enable_source_invoice_no_mapping():
	detail_dt = "FBR Payload Field Mapping Detail"
	if not frappe.db.exists("DocType", detail_dt):
		return

	source_field = _source_field_link_name("Sales Invoice", "name")
	for name in frappe.get_all(detail_dt, filters={"payload_field": "sourceInvoiceNo"}, pluck="name"):
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


def execute():
	sync_payload_source_fields()
	sync_payload_fields()
	sync_payload_field_mappings()
	_enable_source_invoice_no_mapping()
	sync_pos_invoice_fbr_fields()

	for dt in ("Sales Invoice", "POS Invoice", "FBR Payload Field Mapping"):
		frappe.clear_cache(doctype=dt)
