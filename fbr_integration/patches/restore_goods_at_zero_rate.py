import frappe


def execute():
	name = "Goods at Zero-Rate"
	if frappe.db.exists("Sale Type", name):
		current = frappe.db.get_value("Sale Type", name, "name")
		if current != name:
			frappe.db.sql(
				"UPDATE `tabSale Type` SET sale_type=%s, name=%s WHERE name=%s",
				(name, name, current),
			)
		return
	frappe.get_doc({"doctype": "Sale Type", "sale_type": name, "name": name}).insert(
		ignore_permissions=True
	)
