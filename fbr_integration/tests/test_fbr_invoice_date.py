import datetime
import unittest
from fbr_integration.tests.frappe_test_stub import install_frappe_stub

_frappe = install_frappe_stub(force=True)
_frappe.utils.getdate = lambda d: d if isinstance(d, datetime.date) else datetime.date.fromisoformat(str(d)[:10])

from fbr_integration.fbr_api import (  # noqa: E402
	fbr_error_from_stored_response,
	fbr_safe_invoice_date,
	first_fbr_validation_error,
)


class TestFbrInvoiceDate(unittest.TestCase):
	def test_keeps_past_posting_date(self):
		self.assertEqual(fbr_safe_invoice_date("2026-08-04"), "2026-08-04")

	def test_clamps_future_local_date_to_utc_today(self):
		utc_today = datetime.datetime.now(datetime.timezone.utc).date()
		future = utc_today + datetime.timedelta(days=1)
		self.assertEqual(fbr_safe_invoice_date(future.isoformat()), str(utc_today))

	def test_item_level_0043_is_surfaced(self):
		error, code = first_fbr_validation_error(
			{
				"statusCode": "01",
				"status": "Invalid",
				"errorCode": None,
				"error": "",
				"invoiceStatuses": [
					{
						"itemSNo": "1",
						"statusCode": "01",
						"errorCode": "0043",
						"error": "Invoice date is greater than current date. Please provide valid invoice date.",
					}
				],
			}
		)
		self.assertEqual(code, "0043")
		self.assertIn("greater than current date", error)

	def test_stored_response_json(self):
		raw = """{
		  "validationResponse": {
		    "statusCode": "01",
		    "error": "",
		    "invoiceStatuses": [
		      {"statusCode": "01", "errorCode": "0043", "error": "Invoice date is greater than current date."}
		    ]
		  }
		}"""
		error, code = fbr_error_from_stored_response(raw)
		self.assertEqual(code, "0043")
		self.assertIn("greater than current date", error)


if __name__ == "__main__":
	unittest.main()
