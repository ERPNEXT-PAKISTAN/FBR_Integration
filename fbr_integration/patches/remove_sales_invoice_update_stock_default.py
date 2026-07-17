import frappe


def execute():
	property_setter = "Sales Invoice-update_stock-default"
	if frappe.db.exists("Property Setter", property_setter):
		frappe.delete_doc("Property Setter", property_setter, ignore_permissions=True)

	frappe.clear_cache(doctype="Sales Invoice")
