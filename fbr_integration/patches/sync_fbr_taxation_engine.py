from fbr_integration.taxation.fields import sync_fbr_taxation_fields
from fbr_integration.taxation.seed import sync_fbr_taxation_masters


def execute():
	sync_fbr_taxation_fields()
	sync_fbr_taxation_masters()
