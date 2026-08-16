import json
import unittest
from pathlib import Path

from fbr_integration.print_bank import DEFAULT_BANK, get_bank_payment_info


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "print_format.json"


class TestPrintFormats(unittest.TestCase):
	def test_bank_defaults(self):
		self.assertEqual(get_bank_payment_info(), DEFAULT_BANK)
		self.assertEqual(DEFAULT_BANK["account_name"], "ML 88")
		self.assertEqual(DEFAULT_BANK["iban"], "1010122255555")
		self.assertEqual(DEFAULT_BANK["bank"], "Meezan Bank")

	def test_every_print_format_has_same_line_bank_block(self):
		rows = json.loads(FIXTURE.read_text())
		self.assertGreaterEqual(len(rows), 10)
		names = [row["name"] for row in rows]
		self.assertIn("FBR Sales Invoice 3rd Schedule", names)
		self.assertIn("FBR Letterhead-2 3rd Schedule", names)
		for row in rows:
			html = row["html"]
			self.assertIn("Bank Account for Payment.", html, row["name"])
			self.assertIn("<b>Account Name:</b> ML 88", html, row["name"])
			self.assertIn("<b>IBAN Number:</b> 1010122255555", html, row["name"])
			self.assertIn("<b>Bank Name:</b> Meezan Bank", html, row["name"])
			self.assertIn("white-space:nowrap", html, row["name"])
			self.assertNotIn("bank[0].account_name", html, row["name"])

	def test_third_schedule_prints_show_mrp_and_fbr_taxable(self):
		by_name = {row["name"]: row for row in json.loads(FIXTURE.read_text())}
		for name in ("FBR Sales Invoice 3rd Schedule", "FBR Letterhead-2 3rd Schedule"):
			html = by_name[name]["html"]
			self.assertIn(">MRP<", html)
			self.assertIn("custom_fbr_retail_price", html)
			self.assertIn("custom_fbr_taxable_value", html)
			self.assertIn("Taxable (MRP)", html)
			self.assertIn("TAX INVOICE (3rd Schedule)", html)
