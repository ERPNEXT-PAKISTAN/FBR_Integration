import frappe
import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def safe_float(val):
    try:
        num = float(val)
        return num if num >= 0 else 0
    except (TypeError, ValueError):
        return 0


def extra_tax_value(val, sale_type_str):
    reduced_types = ("goodsatreducedrate", "reducedrate", "rr")
    if sale_type_str in reduced_types:
        return ""
    try:
        num = float(val)
        if num <= 0:
            return ""
        return num
    except (TypeError, ValueError):
        return ""


@frappe.whitelist()
def send_to_fbr_si(name: str):
    doc = frappe.get_doc("Sales Invoice", name)

    # Prevent duplicate submission
    if (doc.custom_fbr_invoice_no or "").strip():
        return {
            "success": False,
            "already_sent": True,
            "invoice_no": doc.custom_fbr_invoice_no
        }

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
    for item in doc.items:
        sale_type_str = str(item.custom_sale_type or "").lower().replace(" ", "")
        extra_tax = extra_tax_value(item.custom_extra_tax, sale_type_str)

        if doc.custom_scenario_id == "SN006":
            rate_val = "Exempt"
        else:
            rate_val = "{:.2f}%".format(safe_float(item.custom_sales_tax_rate))

        items_list.append({
            "hsCode": item.custom_hs_code,
            "productDescription": item.item_name,
            "rate": rate_val,
            "uoM": item.custom_fbr_uom,
            "quantity": safe_float(item.qty),
            "totalValues": safe_float(item.custom_tax_inclusive_amount),
            "valueSalesExcludingST": safe_float(item.amount),
            "fixedNotifiedValueOrRetailPrice": safe_float(item.rate),
            "salesTaxApplicable": safe_float(item.custom_sales_tax),
            "salesTaxWithheldAtSource": 0,
            "extraTax": extra_tax,
            "furtherTax": safe_float(item.custom_further_tax),
            "sroScheduleNo": item.custom_sro_schedule_no,
            "fedPayable": 0,
            "discount": safe_float(item.discount_amount),
            "saleType": item.custom_sale_type,
            "sroItemSerialNo": item.custom_sro_item_sno
        })

    payload = {
        "invoiceType": doc.custom_invoice_type,
        "invoiceDate": str(doc.posting_date),
        "sellerNTNCNIC": (doc.company_tax_id or "").strip(),
        "sellerBusinessName": doc.company,
        "sellerAddress": seller_address,
        "sellerProvince": seller_province,
        "buyerNTNCNIC": (doc.tax_id or "").strip(),
        "buyerBusinessName": doc.customer,
        "buyerAddress": buyer_address,
        "buyerProvince": buyer_province,
        "invoiceRefNo": doc.name,
        "scenarioId": doc.custom_scenario_id,
        "buyerRegistrationType": doc.custom_tax_payer_type,
        "items": items_list
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

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
    for st in (validation.get("invoiceStatuses") or []):
        inv_no = st.get("invoiceNo")
        if inv_no:
            invoice_item_nos.append(inv_no)

    if hasattr(doc, "custom_fbr_invoice_item_no"):
        doc.custom_fbr_invoice_item_no = ", ".join(invoice_item_nos)

    if hasattr(doc, "custom_fbr_invoice_statuses"):
        doc.custom_fbr_invoice_statuses = json.dumps(validation.get("invoiceStatuses") or [], indent=2, ensure_ascii=False)

    # QR value field (if you store invoice number for QR)
    if hasattr(doc, "custom_fbr_qr_code"):
        doc.custom_fbr_qr_code = invoice_no or ""

    # mark responsed
    if hasattr(doc, "custom_fbr_responsed"):
        doc.custom_fbr_responsed = "Success" if status_code == "00" else "Error"

    doc.save(ignore_permissions=True)

    # Raise if HTTP error
    if resp.status_code >= 400:
        frappe.throw(f"? FBR HTTP Error\nStatus: {resp.status_code}\n\n{resp_text}")

    # If FBR returned invalid
    if status_code != "00":
        frappe.throw(
            f"? FBR Validation Failed\n\n{json.dumps(res_json, indent=2, ensure_ascii=False)}"
        )

    return {
        "success": True,
        "invoice_no": invoice_no,
        "dated": res_json.get("dated"),
        "validation": validation
    }


def after_submit_invoice(doc, method=None):
    send_invoice_to_fbr(doc)