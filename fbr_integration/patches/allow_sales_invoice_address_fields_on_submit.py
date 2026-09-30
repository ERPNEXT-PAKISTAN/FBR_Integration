"""Allow address-related Sales Invoice fields to be refreshed after submit."""

import frappe


FIELDS = (
	"customer_address",
	"address_display",
	"company_address",
	"company_address_display",
	"company_trn",
)


def execute():
	meta = frappe.get_meta("Sales Invoice")
	for fieldname in FIELDS:
		if not meta.get_field(fieldname):
			continue

		name = f"Sales Invoice-{fieldname}-allow_on_submit"
		values = {
			"doctype": "Property Setter",
			"name": name,
			"doctype_or_field": "DocField",
			"doc_type": "Sales Invoice",
			"field_name": fieldname,
			"property": "allow_on_submit",
			"property_type": "Check",
			"value": "1",
			"is_system_generated": 1,
		}
		if frappe.db.exists("Property Setter", name):
			frappe.db.set_value(
				"Property Setter",
				name,
				{k: v for k, v in values.items() if k != "doctype"},
				update_modified=False,
			)
		else:
			frappe.get_doc(values).insert(ignore_permissions=True)

	frappe.clear_cache(doctype="Sales Invoice")
