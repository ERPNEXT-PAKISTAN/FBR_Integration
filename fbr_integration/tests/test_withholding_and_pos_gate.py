import types
import unittest

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

_frappe = install_frappe_stub(force=True)
_frappe.db.get_value = lambda *a, **k: None
_frappe.get_all = lambda *a, **k: []
_frappe.utils = types.SimpleNamespace(
	getdate=lambda d: d,
	nowdate=lambda: "2026-08-02",
	cint=lambda v=0: int(v or 0),
)


from fbr_integration.fbr_tax_calculation import (  # noqa: E402
	_st_withheld_rate_from_category,
	ensure_pos_flag,
)


class TestWithholdingHelpers(unittest.TestCase):
	def test_st_withheld_category_filter(self):
		self.assertEqual(_st_withheld_rate_from_category("WH TAX - 5% (Sales)"), 0)
		self.assertEqual(_st_withheld_rate_from_category(""), 0)

	def test_ensure_pos_flag_from_profile(self):
		doc = types.SimpleNamespace(
			doctype="Sales Invoice",
			pos_profile="Main POS",
			is_created_using_pos=0,
			is_pos=0,
		)
		ensure_pos_flag(doc)
		self.assertEqual(doc.is_pos, 1)

	def test_ensure_pos_flag_from_created_using_pos(self):
		doc = types.SimpleNamespace(
			doctype="Sales Invoice",
			pos_profile=None,
			is_created_using_pos=1,
			is_pos=0,
		)
		ensure_pos_flag(doc)
		self.assertEqual(doc.is_pos, 1)


class TestAutoSendGate(unittest.TestCase):
	def test_pos_auto_send_default(self):
		import importlib
		import sys

		# Lightweight stubs so fbr_api can import.
		if "fbr_integration.fbr_payload_mapping" not in sys.modules:
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

		settings = types.SimpleNamespace(
			enabled=1,
			auto_send_pos_on_submit=1,
			auto_send_on_submit=0,
		)
		_frappe.get_single = lambda *a, **k: settings

		pos_doc = types.SimpleNamespace(is_pos=1, is_created_using_pos=1)
		plain_doc = types.SimpleNamespace(is_pos=0, is_created_using_pos=0)

		self.assertTrue(mod._should_auto_send_on_submit(pos_doc))
		self.assertFalse(mod._should_auto_send_on_submit(plain_doc))

		settings.auto_send_on_submit = 1
		self.assertTrue(mod._should_auto_send_on_submit(plain_doc))


if __name__ == "__main__":
	unittest.main()
