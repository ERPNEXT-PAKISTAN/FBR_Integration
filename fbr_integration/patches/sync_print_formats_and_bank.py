import frappe

from fbr_integration.print_bank import DEFAULT_BANK
from fbr_integration.print_format_sync import sync_print_formats


def execute():
	sync_print_formats()
	_ensure_company_bank_account()


def _ensure_company_bank_account():
	try:
		if not frappe.db.exists("DocType", "Bank Account"):
			return
		if not frappe.db.exists("Bank", DEFAULT_BANK["bank"]):
			bank = frappe.get_doc({"doctype": "Bank", "bank_name": DEFAULT_BANK["bank"]})
			bank.flags.ignore_permissions = True
			bank.insert(ignore_permissions=True)

		company = None
		try:
			company = frappe.defaults.get_global_default("company")
		except Exception:
			company = None
		if not company:
			company = frappe.db.get_single_value("Global Defaults", "default_company")
		if not company:
			return

		existing = frappe.db.exists(
			"Bank Account",
			{"company": company, "is_company_account": 1, "account_name": DEFAULT_BANK["account_name"]},
		)
		if existing:
			frappe.db.set_value(
				"Bank Account",
				existing,
				{
					"iban": DEFAULT_BANK["iban"],
					"bank": DEFAULT_BANK["bank"],
					"bank_account_no": DEFAULT_BANK["iban"],
					"is_company_account": 1,
				},
			)
			return

		payload = {
			"doctype": "Bank Account",
			"account_name": DEFAULT_BANK["account_name"],
			"bank": DEFAULT_BANK["bank"],
			"iban": DEFAULT_BANK["iban"],
			"bank_account_no": DEFAULT_BANK["iban"],
			"company": company,
			"is_company_account": 1,
		}
		if frappe.db.has_column("Bank Account", "account"):
			gl_account = frappe.db.get_value(
				"Account",
				{"company": company, "account_type": "Bank", "is_group": 0},
				"name",
			)
			if gl_account:
				payload["account"] = gl_account
		doc = frappe.get_doc(payload)
		doc.flags.ignore_permissions = True
		doc.insert(ignore_permissions=True)
	except Exception:
		frappe.log_error(title="FBR bank account sync skipped")
