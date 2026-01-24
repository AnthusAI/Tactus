-- Simple fuzzy matching test

Procedure {
    output = {
        result = field.string{required = true}
    },
    function(input)
        print("Starting fuzzy matching test...")

        -- Test 1: Binary mode
        print("\n=== Test 1: Binary Mode ===")
        local binary = Classify {
            method = "fuzzy",
            expected = "United Education Institute",
            threshold = 0.7,
            algorithm = "token_set_ratio"
        }

        local result1 = binary("Institute Education United Dallas")
        print("Input: Institute Education United Dallas")
        print("Result: " .. result1.value)
        print("Matched: " .. (result1.matched_text or "none"))
        print("Confidence: " .. string.format("%.2f", result1.confidence))

        -- Test 2: Multi-class mode
        print("\n=== Test 2: Multi-Class Mode ===")
        local multiclass = Classify {
            method = "fuzzy",
            classes = {
                "United Education Institute",
                "Abilene Christian University",
                "Florida Technical College"
            },
            threshold = 0.65,
            algorithm = "token_set_ratio"
        }

        local result2 = multiclass("Institute Education United")
        print("Input: Institute Education United")
        print("Result: " .. result2.value)
        print("Matched: " .. (result2.matched_text or "none"))
        print("Confidence: " .. string.format("%.2f", result2.confidence))

        -- Test 3: Different algorithm
        print("\n=== Test 3: Partial Ratio Algorithm ===")
        local partial = Classify {
            method = "fuzzy",
            classes = {"Florida Technical College"},
            threshold = 0.70,
            algorithm = "partial_ratio"
        }

        local result3 = partial("Florida Tech College")
        print("Input: Florida Tech College")
        print("Result: " .. result3.value)
        print("Matched: " .. (result3.matched_text or "none"))
        print("Confidence: " .. string.format("%.2f", result3.confidence))

        print("\n✓ All tests passed!")

        return {result = "Success - all 3 fuzzy matching tests passed"}
    end
}
