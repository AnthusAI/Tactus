"""Tests for template resolver."""

from tactus.core.template_resolver import TemplateResolver, resolve_template


def test_template_resolver_replaces_values():
    resolver = TemplateResolver(params={"topic": "AI"}, state={"count": 2})

    result = resolver.resolve("{params.topic} {state.count}")

    assert result == "AI 2"


def test_template_resolver_preserves_missing():
    resolver = TemplateResolver(params={"topic": "AI"})

    result = resolver.resolve("{params.topic} {state.missing}")

    assert result == "AI {state.missing}"


def test_resolve_template_helper():
    result = resolve_template("Hello {params.name}", params={"name": "Ada"})
    assert result == "Hello Ada"


def test_resolve_empty_template():
    resolver = TemplateResolver(params={"topic": "AI"})
    assert resolver.resolve("") == ""


def test_resolve_unknown_namespace_keeps_marker():
    resolver = TemplateResolver(params={"topic": "AI"})
    result = resolver.resolve("{unknown.value}")
    assert result == "{unknown.value}"


def test_resolve_nested_non_dict_keeps_marker():
    resolver = TemplateResolver(params={"topic": "AI"})
    result = resolver.resolve("{params.topic.value}")
    assert result == "{params.topic.value}"


def test_get_value_empty_parts_returns_none():
    resolver = TemplateResolver()

    class EmptyPath:
        def split(self, _sep):
            return []

    assert resolver._get_value(EmptyPath()) is None
