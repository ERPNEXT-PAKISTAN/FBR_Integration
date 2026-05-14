import frappe

DESIRED_TAX_PAYER_TYPES = {
	"Registered",
	"Unregistered",
	"Unregistered Distributor",
	"Retail Consumer",
}


def _ensure_tax_payer_type_records():
	for value in sorted(DESIRED_TAX_PAYER_TYPES):
		if frappe.db.exists("Tax Payer Type", value):
			continue
		frappe.get_doc({"doctype": "Tax Payer Type", "tax_payer_type": value, "name": value}).insert(
			ignore_permissions=True
		)


def _tax_payer_type_is_referenced(name: str) -> bool:
	if frappe.db.has_column("Sales Invoice", "custom_tax_payer_type"):
		if frappe.db.count("Sales Invoice", {"custom_tax_payer_type": name}):
			return True
	if frappe.db.has_column("Customer", "custom_tax_payer_type"):
		if frappe.db.count("Customer", {"custom_tax_payer_type": name}):
			return True
	return False


def _cleanup_extra_tax_payer_types():
	for row in frappe.get_all("Tax Payer Type", fields=["name"], limit_page_length=0):
		name = row.name
		if name in DESIRED_TAX_PAYER_TYPES:
			continue
		if _tax_payer_type_is_referenced(name):
			continue
		frappe.delete_doc("Tax Payer Type", name, ignore_permissions=True, force=1)


def _fix_hs_code_mapping():
	has_hs_code_no = frappe.db.exists("Custom Field", "Item-custom_hs_code_no")
	has_hs_code = frappe.db.exists("Custom Field", "Item-custom_hs_code")

	if has_hs_code and has_hs_code_no:
		# Keep existing customer field (custom_hs_code_no) as primary and hide duplicate field.
		frappe.db.set_value("Custom Field", "Item-custom_hs_code", "hidden", 1)

	hs_fetch_from = "item_code.custom_hs_code_no" if has_hs_code_no else "item_code.custom_hs_code"

	if frappe.db.exists("Custom Field", "Sales Invoice Item-custom_hs_code"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice Item-custom_hs_code",
			{"fetch_from": hs_fetch_from, "fetch_if_empty": 1},
		)

	if frappe.db.exists("Custom Field", "Sales Invoice Item-custom_fbr_uom"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice Item-custom_fbr_uom",
			{"fetch_from": "item_code.custom_fbr_uom", "fetch_if_empty": 1},
		)

	if frappe.db.exists("Custom Field", "Sales Invoice-custom_tax_payer_type"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_tax_payer_type",
			{"fetch_from": "customer.custom_tax_payer_type", "fetch_if_empty": 1},
		)

	if frappe.db.exists("Custom Field", "Sales Invoice-custom_buyer_province"):
		frappe.db.set_value(
			"Custom Field",
			"Sales Invoice-custom_buyer_province",
			{"fetch_from": "customer.custom_buyer_province", "fetch_if_empty": 1},
		)


def execute():
	_ensure_tax_payer_type_records()
	_cleanup_extra_tax_payer_types()
	_fix_hs_code_mapping()

	for dt in ("Tax Payer Type", "Sales Invoice", "Sales Invoice Item", "Item", "Customer"):
		frappe.clear_cache(doctype=dt)
