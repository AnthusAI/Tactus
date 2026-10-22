"""Declared output fields come back in their declared types, not as the strings DSPy returns."""

from tactus.dspy.agent import DSPyAgentHandle

from tests.dspy.test_agent_execution import _make_agent

SCHEMA = {
    "title": {"type": "string", "required": True},
    "notability": {"type": "number", "required": True},
    "count": {"type": "integer", "required": False},
    "precedential": {"type": "boolean", "required": False},
    "corrections": {"type": "array", "required": True},
    "detail": {"type": "object", "required": False},
}


def test_string_values_become_their_declared_types(monkeypatch):
    agent = _make_agent(monkeypatch, output_schema=SCHEMA)

    typed = agent._typed_output(
        {
            "title": "4",
            "notability": "4",
            "count": "3",
            "precedential": "True",
            "corrections": "['Qualified the holding', 'Fixed the date']",
            "detail": '{"pages": 41}',
            "extra": "kept",
        }
    )

    assert typed == {
        "title": "4",
        "notability": 4,
        "count": 3,
        "precedential": True,
        "corrections": ["Qualified the holding", "Fixed the date"],
        "detail": {"pages": 41},
        "extra": "kept",
    }


def test_values_that_do_not_parse_stay_as_they_are(monkeypatch):
    agent = _make_agent(monkeypatch, output_schema=SCHEMA)

    typed = agent._typed_output({"notability": "high", "corrections": "none", "detail": "[1]"})

    assert typed == {"notability": "high", "corrections": "none", "detail": "[1]"}


def test_numbers_keep_their_fraction():
    assert DSPyAgentHandle._typed_field_value("2.5", "number") == 2.5
    assert DSPyAgentHandle._typed_field_value(3, "number") == 3


def test_an_agent_without_declared_output_is_unchanged(monkeypatch):
    agent = _make_agent(monkeypatch)
    assert agent._typed_output({"response": "4"}) == {"response": "4"}
