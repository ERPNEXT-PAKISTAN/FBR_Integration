import sys
import types
import unittest

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

install_frappe_stub()

# Heavy deps used by fbr_api at import time.
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


from fbr_integration.fbr_api import format_extra_tax_for_payload, format_fbr_rate_percent  # noqa: E402
from fbr_integration.fbr_tax_calculation import (  # noqa: E402
	DEFAULT_INVOICE_TYPE,
	DEFAULT_ITEM_TAX_TEMPLATE_TITLE,
	DEFAULT_SCENARIO_DETAIL,
	DEFAULT_SCENARIO_ID,
	apply_default_invoice_type_and_scenario,
	get_effective_invoice_tax_scenario,
	resolve_item_tax_template_name,
)
from fbr_integration import fbr_tax_calculation as tax_mod  # noqa: E402
from fbr_integration.item_tax_templates import get_item_tax_template_specs  # noqa: E402


class DummyDoc:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

	def get(self, key, default=None):
		return getattr(self, key, default)


def _stub_default_masters():
	tax_mod.frappe.db.exists = lambda *a, **k: True
	tax_mod.frappe.db.get_value = lambda *a, **k: DEFAULT_SCENARIO_ID
	tax_mod.frappe.get_cached_value = lambda *a, **k: "SSC"
	tax_mod.frappe.get_all = lambda *a, **k: [
		{
			"name": f"{DEFAULT_ITEM_TAX_TEMPLATE_TITLE} - SSC",
			"title": DEFAULT_ITEM_TAX_TEMPLATE_TITLE,
		}
	]


class TestFbrTaxCalculation(unittest.TestCase):
	def test_get_effective_invoice_tax_scenario_uses_scenario_id_and_detail(self):
		doc = DummyDoc(
			custom_scenario_detail="SN028 - Retailer - Reduced Rate Goods",
			custom_scenario_id="SN005",
		)

		self.assertEqual(
			get_effective_invoice_tax_scenario(doc),
			"SN028 - Retailer - Reduced Rate Goods",
		)

		doc.custom_scenario_detail = ""
		self.assertEqual(
			get_effective_invoice_tax_scenario(doc),
			"SN005",
		)

		doc.custom_scenario_id = ""
		self.assertEqual(get_effective_invoice_tax_scenario(doc), "")

	def test_apply_defaults_sets_sale_invoice_and_sn001(self):
		_stub_default_masters()

		item = DummyDoc(
			item_code="ITEM-001",
			custom_scenario_detail="",
			item_tax_template="",
		)
		doc = DummyDoc(
			doctype="Sales Invoice",
			is_return=0,
			customer=None,
			company="MOOSA CORPORATION",
			custom_invoice_type="",
			custom_scenario_detail="",
			custom_scenario_id="",
			items=[item],
		)

		apply_default_invoice_type_and_scenario(doc)

		self.assertEqual(doc.custom_invoice_type, DEFAULT_INVOICE_TYPE)
		self.assertEqual(doc.custom_scenario_detail, DEFAULT_SCENARIO_DETAIL)
		self.assertEqual(doc.custom_scenario_id, DEFAULT_SCENARIO_ID)
		self.assertEqual(item.custom_scenario_detail, DEFAULT_SCENARIO_DETAIL)
		self.assertEqual(item.item_tax_template, f"{DEFAULT_ITEM_TAX_TEMPLATE_TITLE} - SSC")

	def test_apply_defaults_on_pos_invoice(self):
		_stub_default_masters()

		item = DummyDoc(
			item_code="ITEM-001",
			custom_scenario_detail="",
			item_tax_template="",
		)
		doc = DummyDoc(
			doctype="POS Invoice",
			is_return=0,
			customer=None,
			company="MOOSA CORPORATION",
			custom_invoice_type="",
			custom_scenario_detail="",
			custom_scenario_id="",
			items=[item],
		)

		apply_default_invoice_type_and_scenario(doc)

		self.assertEqual(doc.custom_invoice_type, DEFAULT_INVOICE_TYPE)
		self.assertEqual(doc.custom_scenario_detail, DEFAULT_SCENARIO_DETAIL)
		self.assertEqual(doc.custom_scenario_id, DEFAULT_SCENARIO_ID)
		self.assertEqual(item.item_tax_template, f"{DEFAULT_ITEM_TAX_TEMPLATE_TITLE} - SSC")

	def test_apply_defaults_does_not_overwrite_existing_values(self):
		_stub_default_masters()

		doc = DummyDoc(
			doctype="Sales Invoice",
			is_return=0,
			customer=None,
			custom_invoice_type="Debit Note",
			custom_scenario_detail="SN002 - Goods at Standard Rate (Unregistered Buyer)",
			custom_scenario_id="SN002",
			items=[],
		)

		apply_default_invoice_type_and_scenario(doc)

		self.assertEqual(doc.custom_invoice_type, "Debit Note")
		self.assertEqual(
			doc.custom_scenario_detail,
			"SN002 - Goods at Standard Rate (Unregistered Buyer)",
		)
		self.assertEqual(doc.custom_scenario_id, "SN002")

	def test_resolve_item_tax_template_prefers_company_sn001(self):
		_stub_default_masters()
		self.assertEqual(
			resolve_item_tax_template_name(
				DEFAULT_SCENARIO_DETAIL, company="MOOSA CORPORATION"
			),
			f"{DEFAULT_ITEM_TAX_TEMPLATE_TITLE} - SSC",
		)

	def test_apply_defaults_skips_invoice_type_on_return(self):
		_stub_default_masters()

		doc = DummyDoc(
			doctype="Sales Invoice",
			is_return=1,
			customer=None,
			custom_invoice_type="",
			custom_scenario_detail="",
			custom_scenario_id="",
			items=[],
		)

		apply_default_invoice_type_and_scenario(doc)

		self.assertEqual(doc.custom_invoice_type, "")
		self.assertEqual(doc.custom_scenario_detail, DEFAULT_SCENARIO_DETAIL)
		self.assertEqual(doc.custom_scenario_id, DEFAULT_SCENARIO_ID)

	def test_format_extra_tax_for_payload_uses_blank_for_reduced_rate_scenarios(self):
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN005"), "")
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN009"), "")
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN028"), "")
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN004"), 12.5)

	def test_format_fbr_rate_percent_matches_di_catalog(self):
		self.assertEqual(format_fbr_rate_percent(18), "18%")
		self.assertEqual(format_fbr_rate_percent(18.00), "18%")
		self.assertEqual(format_fbr_rate_percent(17.5), "17.5%")

	def test_item_tax_template_seed_data_ships_expected_scenarios(self):
		specs = get_item_tax_template_specs()
		self.assertEqual(len(specs), 28)
		self.assertEqual(specs[0]["scenario_id"], "SN001")
		self.assertEqual(specs[-1]["scenario_id"], "SN028")


if __name__ == "__main__":
	unittest.main()
