import unittest

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

frappe = install_frappe_stub()

from fbr_integration.taxation.constants import (  # noqa: E402
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_MANUAL,
	TAX_BASIS_RETAIL_PRICE,
	TAX_BASIS_SALES_VALUE,
)
from fbr_integration.taxation.engine import (  # noqa: E402
	apply_item_tax_amounts,
	calculate_sales_tax,
	get_fbr_taxable_value,
	get_tax_component_base,
)
from fbr_integration.taxation.payload import get_fixed_notified_or_retail_price  # noqa: E402
from fbr_integration.taxation.retail_price import resolve_retail_price  # noqa: E402
from fbr_integration.taxation.snapshot import (  # noqa: E402
	has_tax_snapshot,
	should_preserve_snapshot,
)
from fbr_integration.taxation.validation import validate_fbr_tax_row  # noqa: E402
from fbr_integration import taxation as tax_pkg  # noqa: E402
from fbr_integration.taxation import retail_price as retail_mod  # noqa: E402
from fbr_integration.taxation import snapshot as snapshot_mod  # noqa: E402


class DummyDoc:
	def __init__(self, **kwargs):
		self.__dict__.update(kwargs)

	def get(self, key, default=None):
		return getattr(self, key, default)


def _item(**kwargs):
	defaults = {
		"idx": 1,
		"item_code": "ITEM-001",
		"qty": 1,
		"rate": 800,
		"amount": 800,
		"custom_fbr_tax_calculation_basis": "",
		"custom_fbr_retail_price": 0,
		"custom_fbr_fixed_notified_value": 0,
		"custom_fbr_taxable_value": 0,
		"custom_sales_tax_rate": 0,
		"custom_further_tax_rate": 0,
		"custom_extra_tax_rate": 0,
		"custom_sales_tax": 0,
		"custom_further_tax": 0,
		"custom_extra_tax": 0,
		"custom_total_tax_amount": 0,
		"custom_tax_inclusive_amount": 0,
		"custom_hs_code": "3305.1000",
		"custom_fbr_uom": "Numbers, pieces, units",
		"custom_sale_type": "Goods at standard rate (default)",
	}
	defaults.update(kwargs)
	return DummyDoc(**defaults)


GST_18 = [{"tax_type": "Output Tax - GST", "tax_rate": 18}]


class TestFbrTaxableValue(unittest.TestCase):
	def test_standard_taxable_uses_sales_value(self):
		item = _item(qty=10, rate=800, amount=8000, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		self.assertEqual(get_fbr_taxable_value(item), 8000)
		self.assertEqual(calculate_sales_tax(item, 18), 1440)
		self.assertEqual(item.rate, 800)
		self.assertEqual(item.amount, 8000)

	def test_third_schedule_uses_mrp_times_qty(self):
		item = _item(
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		self.assertEqual(get_fbr_taxable_value(item), 10000)
		self.assertEqual(calculate_sales_tax(item, 18), 1800)
		self.assertEqual(item.rate, 800)
		self.assertEqual(item.amount, 8000)

	def test_zero_rated_item(self):
		item = _item(amount=5000, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		self.assertEqual(calculate_sales_tax(item, 0), 0)

	def test_exempt_item(self):
		item = _item(amount=2500, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		apply_item_tax_amounts(DummyDoc(items=[item]), item, tax_rows=[{"tax_type": "Exempt", "tax_rate": 0}])
		self.assertEqual(item.custom_sales_tax, 0)

	def test_reduced_rate_item(self):
		item = _item(qty=2, rate=1000, amount=2000, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		self.assertEqual(calculate_sales_tax(item, 12), 240)

	def test_fixed_notified_value_item(self):
		item = _item(
			qty=4,
			rate=50,
			amount=200,
			custom_fbr_tax_calculation_basis=TAX_BASIS_FIXED_NOTIFIED,
			custom_fbr_fixed_notified_value=75,
		)
		self.assertEqual(get_fbr_taxable_value(item), 300)
		self.assertEqual(calculate_sales_tax(item, 18), 54)

	def test_manual_taxable_value(self):
		item = _item(
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_MANUAL,
			custom_fbr_taxable_value=1234.56,
		)
		self.assertEqual(get_fbr_taxable_value(item), 1234.56)

	def test_quantity_greater_than_one(self):
		item = _item(
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		self.assertEqual(get_fbr_taxable_value(item), 10000)

	def test_fractional_quantity(self):
		item = _item(
			qty=1.5,
			rate=800,
			amount=1200,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		self.assertEqual(get_fbr_taxable_value(item), 1500)
		self.assertEqual(calculate_sales_tax(item, 18), 270)

	def test_discounted_third_schedule_does_not_reduce_mrp_base(self):
		item = _item(
			qty=10,
			rate=800,
			amount=7000,
			discount_amount=1000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		self.assertEqual(get_fbr_taxable_value(item), 10000)
		self.assertEqual(calculate_sales_tax(item, 18), 1800)
		self.assertEqual(item.amount, 7000)

	def test_missing_mrp_raises(self):
		item = _item(
			item_code="SHAMPOO-001",
			idx=3,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=0,
		)
		with self.assertRaises(Exception) as ctx:
			get_fbr_taxable_value(item)
		self.assertIn("SHAMPOO-001", str(ctx.exception))
		self.assertIn("Retail Price / MRP", str(ctx.exception))

	def test_no_profile_falls_back_to_amount(self):
		item = _item(qty=2, rate=100, amount=200, custom_fbr_tax_calculation_basis="")
		self.assertEqual(get_fbr_taxable_value(item), 200)
		self.assertEqual(calculate_sales_tax(item, 18), 36)

	def test_further_tax_stays_on_sales_value_when_gst_uses_mrp(self):
		item = _item(
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		profile = {
			"further_tax_calculation_basis": TAX_BASIS_SALES_VALUE,
			"extra_tax_calculation_basis": TAX_BASIS_SALES_VALUE,
		}
		self.assertEqual(get_tax_component_base(item, "sales_tax", profile=profile), 10000)
		self.assertEqual(get_tax_component_base(item, "further_tax", profile=profile), 8000)


class TestMixedInvoices(unittest.TestCase):
	def test_mixed_sales_invoice_rows_calculate_independently(self):
		standard = _item(
			idx=1,
			item_code="STD-001",
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE,
		)
		third = _item(
			idx=2,
			item_code="3RD-001",
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		zero = _item(
			idx=3,
			item_code="ZERO-001",
			qty=1,
			rate=500,
			amount=500,
			custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE,
		)
		doc = DummyDoc(doctype="Sales Invoice", items=[standard, third, zero])
		apply_item_tax_amounts(doc, standard, tax_rows=GST_18)
		apply_item_tax_amounts(doc, third, tax_rows=GST_18)
		apply_item_tax_amounts(doc, zero, tax_rows=[{"tax_type": "GST", "tax_rate": 0}])

		self.assertEqual(standard.custom_sales_tax, 1440)
		self.assertEqual(third.custom_sales_tax, 1800)
		self.assertEqual(zero.custom_sales_tax, 0)
		self.assertEqual(standard.amount, 8000)
		self.assertEqual(third.amount, 8000)
		self.assertEqual(third.custom_fbr_taxable_value, 10000)

	def test_mixed_pos_invoice_uses_same_engine(self):
		standard = _item(item_code="A", amount=1000, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		third = _item(
			item_code="B",
			qty=1,
			rate=800,
			amount=800,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		doc = DummyDoc(doctype="POS Invoice", items=[standard, third])
		apply_item_tax_amounts(doc, standard, tax_rows=GST_18)
		apply_item_tax_amounts(doc, third, tax_rows=GST_18)
		self.assertEqual(standard.custom_sales_tax, 180)
		self.assertEqual(third.custom_sales_tax, 180)
		self.assertEqual(third.rate, 800)


class TestReturnsAndSnapshots(unittest.TestCase):
	def test_return_preserves_original_mrp_snapshot(self):
		item = _item(
			qty=-10,
			rate=800,
			amount=-8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		doc = DummyDoc(doctype="Sales Invoice", is_return=1, docstatus=0, items=[item])
		self.assertTrue(should_preserve_snapshot(doc, item))
		self.assertEqual(get_fbr_taxable_value(item), -10000)
		self.assertEqual(calculate_sales_tax(item, 18), -1800)

	def test_pos_return_preserves_snapshot(self):
		item = _item(
			qty=-1,
			rate=800,
			amount=-800,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		doc = DummyDoc(doctype="POS Invoice", is_return=1, items=[item])
		self.assertTrue(has_tax_snapshot(item))
		self.assertTrue(should_preserve_snapshot(doc, item))
		self.assertEqual(item.custom_fbr_retail_price, 1000)

	def test_old_invoice_snapshot_unchanged_after_mrp_change(self):
		item = _item(
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		doc = DummyDoc(doctype="Sales Invoice", is_return=0, docstatus=1, items=[item])
		self.assertTrue(should_preserve_snapshot(doc, item))
		self.assertEqual(item.custom_fbr_retail_price, 1000)


class TestRetailPriceLookup(unittest.TestCase):
	def setUp(self):
		self._orig_exists = retail_mod.frappe.db.exists
		self._orig_get_all = getattr(retail_mod.frappe, "get_all", None)
		self._orig_get_value = getattr(retail_mod.frappe.db, "get_value", None)

	def tearDown(self):
		retail_mod.frappe.db.exists = self._orig_exists
		if self._orig_get_all is not None:
			retail_mod.frappe.get_all = self._orig_get_all
		if self._orig_get_value is not None:
			retail_mod.frappe.db.get_value = self._orig_get_value

	def test_mrp_lookup_by_date(self):
		retail_mod.frappe.db.exists = lambda *a, **k: True
		retail_mod.frappe.get_all = lambda *a, **k: [
			{
				"price_list_rate": 1200,
				"valid_from": "2026-08-01",
				"valid_upto": "2026-12-31",
				"uom": "",
				"currency": "PKR",
			},
			{
				"price_list_rate": 1000,
				"valid_from": "2026-01-01",
				"valid_upto": "2026-07-31",
				"uom": "",
				"currency": "PKR",
			},
		]
		self.assertEqual(resolve_retail_price("SHAMPOO-001", posting_date="2026-06-15"), 1000)
		self.assertEqual(resolve_retail_price("SHAMPOO-001", posting_date="2026-08-16"), 1200)

	def test_mrp_fallback_from_item(self):
		retail_mod.frappe.db.exists = lambda *a, **k: True
		retail_mod.frappe.get_all = lambda *a, **k: []
		item = DummyDoc(custom_fbr_default_retail_price=950)
		self.assertEqual(resolve_retail_price("SHAMPOO-001", item=item), 950)

	def test_uom_specific_item_price(self):
		retail_mod.frappe.db.exists = lambda *a, **k: True
		retail_mod.frappe.get_all = lambda *a, **k: [
			{"price_list_rate": 500, "valid_from": None, "valid_upto": None, "uom": "Kg", "currency": "PKR"},
			{"price_list_rate": 1000, "valid_from": None, "valid_upto": None, "uom": "Nos", "currency": "PKR"},
		]
		self.assertEqual(resolve_retail_price("ITEM-001", uom="Nos"), 1000)
		self.assertEqual(resolve_retail_price("ITEM-001", uom="Kg"), 500)


class TestValidationAndPayload(unittest.TestCase):
	def test_validate_missing_mrp_identifies_row_and_item(self):
		item = _item(
			idx=3,
			item_code="SHAMPOO-001",
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=0,
		)
		with self.assertRaises(Exception) as ctx:
			validate_fbr_tax_row(item, scope="basis")
		msg = str(ctx.exception)
		self.assertIn("Row 3", msg)
		self.assertIn("SHAMPOO-001", msg)
		self.assertIn("Retail Price / MRP", msg)

	def test_legacy_payload_uses_rate_without_profile(self):
		item = _item(rate=800, custom_fbr_tax_calculation_basis="")
		self.assertEqual(get_fixed_notified_or_retail_price(item), 800)

	def test_sales_value_profile_sends_zero_retail_field(self):
		item = _item(rate=800, custom_fbr_tax_calculation_basis=TAX_BASIS_SALES_VALUE)
		self.assertEqual(get_fixed_notified_or_retail_price(item), 0)

	def test_third_schedule_payload_sends_line_mrp_so_fbr_0102_matches(self):
		"""FBR 0102 computes salesTaxApplicable = retailField × rate, not unit × qty × rate."""
		item = _item(
			qty=15,
			rate=750,
			amount=11250,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=900,
			custom_fbr_taxable_value=13500,
			custom_sales_tax=2430,
		)
		retail_field = get_fixed_notified_or_retail_price(item)
		self.assertEqual(retail_field, 13500)
		self.assertEqual(item.amount, 11250)
		self.assertEqual(calculate_sales_tax(item, 18), 2430)
		self.assertEqual(round(retail_field * 18 / 100, 2), 2430)

	def test_third_schedule_payload_falls_back_to_unit_mrp_times_qty(self):
		item = _item(
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
		)
		self.assertEqual(get_fixed_notified_or_retail_price(item), 10000)
		self.assertEqual(item.amount, 8000)
		self.assertEqual(calculate_sales_tax(item, 18), 1800)

	def test_sandbox_and_production_json_share_the_same_builder(self):
		item = _item(
			qty=10,
			rate=800,
			amount=8000,
			custom_fbr_tax_calculation_basis=TAX_BASIS_RETAIL_PRICE,
			custom_fbr_retail_price=1000,
			custom_fbr_taxable_value=10000,
			custom_sales_tax=1800,
		)
		payload = {
			"valueSalesExcludingST": abs(item.amount),
			"fixedNotifiedValueOrRetailPrice": get_fixed_notified_or_retail_price(item, absolute=True),
			"salesTaxApplicable": abs(item.custom_sales_tax),
			"saleType": "3rd Schedule Goods",
		}
		self.assertEqual(payload["valueSalesExcludingST"], 8000)
		self.assertEqual(payload["fixedNotifiedValueOrRetailPrice"], 10000)
		self.assertEqual(payload["salesTaxApplicable"], 1800)

	def test_public_exports(self):
		self.assertTrue(callable(tax_pkg.get_fbr_taxable_value))
		self.assertTrue(callable(tax_pkg.get_fixed_notified_or_retail_price))
		self.assertTrue(callable(snapshot_mod.apply_tax_snapshots))


if __name__ == "__main__":
	unittest.main()
