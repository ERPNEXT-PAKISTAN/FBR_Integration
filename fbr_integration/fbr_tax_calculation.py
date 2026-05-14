import frappe

DEFAULT_FBR_SCENARIO = "Pakistan Tax"

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

MANUAL_SCENARIO_KEYS = {"", "manual", "manual item wise", "none", "no scenario"}
SCENARIO_APPLY_MODE_FILL = "Fill Empty Items"
SCENARIO_APPLY_MODE_FORCE = "Update All Items"


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


def _normalize_text(value):
	return " ".join((value or "").lower().replace("/", " ").replace("-", " ").replace("_", " ").split())


def _scenario_aliases(scenario: str):
	normalized = _normalize_text(scenario)
	if normalized in MANUAL_SCENARIO_KEYS:
		return []
	return SCENARIO_TEMPLATE_ALIASES.get(normalized, [])


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
	apply_mode = (getattr(doc, "custom_fbr_scenario_apply_mode", None) or "").strip()
	auto_apply = apply_mode in {SCENARIO_APPLY_MODE_FILL, SCENARIO_APPLY_MODE_FORCE}
	force_apply = apply_mode == SCENARIO_APPLY_MODE_FORCE

	for item in doc.items:
		item_scenario = (getattr(item, "custom_fbr_item_scenario", None) or "").strip()
		doc_scenario = (getattr(doc, "custom_fbr_scenario", None) or "").strip()
		scenario = item_scenario or doc_scenario
		template_name = resolve_item_tax_template_name(scenario)

		if auto_apply and template_name and (force_apply or not (item.item_tax_template or "").strip()):
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
