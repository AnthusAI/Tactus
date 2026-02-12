"""BDD spec runner for Tactus stdlib modules.

Discovers all .spec.tac files under tactus/stdlib/tac/ and runs their
BDD specifications through the test runner with mocked agents.

This is the stdlib counterpart of tests/testing/test_all_examples.py.
"""

import pytest
from pathlib import Path

from tactus.testing.test_runner import TactusTestRunner
from tactus.validation import TactusValidator

STDLIB_TAC_DIR = Path("tactus/stdlib/tac")


def collect_stdlib_specs():
    """Discover all .spec.tac files under the stdlib tac directory."""
    specs = []
    for spec_file in sorted(STDLIB_TAC_DIR.rglob("*.spec.tac")):
        content = spec_file.read_text()
        if "Specification(" in content or "Specifications(" in content:
            specs.append({"file": spec_file, "id": spec_file.stem})
    return specs


STDLIB_SPECS = collect_stdlib_specs()


class TestStdlibSpecs:
    @pytest.mark.parametrize("spec", STDLIB_SPECS, ids=lambda x: x["id"])
    def test_stdlib_spec_validates(self, spec):
        """Validate that each stdlib spec file passes syntax/semantic checks."""
        validator = TactusValidator()
        result = validator.validate_file(str(spec["file"]))
        assert result.valid, f"Validation failed for {spec['id']}: {result.errors}"

    @pytest.mark.parametrize("spec", STDLIB_SPECS, ids=lambda x: x["id"])
    @pytest.mark.bdd
    @pytest.mark.xdist_group(name="behave_tests")
    def test_stdlib_spec_bdd(self, spec):
        """Run BDD specifications for each stdlib spec file."""
        validator = TactusValidator()
        result = validator.validate_file(str(spec["file"]))
        assert result.valid, f"Validation failed for {spec['id']}: {result.errors}"

        runner = TactusTestRunner(spec["file"], mocked=True)
        runner.setup(
            result.registry.gherkin_specifications,
            custom_steps_dict=result.registry.custom_steps,
        )
        try:
            test_result = runner.run_tests(parallel=False)
            assert test_result.total_scenarios > 0, f"No scenarios found in {spec['id']}"
            assert test_result.failed_scenarios == 0, (
                f"BDD tests failed for {spec['id']}: "
                f"{test_result.failed_scenarios}/{test_result.total_scenarios} failed"
            )
        finally:
            runner.cleanup()


def test_stdlib_spec_coverage():
    """Ensure we have stdlib specs to test."""
    assert (
        len(STDLIB_SPECS) >= 4
    ), f"Only {len(STDLIB_SPECS)} stdlib specs found, expected at least 4"
