"""Remove the hard-coded bank block from the FBR Sales Invoice format."""

import frappe

from fbr_integration.print_format_sync import _load_print_format_fixture_rows


def execute():
	row = next((row for row in _load_print_format_fixture_rows() if row.get("name") == "FBR Sales Invoice"), None)
	if not row or not frappe.db.exists("Print Format", "FBR Sales Invoice"):
		return

	frappe.db.set_value("Print Format", "FBR Sales Invoice", "html", row["html"], update_modified=False)
	frappe.clear_cache(doctype="Print Format")
