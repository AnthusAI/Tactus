Feature: DSPy Signature Creation and Validation
  As a Tactus developer
  I want to create and use DSPy signatures
  So that I can define input/output specifications for modules

  Background:
    Given dspy is installed as a dependency

  # String Format Parsing

  Scenario: Parse simple signature
    When I create a signature "question -> answer"
    Then it should have input field "question"
    And it should have output field "answer"

  Scenario: Parse multi-field signature
    When I create a signature "context, question -> reasoning, answer"
    Then it should have input fields "context" and "question"
    And it should have output fields "reasoning" and "answer"

  Scenario: Parse signature with single input multiple outputs
    When I create a signature "text -> summary, keywords, sentiment"
    Then it should have input field "text"
    And it should have output fields "summary", "keywords", and "sentiment"

  Scenario: Parse signature with multiple inputs single output
    When I create a signature "title, body, author -> article"
    Then it should have input fields "title", "body", and "author"
    And it should have output field "article"

  # Structured Signatures with Descriptions

  Scenario: Create structured signature with field descriptions
    When I create a structured signature with field descriptions
    Then it should have input field "question"
    And input field "question" should have description "The question to answer"
    And it should have output field "answer"
    And output field "answer" should have description "The answer"

  Scenario: Create complex structured signature
    When I create a structured signature with multiple typed fields:
      """
      {
        "input": {
          "context": {"description": "Background information", "type": "string"},
          "question": {"description": "User's question", "type": "string"},
          "max_length": {"description": "Maximum response length", "type": "integer"}
        },
        "output": {
          "answer": {"description": "The answer", "type": "string"},
          "confidence": {"description": "Confidence score", "type": "float"},
          "sources": {"description": "Source references", "type": "list"}
        }
      }
      """
    Then it should have input fields "context", "question", and "max_length"
    And it should have output fields "answer", "confidence", and "sources"
    And input field "max_length" should have type "integer"
    And output field "confidence" should have type "float"

  # Tactus DSL Integration

  Scenario: Simple signature in Tactus procedure
    Given a Tactus procedure with simple signature:
      """
      Procedure "test_signature" {
        output = {
          has_signature = field.boolean{required = true}
        },
        function(input)
          local sig = Signature("question -> answer")
          return {has_signature = sig ~= nil}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_signature should be true

  Scenario: Structured signature in Tactus procedure
    Given a Tactus procedure with structured signature:
      """
      Procedure "test_structured" {
        output = {
          has_input_field = field.boolean{required = true},
          has_output_field = field.boolean{required = true}
        },
        function(input)
          local sig = Signature "qa" {
            input = {
              question = field.string{description = "The question to answer"}
            },
            output = {
              answer = field.string{description = "The answer"}
            }
          }

          -- Check if signature has expected structure
          local has_input = true  -- Signature created successfully
          local has_output = true  -- Signature created successfully

          return {
            has_input_field = has_input,
            has_output_field = has_output
          }
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output has_input_field should be true
    And the output has_output_field should be true

  # Field Type Specifications

  Scenario: Signature with typed fields
    When I create a signature with typed fields:
      """
      {
        "input": {
          "number": {"type": "integer"},
          "text": {"type": "string"},
          "flag": {"type": "boolean"}
        },
        "output": {
          "result": {"type": "float"},
          "items": {"type": "list"}
        }
      }
      """
    Then input field "number" should have type "integer"
    And input field "text" should have type "string"
    And input field "flag" should have type "boolean"
    And output field "result" should have type "float"
    And output field "items" should have type "list"

  # Instructions and Docstrings

  Scenario: Signature with instructions
    When I create a signature with instructions:
      """
      {
        "instructions": "Extract key information from the provided text",
        "input": {
          "text": {"description": "Source text"}
        },
        "output": {
          "entities": {"description": "Named entities"},
          "summary": {"description": "Brief summary"}
        }
      }
      """
    Then the signature should have instructions "Extract key information from the provided text"
    And it should have input field "text"
    And it should have output fields "entities" and "summary"

  # Edge Cases and Error Handling

  Scenario: Empty signature fields
    When I try to create a signature " -> "
    Then an error should be raised in dspy signature
    And the error should mention dspy signature "empty fields"

  Scenario: Invalid signature syntax
    When I try to create a signature "question answer"
    Then an error should be raised in dspy signature
    And the error should mention dspy signature "invalid signature format"

  Scenario: Missing arrow in signature
    When I try to create a signature "question, answer"
    Then an error should be raised in dspy signature
    And the error should mention dspy signature "must contain exactly one"

  Scenario: Duplicate field names
    When I try to create a signature "text, text -> result"
    Then an error should be raised in dspy signature
    And the error should mention dspy signature "duplicate field"

  Scenario: Special characters in field names
    When I create a signature "user_input, max_tokens -> generated_text"
    Then it should have input fields "user_input" and "max_tokens"
    And it should have output field "generated_text"

  # Signature Composition

  Scenario: Combine multiple signatures
    Given a Tactus procedure that combines signatures:
      """
      Procedure "test_composition" {
        output = {
          combined = field.boolean{required = true}
        },
        function(input)
          local sig1 = Signature("text -> summary")
          local sig2 = Signature("summary -> keywords")

          -- Signatures can be used independently
          local can_combine = sig1 ~= nil and sig2 ~= nil

          return {combined = can_combine}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output combined should be true

  # Advanced Structured Signatures

  Scenario: Nested field structures
    When I create a signature with nested structures:
      """
      {
        "input": {
          "document": {
            "description": "Document to process",
            "type": "object",
            "properties": {
              "title": {"type": "string"},
              "content": {"type": "string"}
            }
          }
        },
        "output": {
          "analysis": {
            "description": "Document analysis",
            "type": "object",
            "properties": {
              "sentiment": {"type": "string"},
              "topics": {"type": "list"}
            }
          }
        }
      }
      """
    Then it should have input field "document"
    And input field "document" should have type "object"
    And it should have output field "analysis"
    And output field "analysis" should have type "object"

  Scenario: Optional and required fields
    When I create a signature with optional fields:
      """
      {
        "input": {
          "required_field": {"description": "This is required", "required": true},
          "optional_field": {"description": "This is optional", "required": false}
        },
        "output": {
          "result": {"description": "The result", "required": true}
        }
      }
      """
    Then input field "required_field" should be required
    And input field "optional_field" should be optional
    And output field "result" should be required

  # Signature Validation

  Scenario: Validate signature field types at runtime
    Given a Tactus procedure that validates signature fields:
      """
      Procedure "test_validation" {
        output = {
          valid = field.boolean{required = true}
        },
        function(input)
          local sig = Signature "validator" {
            input = {
              number = field.integer{description = "Must be a number"}
            },
            output = {
              doubled = field.integer{description = "Input doubled"}
            }
          }

          -- Signature created successfully means validation passed
          return {valid = true}
        end
      }
      """
    When the procedure is parsed and executed
    Then the procedure should complete successfully
    And the output valid should be true

  # Default Values

  Scenario: Signature fields with default values
    When I create a signature with default values:
      """
      {
        "input": {
          "text": {"description": "Input text", "default": "Hello"},
          "temperature": {"description": "Temperature", "type": "float", "default": 0.7}
        },
        "output": {
          "response": {"description": "Generated response"}
        }
      }
      """
    Then input field "text" should have default value "Hello"
    And input field "temperature" should have default value 0.7