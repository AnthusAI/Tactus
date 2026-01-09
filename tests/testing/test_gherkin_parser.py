"""
Tests for Gherkin parser.
"""

import pytest

from tactus.testing.gherkin_parser import GherkinParser
from tactus.testing.models import ParsedFeature


def test_parse_simple_feature():
    """Test parsing a simple Gherkin feature."""
    gherkin_text = """
Feature: Simple Feature
  This is a simple feature for testing

  Scenario: Simple Scenario
    Given a precondition
    When an action occurs
    Then an outcome is verified
"""

    parser = GherkinParser()
    feature = parser.parse(gherkin_text)

    assert isinstance(feature, ParsedFeature)
    assert feature.name == "Simple Feature"
    assert "simple feature" in feature.description.lower()
    assert len(feature.scenarios) == 1

    scenario = feature.scenarios[0]
    assert scenario.name == "Simple Scenario"
    assert len(scenario.steps) == 3

    assert scenario.steps[0].keyword == "Given"
    assert scenario.steps[0].message == "a precondition"
    assert scenario.steps[1].keyword == "When"
    assert scenario.steps[1].message == "an action occurs"
    assert scenario.steps[2].keyword == "Then"
    assert scenario.steps[2].message == "an outcome is verified"


def test_parse_feature_with_tags():
    """Test parsing feature with tags."""
    gherkin_text = """
@important @smoke
Feature: Tagged Feature

  @critical
  Scenario: Tagged Scenario
    Given a setup
    Then verify result
"""

    parser = GherkinParser()
    feature = parser.parse(gherkin_text)

    assert "@important" in feature.tags
    assert "@smoke" in feature.tags
    assert "@critical" in feature.scenarios[0].tags


def test_parse_multiple_scenarios():
    """Test parsing feature with multiple scenarios."""
    gherkin_text = """
Feature: Multiple Scenarios

  Scenario: First Scenario
    Given first setup
    Then first result

  Scenario: Second Scenario
    Given second setup
    Then second result
"""

    parser = GherkinParser()
    feature = parser.parse(gherkin_text)

    assert len(feature.scenarios) == 2
    assert feature.scenarios[0].name == "First Scenario"
    assert feature.scenarios[1].name == "Second Scenario"


def test_parse_invalid_gherkin():
    """Test that invalid Gherkin raises error."""
    gherkin_text = "This is not valid Gherkin"

    parser = GherkinParser()
    with pytest.raises(ValueError, match="Invalid Gherkin"):
        parser.parse(gherkin_text)


def test_parse_with_and_but_keywords():
    """Test parsing with And and But keywords."""
    gherkin_text = """
Feature: And/But Keywords

  Scenario: Using And and But
    Given a precondition
    And another precondition
    When an action occurs
    Then an outcome is verified
    And another outcome is verified
    But a negative outcome is not present
"""

    parser = GherkinParser()
    feature = parser.parse(gherkin_text)

    scenario = feature.scenarios[0]
    assert len(scenario.steps) == 6
    assert scenario.steps[1].keyword == "And"
    assert scenario.steps[4].keyword == "And"
    assert scenario.steps[5].keyword == "But"
