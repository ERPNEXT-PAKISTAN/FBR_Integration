"""FBR Digital Invoice custom fields for POS Invoice (desk POS + XPOS)."""

from __future__ import annotations

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from fbr_integration.fbr_tax_calculation import DEFAULT_INVOICE_TYPE, DEFAULT_SCENARIO_DETAIL


def _pos_invoice_insert_after() -> str:
	for fieldname in ("custom_fbr_response", "custom_fbr_tab"):
		if frappe.db.exists("Custom Field", {"dt": "POS Invoice", "fieldname": fieldname}):
			return fieldname
	return "pos_profile"


def get_pos_invoice_fbr_custom_fields() -> dict:
	header_after = _pos_invoice_insert_after()
	allow = {"read_only": 1, "allow_on_submit": 1, "no_copy": 1}
	return {
		"POS Invoice": [
			{
				"fieldname": "custom_fbr_di_section",
				"label": "FBR Digital Invoice",
				"fieldtype": "Section Break",
				"insert_after": header_after,
				"collapsible": 1,
			},
			{
				"fieldname": "custom_invoice_type",
				"label": "Invoice Type",
				"fieldtype": "Link",
				"options": "Invoice Type",
				"insert_after": "custom_fbr_di_section",
				"default": DEFAULT_INVOICE_TYPE,
			},
			{
				"fieldname": "custom_scenario_detail",
				"label": "Scenario Detail",
				"fieldtype": "Link",
				"options": "Scenario ID",
				"insert_after": "custom_invoice_type",
				"default": DEFAULT_SCENARIO_DETAIL,
			},
			{
				"fieldname": "custom_scenario_id",
				"label": "Scenario ID",
				"fieldtype": "Data",
				"insert_after": "custom_scenario_detail",
			},
			{
				"fieldname": "custom_tax_payer_type",
				"label": "Tax Payer Type",
				"fieldtype": "Link",
				"options": "Tax Payer Type",
				"insert_after": "custom_scenario_id",
				"fetch_from": "customer.custom_tax_payer_type",
				"fetch_if_empty": 1,
			},
			{
				"fieldname": "custom_buyer_province",
				"label": "Buyer Province",
				"fieldtype": "Link",
				"options": "Buyer Province",
				"insert_after": "custom_tax_payer_type",
				"fetch_from": "customer.custom_buyer_province",
				"fetch_if_empty": 1,
			},
			{
				"fieldname": "custom_fbr_source_invoice_no",
				"label": "FBR Source Invoice No",
				"fieldtype": "Data",
				"insert_after": "custom_buyer_province",
			},
			{
				"fieldname": "custom_fbr_reason",
				"label": "FBR Return Reason",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_source_invoice_no",
			},
			{
				"fieldname": "custom_fbr_invoice_no",
				"label": "FBR Invoice No",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_reason",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_status",
				"label": "FBR Invoice Status",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_invoice_no",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_status_code",
				"label": "FBR Status Code",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_invoice_status",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_error",
				"label": "FBR Invoice Error",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_invoice_status_code",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_error_code",
				"label": "FBR Error Code",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_invoice_error",
				**allow,
			},
			{
				"fieldname": "custom_fbr_submission_time",
				"label": "FBR Submission Time",
				"fieldtype": "Datetime",
				"insert_after": "custom_fbr_invoice_error_code",
				**allow,
			},
			{
				"fieldname": "custom_fbr_integration_type",
				"label": "FBR Integration Type",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_submission_time",
				**allow,
			},
			{
				"fieldname": "custom_fbr_pos_id",
				"label": "FBR POS ID",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_integration_type",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_item_no",
				"label": "FBR Invoice Item No",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_pos_id",
				**allow,
			},
			{
				"fieldname": "custom_fbr_invoice_statuses",
				"label": "FBR Invoice Statuses",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_invoice_item_no",
				**allow,
			},
			{
				"fieldname": "custom_fbr_digital_invoice_response",
				"label": "FBR Digital Invoice Response",
				"fieldtype": "Long Text",
				"insert_after": "custom_fbr_invoice_statuses",
				**allow,
			},
			{
				"fieldname": "custom_fbr_qr_code",
				"label": "FBR QR Code",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_digital_invoice_response",
				**allow,
			},
			{
				"fieldname": "custom_qr_code",
				"label": "QR Code",
				"fieldtype": "Small Text",
				"insert_after": "custom_fbr_qr_code",
				**allow,
			},
			{
				"fieldname": "custom_fbr_responsed",
				"label": "FBR Responded",
				"fieldtype": "Data",
				"insert_after": "custom_qr_code",
				**allow,
			},
			{
				"fieldname": "custom_sales_tax_withheld_at_source",
				"label": "ST Withheld at Source",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_fbr_responsed",
				"read_only": 1,
			},
		],
		"POS Invoice Item": [
			{
				"fieldname": "custom_scenario_detail",
				"label": "Scenario Detail",
				"fieldtype": "Link",
				"options": "Scenario ID",
				"insert_after": "item_tax_template",
			},
			{
				"fieldname": "custom_hs_code",
				"label": "HS Code",
				"fieldtype": "Link",
				"options": "HS Code",
				"insert_after": "custom_scenario_detail",
				"fetch_from": "item_code.custom_hs_code",
				"fetch_if_empty": 1,
			},
			{
				"fieldname": "custom_fbr_uom",
				"label": "FBR UoM",
				"fieldtype": "Link",
				"options": "FBR UOM",
				"insert_after": "custom_hs_code",
				"fetch_from": "item_code.custom_fbr_uom",
				"fetch_if_empty": 1,
			},
			{
				"fieldname": "custom_sro_schedule_no",
				"label": "SRO Schedule No",
				"fieldtype": "Data",
				"insert_after": "custom_fbr_uom",
			},
			{
				"fieldname": "custom_sro_item_sno",
				"label": "SRO Item SNo",
				"fieldtype": "Data",
				"insert_after": "custom_sro_schedule_no",
			},
			{
				"fieldname": "custom_sales_tax_rate",
				"label": "Sales Tax Rate",
				"fieldtype": "Percent",
				"insert_after": "custom_sro_item_sno",
			},
			{
				"fieldname": "custom_further_tax_rate",
				"label": "Further Tax Rate",
				"fieldtype": "Percent",
				"insert_after": "custom_sales_tax_rate",
			},
			{
				"fieldname": "custom_extra_tax_rate",
				"label": "Extra Tax Rate",
				"fieldtype": "Percent",
				"insert_after": "custom_further_tax_rate",
			},
			{
				"fieldname": "custom_sales_tax_withheld_rate",
				"label": "ST Withheld Rate %",
				"fieldtype": "Percent",
				"insert_after": "custom_extra_tax_rate",
			},
			{
				"fieldname": "custom_sales_tax",
				"label": "Sales Tax Amount",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_sales_tax_withheld_rate",
			},
			{
				"fieldname": "custom_further_tax",
				"label": "Further Tax",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_sales_tax",
			},
			{
				"fieldname": "custom_extra_tax",
				"label": "Extra Tax",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_further_tax",
			},
			{
				"fieldname": "custom_sales_tax_withheld_at_source",
				"label": "ST Withheld at Source",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_extra_tax",
			},
			{
				"fieldname": "custom_total_tax_amount",
				"label": "Total Tax Amount",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_sales_tax_withheld_at_source",
			},
			{
				"fieldname": "custom_tax_inclusive_amount",
				"label": "Tax Inclusive Amount",
				"fieldtype": "Currency",
				"options": "currency",
				"insert_after": "custom_total_tax_amount",
			},
		],
	}


def sync_pos_invoice_fbr_fields():
	create_custom_fields(get_pos_invoice_fbr_custom_fields(), ignore_validate=True, update=True)
	frappe.clear_cache(doctype="POS Invoice")
	frappe.clear_cache(doctype="POS Invoice Item")
