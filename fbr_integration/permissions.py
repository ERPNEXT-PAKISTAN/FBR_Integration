"""Permission helpers shared by FBR dashboard and APIs."""

from __future__ import annotations

from functools import wraps

import frappe
from frappe import _

FINANCE_ROLES = {
	"System Manager",
	"Accounts Manager",
	"Accounts User",
	"Sales Manager",
	"Sales User",
}


def assert_finance_dashboard_access():
	"""Restrict Financial Dashboard APIs to finance/sales roles."""
	if frappe.session.user in ("Administrator", "Guest"):
		if frappe.session.user == "Administrator":
			return
		frappe.throw(_("Login required"), frappe.PermissionError)

	roles = set(frappe.get_roles())
	if roles & FINANCE_ROLES:
		return

	frappe.throw(
		_("You need Accounts or Sales roles to open the Financial Dashboard."),
		frappe.PermissionError,
		title=_("Not Permitted"),
	)


def require_finance_dashboard(fn):
	"""Decorator for whitelisted dashboard methods."""

	@wraps(fn)
	def wrapper(*args, **kwargs):
		assert_finance_dashboard_access()
		return fn(*args, **kwargs)

	return wrapper
