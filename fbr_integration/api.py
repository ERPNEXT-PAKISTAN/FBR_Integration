import frappe

from fbr_integration.fbr_tax_calculation import (
	resolve_item_tax_template_name as _resolve_item_tax_template_name,
)


@frappe.whitelist()
def get_item_tax_template_rates(template_name: str):
	return (
		frappe.get_all(
			"Item Tax Template Detail",
			filters={"parent": template_name, "parenttype": "Item Tax Template"},
			fields=["tax_type", "tax_rate"],
			order_by="idx asc",
			ignore_permissions=True,
		)
		or []
	)


@frappe.whitelist()
def resolve_item_tax_template_name(scenario: str | None = None):
	return _resolve_item_tax_template_name(scenario)
