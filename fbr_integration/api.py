import frappe

@frappe.whitelist()
def get_item_tax_template_rates(template_name: str):
    return frappe.get_all(
        "Item Tax Template Detail",
        filters={"parent": template_name, "parenttype": "Item Tax Template"},
        fields=["tax_type", "tax_rate"],
        order_by="idx asc",
        ignore_permissions=True,
    ) or []