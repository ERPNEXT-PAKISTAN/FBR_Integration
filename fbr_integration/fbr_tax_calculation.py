import frappe

SALES_TAX_KEYS = ("general sales tax", "sales tax", "gst", "output tax", "vat")
FURTHER_TAX_KEYS = ("further tax",)
EXTRA_TAX_KEYS = ("extra tax",)

def _matches(tax_type, keys):
    t = (tax_type or "").lower()
    return any(k in t for k in keys)

def _get_item_tax_template_rows(template_name: str):
    # Read child table rows directly (most reliable)
    return frappe.get_all(
        "Item Tax Template Detail",
        filters={"parent": template_name, "parenttype": "Item Tax Template"},
        fields=["tax_type", "tax_rate"],
        order_by="idx asc",
        ignore_permissions=True,
    ) or []

def calculate_fbr_tax(doc, method=None):
    for item in doc.items:
        qty = float(item.qty or 0)
        rate = float(item.rate or 0)

        if not item.amount:
            item.amount = qty * rate

        amount = float(item.amount or 0)

        # Reset
        item.custom_sales_tax_rate = 0
        item.custom_further_tax_rate = 0
        item.custom_extra_tax_rate = 0

        item.custom_sales_tax = 0
        item.custom_further_tax = 0
        item.custom_extra_tax = 0

        item.custom_total_tax_amount = 0
        item.custom_tax_inclusive_amount = amount

        if not item.item_tax_template:
            continue

        tax_rows = _get_item_tax_template_rows(item.item_tax_template)

        if not tax_rows:
            # Helpful debug (you can remove later)
            frappe.log_error(
                title="FBR Tax Calc: No tax rows found",
                message=f"Template: {item.item_tax_template} | Item: {item.item_code} | SI: {doc.name}"
            )
            continue

        # Determine rates
        for tr in tax_rows:
            tax_type = (tr.get("tax_type") or "")
            tax_rate = float(tr.get("tax_rate") or 0)

            if _matches(tax_type, SALES_TAX_KEYS):
                item.custom_sales_tax_rate = tax_rate
            elif _matches(tax_type, FURTHER_TAX_KEYS):
                item.custom_further_tax_rate = tax_rate
            elif _matches(tax_type, EXTRA_TAX_KEYS):
                item.custom_extra_tax_rate = tax_rate

        # fallback: only one row
        if len(tax_rows) == 1 and float(item.custom_sales_tax_rate or 0) == 0:
            item.custom_sales_tax_rate = float(tax_rows[0].get("tax_rate") or 0)

        # Calculate amounts
        item.custom_sales_tax = (amount * float(item.custom_sales_tax_rate or 0)) / 100
        item.custom_further_tax = (amount * float(item.custom_further_tax_rate or 0)) / 100
        item.custom_extra_tax = (amount * float(item.custom_extra_tax_rate or 0)) / 100

        item.custom_total_tax_amount = (
            float(item.custom_sales_tax or 0)
            + float(item.custom_further_tax or 0)
            + float(item.custom_extra_tax or 0)
        )

        item.custom_tax_inclusive_amount = amount + float(item.custom_total_tax_amount or 0)