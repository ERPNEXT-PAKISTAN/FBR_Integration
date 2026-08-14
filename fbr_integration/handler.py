import frappe
from frappe.utils import cint, cstr

from fbr_integration.fbr_tax_calculation import get_fbr_invoice_doc


def _assert_can_read_invoice(doc):
	doctype = getattr(doc, "doctype", None) or "Sales Invoice"
	if frappe.session.user != "Administrator" and not frappe.has_permission(
		doctype, "read", doc=doc
	):
		frappe.throw(
			f"You do not have permission to read this {doctype}.",
			frappe.PermissionError,
			title="Not Permitted",
		)


@frappe.whitelist()
def send_to_fbr_si(name: str):
	from fbr_integration.fbr_api import send_to_fbr_si as _send

	return _send(name)


@frappe.whitelist()
def get_pos_fbr_status(name: str):
	"""POS summary payload: FBR number, status, QR/barcode after each POS submit."""
	doc = get_fbr_invoice_doc(name)
	_assert_can_read_invoice(doc)

	fbr_no = (
		(getattr(doc, "custom_fbr_invoice_no", None) or "").strip()
		or (getattr(doc, "fbr_invoice_number", None) or "").strip()
	)
	status = (getattr(doc, "custom_fbr_invoice_status", None) or "").strip()
	status_code = (getattr(doc, "custom_fbr_invoice_status_code", None) or "").strip()
	error = (getattr(doc, "custom_fbr_invoice_error", None) or "").strip()

	qr_data_url = ""
	barcode_data_url = ""
	if fbr_no:
		try:
			from fbr_integration.print_barcodes import get_qr_and_barcode_data_uri

			data = get_qr_and_barcode_data_uri(fbr_no)
			qr_data_url = data.get("qr") or ""
			barcode_data_url = data.get("barcode") or ""
		except Exception:
			frappe.log_error(title="FBR POS QR failed", message=frappe.get_traceback())

	return {
		"ok": bool(fbr_no),
		"sales_invoice": doc.name,
		"doctype": doc.doctype,
		"is_pos": cint(getattr(doc, "is_pos", 0)),
		"customer": doc.customer,
		"customer_name": doc.customer_name,
		"posting_date": str(doc.posting_date or ""),
		"grand_total": doc.grand_total,
		"currency": doc.currency,
		"fbr_invoice_no": fbr_no,
		"fbr_status": status,
		"fbr_status_code": status_code,
		"fbr_error": error,
		"qr_data_url": qr_data_url,
		"barcode_data_url": barcode_data_url,
	}


HEADER_RETRY_FIELDS = (
	"custom_invoice_type",
	"custom_scenario_detail",
	"custom_scenario_id",
	"custom_tax_payer_type",
	"custom_buyer_province",
	"custom_fbr_source_invoice_no",
	"territory",
	"tax_id",
)
ITEM_RETRY_FIELDS = ("item_tax_template", "custom_hs_code", "custom_scenario_detail", "custom_sale_type")


@frappe.whitelist()
def get_pos_fbr_retry_form(name: str):
	"""Header + item FBR fields for correcting a failed POS invoice before resend."""
	status = get_pos_fbr_status(name)
	doc = get_fbr_invoice_doc(name)
	items = []
	for row in doc.get("items") or []:
		items.append(
			{
				"name": row.name,
				"idx": row.idx,
				"item_code": row.item_code,
				"item_name": getattr(row, "item_name", "") or row.item_code,
				"item_tax_template": getattr(row, "item_tax_template", "") or "",
				"custom_hs_code": getattr(row, "custom_hs_code", "") or "",
				"custom_scenario_detail": getattr(row, "custom_scenario_detail", "") or "",
				"custom_sale_type": getattr(row, "custom_sale_type", "") or "",
			}
		)
	status["fields"] = {field: getattr(doc, field, "") or "" for field in HEADER_RETRY_FIELDS}
	status["items"] = items
	status["options"] = _retry_link_options(
		{
			"Invoice Type": [status["fields"].get("custom_invoice_type")],
			"Scenario ID": [status["fields"].get("custom_scenario_detail")]
			+ [row.get("custom_scenario_detail") for row in items],
			"Tax Payer Type": [status["fields"].get("custom_tax_payer_type")],
			"Buyer Province": [status["fields"].get("custom_buyer_province")],
			"Item Tax Template": [row.get("item_tax_template") for row in items],
			"HS Code": [row.get("custom_hs_code") for row in items],
			"Sale Type": [row.get("custom_sale_type") for row in items],
		}
	)
	return status


RETRY_LINK_LIMITS = {
	"Invoice Type": 200,
	"Scenario ID": 200,
	"Tax Payer Type": 100,
	"Buyer Province": 100,
	"Item Tax Template": 400,
	"HS Code": 500,
	"Sale Type": 100,
}


def _retry_link_options(extra_values=None) -> dict:
	"""Name lists for XPOS retry dropdowns (desk POS uses native Link controls)."""
	extra_values = extra_values or {}
	out = {}
	for doctype, limit in RETRY_LINK_LIMITS.items():
		names = []
		try:
			if frappe.db.exists("DocType", doctype):
				names = frappe.get_all(
					doctype,
					pluck="name",
					order_by="name",
					limit_page_length=limit,
					ignore_permissions=True,
				)
		except Exception:
			names = []
		seen = {cstr(n) for n in names}
		for raw in extra_values.get(doctype) or []:
			value = cstr(raw).strip()
			if value and value not in seen:
				names.insert(0, value)
				seen.add(value)
		out[doctype] = names
	return out


@frappe.whitelist()
def update_and_send_to_fbr(name: str, values=None, items=None):
	"""Save corrected FBR fields on a submitted POS invoice, then send to FBR."""
	from fbr_integration.fbr_api import assert_can_send_invoice_to_fbr, send_to_fbr_si as _send
	from fbr_integration.fbr_tax_calculation import _extract_scenario_id

	doc = get_fbr_invoice_doc(name)
	assert_can_send_invoice_to_fbr(doc)

	if isinstance(values, str):
		values = frappe.parse_json(values)
	values = values or {}
	if isinstance(items, str):
		items = frappe.parse_json(items)
	items = items or []

	meta = frappe.get_meta(doc.doctype)
	header = {}
	for field in HEADER_RETRY_FIELDS:
		if field not in values or not meta.has_field(field):
			continue
		header[field] = values.get(field)
	if header.get("custom_scenario_detail") and not header.get("custom_scenario_id"):
		header["custom_scenario_id"] = _extract_scenario_id(header["custom_scenario_detail"])
	if header:
		frappe.db.set_value(doc.doctype, doc.name, header, update_modified=True)

	child_dt = f"{doc.doctype} Item"
	child_meta = frappe.get_meta(child_dt) if frappe.db.exists("DocType", child_dt) else None
	for row in items:
		row_name = (row or {}).get("name")
		if not row_name or not frappe.db.exists(child_dt, row_name):
			continue
		child_updates = {}
		for field in ITEM_RETRY_FIELDS:
			if field not in row:
				continue
			if child_meta and not child_meta.has_field(field):
				continue
			child_updates[field] = row.get(field)
		if child_updates:
			frappe.db.set_value(child_dt, row_name, child_updates, update_modified=True)

	try:
		frappe.clear_document_cache(doc.doctype, doc.name)
	except Exception:
		pass
	return _send(name)


@frappe.whitelist()
def get_pos_fbr_status_bulk(names=None):
	"""Map invoice name → FBR number/status for XPOS order history (no QR)."""
	if isinstance(names, str):
		names = frappe.parse_json(names)
	if not isinstance(names, (list, tuple)):
		names = []

	out = {}
	for name in list(names)[:80]:
		name = (name or "").strip()
		if not name:
			continue
		try:
			doc = get_fbr_invoice_doc(name)
			_assert_can_read_invoice(doc)
			fbr_no = (
				(getattr(doc, "custom_fbr_invoice_no", None) or "").strip()
				or (getattr(doc, "fbr_invoice_number", None) or "").strip()
			)
			out[name] = {
				"ok": bool(fbr_no),
				"sales_invoice": doc.name,
				"doctype": doc.doctype,
				"fbr_invoice_no": fbr_no,
				"fbr_status": (getattr(doc, "custom_fbr_invoice_status", None) or "").strip(),
			}
		except Exception:
			continue
	return out


@frappe.whitelist()
def get_fbr_codes(name: str):
	"""Returns QR + Barcode data urls using custom_fbr_invoice_no."""
	doc = get_fbr_invoice_doc(name)
	_assert_can_read_invoice(doc)

	fbr_no = (
		(getattr(doc, "custom_fbr_invoice_no", None) or "").strip()
		or (getattr(doc, "fbr_invoice_number", None) or "").strip()
	)
	if not fbr_no:
		return {
			"ok": False,
			"message": "FBR Invoice No not found",
			"qr_data_url": "",
			"barcode_data_url": "",
		}

	try:
		from fbr_integration.print_barcodes import get_qr_and_barcode_data_uri

		data = get_qr_and_barcode_data_uri(fbr_no)
		return {
			"ok": True,
			"qr_data_url": data.get("qr") or "",
			"barcode_data_url": data.get("barcode") or "",
		}
	except Exception as e:
		frappe.log_error(title="FBR QR/Barcode generation failed", message=frappe.get_traceback())
		return {
			"ok": False,
			"message": f"QR/Barcode generator failed: {e}",
			"qr_data_url": "",
			"barcode_data_url": "",
		}
