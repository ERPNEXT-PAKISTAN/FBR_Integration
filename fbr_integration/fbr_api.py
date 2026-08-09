import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
import requests
import urllib3
from frappe.utils import cint

from fbr_integration.fbr_payload_mapping import (
	apply_extra_item_payload_mappings,
	apply_extra_payload_mappings,
	resolve_payload_value,
)

# InsecureRequestWarning is disabled only when SSL Applied is off (verify=False).


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
	"""Round numeric values for FBR while keeping JSON numbers, not strings."""
	try:
		quant = Decimal("1").scaleb(-precision)
		return float(Decimal(str(val or 0)).quantize(quant, rounding=ROUND_HALF_UP))
	except (InvalidOperation, TypeError, ValueError):
		return 0


def fbr_money(val):
	"""FBR allows money/rate numeric fields up to 2 decimal places."""
	return rounded_float(val, 2)


def fbr_quantity(val):
	"""FBR allows quantity numeric fields up to 4 decimal places."""
	return rounded_float(val, 4)


def safe_str(val):
	"""Return string value, converting None/falsy to empty string."""
	if val is None:
		return ""
	return str(val)


def safe_fbr_text(val):
	"""Normalize text for strict third-party parsers.

	FBR endpoint can reject payloads when descriptive text contains control
	characters or escaped quotes. Keep values plain and compact.
	"""
	text = safe_str(val)
	text = text.replace("\r", " ").replace("\n", " ").replace("\t", " ")
	text = text.replace("\\", "/").replace('"', "")
	return " ".join(text.split())


def safe_fbr_item_text(val):
	"""Sanitize item-facing text fields for strict FBR validation.

	Keeps only basic characters commonly accepted by strict parsers.
	"""
	text = safe_fbr_text(val).replace(",", " ")
	text = re.sub(r"[^A-Za-z0-9./\- ]+", " ", text)
	return " ".join(text.split())


def normalize_registration_no(val):
	"""Keep FBR registration values alphanumeric, e.g. NTN/CNIC or C-prefixed registration."""
	return re.sub(r"[^A-Za-z0-9]+", "", safe_str(val)).upper()


def get_valid_seller_registration_no(doc):
	"""Return a normalized seller registration value or raise a precise local error."""
	raw_value = getattr(doc, "company_tax_id", "")
	registration_no = normalize_registration_no(raw_value)
	if len(registration_no) in (7, 13):
		return registration_no

	frappe.throw(
		"Company Tax ID must be a valid NTN or CNIC before sending to FBR. "
		f"Found '{safe_str(raw_value)}' on Sales Invoice {safe_str(doc.name)}. "
		"Use 7 digits for NTN or 13 digits for CNIC, without separators."
	)


def normalize_fbr_token(token):
	"""Return a clean bearer token value without leaking or duplicating prefixes."""
	token = safe_str(token).strip()
	if token.lower().startswith("bearer "):
		token = token[7:].strip()
	return token


def get_fbr_setting_password(settings, fieldname):
	"""Read Password fields safely across Frappe versions/custom Single storage."""
	try:
		value = settings.get_password(fieldname, raise_exception=False)
	except Exception:
		value = None
	return normalize_fbr_token(value or getattr(settings, fieldname, ""))


def get_pos_credential_row(settings, pos_profile=None):
	"""Return the enabled POS credential row for a POS Profile, if configured."""
	pos_profile = safe_str(pos_profile).strip()
	if not pos_profile:
		return None
	for row in settings.get("pos_credentials") or []:
		if not cint(getattr(row, "enabled", 1)):
			continue
		if safe_str(row.pos_profile).strip() == pos_profile:
			return row
	return None


def get_pos_row_password(row, fieldname):
	"""Decrypt Password values stored on FBR POS Credential child rows."""
	if not row or not getattr(row, "name", None):
		return ""
	try:
		from frappe.utils.password import get_decrypted_password

		value = get_decrypted_password(
			"FBR POS Credential", row.name, fieldname=fieldname, raise_exception=False
		)
	except Exception:
		value = None
	if not value:
		value = getattr(row, fieldname, None)
	return normalize_fbr_token(value)


def get_fbr_connection_settings(settings, pos_profile=None):
	"""Resolve endpoint/token/(optional POS ID) for the active FBR environment.

	When ``pos_profile`` matches an enabled row in POS Credentials, that row's
	token / URL override / FBR POS ID are used. Otherwise fall back to the
	site-wide Sandbox/Production settings.
	"""
	integration_type = safe_str(settings.integration_type).strip()
	is_sandbox = integration_type == "Sandbox"

	if is_sandbox:
		api_url = safe_str(settings.sandbox_api_url).strip()
		token = get_fbr_setting_password(settings, "sandbox_security_token")
	else:
		api_url = safe_str(settings.production_api_url).strip()
		token = get_fbr_setting_password(settings, "production_security_token")

	fbr_pos_id = ""
	row = get_pos_credential_row(settings, pos_profile)
	if row:
		fbr_pos_id = safe_str(row.fbr_pos_id).strip()
		if is_sandbox:
			row_token = get_pos_row_password(row, "sandbox_security_token")
			row_url = safe_str(row.sandbox_api_url).strip()
		else:
			row_token = get_pos_row_password(row, "production_security_token")
			row_url = safe_str(row.production_api_url).strip()
		if row_token:
			token = row_token
		if row_url:
			api_url = row_url

	return integration_type, is_sandbox, api_url, token, fbr_pos_id


def tokens_match(settings):
	"""Compare configured sandbox/production token values without exposing them."""
	sandbox_token = get_fbr_setting_password(settings, "sandbox_security_token")
	production_token = get_fbr_setting_password(settings, "production_security_token")
	return bool(sandbox_token and production_token and sandbox_token == production_token)


def extra_tax_value(val, sale_type_str):
	reduced_types = ("goodsatreducedrate", "reducedrate", "rr")
	if sale_type_str in reduced_types:
		return 0
	try:
		num = float(val)
		if num <= 0:
			return 0
		return num
	except (TypeError, ValueError):
		return 0


def is_reduced_rate_scenario(scenario_id):
	"""Return True for FBR scenarios where extra tax must not be sent."""
	return safe_str(scenario_id).strip().upper() in {"SN005", "SN009", "SN028"}


def format_extra_tax_for_payload(extra_tax, scenario_id):
	"""Return blank extraTax for scenarios where FBR rejects even numeric zero."""
	scenario = safe_str(scenario_id).strip().upper()
	if scenario in {"SN005", "SN006", "SN007", "SN009", "SN028"}:
		return ""
	return safe_float(extra_tax)


def merge_fbr_items(items):
	"""Merge duplicate item lines for strict FBR validation.

	Some FBR responses flag repeated lines as duplicate even within one invoice.
	Merge by item identity fields and sum numeric amounts.
	"""
	merged = {}
	numeric_sum_fields = (
		"quantity",
		"totalValues",
		"valueSalesExcludingST",
		"salesTaxApplicable",
		"salesTaxWithheldAtSource",
		"extraTax",
		"furtherTax",
		"fedPayable",
		"discount",
	)

	for item in items:
		key = (
			item.get("hsCode", ""),
			item.get("productDescription", ""),
			item.get("rate", ""),
			item.get("uoM", ""),
			item.get("saleType", ""),
			item.get("sroScheduleNo", ""),
			item.get("sroItemSerialNo", ""),
		)

		if key not in merged:
			merged[key] = dict(item)
			continue

		target = merged[key]
		for field in numeric_sum_fields:
			if field == "extraTax" and target.get(field) == "" and item.get(field) == "":
				target[field] = ""
				continue
			target[field] = safe_float(target.get(field)) + safe_float(item.get(field))

		# Keep the unit retail/notified value from the first line.
		if not target.get("fixedNotifiedValueOrRetailPrice"):
			target["fixedNotifiedValueOrRetailPrice"] = safe_float(
				item.get("fixedNotifiedValueOrRetailPrice")
			)

	return list(merged.values())


def normalize_fbr_item_numbers(item):
	"""Apply FBR decimal precision limits to one item payload."""
	normalized = dict(item)
	for field in (
		"totalValues",
		"valueSalesExcludingST",
		"fixedNotifiedValueOrRetailPrice",
		"salesTaxApplicable",
		"salesTaxWithheldAtSource",
		"extraTax",
		"furtherTax",
		"fedPayable",
		"discount",
	):
		if field == "extraTax" and normalized.get(field) == "":
			continue
		normalized[field] = fbr_money(normalized.get(field))
	normalized["quantity"] = fbr_quantity(normalized.get("quantity"))
	return normalized


def parse_fbr_response(response):
	"""Parse FBR responses, including sandbox responses with trailing commas."""
	response_text = response.text or ""
	try:
		return response.json()
	except Exception:
		pass

	try:
		cleaned = re.sub(r",\s*([}\]])", r"\1", response_text)
		return json.loads(cleaned)
	except Exception:
		return {"raw_response": response_text}


def normalize_sro_fields_for_scenario(scenario_id, sro_schedule_no, sro_item_sno):
	"""Apply scenario-specific SRO normalization for FBR payload."""
	scenario = safe_str(scenario_id).strip().upper()
	sro_no = safe_str(sro_schedule_no).strip()
	sro_item = safe_str(sro_item_sno).strip()

	if scenario == "SN007":
		normalized_sro = " ".join(sro_no.lower().split())
		if not normalized_sro or normalized_sro.startswith("eighth schedule"):
			sro_no = "6th Schd Table I"
		if not sro_item:
			sro_item = "1"

	return sro_no, sro_item


def normalize_sale_type_for_scenario(scenario_id, sale_type):
	"""Apply scenario-specific sale type normalization for FBR payload."""
	scenario = safe_str(scenario_id).strip().upper()
	sale_type_text = safe_str(sale_type).strip()
	if scenario == "SN024":
		normalized = " ".join(sale_type_text.lower().split())
		if normalized in {
			"goods as per sro.297(i)/2023",
			"goods as per sro 297(i)/2023",
			"goods as per sro.297(|)/2023",
		}:
			return "Goods as per SRO.297(|)/2023"
	return sale_type_text


def sn024_sale_type_candidates(current_sale_type):
	"""Return ordered SN024 saleType candidates for strict gateway matching."""
	candidates = [
		safe_str(current_sale_type).strip(),
		"Goods as per SRO.297(|)/2023",
		"Goods as per SRO.297(I)/2023",
		"Goods at standard rate (default)",
		"Goods Sold that are Listed in SRO 297(1)/2023",
		"Goods as per SRO 297(I)/2023",
	]

	seen = set()
	ordered = []
	for value in candidates:
		if not value or value in seen:
			continue
		seen.add(value)
		ordered.append(value)

	return ordered


def sync_qr_fields(doc, qr_value):
	qr_val = (qr_value or "").strip()
	# keep old and new field names in sync for client installs
	if hasattr(doc, "custom_fbr_qr_code"):
		doc.custom_fbr_qr_code = qr_val
	if hasattr(doc, "custom_qr_code"):
		doc.custom_qr_code = qr_val


def persist_fbr_response_fields(doc):
	"""Persist FBR response fields even when a later throw rolls back the document save."""
	fields = {}
	for fieldname in (
		"custom_fbr_digital_invoice_response",
		"custom_fbr_integration_type",
		"custom_fbr_invoice_status",
		"custom_fbr_invoice_status_code",
		"custom_fbr_invoice_error",
		"custom_fbr_invoice_error_code",
		"custom_fbr_submission_time",
		"custom_fbr_invoice_no",
		"custom_fbr_invoice_item_no",
		"custom_fbr_invoice_statuses",
		"custom_fbr_qr_code",
		"custom_qr_code",
		"custom_fbr_responsed",
	):
		if hasattr(doc, fieldname):
			fields[fieldname] = getattr(doc, fieldname)

	if fields:
		frappe.db.set_value(doc.doctype, doc.name, fields, update_modified=False)
		frappe.db.commit()


def get_source_invoice_no_for_return(doc):
	"""Resolve original *FBR* invoice number for Sales Return / Credit Note.

	FBR DI API field invoiceRefNo must be the FBR invoice number of the original
	Sale Invoice (e.g. 7327556DI1744111990654), NOT the ERPNext Sales Invoice name.
	"""
	# 1) Explicit FBR Source Invoice No on the return
	if hasattr(doc, "custom_fbr_source_invoice_no"):
		manual = safe_str(getattr(doc, "custom_fbr_source_invoice_no", "")).strip()
		if manual:
			return manual

	# 2) From Return Against → original SI's custom_fbr_invoice_no
	return_against = safe_str(getattr(doc, "return_against", "")).strip()
	if return_against:
		try:
			source_fbr_no = frappe.db.get_value(
				"Sales Invoice", return_against, "custom_fbr_invoice_no"
			)
			if source_fbr_no:
				return safe_str(source_fbr_no).strip()
		except Exception:
			pass

	# 3) Parsed from remarks
	parsed_source, _ = _parse_return_meta_from_remarks(getattr(doc, "remarks", ""))
	return parsed_source


def _parse_return_meta_from_remarks(remarks):
	"""Extract optional source invoice and reason from remarks text.

	Supported examples:
	- FBR Source Invoice No: 1953701DI1KLDKA962915
	- Source Invoice No: 1953701DI1KLDKA962915 | Reason: Damaged goods return
	"""
	text = safe_str(remarks)
	if not text:
		return "", ""

	source_match = re.search(
		r"(?:fbr\s*source\s*invoice\s*no|source\s*invoice\s*no)\s*[:#\-]\s*([A-Za-z0-9\-_/]+)",
		text,
		flags=re.IGNORECASE,
	)
	reason_match = re.search(
		r"(?:reason)\s*[:#\-]\s*(.+)$",
		text,
		flags=re.IGNORECASE,
	)

	source = safe_str(source_match.group(1)).strip() if source_match else ""
	reason = safe_str(reason_match.group(1)).strip() if reason_match else ""
	return source, reason


def get_manual_source_invoice_no_for_return(doc):
	"""Resolve manual source FBR invoice number for direct return flow."""
	return get_source_invoice_no_for_return(doc)


def enforce_return_invoice_type(doc, method=None):
	"""Ensure return invoices always use Credit Note type (FBR invoiceType)."""
	if cint(getattr(doc, "is_return", 0)) != 1:
		return

	invoice_type = safe_str(getattr(doc, "custom_invoice_type", "")).strip().lower()
	if invoice_type != "credit note" and hasattr(doc, "custom_invoice_type"):
		doc.custom_invoice_type = "Credit Note"

	# Keep custom_fbr_source_invoice_no filled from return_against when possible
	if hasattr(doc, "custom_fbr_source_invoice_no") and not safe_str(
		getattr(doc, "custom_fbr_source_invoice_no", "")
	).strip():
		source = get_source_invoice_no_for_return(doc)
		if source:
			doc.custom_fbr_source_invoice_no = source


def log_fbr_exchange(doc_name, attempt_label, payload, response):
	"""Store complete FBR request/response exchange for troubleshooting."""
	response_text = safe_str(getattr(response, "text", ""))
	response_status = getattr(response, "status_code", None)

	try:
		response_json = response.json()
	except Exception:
		response_json = None

	log_body = {
		"invoice": safe_str(doc_name),
		"attempt": safe_str(attempt_label),
		"request": payload,
		"response_status": response_status,
		"response_json": response_json,
		"response_raw": response_text,
	}

	frappe.log_error(
		title=f"FBR Exchange [{attempt_label}] {safe_str(doc_name)}",
		message=json.dumps(log_body, indent=2, ensure_ascii=False),
	)


def get_return_reason(doc):
	"""Resolve reason for return payload (debit note requirement)."""
	if hasattr(doc, "custom_fbr_reason"):
		reason = safe_fbr_text(getattr(doc, "custom_fbr_reason", ""))
		if reason:
			return reason

	_, parsed_reason = _parse_return_meta_from_remarks(getattr(doc, "remarks", ""))
	if parsed_reason:
		return safe_fbr_text(parsed_reason)

	remarks = safe_fbr_text(getattr(doc, "remarks", ""))
	return remarks or "Sales Return"


def assert_can_send_invoice_to_fbr(doc):
	"""Require write access on the Sales Invoice before calling FBR."""
	if frappe.session.user == "Administrator":
		return
	if not frappe.has_permission("Sales Invoice", "write", doc=doc):
		frappe.throw(
			"You do not have permission to send this Sales Invoice to FBR.",
			frappe.PermissionError,
			title="Not Permitted",
		)


@frappe.whitelist()
def send_to_fbr_si(name: str):
	if not name:
		frappe.throw("Sales Invoice name is required.")

	doc = frappe.get_doc("Sales Invoice", name)
	assert_can_send_invoice_to_fbr(doc)

	# Enforce submission requirement in Production mode
	settings = frappe.get_single("FBR Invoice Settings")
	_, is_sandbox, _, _, _ = get_fbr_connection_settings(settings, getattr(doc, 'pos_profile', None))
	if not is_sandbox and doc.docstatus != 1:
		frappe.throw(
			"Invoice must be submitted before sending to FBR in Production mode.",
			title="Not Submitted",
		)

	# Prevent duplicate submission
	if (doc.custom_fbr_invoice_no or "").strip():
		return {"success": False, "already_sent": True, "invoice_no": doc.custom_fbr_invoice_no}

	return send_invoice_to_fbr(doc)


def send_invoice_to_fbr(doc, method=None):
	enforce_return_invoice_type(doc)

	settings = frappe.get_single("FBR Invoice Settings")

	if not settings.enabled:
		frappe.throw("FBR Integration Disabled")

	pos_profile = safe_str(getattr(doc, 'pos_profile', '')).strip()
	integration_type, is_sandbox, api_url, token, fbr_pos_id = get_fbr_connection_settings(
		settings, pos_profile=pos_profile
	)

	if not api_url:
		frappe.throw("FBR API URL missing in settings")
	if not token:
		frappe.throw("FBR Token missing in settings")

	# Address
	seller_address = ""
	seller_province = ""
	if doc.company_address:
		addr = frappe.get_doc("Address", doc.company_address)
		seller_address = f"{addr.address_line1}, {addr.city}"
		seller_province = addr.state or ""

	buyer_address = ""
	buyer_province = ""
	if doc.customer_address:
		addr = frappe.get_doc("Address", doc.customer_address)
		buyer_address = f"{addr.address_line1}, {addr.city}"
		buyer_province = addr.state or ""

	is_return_invoice = cint(getattr(doc, "is_return", 0)) == 1
	if is_return_invoice:
		enforce_return_invoice_type(doc)

	# FBR DI: for Credit/Debit Note, invoiceRefNo = original FBR invoice number.
	# For Sale Invoice, invoiceRefNo must be empty.
	fbr_invoice_ref_no = ""
	if is_return_invoice:
		fbr_invoice_ref_no = get_source_invoice_no_for_return(doc)
		if not fbr_invoice_ref_no:
			frappe.throw(
				"Sales Return / Credit Note requires the original FBR Invoice No. "
				"Set Return Against on a Sales Invoice that was already sent to FBR, "
				"or enter FBR Source Invoice No.",
				title="FBR invoiceRefNo missing",
			)
		# Reject ERP names mistakenly used as FBR reference (FBR nos contain "DI").
		if "DI" not in fbr_invoice_ref_no.upper() and safe_str(
			getattr(doc, "return_against", "")
		).strip() == fbr_invoice_ref_no:
			frappe.throw(
				f"Original invoice {fbr_invoice_ref_no} has no FBR Invoice No yet. "
				"Send the original Sale Invoice to FBR first, then create the return.",
				title="Original invoice not reported to FBR",
			)

	# Items
	items_list = []
	scenario_id = safe_str(doc.custom_scenario_id).strip().upper()
	seller_registration_no = get_valid_seller_registration_no(doc)
	is_reduced_rate = is_reduced_rate_scenario(scenario_id)
	is_exempt_scenario = scenario_id == "SN006"
	is_zero_rated_scenario = scenario_id == "SN007"
	num = safe_abs_float if is_return_invoice else safe_float
	for item in doc.items:
		sale_type_str = str(item.custom_sale_type or "").lower().replace(" ", "")
		extra_tax = extra_tax_value(item.custom_extra_tax, sale_type_str)
		if is_reduced_rate:
			extra_tax = 0

		if is_exempt_scenario:
			rate_val = "Exempt"
			sale_type_val = "Exempt goods"
			sales_tax_applicable = 0
			further_tax = 0
			extra_tax = 0
			total_values = num(item.amount)
		elif is_zero_rated_scenario:
			rate_val = "0%"
			sale_type_val = "Goods at zero-rate"
			sales_tax_applicable = 0
			further_tax = 0
			extra_tax = 0
			total_values = num(item.amount)
		else:
			rate_val = f"{num(item.custom_sales_tax_rate):.2f}%"
			sale_type_val = normalize_sale_type_for_scenario(scenario_id, item.custom_sale_type)
			sales_tax_applicable = num(item.custom_sales_tax)
			further_tax = num(item.custom_further_tax)
			total_values = num(item.custom_tax_inclusive_amount)

		sro_schedule_no_val, sro_item_sno_val = normalize_sro_fields_for_scenario(
			scenario_id,
			item.custom_sro_schedule_no,
			item.custom_sro_item_sno,
		)

		value_sales_excluding_st = num(item.amount)
		if value_sales_excluding_st <= 0:
			value_sales_excluding_st = num((safe_float(item.qty) or 0) * (safe_float(item.rate) or 0))

		if value_sales_excluding_st <= 0:
			frappe.throw(
				f"Invalid item value for FBR on row {item.idx} ({safe_str(item.item_code) or safe_str(item.item_name)}). "
				"Value Sales Excluding ST must be greater than zero."
			)

		total_values = num(item.custom_tax_inclusive_amount)
		if total_values <= 0:
			total_values = value_sales_excluding_st + sales_tax_applicable + further_tax + num(extra_tax)

		item_payload = {
			"hsCode": resolve_payload_value(
				"hsCode", safe_str(item.custom_hs_code), doc, item=item, section="Item"
			),
			"productDescription": resolve_payload_value(
				"productDescription",
				safe_fbr_item_text(item.item_name),
				doc,
				item=item,
				section="Item",
			),
			"rate": resolve_payload_value("rate", rate_val, doc, item=item, section="Item"),
			"uoM": resolve_payload_value(
				"uoM", safe_fbr_text(item.custom_fbr_uom), doc, item=item, section="Item"
			),
			"quantity": resolve_payload_value("quantity", num(item.qty), doc, item=item, section="Item"),
			"totalValues": resolve_payload_value("totalValues", total_values, doc, item=item, section="Item"),
			"valueSalesExcludingST": resolve_payload_value(
				"valueSalesExcludingST",
				value_sales_excluding_st,
				doc,
				item=item,
				section="Item",
			),
			"fixedNotifiedValueOrRetailPrice": resolve_payload_value(
				"fixedNotifiedValueOrRetailPrice",
				num(item.rate),
				doc,
				item=item,
				section="Item",
			),
			"salesTaxApplicable": resolve_payload_value(
				"salesTaxApplicable",
				sales_tax_applicable,
				doc,
				item=item,
				section="Item",
			),
			"salesTaxWithheldAtSource": resolve_payload_value(
				"salesTaxWithheldAtSource",
				num(getattr(item, "custom_sales_tax_withheld_at_source", None) or 0),
				doc,
				item=item,
				section="Item",
			),
			"extraTax": resolve_payload_value(
				"extraTax",
				format_extra_tax_for_payload(extra_tax, scenario_id),
				doc,
				item=item,
				section="Item",
			),
			"furtherTax": resolve_payload_value("furtherTax", further_tax, doc, item=item, section="Item"),
			"sroScheduleNo": resolve_payload_value(
				"sroScheduleNo", sro_schedule_no_val, doc, item=item, section="Item"
			),
			"fedPayable": resolve_payload_value("fedPayable", 0, doc, item=item, section="Item"),
			"discount": resolve_payload_value(
				"discount", num(item.discount_amount), doc, item=item, section="Item"
			),
			"saleType": resolve_payload_value("saleType", sale_type_val, doc, item=item, section="Item"),
			"sroItemSerialNo": resolve_payload_value(
				"sroItemSerialNo", sro_item_sno_val, doc, item=item, section="Item"
			),
		}
		apply_extra_item_payload_mappings(item_payload, doc, item, existing_fields=item_payload.keys())

		items_list.append(item_payload)

	# Default invoiceType: Sale Invoice, or Credit Note when is_return.
	default_invoice_type = (
		"Credit Note"
		if is_return_invoice
		else (safe_fbr_text(doc.custom_invoice_type) or "Sale Invoice")
	)
	if is_return_invoice:
		default_invoice_type = safe_fbr_text(doc.custom_invoice_type) or "Credit Note"

	payload = {
		"invoiceType": resolve_payload_value("invoiceType", default_invoice_type, doc),
		"invoiceDate": resolve_payload_value("invoiceDate", str(doc.posting_date), doc),
		"sellerNTNCNIC": resolve_payload_value("sellerNTNCNIC", seller_registration_no, doc),
		"sellerBusinessName": resolve_payload_value("sellerBusinessName", safe_fbr_text(doc.company), doc),
		"sellerAddress": resolve_payload_value("sellerAddress", safe_fbr_text(seller_address), doc),
		"sellerProvince": resolve_payload_value("sellerProvince", safe_fbr_text(seller_province), doc),
		"buyerNTNCNIC": resolve_payload_value("buyerNTNCNIC", normalize_registration_no(doc.tax_id), doc),
		"buyerBusinessName": resolve_payload_value("buyerBusinessName", safe_fbr_text(doc.customer), doc),
		"buyerAddress": resolve_payload_value("buyerAddress", safe_fbr_text(buyer_address), doc),
		"buyerProvince": resolve_payload_value("buyerProvince", safe_fbr_text(buyer_province), doc),
		# FBR official reference field (empty on Sale Invoice; original FBR no on Credit/Debit Note)
		"invoiceRefNo": resolve_payload_value("invoiceRefNo", fbr_invoice_ref_no, doc),
		"scenarioId": resolve_payload_value("scenarioId", safe_str(doc.custom_scenario_id), doc),
		"remarks": resolve_payload_value("remarks", safe_fbr_text(getattr(doc, "remarks", "")), doc),
		"buyerRegistrationType": resolve_payload_value(
			"buyerRegistrationType", safe_fbr_text(doc.custom_tax_payer_type), doc
		),
		"items": [normalize_fbr_item_numbers(item) for item in merge_fbr_items(items_list)],
	}

	if is_return_invoice:
		payload["reason"] = resolve_payload_value("reason", get_return_reason(doc), doc)

	apply_extra_payload_mappings(payload, doc, existing_fields=payload.keys())

	# Enforce FBR contract after optional mappings (do not allow ERP name in invoiceRefNo).
	if is_return_invoice:
		payload["invoiceType"] = safe_fbr_text(payload.get("invoiceType")) or "Credit Note"
		payload["invoiceRefNo"] = fbr_invoice_ref_no
		if not safe_str(payload.get("reason")).strip():
			payload["reason"] = get_return_reason(doc)
	else:
		# Sale Invoice: FBR samples use empty invoiceRefNo
		if safe_str(payload.get("invoiceRefNo")).strip() == safe_str(doc.name).strip():
			payload["invoiceRefNo"] = ""

	# Drop non-API legacy keys if a custom mapping reintroduced them.
	payload.pop("referencedInvoiceNo", None)
	payload.pop("sourceInvoiceNo", None)

	# Lightweight logger (avoid flooding Error Log with full payloads)
	frappe.logger("fbr_integration").info(
		"FBR outgoing payload for %s (%s chars)",
		doc.name,
		len(json.dumps(payload, ensure_ascii=False)),
	)

	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
	verify_ssl = bool(cint(getattr(settings, "ssl_applied", 0)))
	if not verify_ssl:
		urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

	def _post_payload(body):
		return requests.post(api_url, headers=headers, json=body, verify=verify_ssl, timeout=90)

	# Send
	resp = _post_payload(payload)
	log_fbr_exchange(doc.name, "initial", payload, resp)

	# Always keep response in SI for audit (even if invalid)
	resp_text = resp.text or ""
	res_json = parse_fbr_response(resp)

	# Some FBR gateway versions list Debit Note but still accept Credit Note;
	# if type is rejected (0003), retry once as Debit Note with same invoiceRefNo.
	if is_return_invoice:
		validation = res_json.get("validationResponse", {}) or {}
		error_code = validation.get("errorCode") or ""
		invoice_type = safe_str(payload.get("invoiceType")).strip().lower()
		if error_code == "0003" and invoice_type == "credit note":
			payload["invoiceType"] = "Debit Note"
			payload["invoiceRefNo"] = fbr_invoice_ref_no
			frappe.logger("fbr_integration").info(
				"FBR retry Debit Note for return %s (invoiceRefNo=%s)",
				doc.name,
				fbr_invoice_ref_no,
			)
			resp = _post_payload(payload)
			log_fbr_exchange(doc.name, "retry_debit_note", payload, resp)
			resp_text = resp.text or ""
			res_json = parse_fbr_response(resp)

	# SN024 can be strict on saleType labels even when scenario and SRO are valid.
	validation = res_json.get("validationResponse", {}) or {}
	error_code = validation.get("errorCode") or ""
	if scenario_id == "SN024" and error_code == "0204":
		base_sale_type = ""
		if payload.get("items"):
			base_sale_type = safe_str((payload.get("items") or [{}])[0].get("saleType")).strip()

		for attempt_idx, candidate in enumerate(sn024_sale_type_candidates(base_sale_type), start=1):
			if candidate == base_sale_type:
				continue

			retry_payload = dict(payload)
			retry_payload["items"] = [dict(it) for it in payload.get("items") or []]
			for item_payload in retry_payload["items"]:
				item_payload["saleType"] = candidate

			resp = _post_payload(retry_payload)
			log_fbr_exchange(doc.name, f"retry_sn024_sale_type_{attempt_idx}", retry_payload, resp)
			resp_text = resp.text or ""
			res_json = parse_fbr_response(resp)

			validation = res_json.get("validationResponse", {}) or {}
			if validation.get("statusCode") == "00":
				payload = retry_payload
				break

	# Store full response json always
	if hasattr(doc, "custom_fbr_digital_invoice_response"):
		doc.custom_fbr_digital_invoice_response = json.dumps(res_json, indent=2, ensure_ascii=False)

	validation = res_json.get("validationResponse", {}) or {}
	status_code = validation.get("statusCode", "")
	status = validation.get("status", "")
	error = validation.get("error", "")
	error_code = validation.get("errorCode", "")

	# Fill ALL your SI fields (if exist)
	if hasattr(doc, "custom_fbr_integration_type"):
		doc.custom_fbr_integration_type = integration_type

	if fbr_pos_id and hasattr(doc, "custom_fbr_pos_id"):
		doc.custom_fbr_pos_id = fbr_pos_id

	if hasattr(doc, "custom_fbr_invoice_status"):
		doc.custom_fbr_invoice_status = status
	if hasattr(doc, "custom_fbr_invoice_status_code"):
		doc.custom_fbr_invoice_status_code = status_code
	if hasattr(doc, "custom_fbr_invoice_error"):
		doc.custom_fbr_invoice_error = error
	if hasattr(doc, "custom_fbr_invoice_error_code"):
		doc.custom_fbr_invoice_error_code = error_code

	if hasattr(doc, "custom_fbr_submission_time"):
		doc.custom_fbr_submission_time = res_json.get("dated") or frappe.utils.now_datetime()

	# Invoice number
	invoice_no = (res_json.get("invoiceNumber") or "").strip()
	if invoice_no and hasattr(doc, "custom_fbr_invoice_no"):
		doc.custom_fbr_invoice_no = invoice_no

	# Item invoice numbers
	invoice_item_nos = []
	for st in validation.get("invoiceStatuses") or []:
		inv_no = st.get("invoiceNo")
		if inv_no:
			invoice_item_nos.append(inv_no)

	if hasattr(doc, "custom_fbr_invoice_item_no"):
		doc.custom_fbr_invoice_item_no = ", ".join(invoice_item_nos)

	if hasattr(doc, "custom_fbr_invoice_statuses"):
		doc.custom_fbr_invoice_statuses = json.dumps(
			validation.get("invoiceStatuses") or [], indent=2, ensure_ascii=False
		)

	# QR value field(s)
	sync_qr_fields(doc, invoice_no or "")

	# mark responsed
	if hasattr(doc, "custom_fbr_responsed"):
		doc.custom_fbr_responsed = "Success" if status_code == "00" else "Error"

	# Prefer field persistence; avoid blanket ignore_permissions saves.
	try:
		doc.flags.ignore_validate_update_after_submit = True
		doc.save()
	except frappe.PermissionError:
		persist_fbr_response_fields(doc)
	except Exception:
		persist_fbr_response_fields(doc)
	else:
		persist_fbr_response_fields(doc)

	# Raise if HTTP error
	if resp.status_code >= 400:
		fault = res_json.get("fault", {}) if isinstance(res_json, dict) else {}
		if resp.status_code == 401 and safe_str(fault.get("code")) == "900901":
			detail = (
				"FBR rejected the access token for Production. "
				"Update FBR Invoice Settings > Production Security Token with the live/production token."
			)
			if not is_sandbox and tokens_match(settings):
				detail += " The configured Production Security Token is currently the same as the Sandbox Security Token."

			frappe.throw(
				f"FBR Invalid Credentials\n\n{detail}\n\nFBR Response:\n{resp_text}",
				title="FBR Invalid Credentials",
			)
		frappe.throw(
			f"FBR HTTP Error\nStatus: {resp.status_code}\n\n{resp_text}",
			title="FBR HTTP Error",
		)

	# If FBR returned invalid
	if status_code != "00":
		frappe.throw(
			f"FBR Validation Failed\n\n{json.dumps(res_json, indent=2, ensure_ascii=False)}",
			title="FBR Validation Failed",
		)

	return {
		"success": True,
		"invoice_no": invoice_no,
		"dated": res_json.get("dated"),
		"validation": validation,
	}


def _should_auto_send_on_submit(doc) -> bool:
	"""Respect FBR Invoice Settings for POS / all-invoice auto send."""
	try:
		settings = frappe.get_single("FBR Invoice Settings")
	except Exception:
		return False

	if not getattr(settings, "enabled", 0):
		return False

	is_pos = int(getattr(doc, "is_pos", 0) or 0) or int(
		getattr(doc, "is_created_using_pos", 0) or 0
	)

	if is_pos and int(getattr(settings, "auto_send_pos_on_submit", 1) or 0):
		return True

	if int(getattr(settings, "auto_send_on_submit", 0) or 0):
		return True

	return False


def after_submit_invoice(doc, method=None):
	"""Auto-send when settings allow (POS by default; all SI optional)."""
	if not _should_auto_send_on_submit(doc):
		return

	# POS checkout must keep is_pos checked for ERPNext POS accounting.
	if getattr(doc, "pos_profile", None) and not int(getattr(doc, "is_pos", 0) or 0):
		frappe.db.set_value(doc.doctype, doc.name, "is_pos", 1, update_modified=False)
		doc.is_pos = 1

	if (getattr(doc, "custom_fbr_invoice_no", None) or "").strip():
		return

	# X POS built-in FBR (IMS) already fiscalized — do not double-send to DI API.
	if (getattr(doc, "fbr_invoice_number", None) or "").strip():
		return

	try:
		send_invoice_to_fbr(doc)
	except Exception:
		# Never block SI submit / POS checkout on FBR transport errors.
		frappe.log_error(
			title="FBR auto-send on submit failed",
			message=frappe.get_traceback(),
		)
		frappe.msgprint(
			"Sales Invoice submitted, but FBR auto-send failed. Use <b>Send to FBR</b> to retry.",
			indicator="orange",
			alert=True,
		)


@frappe.whitelist()
def import_pos_credentials_from_profiles():
	"""Import FBR POS ID / token rows from POS Profiles that have X POS FBR fields.

	Useful when migrating from X POS per-profile FBR settings into FBR Invoice Settings.
	Does not overwrite existing POS Credential rows for the same POS Profile.
	"""
	frappe.only_for("System Manager")
	if not frappe.db.exists("DocType", "POS Profile"):
		frappe.throw("POS Profile DocType not found")

	settings = frappe.get_single("FBR Invoice Settings")
	existing = {
		safe_str(row.pos_profile).strip()
		for row in (settings.get("pos_credentials") or [])
		if safe_str(row.pos_profile).strip()
	}

	profiles = frappe.get_all(
		"POS Profile",
		filters={"disabled": 0},
		fields=["name", "enable_fbr_integration", "fbr_pos_id", "fbr_environment", "fbr_api_url"],
	)
	# enable_fbr_integration / fbr_* may be missing if xpos not installed
	added = 0
	for profile in profiles:
		name = safe_str(profile.name).strip()
		if not name or name in existing:
			continue
		# Prefer profiles with xpos FBR enabled; otherwise skip empty IDs
		pos_id = ""
		try:
			pos_id = safe_str(frappe.db.get_value("POS Profile", name, "fbr_pos_id")).strip()
		except Exception:
			pos_id = ""
		if not pos_id:
			continue
		enabled = 0
		try:
			enabled = cint(frappe.db.get_value("POS Profile", name, "enable_fbr_integration"))
		except Exception:
			enabled = 0

		row = settings.append(
			"pos_credentials",
			{
				"enabled": 1 if enabled else 0,
				"pos_profile": name,
				"fbr_pos_id": pos_id,
			},
		)
		# Copy bearer token into the environment matching profile/settings
		token = ""
		try:
			token = normalize_fbr_token(
				frappe.get_doc("POS Profile", name).get_password("fbr_bearer_token") or ""
			)
		except Exception:
			token = ""
		env = ""
		try:
			env = safe_str(frappe.db.get_value("POS Profile", name, "fbr_environment")).strip()
		except Exception:
			env = ""
		api_url = ""
		try:
			api_url = safe_str(frappe.db.get_value("POS Profile", name, "fbr_api_url")).strip()
		except Exception:
			api_url = ""

		use_sandbox = (env or settings.integration_type or "").strip().lower() != "production"
		if token:
			if use_sandbox:
				row.sandbox_security_token = token
				if api_url:
					row.sandbox_api_url = api_url
			else:
				row.production_security_token = token
				if api_url:
					row.production_api_url = api_url
		added += 1
		existing.add(name)

	if added:
		settings.flags.ignore_permissions = True
		settings.save(ignore_permissions=True)
	return {"added": added, "total_rows": len(settings.get("pos_credentials") or [])}
