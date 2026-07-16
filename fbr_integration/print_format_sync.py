import json
from pathlib import Path

import frappe


FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "print_format.json"
SKIP_FIELDS = {"creation", "modified", "modified_by", "owner", "docstatus", "doctype"}


def _load_print_format_fixture_rows():
	with FIXTURE_PATH.open() as handle:
		return json.load(handle)


def sync_print_formats():
	for row in _load_print_format_fixture_rows():
		name = row.get("name")
		doc_type = row.get("doc_type")
		if not name or not doc_type:
			continue

		doc = frappe.get_doc("Print Format", name) if frappe.db.exists("Print Format", name) else frappe.new_doc("Print Format")
		for key, value in row.items():
			if key in SKIP_FIELDS:
				continue
			setattr(doc, key, value)

		doc.flags.ignore_permissions = True
		if doc.is_new():
			doc.insert(ignore_permissions=True)
		else:
			doc.save(ignore_permissions=True)

	frappe.clear_cache(doctype="Print Format")
