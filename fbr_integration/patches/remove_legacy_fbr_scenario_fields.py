import frappe


FIELD_NAMES = [
	"Sales Invoice-custom_fbr_scenario",
	"Sales Invoice-custom_fbr_scenario_apply_mode",
	"Sales Invoice Item-custom_fbr_item_scenario",
]


def execute():
	for name in FIELD_NAMES:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=1)

	for doctype in ("Sales Invoice", "Sales Invoice Item", "Custom Field"):
		frappe.clear_cache(doctype=doctype)
