import frappe

from fbr_integration.fbr_tax_calculation import (
	resolve_item_tax_template_name as _resolve_item_tax_template_name,
)


@frappe.whitelist()
def get_item_tax_template_rates(template_name: str):
	return (
		frappe.get_all(
			"Item Tax Template Detail",
			filters={"parent": template_name, "parenttype": "Item Tax Template"},
			fields=["tax_type", "tax_rate"],
			order_by="idx asc",
			ignore_permissions=True,
		)
		or []
	)


@frappe.whitelist()
def resolve_item_tax_template_name(scenario: str | None = None, company: str | None = None):
	return _resolve_item_tax_template_name(scenario, company=company)


@frappe.whitelist()
def get_item_fbr_tax_defaults(
	item_code=None,
	posting_date=None,
	uom=None,
	company=None,
	currency=None,
	qty=None,
	rate=None,
	amount=None,
):
	"""Server-side item fetch for Sales Invoice / POS. Authoritative over client calc."""
	from frappe.utils import flt

	from fbr_integration.taxation.engine import get_fbr_taxable_value
	from fbr_integration.taxation.profile import profile_to_dict, resolve_tax_profile
	from fbr_integration.taxation.retail_price import resolve_fixed_notified_value, resolve_retail_price

	item_code = (item_code or "").strip()
	if not item_code:
		return {}

	item_fields = ["custom_hs_code", "custom_fbr_uom"]
	try:
		if frappe.db.has_column("Item", "custom_fbr_tax_profile"):
			item_fields.extend(
				[
					"custom_fbr_tax_profile",
					"custom_fbr_default_retail_price",
					"custom_fbr_default_fixed_notified_value",
				]
			)
	except Exception:
		pass

	item_master = frappe.db.get_value("Item", item_code, item_fields, as_dict=True) or {}
	row = frappe._dict(
		{
			"item_code": item_code,
			"uom": uom,
			"qty": flt(qty) or 1,
			"rate": flt(rate),
			"amount": flt(amount) if amount not in (None, "") else None,
			"custom_fbr_tax_profile": item_master.get("custom_fbr_tax_profile"),
			"custom_fbr_default_retail_price": item_master.get("custom_fbr_default_retail_price"),
			"custom_fbr_default_fixed_notified_value": item_master.get(
				"custom_fbr_default_fixed_notified_value"
			),
		}
	)
	if not row.amount:
		row.amount = row.qty * row.rate

	doc = frappe._dict(
		{
			"doctype": "Sales Invoice",
			"posting_date": posting_date,
			"company": company,
			"currency": currency,
			"items": [row],
		}
	)
	profile = resolve_tax_profile(row, doc)
	data = profile_to_dict(profile)
	mrp = resolve_retail_price(
		item_code,
		posting_date=posting_date,
		uom=uom,
		currency=currency,
		item=row,
	)
	fixed = resolve_fixed_notified_value(item_code, item=row)
	row.custom_fbr_tax_calculation_basis = data.get("tax_calculation_basis") or ""
	row.custom_fbr_retail_price = mrp
	row.custom_fbr_fixed_notified_value = fixed
	taxable = get_fbr_taxable_value(row, doc, throw=False) if row.custom_fbr_tax_calculation_basis else row.amount

	return {
		"custom_hs_code": item_master.get("custom_hs_code") or "",
		"custom_fbr_uom": item_master.get("custom_fbr_uom") or "",
		"custom_fbr_tax_profile": data.get("name") or item_master.get("custom_fbr_tax_profile") or "",
		"custom_fbr_tax_calculation_basis": row.custom_fbr_tax_calculation_basis,
		"custom_fbr_retail_price": mrp,
		"custom_fbr_default_retail_price": item_master.get("custom_fbr_default_retail_price") or 0,
		"custom_fbr_fixed_notified_value": fixed,
		"custom_fbr_taxable_value": taxable,
		"custom_sale_type": data.get("sale_type") or "",
		"custom_sro_schedule_no": data.get("sro_schedule_no") or "",
		"custom_sro_item_sno": data.get("sro_item_serial_no") or "",
		"custom_sales_tax_rate": data.get("default_sales_tax_rate") or 0,
		"custom_further_tax_rate": data.get("default_further_tax_rate") or 0,
		"custom_extra_tax_rate": data.get("default_extra_tax_rate") or 0,
	}
