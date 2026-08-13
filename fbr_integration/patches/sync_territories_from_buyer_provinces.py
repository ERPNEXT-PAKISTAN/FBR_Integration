import frappe

from fbr_integration.fbr_payload_mapping import (
	DETAIL_DOCTYPE,
	_doctype_available,
	_source_field_link_name,
)
from fbr_integration.territory_sync import sync_territories_from_buyer_provinces


def _remap_buyer_province_to_territory():
	"""Point buyerProvince mapping at Sales Invoice.territory."""
	if not _doctype_available():
		return

	source_field = _source_field_link_name("Sales Invoice", "territory")
	rows = frappe.get_all(
		DETAIL_DOCTYPE,
		filters={"payload_field": "buyerProvince"},
		fields=["name"],
		ignore_permissions=True,
	)
	for row in rows:
		frappe.db.set_value(
			DETAIL_DOCTYPE,
			row.name,
			{
				"source_doctype": "Sales Invoice",
				"source_field": source_field,
				"transform": "FBR Text",
				"current_source": "Sales Invoice.territory",
				"description": (
					"Sales Invoice → Territory (province names synced from Buyer Province). "
					"Fallback: custom_buyer_province, then customer Address state."
				),
			},
			update_modified=False,
		)


def execute():
	created = sync_territories_from_buyer_provinces()
	if created:
		frappe.logger().info(
			"Created Territories from Buyer Province: %s", ", ".join(created)
		)
	_remap_buyer_province_to_territory()
