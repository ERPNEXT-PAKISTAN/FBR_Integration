import frappe
from frappe.utils import cint

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


def ensure_pos_flag(doc, method=None):
	"""Keep Is POS checked when invoice comes from a POS Profile / POS screen."""
	if doc.doctype != "Sales Invoice":
		return
	if getattr(doc, "pos_profile", None) or int(getattr(doc, "is_created_using_pos", 0) or 0):
		doc.is_pos = 1


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


def _rate_from_withholding_category(category_name: str) -> float:
	"""Current Tax Withholding Category rate, or 0."""
	name = (category_name or "").strip()
	if not name or not frappe.db.exists("DocType", "Tax Withholding Rate"):
		return 0
	try:
		from frappe.utils import getdate, nowdate

		today = getdate(nowdate())
		rates = frappe.get_all(
			"Tax Withholding Rate",
			filters={"parent": name, "parenttype": "Tax Withholding Category"},
			fields=["tax_withholding_rate", "from_date", "to_date"],
			order_by="from_date desc",
		)
		for row in rates:
			if getdate(row.from_date) <= today <= getdate(row.to_date):
				return float(row.tax_withholding_rate or 0)
		if rates:
			return float(rates[0].tax_withholding_rate or 0)
	except Exception:
		pass
	return 0


def _invoice_considers_tax_withholding(doc) -> bool:
	"""Core Sales Invoice field: Consider for Tax Withholding (apply_tds)."""
	return bool(cint(getattr(doc, "apply_tds", 0)))


def _item_considers_tax_withholding(doc, item) -> bool:
	"""Parent + child Consider for Tax Withholding must both allow the line.

	- Invoice.apply_tds off → no auto withholding on any line.
	- Item.apply_tds off → skip that line (when the child checkbox is used).
	- Missing item.apply_tds (older rows) → treat as on when invoice is on.
	"""
	if not _invoice_considers_tax_withholding(doc):
		return False
	if hasattr(item, "apply_tds"):
		return bool(cint(getattr(item, "apply_tds", 1)))
	return True


def _default_st_withheld_rate(doc, item) -> float:
	"""Rate for FBR salesTaxWithheldAtSource.

	- Manual rate typed on the item row is kept only when withholding is allowed
	  for that line (invoice + item Consider for Tax Withholding).
	- Auto rate from Customer/Item Tax Withholding Category only when both
	  Sales Invoice.apply_tds and item.apply_tds are checked.
	"""
	if not _item_considers_tax_withholding(doc, item):
		return 0

	existing = float(getattr(item, "custom_sales_tax_withheld_rate", None) or 0)
	if existing:
		return existing

	item_cat = getattr(item, "tax_withholding_category", None) or ""
	rate = _rate_from_withholding_category(item_cat)
	if rate:
		return rate

	if doc.customer:
		cust = (
			frappe.db.get_value(
				"Customer",
				doc.customer,
				["tax_withholding_category", "tax_withholding_group"],
				as_dict=True,
			)
			or {}
		)
		rate = _rate_from_withholding_category(cust.get("tax_withholding_category") or "")
		if rate:
			return rate
	return 0


def _allocate_invoice_withholding_to_items(doc):
	"""When apply_tds built tax_withholding_entries, push totals into FBR item field."""
	if not _invoice_considers_tax_withholding(doc):
		return

	entries = doc.get("tax_withholding_entries") or []
	if not entries:
		return

	# Prefer ST Withheld / FBR categories; otherwise use all apply_tds entry amounts.
	st_total = 0.0
	all_total = 0.0
	for entry in entries:
		amt = abs(float(getattr(entry, "withholding_amount", None) or 0))
		all_total += amt
		cat = (getattr(entry, "tax_withholding_category", None) or "").upper()
		if "ST WITHHELD" in cat or "SALES TAX WITHHELD" in cat:
			st_total += amt

	wh_total = st_total if st_total > 0 else all_total
	if wh_total <= 0:
		return

	items = [
		i
		for i in (doc.items or [])
		if float(getattr(i, "amount", None) or 0) > 0 and _item_considers_tax_withholding(doc, i)
	]
	if not items:
		return

	base = sum(abs(float(i.amount or 0)) for i in items) or 1
	allocated = 0.0
	for idx, item in enumerate(items):
		if idx == len(items) - 1:
			share = round(wh_total - allocated, 2)
		else:
			share = round(wh_total * (abs(float(item.amount or 0)) / base), 2)
			allocated += share
		item.custom_sales_tax_withheld_at_source = share
		# Keep rate informative when derived from invoice entries
		if not float(getattr(item, "custom_sales_tax_withheld_rate", None) or 0):
			amt = abs(float(item.amount or 0))
			item.custom_sales_tax_withheld_rate = round((share / amt) * 100, 6) if amt else 0


def calculate_fbr_tax(doc, method=None):
	invoice_withheld = 0.0

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

		# Reset tax amounts (keep withheld rate if user/customer set it)
		item.custom_sales_tax_rate = 0
		item.custom_further_tax_rate = 0
		item.custom_extra_tax_rate = 0

		item.custom_sales_tax = 0
		item.custom_further_tax = 0
		item.custom_extra_tax = 0

		item.custom_total_tax_amount = 0
		item.custom_tax_inclusive_amount = amount

		withheld_rate = _default_st_withheld_rate(doc, item)
		# If Consider for Tax Withholding is off (invoice or row), clear FBR withheld fields.
		if not _item_considers_tax_withholding(doc, item):
			item.custom_sales_tax_withheld_rate = 0
			item.custom_sales_tax_withheld_at_source = 0
		else:
			item.custom_sales_tax_withheld_rate = withheld_rate
			item.custom_sales_tax_withheld_at_source = (
				(amount * withheld_rate) / 100 if withheld_rate else 0
			)

		if not item.item_tax_template:
			invoice_withheld += float(item.custom_sales_tax_withheld_at_source or 0)
			continue

		tax_rows = _get_item_tax_template_rows(item.item_tax_template)

		if not tax_rows:
			# Helpful debug (you can remove later)
			frappe.log_error(
				title="FBR Tax Calc: No tax rows found",
				message=f"Template: {item.item_tax_template} | Item: {item.item_code} | SI: {doc.name}",
			)
			invoice_withheld += float(item.custom_sales_tax_withheld_at_source or 0)
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
		invoice_withheld += float(item.custom_sales_tax_withheld_at_source or 0)

	_allocate_invoice_withholding_to_items(doc)
	invoice_withheld = sum(
		float(getattr(i, "custom_sales_tax_withheld_at_source", None) or 0) for i in (doc.items or [])
	)
	if hasattr(doc, "custom_sales_tax_withheld_at_source"):
		doc.custom_sales_tax_withheld_at_source = invoice_withheld
