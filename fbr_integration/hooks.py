app_name = "fbr_integration"
app_title = "FBR Integration"
app_publisher = "Taimoor"
app_description = "FBR Digital Invoice Integration"
app_email = "tymuur@outlook.com"
app_license = "MIT"

# Apps launcher entry. Desktop Icon link is corrected per major via compat.workspace_route().
add_to_apps_screen = [
	{
		"name": "fbr_integration",
		"logo": "/assets/fbr_integration/images/fbr/DI_invoicing.png",
		"title": "FBR Integration",
		"route": "/app/fbr-pakistan",
	}
]

extend_bootinfo = "fbr_integration.compat.boot_session"

# Auto-send is gated in after_submit_invoice via FBR Invoice Settings
# (POS on by default; all SI optional). Manual Send to FBR always available.

doc_events = {
	"Sales Invoice": {
		"before_validate": [
			"fbr_integration.fbr_tax_calculation.disable_update_stock_for_delivery_note_invoice",
			"fbr_integration.fbr_tax_calculation.sync_return_source_invoice_no",
			"fbr_integration.fbr_tax_calculation.ensure_pos_flag",
		],
		"validate": [
			"fbr_integration.fbr_tax_calculation.ensure_pos_flag",
			"fbr_integration.fbr_tax_calculation.sync_return_source_invoice_no",
			"fbr_integration.fbr_tax_calculation.sync_sales_invoice_master_defaults",
			"fbr_integration.fbr_tax_calculation.calculate_fbr_tax",
			"fbr_integration.fbr_api.enforce_return_invoice_type",
		],
		"before_save": [
			"fbr_integration.fbr_tax_calculation.ensure_pos_flag",
			"fbr_integration.fbr_tax_calculation.restore_submitted_sales_tax_rows",
			"fbr_integration.fbr_tax_calculation.sync_return_source_invoice_no",
			"fbr_integration.fbr_tax_calculation.sync_sales_invoice_master_defaults",
			"fbr_integration.fbr_tax_calculation.calculate_fbr_tax",
			"fbr_integration.fbr_api.enforce_return_invoice_type",
		],
		"on_submit": "fbr_integration.fbr_api.after_submit_invoice",
	}
}

# Sales Invoice UI: live tax + send button + QR/barcode rendering
doctype_js = {
	"Sales Invoice": "public/js/sales_invoice_fbr.js",
	"FBR Payload Field Mapping": [
		"public/js/fbr_payload_field_mapping.js",
		"public/js/fbr_payload_reference.js",
	],
	"FBR Payload Field": "public/js/fbr_payload_reference.js",
	"FBR Payload Source Field": "public/js/fbr_payload_reference.js",
}

doctype_list_js = {
	"FBR Payload Field Mapping": [
		"public/js/fbr_payload_reference.js",
		"public/js/fbr_payload_reference_list.js",
	],
	"FBR Payload Field": [
		"public/js/fbr_payload_reference.js",
		"public/js/fbr_payload_reference_list.js",
	],
	"FBR Payload Source Field": [
		"public/js/fbr_payload_reference.js",
		"public/js/fbr_payload_reference_list.js",
	],
}

# Purple button CSS + dual desk route helper
app_include_css = ["/assets/fbr_integration/css/fbr.css"]
app_include_js = ["/assets/fbr_integration/js/fbr_desk.js"]

after_install = "fbr_integration.install.after_install"
before_uninstall = "fbr_integration.install.before_uninstall"

# Desk nav every migrate; heavy master syncs only when FBR_SYNC_VERSION changes.
after_migrate = ["fbr_integration.migrate_tasks.run_after_migrate"]

# Fixtures: ship custom fields + print formats + reports + workspace/dashboard (recommended)
fixtures = [
	{"dt": "Module Def", "filters": [["module_name", "=", "FBR Integration"]]},
	{
		"dt": "Custom Field",
		"filters": [
			[
				"dt",
				"in",
				[
					"Sales Invoice",
					"Sales Invoice Item",
					"Delivery Note",
					"Delivery Note Item",
					"Customer",
					"Item",
					"Item Tax Template",
				],
			]
		],
	},
	{
		"dt": "Property Setter",
		"filters": [
			[
				"doc_type",
				"in",
				[
					"Sales Invoice",
					"Sales Invoice Item",
					"Sales Taxes and Charges",
					"Delivery Note",
					"Delivery Note Item",
				],
			]
		],
	},
	{"dt": "Print Format", "filters": [["module", "=", "FBR Integration"]]},
	{
		"dt": "Report",
		"filters": [
			[
				"name",
				"in",
				[
					"Consumption Report",
					"FBR Expenses Detail",
					"FBR Expenses GL Dynamic",
					"FBR Item Wise",
					"FBR Purchases Detail",
					"FBR Sales Detail",
					"FBR Sales Summary",
					"Sales by Item",
					"Sales by item Group",
					"Sales Invoices Detail Report",
					"Sales Trend Analysis Report",
					"Stock Report",
					"Supplier Wise Purchases Detail",
					"Sales Invoice Summary",
					"Purchase Receipts Summary",
					"Purchase Invoice Summary",
				],
			]
		],
	},
	{"dt": "Workspace", "filters": [["name", "in", ["FBR Pakistan"]]]},
	{"dt": "Custom HTML Block", "filters": [["name", "in", ["FBR Fiscal Year KPI Summary"]]]},
	{"dt": "Dashboard", "filters": [["module", "=", "FBR Integration"]]},
	# Master / seed data — auto-imported on bench migrate
	{"dt": "Buyer Province", "filters": [["name", "!=", ""]]},
	{"dt": "FBR UOM", "filters": [["name", "!=", ""]]},
	{"dt": "Invoice Type", "filters": [["name", "!=", ""]]},
	{"dt": "Sale Type", "filters": [["name", "!=", ""]]},
	{"dt": "Tax Payer Type", "filters": [["name", "!=", ""]]},
	{"dt": "Scenario ID", "filters": [["name", "!=", ""]]},
	{"dt": "SRO Schedule No", "filters": [["name", "!=", ""]]},
	{"dt": "SRO Item SNo", "filters": [["name", "!=", ""]]},
	{"dt": "HS Code", "filters": [["name", "!=", ""]]},
]
