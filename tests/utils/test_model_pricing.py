from tactus.utils.model_pricing import (
    DEFAULT_PRICING,
    get_model_pricing,
    normalize_model_name,
)


def test_normalize_model_name_with_provider_prefix():
    model, provider = normalize_model_name("openai:gpt-4o")
    assert model == "gpt-4o"
    assert provider == "openai"


def test_normalize_model_name_bedrock_format():
    model, provider = normalize_model_name("anthropic.claude-3-5-sonnet-20241022-v2:0")
    assert model == "anthropic.claude-3-5-sonnet-20241022-v2:0"
    assert provider == "bedrock"


def test_normalize_model_name_infers_provider():
    assert normalize_model_name("gpt-4o")[1] == "openai"
    assert normalize_model_name("claude-3-5-sonnet")[1] == "anthropic"
    assert normalize_model_name("gemini-2.5-flash")[1] == "google"


def test_normalize_model_name_respects_provider_hint():
    model, provider = normalize_model_name("custom-model", provider="OpenAI")
    assert model == "custom-model"
    assert provider == "openai"


def test_normalize_model_name_defaults_to_openai_when_unknown():
    model, provider = normalize_model_name("custom-model")
    assert model == "custom-model"
    assert provider == "openai"


def test_get_model_pricing_known_openai_model():
    pricing = get_model_pricing("gpt-4o", provider="openai")
    assert pricing == {"input": 2.50, "output": 10.00}


def test_get_model_pricing_falls_back_to_base_name():
    pricing = get_model_pricing("gpt-4o-2025-01-01", provider="openai")
    assert pricing == {"input": 2.50, "output": 10.00}


def test_get_model_pricing_unknown_model_uses_default():
    pricing = get_model_pricing("unknown-model", provider="openai")
    assert pricing == DEFAULT_PRICING


def test_get_model_pricing_single_token_name_uses_default():
    pricing = get_model_pricing("unknown", provider="openai")
    assert pricing == DEFAULT_PRICING
