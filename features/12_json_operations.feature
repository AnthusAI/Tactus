Feature: JSON Operations
  As a workflow developer
  I want to parse and generate JSON
  So that workflows can work with structured data

  Background:
    Given a Tactus workflow environment
    And the JSON primitive is initialized

  Scenario: Parsing valid JSON string
    Given a JSON string:
      """
      {"name": "Alice", "age": 30, "active": true}
      """
    When I parse the JSON
    Then I should have a Python dict
    And field "name" should equal "Alice"
    And field "age" should equal 30
    And field "active" should be true

  Scenario: Generating JSON from data
    Given a Python dict:
      | key    | value  |
      | name   | Bob    |
      | score  | 95     |
    When I convert to JSON
    Then the result should be valid JSON string
    And parsing it back should give the original data

  Scenario: Handling nested JSON structures
    Given a JSON string with nested objects:
      """
      {
        "user": {
          "name": "Alice",
          "address": {
            "city": "San Francisco",
            "state": "CA"
          }
        }
      }
      """
    When I parse the JSON
    Then I should be able to access "user.name"
    And "user.address.city" should equal "San Francisco"

  Scenario: JSON arrays
    Given a JSON string:
      """
      {"items": [1, 2, 3, 4, 5]}
      """
    When I parse the JSON
    Then field "items" should be a list
    And the list should have 5 elements
    And the first element should be 1

  Scenario: Invalid JSON handling
    Given an invalid JSON string:
      """
      {name: "Alice", "age": 30}
      """
    When I try to parse the JSON
    Then a JSON parse error should be raised
    And the workflow can handle the error

  Scenario: Pretty printing JSON
    Given a data structure with nested objects
    When I convert to JSON with pretty=true
    Then the output should be formatted with indentation
    And it should be human-readable

  Scenario: JSON schema validation
    Given a JSON schema:
      """
      {
        "type": "object",
        "properties": {
          "name": {"type": "string"},
          "age": {"type": "number"}
        },
        "required": ["name"]
      }
      """
    When I validate JSON data against the schema
    Then valid data should pass validation
    And invalid data should fail validation

  Scenario: Working with JSON in workflow state
    When I set state "config" to parsed JSON:
      """
      {"debug": true, "timeout": 30}
      """
    Then state "config" should be a dict
    And I can access config.debug directly
    And converting state "config" back to JSON should work
