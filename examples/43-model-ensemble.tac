-- Example: Ensemble vote across two mock models

Model "arm_a" {
    type = "mock",
    value = "positive",
}

Model "arm_b" {
    type = "mock",
    value = "negative",
}

Model "sentiment_ensemble" {
    type = "ensemble",
    strategy = "vote",
    members = {
        { type = "mock", value = "positive" },
        { type = "mock", value = "negative" },
        { type = "mock", value = "positive" },
    }
}

procedure "classify" {
    input = { text = "string" },
    output = { label = "string" },
    function(input)
        local result = sentiment_ensemble:predict({text = input.text})
        return { label = result.output or result.result or result }
    end
}
