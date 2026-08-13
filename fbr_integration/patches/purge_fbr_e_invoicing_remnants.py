"""Fully purge leftovers from the uninstalled old app ``fbr_e_invoicing``.

That app's patch ``v1_3.setup_pakistan_tax_accounts_and_item_templates`` created
regional Item Tax Templates. ``fbr_e_invoicing`` is no longer installed; this
patch removes residual Patch Log rows, desktop icons, and re-runs template cleanup
so migrate never leaves those seeds behind.
"""

from __future__ import annotations

import frappe

from fbr_integration.patches.cleanup_legacy_item_tax_templates import execute as cleanup_tax_templates


def _delete_all(doctype: str, filters: dict | list):
	if not frappe.db.exists("DocType", doctype):
		return 0
	names = frappe.get_all(doctype, filters=filters, pluck="name", ignore_permissions=True)
	for name in names:
		try:
			frappe.delete_doc(doctype, name, force=True, ignore_permissions=True)
		except Exception:
			frappe.db.delete(doctype, {"name": name})
	return len(names)


def execute():
	# 1) Historical patch log from old app (cannot re-run without the app on disk)
	deleted_patches = frappe.db.sql(
		"DELETE FROM `tabPatch Log` WHERE patch LIKE 'fbr_e_invoicing.%'"
	)
	# sql returns rowcount differently; also clear via ORM-style
	frappe.db.sql("DELETE FROM `tabPatch Log` WHERE patch LIKE %s", ("fbr_e_invoicing.%",))

	# 2) Desktop / nav leftovers pointing at old app
	_delete_all("Desktop Icon", {"app": "fbr_e_invoicing"})
	if frappe.db.exists("DocType", "Desktop Icon"):
		for name in frappe.get_all(
			"Desktop Icon",
			or_filters={
				"label": ["like", "%Pak Compliance%"],
				"name": ["like", "%fbr_e%"],
			},
			pluck="name",
			ignore_permissions=True,
		):
			frappe.delete_doc("Desktop Icon", name, force=True, ignore_permissions=True)

	# 3) Orphan module defs for old app
	_delete_all("Module Def", {"app_name": "fbr_e_invoicing"})

	# 4) Any DocTypes still registered under old module names
	for module in ("FBR E Invoicing", "FBR E-Invoicing", "fbr_e_invoicing"):
		for name in frappe.get_all("DocType", filters={"module": module}, pluck="name"):
			try:
				frappe.delete_doc("DocType", name, force=True, ignore_permissions=True)
			except Exception:
				pass
		_delete_all("Module Def", {"name": module})

	# 5) Ensure regional templates from that app stay gone
	cleanup_tax_templates()

	frappe.clear_cache()
	frappe.logger("fbr_integration").info("Purged fbr_e_invoicing remnants")
