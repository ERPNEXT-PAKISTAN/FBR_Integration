import importlib
import sys
import types
import unittest

from fbr_integration.tests.frappe_test_stub import FakePermissionError, install_frappe_stub

_frappe = install_frappe_stub(force=True)

from fbr_integration.permissions import assert_finance_dashboard_access  # noqa: E402


class TestFinanceDashboardPermissions(unittest.TestCase):
	def test_administrator_allowed(self):
		_frappe.session.user = "Administrator"
		assert_finance_dashboard_access()

	def test_guest_denied(self):
		_frappe.session.user = "Guest"
		with self.assertRaises(FakePermissionError):
			assert_finance_dashboard_access()

	def test_accounts_user_allowed(self):
		_frappe.session.user = "a@example.com"
		_frappe.get_roles = lambda: ["Accounts User"]
		assert_finance_dashboard_access()

	def test_unrelated_role_denied(self):
		_frappe.session.user = "a@example.com"
		_frappe.get_roles = lambda: ["Employee"]
		with self.assertRaises(FakePermissionError):
			assert_finance_dashboard_access()


class TestSendGuard(unittest.TestCase):
	def test_assert_can_send_requires_write(self):
		mapping = types.ModuleType("fbr_integration.fbr_payload_mapping")
		mapping.apply_extra_item_payload_mappings = lambda *a, **k: None
		mapping.apply_extra_payload_mappings = lambda *a, **k: None
		mapping.resolve_payload_value = lambda *a, **k: None
		sys.modules["fbr_integration.fbr_payload_mapping"] = mapping

		for pkg in ("requests", "urllib3"):
			if pkg not in sys.modules:
				mod = types.ModuleType(pkg)
				if pkg == "urllib3":
					mod.disable_warnings = lambda *a, **k: None
				sys.modules[pkg] = mod

		mod = importlib.import_module("fbr_integration.fbr_api")
		mod = importlib.reload(mod)
		assert_can_send_invoice_to_fbr = mod.assert_can_send_invoice_to_fbr

		import frappe as frappe_mod

		doc = types.SimpleNamespace(name="SI-1", doctype="Sales Invoice")
		frappe_mod.session.user = "user@example.com"
		frappe_mod.has_permission = lambda *a, **k: False
		with self.assertRaises(frappe_mod.PermissionError):
			assert_can_send_invoice_to_fbr(doc)

		frappe_mod.has_permission = lambda *a, **k: True
		assert_can_send_invoice_to_fbr(doc)

		frappe_mod.session.user = "Administrator"
		frappe_mod.has_permission = lambda *a, **k: False
		assert_can_send_invoice_to_fbr(doc)


if __name__ == "__main__":
	unittest.main()
