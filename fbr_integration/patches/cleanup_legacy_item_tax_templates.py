"""Remove Item Tax Templates seeded by old fbr_e_invoicing app.

fbr_e_invoicing.patches.v1_3.setup_pakistan_tax_accounts_and_item_templates
created ~40 regional Sales/Purchases Service Tax templates. Current
fbr_integration only ships SN001–SN028 scenario Item Tax Templates via
item_tax_templates.sync_item_tax_templates().
"""

from __future__ import annotations

import frappe

from fbr_integration.item_tax_templates import get_item_tax_template_specs


def _allowed_titles_and_names() -> set[str]:
	allowed: set[str] = set()
	for spec in get_item_tax_template_specs():
		title = (spec.get("title") or "").strip()
		if title:
			allowed.add(title)
		for alias in spec.get("aliases") or []:
			if alias:
				allowed.add(alias)
		for legacy in spec.get("legacy_titles") or []:
			if legacy:
				allowed.add(legacy)
	return allowed


def _is_fbr_scenario_template(name: str, title: str) -> bool:
	"""Keep SN001–SN028 templates (with or without company suffix)."""
	for value in (name or "", title or ""):
		value = value.strip()
		if value.startswith("SN") and len(value) >= 5 and value[2:5].isdigit():
			return True
		# title form: "SN001 - 18% Goods..."
		if value[:5].startswith("SN") and value[2:5].isdigit():
			return True
	return False


def _template_in_use(name: str) -> bool:
	if frappe.db.exists("Sales Invoice Item", {"item_tax_template": name}):
		return True
	if frappe.db.exists("Purchase Invoice Item", {"item_tax_template": name}):
		return True
	if frappe.db.exists("Item Tax", {"item_tax_template": name}):
		return True
	if frappe.db.exists("POS Invoice Item", {"item_tax_template": name}):
		return True
	return False


def execute():
	if not frappe.db.exists("DocType", "Item Tax Template"):
		return

	allowed = _allowed_titles_and_names()
	rows = frappe.get_all(
		"Item Tax Template",
		fields=["name", "title", "disabled"],
		limit_page_length=0,
	)

	deleted = 0
	disabled = 0
	for row in rows:
		name = row.name or ""
		title = (row.title or "").strip()
		if _is_fbr_scenario_template(name, title):
			continue
		if title in allowed or name in allowed:
			continue

		# Legacy regional templates from fbr_e_invoicing / Pakistan CoA seeds
		if _template_in_use(name):
			if not row.disabled:
				frappe.db.set_value("Item Tax Template", name, "disabled", 1, update_modified=False)
				disabled += 1
			continue

		frappe.delete_doc("Item Tax Template", name, force=True, ignore_permissions=True)
		deleted += 1

	frappe.logger("fbr_integration").info(
		"cleanup_legacy_item_tax_templates: deleted=%s disabled=%s", deleted, disabled
	)
