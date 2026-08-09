import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields


def execute():
	create_custom_fields(
		{
			"Sales Invoice": [
				{
					"fieldname": "custom_fbr_pos_id",
					"label": "FBR POS ID",
					"fieldtype": "Data",
					"insert_after": "custom_fbr_integration_type",
					"read_only": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
					"description": "FBR POS Registration ID used when this invoice was sent (from POS Credentials).",
				}
			]
		},
		ignore_validate=True,
		update=True,
	)
	frappe.clear_cache(doctype="Sales Invoice")
