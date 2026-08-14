# Copyright (c) 2026, Taimoor and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from fbr_integration.pos_reports import fbr_no_sql, invoice_doctypes, pos_filters_sql


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 110},
		{
			"label": _("POS Profile"),
			"fieldname": "pos_profile",
			"fieldtype": "Link",
			"options": "POS Profile",
			"width": 150,
		},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 90},
		{"label": _("Sent to FBR"), "fieldname": "sent", "fieldtype": "Int", "width": 110},
		{"label": _("Not sent"), "fieldname": "pending", "fieldtype": "Int", "width": 100},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
		{"label": _("Sent Amount"), "fieldname": "sent_amount", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	values = {}
	unions = []
	for doctype in invoice_doctypes():
		alias = "si"
		conds = pos_filters_sql(alias, filters, values, doctype)
		fbr_expr = fbr_no_sql(alias, doctype)
		unions.append(
			f"""
			SELECT
				{alias}.posting_date,
				{alias}.pos_profile,
				COUNT(*) AS invoices,
				SUM(CASE WHEN {fbr_expr} != '' THEN 1 ELSE 0 END) AS sent,
				SUM(CASE WHEN {fbr_expr} = '' THEN 1 ELSE 0 END) AS pending,
				SUM({alias}.grand_total) AS grand_total,
				SUM(CASE WHEN {fbr_expr} != '' THEN {alias}.grand_total ELSE 0 END) AS sent_amount
			FROM `tab{doctype}` {alias}
			WHERE {" AND ".join(conds)}
			GROUP BY {alias}.posting_date, {alias}.pos_profile
			"""
		)

	if not unions:
		return []

	rows = frappe.db.sql(
		" UNION ALL ".join(unions),
		values,
		as_dict=True,
	)

	merged = {}
	for row in rows:
		key = (row.posting_date, row.pos_profile)
		bucket = merged.setdefault(
			key,
			{
				"posting_date": row.posting_date,
				"pos_profile": row.pos_profile,
				"invoices": 0,
				"sent": 0,
				"pending": 0,
				"grand_total": 0,
				"sent_amount": 0,
			},
		)
		bucket["invoices"] += int(row.invoices or 0)
		bucket["sent"] += int(row.sent or 0)
		bucket["pending"] += int(row.pending or 0)
		bucket["grand_total"] = flt(bucket["grand_total"]) + flt(row.grand_total)
		bucket["sent_amount"] = flt(bucket["sent_amount"]) + flt(row.sent_amount)

	return sorted(merged.values(), key=lambda r: (r["posting_date"] or "", r["pos_profile"] or ""), reverse=True)
