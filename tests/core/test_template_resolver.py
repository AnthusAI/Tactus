from tactus.core.template_resolver import TemplateResolver


def test_jinja2_templates_render_with_provided_context():
    resolver = TemplateResolver(mode="jinja2")
    template = "Hello {{ input.name }} from {{ locals.region }}!"
    context = {"input": {"name": "Ada"}, "locals": {"region": "London"}}

    assert resolver.render(template, context) == "Hello Ada from London!"


def test_plain_mode_leaves_template_unchanged():
    resolver = TemplateResolver(mode="plain")
    template = "Hello {{ input.name }}"

    assert resolver.render(template, {"input": {"name": "Grace"}}) == template


def test_missing_variables_return_template_without_rendering():
    resolver = TemplateResolver(mode="jinja2")
    template = "Hello {{ missing.value }}"

    assert resolver.render(template, {"input": {"name": "Ada"}}) == template
