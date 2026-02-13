-- Example: Use registry-backed Naive Bayes classifier (trained via tactus train)

Model "imdb_nb" {
  type = "registry",
  name = "imdb_nb",
  version = "latest",
  input = { text = "string" },
  output = { label = "string", confidence = "float" }
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
    -- Registry-backed model handle (trained via tactus train)
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
