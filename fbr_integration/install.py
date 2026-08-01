import frappe

from fbr_integration import item_tax_templates
from fbr_integration.compat import ensure_desk_navigation
from fbr_integration.fbr_payload_mapping import (
	sync_payload_field_mappings,
	sync_payload_fields,
	sync_payload_source_fields,
)
from fbr_integration.print_format_sync import sync_print_formats


def after_install():
	# Fixtures (Custom Fields / Workspace) must exist before mappings and v16 desk assets.
	from frappe.utils.fixtures import sync_fixtures

	sync_fixtures("fbr_integration")
	frappe.clear_cache()

	item_tax_templates.sync_item_tax_templates()
	sync_payload_fields()
	sync_payload_source_fields()
	sync_payload_field_mappings()
	sync_print_formats()

	# v15: no-op for sidebar/icon. v16: create Workspace Sidebar + Desktop Icon.
	ensure_desk_navigation()
