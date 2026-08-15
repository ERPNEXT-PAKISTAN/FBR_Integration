import json
from pathlib import Path

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from fbr_integration.pos_invoice_fields import sync_pos_invoice_fbr_fields

SRO_TYPO = "Goods as per SRO.297(|)/2023"
SRO_CORRECT = "Goods as per SRO.297(I)/2023"
ZERO_RATE_LEGACY = "Goods at zero-rate"
ZERO_RATE_OFFICIAL = "Goods at Zero-Rate"
READ_ROLES = (
	"Accounts Manager",
	"Accounts User",
	"Sales Manager",
	"Sales User",
	"Stock Manager",
	"Stock User",
)
LINK_DOCTYPES = ("Sale Type", "HS Code", "FBR UOM")


def _sale_type_fixture_rows():
	path = Path(__file__).resolve().parents[1] / "fixtures" / "sale_type.json"
	return json.loads(path.read_text())


def _ensure_sale_types():
	for row in _sale_type_fixture_rows():
		name = (row.get("sale_type") or row.get("name") or "").strip()
		if not name or frappe.db.exists("Sale Type", name):
			continue
		frappe.get_doc({"doctype": "Sale Type", "sale_type": name, "name": name}).insert(
			ignore_permissions=True
		)


def _remap_sale_type_column(doctype, old, new):
	table = f"tab{doctype}"
	if not frappe.db.table_exists(doctype) or not frappe.db.has_column(doctype, "custom_sale_type"):
		return
	frappe.db.sql(
		f"UPDATE `{table}` SET custom_sale_type = %s WHERE custom_sale_type = %s",
		(new, old),
	)


def _rename_sale_type(old, new):
	current = frappe.db.get_value("Sale Type", {"name": old}, "name")
	if not current:
		return
	if current == new:
		return

	# Case-only rename on a case-insensitive collation is the same row.
	if current.lower() == new.lower():
		frappe.db.sql(
			"UPDATE `tabSale Type` SET sale_type=%s, name=%s WHERE name=%s",
			(new, new, current),
		)
		for doctype in ("Sales Invoice Item", "POS Invoice Item", "Delivery Note Item"):
			_remap_sale_type_column(doctype, current, new)
		return

	if not frappe.db.exists("Sale Type", new):
		try:
			frappe.rename_doc("Sale Type", current, new, force=True, ignore_permissions=True)
			return
		except Exception:
			frappe.db.sql(
				"UPDATE `tabSale Type` SET sale_type=%s, name=%s WHERE name=%s",
				(new, new, current),
			)

	for doctype in ("Sales Invoice Item", "POS Invoice Item", "Delivery Note Item"):
		_remap_sale_type_column(doctype, current, new)
	if frappe.db.exists("Sale Type", current) and current != new:
		frappe.delete_doc("Sale Type", current, ignore_permissions=True, force=1)


def _fix_sro_sale_type_typo():
	_rename_sale_type(SRO_TYPO, SRO_CORRECT)
	_rename_sale_type(ZERO_RATE_LEGACY, ZERO_RATE_OFFICIAL)


def _ensure_item_link_fields():
	create_custom_fields(
		{
			"Item": [
				{
					"fieldname": "custom_hs_code",
					"label": "HS Code",
					"fieldtype": "Link",
					"options": "HS Code",
					"insert_after": "item_group",
					"ignore_user_permissions": 1,
				},
				{
					"fieldname": "custom_fbr_uom",
					"label": "FBR UoM",
					"fieldtype": "Link",
					"options": "FBR UOM",
					"insert_after": "custom_hs_code",
					"ignore_user_permissions": 1,
				},
			]
		},
		ignore_validate=True,
		update=True,
	)

	field_updates = {
		"Item-custom_hs_code": {
			"fieldtype": "Link",
			"options": "HS Code",
			"hidden": 0,
			"fetch_from": None,
			"fetch_if_empty": 0,
			"ignore_user_permissions": 1,
		},
		"Item-custom_fbr_uom": {
			"fieldtype": "Link",
			"options": "FBR UOM",
			"hidden": 0,
			"fetch_from": None,
			"fetch_if_empty": 0,
			"ignore_user_permissions": 1,
		},
		"Sales Invoice Item-custom_hs_code": {
			"fieldtype": "Link",
			"options": "HS Code",
			"fetch_from": "item_code.custom_hs_code",
			"fetch_if_empty": 1,
			"default": "",
			"ignore_user_permissions": 1,
		},
		"Sales Invoice Item-custom_fbr_uom": {
			"fieldtype": "Link",
			"options": "FBR UOM",
			"fetch_from": "item_code.custom_fbr_uom",
			"fetch_if_empty": 1,
			"default": "",
			"ignore_user_permissions": 1,
		},
		"Sales Invoice Item-custom_sale_type": {
			"fieldtype": "Link",
			"options": "Sale Type",
			"ignore_user_permissions": 1,
		},
		"POS Invoice Item-custom_hs_code": {
			"fieldtype": "Link",
			"options": "HS Code",
			"fetch_from": "item_code.custom_hs_code",
			"fetch_if_empty": 1,
			"default": "",
			"ignore_user_permissions": 1,
		},
		"POS Invoice Item-custom_fbr_uom": {
			"fieldtype": "Link",
			"options": "FBR UOM",
			"fetch_from": "item_code.custom_fbr_uom",
			"fetch_if_empty": 1,
			"default": "",
			"ignore_user_permissions": 1,
		},
	}

	for name, values in field_updates.items():
		if not frappe.db.exists("Custom Field", name):
			continue
		frappe.db.set_value("Custom Field", name, values, update_modified=False)


def _ensure_read_permissions():
	for doctype in LINK_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		doc = frappe.get_doc("DocType", doctype)
		existing = {row.role for row in doc.permissions}
		changed = False
		for role in READ_ROLES:
			if role in existing:
				continue
			doc.append(
				"permissions",
				{
					"role": role,
					"read": 1,
					"report": 1,
					"export": 1,
					"print": 1,
					"email": 1,
				},
			)
			changed = True
		if changed:
			doc.save(ignore_permissions=True)


def execute():
	_ensure_sale_types()
	_fix_sro_sale_type_typo()
	_ensure_item_link_fields()
	_ensure_read_permissions()
	sync_pos_invoice_fbr_fields()

	for dt in (
		"Sale Type",
		"HS Code",
		"FBR UOM",
		"Item",
		"Sales Invoice",
		"Sales Invoice Item",
		"POS Invoice",
		"POS Invoice Item",
	):
		frappe.clear_cache(doctype=dt)
