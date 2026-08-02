"""Keep allow_on_submit only for FBR response/custom fields; remove core SI overrides."""

import frappe

# Core fields previously forced allow_on_submit — remove those Property Setters.
CORE_DOCFIELD_SETTERS = [
	("Sales Invoice", "customer"),
	("Sales Invoice", "posting_date"),
	("Sales Invoice", "tc_name"),
	("Sales Invoice", "terms"),
	("Sales Invoice", "debit_to"),
	("Sales Invoice", "territory"),
	("Sales Invoice", "customer_address"),
	("Sales Invoice", "tax_category"),
	("Sales Invoice", "taxes_and_charges"),
	("Sales Invoice", "taxes"),
	("Sales Invoice", "total_qty"),
	("Sales Invoice", "base_total"),
	("Sales Invoice", "base_net_total"),
	("Sales Invoice", "total"),
	("Sales Invoice", "net_total"),
	("Sales Invoice", "base_total_taxes_and_charges"),
	("Sales Invoice", "total_taxes_and_charges"),
	("Sales Invoice", "base_grand_total"),
	("Sales Invoice", "base_rounding_adjustment"),
	("Sales Invoice", "base_rounded_total"),
	("Sales Invoice", "base_in_words"),
	("Sales Invoice", "grand_total"),
	("Sales Invoice", "rounding_adjustment"),
	("Sales Invoice", "rounded_total"),
	("Sales Invoice", "in_words"),
	("Sales Invoice", "outstanding_amount"),
	("Sales Invoice", "other_charges_calculation"),
	("Sales Invoice Item", "item_tax_template"),
	("Sales Invoice Item", "qty"),
	("Sales Invoice Item", "rate"),
	("Sales Invoice Item", "amount"),
	("Sales Invoice Item", "base_rate"),
	("Sales Invoice Item", "base_amount"),
	("Sales Invoice Item", "net_rate"),
	("Sales Invoice Item", "net_amount"),
	("Sales Invoice Item", "base_net_rate"),
	("Sales Invoice Item", "base_net_amount"),
	("Sales Invoice Item", "stock_qty"),
	("Sales Invoice Item", "stock_uom_rate"),
	("Sales Invoice Item", "item_tax_rate"),
	("Sales Invoice Item", "discount_percentage"),
	("Sales Invoice Item", "discount_amount"),
	("Sales Taxes and Charges", "charge_type"),
	("Sales Taxes and Charges", "account_head"),
	("Sales Taxes and Charges", "account_currency"),
	("Sales Taxes and Charges", "description"),
	("Sales Taxes and Charges", "rate"),
	("Sales Taxes and Charges", "tax_amount"),
	("Sales Taxes and Charges", "base_tax_amount"),
	("Sales Taxes and Charges", "tax_amount_after_discount_amount"),
	("Sales Taxes and Charges", "base_tax_amount_after_discount_amount"),
	("Sales Taxes and Charges", "total"),
	("Sales Taxes and Charges", "base_total"),
	("Sales Taxes and Charges", "row_id"),
	("Sales Taxes and Charges", "included_in_print_rate"),
	("Sales Taxes and Charges", "included_in_paid_amount"),
	("Sales Taxes and Charges", "dont_recompute_tax"),
	("Sales Taxes and Charges", "item_wise_tax_detail"),
	("Sales Taxes and Charges", "cost_center"),
	("Sales Taxes and Charges", "project"),
]

# FBR fields that still need post-submit updates after FBR response.
FBR_ALLOW_ON_SUBMIT = {
	"Sales Invoice": [
		"custom_fbr_digital_invoice_response",
		"custom_fbr_integration_type",
		"custom_fbr_invoice_status",
		"custom_fbr_invoice_status_code",
		"custom_fbr_invoice_error",
		"custom_fbr_invoice_error_code",
		"custom_fbr_submission_time",
		"custom_fbr_invoice_no",
		"custom_fbr_invoice_item_no",
		"custom_fbr_invoice_statuses",
		"custom_fbr_qr_code",
		"custom_qr_code",
		"custom_fbr_responsed",
		"custom_fbr_response",
	],
}


def execute():
	for doctype, fieldname in CORE_DOCFIELD_SETTERS:
		name = f"{doctype}-{fieldname}-allow_on_submit"
		if frappe.db.exists("Property Setter", name):
			frappe.delete_doc("Property Setter", name, ignore_permissions=True, force=1)

	for doctype, fields in FBR_ALLOW_ON_SUBMIT.items():
		for fieldname in fields:
			_ensure_custom_allow_on_submit(doctype, fieldname)

	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Sales Invoice Item")
	frappe.clear_cache(doctype="Sales Taxes and Charges")


def _ensure_custom_allow_on_submit(doctype, fieldname):
	if not frappe.db.exists("Custom Field", {"dt": doctype, "fieldname": fieldname}):
		return

	name = f"{doctype}-{fieldname}-allow_on_submit"
	values = {
		"doctype": "Property Setter",
		"name": name,
		"doctype_or_field": "DocField",
		"doc_type": doctype,
		"field_name": fieldname,
		"property": "allow_on_submit",
		"property_type": "Check",
		"value": "1",
		"is_system_generated": 1,
	}
	if frappe.db.exists("Property Setter", name):
		doc = frappe.get_doc("Property Setter", name)
		doc.update(values)
		doc.save(ignore_permissions=True)
	else:
		# Custom Field property is better set on the Custom Field itself
		cf_name = frappe.db.get_value("Custom Field", {"dt": doctype, "fieldname": fieldname}, "name")
		if cf_name:
			frappe.db.set_value("Custom Field", cf_name, "allow_on_submit", 1)
