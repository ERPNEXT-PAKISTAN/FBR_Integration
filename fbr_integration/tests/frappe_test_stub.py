"""Shared lightweight frappe stub for offline unit tests."""

from __future__ import annotations

import sys
import types


class FakePermissionError(Exception):
	pass


def install_frappe_stub(*, version: str = "16.0.0", force: bool = False):
	existing = sys.modules.get("frappe")
	if existing is not None and not force and getattr(existing, "__fbr_test_stub__", False):
		return existing
	if existing is not None and not force and hasattr(existing, "get_doc"):
		# Real frappe already loaded (bench test run).
		return existing

	frappe = types.ModuleType("frappe")
	frappe.__fbr_test_stub__ = True
	frappe.__path__ = []
	frappe.__version__ = version
	frappe.whitelist = lambda *args, **kwargs: (lambda fn: fn)
	frappe.PermissionError = FakePermissionError
	frappe.safe_decode = lambda value: value
	frappe._ = lambda x: x
	frappe.scrub = lambda s: str(s or "").lower().replace(" ", "_")
	frappe.session = types.SimpleNamespace(user="Administrator")
	frappe.get_roles = lambda: ["System Manager"]
	frappe.has_permission = lambda *a, **k: True
	frappe.db = types.SimpleNamespace(exists=lambda *a, **k: False)

	def _throw(*args, **kwargs):
		exc_type = kwargs.get("exc")
		if exc_type is None and len(args) > 1 and isinstance(args[1], type):
			exc_type = args[1]
		raise (exc_type or Exception)(args[0] if args else "error")

	frappe.throw = _throw

	utils = types.ModuleType("frappe.utils")
	utils.cint = lambda value=0: int(value or 0)
	frappe.utils = utils

	sys.modules["frappe"] = frappe
	sys.modules["frappe.utils"] = utils
	return frappe
