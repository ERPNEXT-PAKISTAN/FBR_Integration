"""Resolve FBR Retail Price / MRP from the FBR Retail Price price list."""

from __future__ import annotations

import frappe
from frappe.utils import cint, cstr, flt, getdate

from fbr_integration.taxation.constants import DEFAULT_RETAIL_PRICE_LIST


def get_retail_price_list(settings=None) -> str:
	from fbr_integration.taxation.profile import get_taxation_settings

	settings = settings or get_taxation_settings()
	return cstr(settings.get("fbr_retail_price_list")).strip() or DEFAULT_RETAIL_PRICE_LIST


def ensure_fbr_retail_price_list(currency: str | None = None) -> str:
	"""Create the FBR Retail Price selling price list if missing. Idempotent."""
	name = DEFAULT_RETAIL_PRICE_LIST
	if frappe.db.exists("Price List", name):
		return name

	price_currency = (currency or "").strip() or _default_currency()
	doc = frappe.get_doc(
		{
			"doctype": "Price List",
			"price_list_name": name,
			"selling": 1,
			"buying": 0,
			"enabled": 1,
			"currency": price_currency,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)
	return name


def _default_currency() -> str:
	try:
		company = frappe.defaults.get_global_default("company") if getattr(frappe, "defaults", None) else None
		if company:
			currency = frappe.db.get_value("Company", company, "default_currency")
			if currency:
				return currency
	except Exception:
		pass
	return "PKR"


def resolve_retail_price(
	item_code,
	posting_date=None,
	uom=None,
	price_list=None,
	currency=None,
	item=None,
	settings=None,
) -> float:
	"""Return the unit MRP for an item.

	Lookup order:
	1. Applicable Item Price on the FBR Retail Price list for posting date / UOM
	2. Item.custom_fbr_default_retail_price
	3. 0
	"""
	item_code = cstr(item_code).strip()
	if not item_code:
		return 0.0

	price_list = cstr(price_list).strip() or get_retail_price_list(settings)
	listed = _lookup_item_price(item_code, price_list, posting_date, uom, currency)
	if listed > 0:
		return listed

	fallback = 0.0
	if item is not None:
		fallback = flt(getattr(item, "custom_fbr_default_retail_price", None))
	if fallback <= 0:
		try:
			fallback = flt(frappe.db.get_value("Item", item_code, "custom_fbr_default_retail_price"))
		except Exception:
			fallback = 0.0
	return flt(fallback)


def resolve_fixed_notified_value(item_code, item=None) -> float:
	value = 0.0
	if item is not None:
		value = flt(getattr(item, "custom_fbr_default_fixed_notified_value", None))
		if value <= 0:
			value = flt(getattr(item, "custom_fbr_fixed_notified_value", None))
	if value <= 0 and item_code:
		try:
			value = flt(frappe.db.get_value("Item", item_code, "custom_fbr_default_fixed_notified_value"))
		except Exception:
			value = 0.0
	return flt(value)


def _lookup_item_price(item_code, price_list, posting_date, uom, currency) -> float:
	if not frappe.db.exists("DocType", "Item Price"):
		return 0.0
	if not frappe.db.exists("Price List", price_list):
		return 0.0

	transaction_date = None
	if posting_date:
		try:
			transaction_date = getdate(posting_date)
		except Exception:
			transaction_date = None

	filters = {"item_code": item_code, "price_list": price_list}
	try:
		rows = frappe.get_all(
			"Item Price",
			filters=filters,
			fields=["price_list_rate", "valid_from", "valid_upto", "uom", "currency", "creation"],
			order_by="valid_from desc, creation desc",
			ignore_permissions=True,
		)
	except Exception:
		return 0.0

	uom = cstr(uom).strip()
	currency = cstr(currency).strip()
	uom_exact = []
	uom_blank = []
	uom_other = []
	for row in rows:
		if not _date_applies(row, transaction_date):
			continue
		if currency and cstr(row.get("currency")).strip() and cstr(row.get("currency")).strip() != currency:
			continue
		rate = flt(row.get("price_list_rate"))
		if rate <= 0:
			continue
		row_uom = cstr(row.get("uom")).strip()
		if uom and row_uom == uom:
			uom_exact.append(rate)
		elif not row_uom:
			uom_blank.append(rate)
		else:
			uom_other.append(rate)

	if uom_exact:
		return flt(uom_exact[0])
	if uom_blank:
		return flt(uom_blank[0])
	if not uom and uom_other:
		return flt(uom_other[0])
	return 0.0


def _date_applies(row, transaction_date) -> bool:
	if not transaction_date:
		return True
	valid_from = row.get("valid_from")
	valid_upto = row.get("valid_upto")
	try:
		if valid_from and getdate(valid_from) > transaction_date:
			return False
		if valid_upto and getdate(valid_upto) < transaction_date:
			return False
	except Exception:
		return True
	return True
