Feature: Model Primitive for ML Inference
  As a workflow developer
  I want to use ML models for inference operations
  So that I can classify, extract, and analyze data with trained models

  Background:
  Given a Tactus validation environment

  Scenario: Model declaration is recognized in validation
  Given a Lua DSL file with content:
  """
  intent_classifier = Model {
    type = "http",
    endpoint = "https://api.example.com/classify",
    timeout = 10.0
  }

  worker = Agent {
  provider = "openai",
  model = "gpt-4o",
  system_prompt = "Process",
  tools = {}
  }

  Procedure {
    input = {
      name = field.string{}
      },
    state = {},
    function(input)
      return {intent = "test"}
    end
  }
  """
  When I validate the file
  Then validation should succeed
  And it should recognize model declarations

  Scenario: HTTP model type is supported
  Given a Lua DSL file with content:
  """
  classifier = Model {
    type = "http",
    endpoint = "https://httpbin.org/post",
    timeout = 30.0
  }

  main = Procedure "main" {
    output = {result = field.string{}},
    state = {},
    function(input)
      return {result = "ok"}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: PyTorch model type is supported
  Given a Lua DSL file with content:
  """
  sentiment = Model {
    type = "pytorch",
    path = "models/sentiment.pt",
    device = "cpu",
    labels = {"negative", "neutral", "positive"}
  }

  main = Procedure "main" {
    output = {result = field.string{}},
    state = {},
    function(input)
      return {result = "ok"}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Model requires type field
  Given a Lua DSL file with content:
  """
  classifier = Model {
    endpoint = "https://api.example.com"
  }

  main = Procedure "main" {
    output = {result = field.string{}},
    state = {},
    function(input)
      return {result = "ok"}
    end
  }
  """
  When I validate the file
  Then validation should succeed

  Scenario: Multiple models can be declared
  Given a Lua DSL file with content:
  """
  intent_classifier = Model {
    type = "http",
    endpoint = "https://api.example.com/intent"
  }

  sentiment_analyzer = Model {
    type = "http",
    endpoint = "https://api.example.com/sentiment"
  }

  main = Procedure "main" {
    output = {result = field.string{}},
    state = {},
    function(input)
      return {result = "ok"}
    end
  }
  """
  When I validate the file
  Then validation should succeed
  And it should recognize multiple model declarations

  Scenario: Model used in procedure
  Given a Lua DSL file with content:
  """
  classifier = Model {
    type = "http",
    endpoint = "https://httpbin.org/post"
  }

  main = Procedure "main" {
    input = {
      name = field.string{default = "test"}
      },
    state = {},
    function(input)
      local result = Classifier.predict({text = input.text})
      return {classification = "classified"}
    end
  }
  """
  When I validate the file
  Then validation should succeed
