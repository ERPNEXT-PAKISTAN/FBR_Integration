from fbr_integration import item_tax_templates
from fbr_integration.print_format_sync import sync_print_formats


def after_install():
	item_tax_templates.sync_item_tax_templates()
	sync_print_formats()
