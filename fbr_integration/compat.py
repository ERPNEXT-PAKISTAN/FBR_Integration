"""
Dual Frappe v15 / v16 desk compatibility helpers.

v15: classic Workspace (+ fixtures) is enough.
v16: also needs Workspace.type/app/module, Workspace Sidebar, and Desktop Icon.
Detect features by DocType existence so the same app works on both majors.
"""

from __future__ import annotations

import frappe

APP = "fbr_integration"
WORKSPACE = "FBR Pakistan"
SIDEBAR = "FBR Pakistan"
ICON_LABEL = "FBR Integration"
ICON_LOGO = "/assets/fbr_integration/images/fbr/DI_invoicing.png"


def workspace_route() -> str:
	"""v15 uses /app/<workspace>; v16 uses /desk/<workspace>."""
	slug = frappe.scrub(WORKSPACE).replace("_", "-")
	return f"/desk/{slug}" if has_v16_desk() else f"/app/{slug}"


def frappe_major() -> int:
	try:
		return int(str(frappe.__version__).split(".", 1)[0])
	except Exception:
		return 0


def has_v16_desk() -> bool:
	"""True when Workspace Sidebar exists (v16 desk navigation)."""
	return bool(frappe.db.exists("DocType", "Workspace Sidebar"))


def ensure_desk_navigation():
	"""
	Idempotent. Safe on v15 (no-op for v16-only entities) and v16.
	Call from after_install / after_migrate.
	"""
	_ensure_workspace_fields()
	if not has_v16_desk():
		return

	_ensure_workspace_sidebar()
	_ensure_desktop_icon()
	frappe.db.commit()


def _ensure_workspace_fields():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	meta = frappe.get_meta("Workspace")
	updates = {}
	if meta.has_field("type") and not frappe.db.get_value("Workspace", WORKSPACE, "type"):
		updates["type"] = "Workspace"
	if meta.has_field("app") and not frappe.db.get_value("Workspace", WORKSPACE, "app"):
		updates["app"] = APP
	if meta.has_field("module"):
		module = frappe.db.get_value("Workspace", WORKSPACE, "module")
		if not module:
			updates["module"] = "FBR Integration"
	if updates:
		frappe.db.set_value("Workspace", WORKSPACE, updates, update_modified=False)


def _ensure_workspace_sidebar():
	if not frappe.db.exists("Workspace", WORKSPACE):
		return

	workspace = frappe.get_doc("Workspace", WORKSPACE)
	items = _sidebar_items_from_workspace(workspace)

	if frappe.db.exists("Workspace Sidebar", SIDEBAR):
		sidebar = frappe.get_doc("Workspace Sidebar", SIDEBAR)
		sidebar.items = []
		for row in items:
			sidebar.append("items", row)
		sidebar.header_icon = workspace.icon or "file-large"
		sidebar.app = APP
		sidebar.module = "FBR Integration"
		sidebar.standard = 1
		sidebar.flags.ignore_links = True
		sidebar.save(ignore_permissions=True)
		return

	sidebar = frappe.new_doc("Workspace Sidebar")
	sidebar.title = SIDEBAR
	sidebar.name = SIDEBAR
	sidebar.header_icon = workspace.icon or "file-large"
	sidebar.app = APP
	sidebar.module = "FBR Integration"
	sidebar.standard = 1
	for row in items:
		sidebar.append("items", row)
	sidebar.flags.ignore_links = True
	sidebar.insert(ignore_permissions=True)


def _sidebar_items_from_workspace(workspace) -> list[dict]:
	items = [
		{
			"label": "Home",
			"link_to": WORKSPACE,
			"link_type": "Workspace",
			"type": "Link",
			"icon": "home",
			"child": 0,
			"indent": 0,
			"collapsible": 1,
		}
	]

	for link in workspace.links or []:
		if link.type == "Card Break":
			items.append(
				{
					"label": link.label,
					"type": "Section Break",
					"link_type": "DocType",
					"icon": link.icon or "",
					"child": 0,
					"indent": 0,
					"collapsible": 1,
				}
			)
			continue

		if link.type != "Link" or not link.link_to:
			continue

		link_type = link.link_type or "DocType"
		if getattr(link, "is_query_report", 0) and link_type == "Report":
			link_type = "Report"

		items.append(
			{
				"label": link.label,
				"link_to": link.link_to,
				"link_type": link_type,
				"type": "Link",
				"icon": link.icon or "",
				"child": 1,
				"indent": 1,
				"collapsible": 1,
			}
		)

	return items


def _ensure_desktop_icon():
	if not frappe.db.exists("DocType", "Desktop Icon"):
		return

	meta = frappe.get_meta("Desktop Icon")
	# v16 App icon shape; skip on older Desktop Icon schemas
	if not meta.has_field("icon_type"):
		return

	values = {
		"label": ICON_LABEL,
		"icon_type": "App",
		"link_type": "External",
		"link": workspace_route(),
		"app": APP,
		"logo_url": ICON_LOGO,
		"standard": 1,
		"hidden": 0,
		"bg_color": "gray" if meta.has_field("bg_color") else None,
		"sidebar": SIDEBAR if meta.has_field("sidebar") else None,
	}
	values = {k: v for k, v in values.items() if v is not None}

	if frappe.db.exists("Desktop Icon", ICON_LABEL):
		frappe.db.set_value("Desktop Icon", ICON_LABEL, values, update_modified=False)
		return

	doc = frappe.new_doc("Desktop Icon")
	doc.update(values)
	doc.flags.ignore_links = True
	doc.insert(ignore_permissions=True)
