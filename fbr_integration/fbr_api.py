import json
import re

import frappe
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def safe_float(val):
	try:
		num = float(val)
		return num if num >= 0 else 0
	except (TypeError, ValueError):
		return 0


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
			target[field] = safe_float(target.get(field)) + safe_float(item.get(field))

		# Keep the unit retail/notified value from the first line.
		if not target.get("fixedNotifiedValueOrRetailPrice"):
			target["fixedNotifiedValueOrRetailPrice"] = safe_float(
				item.get("fixedNotifiedValueOrRetailPrice")
			)

	return list(merged.values())


def sync_qr_fields(doc, qr_value):
	qr_val = (qr_value or "").strip()
	# keep old and new field names in sync for client installs
	if hasattr(doc, "custom_fbr_qr_code"):
		doc.custom_fbr_qr_code = qr_val
	if hasattr(doc, "custom_qr_code"):
		doc.custom_qr_code = qr_val


@frappe.whitelist()
def send_to_fbr_si(name: str):
	doc = frappe.get_doc("Sales Invoice", name)

	# Prevent duplicate submission
	if (doc.custom_fbr_invoice_no or "").strip():
		return {"success": False, "already_sent": True, "invoice_no": doc.custom_fbr_invoice_no}

	return send_invoice_to_fbr(doc)


def send_invoice_to_fbr(doc, method=None):
	settings = frappe.get_single("FBR Invoice Settings")

	if not settings.enabled:
		frappe.throw("FBR Integration Disabled")

	if settings.integration_type == "Sandbox":
		api_url = settings.sandbox_api_url
		token = (settings.sandbox_security_token or "").strip()
	else:
		api_url = settings.production_api_url
		token = (settings.production_security_token or "").strip()

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

	# Items
	items_list = []
	is_exempt_scenario = safe_str(doc.custom_scenario_id).strip().upper() == "SN006"
	for item in doc.items:
		sale_type_str = str(item.custom_sale_type or "").lower().replace(" ", "")
		extra_tax = extra_tax_value(item.custom_extra_tax, sale_type_str)

		if is_exempt_scenario:
			rate_val = "Exempt"
			sale_type_val = "Exempt goods"
			sales_tax_applicable = 0
			further_tax = 0
			extra_tax = 0
			total_values = safe_float(item.amount)
		else:
			rate_val = f"{safe_float(item.custom_sales_tax_rate):.2f}%"
			sale_type_val = safe_str(item.custom_sale_type)
			sales_tax_applicable = safe_float(item.custom_sales_tax)
			further_tax = safe_float(item.custom_further_tax)
			total_values = safe_float(item.custom_tax_inclusive_amount)

		items_list.append(
			{
				"hsCode": safe_str(item.custom_hs_code),
				"productDescription": safe_fbr_item_text(item.item_name),
				"rate": rate_val,
				"uoM": safe_fbr_item_text(item.custom_fbr_uom),
				"quantity": safe_float(item.qty),
				"totalValues": total_values,
				"valueSalesExcludingST": safe_float(item.amount),
				"fixedNotifiedValueOrRetailPrice": safe_float(item.rate),
				"salesTaxApplicable": sales_tax_applicable,
				"salesTaxWithheldAtSource": 0,
				"extraTax": extra_tax,
				"furtherTax": further_tax,
				"sroScheduleNo": safe_fbr_item_text(item.custom_sro_schedule_no),
				"fedPayable": 0,
				"discount": safe_float(item.discount_amount),
				"saleType": sale_type_val,
				"sroItemSerialNo": safe_fbr_item_text(item.custom_sro_item_sno),
			}
		)

	payload = {
		"invoiceType": safe_fbr_text(doc.custom_invoice_type),
		"invoiceDate": str(doc.posting_date),
		"sellerNTNCNIC": safe_str(doc.company_tax_id),
		"sellerBusinessName": safe_fbr_text(doc.company),
		"sellerAddress": safe_fbr_text(seller_address),
		"sellerProvince": safe_fbr_text(seller_province),
		"buyerNTNCNIC": safe_str(doc.tax_id),
		"buyerBusinessName": safe_fbr_text(doc.customer),
		"buyerAddress": safe_fbr_text(buyer_address),
		"buyerProvince": safe_fbr_text(buyer_province),
		"invoiceRefNo": safe_str(doc.name),
		"scenarioId": safe_str(doc.custom_scenario_id),
		"buyerRegistrationType": safe_fbr_text(doc.custom_tax_payer_type),
		"items": merge_fbr_items(items_list),
	}

	# Debug log — visible in bench logs to help diagnose FBR rejections
	frappe.log_error(
		title="FBR Outgoing Payload",
		message=json.dumps(payload, indent=2, ensure_ascii=False),
	)

	headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

	# Send
	resp = requests.post(api_url, headers=headers, json=payload, verify=False, timeout=90)

	# Always keep response in SI for audit (even if invalid)
	resp_text = resp.text or ""
	try:
		res_json = resp.json()
	except Exception:
		res_json = {"raw_response": resp_text}

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
		doc.custom_fbr_integration_type = settings.integration_type

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
