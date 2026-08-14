"""Add a POS card (order history + reports) to the FBR Pakistan workspace."""

from __future__ import annotations

import json

import frappe

WORKSPACE = "FBR Pakistan"
POS_CARD = "POS"
SKIP_LINK_KEYS = {"name", "owner", "creation", "modified", "modified_by", "parent", "parentfield", "parenttype", "idx", "docstatus"}
POS_LINKS = [
	{"type": "Card Break", "label": POS_CARD, "link_type": "DocType", "hidden": 0, "link_count": 8},
	{
		"type": "Link",
		"label": "Point of Sale",
		"link_to": "point-of-sale",
		"link_type": "Page",
		"hidden": 0,
	},
	{"type": "Link", "label": "POS Profile", "link_to": "POS Profile", "link_type": "DocType", "hidden": 0},
	{
		"type": "Link",
		"label": "POS Opening Entry",
		"link_to": "POS Opening Entry",
		"link_type": "DocType",
		"hidden": 0,
	},
	{
		"type": "Link",
		"label": "POS Closing Entry",
		"link_to": "POS Closing Entry",
		"link_type": "DocType",
		"hidden": 0,
	},
	{
		"type": "Link",
		"label": "FBR POS Order History",
		"link_to": "FBR POS Order History",
		"link_type": "Report",
		"is_query_report": 1,
		"hidden": 0,
	},
	{
		"type": "Link",
		"label": "FBR POS Sales Summary",
		"link_to": "FBR POS Sales Summary",
		"link_type": "Report",
		"is_query_report": 1,
		"hidden": 0,
	},
	{
		"type": "Link",
		"label": "FBR POS Item Wise",
		"link_to": "FBR POS Item Wise",
		"link_type": "Report",
		"is_query_report": 1,
		"hidden": 0,
	},
	{
		"type": "Link",
		"label": "FBR POS Closing Summary",
		"link_to": "FBR POS Closing Summary",
		"link_type": "Report",
		"is_query_report": 1,
		"hidden": 0,
	},
]


def ensure_pos_workspace_links():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	ws = frappe.get_doc("Workspace", WORKSPACE)
	labels = [row.label for row in ws.links]
	if POS_CARD not in labels:
		insert_at = next((i for i, row in enumerate(ws.links) if row.label == "Reports"), len(ws.links))
		rows = [_clean_link(row.as_dict()) for row in ws.links]
		rows[insert_at:insert_at] = POS_LINKS
		ws.set("links", [])
		for row in rows:
			ws.append("links", row)
	else:
		existing = set(labels)
		missing = [row for row in POS_LINKS if row.get("type") == "Link" and row["label"] not in existing]
		if missing:
			idx = next(i for i, row in enumerate(ws.links) if row.label == POS_CARD)
			rows = [_clean_link(row.as_dict()) for row in ws.links]
			for offset, payload in enumerate(missing, start=1):
				rows.insert(idx + offset, payload)
			ws.set("links", [])
			for row in rows:
				ws.append("links", row)

	_ensure_pos_card_in_content(ws)
	ws.flags.ignore_links = True
	ws.flags.ignore_permissions = True
	ws.save(ignore_permissions=True)


def _clean_link(row: dict) -> dict:
	return {k: v for k, v in row.items() if k not in SKIP_LINK_KEYS and v is not None}


def _ensure_pos_card_in_content(ws):
	raw = ws.content or "[]"
	try:
		blocks = json.loads(raw)
	except Exception:
		return
	if any((b.get("data") or {}).get("card_name") == POS_CARD for b in blocks):
		return
	card = {"id": "pos_card", "type": "card", "data": {"card_name": POS_CARD, "col": 4}}
	insert_at = next(
		(i + 1 for i, b in enumerate(blocks) if (b.get("data") or {}).get("card_name") == "Documents"),
		len(blocks),
	)
	blocks.insert(insert_at, card)
	ws.content = json.dumps(blocks)
