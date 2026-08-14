from fbr_integration.compat import ensure_desk_navigation
from fbr_integration.workspace_pos import ensure_pos_workspace_links


def execute():
	ensure_pos_workspace_links()
	ensure_desk_navigation()
