"""Ensure FBR response custom fields can be updated after submit.

Core Sales Invoice fields are intentionally NOT opened for edit after submit.
"""

import frappe

FBR_ALLOW_ON_SUBMIT = {
	"Sales Invoice": [
		"custom_fbr_digital_invoice_response",
		"custom_fbr_integration_type",
		"custom_fbr_invoice_status",
		"custom_fbr_invoice_status_code",
		"custom_fbr_invoice_error",
		"custom_fbr_invoice_error_code",
		"custom_fbr_submission_time",
		"custom_fbr_invoice_no",
		"custom_fbr_invoice_item_no",
		"custom_fbr_invoice_statuses",
		"custom_fbr_qr_code",
		"custom_qr_code",
		"custom_fbr_responsed",
		"custom_fbr_response",
	],
}


def execute():
	for doctype, fields in FBR_ALLOW_ON_SUBMIT.items():
		for fieldname in fields:
			_set_custom_field_allow_on_submit(doctype, fieldname)

	frappe.clear_cache(doctype="Sales Invoice")


def _set_custom_field_allow_on_submit(doctype, fieldname):
	cf_name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
	if not cf_name:
		return
	frappe.db.set_value("Custom Field", cf_name, "allow_on_submit", 1, update_modified=False)
