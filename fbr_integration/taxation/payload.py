"""FBR JSON helpers for taxable value vs retail/notified price."""

from __future__ import annotations

from frappe.utils import flt

from fbr_integration.taxation.constants import (
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_MANUAL,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_SALES_VALUE,
)


def _line_value(unit, item, *, absolute=False) -> float:
	"""FBR 0102 multiplies this field by the rate only — not by quantity again.

	Send the line retail / notified value (unit × qty), which is the same base
	used for GST. Quantity × rate is a different FBR check (error 0105).
	"""
	taxable = flt(getattr(item, "custom_fbr_taxable_value", None))
	if taxable:
		value = taxable
	else:
		qty = flt(getattr(item, "qty", None))
		value = flt(unit) * qty
	if absolute:
		return abs(value)
	return value


def get_fixed_notified_or_retail_price(item, *, absolute=False) -> float:
	"""FBR JSON field ``fixedNotifiedValueOrRetailPrice``.

	- Retail Price / MRP → line MRP (unit MRP × qty)
	- Fixed / Notified Value → line notified value (unit × qty)
	- Sales Value (explicit profile) → 0
	- No profile / blank basis → item.rate (backward compatible)
	"""
	basis = (getattr(item, "custom_fbr_tax_calculation_basis", None) or "").strip()
	if basis == TAX_BASIS_RETAIL_PRICE:
		return _line_value(getattr(item, "custom_fbr_retail_price", None), item, absolute=absolute)
	if basis == TAX_BASIS_FIXED_NOTIFIED:
		return _line_value(getattr(item, "custom_fbr_fixed_notified_value", None), item, absolute=absolute)
	if basis in {TAX_BASIS_SALES_VALUE, TAX_BASIS_MANUAL}:
		return 0.0

	value = flt(getattr(item, "rate", None))
	if absolute:
		return abs(value)
	return value
