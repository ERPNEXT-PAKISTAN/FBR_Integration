"""Shared POS invoice queries for FBR desk reports (Sales Invoice + POS Invoice)."""

from __future__ import annotations

import frappe
from frappe.utils import getdate


def invoice_doctypes() -> list[str]:
	doctypes = ["Sales Invoice"]
	if frappe.db.exists("DocType", "POS Invoice"):
		doctypes.append("POS Invoice")
	return doctypes


def fbr_no_sql(alias: str, doctype: str) -> str:
	parts = []
	if frappe.db.has_column(doctype, "custom_fbr_invoice_no"):
		parts.append(f"NULLIF({alias}.custom_fbr_invoice_no, '')")
	if frappe.db.has_column(doctype, "fbr_invoice_number"):
		parts.append(f"NULLIF({alias}.fbr_invoice_number, '')")
	if not parts:
		return "''"
	if len(parts) == 1:
		return f"IFNULL({parts[0]}, '')"
	return f"IFNULL(COALESCE({', '.join(parts)}), '')"


def fbr_status_sql(alias: str, doctype: str) -> str:
	if frappe.db.has_column(doctype, "custom_fbr_invoice_status"):
		return f"IFNULL({alias}.custom_fbr_invoice_status, '')"
	return "''"


def pos_filters_sql(alias: str, filters, values: dict, doctype: str) -> list[str]:
	conditions = [f"{alias}.docstatus = 1", f"{alias}.is_pos = 1"]
	if filters.get("company"):
		conditions.append(f"{alias}.company = %(company)s")
		values["company"] = filters.company
	if filters.get("pos_profile"):
		conditions.append(f"{alias}.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	if filters.get("customer"):
		conditions.append(f"{alias}.customer = %(customer)s")
		values["customer"] = filters.customer
	if filters.get("from_date"):
		conditions.append(f"{alias}.posting_date >= %(from_date)s")
		values["from_date"] = getdate(filters.from_date)
	if filters.get("to_date"):
		conditions.append(f"{alias}.posting_date <= %(to_date)s")
		values["to_date"] = getdate(filters.to_date)

	status = (filters.get("fbr_status") or "All").strip()
	fbr_expr = fbr_no_sql(alias, doctype)
	if status == "Sent":
		conditions.append(f"{fbr_expr} != ''")
	elif status == "Not Sent":
		conditions.append(f"{fbr_expr} = ''")
	return conditions
