-- Example: HTTP model usage with a safe mock-mode fallback.

http_classifier = Model {
  type = "http",
  endpoint = "https://httpbin.org/post",
  timeout = 10.0,
  input = {text = "string"},
  output = {label = "string", confidence = "float"}
}

Procedure "main" {
  input = {
    text = field.string{default = "hello"}
  },
  output = {
    label = field.string{},
    confidence = field.number{}
  },
  state = {},
  function(input)
    if os.getenv("TACTUS_MOCK_MODE") == "1" then
      return {label = "mocked", confidence = 1.0}
    end

    local result = http_classifier({text = input.text})
    local output = result.output or result
    return {
      label = output.label or "unknown",
      confidence = output.confidence or 0.0
    }
  end
}
