"""Ensure FBR tax masters exist for each company.

Item Tax Template (28) and Tax Withholding Category (29) depend on the
company chart of accounts, so they are seeded here instead of as fixtures.
Tax Category (Input Tax, Output Tax) has no company link and is also seeded
here so a site gets it even before the fixture import runs.
"""

import frappe

from fbr_integration.item_tax_templates import ITEM_TAX_TEMPLATE_SPECS, sync_item_tax_templates
from fbr_integration.tax_category_sync import sync_tax_categories
from fbr_integration.tax_withholding_sync import expected_category_names, sync_tax_withholding_masters


def _company_has_accounts(company: str) -> bool:
	return bool(frappe.db.get_value("Account", {"company": company}, "name"))


def company_tax_masters_incomplete(company: str) -> bool:
	"""True when this company has a chart but is missing FBR tax masters."""
	if not company or not _company_has_accounts(company):
		return False

	titles = [row["title"] for row in ITEM_TAX_TEMPLATE_SPECS]
	found = frappe.get_all(
		"Item Tax Template",
		filters={"company": company, "title": ["in", titles]},
		pluck="title",
		limit_page_length=0,
	)
	if len(set(found)) < len(titles):
		return True

	if not frappe.db.exists("DocType", "Tax Withholding Category"):
		return False

	for name in expected_category_names():
		if not frappe.db.exists("Tax Withholding Category", name):
			return True
		if not frappe.db.exists("Tax Withholding Account", {"parent": name, "company": company}):
			return True
	return False


def tax_masters_missing() -> bool:
	"""True when no company exists yet, or any company with a chart is incomplete."""
	companies = frappe.get_all("Company", pluck="name")
	if not companies:
		return True
	return any(company_tax_masters_incomplete(company) for company in companies)


def ensure_tax_masters_for_company(company: str):
	sync_tax_categories()
	if not company_tax_masters_incomplete(company):
		return
	sync_item_tax_templates(companies=[company])
	sync_tax_withholding_masters(companies=[company])


def seed_company_tax_masters(doc, method=None):
	"""Company.on_update hook. Chart of accounts is created before this runs."""
	if frappe.flags.in_test or frappe.flags.in_install or frappe.flags.in_migrate:
		return
	company = getattr(doc, "name", None)
	if not company:
		return
	try:
		ensure_tax_masters_for_company(company)
	except Exception:
		frappe.log_error(title="FBR tax master seed failed", message=frappe.get_traceback())
