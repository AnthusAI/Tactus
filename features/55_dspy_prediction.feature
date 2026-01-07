Feature: DSPy Prediction Objects and Field Access
  As a Tactus developer
  I want to work with DSPy prediction objects
  So that I can access and manipulate module outputs

  Background:
    Given dspy is installed as a dependency

  # Basic Prediction Creation

  Scenario: Create Prediction with fields
    When I create a Prediction with fields
    Then I can access prediction fields as attributes
    And I can get prediction data as a dictionary

  Scenario: Create Prediction with single field
    When I create a Prediction with field "result" value "success"
    Then the prediction should have field "result"
    And the field "result" should equal "success"

  Scenario: Create Prediction with multiple fields
    When I create a Prediction with fields:
      | field    | value           |
      | answer   | 42              |
      | reasoning| The calculation |
      | confidence| 0.95           |
    Then the prediction should have all fields
    And each field should have the correct value

  # Field Access Methods

  Scenario: Access field as attribute
    Given a Prediction with field "answer" value "42"
    When I access prediction.answer
    Then I should get "42"

  Scenario: Access field using get method
    Given a Prediction with field "score" value 100
    When I use prediction.get("score")
    Then I should get 100

  Scenario: Access field with default value
    Given a Prediction without field "missing"
    When I use prediction.get("missing", default="N/A")
    Then I should get "N/A"

  Scenario: Check field existence
    Given a Prediction with fields "name" and "age"
    When I check if field "name" exists
    Then it should return true
    When I check if field "address" exists
    Then it should return false

  # Dictionary Operations

  Scenario: Convert Prediction to dictionary
    Given a Prediction with multiple fields
    When I convert it to a dictionary
    Then I should get all fields as key-value pairs
    And the dictionary should be mutable

  Scenario: Create Prediction from dictionary
    Given a dictionary with keys and values:
      | key      | value    |
      | status   | complete |
      | score    | 85       |
      | passed   | true     |
    When I create a Prediction from the dictionary
    Then the prediction should have all fields
    And maintain the original values

  # Tactus DSL Integration

  Scenario: Prediction in Tactus procedure
    Given a Tactus procedure that creates a Prediction:
      """
      Procedure "test_prediction" {
        output = {
          has_field = field.boolean{required = true},
          field_value = field.string{required = true}
        },
        function(input)
          -- Create a prediction (mock)
          local pred = {
            answer = "The answer is 42",
            confidence = 0.9
          }

          return {
            has_field = pred.answer ~= nil,
            field_value = pred.answer
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_field should be true
    And the output field_value should be "The answer is 42"

  Scenario: Module returns Prediction
    Given a Tactus procedure with Module returning Prediction:
      """
      Procedure "test_module_prediction" {
        output = {
          got_prediction = field.boolean{required = true}
        },
        function(input)
          local qa = Module "qa" {
            signature = "question -> answer, confidence",
            strategy = "predict"
          }

          -- Mock module invocation
          local prediction = {
            answer = "Sample answer",
            confidence = 0.85
          }

          return {
            got_prediction = prediction ~= nil
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output got_prediction should be true

  # DSPy Prediction Wrapping

  Scenario: Wrap DSPy Prediction
    Given a DSPy Prediction object
    When I wrap it in TactusPrediction
    Then the TactusPrediction should delegate to the underlying prediction
    And all fields should be accessible

  Scenario: Unwrap to DSPy Prediction
    Given a TactusPrediction wrapper
    When I unwrap to get DSPy Prediction
    Then I should get the original DSPy object
    And it should work with DSPy modules

  # Type Preservation

  Scenario: Preserve string types
    When I create a Prediction with string field "text" value "hello"
    Then the field type should be string
    And the value should be "hello"

  Scenario: Preserve numeric types
    When I create a Prediction with numeric fields:
      | field   | value | type    |
      | integer | 42    | int     |
      | float   | 3.14  | float   |
      | score   | 100   | int     |
    Then each field should maintain its type

  Scenario: Preserve boolean types
    When I create a Prediction with boolean field "success" value true
    Then the field type should be boolean
    And the value should be true

  Scenario: Preserve list types
    When I create a Prediction with list field "items" value ["a", "b", "c"]
    Then the field type should be list
    And the list should contain all items

  Scenario: Preserve nested structures
    When I create a Prediction with nested field:
      """
      {
        "result": {
          "status": "success",
          "details": {
            "score": 95,
            "passed": true
          }
        }
      }
      """
    Then the nested structure should be preserved
    And I can access nested fields

  # Field Validation

  Scenario: Validate required fields
    Given a Prediction schema with required fields
    When I create a Prediction missing required field "answer"
    Then an error should be raised
    And the error should mention "answer is required"

  Scenario: Validate field types
    Given a Prediction schema with typed fields
    When I create a Prediction with wrong type for "age"
    Then an error should be raised
    And the error should mention "type mismatch"

  # Advanced Field Operations

  Scenario: Update prediction field
    Given a Prediction with field "status" value "pending"
    When I update field "status" to "complete"
    Then the field "status" should equal "complete"

  Scenario: Add new field to prediction
    Given a Prediction with field "answer"
    When I add field "timestamp" with current time
    Then the prediction should have both fields

  Scenario: Remove field from prediction
    Given a Prediction with fields "answer" and "debug_info"
    When I remove field "debug_info"
    Then the prediction should only have "answer"

  # Iteration and Enumeration

  Scenario: Iterate over prediction fields
    Given a Prediction with multiple fields
    When I iterate over the prediction
    Then I should get all field names and values
    And maintain the original order

  Scenario: Get all field names
    Given a Prediction with fields "a", "b", "c"
    When I get all field names
    Then I should get ["a", "b", "c"]

  Scenario: Get all field values
    Given a Prediction with values
    When I get all field values
    Then I should get a list of all values

  # Error Handling

  Scenario: Error on accessing non-existent field
    Given a Prediction without field "missing"
    When I try to access prediction.missing
    Then it should return None or raise AttributeError

  Scenario: Error on invalid field name
    When I try to create a Prediction with field "123invalid"
    Then an error should be raised
    And the error should mention "invalid field name"

  # Prediction Comparison

  Scenario: Compare two predictions
    Given two Predictions with same fields and values
    When I compare them
    Then they should be equal

  Scenario: Compare predictions with different values
    Given two Predictions with same fields but different values
    When I compare them
    Then they should not be equal

  # Serialization

  Scenario: Serialize Prediction to JSON
    Given a Prediction with various field types
    When I serialize to JSON
    Then I should get valid JSON string
    And all fields should be included

  Scenario: Deserialize Prediction from JSON
    Given a JSON string with prediction data
    When I deserialize to Prediction
    Then all fields should be restored
    And types should be preserved

  # Integration with History

  Scenario: Store Prediction in History
    Given a History and a Prediction
    When I add the Prediction to History
    Then the History should contain the prediction data
    And it should be retrievable

  # Prediction Metadata

  Scenario: Prediction with metadata
    When I create a Prediction with metadata:
      """
      {
        "fields": {"answer": "42"},
        "metadata": {
          "model": "gpt-4",
          "timestamp": "2024-01-01T10:00:00Z",
          "confidence": 0.95
        }
      }
      """
    Then the prediction should have fields and metadata
    And metadata should be accessible separately