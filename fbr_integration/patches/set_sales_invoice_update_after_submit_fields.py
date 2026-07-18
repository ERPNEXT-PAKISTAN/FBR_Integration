import frappe

SALES_INVOICE_FIELDS = [
	"customer",
	"posting_date",
	"tc_name",
	"terms",
	"debit_to",
	"territory",
	"customer_address",
	"tax_category",
	"taxes_and_charges",
	"taxes",
]

SALES_INVOICE_ITEM_FIELDS = [
	"item_tax_template",
	"qty",
	"rate",
]

SALES_TAX_FIELDS = [
	"charge_type",
	"account_head",
	"description",
	"rate",
	"tax_amount",
	"base_tax_amount",
	"tax_amount_after_discount_amount",
	"base_tax_amount_after_discount_amount",
	"total",
	"base_total",
	"included_in_print_rate",
	"cost_center",
]


def execute():
	for doctype, fields in (
		("Sales Invoice", SALES_INVOICE_FIELDS),
		("Sales Invoice Item", SALES_INVOICE_ITEM_FIELDS),
		("Sales Taxes and Charges", SALES_TAX_FIELDS),
	):
		for fieldname in fields:
			_set_allow_on_submit(doctype, fieldname)

	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Sales Invoice Item")
	frappe.clear_cache(doctype="Sales Taxes and Charges")


def _set_allow_on_submit(doctype, fieldname):
	if not frappe.db.exists("DocType", doctype):
		return
	if not frappe.db.exists("DocField", {"parent": doctype, "fieldname": fieldname}):
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
		frappe.get_doc(values).insert(ignore_permissions=True)
