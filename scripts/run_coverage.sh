#!/usr/bin/env bash
set -euo pipefail

coverage erase

coverage run --parallel-mode -m pytest
after_pytest=$?

coverage run --parallel-mode -m behave

coverage combine
coverage report
coverage html
coverage json -o coverage.json

/opt/anaconda3/bin/python - <<'PY'
import json

with open("coverage.json") as coverage_file:
    coverage_data = json.load(coverage_file)

percent_covered = float(coverage_data["totals"]["percent_covered"])

def coverage_color(percentage: float) -> str:
    if percentage >= 95:
        return "brightgreen"
    if percentage >= 90:
        return "green"
    if percentage >= 80:
        return "yellowgreen"
    if percentage >= 70:
        return "yellow"
    if percentage >= 60:
        return "orange"
    return "red"

badge_payload = {
    "schemaVersion": 1,
    "label": "coverage",
    "message": f"{percent_covered:.1f}%",
    "color": coverage_color(percent_covered),
}

with open("coverage_badge.json", "w") as badge_file:
    json.dump(badge_payload, badge_file)
    badge_file.write("\n")
PY

exit ${after_pytest}
