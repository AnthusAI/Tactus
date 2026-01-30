from tactus.providers.bedrock import BedrockProvider
from tactus.providers.google import GoogleProvider
from tactus.providers.openai import OpenAIProvider


def test_openai_provider_config_from_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = OpenAIProvider.create_config("gpt-4o", credentials={"api_key": "k1"})
    assert config.credentials == {"api_key": "k1"}


def test_openai_provider_config_from_uppercase_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = OpenAIProvider.create_config("gpt-4o", credentials={"OPENAI_API_KEY": "k2"})
    assert config.credentials == {"api_key": "k2"}


def test_openai_provider_config_from_env(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = OpenAIProvider.create_config("gpt-4o")
    assert config.credentials is None


def test_openai_provider_config_env_set_ignores_uppercase(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    config = OpenAIProvider.create_config("gpt-4o", credentials={"OPENAI_API_KEY": "k2"})
    assert config.credentials is None


def test_openai_provider_config_no_env_no_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    config = OpenAIProvider.create_config("gpt-4o", credentials={})
    assert config.credentials is None


def test_openai_provider_validate_and_required_credentials():
    assert OpenAIProvider.validate_model("gpt-4o") is True
    assert OpenAIProvider.validate_model("unknown") is False
    assert OpenAIProvider.get_required_credentials() == ["OPENAI_API_KEY"]


def test_openai_provider_check_credentials(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert OpenAIProvider.check_credentials() is False
    monkeypatch.setenv("OPENAI_API_KEY", "k")
    assert OpenAIProvider.check_credentials() is True


def test_google_provider_config_from_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = GoogleProvider.create_config("gemini-1.5-pro", credentials={"api_key": "k1"})
    assert config.credentials == {"api_key": "k1"}


def test_google_provider_config_from_uppercase_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = GoogleProvider.create_config("gemini-1.5-pro", credentials={"GOOGLE_API_KEY": "k2"})
    assert config.credentials == {"api_key": "k2"}


def test_google_provider_config_env_set_ignores_uppercase(monkeypatch):
    monkeypatch.setenv("GOOGLE_API_KEY", "env")
    config = GoogleProvider.create_config("gemini-1.5-pro", credentials={"GOOGLE_API_KEY": "k2"})
    assert config.credentials is None


def test_google_provider_config_no_env_no_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    config = GoogleProvider.create_config("gemini-1.5-pro", credentials={})
    assert config.credentials is None


def test_google_provider_validate_and_required_credentials():
    assert GoogleProvider.validate_model("gemini-1.5-pro") is True
    assert GoogleProvider.validate_model("other") is False
    assert GoogleProvider.get_required_credentials() == ["GOOGLE_API_KEY"]


def test_google_provider_check_credentials(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GoogleProvider.check_credentials() is False
    monkeypatch.setenv("GOOGLE_API_KEY", "k")
    assert GoogleProvider.check_credentials() is True


def test_bedrock_provider_validate_variants():
    assert BedrockProvider.validate_model("anthropic.claude-3-haiku-20240307-v1:0") is True
    assert BedrockProvider.validate_model("amazon.titan") is True
    assert BedrockProvider.validate_model("cohere.command") is True
    assert BedrockProvider.validate_model("unknown") is False


def test_bedrock_provider_create_config_uses_credentials_and_region(monkeypatch):
    monkeypatch.delenv("AWS_DEFAULT_REGION", raising=False)
    config = BedrockProvider.create_config(
        "anthropic.claude-3-haiku-20240307-v1:0",
        credentials={
            "access_key_id": "a",
            "secret_access_key": "s",
            "region": "us-west-2",
        },
    )
    assert config.credentials == {"access_key_id": "a", "secret_access_key": "s"}
    assert config.region == "us-west-2"


def test_bedrock_provider_create_config_uses_env_region(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    config = BedrockProvider.create_config("anthropic.claude-v2", credentials=None)
    assert config.region == "us-east-2"


def test_bedrock_provider_create_config_with_region_param(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-east-2")
    config = BedrockProvider.create_config(
        "anthropic.claude-v2",
        credentials=None,
        region="eu-west-1",
    )
    assert config.region == "eu-west-1"


def test_bedrock_provider_create_config_uppercase_credentials():
    config = BedrockProvider.create_config(
        "anthropic.claude-v2",
        credentials={"AWS_ACCESS_KEY_ID": "a", "AWS_SECRET_ACCESS_KEY": "s"},
    )
    assert config.credentials == {"access_key_id": "a", "secret_access_key": "s"}


def test_bedrock_provider_required_credentials():
    required = BedrockProvider.get_required_credentials()
    assert "AWS_ACCESS_KEY_ID" in required
    assert "AWS_SECRET_ACCESS_KEY" in required


def test_bedrock_provider_check_credentials(monkeypatch):
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert BedrockProvider.check_credentials() is False
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "a")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "s")
    assert BedrockProvider.check_credentials() is True
