import frappe

FIELD_NAMES = (
	"Sales Invoice Item-custom_tax_rate",
	"Sales Invoice Item-custom_tax_amount",
	"POS Invoice Item-custom_tax_rate",
	"POS Invoice Item-custom_tax_amount",
)


def execute():
	for name in FIELD_NAMES:
		if frappe.db.exists("Custom Field", name):
			frappe.delete_doc("Custom Field", name, ignore_permissions=True, force=1)

	for doctype in ("Sales Invoice Item", "POS Invoice Item", "Custom Field"):
		frappe.clear_cache(doctype=doctype)
