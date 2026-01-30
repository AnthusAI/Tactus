Feature: IDE Config API
  As an IDE client
  I want configuration endpoints to respond
  So that settings can be read and saved

  Background:
    Given a config API client

  Scenario: Get config
    When I request the config
    Then the config response should include effective config

  Scenario: Save project config
    When I save a project config
    Then the config save should succeed

  Scenario: Save config by source
    When I save config changes by source
    Then the source save should succeed

  Scenario: Validate config
    When I validate a config payload
    Then the config validation should return warnings

  Scenario: Save config requires body
    When I save config without a body
    Then the config error should mention "Missing request body"

  Scenario: Save config rejects invalid target
    When I save config with invalid target
    Then the config error should mention "Invalid target"

  Scenario: Validate config requires body
    When I validate config without a body
    Then the config error should mention "Missing request body"

  Scenario: Validate config rejects non-object
    When I validate config with non-object
    Then the config error should mention "Config must be an object"
