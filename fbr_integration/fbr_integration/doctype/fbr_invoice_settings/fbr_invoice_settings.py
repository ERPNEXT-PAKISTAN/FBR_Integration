# Copyright (c) 2026, FBR Integration and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class FBRInvoiceSettings(Document):
	def validate(self):
		self._validate_pos_credentials()

	def _validate_pos_credentials(self):
		seen_profiles = set()
		seen_pos_ids = set()
		for row in self.get("pos_credentials") or []:
			profile = (row.pos_profile or "").strip()
			pos_id = (row.fbr_pos_id or "").strip()
			if not profile:
				continue
			if profile in seen_profiles:
				frappe.throw(_("POS Profile {0} is listed more than once in POS Credentials.").format(profile))
			seen_profiles.add(profile)
			if pos_id:
				key = pos_id.upper()
				if key in seen_pos_ids:
					frappe.throw(_("FBR POS ID {0} is used on more than one POS Credential row.").format(pos_id))
				seen_pos_ids.add(key)
