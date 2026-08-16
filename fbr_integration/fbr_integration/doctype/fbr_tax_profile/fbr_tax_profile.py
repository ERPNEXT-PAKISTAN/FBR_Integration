# Copyright (c) 2026, FBR Integration and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.utils import cint

from fbr_integration.taxation.constants import (
	TAX_BASIS_FIXED_NOTIFIED,
	TAX_BASIS_RETAIL_PRICE,
)


class FBRTaxProfile(Document):
	def validate(self):
		if cint(self.requires_retail_price) and self.tax_calculation_basis != TAX_BASIS_RETAIL_PRICE:
			frappe.throw(
				"Requires Retail Price / MRP is checked, so Tax Calculation Basis must be Retail Price / MRP."
			)
		if (
			cint(self.requires_fixed_notified_value)
			and self.tax_calculation_basis != TAX_BASIS_FIXED_NOTIFIED
		):
			frappe.throw(
				"Requires Fixed / Notified Value is checked, so Tax Calculation Basis must be Fixed / Notified Value."
			)
