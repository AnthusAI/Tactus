"""
Gherkin parser integration using gherkin-official library.
"""

import logging
from typing import Optional

try:
    from gherkin.parser import Parser
    from gherkin.token_scanner import TokenScanner

    GHERKIN_AVAILABLE = True
except ImportError:
    GHERKIN_AVAILABLE = False

from .models import ParsedStep, ParsedScenario, ParsedFeature


logger = logging.getLogger(__name__)


class GherkinParser:
    """
    Parses Gherkin text into structured Pydantic models.

    Uses the official Gherkin parser library for accurate parsing.
    """

    def __init__(self):
        if not GHERKIN_AVAILABLE:
            raise ImportError(
                "gherkin-official library not installed. "
                "Install with: pip install gherkin-official"
            )
        self.parser = Parser()

    def parse(self, gherkin_text: str) -> ParsedFeature:
        """
        Parse Gherkin text into a ParsedFeature model.

        Args:
            gherkin_text: Raw Gherkin feature text

        Returns:
            ParsedFeature with all scenarios and steps

        Raises:
            ValueError: If Gherkin syntax is invalid
        """
        try:
            scanner = TokenScanner(gherkin_text)
            gherkin_document = self.parser.parse(scanner)

            if not gherkin_document or not gherkin_document.get("feature"):
                raise ValueError("No feature found in Gherkin text")

            return self._convert_to_pydantic(gherkin_document)

        except Exception as e:
            logger.error(f"Failed to parse Gherkin: {e}")
            raise ValueError(f"Invalid Gherkin syntax: {e}")

    def _convert_to_pydantic(self, gherkin_document: dict) -> ParsedFeature:
        """Convert Gherkin parser output to Pydantic models."""
        feature_data = gherkin_document["feature"]

        # Extract feature metadata
        feature_name = feature_data.get("name", "Unnamed Feature")
        feature_description = feature_data.get("description", "")
        feature_tags = [tag["name"] for tag in feature_data.get("tags", [])]
        feature_line = feature_data.get("location", {}).get("line")

        # Parse scenarios
        scenarios = []
        for child in feature_data.get("children", []):
            if child.get("scenario"):
                scenario = self._parse_scenario(child["scenario"])
                scenarios.append(scenario)

        return ParsedFeature(
            name=feature_name,
            description=feature_description,
            scenarios=scenarios,
            tags=feature_tags,
            line=feature_line,
        )

    def _parse_scenario(self, scenario_data: dict) -> ParsedScenario:
        """Parse a scenario from Gherkin parser output."""
        scenario_name = scenario_data.get("name", "Unnamed Scenario")
        scenario_tags = [tag["name"] for tag in scenario_data.get("tags", [])]
        scenario_line = scenario_data.get("location", {}).get("line")

        # Parse steps
        steps = []
        for step_data in scenario_data.get("steps", []):
            step = self._parse_step(step_data)
            steps.append(step)

        return ParsedScenario(
            name=scenario_name,
            tags=scenario_tags,
            steps=steps,
            line=scenario_line,
        )

    def _parse_step(self, step_data: dict) -> ParsedStep:
        """Parse a step from Gherkin parser output."""
        keyword = step_data.get("keyword", "").strip()
        text = step_data.get("text", "")
        line = step_data.get("location", {}).get("line")

        return ParsedStep(
            keyword=keyword,
            text=text,
            line=line,
        )


def parse_gherkin(gherkin_text: str) -> Optional[ParsedFeature]:
    """
    Convenience function to parse Gherkin text.

    Args:
        gherkin_text: Raw Gherkin feature text

    Returns:
        ParsedFeature or None if parsing fails
    """
    try:
        parser = GherkinParser()
        return parser.parse(gherkin_text)
    except Exception as e:
        logger.error(f"Failed to parse Gherkin: {e}")
        return None
