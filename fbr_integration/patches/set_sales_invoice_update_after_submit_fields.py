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
	"total_qty",
	"base_total",
	"base_net_total",
	"total",
	"net_total",
	"base_total_taxes_and_charges",
	"total_taxes_and_charges",
	"base_grand_total",
	"base_rounding_adjustment",
	"base_rounded_total",
	"base_in_words",
	"grand_total",
	"rounding_adjustment",
	"rounded_total",
	"in_words",
	"outstanding_amount",
	"other_charges_calculation",
]

SALES_INVOICE_ITEM_FIELDS = [
	"item_tax_template",
	"qty",
	"rate",
	"amount",
	"base_rate",
	"base_amount",
	"net_rate",
	"net_amount",
	"base_net_rate",
	"base_net_amount",
	"stock_qty",
	"stock_uom_rate",
	"item_tax_rate",
	"discount_percentage",
	"discount_amount",
]

SALES_TAX_FIELDS = [
	"charge_type",
	"account_head",
	"account_currency",
	"description",
	"rate",
	"tax_amount",
	"base_tax_amount",
	"tax_amount_after_discount_amount",
	"base_tax_amount_after_discount_amount",
	"total",
	"base_total",
	"row_id",
	"included_in_print_rate",
	"included_in_paid_amount",
	"dont_recompute_tax",
	"item_wise_tax_detail",
	"cost_center",
	"project",
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
