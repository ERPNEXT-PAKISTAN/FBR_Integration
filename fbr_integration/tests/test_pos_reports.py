import unittest
from unittest.mock import MagicMock

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

_frappe = install_frappe_stub(force=True)
_frappe.db.has_column = lambda dt, col: col in {
	"custom_fbr_invoice_no",
	"fbr_invoice_number",
	"custom_fbr_invoice_status",
}
_frappe.db.exists = lambda *a, **k: True
_frappe.utils.getdate = lambda v: v

from fbr_integration import pos_reports  # noqa: E402


class TestPosReports(unittest.TestCase):
	def test_fbr_no_sql_uses_both_fields(self):
		sql = pos_reports.fbr_no_sql("si", "Sales Invoice")
		self.assertIn("custom_fbr_invoice_no", sql)
		self.assertIn("fbr_invoice_number", sql)

	def test_sent_filter_requires_number(self):
		values = {}
		filters = MagicMock(company=None, pos_profile=None, customer=None, from_date=None, to_date=None)
		filters.get = lambda key, default=None: "Sent" if key == "fbr_status" else default
		conds = pos_reports.pos_filters_sql("si", filters, values, "Sales Invoice")
		self.assertTrue(any("!= ''" in c for c in conds))

	def test_not_sent_filter(self):
		values = {}
		filters = MagicMock()
		filters.get = lambda key, default=None: "Not Sent" if key == "fbr_status" else default
		conds = pos_reports.pos_filters_sql("si", filters, values, "Sales Invoice")
		self.assertTrue(any("= ''" in c for c in conds))


if __name__ == "__main__":
	unittest.main()
