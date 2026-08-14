"""Keep ERPNext Territory names aligned with FBR Buyer Province masters."""

from __future__ import annotations

import frappe


ROOT_TERRITORY = "All Territories"


def ensure_territory_for_buyer_province(province_name: str) -> str | None:
	"""Create a leaf Territory with the same name as Buyer Province if missing."""
	name = (province_name or "").strip()
	if not name:
		return None

	if frappe.db.exists("Territory", name):
		return name

	if not frappe.db.exists("Territory", ROOT_TERRITORY):
		frappe.get_doc(
			{
				"doctype": "Territory",
				"territory_name": ROOT_TERRITORY,
				"is_group": 1,
			}
		).insert(ignore_permissions=True)

	doc = frappe.get_doc(
		{
			"doctype": "Territory",
			"territory_name": name,
			"parent_territory": ROOT_TERRITORY,
			"is_group": 0,
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def sync_territories_from_buyer_provinces() -> list[str]:
	"""Ensure every Buyer Province has a matching Territory. Returns created names."""
	created: list[str] = []
	for row in frappe.get_all("Buyer Province", pluck="name"):
		if frappe.db.exists("Territory", row):
			continue
		ensure_territory_for_buyer_province(row)
		created.append(row)
	return created


def on_buyer_province_update(doc, method=None):
	"""Create Territory when a Buyer Province is saved."""
	ensure_territory_for_buyer_province(doc.name)


def sync_invoice_territory_from_buyer_province(doc, method=None):
	"""Fill empty Territory / Buyer Province from each other when names match."""
	if doc.doctype not in ("Sales Invoice", "POS Invoice"):
		return

	province = (getattr(doc, "custom_buyer_province", None) or "").strip()
	territory = (getattr(doc, "territory", None) or "").strip()

	if province:
		ensure_territory_for_buyer_province(province)
		# FBR buyerProvince is taken from Territory — keep it aligned with Buyer Province.
		if territory != province:
			doc.territory = province
		return

	if territory and frappe.db.exists("Buyer Province", territory):
		doc.custom_buyer_province = territory
