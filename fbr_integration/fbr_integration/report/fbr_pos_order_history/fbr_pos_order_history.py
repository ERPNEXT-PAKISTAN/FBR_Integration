# Copyright (c) 2026, Taimoor and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.utils import flt

from fbr_integration.pos_reports import (
	fbr_no_sql,
	fbr_status_sql,
	invoice_doctypes,
	pos_filters_sql,
)


def execute(filters=None):
	filters = frappe._dict(filters or {})
	columns = get_columns()
	data = get_data(filters)
	summary = get_summary(data)
	return columns, data, None, None, summary


def get_columns():
	return [
		{"label": _("QR"), "fieldname": "fbr_qr", "fieldtype": "Data", "width": 80},
		{
			"label": _("Invoice"),
			"fieldname": "invoice",
			"fieldtype": "Dynamic Link",
			"options": "invoice_doctype",
			"width": 170,
		},
		{"label": _("Type"), "fieldname": "invoice_doctype", "fieldtype": "Data", "width": 120, "hidden": 1},
		{"label": _("Date"), "fieldname": "posting_date", "fieldtype": "Date", "width": 100},
		{"label": _("Time"), "fieldname": "posting_time", "fieldtype": "Data", "width": 90},
		{
			"label": _("Customer"),
			"fieldname": "customer",
			"fieldtype": "Link",
			"options": "Customer",
			"width": 160,
		},
		{"label": _("Customer Name"), "fieldname": "customer_name", "fieldtype": "Data", "width": 160},
		{
			"label": _("POS Profile"),
			"fieldname": "pos_profile",
			"fieldtype": "Link",
			"options": "POS Profile",
			"width": 130,
		},
		{"label": _("Grand Total"), "fieldname": "grand_total", "fieldtype": "Currency", "width": 120},
		{"label": _("FBR Invoice No"), "fieldname": "fbr_invoice_no", "fieldtype": "Data", "width": 180},
		{"label": _("FBR Status"), "fieldname": "fbr_status", "fieldtype": "Data", "width": 120},
	]


def get_data(filters):
	values = {}
	unions = []
	for doctype in invoice_doctypes():
		alias = "si"
		conds = pos_filters_sql(alias, filters, values, doctype)
		unions.append(
			f"""
			SELECT
				{alias}.name AS invoice,
				'{doctype}' AS invoice_doctype,
				{alias}.posting_date,
				{alias}.posting_time,
				{alias}.customer,
				{alias}.customer_name,
				{alias}.pos_profile,
				{alias}.grand_total,
				{fbr_no_sql(alias, doctype)} AS fbr_invoice_no,
				{fbr_status_sql(alias, doctype)} AS fbr_status
			FROM `tab{doctype}` {alias}
			WHERE {" AND ".join(conds)}
			"""
		)

	if not unions:
		return []

	rows = frappe.db.sql(
		" UNION ALL ".join(unions) + " ORDER BY posting_date DESC, posting_time DESC, invoice DESC LIMIT 500",
		values,
		as_dict=True,
	)
	for row in rows:
		row["fbr_qr"] = (row.get("fbr_invoice_no") or "").strip()
	return rows


def get_summary(data):
	sent = [r for r in data if (r.get("fbr_invoice_no") or "").strip()]
	pending = [r for r in data if not (r.get("fbr_invoice_no") or "").strip()]
	return [
		{"label": _("Invoices"), "value": len(data), "indicator": "blue"},
		{"label": _("Sent to FBR"), "value": len(sent), "indicator": "green"},
		{"label": _("Not sent"), "value": len(pending), "indicator": "orange"},
		{
			"label": _("POS Total"),
			"value": flt(sum(flt(r.get("grand_total")) for r in data)),
			"indicator": "blue",
			"datatype": "Currency",
		},
	]
