# Copyright (c) 2026, Taimoor and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from fbr_integration.pos_reports import fbr_no_sql


def execute(filters=None):
	filters = frappe._dict(filters or {})
	if not frappe.db.exists("DocType", "POS Closing Entry"):
		return get_columns(), []
	return get_columns(), get_data(filters)


def get_columns():
	return [
		{
			"label": _("Closing Entry"),
			"fieldname": "name",
			"fieldtype": "Link",
			"options": "POS Closing Entry",
			"width": 170,
		},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{
			"label": _("POS Profile"),
			"fieldname": "pos_profile",
			"fieldtype": "Link",
			"options": "POS Profile",
			"width": 140,
		},
		{"label": _("User"), "fieldname": "user", "fieldtype": "Link", "options": "User", "width": 140},
		{"label": _("Invoices"), "fieldname": "invoices", "fieldtype": "Int", "width": 90},
		{"label": _("Sent to FBR"), "fieldname": "sent", "fieldtype": "Int", "width": 110},
		{"label": _("Not sent"), "fieldname": "pending", "fieldtype": "Int", "width": 100},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 130},
	]


def get_data(filters):
	conditions = ["ce.docstatus = 1"]
	values = {}
	if filters.get("company"):
		conditions.append("ce.company = %(company)s")
		values["company"] = filters.company
	if filters.get("pos_profile"):
		conditions.append("ce.pos_profile = %(pos_profile)s")
		values["pos_profile"] = filters.pos_profile
	if filters.get("from_date"):
		conditions.append("ce.posting_date >= %(from_date)s")
		values["from_date"] = filters.from_date
	if filters.get("to_date"):
		conditions.append("ce.posting_date <= %(to_date)s")
		values["to_date"] = filters.to_date

	closings = frappe.db.sql(
		f"""
		SELECT ce.name, ce.posting_date, ce.pos_profile, ce.user, ce.grand_total
		FROM `tabPOS Closing Entry` ce
		WHERE {" AND ".join(conditions)}
		ORDER BY ce.posting_date DESC, ce.name DESC
		LIMIT 200
		""",
		values,
		as_dict=True,
	)
	if not closings:
		return []

	names = [c.name for c in closings]
	si_stats = _invoice_stats("Sales Invoice Reference", "sales_invoice", "Sales Invoice", names)
	pos_stats = {}
	if frappe.db.exists("DocType", "POS Invoice Reference"):
		pos_stats = _invoice_stats("POS Invoice Reference", "pos_invoice", "POS Invoice", names)

	out = []
	for row in closings:
		si = si_stats.get(row.name, {"invoices": 0, "sent": 0})
		pos = pos_stats.get(row.name, {"invoices": 0, "sent": 0})
		invoices = si["invoices"] + pos["invoices"]
		sent = si["sent"] + pos["sent"]
		out.append(
			{
				"name": row.name,
				"posting_date": row.posting_date,
				"pos_profile": row.pos_profile,
				"user": row.user,
				"invoices": invoices,
				"sent": sent,
				"pending": max(invoices - sent, 0),
				"grand_total": flt(row.grand_total),
			}
		)
	return out


def _invoice_stats(child_dt, invoice_field, invoice_dt, closing_names):
	if not frappe.db.exists("DocType", child_dt) or not frappe.db.exists("DocType", invoice_dt):
		return {}
	if not frappe.db.has_column(child_dt, invoice_field):
		return {}

	fbr_expr = fbr_no_sql("inv", invoice_dt)
	rows = frappe.db.sql(
		f"""
		SELECT
			ref.parent AS closing,
			COUNT(*) AS invoices,
			SUM(CASE WHEN {fbr_expr} != '' THEN 1 ELSE 0 END) AS sent
		FROM `tab{child_dt}` ref
		INNER JOIN `tab{invoice_dt}` inv ON inv.name = ref.{invoice_field}
		WHERE ref.parenttype = 'POS Closing Entry' AND ref.parent IN %(names)s
		GROUP BY ref.parent
		""",
		{"names": closing_names},
		as_dict=True,
	)
	return {r.closing: {"invoices": int(r.invoices or 0), "sent": int(r.sent or 0)} for r in rows}
