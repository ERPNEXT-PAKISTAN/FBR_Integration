"""Shared FBR taxable-value and sales-tax calculations."""

from __future__ import annotations

import frappe
from frappe.utils import flt

from fbr_integration.taxation.constants import (
	COMPONENT_EXTRA_TAX,
	COMPONENT_FED,
	COMPONENT_FURTHER_TAX,
	COMPONENT_SALES_TAX,
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_MANUAL,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_SALES_VALUE,
)
from fbr_integration.taxation.profile import profile_to_dict, resolve_tax_profile
from fbr_integration.taxation.snapshot import apply_tax_snapshots


def money(value, precision=2):
	return flt(value, precision)


def _item_label(item) -> str:
	idx = getattr(item, "idx", None) or "?"
	code = getattr(item, "item_code", None) or getattr(item, "item_name", None) or "Unknown"
	return f"Row {idx} — Item {code}"


def get_fbr_taxable_value(item, doc=None, *, throw=True):
	"""Return the FBR sales-tax valuation base for one item row.

	Does not change ERPNext ``rate`` or ``amount``.
	"""
	basis = (getattr(item, "custom_fbr_tax_calculation_basis", None) or "").strip() or TAX_BASIS_SALES_VALUE
	qty = flt(getattr(item, "qty", None))
	amount = flt(getattr(item, "amount", None))
	if not amount:
		amount = qty * flt(getattr(item, "rate", None))

	if basis == TAX_BASIS_SALES_VALUE:
		return money(amount)

	if basis == TAX_BASIS_RETAIL_PRICE:
		retail_price = flt(getattr(item, "custom_fbr_retail_price", None))
		if retail_price <= 0:
			if throw:
				frappe.throw(
					f"{_item_label(item)}:\n"
					"FBR Retail Price / MRP is required because the selected FBR Tax Profile "
					"uses Retail Price / MRP as the tax calculation basis."
				)
			return money(0)
		return money(retail_price * qty)

	if basis == TAX_BASIS_FIXED_NOTIFIED:
		notified_value = flt(getattr(item, "custom_fbr_fixed_notified_value", None))
		if notified_value <= 0:
			if throw:
				frappe.throw(
					f"{_item_label(item)}:\n"
					"Fixed / Notified Value is required because the selected FBR Tax Profile "
					"uses Fixed / Notified Value as the tax calculation basis."
				)
			return money(0)
		return money(notified_value * qty)

	if basis == TAX_BASIS_MANUAL:
		return money(getattr(item, "custom_fbr_taxable_value", None))

	return money(amount)


def get_tax_component_base(item, component, doc=None, profile=None, *, throw=False):
	"""Taxable base for a specific tax component.

	Sales tax follows the item/profile tax calculation basis.
	Further Tax, Extra Tax, and FED default to Sales Value unless the profile
	explicitly sets another basis for that component.
	"""
	if component == COMPONENT_SALES_TAX:
		return get_fbr_taxable_value(item, doc, throw=throw)

	basis = TAX_BASIS_SALES_VALUE
	data = profile_to_dict(profile) if profile and not isinstance(profile, dict) else (profile or {})
	if component == COMPONENT_FURTHER_TAX:
		basis = data.get("further_tax_calculation_basis") or TAX_BASIS_SALES_VALUE
	elif component == COMPONENT_EXTRA_TAX:
		basis = data.get("extra_tax_calculation_basis") or TAX_BASIS_SALES_VALUE
	elif component == COMPONENT_FED:
		basis = data.get("fed_calculation_basis") or TAX_BASIS_SALES_VALUE

	original = getattr(item, "custom_fbr_tax_calculation_basis", None)
	try:
		item.custom_fbr_tax_calculation_basis = basis
		return get_fbr_taxable_value(item, doc, throw=throw)
	finally:
		item.custom_fbr_tax_calculation_basis = original


def calculate_sales_tax(item, rate, doc=None, *, throw=True):
	taxable_value = get_fbr_taxable_value(item, doc, throw=throw)
	return money(taxable_value * flt(rate) / 100.0)


def apply_fbr_taxation_to_invoice(doc):
	"""Apply snapshots then per-row FBR tax amounts. Shared by SI and POS Invoice."""
	apply_tax_snapshots(doc)


def apply_item_tax_amounts(doc, item, tax_rows=None, profile=None):
	"""Set FBR tax amount fields on one item from rates and the correct bases."""
	amount = flt(getattr(item, "amount", None))
	if not amount:
		amount = flt(item.qty) * flt(item.rate)
		if hasattr(item, "amount") and not item.amount:
			item.amount = amount

	profile = profile or resolve_tax_profile(item, doc)
	data = profile_to_dict(profile)

	if hasattr(item, "custom_sales_tax_rate"):
		item.custom_sales_tax_rate = 0
	if hasattr(item, "custom_further_tax_rate"):
		item.custom_further_tax_rate = 0
	if hasattr(item, "custom_extra_tax_rate"):
		item.custom_extra_tax_rate = 0
	if hasattr(item, "custom_sales_tax"):
		item.custom_sales_tax = 0
	if hasattr(item, "custom_further_tax"):
		item.custom_further_tax = 0
	if hasattr(item, "custom_extra_tax"):
		item.custom_extra_tax = 0
	if hasattr(item, "custom_total_tax_amount"):
		item.custom_total_tax_amount = 0
	if hasattr(item, "custom_tax_inclusive_amount"):
		item.custom_tax_inclusive_amount = amount

	sales_rate = 0.0
	further_rate = 0.0
	extra_rate = 0.0
	for tr in tax_rows or []:
		tax_type = (tr.get("tax_type") or "") if isinstance(tr, dict) else getattr(tr, "tax_type", "")
		tax_rate = flt(tr.get("tax_rate") if isinstance(tr, dict) else getattr(tr, "tax_rate", 0))
		lower = tax_type.lower()
		if any(key in lower for key in ("general sales tax", "sales tax", "gst", "output tax", "vat")):
			sales_rate = tax_rate
		elif "further tax" in lower:
			further_rate = tax_rate
		elif "extra tax" in lower:
			extra_rate = tax_rate

	if tax_rows and len(tax_rows) == 1 and sales_rate == 0:
		only = tax_rows[0]
		sales_rate = flt(only.get("tax_rate") if isinstance(only, dict) else getattr(only, "tax_rate", 0))

	if sales_rate == 0:
		sales_rate = flt(data.get("default_sales_tax_rate"))
	if further_rate == 0:
		further_rate = flt(data.get("default_further_tax_rate"))
	if extra_rate == 0:
		extra_rate = flt(data.get("default_extra_tax_rate"))

	if hasattr(item, "custom_sales_tax_rate"):
		item.custom_sales_tax_rate = sales_rate
	if hasattr(item, "custom_further_tax_rate"):
		item.custom_further_tax_rate = further_rate
	if hasattr(item, "custom_extra_tax_rate"):
		item.custom_extra_tax_rate = extra_rate

	sales_base = get_tax_component_base(item, COMPONENT_SALES_TAX, doc, profile=data, throw=False)
	further_base = get_tax_component_base(item, COMPONENT_FURTHER_TAX, doc, profile=data, throw=False)
	extra_base = get_tax_component_base(item, COMPONENT_EXTRA_TAX, doc, profile=data, throw=False)

	if hasattr(item, "custom_fbr_taxable_value"):
		item.custom_fbr_taxable_value = sales_base

	if hasattr(item, "custom_sales_tax"):
		item.custom_sales_tax = money(sales_base * sales_rate / 100.0)
	if hasattr(item, "custom_further_tax"):
		item.custom_further_tax = money(further_base * further_rate / 100.0)
	if hasattr(item, "custom_extra_tax"):
		item.custom_extra_tax = money(extra_base * extra_rate / 100.0)

	total_tax = (
		flt(getattr(item, "custom_sales_tax", None))
		+ flt(getattr(item, "custom_further_tax", None))
		+ flt(getattr(item, "custom_extra_tax", None))
	)
	if hasattr(item, "custom_total_tax_amount"):
		item.custom_total_tax_amount = money(total_tax)
	if hasattr(item, "custom_tax_inclusive_amount"):
		item.custom_tax_inclusive_amount = money(amount + total_tax)

	return sales_base
