import frappe

from fbr_integration.fbr_payload_mapping import (
	_source_field_link_name,
	sync_payload_source_fields,
)
from fbr_integration.tax_withholding_sync import sync_withholding


def execute():
	sync_withholding()
	sync_payload_source_fields()

	detail_dt = "FBR Payload Field Mapping Detail"
	if not frappe.db.exists("DocType", detail_dt):
		return

	names = frappe.get_all(
		detail_dt,
		filters={"payload_field": "salesTaxWithheldAtSource"},
		pluck="name",
	)
	source_field = _source_field_link_name(
		"Sales Invoice Item", "custom_sales_tax_withheld_at_source"
	)
	for name in names:
		frappe.db.set_value(
			detail_dt,
			name,
			{
				"source_doctype": "Sales Invoice Item",
				"source_field": source_field,
				"transform": "Absolute Float",
				"current_source": "Sales Invoice Item.custom_sales_tax_withheld_at_source",
				"description": (
					"Current: Sales Invoice Item → ST Withheld at Source "
					"(custom_sales_tax_withheld_at_source)."
				),
			},
			update_modified=False,
		)
