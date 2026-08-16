"""Custom fields for the universal FBR taxation engine. Idempotent via create_custom_fields."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

TAX_BASIS_OPTIONS = "Sales Value\nRetail Price / MRP\nFixed / Notified Value\nManual Taxable Value"


def _item_snapshot_fields(insert_after: str) -> list[dict]:
	return [
		{
			"fieldname": "custom_fbr_tax_profile",
			"label": "FBR Tax Profile",
			"fieldtype": "Link",
			"options": "FBR Tax Profile",
			"insert_after": insert_after,
			"description": "Per-item FBR tax rule. Overrides Item master when set.",
		},
		{
			"fieldname": "custom_fbr_tax_calculation_basis",
			"label": "FBR Tax Calculation Basis",
			"fieldtype": "Select",
			"options": TAX_BASIS_OPTIONS,
			"insert_after": "custom_fbr_tax_profile",
			"read_only": 1,
			"description": "Snapshotted at transaction time from the FBR Tax Profile.",
		},
		{
			"fieldname": "custom_fbr_retail_price",
			"label": "FBR Retail Price / MRP",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "custom_fbr_tax_calculation_basis",
			"description": "Unit MRP used for FBR tax valuation. Does not replace Rate.",
		},
		{
			"fieldname": "custom_fbr_fixed_notified_value",
			"label": "FBR Fixed / Notified Value",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "custom_fbr_retail_price",
		},
		{
			"fieldname": "custom_fbr_taxable_value",
			"label": "FBR Taxable Value",
			"fieldtype": "Currency",
			"options": "currency",
			"insert_after": "custom_fbr_fixed_notified_value",
			"read_only": 1,
			"description": "Computed FBR sales-tax base for this row.",
		},
	]


def get_fbr_taxation_custom_fields() -> dict:
	return {
		"Item": [
			{
				"fieldname": "custom_fbr_tax_profile",
				"label": "FBR Tax Profile",
				"fieldtype": "Link",
				"options": "FBR Tax Profile",
				"insert_after": "custom_fbr_uom",
				"description": "Reusable FBR tax rule for this item. Leave blank for standard sales-value GST.",
			},
			{
				"fieldname": "custom_fbr_default_retail_price",
				"label": "Default FBR Retail Price / MRP",
				"fieldtype": "Currency",
				"insert_after": "custom_fbr_tax_profile",
				"description": "Fallback MRP when no Item Price exists on the FBR Retail Price list.",
			},
			{
				"fieldname": "custom_fbr_default_fixed_notified_value",
				"label": "Default FBR Fixed / Notified Value",
				"fieldtype": "Currency",
				"insert_after": "custom_fbr_default_retail_price",
			},
		],
		"Sales Invoice Item": _item_snapshot_fields("custom_sale_type"),
		"POS Invoice Item": [
			{
				"fieldname": "custom_sale_type",
				"label": "Sale Type",
				"fieldtype": "Link",
				"options": "Sale Type",
				"insert_after": "custom_fbr_uom",
				"ignore_user_permissions": 1,
			},
			*_item_snapshot_fields("custom_sale_type"),
		],
	}


def sync_fbr_taxation_fields():
	create_custom_fields(get_fbr_taxation_custom_fields(), ignore_validate=True, update=True)
	_set_item_fetch_from()
	for doctype in (
		"Item",
		"Sales Invoice Item",
		"POS Invoice Item",
		"FBR Invoice Settings",
	):
		frappe.clear_cache(doctype=doctype)


def _set_item_fetch_from():
	for dt in ("Sales Invoice Item", "POS Invoice Item"):
		name = f"{dt}-custom_fbr_tax_profile"
		if frappe.db.exists("Custom Field", name):
			frappe.db.set_value(
				"Custom Field",
				name,
				{"fetch_from": "item_code.custom_fbr_tax_profile", "fetch_if_empty": 1},
				update_modified=False,
			)
