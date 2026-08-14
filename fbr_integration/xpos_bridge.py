"""XPOS bridge: works with stock XPOS from any source.

Server auto-send / custom fields already run on Sales Invoice and POS Invoice.
This module adds the XPOS SPA UI and thermal-receipt FBR block without forking XPOS:

- after_request injects xpos_fbr.js into /xpos HTML
- jinja helpers render FBR number + QR on print when sent
- migrate patches XPOS / POS Profile print formats
"""

from __future__ import annotations

import frappe
from frappe.utils import cstr

ASSET_VERSION = "2026.08.14"
SCRIPT_ID = "fbr-xpos-bridge"
FBR_BLOCK_MARKERS = (
	"fbr_pos_receipt_block",
	"xpos_fbr_block",
	"custom_fbr_invoice_no",
)
FBR_SECTION_CSS = """
.fbr-section {
    text-align: center;
    padding: 6px 0 4px;
    border-top: 1px dashed #000;
    margin-top: 4px;
}
.fbr-title {
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 0.4px;
    text-transform: uppercase;
}
.fbr-no {
    font-size: 10px;
    font-weight: 700;
    margin: 2px 0 4px;
    word-break: break-all;
}
.fbr-section img {
    width: 28mm;
    height: 28mm;
    margin: 0 auto;
}
"""
FBR_BLOCK_JINJA = "{{ fbr_pos_receipt_block(doc) }}"
SKIP_PRINT_MODULES = {"FBR Integration"}


def fbr_invoice_no(doc) -> str:
	"""FBR Digital Invoice number, or XPOS IMS fiscal number if that was used."""
	return (
		cstr(getattr(doc, "custom_fbr_invoice_no", None)).strip()
		or cstr(getattr(doc, "fbr_invoice_number", None)).strip()
	)


def fbr_pos_receipt_block(doc) -> str:
	"""Thermal / POS receipt HTML: FBR number + QR only when the invoice was sent."""
	fbr_no = fbr_invoice_no(doc)
	if not fbr_no:
		return ""

	qr_src = _qr_data_uri(fbr_no)

	esc = frappe.utils.escape_html(fbr_no)
	img = f'<img src="{qr_src}" alt="FBR QR" />' if qr_src else ""
	return (
		'<div class="fbr-section">'
		'<div class="fbr-title">FBR Digital Invoice</div>'
		f'<div class="fbr-no">{esc}</div>'
		f"{img}"
		"</div>"
	)


def _qr_data_uri(fbr_no: str) -> str:
	try:
		from fbr_integration.print_barcodes import get_qr_and_barcode_data_uri

		return (get_qr_and_barcode_data_uri(fbr_no) or {}).get("qr") or ""
	except Exception:
		frappe.log_error(title="FBR XPOS receipt QR failed", message=frappe.get_traceback())
		return ""


def inject_xpos_bridge(response=None, request=None):
	"""Append FBR overlay assets to the XPOS SPA shell (any XPOS build)."""
	try:
		if not response or not request:
			return
		path = cstr(getattr(request, "path", "") or "")
		if not _is_xpos_html_path(path):
			return
		ctype = (response.headers.get("Content-Type") or "").lower()
		if "html" not in ctype:
			return
		if getattr(response, "direct_passthrough", False):
			return

		html = response.get_data(as_text=True)
		if not html or SCRIPT_ID in html:
			return

		snippet = (
			f'\n<link rel="stylesheet" href="/assets/fbr_integration/css/xpos_fbr.css?v={ASSET_VERSION}">'
			f'\n<script src="/assets/fbr_integration/js/xpos_fbr.js?v={ASSET_VERSION}" id="{SCRIPT_ID}"></script>\n'
		)
		if "</body>" in html:
			html = html.replace("</body>", snippet + "</body>", 1)
		else:
			html += snippet
		response.set_data(html)
		data = response.get_data()
		response.headers["Content-Length"] = str(len(data) if isinstance(data, (bytes, bytearray)) else len(html))
	except Exception:
		frappe.log_error(title="FBR XPOS bridge inject failed", message=frappe.get_traceback())


def _is_xpos_html_path(path: str) -> bool:
	if not path.startswith("/xpos"):
		return False
	lower = path.lower()
	for ext in (
		".js",
		".css",
		".svg",
		".png",
		".jpg",
		".woff",
		".woff2",
		".json",
		".webmanifest",
		".map",
	):
		if lower.endswith(ext):
			return False
	if "/assets/" in lower:
		return False
	return True


def sync_xpos_print_formats():
	"""Insert FBR receipt block into XPOS / POS Profile print formats when missing."""
	if not frappe.db.exists("DocType", "Print Format"):
		return

	for name in sorted(_target_print_format_names()):
		try:
			_patch_print_format(name)
		except Exception:
			frappe.log_error(
				title=f"FBR XPOS print format sync failed: {name}",
				message=frappe.get_traceback(),
			)


def _target_print_format_names() -> set[str]:
	names = {"XPOS Thermal Receipt", "XPOS SI Thermal Receipt"}
	if frappe.db.exists("DocType", "POS Profile") and frappe.db.has_column("POS Profile", "print_format"):
		for row in frappe.get_all("POS Profile", fields=["print_format"]):
			if row.get("print_format"):
				names.add(row["print_format"])

	for row in frappe.get_all(
		"Print Format",
		filters={"module": "X POS", "disabled": 0},
		fields=["name"],
	):
		names.add(row["name"])

	return {n for n in names if n}


def _patch_print_format(name: str):
	if not frappe.db.exists("Print Format", name):
		return

	row = frappe.db.get_value(
		"Print Format",
		name,
		["module", "html", "css", "custom_format"],
		as_dict=True,
	)
	if not row:
		return
	if cstr(row.get("module")) in SKIP_PRINT_MODULES:
		return

	html = row.get("html") or ""
	css = row.get("css") or ""
	new_html = _ensure_fbr_block(html)
	new_css = _ensure_fbr_css(css)
	if new_html == html and new_css == css:
		return

	_set_print_format_html_css(name, new_html, new_css)


def _ensure_fbr_block(html: str) -> str:
	if not html:
		return html
	if any(marker in html for marker in FBR_BLOCK_MARKERS):
		return html

	block = f"\n    {FBR_BLOCK_JINJA}\n\n    "
	needles = (
		'<div class="barcode-section">',
		"<div class='barcode-section'>",
		'<div class="receipt-footer">',
		"<div class='receipt-footer'>",
	)
	for needle in needles:
		if needle in html:
			return html.replace(needle, block + needle, 1)
	return html + f"\n{FBR_BLOCK_JINJA}\n"


def _ensure_fbr_css(css: str) -> str:
	if ".fbr-section" in (css or ""):
		return css
	return (css or "") + "\n" + FBR_SECTION_CSS


def _set_print_format_html_css(name: str, html: str, css: str):
	try:
		doc = frappe.get_doc("Print Format", name)
		doc.html = html
		doc.css = css
		doc.flags.ignore_permissions = True
		doc.save(ignore_permissions=True)
	except Exception:
		frappe.db.set_value(
			"Print Format",
			name,
			{"html": html, "css": css},
			update_modified=True,
		)
