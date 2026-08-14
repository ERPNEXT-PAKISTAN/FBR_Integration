# Copyright (c) 2026, Taimoor and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from fbr_integration.pos_reports import fbr_no_sql, invoice_doctypes, pos_filters_sql


def execute(filters=None):
	filters = frappe._dict(filters or {})
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{"label": _("Item"), "fieldname": "item_code", "fieldtype": "Link", "options": "Item", "width": 140},
		{"label": _("Item Name"), "fieldname": "item_name", "fieldtype": "Data", "width": 180},
		{"label": _("Qty"), "fieldname": "qty", "fieldtype": "Float", "width": 90},
		{"label": _("Amount"), "fieldname": "amount", "fieldtype": "Currency", "width": 120},
		{"label": _("Sent Qty"), "fieldname": "sent_qty", "fieldtype": "Float", "width": 90},
		{"label": _("Sent Amount"), "fieldname": "sent_amount", "fieldtype": "Currency", "width": 120},
	]


def get_data(filters):
	values = {}
	unions = []
	for doctype in invoice_doctypes():
		alias = "si"
		item = "sii"
		conds = pos_filters_sql(alias, filters, values, doctype)
		fbr_expr = fbr_no_sql(alias, doctype)
		unions.append(
			f"""
			SELECT
				{item}.item_code,
				{item}.item_name,
				SUM({item}.qty) AS qty,
				SUM({item}.amount) AS amount,
				SUM(CASE WHEN {fbr_expr} != '' THEN {item}.qty ELSE 0 END) AS sent_qty,
				SUM(CASE WHEN {fbr_expr} != '' THEN {item}.amount ELSE 0 END) AS sent_amount
			FROM `tab{doctype}` {alias}
			INNER JOIN `tab{doctype} Item` {item} ON {item}.parent = {alias}.name
			WHERE {" AND ".join(conds)}
			GROUP BY {item}.item_code, {item}.item_name
			"""
		)

	if not unions:
		return []

	rows = frappe.db.sql(" UNION ALL ".join(unions), values, as_dict=True)
	merged = {}
	for row in rows:
		key = row.item_code
		bucket = merged.setdefault(
			key,
			{
				"item_code": row.item_code,
				"item_name": row.item_name,
				"qty": 0,
				"amount": 0,
				"sent_qty": 0,
				"sent_amount": 0,
			},
		)
		bucket["qty"] += float(row.qty or 0)
		bucket["amount"] += float(row.amount or 0)
		bucket["sent_qty"] += float(row.sent_qty or 0)
		bucket["sent_amount"] += float(row.sent_amount or 0)
	return sorted(merged.values(), key=lambda r: r["amount"], reverse=True)
