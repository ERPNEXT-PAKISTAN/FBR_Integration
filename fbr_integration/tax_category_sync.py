"""Seed the Tax Category masters FBR invoices use."""

import frappe

TAX_CATEGORIES = ("Input Tax", "Output Tax")


def sync_tax_categories():
	"""Create Input Tax and Output Tax. Other tax categories are left untouched."""
	if not frappe.db.exists("DocType", "Tax Category"):
		return

	for title in TAX_CATEGORIES:
		if frappe.db.exists("Tax Category", title):
			continue
		doc = frappe.get_doc({"doctype": "Tax Category", "title": title, "disabled": 0})
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
