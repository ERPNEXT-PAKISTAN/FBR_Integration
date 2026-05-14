app_name = "fbr_integration"
app_title = "FBR Integration"
app_publisher = "Taimoor"
app_description = "FBR Digital Invoice Integration"
app_email = "tymuur@outlook.com"
app_license = "MIT"

AUTO_SEND_ON_SUBMIT = 0  # 1 = auto send on submit, 0 = manual button

doc_events = {
	"Sales Invoice": {
		"validate": [
			"fbr_integration.fbr_tax_calculation.calculate_fbr_tax",
			"fbr_integration.fbr_api.enforce_return_invoice_type",
		],
		"before_save": [
			"fbr_integration.fbr_tax_calculation.calculate_fbr_tax",
			"fbr_integration.fbr_api.enforce_return_invoice_type",
		],
	}
}

if AUTO_SEND_ON_SUBMIT:
	doc_events["Sales Invoice"]["on_submit"] = "fbr_integration.fbr_api.after_submit_invoice"

# Sales Invoice UI: live tax + send button + QR/barcode rendering
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice_fbr.js",
}

# Purple button CSS (you already have fbr.css)
app_include_css = ["/assets/fbr_integration/css/fbr.css"]

# Fixtures: ship custom fields + print formats + reports + workspace/dashboard (recommended)
fixtures = [
	{"dt": "Module Def", "filters": [["module_name", "=", "FBR Integration"]]},
	{
		"dt": "Custom Field",
		"filters": [["dt", "in", ["Sales Invoice", "Sales Invoice Item"]]],
	},
	{"dt": "Print Format", "filters": [["module", "=", "FBR Integration"]]},
	{"dt": "Workspace", "filters": [["name", "in", ["FBR Pakistan"]]]},
	{"dt": "Dashboard", "filters": [["module", "=", "FBR Integration"]]},
	# Master / seed data — auto-imported on bench migrate
	{"dt": "Buyer Province", "filters": [["name", "!=", ""]]},
	{"dt": "FBR UOM", "filters": [["name", "!=", ""]]},
	{"dt": "Invoice Type", "filters": [["name", "!=", ""]]},
	{"dt": "Sale Type", "filters": [["name", "!=", ""]]},
	{"dt": "Tax Payer Type", "filters": [["name", "!=", ""]]},
	{"dt": "Scenario ID", "filters": [["name", "!=", ""]]},
	{"dt": "SRO Schedule No", "filters": [["name", "!=", ""]]},
	{"dt": "SRO Item SNO", "filters": [["name", "!=", ""]]},
	{"dt": "HS Code", "filters": [["name", "!=", ""]]},
]
