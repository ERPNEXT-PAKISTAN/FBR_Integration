"""Seed Pakistan Tax Withholding Groups / Categories and Chart of Accounts.

Creates masters used by ERPNext Sales Invoice apply_tds and by FBR
salesTaxWithheldAtSource item mapping.
"""

from __future__ import annotations

from datetime import date

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields
from frappe.utils import getdate

from fbr_integration.item_tax_templates import (
	_create_tax_account,
	_find_account,
	_normalize_tax_account,
	_resolve_tax_parent,
)

# Fiscal-year style rate window (refreshed on sync when missing/expired).
RATE_FROM = date(2025, 7, 1)
RATE_TO = date(2027, 6, 30)

# Income-tax style withholding on sales (matches common PK chart seeds).
WH_SALES_RATES = (1, 1.5, 4, 5, 5.5, 7.5, 8, 9, 10, 11)

# Purchase-side withholding rates.
WH_PURCHASE_RATES = (1, 1.5, 2, 3.5, 4, 5, 5.5, 6, 7.5, 8, 9, 10, 11)

# Sales Tax Withheld at Source rates for FBR DI item field.
ST_WITHHELD_RATES = (1, 2, 3, 5, 10, 20)

GROUPS = (
	"FBR Sales Tax Withheld at Source",
	"WH TAX Sales",
	"Withholding Tax Purchases",
)


def _fmt_rate(rate: float) -> str:
	value = float(rate)
	if value.is_integer():
		return str(int(value))
	return f"{value:g}"


def _ensure_group(group_name: str):
	if not frappe.db.exists("DocType", "Tax Withholding Group"):
		return
	if frappe.db.exists("Tax Withholding Group", group_name):
		return
	doc = frappe.get_doc({"doctype": "Tax Withholding Group", "group_name": group_name})
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)


def _resolve_or_create_account(company: str, account_name: str) -> str:
	existing, account_type = _find_account(company, (account_name,))
	if existing:
		if account_type not in {"Tax", "Chargeable", "Payable"}:
			_normalize_tax_account(existing)
		return existing
	# Prefer liability parent; fall back to Duties and Taxes via helper.
	if not _resolve_tax_parent(company):
		return ""
	return _create_tax_account(company, account_name)


def _ensure_category(
	*,
	name: str,
	group_name: str,
	rate: float,
	companies: list[str],
	account_name: str,
):
	if not frappe.db.exists("DocType", "Tax Withholding Category"):
		return

	accounts = []
	for company in companies:
		account = _resolve_or_create_account(company, account_name)
		if account:
			accounts.append({"company": company, "account": account})

	if not accounts:
		return

	rate_row = {
		"from_date": RATE_FROM,
		"to_date": RATE_TO,
		"tax_withholding_rate": float(rate),
		"single_threshold": 0,
		"cumulative_threshold": 0,
	}
	if frappe.db.exists("DocType", "Tax Withholding Group"):
		rate_row["tax_withholding_group"] = group_name

	if frappe.db.exists("Tax Withholding Category", name):
		doc = frappe.get_doc("Tax Withholding Category", name)
		# Keep existing company account rows; add missing companies.
		existing_companies = {row.company for row in doc.accounts or []}
		changed = False
		for row in accounts:
			if row["company"] not in existing_companies:
				doc.append("accounts", row)
				changed = True
		# Only seed a rate when the category has none — never overlap date windows.
		if not (doc.rates or []):
			doc.append("rates", rate_row)
			changed = True
		if changed:
			doc.flags.ignore_permissions = True
			doc.save(ignore_permissions=True)
		return

	doc = frappe.get_doc(
		{
			"doctype": "Tax Withholding Category",
			"name": name,
			"category_name": name,
			"tax_deduction_basis": "Net Total",
			"round_off_tax_amount": 0,
			"tax_on_excess_amount": 0,
			"rates": [rate_row],
			"accounts": accounts,
		}
	)
	doc.flags.ignore_permissions = True
	doc.insert(ignore_permissions=True)


def sync_tax_withholding_masters():
	"""Idempotent: groups + CoA + categories for all companies."""
	if not frappe.db.exists("DocType", "Tax Withholding Category"):
		return

	for group_name in GROUPS:
		_ensure_group(group_name)

	companies = frappe.get_all("Company", pluck="name")
	if not companies:
		return

	# Parent liability bucket for ST withheld
	for company in companies:
		_resolve_or_create_account(company, "Sales Tax Withheld at Source")
		_resolve_or_create_account(company, "Withholding Tax")

	for rate in ST_WITHHELD_RATES:
		label = _fmt_rate(rate)
		_ensure_category(
			name=f"ST Withheld - {label}% (FBR)",
			group_name="FBR Sales Tax Withheld at Source",
			rate=rate,
			companies=companies,
			account_name=f"ST Withheld - {label}%",
		)

	for rate in WH_SALES_RATES:
		label = _fmt_rate(rate)
		name = f"WH TAX - {label}% (Sales)"
		_ensure_group(name)  # site historically used category name as group too
		_ensure_category(
			name=name,
			group_name=name,
			rate=rate,
			companies=companies,
			account_name=f"WH TAX - {label}%",
		)

	for rate in WH_PURCHASE_RATES:
		label = _fmt_rate(rate)
		name = f"Withholding Tax - {label}% (Purchases)"
		_ensure_group(name)
		_ensure_category(
			name=name,
			group_name=name,
			rate=rate,
			companies=companies,
			account_name=f"Withholding Tax - {label}%",
		)


def sync_withholding_custom_fields():
	"""Sales Invoice / Item fields for FBR salesTaxWithheldAtSource."""
	custom_fields = {
		"Sales Invoice Item": [
			{
				"fieldname": "custom_sales_tax_withheld_rate",
				"label": "ST Withheld Rate %",
				"fieldtype": "Percent",
				"insert_after": "custom_extra_tax_rate",
				"description": "Sales Tax Withheld at Source rate (FBR salesTaxWithheldAtSource).",
			},
			{
				"fieldname": "custom_sales_tax_withheld_at_source",
				"label": "ST Withheld at Source",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_extra_tax",
				"description": "Amount sent to FBR as salesTaxWithheldAtSource.",
			},
		],
		"Sales Invoice": [
			{
				"fieldname": "custom_sales_tax_withheld_at_source",
				"label": "ST Withheld at Source",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "total_taxes_and_charges",
				"read_only": 1,
				"description": "Sum of item Sales Tax Withheld at Source.",
			},
		],
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)
	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Sales Invoice Item")


def sync_withholding():
	sync_withholding_custom_fields()
	sync_tax_withholding_masters()
