import unittest
from unittest.mock import patch

from fbr_integration.tests.frappe_test_stub import install_frappe_stub

install_frappe_stub()

from fbr_integration import compat  # noqa: E402


class TestCompat(unittest.TestCase):
	def test_desk_prefix_v15_uses_app(self):
		with patch.object(compat, "has_v16_desk", return_value=False):
			self.assertEqual(compat.desk_prefix(), "/app")
			self.assertEqual(compat.desk_path("financial-dashboard"), "/app/financial-dashboard")

	def test_desk_prefix_v16_uses_desk(self):
		with patch.object(compat, "has_v16_desk", return_value=True):
			self.assertEqual(compat.desk_prefix(), "/desk")
			self.assertEqual(compat.desk_path("/app/fbr-pakistan"), "/desk/fbr-pakistan")
			self.assertEqual(compat.desk_path("desk/fbr-usage-guide"), "/desk/fbr-usage-guide")

	def test_workspace_route_scrubs_name(self):
		with patch.object(compat, "has_v16_desk", return_value=False):
			self.assertEqual(compat.workspace_route(), "/app/fbr-pakistan")


if __name__ == "__main__":
	unittest.main()
