import sys
import types
import unittest


if "frappe" not in sys.modules:
	frappe_stub = types.SimpleNamespace(
		__path__=[],
		whitelist=lambda *args, **kwargs: (lambda fn: fn),
		safe_decode=lambda value: value,
		throw=lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError(args[0] if args else "")),
	)
	sys.modules["frappe"] = frappe_stub
	frappe_utils_stub = types.SimpleNamespace(cint=lambda value=0: int(value or 0))
	sys.modules["frappe.utils"] = frappe_utils_stub
	setattr(frappe_stub, "utils", frappe_utils_stub)


from fbr_integration.fbr_api import format_extra_tax_for_payload  # noqa: E402
from fbr_integration.fbr_tax_calculation import (  # noqa: E402
	get_effective_invoice_tax_scenario,
)
from fbr_integration.item_tax_templates import get_item_tax_template_specs  # noqa: E402


class DummyDoc:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

	def get(self, key, default=None):
		return getattr(self, key, default)


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

	def test_format_extra_tax_for_payload_uses_blank_for_reduced_rate_scenarios(self):
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN005"), "")
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN009"), "")
		self.assertEqual(format_extra_tax_for_payload(12.5, "SN004"), 12.5)

	def test_item_tax_template_seed_data_ships_expected_scenarios(self):
		specs = get_item_tax_template_specs()
		self.assertEqual(len(specs), 28)
		self.assertEqual(specs[0]["scenario_id"], "SN001")
		self.assertEqual(specs[-1]["scenario_id"], "SN028")


if __name__ == "__main__":
	unittest.main()
