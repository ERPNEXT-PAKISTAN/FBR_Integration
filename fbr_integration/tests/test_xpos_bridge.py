import unittest
from unittest.mock import MagicMock, patch

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

_frappe = install_frappe_stub(force=True)
_frappe.utils.cstr = lambda value=None: "" if value is None else str(value)
_frappe.utils.escape_html = lambda value: (
	str(value or "")
	.replace("&", "&amp;")
	.replace("<", "&lt;")
	.replace(">", "&gt;")
)
_frappe.log_error = lambda *a, **k: None
_frappe.get_traceback = lambda: ""

from fbr_integration import xpos_bridge  # noqa: E402


class TestXposBridge(unittest.TestCase):
	def test_html_path_skips_assets(self):
		self.assertTrue(xpos_bridge._is_xpos_html_path("/xpos"))
		self.assertTrue(xpos_bridge._is_xpos_html_path("/xpos/orders"))
		self.assertFalse(xpos_bridge._is_xpos_html_path("/desk"))
		self.assertFalse(xpos_bridge._is_xpos_html_path("/xpos/assets/index.js"))
		self.assertFalse(xpos_bridge._is_xpos_html_path("/assets/xpos/xpos/index.js"))

	def test_injects_script_before_body_end(self):
		response = MagicMock()
		response.headers = {"Content-Type": "text/html; charset=utf-8"}
		response.direct_passthrough = False
		response.get_data.side_effect = lambda as_text=False: (
			"<html><body>XPOS</body></html>" if as_text else b"<html><body>XPOS</body></html>"
		)
		request = MagicMock(path="/xpos")

		xpos_bridge.inject_xpos_bridge(response=response, request=request)

		html = response.set_data.call_args[0][0]
		self.assertIn('id="fbr-xpos-bridge"', html)
		self.assertIn("xpos_fbr.js", html)
		self.assertIn("</body>", html)
		self.assertLess(html.index("xpos_fbr.js"), html.index("</body>"))

	def test_does_not_inject_twice(self):
		response = MagicMock()
		response.headers = {"Content-Type": "text/html"}
		response.direct_passthrough = False
		response.get_data.side_effect = lambda as_text=False: '<script id="fbr-xpos-bridge"></script>'
		request = MagicMock(path="/xpos")
		xpos_bridge.inject_xpos_bridge(response=response, request=request)
		response.set_data.assert_not_called()

	def test_receipt_block_empty_without_fbr_number(self):
		doc = MagicMock(custom_fbr_invoice_no="", fbr_invoice_number="")
		self.assertEqual(xpos_bridge.fbr_pos_receipt_block(doc), "")

	def test_receipt_block_renders_number_and_qr(self):
		doc = MagicMock(custom_fbr_invoice_no="1234567DIABCDEF", fbr_invoice_number="")
		with patch.object(xpos_bridge, "_qr_data_uri", return_value="data:image/png;base64,AAA"):
			html = xpos_bridge.fbr_pos_receipt_block(doc)
		self.assertIn("1234567DIABCDEF", html)
		self.assertIn("fbr-section", html)
		self.assertIn("data:image/png;base64,AAA", html)

	def test_print_html_inserts_block_once(self):
		src = '<div>notes</div>\n<div class="barcode-section">x</div>'
		once = xpos_bridge._ensure_fbr_block(src)
		self.assertIn("fbr_pos_receipt_block", once)
		self.assertEqual(once, xpos_bridge._ensure_fbr_block(once))
		self.assertLess(once.index("fbr_pos_receipt_block"), once.index("barcode-section"))

	def test_skips_when_xpos_fork_already_has_block(self):
		src = "{{ xpos_fbr_block(doc) }}\n<div class=\"barcode-section\">x</div>"
		self.assertEqual(src, xpos_bridge._ensure_fbr_block(src))


if __name__ == "__main__":
	unittest.main()
