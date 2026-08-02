"""Lean after_migrate orchestration with versioned heavy syncs."""

from __future__ import annotations

import frappe

from fbr_integration.compat import ensure_desk_navigation
from fbr_integration.fbr_payload_mapping import (
	sync_payload_field_mappings,
	sync_payload_fields,
	sync_payload_source_fields,
)
from fbr_integration.item_tax_templates import sync_item_tax_templates
from fbr_integration.print_format_sync import sync_print_formats

# Bump when fixture/sync logic changes and a full resync is required.
FBR_SYNC_VERSION = "2026.08.02"


def run_after_migrate():
	"""Always refresh desk nav; run heavy syncs only when version changes or empty."""
	ensure_desk_navigation()
	sync_print_formats()

	current = frappe.db.get_default("fbr_integration_sync_version")
	needs_full = current != FBR_SYNC_VERSION
	needs_seed = _mapping_tables_empty()

	if needs_full or needs_seed:
		sync_item_tax_templates()
		sync_payload_fields()
		sync_payload_source_fields()
		sync_payload_field_mappings()
		frappe.db.set_default("fbr_integration_sync_version", FBR_SYNC_VERSION)
		frappe.db.commit()


def _mapping_tables_empty() -> bool:
	for dt in ("FBR Payload Field", "FBR Payload Source Field"):
		if frappe.db.exists("DocType", dt) and not frappe.db.count(dt):
			return True
	return False
