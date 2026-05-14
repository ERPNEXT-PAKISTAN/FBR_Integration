import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	custom_fields = {
		"Customer": [
			{
				"fieldname": "custom_tax_payer_type",
				"label": "Tax Payer Type",
				"fieldtype": "Link",
				"options": "Tax Payer Type",
				"insert_after": "tax_id",
			},
			{
				"fieldname": "custom_buyer_province",
				"label": "Buyer Province",
				"fieldtype": "Link",
				"options": "Buyer Province",
				"insert_after": "custom_tax_payer_type",
			},
		],
		"Item": [
			{
				"fieldname": "custom_hs_code",
				"label": "HS Code",
				"fieldtype": "Link",
				"options": "HS Code",
				"insert_after": "item_group",
			},
			{
				"fieldname": "custom_fbr_uom",
				"label": "FBR UoM",
				"fieldtype": "Link",
				"options": "FBR UOM",
				"insert_after": "custom_hs_code",
			},
		],
	}
	create_custom_fields(custom_fields, ignore_validate=True, update=True)

	fetch_map = {
		"Sales Invoice-custom_tax_payer_type": "customer.custom_tax_payer_type",
		"Sales Invoice-custom_buyer_province": "customer.custom_buyer_province",
		"Sales Invoice Item-custom_hs_code": "item_code.custom_hs_code",
		"Sales Invoice Item-custom_fbr_uom": "item_code.custom_fbr_uom",
	}

	for custom_field_name, fetch_from in fetch_map.items():
		if not frappe.db.exists("Custom Field", custom_field_name):
			continue
		frappe.db.set_value(
			"Custom Field",
			custom_field_name,
			{
				"fetch_from": fetch_from,
				"fetch_if_empty": 1,
			},
		)

	frappe.clear_cache(doctype="Sales Invoice")
	frappe.clear_cache(doctype="Sales Invoice Item")
	frappe.clear_cache(doctype="Customer")
	frappe.clear_cache(doctype="Item")
