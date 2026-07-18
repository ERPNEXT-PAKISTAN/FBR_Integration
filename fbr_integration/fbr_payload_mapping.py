import frappe
from frappe.utils import getdate

MAPPING_DOCTYPE = "FBR Payload Field Mapping"
DETAIL_DOCTYPE = "FBR Payload Field Mapping Detail"
SOURCE_FIELD_DOCTYPE = "FBR Payload Source Field"
MAPPING_TABLE_FIELDS = ("header_mappings", "item_mappings", "mappings")
SOURCE_FIELD_DOCTYPES = (
	"Sales Invoice",
	"Sales Invoice Item",
	"Address",
	"Customer",
	"Company",
	"Item",
	"Item Tax Template",
)
HEADER_LINKED_DOCTYPE_FIELDS = {
	"Customer": "customer",
	"Company": "company",
}
ITEM_LINKED_DOCTYPE_FIELDS = {
	"Item": "item_code",
	"Item Tax Template": "item_tax_template",
}


DEFAULT_PAYLOAD_FIELD_MAPPINGS = [
	# Header
	{
		"payload_section": "Header",
		"payload_field": "invoiceType",
		"source_doctype": "Sales Invoice",
		"source_field": "custom_invoice_type",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice → Invoice Type (custom_invoice_type). For returns app may retry as Debit Note if FBR rejects Credit Note.",
	},
	{
		"payload_section": "Header",
		"payload_field": "invoiceDate",
		"source_doctype": "Sales Invoice",
		"source_field": "posting_date",
		"transform": "Date YYYY-MM-DD",
		"description": "Current: Sales Invoice → Posting Date (posting_date).",
	},
	{
		"payload_section": "Header",
		"payload_field": "sellerNTNCNIC",
		"source_doctype": "Sales Invoice",
		"source_field": "company_tax_id",
		"transform": "Registration No",
		"description": "Current: Sales Invoice → Company Tax ID (company_tax_id), digits only.",
	},
	{
		"payload_section": "Header",
		"payload_field": "sellerBusinessName",
		"source_doctype": "Sales Invoice",
		"source_field": "company",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice → Company (company).",
	},
	{
		"payload_section": "Header",
		"payload_field": "sellerAddress",
		"source_doctype": "Address",
		"source_field": "",
		"transform": "FBR Text",
		"description": "Current: Company Address → Address Line 1 + City. If mapped to Address, app reads the invoice company_address record.",
	},
	{
		"payload_section": "Header",
		"payload_field": "sellerProvince",
		"source_doctype": "Address",
		"source_field": "state",
		"transform": "FBR Text",
		"description": "Current: Company Address → State. If mapped to Address, app reads the invoice company_address record.",
	},
	{
		"payload_section": "Header",
		"payload_field": "buyerNTNCNIC",
		"source_doctype": "Sales Invoice",
		"source_field": "tax_id",
		"transform": "Registration No",
		"description": "Current: Sales Invoice → Tax ID (tax_id), digits only.",
	},
	{
		"payload_section": "Header",
		"payload_field": "buyerBusinessName",
		"source_doctype": "Sales Invoice",
		"source_field": "customer",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice → Customer link field (customer), not Customer Name.",
	},
	{
		"payload_section": "Header",
		"payload_field": "buyerAddress",
		"source_doctype": "Address",
		"source_field": "",
		"transform": "FBR Text",
		"description": "Current: Customer Address → Address Line 1 + City. If mapped to Address, app reads the invoice customer_address record.",
	},
	{
		"payload_section": "Header",
		"payload_field": "buyerProvince",
		"source_doctype": "Address",
		"source_field": "state",
		"transform": "FBR Text",
		"description": "Current: Customer Address → State. If mapped to Address, app reads the invoice customer_address record.",
	},
	{
		"payload_section": "Header",
		"payload_field": "invoiceRefNo",
		"source_doctype": "Sales Invoice",
		"source_field": "name",
		"transform": "Text",
		"description": "Current: Sales Invoice → Name (name).",
	},
	{
		"payload_section": "Header",
		"payload_field": "scenarioId",
		"source_doctype": "Sales Invoice",
		"source_field": "custom_scenario_id",
		"transform": "Text",
		"description": "Current: Sales Invoice → Scenario ID (custom_scenario_id).",
	},
	{
		"payload_section": "Header",
		"payload_field": "referencedInvoiceNo",
		"source_doctype": "Sales Invoice",
		"source_field": "",
		"transform": "Text",
		"description": "Current: Sales Invoice name; for returns current source FBR invoice number overrides this.",
	},
	{
		"payload_section": "Header",
		"payload_field": "sourceInvoiceNo",
		"source_doctype": "Sales Invoice",
		"source_field": "",
		"transform": "Text",
		"description": "Current: Sales Invoice name; for returns current source FBR invoice number overrides this.",
	},
	{
		"payload_section": "Header",
		"payload_field": "reason",
		"source_doctype": "Sales Invoice",
		"source_field": "custom_fbr_reason",
		"transform": "FBR Text",
		"description": "Current: FBR Return Reason, then parsed Remarks, then Sales Return.",
	},
	{
		"payload_section": "Header",
		"payload_field": "remarks",
		"source_doctype": "Sales Invoice",
		"source_field": "remarks",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice → Remarks (remarks).",
	},
	{
		"payload_section": "Header",
		"payload_field": "buyerRegistrationType",
		"source_doctype": "Sales Invoice",
		"source_field": "custom_tax_payer_type",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice → Tax Payer Type (custom_tax_payer_type).",
	},
	# Item
	{
		"payload_section": "Item",
		"payload_field": "hsCode",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_hs_code",
		"transform": "Text",
		"description": "Current: Sales Invoice Item → HS Code (custom_hs_code).",
	},
	{
		"payload_section": "Item",
		"payload_field": "productDescription",
		"source_doctype": "Sales Invoice Item",
		"source_field": "item_name",
		"transform": "FBR Item Text",
		"description": "Current: Sales Invoice Item → Item Name (item_name).",
	},
	{
		"payload_section": "Item",
		"payload_field": "rate",
		"source_doctype": "Sales Invoice Item",
		"source_field": "",
		"transform": "Text",
		"description": "Current: Sales Tax Rate as percent; Exempt and Zero Rated scenarios override this with FBR labels.",
	},
	{
		"payload_section": "Item",
		"payload_field": "uoM",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_fbr_uom",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice Item → FBR UOM (custom_fbr_uom).",
	},
	{
		"payload_section": "Item",
		"payload_field": "quantity",
		"source_doctype": "Sales Invoice Item",
		"source_field": "qty",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Qty (qty), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "totalValues",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_tax_inclusive_amount",
		"transform": "Absolute Float",
		"description": "Current: Tax Inclusive Amount; app falls back to amount + taxes when empty.",
	},
	{
		"payload_section": "Item",
		"payload_field": "valueSalesExcludingST",
		"source_doctype": "Sales Invoice Item",
		"source_field": "amount",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Amount (amount), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "fixedNotifiedValueOrRetailPrice",
		"source_doctype": "Sales Invoice Item",
		"source_field": "rate",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Rate (rate), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "salesTaxApplicable",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_sales_tax",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Sales Tax Amount (custom_sales_tax), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "salesTaxWithheldAtSource",
		"source_doctype": "Sales Invoice Item",
		"source_field": "",
		"transform": "Float",
		"description": "Current: constant 0.",
	},
	{
		"payload_section": "Item",
		"payload_field": "extraTax",
		"source_doctype": "Sales Invoice Item",
		"source_field": "",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Extra Tax (custom_extra_tax); blank for scenarios where FBR rejects zero.",
	},
	{
		"payload_section": "Item",
		"payload_field": "furtherTax",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_further_tax",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Further Tax (custom_further_tax), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "sroScheduleNo",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_sro_schedule_no",
		"transform": "Text",
		"description": "Current: Sales Invoice Item → SRO Schedule No, with scenario-specific normalization.",
	},
	{
		"payload_section": "Item",
		"payload_field": "fedPayable",
		"source_doctype": "Sales Invoice Item",
		"source_field": "",
		"transform": "Float",
		"description": "Current: constant 0.",
	},
	{
		"payload_section": "Item",
		"payload_field": "discount",
		"source_doctype": "Sales Invoice Item",
		"source_field": "discount_amount",
		"transform": "Absolute Float",
		"description": "Current: Sales Invoice Item → Discount Amount (discount_amount), absolute for returns.",
	},
	{
		"payload_section": "Item",
		"payload_field": "saleType",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_sale_type",
		"transform": "FBR Text",
		"description": "Current: Sales Invoice Item → Sale Type, with scenario-specific normalization.",
	},
	{
		"payload_section": "Item",
		"payload_field": "sroItemSerialNo",
		"source_doctype": "Sales Invoice Item",
		"source_field": "custom_sro_item_sno",
		"transform": "Text",
		"description": "Current: Sales Invoice Item → SRO Item SNo (custom_sro_item_sno).",
	},
]


def safe_float(val):
	try:
		num = float(val)
		return num if num >= 0 else 0
	except (TypeError, ValueError):
		return 0


def safe_abs_float(val):
	try:
		return abs(float(val))
	except (TypeError, ValueError):
		return 0


def rounded_float(val, precision):
	try:
		from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

		quant = Decimal("1").scaleb(-precision)
		return float(Decimal(str(val or 0)).quantize(quant, rounding=ROUND_HALF_UP))
	except (InvalidOperation, TypeError, ValueError):
		return 0


def fbr_money(val):
	return rounded_float(val, 2)


def fbr_quantity(val):
	return rounded_float(val, 4)


def safe_str(val):
	if val is None:
		return ""
	return str(val)


def safe_fbr_text(val):
	text = safe_str(val)
	text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
	text = text.replace("\\", "/").replace('"', "")
	return " ".join(text.split())


def safe_fbr_item_text(val):
	import re

	text = safe_fbr_text(val).replace(",", " ")
	text = re.sub(r"[^A-Za-z0-9./\- ]+", " ", text)
	return " ".join(text.split())


def normalize_registration_no(val):
	import re

	return re.sub(r"\D+", "", safe_str(val))


def _doctype_available():
	return frappe.db.exists("DocType", MAPPING_DOCTYPE)


def _source_field_doctype_available():
	return frappe.db.exists("DocType", SOURCE_FIELD_DOCTYPE)


def _source_field_link_name(source_doctype, source_field):
	if not source_doctype or not source_field:
		return ""
	if "." in source_field and source_field.startswith(f"{source_doctype}."):
		return source_field
	return f"{source_doctype}.{source_field}"


def get_source_fieldname(source_doctype, source_field):
	if not source_field:
		return ""
	if "." in source_field and source_field.startswith(f"{source_doctype}."):
		return source_field.split(".", 1)[1]
	return source_field


def sync_payload_source_fields():
	if not _source_field_doctype_available():
		return

	blocked = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Fold"}
	for source_doctype in SOURCE_FIELD_DOCTYPES:
		if not frappe.db.exists("DocType", source_doctype):
			continue

		rows = [
			{
				"name": _source_field_link_name(source_doctype, "name"),
				"source_doctype": source_doctype,
				"fieldname": "name",
				"label": "Document Name",
				"fieldtype": "Data",
			}
		]
		for field in frappe.get_meta(source_doctype).fields:
			if field.fieldtype in blocked or not field.fieldname:
				continue
			rows.append(
				{
					"name": _source_field_link_name(source_doctype, field.fieldname),
					"source_doctype": source_doctype,
					"fieldname": field.fieldname,
					"label": field.label or field.fieldname,
					"fieldtype": field.fieldtype,
				}
			)

		for row in rows:
			if frappe.db.exists(SOURCE_FIELD_DOCTYPE, row["name"]):
				frappe.db.set_value(
					SOURCE_FIELD_DOCTYPE,
					row["name"],
					{
						"source_doctype": row["source_doctype"],
						"fieldname": row["fieldname"],
						"label": row["label"],
						"fieldtype": row["fieldtype"],
					},
					update_modified=False,
				)
				continue

			doc = frappe.new_doc(SOURCE_FIELD_DOCTYPE)
			doc.update(row)
			doc.insert(ignore_permissions=True)

	frappe.db.commit()
	frappe.clear_cache(doctype=SOURCE_FIELD_DOCTYPE)


def _table_field_for_section(section):
	return "item_mappings" if section == "Item" else "header_mappings"


def _iter_mapping_rows(settings):
	for table_field in MAPPING_TABLE_FIELDS:
		yield from settings.get(table_field) or []


def _move_legacy_rows_to_section_tables():
	if not frappe.db.table_exists(DETAIL_DOCTYPE):
		return

	legacy_rows = frappe.get_all(
		DETAIL_DOCTYPE,
		filters={"parent": MAPPING_DOCTYPE, "parentfield": "mappings"},
		fields=["name", "payload_section"],
		ignore_permissions=True,
	)
	for row in legacy_rows:
		frappe.db.set_value(
			DETAIL_DOCTYPE,
			row.name,
			"parentfield",
			_table_field_for_section(row.payload_section),
			update_modified=False,
		)


def sync_payload_field_mappings():
	if not _doctype_available():
		return

	sync_payload_source_fields()
	_move_legacy_rows_to_section_tables()
	settings = frappe.get_single(MAPPING_DOCTYPE)
	settings.enabled = 1 if settings.enabled is None else settings.enabled
	for mapping_row in _iter_mapping_rows(settings):
		if mapping_row.source_doctype and mapping_row.source_field:
			mapping_row.source_field = _source_field_link_name(
				mapping_row.source_doctype, mapping_row.source_field
			)

	existing = {(row.payload_section, row.payload_field) for row in _iter_mapping_rows(settings)}

	for row in DEFAULT_PAYLOAD_FIELD_MAPPINGS:
		key = (row["payload_section"], row["payload_field"])
		if key in existing:
			continue
		settings.append(
			_table_field_for_section(row["payload_section"]),
			{
				"enabled": 1,
				"payload_section": row["payload_section"],
				"payload_field": row["payload_field"],
				"source_doctype": row.get("source_doctype"),
				"source_field": _source_field_link_name(row.get("source_doctype"), row.get("source_field")),
				"transform": row.get("transform") or "Raw",
				"current_source": _current_source(row),
				"description": row.get("description"),
			},
		)

	settings.save(ignore_permissions=True)
	frappe.db.commit()
	frappe.clear_cache(doctype=MAPPING_DOCTYPE)


def _current_source(row):
	source_doctype = row.get("source_doctype") or ""
	source_field = get_source_fieldname(source_doctype, row.get("source_field") or "")
	if not source_doctype or not source_field:
		return "Computed / Constant"
	return f"{source_doctype}.{source_field}"


def _get_settings_rows():
	try:
		if not _doctype_available():
			return {}
		settings = frappe.get_cached_doc(MAPPING_DOCTYPE)
	except Exception:
		return {}

	if not getattr(settings, "enabled", 0):
		return {}

	rows = {}
	for row in _iter_mapping_rows(settings):
		if getattr(row, "enabled", 0) and row.payload_field:
			rows[(row.payload_section, row.payload_field)] = row
	return rows


def _get_address_doc(doc, payload_field):
	address_name = (
		getattr(doc, "company_address", None)
		if payload_field.startswith("seller")
		else getattr(doc, "customer_address", None)
	)
	if not address_name:
		return None
	try:
		return frappe.get_doc("Address", address_name)
	except Exception:
		return None


def _get_linked_doc(source_doctype, source_name):
	if not source_name:
		return None
	try:
		return frappe.get_doc(source_doctype, source_name)
	except Exception:
		return None


def _get_source_value(row, doc, item=None):
	source_doctype = (getattr(row, "source_doctype", None) or "").strip()
	source_field = get_source_fieldname(source_doctype, (getattr(row, "source_field", None) or "").strip())
	payload_field = (getattr(row, "payload_field", None) or "").strip()
	if not source_doctype or not source_field:
		return None

	if source_doctype == "Sales Invoice":
		source_doc = doc
	elif source_doctype == "Sales Invoice Item":
		source_doc = item
	elif source_doctype == "Address":
		source_doc = _get_address_doc(doc, payload_field)
	elif source_doctype in HEADER_LINKED_DOCTYPE_FIELDS:
		source_doc = _get_linked_doc(
			source_doctype, getattr(doc, HEADER_LINKED_DOCTYPE_FIELDS[source_doctype], None)
		)
	elif source_doctype in ITEM_LINKED_DOCTYPE_FIELDS:
		source_doc = _get_linked_doc(
			source_doctype,
			getattr(item, ITEM_LINKED_DOCTYPE_FIELDS[source_doctype], None) if item else None,
		)
	else:
		return None

	if not source_doc:
		return None
	return getattr(source_doc, source_field, None)


def apply_mapping_transform(value, transform):
	transform = (transform or "Raw").strip()
	if transform == "Text":
		return safe_str(value)
	if transform == "FBR Text":
		return safe_fbr_text(value)
	if transform == "FBR Item Text":
		return safe_fbr_item_text(value)
	if transform == "Registration No":
		return normalize_registration_no(value)
	if transform == "Date YYYY-MM-DD":
		return str(getdate(value)) if value else ""
	if transform == "Float":
		return safe_float(value)
	if transform == "Absolute Float":
		return safe_abs_float(value)
	if transform == "Money 2 Decimals":
		return fbr_money(value)
	if transform == "Quantity 4 Decimals":
		return fbr_quantity(value)
	return value


def resolve_payload_value(payload_field, default, doc, item=None, section="Header"):
	row = _get_settings_rows().get((section, payload_field))
	if not row:
		return default

	value = _get_source_value(row, doc, item=item)
	if value in (None, ""):
		return default

	return apply_mapping_transform(value, getattr(row, "transform", None))


@frappe.whitelist()
def get_doctype_field_options(doctype):
	if not doctype:
		return []

	try:
		meta = frappe.get_meta(doctype)
	except Exception:
		return []

	blocked = {"Section Break", "Column Break", "Tab Break", "HTML", "Button", "Table", "Fold"}
	fields = [
		{"value": _source_field_link_name(doctype, "name"), "label": "name - Document Name"},
	]
	for field in meta.fields:
		if field.fieldtype in blocked or not field.fieldname:
			continue
		label = field.label or field.fieldname
		fields.append(
			{
				"value": _source_field_link_name(doctype, field.fieldname),
				"label": f"{field.fieldname} - {label}",
			}
		)
	return fields


@frappe.whitelist()
def search_doctype_fields(doctype=None, source_doctype=None, txt=None, **kwargs):
	selected_doctype = source_doctype or doctype
	search_text = (txt or "").lower()
	fields = get_doctype_field_options(selected_doctype)
	if search_text:
		fields = [
			field
			for field in fields
			if search_text in field.get("value", "").lower() or search_text in field.get("label", "").lower()
		]
	return fields
