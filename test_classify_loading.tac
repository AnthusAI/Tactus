-- Test that classify module loads correctly

print("Testing module loading...")

-- Test 1: Load main module
local classify = require("tactus.classify")
print("✓ Main module loaded")

-- Test 2: Verify exports
assert(classify.BaseClassifier, "BaseClassifier not exported")
assert(classify.LLMClassifier, "LLMClassifier not exported")
assert(classify.FuzzyMatchClassifier, "FuzzyMatchClassifier not exported")
assert(classify.class, "class helper not exported")
print("✓ All classes exported")

-- Test 3: Load specific classifier
local llm_module = require("tactus.classify.llm")
assert(llm_module.LLMClassifier, "LLMClassifier not in llm module")
print("✓ Specific module loading works")

-- Test 4: Create FuzzyMatchClassifier instance
local fuzzy = classify.FuzzyMatchClassifier:new {
    expected = "hello",
    threshold = 0.8
}
assert(fuzzy, "Could not create FuzzyMatchClassifier")
print("✓ FuzzyMatchClassifier instantiation works")

-- Test 5: Test classification
local result = fuzzy:classify("helo")
assert(result.value == "Yes", "Expected 'Yes' for fuzzy match, got: " .. tostring(result.value))
assert(result.confidence, "Expected confidence score")
print("✓ Fuzzy classification works: value=" .. result.value .. ", confidence=" .. tostring(result.confidence))

print("\n✅ All module loading tests passed!")

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        return {result = "success"}
    end
}
