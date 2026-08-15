from fbr_integration.patches.sync_sale_types_and_item_fbr_links import (
	ZERO_RATE_LEGACY,
	ZERO_RATE_OFFICIAL,
	_rename_sale_type,
)


def execute():
	_rename_sale_type(ZERO_RATE_LEGACY, ZERO_RATE_OFFICIAL)
