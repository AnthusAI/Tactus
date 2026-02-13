-- Example: A/B routing between two candidates

Model "candidate_a" { type = "mock", value = "A" }
Model "candidate_b" { type = "mock", value = "B" }

Model "ab_classifier" {
    type = "ab_test",
    arms = {
        { type = "mock", value = "A" },
        { type = "mock", value = "B" },
    },
    weights = {0.25, 0.75},
}

procedure "route" {
    input = { text = "string" },
    output = { label = "string", arm = "integer" },
    function(input)
        local result = ab_classifier:predict({text = input.text})
        return {
            label = result.output or result.result,
            arm = (result.metadata and result.metadata.arm_index) or (result.meta and result.meta.arm_index)
        }
    end
}
