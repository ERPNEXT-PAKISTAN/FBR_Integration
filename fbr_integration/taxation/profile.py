"""Resolve the FBR Tax Profile for an invoice item."""

from __future__ import annotations

import frappe
from frappe.utils import cint, cstr

from fbr_integration.taxation.constants import TAX_BASIS_SALES_VALUE


def get_taxation_settings():
	"""Return FBR Invoice Settings values used by the tax engine."""
	defaults = {
		"default_fbr_tax_profile": "",
		"fbr_retail_price_list": "FBR Retail Price",
		"auto_fetch_fbr_retail_price": 1,
		"allow_item_level_tax_profile": 1,
		"validate_fbr_tax_profile_before_submission": 0,
	}
	try:
		if not frappe.db.exists("DocType", "FBR Invoice Settings"):
			return defaults
		values = (
			frappe.db.get_singles_dict("FBR Invoice Settings")
			if hasattr(frappe.db, "get_singles_dict")
			else {}
		) or {}
		for key in list(defaults):
			if key in values and values.get(key) not in (None, ""):
				defaults[key] = values.get(key)
			else:
				try:
					value = frappe.db.get_single_value("FBR Invoice Settings", key)
				except Exception:
					value = None
				if value not in (None, ""):
					defaults[key] = value
	except Exception:
		pass
	defaults["auto_fetch_fbr_retail_price"] = cint(defaults.get("auto_fetch_fbr_retail_price", 1))
	defaults["allow_item_level_tax_profile"] = cint(defaults.get("allow_item_level_tax_profile", 1))
	defaults["validate_fbr_tax_profile_before_submission"] = cint(
		defaults.get("validate_fbr_tax_profile_before_submission", 0)
	)
	return defaults


def _load_profile(name: str):
	profile_name = cstr(name).strip()
	if not profile_name:
		return None
	try:
		if not frappe.db.exists("DocType", "FBR Tax Profile"):
			return None
		if not frappe.db.exists("FBR Tax Profile", profile_name):
			return None
		profile = frappe.get_cached_doc("FBR Tax Profile", profile_name)
	except Exception:
		return None
	if not cint(getattr(profile, "enabled", 1)):
		return None
	return profile


def resolve_tax_profile(item, doc=None, settings=None):
	"""Return the FBR Tax Profile for an item row.

	Priority:
	1. Sales Invoice / POS Invoice Item override
	2. Item master profile (when allowed)
	3. Company / FBR Invoice Settings default
	4. None (existing app behavior)
	"""
	settings = settings or get_taxation_settings()

	row_profile = cstr(getattr(item, "custom_fbr_tax_profile", None)).strip()
	profile = _load_profile(row_profile)
	if profile:
		return profile

	if cint(settings.get("allow_item_level_tax_profile", 1)):
		item_code = cstr(getattr(item, "item_code", None)).strip()
		if item_code:
			try:
				item_profile = frappe.db.get_value("Item", item_code, "custom_fbr_tax_profile")
			except Exception:
				item_profile = None
			profile = _load_profile(item_profile)
			if profile:
				return profile

	return _load_profile(settings.get("default_fbr_tax_profile"))


def profile_to_dict(profile) -> dict:
	if not profile:
		return {}
	return {
		"name": getattr(profile, "name", None),
		"sale_type": cstr(getattr(profile, "sale_type", None)).strip(),
		"tax_calculation_basis": cstr(getattr(profile, "tax_calculation_basis", None)).strip()
		or TAX_BASIS_SALES_VALUE,
		"default_sales_tax_rate": getattr(profile, "default_sales_tax_rate", None) or 0,
		"default_further_tax_rate": getattr(profile, "default_further_tax_rate", None) or 0,
		"default_extra_tax_rate": getattr(profile, "default_extra_tax_rate", None) or 0,
		"default_fed_rate": getattr(profile, "default_fed_rate", None) or 0,
		"further_tax_calculation_basis": cstr(
			getattr(profile, "further_tax_calculation_basis", None)
		).strip()
		or TAX_BASIS_SALES_VALUE,
		"extra_tax_calculation_basis": cstr(getattr(profile, "extra_tax_calculation_basis", None)).strip()
		or TAX_BASIS_SALES_VALUE,
		"fed_calculation_basis": cstr(getattr(profile, "fed_calculation_basis", None)).strip()
		or TAX_BASIS_SALES_VALUE,
		"requires_retail_price": cint(getattr(profile, "requires_retail_price", 0)),
		"requires_fixed_notified_value": cint(getattr(profile, "requires_fixed_notified_value", 0)),
		"requires_sro_fields": cint(getattr(profile, "requires_sro_fields", 0)),
		"sro_schedule_no": cstr(getattr(profile, "sro_schedule_no", None)).strip(),
		"sro_item_serial_no": cstr(getattr(profile, "sro_item_serial_no", None)).strip(),
		"description": cstr(getattr(profile, "description", None)).strip(),
	}
