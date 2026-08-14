import frappe

from fbr_integration.fbr_tax_calculation import (
	DEFAULT_INVOICE_TYPE,
	DEFAULT_SCENARIO_DETAIL,
)


def execute():
	updates = {
		"Sales Invoice-custom_invoice_type": DEFAULT_INVOICE_TYPE,
		"Sales Invoice-custom_scenario_detail": DEFAULT_SCENARIO_DETAIL,
	}
	for field_name, default in updates.items():
		if not frappe.db.exists("Custom Field", field_name):
			continue
		frappe.db.set_value("Custom Field", field_name, "default", default)

	frappe.clear_cache(doctype="Sales Invoice")
