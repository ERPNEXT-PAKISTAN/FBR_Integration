from pathlib import Path
import re

import frappe


SCENARIO_SOURCE_PATH = (
	Path(__file__).resolve().parents[1] / "scenario_data" / "source" / "DI_Scenarios_Summary.txt"
)


def _load_canonical_scenarios():
	canonical = {}
	pattern = re.compile(r"^(SN\d{3}):\s*(.+)$")

	if not SCENARIO_SOURCE_PATH.exists():
		return canonical

	for line in SCENARIO_SOURCE_PATH.read_text().splitlines():
		match = pattern.match(line.strip())
		if not match:
			continue
		scenario_id, scenario_detail = match.groups()
		canonical[scenario_id] = scenario_detail.strip()

	return canonical


def execute():
	canonical = _load_canonical_scenarios()
	if not canonical:
		return

	for row in frappe.get_all("Scenario ID", fields=["name", "scenario_id"], limit_page_length=0):
		scenario_id = (row.scenario_id or "").strip().upper()
		scenario_detail = canonical.get(scenario_id)
		if not scenario_detail:
			continue

		expected_name = f"{scenario_id} - {scenario_detail}"
		current_name = (row.name or "").strip()
		if current_name == expected_name:
			continue

		frappe.delete_doc("Scenario ID", row.name, ignore_permissions=True, force=1)

	frappe.clear_cache(doctype="Scenario ID")
