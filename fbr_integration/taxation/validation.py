"""Authoritative FBR tax-row validation before submission / FBR send."""

from __future__ import annotations

import frappe
from frappe.utils import cint, cstr, flt

from fbr_integration.taxation.constants import (
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_MANUAL,
	TAX_BASIS_RETAIL_PRICE,
)
from fbr_integration.taxation.profile import get_taxation_settings, profile_to_dict, resolve_tax_profile

FBR_INVOICE_DOCTYPES = ("Sales Invoice", "POS Invoice")


def _item_label(item) -> str:
	idx = getattr(item, "idx", None) or "?"
	code = getattr(item, "item_code", None) or getattr(item, "item_name", None) or "Unknown"
	return f"Row {idx} — Item {code}"


def validate_fbr_tax_row(item, doc=None, profile=None, *, require_profile=False, scope="full"):
	"""Raise with row/item/field context when a required FBR value is missing.

	scope:
	- ``basis``: only MRP / notified / manual taxable value
	- ``full``: HS Code, UOM, Sale Type, SRO, and basis fields
	"""
	errors = []
	profile = profile or resolve_tax_profile(item, doc)
	data = profile_to_dict(profile)
	basis = (
		cstr(getattr(item, "custom_fbr_tax_calculation_basis", None)).strip()
		or data.get("tax_calculation_basis")
		or ""
	)

	if require_profile and not data:
		errors.append("FBR Tax Profile is required.")

	if scope == "full":
		if not cstr(getattr(item, "custom_hs_code", None)).strip():
			errors.append("HS Code is required.")
		if not cstr(getattr(item, "custom_fbr_uom", None)).strip():
			errors.append("FBR UOM is required.")
		if not cstr(getattr(item, "custom_sale_type", None)).strip() and not data.get("sale_type"):
			errors.append("Sale Type is required.")
		if data.get("requires_sro_fields"):
			if not cstr(getattr(item, "custom_sro_schedule_no", None)).strip():
				errors.append("SRO Schedule No is required by the FBR Tax Profile.")
			if not cstr(getattr(item, "custom_sro_item_sno", None)).strip():
				errors.append("SRO Item Serial No is required by the FBR Tax Profile.")

	if basis == TAX_BASIS_RETAIL_PRICE or data.get("requires_retail_price"):
		if flt(getattr(item, "custom_fbr_retail_price", None)) <= 0:
			errors.append(
				"FBR Retail Price / MRP is required because the selected FBR Tax Profile "
				"uses Retail Price / MRP as the tax calculation basis."
			)

	if basis == TAX_BASIS_FIXED_NOTIFIED or data.get("requires_fixed_notified_value"):
		if flt(getattr(item, "custom_fbr_fixed_notified_value", None)) <= 0:
			errors.append(
				"Fixed / Notified Value is required because the selected FBR Tax Profile "
				"uses Fixed / Notified Value as the tax calculation basis."
			)

	if basis == TAX_BASIS_MANUAL and flt(getattr(item, "custom_fbr_taxable_value", None)) <= 0:
		errors.append(
			"Manual Taxable Value is required because the selected FBR Tax Profile "
			"uses Manual Taxable Value as the tax calculation basis."
		)

	if errors:
		frappe.throw(f"{_item_label(item)}:\n" + "\n".join(errors))


def validate_fbr_invoice_for_submission(doc, method=None, *, force=False):
	"""Validate tax-profile rows. Existing invoices without profiles are unchanged."""
	if getattr(doc, "doctype", None) not in FBR_INVOICE_DOCTYPES:
		return

	settings = get_taxation_settings()
	full = force or cint(settings.get("validate_fbr_tax_profile_before_submission"))

	for item in doc.get("items") or []:
		profile = resolve_tax_profile(item, doc, settings=settings)
		basis = cstr(getattr(item, "custom_fbr_tax_calculation_basis", None)).strip()
		data = profile_to_dict(profile)
		needs_basis = basis in {
			TAX_BASIS_RETAIL_PRICE,
			TAX_BASIS_FIXED_NOTIFIED,
			TAX_BASIS_MANUAL,
		} or data.get("requires_retail_price") or data.get("requires_fixed_notified_value")

		if full and (profile or basis):
			validate_fbr_tax_row(item, doc, profile=profile, scope="full")
		elif needs_basis:
			validate_fbr_tax_row(item, doc, profile=profile, scope="basis")
