import frappe


def execute():
	for row in frappe.get_all("Scenario ID", fields=["name"], limit_page_length=0):
		frappe.delete_doc("Scenario ID", row.name, ignore_permissions=True, force=1)

	frappe.clear_cache(doctype="Scenario ID")
