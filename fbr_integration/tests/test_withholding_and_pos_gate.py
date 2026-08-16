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
	cstr=lambda v="": "" if v is None else str(v),
)
import sys

sys.modules["frappe.utils"].cstr = _frappe.utils.cstr
sys.modules["frappe.utils"].getdate = _frappe.utils.getdate
sys.modules["frappe.utils"].cint = _frappe.utils.cint
_frappe.msgprint = lambda *a, **k: None
_frappe.get_cached_doc = lambda *a, **k: types.SimpleNamespace(rates=[])
_frappe.get_single = lambda *a, **k: types.SimpleNamespace()


from fbr_integration.fbr_tax_calculation import (  # noqa: E402
	_allocate_invoice_withholding_to_items,
	_default_st_withheld_rate,
	_invoice_considers_tax_withholding,
	_item_considers_tax_withholding,
	ensure_pos_flag,
	gate_pos_tax_withholding,
)


class TestWithholdingHelpers(unittest.TestCase):

	def test_item_apply_tds_gate(self):
		item_on = types.SimpleNamespace(apply_tds=1, tax_withholding_category="")
		item_off = types.SimpleNamespace(apply_tds=0, tax_withholding_category="")
		doc_on = types.SimpleNamespace(apply_tds=1, customer="C1")
		doc_off = types.SimpleNamespace(apply_tds=0, customer="C1")
		self.assertTrue(_item_considers_tax_withholding(doc_on, item_on))
		self.assertFalse(_item_considers_tax_withholding(doc_on, item_off))
		self.assertFalse(_item_considers_tax_withholding(doc_off, item_on))

	def test_apply_tds_gates_auto_rate(self):
		item = types.SimpleNamespace(
			custom_sales_tax_withheld_rate=0,
			tax_withholding_category="",
		)
		doc_off = types.SimpleNamespace(apply_tds=0, customer="C1")
		doc_on = types.SimpleNamespace(apply_tds=1, customer="C1")
		self.assertFalse(_invoice_considers_tax_withholding(doc_off))
		self.assertTrue(_invoice_considers_tax_withholding(doc_on))
		# Without apply_tds, customer category must not auto-apply.
		self.assertEqual(_default_st_withheld_rate(doc_off, item), 0)
		# Manual item rate is also ignored while withholding is off.
		item.custom_sales_tax_withheld_rate = 5
		self.assertEqual(_default_st_withheld_rate(doc_off, item), 0)
		self.assertEqual(_default_st_withheld_rate(doc_on, item), 5)

	def test_allocate_overwrites_stale_withheld_rate(self):
		item = types.SimpleNamespace(
			amount=30000,
			apply_tds=1,
			custom_sales_tax_withheld_rate=5,
			custom_sales_tax_withheld_at_source=1500,
		)
		doc = types.SimpleNamespace(
			apply_tds=1,
			tax_withholding_entries=[
				types.SimpleNamespace(
					withholding_amount=600,
					tax_withholding_category="ST Withheld - 2% (FBR)",
				)
			],
			items=[item],
		)
		doc.get = lambda key, default=None, _doc=doc: getattr(_doc, key, default)
		_allocate_invoice_withholding_to_items(doc)
		self.assertEqual(item.custom_sales_tax_withheld_at_source, 600)
		self.assertAlmostEqual(item.custom_sales_tax_withheld_rate, 2.0)

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


class TestPosWithholdingGate(unittest.TestCase):
	def _pos_doc(self, **kwargs):
		item = types.SimpleNamespace(
			apply_tds=1,
			tax_withholding_category=kwargs.pop("item_category", "TCS"),
		)
		defaults = dict(
			doctype="Sales Invoice",
			is_pos=1,
			is_created_using_pos=1,
			pos_profile="Main POS",
			apply_tds=1,
			custom_apply_tax_withholding=0,
			posting_date="2026-08-14",
			tax_withholding_group="",
			customer="C1",
			items=[item],
		)
		defaults.update(kwargs)
		doc = types.SimpleNamespace(**defaults)
		doc.get = lambda key, default=None, _doc=doc: getattr(_doc, key, default)
		return doc

	def test_pos_unchecks_withholding_by_default(self):
		doc = self._pos_doc(custom_apply_tax_withholding=0, apply_tds=1)
		gate_pos_tax_withholding(doc)
		self.assertEqual(doc.apply_tds, 0)
		self.assertEqual(doc.items[0].apply_tds, 0)

	def test_non_pos_leaves_apply_tds_alone(self):
		doc = self._pos_doc(is_pos=0, is_created_using_pos=0, pos_profile=None, apply_tds=1)
		gate_pos_tax_withholding(doc)
		self.assertEqual(doc.apply_tds, 1)

	def test_pos_checked_skips_when_rate_missing(self):
		messages = []
		import frappe as frappe_mod
		from fbr_integration import fbr_tax_calculation as tax_mod

		def _msg(*a, **k):
			messages.append(a[0] if a else "")

		frappe_mod.msgprint = _msg
		tax_mod.frappe.msgprint = _msg
		frappe_mod.db.exists = lambda *a, **k: False
		tax_mod.frappe.db.exists = lambda *a, **k: False
		doc = self._pos_doc(custom_apply_tax_withholding=1, apply_tds=0)
		gate_pos_tax_withholding(doc)
		self.assertEqual(doc.apply_tds, 0)
		self.assertTrue(messages)

	def test_pos_checked_keeps_apply_tds_when_rate_exists(self):
		import frappe as frappe_mod
		from fbr_integration import fbr_tax_calculation as tax_mod

		frappe_mod.db.exists = lambda *a, **k: True
		tax_mod.frappe.db.exists = lambda *a, **k: True
		cat = types.SimpleNamespace(
			rates=[
				types.SimpleNamespace(
					from_date="2026-01-01",
					to_date="2026-12-31",
					tax_withholding_group="",
				)
			]
		)
		cat.get = lambda key, default=None, _cat=cat: getattr(_cat, key, default)
		frappe_mod.get_cached_doc = lambda *a, **k: cat
		tax_mod.frappe.get_cached_doc = lambda *a, **k: cat
		doc = self._pos_doc(custom_apply_tax_withholding=1, apply_tds=0)
		gate_pos_tax_withholding(doc)
		self.assertEqual(doc.apply_tds, 1)


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
		sys.modules["frappe"].get_single = lambda *a, **k: settings

		pos_doc = types.SimpleNamespace(is_pos=1, is_created_using_pos=1)
		plain_doc = types.SimpleNamespace(is_pos=0, is_created_using_pos=0)

		self.assertTrue(mod._should_auto_send_on_submit(pos_doc))
		self.assertFalse(mod._should_auto_send_on_submit(plain_doc))

		consolidated = types.SimpleNamespace(
			is_pos=1, is_created_using_pos=1, is_consolidated=1
		)
		self.assertFalse(mod._should_auto_send_on_submit(consolidated))

		settings.auto_send_on_submit = 1
		self.assertTrue(mod._should_auto_send_on_submit(plain_doc))


if __name__ == "__main__":
	unittest.main()
