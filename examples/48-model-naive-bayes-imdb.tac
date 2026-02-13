-- Example: Use registry-backed Naive Bayes classifier (trained via tactus train)

Procedure {
  input = {
    text = field.string{required = true}
  },
  output = {
    label = field.string{required = true},
    confidence = field.number{required = false}
  },
  function(input)
    local classify = require("tactus.classify")
    local classifier = classify.NaiveBayesClassifier:new {
      name = "imdb_nb",
      version = "latest"
    }

    local result = classifier:classify(input.text)
    return {
      label = result.value,
      confidence = result.confidence
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
