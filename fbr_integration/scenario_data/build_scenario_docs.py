import json
import re
from pathlib import Path

SOURCE_DIR = Path(__file__).resolve().parent / "source"
SOURCE_TEXT_FILE = SOURCE_DIR / "DI_Scenarios_Summary.txt"
OUTPUT_DIR = Path(__file__).resolve().parents[1] / "public" / "scenario_docs"


def validate_scenario(scenario):
	"""Validate required fields in parsed scenario."""
	errorrs = []

	if not scenario.get("id") or not re.match(r"^SN\d{3}$", scenario["id"]):
		errorrs.append(f"Invalid scenario ID: {scenario.get('id')}")

	if not scenario.get("title"):
		errorrs.append(f"Missing title in scenario {scenario.get('id')}")

	if not scenario.get("description"):
		errorrs.append(f"Missing description in scenario {scenario.get('id')}")

	if not isinstance(scenario.get("sample"), dict):
		errorrs.append(f"Invalid sample (must be JSON object) in {scenario.get('id')}")
	else:
		sample = scenario["sample"]
		required_sample_keys = ["invoiceType", "scenarioId", "items"]
		for key in required_sample_keys:
			if key not in sample:
				errorrs.append(f"Missing required field '{key}' in sample payload for {scenario.get('id')}")

	if errorrs:
		raise ValueError(f"Validation failed for {scenario.get('id')}:\n" + "\n".join(errorrs))


def parse_scenarios(raw_text):
	scenarios = []
	parts = re.split(r"\n(?=SN\d{3}:)", raw_text.strip())

	for part in parts:
		part = part.strip()
		if not part:
			continue

		lines = part.splitlines()
		header = lines[0].strip()
		match = re.match(r"^(SN\d{3}):\s*(.+)$", header)
		if not match:
			continue

		scenario_id = match.group(1)
		title = match.group(2).strip()
		json_start = part.find("{")
		json_end = part.rfind("}") + 1

		if json_start == -1 or json_end <= json_start:
			raise ValueError(f"Missing JSON payload for {scenario_id}")

		description = part[len(header) : json_start].strip()
		sample = json.loads(part[json_start:json_end])
		scenario = {
			"id": scenario_id,
			"title": title,
			"description": description,
			"sample": sample,
		}
		validate_scenario(scenario)
		scenarios.append(scenario)

	return scenarios


def write_scenarios(scenarios):
	OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

	for scenario in scenarios:
		output_file = OUTPUT_DIR / f"{scenario['id']}.json"
		output_file.write_text(json.dumps(scenario, indent=2) + "\n", encoding="utf-8")

	index_data = [
		{
			"id": scenario["id"],
			"title": scenario["title"],
			"description": scenario["description"],
		}
		for scenario in scenarios
	]
	index_file = OUTPUT_DIR / "index.json"
	index_file.write_text(json.dumps(index_data, indent=2) + "\n", encoding="utf-8")


def main():
	try:
		print(f"Building FBR scenario catalog from {SOURCE_TEXT_FILE}...")

		if not SOURCE_TEXT_FILE.exists():
			raise FileNotFoundError(f"Source file not found: {SOURCE_TEXT_FILE}")

		raw_text = SOURCE_TEXT_FILE.read_text(encoding="utf-8")
		print(f"Source file size: {len(raw_text)} bytes")

		scenarios = parse_scenarios(raw_text)
		print(f"✓ Parsed {len(scenarios)} scenarios")

		write_scenarios(scenarios)
		print(f"✓ Wrote {len(scenarios)} scenario documents to {OUTPUT_DIR}")
		print(f"✓ Generated index catalog at {OUTPUT_DIR / 'index.json'}")

		print(f"\nBuild successful: {len(scenarios)} FBR scenarios ready for deployment")
		return 0
	except FileNotFoundError as e:
		print(f"FILE ERROR: {e}", file=__import__("sys").stderr)
		return 1
	except json.JSONDecodeError as e:
		print(
			f"JSON PARSE ERROR: {e}\nCheck scenario source file for invalid JSON.",
			file=__import__("sys").stderr,
		)
		return 1
	except ValueError as e:
		print(f"VALIDATION ERROR: {e}\nSee above for details.", file=__import__("sys").stderr)
		return 1
	except Exception as e:
		print(f"UNEXPECTED ERROR: {e}", file=__import__("sys").stderr)
		return 1


if __name__ == "__main__":
	main()
