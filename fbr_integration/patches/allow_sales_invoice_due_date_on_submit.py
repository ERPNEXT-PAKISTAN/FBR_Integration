"""Allow Payment Due Date / payment schedule edits on submitted Sales Invoices."""

import frappe

SALES_INVOICE_FIELDS = (
	"due_date",
	"payment_schedule",
	"payment_terms_template",
	"ignore_default_payment_terms_template",
	"status",
)

PAYMENT_SCHEDULE_FIELDS = (
	"payment_term",
	"description",
	"due_date",
	"invoice_portion",
	"mode_of_payment",
	"due_date_based_on",
	"credit_days",
	"credit_months",
	"discount_date",
	"discount",
	"discount_type",
	"discount_validity_based_on",
	"discount_validity",
	"payment_amount",
	"outstanding",
	"paid_amount",
	"discounted_amount",
	"base_payment_amount",
	"base_outstanding",
	"base_paid_amount",
)


def execute():
	for fieldname in SALES_INVOICE_FIELDS:
		_ensure_allow_on_submit("Sales Invoice", fieldname)
	for fieldname in PAYMENT_SCHEDULE_FIELDS:
		_ensure_allow_on_submit("Payment Schedule", fieldname)

	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Payment Schedule")


def _ensure_allow_on_submit(doctype, fieldname):
	meta = frappe.get_meta(doctype)
	if not meta.get_field(fieldname):
		return

	name = f"{doctype}-{fieldname}-allow_on_submit"
	values = {
		"doctype_or_field": "DocField",
		"doc_type": doctype,
		"field_name": fieldname,
		"property": "allow_on_submit",
		"property_type": "Check",
		"value": "1",
		"is_system_generated": 1,
	}
	if frappe.db.exists("Property Setter", name):
		frappe.db.set_value("Property Setter", name, values, update_modified=False)
		return

	doc = frappe.get_doc({"doctype": "Property Setter", "name": name, **values})
	doc.flags.ignore_permissions = True
	doc.insert()
