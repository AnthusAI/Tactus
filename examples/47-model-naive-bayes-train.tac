-- Example: Train + run Naive Bayes on IMDB (HuggingFace)

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
    confidence = field.number{required = false}
  },
  function(input)
    local classifier = Model("imdb_nb")
    local result = classifier({text = input.text})
    local output = result.output or result
    return {
      label = output.label,
      confidence = output.confidence
    }
  end
}

Specification([[
Feature: Registry-backed Naive Bayes classifier
  Scenario: Classify a positive review
    Given the procedure has started
    And the input text is "A wonderful movie with great acting."
    When the procedure runs
    Then the procedure should complete successfully
]])
