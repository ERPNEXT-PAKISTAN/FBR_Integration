"""Snapshot FBR tax profile and MRP onto invoice rows at transaction time."""

from __future__ import annotations

import frappe
from frappe.utils import cint, cstr, flt

from fbr_integration.taxation.constants import (
	PROFILE_COPY_FIELDS,
	SALE_TYPE_STANDARD,
	SNAPSHOT_FIELDS,
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_SALES_VALUE,
)

DEFAULT_SRO_SCHEDULE = "EIGHTH SCHEDULE Table 1"
DEFAULT_SRO_ITEM = "81"
from fbr_integration.taxation.profile import get_taxation_settings, profile_to_dict, resolve_tax_profile
from fbr_integration.taxation.retail_price import resolve_fixed_notified_value, resolve_retail_price


def has_tax_snapshot(item) -> bool:
	basis = cstr(getattr(item, "custom_fbr_tax_calculation_basis", None)).strip()
	if basis:
		return True
	if flt(getattr(item, "custom_fbr_retail_price", None)) > 0:
		return True
	if flt(getattr(item, "custom_fbr_fixed_notified_value", None)) > 0:
		return True
	if flt(getattr(item, "custom_fbr_taxable_value", None)) > 0:
		return True
	return False


def should_preserve_snapshot(doc, item) -> bool:
	"""Returns/credit notes keep the original invoice snapshot, including old MRP."""
	if cint(getattr(doc, "is_return", 0)) and has_tax_snapshot(item):
		return True
	if cint(getattr(doc, "docstatus", 0)) == 1 and has_tax_snapshot(item):
		return True
	return False


def apply_tax_snapshots(doc, settings=None):
	"""Copy profile + MRP onto each item row. Never changes item.rate or item.amount."""
	settings = settings or get_taxation_settings()
	copy_return_snapshots(doc)
	for item in doc.get("items") or []:
		if should_preserve_snapshot(doc, item):
			continue
		apply_item_snapshot(doc, item, settings=settings)


def apply_item_snapshot(doc, item, settings=None, profile=None):
	settings = settings or get_taxation_settings()
	profile = profile or resolve_tax_profile(item, doc, settings=settings)
	data = profile_to_dict(profile)

	if data.get("name") and hasattr(item, "custom_fbr_tax_profile"):
		if not cstr(getattr(item, "custom_fbr_tax_profile", None)).strip():
			item.custom_fbr_tax_profile = data["name"]

	if data.get("tax_calculation_basis") and hasattr(item, "custom_fbr_tax_calculation_basis"):
		item.custom_fbr_tax_calculation_basis = data["tax_calculation_basis"]

	if data.get("sale_type") and hasattr(item, "custom_sale_type"):
		current_sale_type = cstr(getattr(item, "custom_sale_type", None)).strip()
		if not current_sale_type or current_sale_type == SALE_TYPE_STANDARD:
			item.custom_sale_type = data["sale_type"]

	if data.get("sro_schedule_no") and hasattr(item, "custom_sro_schedule_no"):
		if not cstr(getattr(item, "custom_sro_schedule_no", None)).strip():
			item.custom_sro_schedule_no = data["sro_schedule_no"]
	elif hasattr(item, "custom_sro_schedule_no") and not data.get("requires_sro_fields"):
		if cstr(getattr(item, "custom_sro_schedule_no", None)).strip() == DEFAULT_SRO_SCHEDULE:
			item.custom_sro_schedule_no = ""

	if data.get("sro_item_serial_no") and hasattr(item, "custom_sro_item_sno"):
		if not cstr(getattr(item, "custom_sro_item_sno", None)).strip():
			item.custom_sro_item_sno = data["sro_item_serial_no"]
	elif hasattr(item, "custom_sro_item_sno") and not data.get("requires_sro_fields"):
		if cstr(getattr(item, "custom_sro_item_sno", None)).strip() == DEFAULT_SRO_ITEM:
			item.custom_sro_item_sno = ""

	basis = cstr(getattr(item, "custom_fbr_tax_calculation_basis", None)).strip() or TAX_BASIS_SALES_VALUE
	auto_fetch = cint(settings.get("auto_fetch_fbr_retail_price", 1))
	submitted = cint(getattr(doc, "docstatus", 0)) == 1

	if hasattr(item, "custom_fbr_retail_price") and not submitted:
		existing_mrp = flt(getattr(item, "custom_fbr_retail_price", None))
		if auto_fetch or existing_mrp <= 0:
			mrp = resolve_retail_price(
				getattr(item, "item_code", None),
				posting_date=getattr(doc, "posting_date", None),
				uom=getattr(item, "uom", None),
				currency=getattr(doc, "currency", None),
				item=item,
				settings=settings,
			)
			if mrp > 0:
				item.custom_fbr_retail_price = mrp
			elif basis == TAX_BASIS_RETAIL_PRICE:
				item.custom_fbr_retail_price = existing_mrp

	if hasattr(item, "custom_fbr_fixed_notified_value") and not submitted:
		existing_fixed = flt(getattr(item, "custom_fbr_fixed_notified_value", None))
		if existing_fixed <= 0:
			fixed = resolve_fixed_notified_value(getattr(item, "item_code", None), item=item)
			if fixed > 0:
				item.custom_fbr_fixed_notified_value = fixed

	return data


def copy_return_snapshots(doc):
	"""Copy original invoice snapshots onto return rows when ERPNext did not already copy them."""
	if not cint(getattr(doc, "is_return", 0)):
		return
	source_name = cstr(getattr(doc, "return_against", None)).strip()
	if not source_name:
		return

	source_doctype = getattr(doc, "doctype", None)
	child_doctype = f"{source_doctype} Item" if source_doctype else ""
	if not source_doctype or not frappe.db.exists(source_doctype, source_name):
		for candidate in ("Sales Invoice", "POS Invoice"):
			if frappe.db.exists(candidate, source_name):
				source_doctype = candidate
				child_doctype = f"{candidate} Item"
				break
		else:
			return

	fields = [
		field
		for field in SNAPSHOT_FIELDS + PROFILE_COPY_FIELDS + ("custom_sales_tax_rate",)
		if _child_has_field(child_doctype, field)
	]
	if not fields:
		return

	source_items = frappe.get_all(
		child_doctype,
		filters={"parent": source_name, "parenttype": source_doctype},
		fields=["name", "item_code", "idx", *fields],
		order_by="idx asc",
		ignore_permissions=True,
	)
	by_name = {row.name: row for row in source_items}
	by_item = {}
	for row in source_items:
		by_item.setdefault(cstr(row.item_code), []).append(row)

	for item in doc.get("items") or []:
		source = _match_source_row(item, by_name, by_item)
		if not source:
			continue
		for field in fields:
			current = getattr(item, field, None)
			if field in SNAPSHOT_FIELDS:
				if field.endswith("_basis") or field.endswith("_profile"):
					if cstr(current).strip():
						continue
				elif flt(current):
					continue
			elif cstr(current).strip() and field in PROFILE_COPY_FIELDS:
				continue
			value = source.get(field)
			if value not in (None, ""):
				setattr(item, field, value)


def _match_source_row(item, by_name, by_item):
	for attr in ("sales_invoice_item", "pos_invoice_item", "dn_detail"):
		ref = cstr(getattr(item, attr, None)).strip()
		if ref and ref in by_name:
			return by_name[ref]
	item_code = cstr(getattr(item, "item_code", None)).strip()
	candidates = by_item.get(item_code) or []
	if len(candidates) == 1:
		return candidates[0]
	idx = cint(getattr(item, "idx", 0))
	for row in candidates:
		if cint(row.idx) == idx:
			return row
	return candidates[0] if candidates else None


def _child_has_field(doctype, fieldname) -> bool:
	try:
		return bool(frappe.get_meta(doctype).has_field(fieldname))
	except Exception:
		return True
