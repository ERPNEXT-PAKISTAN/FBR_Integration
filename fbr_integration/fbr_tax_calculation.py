import frappe

SCENARIO_TEMPLATE_ALIASES = {
	"all taxes": ["all taxes", "taxable", "gst further extra", "gst+further+extra"],
	"pakistan tax": ["pakistan tax", "taxable", "gst further extra", "gst+further+extra"],
	"zero rated": ["zero rated", "zero-rated", "zero rated goods"],
	"exempt": ["exempt"],
	"cement per qty": ["cement per qty", "cement /qty", "cement qty"],
}

SALES_TAX_KEYS = ("general sales tax", "sales tax", "gst", "output tax", "vat")
FURTHER_TAX_KEYS = ("further tax",)
EXTRA_TAX_KEYS = ("extra tax",)

SCENARIO_ID_TEMPLATE_ALIASES = {
	"sn005": ["reduced rate", "goods at reduced rate", "reduced rate sale"],
	"sn006": ["exempt", "exempt goods"],
	"sn007": ["zero rated", "zero-rated", "goods at zero rate", "zero rated goods"],
	"sn009": ["reduced rate", "goods at reduced rate", "reduced rate sale"],
}


def _normalize_text(value):
	return " ".join((value or "").lower().replace("/", " ").replace("-", " ").replace("_", " ").split())


def _scenario_aliases(scenario: str):
	normalized = _normalize_text(scenario)
	if normalized in SCENARIO_TEMPLATE_ALIASES:
		return SCENARIO_TEMPLATE_ALIASES[normalized]

	match = frappe.safe_decode(scenario or "")
	match = (match or "").strip().upper()
	scenario_id = ""
	if match.startswith("SN") and len(match) >= 5:
		scenario_id = match.split(" ", 1)[0]

	if scenario_id and scenario_id.lower() in SCENARIO_ID_TEMPLATE_ALIASES:
		return SCENARIO_ID_TEMPLATE_ALIASES[scenario_id.lower()]

	for key, aliases in SCENARIO_TEMPLATE_ALIASES.items():
		if key and key in normalized:
			return aliases

	for key, aliases in SCENARIO_ID_TEMPLATE_ALIASES.items():
		if key in normalized:
			return aliases

	return []


def sync_sales_invoice_master_defaults(doc, method=None):
	"""Fill FBR fields from Customer/Item masters when invoice/item values are empty."""
	if doc.doctype != "Sales Invoice":
		return

	if doc.customer:
		customer_defaults = (
			frappe.db.get_value(
				"Customer",
				doc.customer,
				["custom_tax_payer_type", "custom_buyer_province"],
				as_dict=True,
			)
			or {}
		)

		if not getattr(doc, "custom_tax_payer_type", None):
			doc.custom_tax_payer_type = customer_defaults.get("custom_tax_payer_type")

		if not getattr(doc, "custom_buyer_province", None):
			doc.custom_buyer_province = customer_defaults.get("custom_buyer_province")

	for item in doc.get("items") or []:
		if not item.item_code:
			continue

		item_defaults = (
			frappe.db.get_value(
				"Item",
				item.item_code,
				["custom_hs_code", "custom_fbr_uom"],
				as_dict=True,
			)
			or {}
		)

		if not getattr(item, "custom_hs_code", None):
			item.custom_hs_code = item_defaults.get("custom_hs_code")

		if not getattr(item, "custom_fbr_uom", None):
			item.custom_fbr_uom = item_defaults.get("custom_fbr_uom")


def sync_return_source_invoice_no(doc, method=None):
	"""Copy source FBR invoice number to return invoices.

	When a Sales Return is created against a submitted Sales Invoice, ERPNext sets
	`return_against` to the source invoice name. FBR needs the original FBR invoice
	number, so keep `custom_fbr_source_invoice_no` aligned with the source invoice's
	`custom_fbr_invoice_no`.
	"""
	if doc.doctype != "Sales Invoice":
		return

	if not getattr(doc, "is_return", 0):
		return

	if not hasattr(doc, "custom_fbr_source_invoice_no"):
		return

	return_against = (getattr(doc, "return_against", None) or "").strip()
	if not return_against:
		return

	source_fbr_no = (
		frappe.db.get_value("Sales Invoice", return_against, "custom_fbr_invoice_no") or ""
	).strip()
	doc.custom_fbr_source_invoice_no = source_fbr_no


def disable_update_stock_for_delivery_note_invoice(doc, method=None):
	if doc.doctype != "Sales Invoice" or not getattr(doc, "update_stock", 0):
		return

	for item in doc.get("items") or []:
		if getattr(item, "delivery_note", None) or getattr(item, "dn_detail", None):
			doc.update_stock = 0
			return


def restore_submitted_sales_tax_rows(doc, method=None):
	"""Keep submitted Sales Invoice tax rows from being dropped during updates.

	ERPNext v15 compares submitted child table rows by index during
	`on_update_after_submit`. If the browser sends fewer `taxes` rows than the saved
	invoice has, ERPNext raises IndexError before it can repost accounting entries.
	Restore missing existing rows, then let ERPNext recalculate amounts normally.
	"""
	if doc.doctype != "Sales Invoice" or doc.docstatus != 1 or not doc.name:
		return

	existing_taxes = frappe.get_all(
		"Sales Taxes and Charges",
		filters={"parent": doc.name, "parenttype": "Sales Invoice", "parentfield": "taxes"},
		fields=["*"],
		order_by="idx asc",
		ignore_permissions=True,
	)
	if not existing_taxes:
		return

	current_tax_names = {tax.name for tax in doc.get("taxes") or [] if tax.name}
	missing_taxes = [tax for tax in existing_taxes if tax.name not in current_tax_names]
	if not missing_taxes:
		return

	for tax in missing_taxes:
		row = doc.append("taxes", {})
		for fieldname, value in tax.items():
			if fieldname in {"doctype", "parent", "parenttype", "parentfield", "creation", "modified"}:
				continue
			row.set(fieldname, value)

	if not doc.taxes_and_charges:
		doc.taxes_and_charges = frappe.db.get_value("Sales Invoice", doc.name, "taxes_and_charges")

	doc.calculate_taxes_and_totals()


def get_effective_invoice_tax_scenario(doc):
	detail = (getattr(doc, "custom_scenario_detail", None) or "").strip()
	if detail:
		return detail

	scenario_id = (getattr(doc, "custom_scenario_id", None) or "").strip()
	return scenario_id


def resolve_item_tax_template_name(scenario: str | None = None):
	aliases = _scenario_aliases(scenario)
	if not aliases:
		return ""
	templates = (
		frappe.get_all(
			"Item Tax Template",
			fields=["name"],
			order_by="name asc",
			ignore_permissions=True,
		)
		or []
	)
	normalized_templates = [(template["name"], _normalize_text(template["name"])) for template in templates]

	for alias in aliases:
		alias_norm = _normalize_text(alias)
		exact_matches = [name for name, normalized in normalized_templates if normalized == alias_norm]
		if exact_matches:
			return exact_matches[0]

		partial_matches = [
			name for name, normalized in normalized_templates if alias_norm and alias_norm in normalized
		]
		if partial_matches:
			return partial_matches[0]

	return ""


def _matches(tax_type, keys):
	t = (tax_type or "").lower()
	return any(k in t for k in keys)


def _get_item_tax_template_rows(template_name: str):
	# Read child table rows directly (most reliable)
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


def calculate_fbr_tax(doc, method=None):
	for item in doc.items:
		scenario = get_effective_invoice_tax_scenario(doc)
		template_name = resolve_item_tax_template_name(scenario)

		if template_name and not (item.item_tax_template or "").strip():
			item.item_tax_template = template_name
		# If no mapping is found, keep any manually selected template.

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
				message=f"Template: {item.item_tax_template} | Item: {item.item_code} | SI: {doc.name}",
			)
			continue

		# Determine rates
		for tr in tax_rows:
			tax_type = tr.get("tax_type") or ""
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
