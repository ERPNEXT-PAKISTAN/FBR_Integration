import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import frappe
import requests
import urllib3
from frappe.utils import cint

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


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
	"""Keep only digits for FBR registration values like NTN/CNIC."""
	return re.sub(r"\D+", "", safe_str(val))


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


def get_fbr_connection_settings(settings):
	"""Resolve endpoint/token for the active FBR environment."""
	integration_type = safe_str(settings.integration_type).strip()
	is_sandbox = integration_type == "Sandbox"

	if is_sandbox:
		api_url = safe_str(settings.sandbox_api_url).strip()
		token = get_fbr_setting_password(settings, "sandbox_security_token")
	else:
		api_url = safe_str(settings.production_api_url).strip()
		token = get_fbr_setting_password(settings, "production_security_token")

	return integration_type, is_sandbox, api_url, token


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
	return safe_str(scenario_id).strip().upper() in {"SN005", "SN009"}


def format_extra_tax_for_payload(extra_tax, scenario_id):
	"""Return blank extraTax for scenarios where FBR rejects even numeric zero."""
	scenario = safe_str(scenario_id).strip().upper()
	if scenario in {"SN005", "SN006", "SN007", "SN009"}:
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


def get_source_invoice_no_for_return(doc):
	"""Resolve source invoice number for Sales Return payloads."""
	return_against = safe_str(getattr(doc, "return_against", "")).strip()
	if not return_against:
		return ""

	try:
		source_fbr_no = frappe.db.get_value("Sales Invoice", return_against, "custom_fbr_invoice_no")
		if source_fbr_no:
			return safe_str(source_fbr_no).strip()
	except Exception:
		pass

	# Fallback to ERP invoice id if FBR invoice no is not present.
	return return_against


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
	"""Resolve manual source invoice number for direct return flow."""
	if hasattr(doc, "custom_fbr_source_invoice_no"):
		manual = safe_str(getattr(doc, "custom_fbr_source_invoice_no", "")).strip()
		if manual:
			return manual

	parsed_source, _ = _parse_return_meta_from_remarks(getattr(doc, "remarks", ""))
	return parsed_source


def enforce_return_invoice_type(doc, method=None):
	"""Ensure return invoices always use Credit Note type."""
	if cint(getattr(doc, "is_return", 0)) != 1:
		return

	invoice_type = safe_str(getattr(doc, "custom_invoice_type", "")).strip().lower()
	if invoice_type != "credit note" and hasattr(doc, "custom_invoice_type"):
		doc.custom_invoice_type = "Credit Note"


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


@frappe.whitelist()
def send_to_fbr_si(name: str):
	doc = frappe.get_doc("Sales Invoice", name)

	# Enforce submission requirement in Production mode
	settings = frappe.get_single("FBR Invoice Settings")
	_, is_sandbox, _, _ = get_fbr_connection_settings(settings)
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

	integration_type, is_sandbox, api_url, token = get_fbr_connection_settings(settings)

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
	is_credit_note_return = (
		is_return_invoice
		and safe_str(getattr(doc, "custom_invoice_type", "")).strip().lower() == "credit note"
	)
	manual_source_invoice_no = get_manual_source_invoice_no_for_return(doc)

	if (
		is_credit_note_return
		and not safe_str(getattr(doc, "return_against", "")).strip()
		and not manual_source_invoice_no
	):
		frappe.throw(
			"Sales Return Credit Note requires one source reference: "
			"either Return Against (original Sales Invoice) or FBR Source Invoice No."
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

		items_list.append(
			{
				"hsCode": safe_str(item.custom_hs_code),
				"productDescription": safe_fbr_item_text(item.item_name),
				"rate": rate_val,
				"uoM": safe_fbr_text(item.custom_fbr_uom),
				"quantity": num(item.qty),
				"totalValues": total_values,
				"valueSalesExcludingST": value_sales_excluding_st,
				"fixedNotifiedValueOrRetailPrice": num(item.rate),
				"salesTaxApplicable": sales_tax_applicable,
				"salesTaxWithheldAtSource": 0,
				"extraTax": format_extra_tax_for_payload(extra_tax, scenario_id),
				"furtherTax": further_tax,
				"sroScheduleNo": sro_schedule_no_val,
				"fedPayable": 0,
				"discount": num(item.discount_amount),
				"saleType": sale_type_val,
				"sroItemSerialNo": sro_item_sno_val,
			}
		)

	payload = {
		"invoiceType": safe_fbr_text(doc.custom_invoice_type),
		"invoiceDate": str(doc.posting_date),
		"sellerNTNCNIC": seller_registration_no,
		"sellerBusinessName": safe_fbr_text(doc.company),
		"sellerAddress": safe_fbr_text(seller_address),
		"sellerProvince": safe_fbr_text(seller_province),
		"buyerNTNCNIC": safe_str(doc.tax_id),
		"buyerBusinessName": safe_fbr_text(doc.customer),
		"buyerAddress": safe_fbr_text(buyer_address),
		"buyerProvince": safe_fbr_text(buyer_province),
		"invoiceRefNo": safe_str(doc.name),
		"scenarioId": safe_str(doc.custom_scenario_id),
		"referencedInvoiceNo": safe_str(doc.name),
		"sourceInvoiceNo": safe_str(doc.name),
		"reason": "",
		"remarks": safe_fbr_text(getattr(doc, "remarks", "")),
		"buyerRegistrationType": safe_fbr_text(doc.custom_tax_payer_type),
		"items": [normalize_fbr_item_numbers(item) for item in merge_fbr_items(items_list)],
	}

	if is_credit_note_return:
		payload["reason"] = get_return_reason(doc)
		source_invoice_no = get_source_invoice_no_for_return(doc) or manual_source_invoice_no
		if not source_invoice_no:
			frappe.throw(
				"Unable to resolve source invoice number for Credit Note. "
				"Set Return Against or provide FBR Source Invoice No."
			)
		payload["referencedInvoiceNo"] = safe_str(source_invoice_no)
		payload["sourceInvoiceNo"] = source_invoice_no

	# Debug log — visible in bench logs to help diagnose FBR rejections
	frappe.log_error(
		title="FBR Outgoing Payload",
		message=json.dumps(payload, indent=2, ensure_ascii=False),
	)

	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

	def _post_payload(body):
		return requests.post(api_url, headers=headers, json=body, verify=False, timeout=90)

	# Send
	resp = _post_payload(payload)
	log_fbr_exchange(doc.name, "initial", payload, resp)

	# Always keep response in SI for audit (even if invalid)
	resp_text = resp.text or ""
	res_json = parse_fbr_response(resp)

	# Some FBR setups reject Credit Note label but accept Debit Note for returns.
	if is_credit_note_return:
		validation = res_json.get("validationResponse", {}) or {}
		error_code = validation.get("errorCode") or ""
		invoice_type = safe_str(payload.get("invoiceType")).strip().lower()
		if error_code == "0003" and invoice_type == "credit note":
			payload["invoiceType"] = "Debit Note"
			frappe.log_error(
				title="FBR Outgoing Payload Retry",
				message=json.dumps(payload, indent=2, ensure_ascii=False),
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

	doc.save(ignore_permissions=True)

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
		frappe.throw(f"? FBR HTTP Error\nStatus: {resp.status_code}\n\n{resp_text}")

	# If FBR returned invalid
	if status_code != "00":
		frappe.throw(f"? FBR Validation Failed\n\n{json.dumps(res_json, indent=2, ensure_ascii=False)}")

	return {
		"success": True,
		"invoice_no": invoice_no,
		"dated": res_json.get("dated"),
		"validation": validation,
	}


def after_submit_invoice(doc, method=None):
	send_invoice_to_fbr(doc)
