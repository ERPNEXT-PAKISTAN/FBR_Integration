import types
import unittest

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

_frappe = install_frappe_stub(force=True)


# Minimal import surface for helpers under test
import importlib
import sys

mapping = types.ModuleType("fbr_integration.fbr_payload_mapping")
mapping.apply_extra_item_payload_mappings = lambda *a, **k: None
mapping.apply_extra_payload_mappings = lambda *a, **k: None
mapping.resolve_payload_value = lambda field, default, *a, **k: default
sys.modules["fbr_integration.fbr_payload_mapping"] = mapping
for pkg in ("requests", "urllib3"):
	if pkg not in sys.modules:
		mod = types.ModuleType(pkg)
		if pkg == "urllib3":
			mod.disable_warnings = lambda *a, **k: None
		sys.modules[pkg] = mod

mod = importlib.import_module("fbr_integration.fbr_api")
mod = importlib.reload(mod)


def _bind_db_get_value(value="1953701DI1KLDKA962915"):
	db = types.SimpleNamespace(
		exists=lambda *a, **k: True,
		has_column=lambda *a, **k: True,
		get_value=lambda *a, **k: value,
	)
	sys.modules["frappe"].db = db
	tax_mod = sys.modules.get("fbr_integration.fbr_tax_calculation")
	if tax_mod is not None:
		tax_mod.frappe.db = db


class TestReturnInvoiceRef(unittest.TestCase):
	def test_source_prefers_custom_fbr_source_invoice_no(self):
		_bind_db_get_value("SHOULD_NOT_USE")
		doc = types.SimpleNamespace(
			custom_fbr_source_invoice_no="7000007DI1747119701593",
			return_against="ACC-SINV-2026-0001",
			remarks="",
		)
		self.assertEqual(
			mod.get_source_invoice_no_for_return(doc),
			"7000007DI1747119701593",
		)

	def test_source_from_return_against_fbr_no(self):
		_bind_db_get_value("1953701DI1KLDKA962915")
		doc = types.SimpleNamespace(
			custom_fbr_source_invoice_no="",
			return_against="ACC-SINV-2026-0001",
			remarks="",
		)
		self.assertEqual(
			mod.get_source_invoice_no_for_return(doc),
			"1953701DI1KLDKA962915",
		)

	def test_enforce_sets_credit_note(self):
		_bind_db_get_value("1953701DI1KLDKA962915")
		doc = types.SimpleNamespace(
			is_return=1,
			custom_invoice_type="Sale Invoice",
			custom_fbr_source_invoice_no="",
			return_against="ACC-SINV-2026-0001",
			remarks="",
		)
		mod.enforce_return_invoice_type(doc)
		self.assertEqual(doc.custom_invoice_type, "Credit Note")
		self.assertEqual(doc.custom_fbr_source_invoice_no, "1953701DI1KLDKA962915")


if __name__ == "__main__":
	unittest.main()
