from tactus.core.registry import RegistryBuilder


def test_validate_allows_agent_provider_omitted_when_model_is_provider_slash_model():
    builder = RegistryBuilder()
    builder.register_agent(
        "World",
        {
            "model": "openai/gpt-4o-mini",
            "system_prompt": "You are World.",
        },
    )

    result = builder.validate()

    assert result.valid
    assert not [e for e in result.errors if "missing provider" in e.message]


def test_validate_allows_agent_provider_omitted_when_model_is_provider_colon_model():
    builder = RegistryBuilder()
    builder.register_agent(
        "World",
        {
            "model": "openai:gpt-4o-mini",
            "system_prompt": "You are World.",
        },
    )

    result = builder.validate()

    assert result.valid
    assert not [e for e in result.errors if "missing provider" in e.message]


def test_validate_rejects_agent_provider_omitted_when_model_has_no_provider_prefix():
    builder = RegistryBuilder()
    builder.register_agent(
        "World",
        {
            "model": "gpt-4o-mini",
            "system_prompt": "You are World.",
        },
    )

    result = builder.validate()

    assert not result.valid
    assert [e for e in result.errors if "missing provider" in e.message]
