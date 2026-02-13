-- Example: Registry-backed model with fallback configuration.

registry_model = Model {
  type = "registry",
  name = "imdb_nb",
  version = "champion",
  registry_dir = "examples/models/registry",
  fallback = {
    type = "mock",
    value = {label = "mocked", confidence = 1.0}
  },
  input = {text = "string"},
  output = {label = "string", confidence = "float"}
}

Procedure "main" {
  input = {
    text = field.string{default = "An excellent movie"}
  },
  output = {
    label = field.string{},
    confidence = field.number{}
  },
  state = {},
  function(input)
    local result = registry_model({text = input.text})
    local output = result.output or result
    return {
      label = output.label or "unknown",
      confidence = output.confidence or 0.0
    }
  end
}
