import frappe

from fbr_integration.patches.sync_sale_types_and_item_fbr_links import READ_ROLES
from fbr_integration.pos_invoice_fields import sync_pos_invoice_fbr_fields

# Reuse the helper against Buyer Province / Tax Payer Type as well.
LINK_DOCTYPES = ("Buyer Province", "Tax Payer Type")


def _ensure_customer_link_fields():
	field_updates = {
		"Customer-custom_buyer_province": {
			"fieldtype": "Link",
			"options": "Buyer Province",
			"hidden": 0,
			"ignore_user_permissions": 1,
		},
		"Customer-custom_tax_payer_type": {
			"fieldtype": "Link",
			"options": "Tax Payer Type",
			"hidden": 0,
			"ignore_user_permissions": 1,
		},
		"Sales Invoice-custom_buyer_province": {
			"fieldtype": "Link",
			"options": "Buyer Province",
			"fetch_from": "customer.custom_buyer_province",
			"fetch_if_empty": 1,
			"ignore_user_permissions": 1,
		},
		"Sales Invoice-custom_tax_payer_type": {
			"fieldtype": "Link",
			"options": "Tax Payer Type",
			"fetch_from": "customer.custom_tax_payer_type",
			"fetch_if_empty": 1,
			"ignore_user_permissions": 1,
		},
		"POS Invoice-custom_buyer_province": {
			"fieldtype": "Link",
			"options": "Buyer Province",
			"fetch_from": "customer.custom_buyer_province",
			"fetch_if_empty": 1,
			"ignore_user_permissions": 1,
		},
		"POS Invoice-custom_tax_payer_type": {
			"fieldtype": "Link",
			"options": "Tax Payer Type",
			"fetch_from": "customer.custom_tax_payer_type",
			"fetch_if_empty": 1,
			"ignore_user_permissions": 1,
		},
	}
	for name, values in field_updates.items():
		if not frappe.db.exists("Custom Field", name):
			continue
		frappe.db.set_value("Custom Field", name, values, update_modified=False)


def _ensure_province_permissions():
	for doctype in LINK_DOCTYPES:
		if not frappe.db.exists("DocType", doctype):
			continue
		doc = frappe.get_doc("DocType", doctype)
		existing = {row.role for row in doc.permissions}
		changed = False
		for role in READ_ROLES:
			if role in existing:
				continue
			doc.append(
				"permissions",
				{
					"role": role,
					"read": 1,
					"report": 1,
					"export": 1,
					"print": 1,
					"email": 1,
				},
			)
			changed = True
		if changed:
			doc.save(ignore_permissions=True)


def execute():
	_ensure_customer_link_fields()
	_ensure_province_permissions()
	sync_pos_invoice_fbr_fields()

	for dt in (
		"Buyer Province",
		"Tax Payer Type",
		"Customer",
		"Sales Invoice",
		"POS Invoice",
	):
		frappe.clear_cache(doctype=dt)
