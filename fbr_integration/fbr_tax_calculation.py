import frappe
from frappe.utils import cint

DEFAULT_INVOICE_TYPE = "Sale Invoice"
DEFAULT_SCENARIO_DETAIL = "SN001 - Goods at Standard Rate (Registered Buyer)"
DEFAULT_SCENARIO_ID = "SN001"
DEFAULT_ITEM_TAX_TEMPLATE_TITLE = "SN001 - 18% Goods at Standard Rate to Registered Buyers"
FBR_INVOICE_DOCTYPES = ("Sales Invoice", "POS Invoice")

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


def _extract_scenario_id(scenario: str) -> str:
	text = (scenario or "").strip().upper()
	if text.startswith("SN") and len(text) >= 5 and text[2:5].isdigit():
		return text[:5]
	return ""


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


def is_fbr_invoice_doctype(doc) -> bool:
	return getattr(doc, "doctype", None) in FBR_INVOICE_DOCTYPES


def ensure_pos_flag(doc, method=None):
	"""Keep Is POS checked when invoice comes from a POS Profile / POS screen."""
	if not is_fbr_invoice_doctype(doc):
		return
	if getattr(doc, "pos_profile", None) or int(getattr(doc, "is_created_using_pos", 0) or 0):
		doc.is_pos = 1


def _is_pos_invoice(doc) -> bool:
	return bool(
		cint(getattr(doc, "is_pos", 0))
		or cint(getattr(doc, "is_created_using_pos", 0))
		or getattr(doc, "pos_profile", None)
	)


def _pos_wht_setting_enabled() -> bool:
	try:
		return bool(cint(frappe.db.get_single_value("FBR Invoice Settings", "apply_tax_withholding_on_pos")))
	except Exception:
		return False


def _clear_invoice_apply_tds(doc):
	if hasattr(doc, "apply_tds"):
		doc.apply_tds = 0
	for item in doc.get("items") or []:
		if hasattr(item, "apply_tds"):
			item.apply_tds = 0


def _has_applicable_wht_rate(doc) -> bool:
	"""True when a Tax Withholding Category rate window matches posting date + group."""
	from frappe.utils import cstr, getdate

	posting = getdate(getattr(doc, "posting_date", None))
	if not posting:
		return False
	group = cstr(getattr(doc, "tax_withholding_group", None))
	cats = {
		cstr(getattr(item, "tax_withholding_category", None))
		for item in (doc.get("items") or [])
		if getattr(item, "tax_withholding_category", None)
	}
	if not cats and getattr(doc, "customer", None):
		cat = frappe.db.get_value("Customer", doc.customer, "tax_withholding_category")
		if cat:
			cats.add(cstr(cat))
	if not cats:
		return False

	for cat in cats:
		if not frappe.db.exists("Tax Withholding Category", cat):
			continue
		try:
			cat_doc = frappe.get_cached_doc("Tax Withholding Category", cat)
		except Exception:
			continue
		for row in cat_doc.get("rates") or []:
			try:
				if getdate(row.from_date) <= posting <= getdate(row.to_date) and cstr(
					row.tax_withholding_group
				) == group:
					return True
			except Exception:
				continue
	return False


def gate_pos_tax_withholding(doc, method=None):
	"""POS: Consider for Tax Withholding is opt-in and must never block checkout.

	Default is off (FBR Invoice Settings + POS checkbox). If withholding is on
	but no rate exists for the posting date, skip it instead of throwing.
	"""
	if not is_fbr_invoice_doctype(doc) or not _is_pos_invoice(doc):
		return
	if not hasattr(doc, "apply_tds"):
		return

	explicit = bool(cint(getattr(doc, "custom_apply_tax_withholding", 0)))
	if not explicit:
		_clear_invoice_apply_tds(doc)
		return

	doc.apply_tds = 1
	if not _has_applicable_wht_rate(doc):
		_clear_invoice_apply_tds(doc)
		frappe.msgprint(
			"Tax withholding was skipped: no Tax Withholding rate found for this posting date.",
			indicator="orange",
			alert=True,
		)


def _link_exists(doctype: str, name: str) -> bool:
	if not doctype or not name:
		return False
	try:
		return bool(frappe.db.exists(doctype, name))
	except Exception:
		return False


def _resolve_default_scenario_detail() -> str:
	if _link_exists("Scenario ID", DEFAULT_SCENARIO_DETAIL):
		return DEFAULT_SCENARIO_DETAIL
	try:
		name = frappe.db.get_value("Scenario ID", {"scenario_id": DEFAULT_SCENARIO_ID}, "name")
		if name:
			return name
	except Exception:
		pass
	return ""


def apply_default_invoice_type_and_scenario(doc, method=None):
	"""Fill Sale Invoice + SN001 when FBR header fields are empty.

	Desk forms, POS/API inserts, and Send to FBR all need these so FBR
	does not reject a payload with a blank invoiceType or scenarioId.
	Returns are left to enforce_return_invoice_type (Credit Note).
	"""
	if not is_fbr_invoice_doctype(doc):
		return

	is_return = cint(getattr(doc, "is_return", 0)) == 1
	if (
		not is_return
		and hasattr(doc, "custom_invoice_type")
		and not (getattr(doc, "custom_invoice_type", None) or "").strip()
		and _link_exists("Invoice Type", DEFAULT_INVOICE_TYPE)
	):
		doc.custom_invoice_type = DEFAULT_INVOICE_TYPE

	if hasattr(doc, "custom_scenario_detail") and not (
		getattr(doc, "custom_scenario_detail", None) or ""
	).strip():
		scenario_detail = _resolve_default_scenario_detail()
		if scenario_detail:
			doc.custom_scenario_detail = scenario_detail

	detail = (getattr(doc, "custom_scenario_detail", None) or "").strip()
	if hasattr(doc, "custom_scenario_id") and not (
		getattr(doc, "custom_scenario_id", None) or ""
	).strip():
		scenario_id = ""
		if detail:
			try:
				scenario_id = frappe.db.get_value("Scenario ID", detail, "scenario_id") or ""
			except Exception:
				scenario_id = ""
		doc.custom_scenario_id = scenario_id or (DEFAULT_SCENARIO_ID if detail else "")

	apply_scenario_tax_templates_to_items(doc, overwrite=False)


def apply_scenario_tax_templates_to_items(doc, overwrite=False):
	"""Apply the parent scenario's Item Tax Template to invoice items.

	Empty rows get the template. When overwrite=True (parent scenario changed),
	existing templates are updated too. Fields stay editable.
	"""
	scenario = get_effective_invoice_tax_scenario(doc) or DEFAULT_SCENARIO_DETAIL
	detail = (getattr(doc, "custom_scenario_detail", None) or "").strip()
	template_name = ""
	try:
		template_name = resolve_item_tax_template_name(
			scenario, company=getattr(doc, "company", None)
		)
	except Exception:
		template_name = ""

	for item in doc.get("items") or []:
		if detail and hasattr(item, "custom_scenario_detail"):
			item_detail = (getattr(item, "custom_scenario_detail", None) or "").strip()
			if overwrite or not item_detail:
				item.custom_scenario_detail = detail

		if not template_name or not hasattr(item, "item_tax_template"):
			continue
		current = (getattr(item, "item_tax_template", None) or "").strip()
		if overwrite or not current:
			item.item_tax_template = template_name


def persist_fbr_header_defaults(doc):
	"""Write filled FBR header defaults onto an already-saved invoice."""
	name = getattr(doc, "name", None)
	doctype = getattr(doc, "doctype", None)
	if not name or not doctype or not frappe.db.exists(doctype, name):
		return

	updates = {}
	for field in ("custom_invoice_type", "custom_scenario_detail", "custom_scenario_id"):
		value = (getattr(doc, field, None) or "").strip()
		if value:
			updates[field] = value
	if updates:
		frappe.db.set_value(doctype, name, updates, update_modified=False)


def sync_sales_invoice_master_defaults(doc, method=None):
	"""Fill FBR fields from Customer/Item masters when invoice/item values are empty."""
	if not is_fbr_invoice_doctype(doc):
		return

	apply_default_invoice_type_and_scenario(doc)

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

		customer_type = (customer_defaults.get("custom_tax_payer_type") or "").strip()
		customer_province = (customer_defaults.get("custom_buyer_province") or "").strip()
		if customer_type and not (getattr(doc, "custom_tax_payer_type", None) or "").strip():
			doc.custom_tax_payer_type = customer_type
		if customer_province and not (getattr(doc, "custom_buyer_province", None) or "").strip():
			doc.custom_buyer_province = customer_province

	for item in doc.get("items") or []:
		if not item.item_code:
			continue

		fields = ["custom_hs_code", "custom_fbr_uom"]
		try:
			if frappe.db.has_column("Item", "custom_fbr_tax_profile"):
				fields.append("custom_fbr_tax_profile")
		except Exception:
			pass

		item_defaults = (
			frappe.db.get_value(
				"Item",
				item.item_code,
				fields,
				as_dict=True,
			)
			or {}
		)

		item_hs = (item_defaults.get("custom_hs_code") or "").strip()
		item_uom = (item_defaults.get("custom_fbr_uom") or "").strip()
		item_profile = (item_defaults.get("custom_fbr_tax_profile") or "").strip()
		current_hs = (getattr(item, "custom_hs_code", None) or "").strip()
		current_uom = (getattr(item, "custom_fbr_uom", None) or "").strip()

		# Field defaults (3005.1010 / KG) used to block fetch_from / empty-only sync.
		if item_hs and (not current_hs or current_hs == "3005.1010"):
			item.custom_hs_code = item_hs

		if item_uom and (not current_uom or current_uom == "KG"):
			item.custom_fbr_uom = item_uom

		if (
			item_profile
			and hasattr(item, "custom_fbr_tax_profile")
			and not (getattr(item, "custom_fbr_tax_profile", None) or "").strip()
		):
			item.custom_fbr_tax_profile = item_profile


def sync_return_source_invoice_no(doc, method=None):
	"""Copy source FBR invoice number to return invoices.

	When a Sales Return is created against a submitted Sales Invoice, ERPNext sets
	`return_against` to the source invoice name. FBR needs the original FBR invoice
	number, so keep `custom_fbr_source_invoice_no` aligned with the source invoice's
	`custom_fbr_invoice_no`.
	"""
	if not is_fbr_invoice_doctype(doc):
		return

	if not getattr(doc, "is_return", 0):
		return

	if not hasattr(doc, "custom_fbr_source_invoice_no"):
		return

	return_against = (getattr(doc, "return_against", None) or "").strip()
	if not return_against:
		return

	doc.custom_fbr_source_invoice_no = get_source_fbr_invoice_no(return_against)


def get_source_fbr_invoice_no(return_against: str) -> str:
	"""Look up custom_fbr_invoice_no on Sales Invoice or POS Invoice."""
	name = (return_against or "").strip()
	if not name:
		return ""
	for doctype in FBR_INVOICE_DOCTYPES:
		try:
			if not frappe.db.exists(doctype, name):
				continue
			if not frappe.db.has_column(doctype, "custom_fbr_invoice_no"):
				continue
			value = (frappe.db.get_value(doctype, name, "custom_fbr_invoice_no") or "").strip()
			if value:
				return value
		except Exception:
			continue
	return ""


def get_fbr_invoice_doc(name: str):
	"""Load a Sales Invoice or POS Invoice by name."""
	invoice_name = (name or "").strip()
	if not invoice_name:
		frappe.throw("Invoice name is required.")
	for doctype in FBR_INVOICE_DOCTYPES:
		if frappe.db.exists(doctype, invoice_name):
			return frappe.get_doc(doctype, invoice_name)
	frappe.throw(f"Invoice {invoice_name} not found.")


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


def resolve_item_tax_template_name(scenario: str | None = None, company: str | None = None):
	"""Return the Item Tax Template for an FBR scenario, preferring the invoice company.

	SN001 on company SSC resolves to
	"SN001 - 18% Goods at Standard Rate to Registered Buyers - SSC".
	"""
	scenario = (scenario or "").strip() or DEFAULT_SCENARIO_DETAIL
	scenario_id = _extract_scenario_id(scenario)
	company = (company or "").strip()

	templates = _list_item_tax_templates(company)
	if not templates and company:
		templates = _list_item_tax_templates(None)
	if not templates:
		return _fallback_template_name(company, scenario_id)

	if scenario_id:
		prefixed = [
			row
			for row in templates
			if _template_matches_scenario(row, scenario_id)
		]
		if prefixed:
			return _prefer_company_template(prefixed, company)

	aliases = _scenario_aliases(scenario)
	normalized_templates = [
		(row["name"], _normalize_text(row.get("name") or ""), _normalize_text(row.get("title") or ""))
		for row in templates
	]
	for alias in aliases:
		alias_norm = _normalize_text(alias)
		if not alias_norm:
			continue
		exact = [name for name, name_n, title_n in normalized_templates if alias_norm in (name_n, title_n)]
		if exact:
			return exact[0]
		partial = [
			name
			for name, name_n, title_n in normalized_templates
			if alias_norm in name_n or alias_norm in title_n
		]
		if partial:
			return partial[0]

	return _fallback_template_name(company, scenario_id)


def _list_item_tax_templates(company: str | None):
	filters = {"disabled": 0}
	if company:
		filters["company"] = company
	try:
		return (
			frappe.get_all(
				"Item Tax Template",
				filters=filters,
				fields=["name", "title"],
				order_by="name asc",
				ignore_permissions=True,
			)
			or []
		)
	except Exception:
		return []


def _template_matches_scenario(row, scenario_id: str) -> bool:
	needle = scenario_id.upper()
	name = (row.get("name") or "").upper()
	title = (row.get("title") or "").upper()
	return name.startswith(f"{needle} ") or name.startswith(f"{needle}-") or title.startswith(needle)


def _prefer_company_template(rows, company: str | None) -> str:
	if company:
		try:
			abbr = frappe.get_cached_value("Company", company, "abbr") or ""
		except Exception:
			abbr = ""
		if abbr:
			suffix = f" - {abbr}"
			for row in rows:
				if (row.get("name") or "").endswith(suffix):
					return row["name"]
	return rows[0]["name"]


def _fallback_template_name(company: str | None, scenario_id: str) -> str:
	if scenario_id and scenario_id != DEFAULT_SCENARIO_ID:
		return ""
	title = DEFAULT_ITEM_TAX_TEMPLATE_TITLE
	candidates = [title]
	if company:
		try:
			abbr = frappe.get_cached_value("Company", company, "abbr") or ""
		except Exception:
			abbr = ""
		if abbr:
			candidates.insert(0, f"{title} - {abbr}")
	for name in candidates:
		if _link_exists("Item Tax Template", name):
			return name
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

	# Category on the item row is the source of truth (e.g. ST Withheld - 2%).
	# A leftover sales-tax % in custom_sales_tax_withheld_rate must not win.
	item_cat = getattr(item, "tax_withholding_category", None) or ""
	rate = _rate_from_withholding_category(item_cat)
	if rate:
		return rate

	existing = float(getattr(item, "custom_sales_tax_withheld_rate", None) or 0)
	if existing:
		return existing

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
		amt = abs(float(item.amount or 0))
		item.custom_sales_tax_withheld_rate = round((share / amt) * 100, 6) if amt else 0



def sync_item_apply_tds_with_parent(doc, method=None):
	"""Keep item Consider for Tax Withholding aligned with the invoice checkbox.

	- Parent unchecked → every item row unchecked (no per-line WHT).
	- Parent checked → leave item flags as set in the UI (user may uncheck
	  specific lines). New rows default from client to match parent.
	"""
	parent_on = bool(cint(getattr(doc, "apply_tds", 0)))
	if parent_on:
		return
	for item in doc.get("items") or []:
		if cint(getattr(item, "apply_tds", 0)):
			item.apply_tds = 0


def calculate_fbr_tax(doc, method=None):
	if not is_fbr_invoice_doctype(doc):
		return

	from fbr_integration.taxation.engine import apply_item_tax_amounts
	from fbr_integration.taxation.snapshot import apply_tax_snapshots

	sync_item_apply_tds_with_parent(doc)
	apply_tax_snapshots(doc)
	invoice_withheld = 0.0

	for item in doc.items:
		scenario = get_effective_invoice_tax_scenario(doc)
		template_name = resolve_item_tax_template_name(
			scenario, company=getattr(doc, "company", None)
		)

		if template_name and not (item.item_tax_template or "").strip():
			item.item_tax_template = template_name
		# If no mapping is found, keep any manually selected template.

		qty = float(item.qty or 0)
		rate = float(item.rate or 0)

		if not item.amount:
			item.amount = qty * rate

		amount = float(item.amount or 0)

		withheld_rate = _default_st_withheld_rate(doc, item)
		# If Consider for Tax Withholding is off (invoice or row), clear FBR withheld fields.
		# Withholding stays on commercial sales value, not MRP.
		if not _item_considers_tax_withholding(doc, item):
			item.custom_sales_tax_withheld_rate = 0
			item.custom_sales_tax_withheld_at_source = 0
		else:
			item.custom_sales_tax_withheld_rate = withheld_rate
			item.custom_sales_tax_withheld_at_source = (
				(amount * withheld_rate) / 100 if withheld_rate else 0
			)

		tax_rows = []
		if item.item_tax_template:
			tax_rows = _get_item_tax_template_rows(item.item_tax_template)
			if not tax_rows:
				frappe.log_error(
					title="FBR Tax Calc: No tax rows found",
					message=f"Template: {item.item_tax_template} | Item: {item.item_code} | SI: {doc.name}",
				)

		apply_item_tax_amounts(doc, item, tax_rows=tax_rows)
		invoice_withheld += float(item.custom_sales_tax_withheld_at_source or 0)

	_allocate_invoice_withholding_to_items(doc)
	invoice_withheld = sum(
		float(getattr(i, "custom_sales_tax_withheld_at_source", None) or 0) for i in (doc.items or [])
	)
	if hasattr(doc, "custom_sales_tax_withheld_at_source"):
		doc.custom_sales_tax_withheld_at_source = invoice_withheld
