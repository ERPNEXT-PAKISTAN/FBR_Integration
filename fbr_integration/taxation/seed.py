"""Idempotent seed data: default tax profiles and FBR Retail Price list."""

from __future__ import annotations

import frappe

from fbr_integration.taxation.constants import (
	DEFAULT_RETAIL_PRICE_LIST,
	SALE_TYPE_EXEMPT,
	SALE_TYPE_FIXED_NOTIFIED,
	SALE_TYPE_REDUCED,
	SALE_TYPE_STANDARD,
	SALE_TYPE_THIRD_SCHEDULE,
	SALE_TYPE_ZERO_RATE,
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_SALES_VALUE,
)
from fbr_integration.taxation.retail_price import ensure_fbr_retail_price_list

DEFAULT_PROFILES = (
	{
		"profile_name": "Standard Taxable Goods",
		"sale_type": SALE_TYPE_STANDARD,
		"tax_calculation_basis": TAX_BASIS_SALES_VALUE,
		"default_sales_tax_rate": 18,
		"description": "GST on actual sales value. Use for goods that are not Third Schedule.",
	},
	{
		"profile_name": "3rd Schedule Goods",
		"sale_type": SALE_TYPE_THIRD_SCHEDULE,
		"tax_calculation_basis": TAX_BASIS_RETAIL_PRICE,
		"default_sales_tax_rate": 18,
		"requires_retail_price": 1,
		"description": "GST on printed retail price / MRP × quantity. Selling rate stays commercial.",
	},
	{
		"profile_name": "Zero-Rated Goods",
		"sale_type": SALE_TYPE_ZERO_RATE,
		"tax_calculation_basis": TAX_BASIS_SALES_VALUE,
		"default_sales_tax_rate": 0,
		"description": "Zero-rated goods. Tax basis remains sales value.",
	},
	{
		"profile_name": "Exempt Goods",
		"sale_type": SALE_TYPE_EXEMPT,
		"tax_calculation_basis": TAX_BASIS_SALES_VALUE,
		"default_sales_tax_rate": 0,
		"description": "Exempt goods. Tax basis remains sales value.",
	},
	{
		"profile_name": "Reduced Rate Goods",
		"sale_type": SALE_TYPE_REDUCED,
		"tax_calculation_basis": TAX_BASIS_SALES_VALUE,
		"description": "Reduced-rate goods. Rate comes from the Item Tax Template when present.",
	},
	{
		"profile_name": "Fixed / Notified Value Goods",
		"sale_type": SALE_TYPE_FIXED_NOTIFIED,
		"tax_calculation_basis": TAX_BASIS_FIXED_NOTIFIED,
		"default_sales_tax_rate": 18,
		"requires_fixed_notified_value": 1,
		"description": "GST on FBR notified / fixed value × quantity.",
	},
)


def seed_default_tax_profiles():
	if not frappe.db.exists("DocType", "FBR Tax Profile"):
		return
	for row in DEFAULT_PROFILES:
		name = row["profile_name"]
		if frappe.db.exists("FBR Tax Profile", name):
			continue
		doc = frappe.get_doc({"doctype": "FBR Tax Profile", "enabled": 1, **row})
		doc.insert(ignore_permissions=True)


def seed_fbr_retail_price_list():
	if not frappe.db.exists("DocType", "Price List"):
		return DEFAULT_RETAIL_PRICE_LIST
	return ensure_fbr_retail_price_list()


def set_settings_price_list_default():
	if not frappe.db.exists("DocType", "FBR Invoice Settings"):
		return
	try:
		current = frappe.db.get_single_value("FBR Invoice Settings", "fbr_retail_price_list")
	except Exception:
		return
	if not current:
		frappe.db.set_single_value("FBR Invoice Settings", "fbr_retail_price_list", DEFAULT_RETAIL_PRICE_LIST)


def sync_retail_price_payload_mapping():
	"""Stop mapping fixedNotifiedValueOrRetailPrice from item.rate so the engine can set it."""
	if not frappe.db.exists("DocType", "FBR Payload Field Mapping Detail"):
		return
	rows = frappe.get_all(
		"FBR Payload Field Mapping Detail",
		filters={"payload_field": "fixedNotifiedValueOrRetailPrice"},
		fields=["name", "source_field", "source_doctype"],
		ignore_permissions=True,
	)
	for row in rows:
		source_field = (row.source_field or "").strip()
		if source_field.endswith(".rate") or source_field == "rate":
			frappe.db.set_value(
				"FBR Payload Field Mapping Detail",
				row.name,
				{
					"source_doctype": "",
					"source_field": "",
					"current_source": "Computed / FBR Tax Engine",
					"description": (
						"Unit MRP or notified value from the FBR tax snapshot. "
						"0 for Sales Value profiles. Legacy invoices without a profile still send Rate."
					),
				},
				update_modified=False,
			)


def sync_fbr_taxation_masters():
	seed_fbr_retail_price_list()
	seed_default_tax_profiles()
	set_settings_price_list_default()
	sync_retail_price_payload_mapping()
	ensure_workspace_link()


def ensure_workspace_link():
	if not frappe.db.exists("Workspace", "FBR Pakistan"):
		return
	try:
		ws = frappe.get_doc("Workspace", "FBR Pakistan")
	except Exception:
		return
	for link in ws.get("links") or []:
		if getattr(link, "link_to", None) == "FBR Tax Profile":
			return
	insert_idx = None
	for idx, link in enumerate(ws.get("links") or []):
		if getattr(link, "label", None) == "Tax Masters" and getattr(link, "type", None) == "Card Break":
			insert_idx = idx + 1
			link.link_count = (link.link_count or 0) + 1
			break
	row = {
		"label": "FBR Tax Profile",
		"link_to": "FBR Tax Profile",
		"link_type": "DocType",
		"type": "Link",
	}
	if insert_idx is None:
		ws.append("links", row)
	else:
		ws.append("links", row)
		links = ws.get("links")
		links.insert(insert_idx, links.pop())
	ws.flags.ignore_permissions = True
	ws.flags.ignore_links = True
	ws.save(ignore_permissions=True)
