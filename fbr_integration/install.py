import frappe

from fbr_integration import item_tax_templates
from fbr_integration.compat import cleanup_desk_navigation, ensure_desk_navigation
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

	from fbr_integration.pos_invoice_fields import sync_pos_invoice_fbr_fields

	sync_pos_invoice_fbr_fields()

	from fbr_integration.tax_withholding_sync import sync_withholding

	sync_withholding()
	sync_payload_fields()
	sync_payload_source_fields()
	sync_payload_field_mappings()
	sync_print_formats()

	from fbr_integration.xpos_bridge import sync_xpos_print_formats

	sync_xpos_print_formats()

	from fbr_integration.workspace_pos import ensure_pos_workspace_links

	ensure_pos_workspace_links()
	ensure_desk_navigation()


def before_uninstall():
	"""Remove desk assets this app created so they don't linger after uninstall."""
	cleanup_desk_navigation()
	frappe.db.commit()
