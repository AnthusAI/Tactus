from tactus.providers.bedrock import BedrockProvider
from tactus.providers.google import GoogleProvider


def test_bedrock_provider_validation_and_credentials(monkeypatch):
    assert BedrockProvider.validate_model("anthropic.claude-3-5-sonnet-20240620-v1:0")
    assert BedrockProvider.validate_model("amazon.titan-text-premier")
    assert not BedrockProvider.validate_model("unknown-model")

    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)
    assert BedrockProvider.check_credentials() is False

    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "secret")
    assert BedrockProvider.check_credentials() is True


def test_bedrock_provider_create_config_uses_credentials_and_region(monkeypatch):
    monkeypatch.setenv("AWS_DEFAULT_REGION", "us-west-2")

    config = BedrockProvider.create_config(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        credentials={
            "AWS_ACCESS_KEY_ID": "key",
            "AWS_SECRET_ACCESS_KEY": "secret",
            "AWS_DEFAULT_REGION": "us-east-2",
        },
    )

    assert config.provider_name == BedrockProvider.PROVIDER_NAME
    assert config.model_id.startswith("anthropic.")
    assert config.credentials["access_key_id"] == "key"
    assert config.credentials["secret_access_key"] == "secret"
    assert config.region == "us-east-2"


def test_google_provider_validation_and_credentials(monkeypatch):
    assert GoogleProvider.validate_model("gemini-1.5-pro")
    assert GoogleProvider.validate_model("gemini-custom")
    assert not GoogleProvider.validate_model("other-model")

    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
    assert GoogleProvider.check_credentials() is False

    monkeypatch.setenv("GOOGLE_API_KEY", "key")
    assert GoogleProvider.check_credentials() is True


def test_google_provider_create_config_uses_api_key(monkeypatch):
    monkeypatch.delenv("GOOGLE_API_KEY", raising=False)

    config = GoogleProvider.create_config(
        model_id="gemini-2.0-flash-exp",
        credentials={"api_key": "from-credentials"},
        extra="value",
    )

    assert config.provider_name == GoogleProvider.PROVIDER_NAME
    assert config.model_id == "gemini-2.0-flash-exp"
    assert config.credentials["api_key"] == "from-credentials"
    assert config.region is None
    assert config.additional_config["extra"] == "value"
