import frappe

from fbr_integration import item_tax_templates
from fbr_integration.fbr_payload_mapping import (
	sync_payload_field_mappings,
	sync_payload_fields,
	sync_payload_source_fields,
)
from fbr_integration.print_format_sync import sync_print_formats


def after_install():
	# Fixtures (Custom Fields) must exist before payload mappings link to them.
	from frappe.utils.fixtures import sync_fixtures

	sync_fixtures("fbr_integration")
	frappe.clear_cache()

	item_tax_templates.sync_item_tax_templates()
	sync_payload_fields()
	sync_payload_source_fields()
	sync_payload_field_mappings()
	sync_print_formats()
