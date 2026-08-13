"""Allow editing Sales Invoice Item Consider for Tax Withholding checkbox."""

import frappe


def execute():
	# Core field is read_only=1; unlock so users can opt out per line.
	name = "Sales Invoice Item-apply_tds-read_only"
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, "value", "0", update_modified=False)
	else:
		frappe.get_doc(
			{
				"doctype": "Property Setter",
				"doctype_or_field": "DocField",
				"doc_type": "Sales Invoice Item",
				"field_name": "apply_tds",
				"property": "read_only",
				"property_type": "Check",
				"value": "0",
				"name": name,
			}
		).insert(ignore_permissions=True)

	# Keep default checked when parent apply_tds is on; user can uncheck lines.
	frappe.clear_cache(doctype="Sales Invoice Item")
