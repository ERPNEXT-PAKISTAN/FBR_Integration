from fbr_integration import item_tax_templates
from fbr_integration.fbr_payload_mapping import sync_payload_field_mappings, sync_payload_source_fields
from fbr_integration.print_format_sync import sync_print_formats


def after_install():
	item_tax_templates.sync_item_tax_templates()
	sync_payload_source_fields()
	sync_payload_field_mappings()
	sync_print_formats()
