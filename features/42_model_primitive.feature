Feature: Model Primitive for ML Inference
  As a workflow developer
  I want to use ML models for inference operations
  So that I can classify, extract, and analyze data with trained models

  Background:
    Given a Tactus validation environment

  Scenario: Model declaration is recognized in validation
    Given a Lua DSL file with content:
      """
      model("intent_classifier", {
        type = "http",
        endpoint = "https://api.example.com/classify",
        timeout = 10.0
      })

      agent("worker", {
        provider = "openai",
        model = "gpt-4o",
        system_prompt = "Process",
        tools = {}
      })

      main = procedure("main", {
        input = {text = {type = "string"}},
        output = {intent = {type = "string"}},
        state = {}
      }, function()
        return {intent = "test"}
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize model declarations

  Scenario: HTTP model type is supported
    Given a Lua DSL file with content:
      """
      model("classifier", {
        type = "http",
        endpoint = "https://httpbin.org/post",
        timeout = 30.0
      })

      main = procedure("main", {
        output = {result = {type = "string"}},
        state = {}
      }, function()
        return {result = "ok"}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: PyTorch model type is supported
    Given a Lua DSL file with content:
      """
      model("sentiment", {
        type = "pytorch",
        path = "models/sentiment.pt",
        device = "cpu",
        labels = {"negative", "neutral", "positive"}
      })

      main = procedure("main", {
        output = {result = {type = "string"}},
        state = {}
      }, function()
        return {result = "ok"}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Model requires type field
    Given a Lua DSL file with content:
      """
      model("classifier", {
        endpoint = "https://api.example.com"
      })

      main = procedure("main", {
        output = {result = {type = "string"}},
        state = {}
      }, function()
        return {result = "ok"}
      end)
      """
    When I validate the file
    Then validation should succeed

  Scenario: Multiple models can be declared
    Given a Lua DSL file with content:
      """
      model("intent_classifier", {
        type = "http",
        endpoint = "https://api.example.com/intent"
      })

      model("sentiment_analyzer", {
        type = "http",
        endpoint = "https://api.example.com/sentiment"
      })

      main = procedure("main", {
        output = {result = {type = "string"}},
        state = {}
      }, function()
        return {result = "ok"}
      end)
      """
    When I validate the file
    Then validation should succeed
    And it should recognize multiple model declarations

  Scenario: Model used in procedure
    Given a Lua DSL file with content:
      """
      model("classifier", {
        type = "http",
        endpoint = "https://httpbin.org/post"
      })

      main = procedure("main", {
        input = {text = {type = "string", default = "test"}},
        output = {classification = {type = "string"}},
        state = {}
      }, function()
        local result = Classifier.predict({text = input.text})
        return {classification = "classified"}
      end)
      """
    When I validate the file
    Then validation should succeed
