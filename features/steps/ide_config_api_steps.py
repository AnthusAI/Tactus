"""BDD steps for IDE config API."""

import sys
import tempfile
from pathlib import Path
from unittest import mock

from behave import given, when, then
from flask import Flask

project_root = Path(__file__).resolve().parents[2]
backend_path = project_root / "tactus-ide" / "backend"
sys.path.insert(0, str(backend_path))

import config_server  # noqa: E402


def _setup_temp_context(context):
    temp_dir = tempfile.TemporaryDirectory()
    context._temp_config_dir = temp_dir
    context.temp_root = Path(temp_dir.name)


@given("a config API client")
def step_create_config_client(context):
    _setup_temp_context(context)
    app = Flask("tactus_ide_tests", root_path=str(project_root))
    config_server.register_config_routes(app)
    context.client = app.test_client()


@when("I request the config")
def step_get_config(context):
    with mock.patch.object(config_server.Path, "cwd", return_value=context.temp_root):
        with mock.patch.object(config_server.Path, "home", return_value=context.temp_root):
            context.get_response = context.client.get("/api/config")


@then("the config response should include effective config")
def step_verify_config(context):
    payload = context.get_response.get_json()
    assert "config" in payload
    assert "project_config" in payload


@when("I save a project config")
def step_save_project_config(context):
    payload = {"config": {"default_provider": "openai"}, "targetFile": "project"}
    with mock.patch.object(config_server.Path, "cwd", return_value=context.temp_root):
        with mock.patch.object(config_server.Path, "home", return_value=context.temp_root):
            context.save_response = context.client.post("/api/config", json=payload)


@then("the config save should succeed")
def step_verify_save(context):
    payload = context.save_response.get_json()
    assert payload.get("success") is True


@when("I save config changes by source")
def step_save_by_source(context):
    payload = {
        "changes": {"default_provider": "openai"},
        "target_strategy": "force_project",
    }
    with mock.patch.object(config_server.Path, "cwd", return_value=context.temp_root):
        with mock.patch.object(config_server.Path, "home", return_value=context.temp_root):
            context.source_save_response = context.client.post(
                "/api/config/save-by-source", json=payload
            )


@then("the source save should succeed")
def step_verify_source_save(context):
    payload = context.source_save_response.get_json()
    assert payload.get("success") is True
    assert "saved_to" in payload


@when("I validate a config payload")
def step_validate_config(context):
    payload = {"config": {"default_provider": "unknown"}}
    context.validate_response = context.client.post("/api/config/validate", json=payload)


@then("the config validation should return warnings")
def step_verify_validation(context):
    payload = context.validate_response.get_json()
    assert payload.get("valid") is True
    assert payload.get("warnings")


@when("I save config without a body")
def step_save_config_no_body(context):
    context.error_response = context.client.post("/api/config", json={})


@when("I save config with invalid target")
def step_save_config_invalid_target(context):
    payload = {"config": {"default_provider": "openai"}, "targetFile": "invalid"}
    with mock.patch.object(config_server.Path, "cwd", return_value=context.temp_root):
        with mock.patch.object(config_server.Path, "home", return_value=context.temp_root):
            context.error_response = context.client.post("/api/config", json=payload)


@when("I validate config without a body")
def step_validate_config_no_body(context):
    context.error_response = context.client.post("/api/config/validate", json={})


@when("I validate config with non-object")
def step_validate_config_non_object(context):
    context.error_response = context.client.post("/api/config/validate", json={"config": "text"})


@then('the config error should mention "{message}"')
def step_verify_config_error(context, message):
    payload = context.error_response.get_json()
    if "error" in payload:
        assert message in payload["error"]
    else:
        errors = payload.get("errors", [])
        assert any(message in error for error in errors)
