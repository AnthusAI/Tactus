-- Example: Train + run Naive Bayes on IMDB (HuggingFace)
-- Train a real model: tactus train examples/47-model-naive-bayes-train.tac --model imdb_nb
-- Test real model: tactus test examples/47-model-naive-bayes-train.tac
-- Test logic only (mocked): tactus test examples/47-model-naive-bayes-train.tac --mock

Model "imdb_nb" {
  type = "registry",
  name = "imdb_nb",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" },
  training = {
    data = {
      source = "hf",
      name = "imdb",
      train = "train",
      test = "test",
      shuffle = { train = true, test = true },
      limit = { train = 25000, test = 25000 },
      seed = 42,
      text_field = "text",
      label_field = "label"
    },
    candidates = {
      {
        name = "nb-tfidf",
        trainer = "naive_bayes",
        hyperparameters = {
          alpha = 1.0,
          max_features = 50000,
          ngram_min = 1,
          ngram_max = 2
        }
      }
    }
  }
}

Procedure {
  input = {
    text = field.string{required = true}
  },
  output = {
    label = field.string{required = true},
    confidence = field.number{required = false},
    decision = field.string{required = true}
  },
  function(input)
    local classifier = Model("imdb_nb")
    local result = classifier({text = input.text})
    local output = result.output or result

    local decision = "review"
    if output.confidence ~= nil and output.confidence >= 0.7 then
      if output.label == "positive" then
        decision = "yes"
      else
        decision = "no"
      end
    end

    return {
      label = output.label,
      confidence = output.confidence,
      decision = decision
    }
  end
}

-- Mocked model responses for deterministic specs.
-- Run mocked: tactus test examples/47-model-naive-bayes-train.tac --mock
Mocks {
  imdb_nb = {
    conditional = {
      {when = {text = "A wonderful movie with great acting."}, returns = {label = "positive", confidence = 0.92}},
      {when = {text = "This was a terrible movie with bad acting."}, returns = {label = "negative", confidence = 0.87}},
      {when = {text = "A confusing movie with uneven pacing."}, returns = {label = "positive", confidence = 0.42}}
    }
  }
}

Specification([[
Feature: Registry-backed Naive Bayes classifier
  Scenario: Positive review routes to yes
    Given the procedure has started
    And the input text is "A wonderful movie with great acting."
    When the procedure runs
    Then the output decision should be "yes"
    And the output label should be "positive"
    And the procedure should complete successfully

  Scenario: Negative review routes to no
    Given the procedure has started
    And the input text is "This was a terrible movie with bad acting."
    When the procedure runs
    Then the output decision should be "no"
    And the output label should be "negative"
    And the procedure should complete successfully

  Scenario: Low confidence routes to review
    Given the procedure has started
    And the input text is "A confusing movie with uneven pacing."
    When the procedure runs
    Then the output decision should be "review"
    And the output confidence should exist
    And the procedure should complete successfully
]])
